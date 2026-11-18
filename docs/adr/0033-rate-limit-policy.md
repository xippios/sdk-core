# ADR-0033: Rate-limit policy — a fast pace, quotas spent, the 429 interpreted

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0010

## Context

The family's sources do not fit one per-source limiter configured from documented limits:
some document no limit, UN Comtrade documents a per-second limit and a daily quota that it
answers with 403, and api.data.gov a rolling hourly quota per key, reported in
`X-RateLimit-Limit` and `X-RateLimit-Remaining`, and a 429 once it is spent. A limiter sized
never to reach an hourly quota is slow, and a per-minute token bucket cannot express a daily
quota at all. This record states ADR-0010 with ADR-0011's amendment of 2026-10-23, ADR-0015's
follow-up of 2026-10-24 and its amendments of 2026-10-27, 2026-10-30 and 2026-11-18 as they
stand, and changes no decision; their history stays in ADR-0010.

## Decision

Decided 2026-10-23 for every package.

1. **Pace.** The limiter sets a fast pace within any documented per-second or per-minute
   limit. Where the source documents none, the package sets a stated self-imposed pace, and
   its CLAUDE.md names it as self-imposed. A source whose upstream states per-endpoint
   windows shorter than an hour, as X states a 15-minute window for each endpoint, sets a
   fast self-imposed pace, since such a window is no per-second or per-minute limit. Core
   builds one limiter per client, so a second client beside the first paces apart; every
   host a source sends to is paced by one limiter, in three cases:
   1. **A second base URL on the same host**, as Eurostat serves its `DS-` datasets from
      `https://ec.europa.eu/eurostat/api/comext/dissemination` beside
      `https://ec.europa.eu/eurostat/api/dissemination`, with the same services and answer
      shapes, is requested through the source's one client, by the absolute URL, which httpx
      takes over the base URL: one limiter, one cache and one `classify`, whose path checks
      name both bases, as Johannes decided for sdk-eurostat on 2026-10-28. A packaged list
      fetched from the second base names its operation by its full URL, since the path alone
      names the first base's operation: a reading of ADR-0041, decision 1's "operationId or
      path", decided by Johannes on 2026-10-28.
   2. **A mirror the publisher runs.** Task code may send to "an origin or mirror the
      publisher runs itself: meta.endpoint names the URL sent, the canonical host's pace
      applies, and docs/upstream/ names both hosts"
      (https://github.com/xippios/sdk-core/issues/239), where its canonical host refuses
      automated requests, as sdk-usda-wasde's snapshot reads USDA's CDN origin,
      `usda.azureedge.us`, for pages that `www.usda.gov` refuses. "A file read from an origin
      or mirror that the publisher runs keeps the file's name in meta.endpoint, and the
      mirror's URL goes in meta.request" (https://github.com/xippios/sdk-core/issues/276;
      ADR-0020, amendment 2026-11-18, point c). One limiter paces both hosts where the
      source sends to both. A mirror that anyone else runs is never sent to, since the
      provenance of ADR-0028 would then rest on the bytes alone.
   3. **A host that a dependency paces.** A dependent sends nothing to a host that its
      dependency sends to: it reaches that host through the dependency's tasks, as ADR-0021,
      decision 1 has it consume them, and the dependency's limiter alone paces the host,
      where a client of the dependent's own would add a second limiter. sdk-usda-wasde
      reaches ESMIS only through xippios-usda-esmis's tasks, and its own client sends
      nothing.
2. **Quotas.** Longer-window quotas (hourly, daily) may be exhausted when more data sooner is
   worth it. The limiter does not pre-ration them, nor the per-endpoint windows of decision
   1: a spent window is `classify`'s, a 429 whose reset header gives `retry_after`, the
   window its fallback. `QuotaPolicy` tracks one window per client (ADR-0037, decision 2)
   and is not used for per-endpoint windows, so decision 4's refusal before a spent window
   waits for a policy keyed per endpoint; until then a spent window costs one 429. Johannes
   decided the per-endpoint windows on 2026-10-29 (ADR-0027, decision 2).
3. **The answer to a spent limit.** The client interprets the upstream's 429, and any other
   answer the source documents for a spent limit (Comtrade's 403), in
   `ClientConfig.classify`: a `RateLimitError` whose `retry_after` comes from `Retry-After`
   when upstream sends it, otherwise from the source's quota headers or a documented
   fallback. A quota snapshot is kept from the quota headers: limit, remaining, the time it
   was observed and, after a refusal, its `retry_after`, otherwise the documented fallback
   counted from the observation time. It is a `QuotaPolicy` on the
   client's `before_request` and `observe` hooks (ADR-0037, decision 2), whose instance the
   package installs where it chooses, one per key per process for api.data.gov
   (ADR-0032, decision 5). Retries honour `retry_after` up to `RetryPolicy.backoff_max`;
   beyond that the error reaches the caller carrying `retry_after`.
4. **No firing into a spent quota.** When the snapshot says nothing remains, the next request
   waits out the remaining wait first if it is within the quota policy's `pause_cap`, 30 s by
   default, the default `backoff_max`, one bound wherever the policy is installed; if it is
   longer, the package raises `RateLimitError` with the remaining `retry_after` before
   sending anything, so a sync call or an MCP tool call never blocks for an hour.
5. **Pauses are stated.** A wait within `pause_cap` happens inside the call and is logged. A
   pause handed back to the caller is stated in the error text: MCP `error: RateLimitError:
   <message> (retry after N s)`, HTTP a 429 problem with `retry_after` and a `Retry-After`
   header.

## Consequences

- Conventions §5 (`RateLimitError`) and §6 (the rate-limiter bullet) state this policy.
- The template's CLAUDE.md rate-limit row should state where the pace comes from, documented
  or self-imposed.
- The quota snapshot is per process, so processes and packages that share one key do not see
  each other's spending, as api.data.gov counts the quota across every API the key is used
  for (ADR-0032); for api.data.gov the snapshot is kept per key, one per process
  (ADR-0032, decision 5).
- A 5xx and a transport failure are retried for idempotent methods only (ADR-0011).

Conventions §2, §4, §5 and §6, the README and the docstrings of `ClientConfig`,
`xippios.core.client.quota` and `xippios.core.data_gov` state its decisions from 1.28 on.
