# ADR-0015: Client request hooks and a quota policy

Status: Accepted · Date: 2026-10-24

## Context

ADR-0010 decided how the family spends an upstream's longer-window quota: the client
keeps a quota snapshot from the quota headers, a request into a quota the snapshot shows
spent waits it out within `RetryPolicy.backoff_max` or raises `RateLimitError` without
sending, and retries honour the `retry_after` that `classify` derives. It also recorded
that core fell short of it, and promised a core helper once sdk-usda-psd had proven the
pattern. The helper had to observe every response, raw ones (`raise_on_error=False`)
included; never take quota headers from a cache hit; and say, when it refuses, that
nothing was sent and when the quota is expected back.

sdk-usda-psd proved it in its PR 3 and had to build around core to do so (its
`_client.py` on main):

- `QuotaAwareClient`, a subclass of `AsyncClient` that overrides `request`, because the
  client has no hook before a request. The pause must not delay a request the cache can
  answer, so the subclass probes the cache itself, `_cached`, on core's protected
  `_pool()` and `_cache_key()`, which core 0.2.0 renames.
- A module-level snapshot, `Quota`, `observe_quota` and `quota_pause`. `observe_quota`
  is called from `classify`, the only place that saw every response, and again after a
  raw request, since `classify` does not run for one.
- Retries it could not shape. Core's retry loop runs before `classify`, so a 429 without
  `Retry-After`, api.data.gov's documented answer to a spent hourly quota, was retried
  three more times on the exponential backoff, each another request into the spent
  quota, before `classify` could say "one hour". Its test
  `test_core_retries_a_429_only_within_its_backoff` pins those four requests.
- A cache hit carries no trace of when it was stored, so its tasks stamp a hit with the
  current time as `retrieved_at`.

sdk-comtrade fetches UN Comtrade's public reference files from the host of its keyed
data API. `AsyncClient` sends its `auth` with every request, so the package keeps a
second client without auth, `reference_client`, only to keep the key off them.

sdk-usda-esr and sdk-usda-gats sit behind the same gateway as PSD and would copy its
client.

## Decision

1. **Two hooks on `ClientConfig`, next to `classify`.**
   - `before_request: Callable[[httpx.Request], Awaitable[None] | None] | None` is called
     once per `request()` call, not per retry, after the cache lookup and before the rate
     limiter; a cache hit returns before it. It receives the request as built from base
     URL, path, query parameters, body and headers, without the credentials of `auth`,
     which apply when it is sent; changes to it are not sent. It may be sync or async (an
     awaitable result is awaited), may wait, and may raise a taxonomy error, in which
     case nothing is sent.
   - `observe: Callable[[httpx.Response], None] | None` is called with every response
     that came from the wire, each retried attempt included and a cache hit never,
     before `classify` and before the retry decision, whether or not the caller asked
     for the raw response. An exception it raises propagates: it is a programming error.
2. **A quota policy on those hooks.** `QuotaPolicy(*,
   limit_header="x-ratelimit-limit", remaining_header="x-ratelimit-remaining",
   reset_header=None, window=3600.0, spent=None, pause_cap=None, source=None,
   clock=..., sleep=asyncio.sleep)` and `QuotaSnapshot`, exported from `xippios.core`
   and `xippios.core.client`, implement ADR-0010's decisions 3 to 5:
   - `observe(response)` keeps a `QuotaSnapshot(limit, remaining, observed_at,
     resumes_at)`, frozen and replaced under a lock. A response with neither quota header
     leaves it alone; a missing limit keeps the last one; a count that is not ASCII
     digits is ignored. A 429 marks the quota spent, and so does a response that leaves
     nothing; `resumes_at` is then `Retry-After` (on a 429), else the reset header, else
     `window` from now. The reset header is read as delay-seconds, as epoch seconds
     when its integer exceeds ten years of seconds (GitHub's `x-ratelimit-reset`), or as
     an HTTP-date. A cache hit is ignored. `limit_header` or `remaining_header` set to
     `None` turns that header's reading off; with both off, the policy relies on a 429,
     `spent` and `mark_spent` alone.
   - `spent(response) -> float | None`, optional, is asked about every observed
     response after the headers are read: a number marks the quota spent for that many
     seconds, ahead of `Retry-After` and the reset header, so an upstream that answers a
     spent limit with something other than a 429 is covered too (UN Comtrade's 403,
     "Quota will be replenished in HH:MM:SS"). `mark_spent(retry_after)` does the same
     from code that learns of a spent quota elsewhere.
   - Every wait that comes from upstream, through a header or `spent`, is cut to
     `window`, which is at most ten years: no refusal outlives one window, and no
     `resumes_at` overflows on a value no upstream means. `window` is the one setting
     for both the fallback wait and that ceiling: an hourly quota keeps the default
     3600 s (api.data.gov), a daily quota sets `window=86400` (UN Comtrade's, whose 403
     names up to 24 hours, which a one-hour window would cut to one).
   - `before_request(request)` does nothing until the snapshot shows the quota spent and
     not yet back. Then it waits until `resumes_at` when that is within `pause_cap`,
     logging one warning naming the method and path, and otherwise raises
     `RateLimitError` with `retry_after` set to the wait, saying that nothing was sent
     and when the quota is expected back. Messages and the log line carry numbers,
     times, the method and the path; never a host, a query, a key or a variable's value.
   - `install(config)` returns `dataclasses.replace(config, before_request=...,
     observe=...)`. The installed `before_request` is bound to that config's cap: the
     policy's `pause_cap` when it was given one, else `config.retry.backoff_max`, the
     bound the retry loop uses for a `Retry-After`; nothing is written back into the
     policy, so one policy on two configs pauses each within its own bound, and a
     client from `derive` keeps its parent's hooks and cap. A config that already has a
     `before_request` or `observe` hook that is not this policy's is refused with
     `ValueError`, never silently overwritten; installing the same policy again is
     allowed. Called directly, `before_request` caps at `pause_cap`, or 30 s.
     `snapshot()` reads, `reset()` forgets.
   - The snapshot belongs to the policy instance: clients that draw on one quota, one
     key say, share one policy. ADR-0010 left open whether the snapshot is kept per key
     or per source; the package decides by where it installs the instance.
3. **`classify` shapes retries.** `send_with_retries` takes `classify=`, and
   `AsyncClient.request` passes `ClientConfig.classify`. Before a 429 or 5xx is retried
   the loop calls it, at most once per attempt: a `RateLimitError` it returns sets the
   wait from its `retry_after`, else the `Retry-After` header's, so a wait beyond
   `backoff_max` ends the retries; an `UpstreamError` for a 5xx, which restates the
   default mapping, and `None` keep the status rule of ADR-0011, so a 5xx is retried
   when the method allows; any other error it returns, an `AuthError` or an
   `InvalidRequestError` for instance, ends them at once. The final response is
   classified as before; the loop's answer is reused, not asked for twice. With
   `raise_on_error=False` the loop stops the same way and the response is returned.
4. **`auth=` per request.** `AsyncClient.request`, `get` and `get_json`, the same on
   `Client`, and `record`/`record_sync` take `auth: httpx.Auth | UseClientDefault | None
   = httpx.USE_CLIENT_DEFAULT`, typed as httpx types it and passed to httpx's `send`:
   `None` sends the request, every retry included, without the client's credentials,
   an `httpx.Auth` replaces them for that call, the default sends the client's. A call
   with `auth=None` and one with the default share the cache: the keyless endpoints
   this is for answer alike either way. A call with an `httpx.Auth` of its own bypasses
   the cache, neither looked up nor stored, since another identity may get another
   answer from the same URL.
5. **A cache hit says when it was stored.** Next to `"xippios_cache": "hit"`, a hit
   carries `response.extensions["xippios_cache_stored_at"]`, the entry's `stored_at` in
   epoch seconds. On a hit a task sets `retrieved_at` from it (conventions §4). Since
   `get_json` returns the payload alone, a wrapper that needs the response calls `get`
   and then `xippios.core.client.decode_json(response, *, source=None, path=None)`, the
   decoding `get_json` does, with its `ValidationError` for a body that is not JSON.

## Consequences

- sdk-usda-psd, adopting the core release that carries this ADR, deletes
  `QuotaAwareClient` with its cache probe, `observe_quota`, `quota_pause`, the
  module-level snapshot and `Quota`. One `QuotaPolicy(window=QUOTA_WINDOW,
  source=SOURCE)` replaces them; its client becomes
  `AsyncClient(policy.install(config), auth=auth)`, its `classify` reads
  `policy.snapshot()` for its message instead of updating the snapshot, and its tests
  reset nothing: the testing plugin forgets every policy's snapshot around each offline
  test and turns the pause off unless the test is marked `rate_limited` (ADR-0013,
  decision 4). Its 429 without `Retry-After` is raised after one request, carrying the
  one-hour `retry_after`, instead of four.
- sdk-usda-esr and sdk-usda-gats start from `QuotaPolicy` instead of copying PSD's
  client. A package that shares one key across several of its clients installs one
  policy on all of them. Processes, and packages that share a key in one process, still
  keep a snapshot each and do not see each other's spending (ADR-0009, ADR-0010).
- sdk-comtrade drops `reference_client` and fetches the reference files with
  `auth=None` on its one client, which can keep the reference cache for those paths
  alone through `cache_filter`.
- Sources set `retrieved_at` from `xippios_cache_stored_at` on a cache hit.
- **Behaviour change**, pre-1.0 (conventions §12): a 429 or 5xx that a source's
  `classify` maps to an error other than an `UpstreamError` for a 5xx is no longer
  retried blindly. sdk-cashctrl, whose `classify` maps every 4xx and 5xx through the
  default mapping on a copy of the response with the organisation's host scrubbed,
  keeps its 5xx retries for reads and its host scrub; its 429 becomes a
  `RateLimitError` with `Retry-After` as before. Only a 429 or 5xx is retried at all: an
  answer of another status that `classify` maps to `RateLimitError`, UN Comtrade's 403
  for a spent daily quota, is still raised after one attempt, as ADR-0010 noted.
- ADR-0010's decision 4, no request fired into a spent quota, now holds for every
  source through the policy, whatever its answer to a spent limit: a 429 marks the
  quota spent by itself, and any other answer through `spent`. usda-nass, comtrade and
  cashctrl adopt decision 4 by installing a policy, as ADR-0010's adoption note
  foresaw. sdk-comtrade installs `QuotaPolicy(limit_header=None, remaining_header=None,
  window=86400, spent=...)`: its `x-ratelimit-*` headers describe the per-second pace
  (`x-ratelimit-limit: 1`), not the daily quota, so a remaining 0 would pause for a
  whole window; its quota is daily; and its `spent` reads the 403's "replenished in"
  time.
- Any source adopting the policy first checks that the `x-ratelimit-*` headers it lets
  the policy read describe the long-window quota, not a per-second or per-minute pace;
  otherwise it sets those header names to `None`.
- A GET cached by a keyed call answers the same GET sent with `auth=None`, and the
  other way round. A source whose keyed and keyless answers differ for one URL keeps
  them apart with `cache_filter`; one that sends another identity's credentials passes
  that `httpx.Auth` and never shares an entry.
- `UseClientDefault`, the type of `httpx.USE_CLIENT_DEFAULT`, is private to httpx
  (`httpx._client`); core imports it in one place, `client/_core.py`, and re-exports it
  from `xippios.core.client` for sources whose wrappers pass `auth=` through. An httpx
  release that moves it breaks that import, which mypy and the tests catch.
- The two hooks are general: a source can observe other headers or refuse other
  requests before they are sent, with the same placement guarantees, without
  subclassing `AsyncClient`.
- The testing plugin keeps offline tests free of quota pauses and of quotas left spent
  by a replay; ADR-0013 lists it as its decision 4.
- Conventions 1.10: §4 names `xippios_cache_stored_at` as the `retrieved_at` of a cache
  hit; §6 states the hooks, the quota policy, `classify`'s part in retries and `auth=`
  per request; §10 the plugin's quota guarantee. ADR-0010's "core today" note is
  resolved.
