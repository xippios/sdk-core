# ADR-0037: Client request hooks and a quota policy

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0015 · Amended 2026-11-21 by https://github.com/xippios/sdk-core/issues/364

## Context

ADR-0033 decided how the family spends an upstream's longer-window quota, and the client had
no place to keep a quota snapshot, to pause before a request or to let `classify` shape its
retries, so sdk-usda-psd built around core to prove the policy, and sdk-comtrade kept a
second client only to keep its key off public files. This record states ADR-0015 with
ADR-0016's amendment of 2026-10-24, ADR-0023's, ADR-0022's and its own amendments of
2026-10-27 and its amendment of 2026-11-18 as they stand, and changes no decision; their
history stays in ADR-0015.

## Decision

1. **Two hooks on `ClientConfig`, next to `classify`.**
   - `before_request: Callable[[httpx.Request], Awaitable[None] | None] | None` is called once
     per `request()` call, not per retry, after the cache lookup and before the rate limiter;
     a cache hit returns before it. It receives the request as built from base URL, path,
     query parameters, body and headers, without the credentials of `auth`, which apply when
     it is sent; changes to it are not sent. It may be sync or async (an awaitable result is
     awaited), may wait, and may raise a taxonomy error, in which case nothing is sent.
   - `observe: Callable[[httpx.Response], None] | None` is called with every response that
     came from the wire, each retried attempt included and a cache hit never, before
     `classify` and before the retry decision, whether or not the caller asked for the raw
     response. An exception it raises propagates: it is a programming error.
   - The request each hook sees, the one `before_request` gets and each attempt that
     `observe` gets as `response.request`, carries the marks of decision 4 that say where
     its credentials go.
2. **A quota policy on those hooks.** `QuotaPolicy(*, limit_header="x-ratelimit-limit",
   remaining_header="x-ratelimit-remaining", window=3600.0, spent=None, pause_cap=30.0,
   source=None, clock=..., sleep=asyncio.sleep)`, exported from `xippios.core` and
   `xippios.core.client`, with `QuotaSnapshot` importable from `xippios.core.client.quota`,
   implements ADR-0033's decisions 3 to 5. Johannes decided its shape of core 0.3.0 on
   2026-10-27.
   - `observe(response)` keeps a `QuotaSnapshot(limit, remaining, observed_at, resumes_at)`,
     frozen and replaced under a lock. A response with neither quota header leaves it alone;
     a missing limit keeps the last one; a count that is not ASCII digits is ignored. A 429
     marks the quota spent, and so does a response that leaves nothing; `resumes_at` is then
     a 429's `Retry-After`, or the seconds `spent` names, else `window` from now. A cache hit
     is ignored. `limit_header` or `remaining_header` set to `None` turns that header's
     reading off; with both off, the policy relies on a 429 and `spent` alone.
   - `spent(response) -> float | None`, optional, is asked about every observed response
     after the headers are read: a number marks the quota spent for that many seconds, ahead
     of `Retry-After`, so an upstream that answers a spent limit with something other than a
     429 is covered too (UN Comtrade's 403, "Quota will be replenished in HH:MM:SS").
   - Every wait that comes from upstream, through a header or `spent`, is cut to `window`,
     which is at most ten years: no refusal outlives one window, and no `resumes_at`
     overflows on a value no upstream means. `window` is the one setting for both the
     fallback wait and that ceiling: an hourly quota keeps the default 3600 s
     (api.data.gov), a daily quota sets `window=86400` (UN Comtrade's).
   - `before_request(request)` does nothing until the snapshot shows the quota spent and not
     yet back. Then it waits until `resumes_at` when that is within `pause_cap`, 30.0 s by
     default, the default `backoff_max`, the one bound of the pause, as the hook and called
     directly, logging one warning
     naming the method and path, and otherwise raises `RateLimitError` with `retry_after` set
     to the wait, saying that nothing was sent and when the quota is expected back. Messages
     and the log line carry numbers, times, the method and the path; never a host, a query,
     a key or a variable's value.
   - A request marked `xippios_auth: "none"` or `xippios_origin: "other"` (decision 4) is
     outside the quota: `before_request` neither waits nor refuses before it, and `observe`
     leaves the snapshot alone for its answer. The client's limiter still paces it, since
     the pace is the host's (ADR-0033, decision 1). A request or a response built without the
     marks, by hand or in a test, counts as before.
   - `install(config)` returns `dataclasses.replace(config,
     before_request=self.before_request, observe=self.observe)`: it reads nothing from the
     config, binds nothing per config and refuses no config with hooks of its own, which a
     source composes itself; installing again changes nothing. Since the hook `install` sets
     is `before_request` itself, a subclass's override is called through it. `snapshot()`
     reads, `reset()` forgets.
   - A `classify` reads the wait for a 429 from `snapshot()`'s `resumes_at`, since `observe`
     ran before it (decision 1).
   - The snapshot belongs to the policy instance: clients that draw on one quota, one key
     say, share one policy, and the package decides whether the snapshot is kept per key or
     per source by where it installs the instance.
3. **`classify` shapes retries.** `send_with_retries` takes `classify=`, and
   `AsyncClient.request` passes `ClientConfig.classify`. Before a 429 or 5xx is retried the
   loop calls it, at most once per attempt: a `RateLimitError` it returns sets the wait from
   its `retry_after`, else the `Retry-After` header's, so a wait beyond `backoff_max` ends
   the retries; an `UpstreamError` for a 5xx, which restates the default mapping, and `None`
   keep the status rule of ADR-0011, so a 5xx is retried when the method allows; any other
   error it returns, an `AuthError` or an `InvalidRequestError` for instance, ends them at
   once. The final response is classified as before; the loop's answer is reused, not asked
   for twice. With `raise_on_error=False` the loop stops the same way and the response is
   returned.
4. **`auth=` per request, and the reach of the client's auth.** `AsyncClient.request`, `get`,
   `get_json`, `get_answer`, `post_json` and `delete_json`, and `record` and `record_sync`,
   take `auth=` with three states, its default core's own private sentinel, mapped to
   `httpx.USE_CLIENT_DEFAULT` where the request is sent: `None` sends the request, every
   retry included, without the client's credentials, an `httpx.Auth` replaces them for that
   call, the default sends the client's. A call with `auth=None` and one with the default
   share the cache: the keyless endpoints this is for answer alike either way. A call with
   an `httpx.Auth` of its own bypasses the cache, neither looked up nor stored, since another
   identity may get another answer from the same URL. The client's `auth` goes to the base
   URL's origin alone, its scheme, host and port as httpx normalises them: a request to any
   other origin is sent without it, and an `httpx.Auth` that the call passes goes wherever
   the call sends it. It covers every auth on a client, the `EnvKeyAuth` helpers, a source's
   own bearer and `RenewingBearerAuth`. The client sets two extensions on every request it
   builds: `xippios_auth`, `"client"`, `"none"` or `"own"` for the default, `auth=None` and
   an auth of the call's own, and `xippios_origin`, `"base"` or `"other"`.
5. **A cached answer says when it was stored, and only `get_answer` stores.** Next to
   `"xippios_cache": "hit"`, a hit carries `response.extensions["xippios_cache_stored_at"]`,
   the entry's `stored_at` in epoch seconds, and on a hit a task sets `retrieved_at` from it
   (conventions §4). Every GET but a recording's (decision 6) reads the cache, and `request`,
   `get`, `get_json` and `record` store nothing: `AsyncClient.get_answer` stores a 200 within `cache_max_bytes`, where the
   cache and `cache_filter` take it, once its body decoded and, with `parse=`, its payload
   parsed, so a body that fails either is requested again on the next call. It reads the
   clock once, when the answer arrives and before the decode and the parse, and that reading
   is both the entry's `stored_at` and the miss's `retrieved_at`, so a hit and the miss that
   stored it carry one `retrieved_at`, which a test asserts equal instead of bracketing it
   with `CLOCK_SLACK`. It returns `Answer[T]`, `payload: T` with
   `retrieved_at`: `get_answer(path, ...)` an `Answer[Any]`, and `get_answer(path, ...,
   parse=T, endpoint="<operation>")` the payload parsed with core's `parse(T, payload,
   source=<the client's source>, endpoint=...)` as an `Answer[T]`. `endpoint` comes with
   `parse` and only then: `parse` without it raises `TypeError` before anything is sent. An
   entry stored without `parse=`, or for another type, is parsed again on each hit, and a hit
   that fails to parse raises and keeps its entry. A wrapper that returns a value it derives
   from the payload returns `Answer(value, answer.retrieved_at)`, an `Answer` of the value's
   type. A wrapper that needs the response calls `get` and then
   `xippios.core.client.decode_json(response, *, source=None, path=None)`, the decoding
   `get_json` does, with its `ValidationError` for a body that is not JSON; it is answered by
   an entry `get_answer` stored and stores none itself.
6. **A recording sends once.** `record` and `record_sync` send one request through the client
   they are given, its `before_request` run once and its limiter and `observe` as for any
   request, its auth held to the base URL's origin and the request marked as decision 4 has
   it, and record the answer whatever its status: never retried, whatever the client's
   `RetryPolicy` says, and never answered from the cache nor stored in it, since an answer
   the cache holds is no live exchange. `classify` is not asked, since nothing is retried or
   raised, and a failure in transit is the `TransportError` it is for `request`. A recording
   needs no client built for one attempt; a recorder that sends through `client.request` to
   rewrite a fixture before the write keeps its one-attempt client, since `record` writes
   the file itself and ADR-0042, decision 4, gives it no hook. The plan of core 0.4.0
   decided that a recording never retries.
7. **The write counterparts of `get_json`.** `AsyncClient.post_json(path, *, json=None,
   data=None, params=None, headers=None, auth=...)` and `delete_json(path, *, params=None,
   headers=None, auth=...)` send through `request`, so `classify`, the hooks, the limiter
   and ADR-0011's rule for a method that is not idempotent apply as there, `auth=` takes
   decision 4's three states, and the cache is neither read nor written, as for every method
   but GET. They decode the answer as `get_json` does, its `ValidationError` naming the path,
   and return `None` for an answer with no body at all, a 204 say, or Gmail's answer to
   `drafts.delete`; a body of whitespace is a body, and not JSON. `get_json` still refuses
   an empty body. A DELETE sends no body; one that must sends it through `request`.

## Consequences

- A package that shares one key across several of its clients installs one policy on all of
  them. Processes keep a snapshot each, and so do packages that share a key in one process,
  except behind api.data.gov, where `xippios.core.data_gov` shares one policy per process
  (ADR-0032, decision 5).
- Only a 429 or 5xx is retried at all: an answer of another status that `classify` maps to
  `RateLimitError`, UN Comtrade's 403 for a spent daily quota, is raised after one attempt.
- ADR-0033's decision 4, no request fired into a spent quota, holds for every source through
  the policy, whatever its answer to a spent limit: a 429 marks the quota spent by itself,
  and any other answer through `spent`. sdk-comtrade installs
  `QuotaPolicy(limit_header=None, remaining_header=None, window=86400, spent=...)`: its
  `x-ratelimit-*` headers describe the per-second pace, not the daily quota.
- Any source adopting the policy first checks that the `x-ratelimit-*` headers it lets the
  policy read describe the long-window quota, not a per-second or per-minute pace; otherwise
  it sets those header names to `None`.
- A source whose 429 is a pace refusal and that has no long-window quota sets `window` to the
  documented pause or installs no policy; the default window is an hourly quota's.
- A GET cached by a keyed call answers the same GET sent with `auth=None`, and the other way
  round. A source whose keyed and keyless answers differ for one URL keeps them apart with
  `cache_filter`; one that sends another identity's credentials passes that `httpx.Auth` and
  never shares an entry.
- The two hooks are general: a source can observe other headers or refuse other requests
  before they are sent, with the same placement guarantees, without subclassing
  `AsyncClient`.
- `Answer[T]` replaces sdk-comtrade's `ReferenceFile[T]` (`Answer[list[T]]`) and
  sdk-usda-nass's `ParamValues` (`Answer[list[str]]`), which their adoption of core 0.4.0
  deletes, with no alias, since no user depends on either yet.
- The testing plugin keeps offline tests free of quota pauses and of quotas left spent by a
  replay (ADR-0035, decision 4). It turns off the pause step alone, so a wait or a refusal of
  a subclass's own override of `before_request` is not neutralised.

Conventions §4, §6, §10 and §15, the definition of done's Adoption PR block, the README and
the docstrings of `AsyncClient`, `ClientConfig`, `QuotaPolicy`, `send_with_retries`,
`RenewingBearerAuth`, `xippios.core.data_gov`, the testing plugin and `record` state its
decisions from 1.28 on.

## Amendment 2026-11-21

ADR-0048, decisions 3, 4 and 6 (https://github.com/xippios/sdk-core/issues/364), amends
decision 6. A recording keeps a final answer whatever its status, a 4xx or a 5xx included, and
refuses an answer of a 1xx or a 3xx status, which is no final answer of its operation, on every
path. No recorder keeps a client built for one attempt: `rewrite=` runs a source's step inside
`record`, and `send_once` sends a recording's one request, as `record` sends it, for a source that
needs the answer itself. The rest of decision 6 stands.
