# ADR-0010: Rate-limit policy — a fast pace, quotas spent, the 429 interpreted

Status: Accepted · Date: 2026-10-23

## Context

Conventions §6 asked for "a per-source rate limiter configured from the source's
documented limits". The family's sources do not fit that sentence:

- Some document no limit. NASS Quick Stats documents none, and FAS PSD none beyond its
  gateway's hourly quota; their packages run self-imposed paces of 30 and 60 requests
  per minute.
- UN Comtrade documents a per-second limit (one call per second for a free key) and a
  daily quota (500 calls), and answers a spent daily quota with 403, not 429.
- api.data.gov, the gateway in front of the FAS APIs, documents (developer manual, read
  2026-10-23) a rolling hourly quota per key, 1,000 requests by default, reported in
  `X-RateLimit-Limit` and `X-RateLimit-Remaining` on every response, and a 429 with the
  error code `OVER_RATE_LIMIT` once it is spent. It documents no `Retry-After`, only
  that the block is lifted by waiting an hour. `x-ratelimit-limit: 1000` was observed
  on every PSD answer to a valid key recorded on 2026-10-23; the 429 is documented and
  not yet observed (sdk-usda-psd PR 3 records one).

A limiter sized never to reach an hourly quota, about 16 requests per minute for 1,000
per hour, is slow when a short burst would deliver the data sooner; a per-minute token
bucket cannot express a daily quota at all. Core has the pieces but no policy:
`RateLimit` is a token bucket per minute, the retry loop honours the `Retry-After`
header of a 429 or 5xx up to `RetryPolicy.backoff_max` and beyond it hands the error to
the caller, and `ClientConfig.classify` (ADR-0008) can map any documented answer to a
`RateLimitError` with `retry_after`.

## Decision

Decided 2026-10-23 for every package.

1. **Pace.** The limiter sets a fast pace within any documented per-second or
   per-minute limit. Where the source documents none, the package sets a stated
   self-imposed pace, and its CLAUDE.md names it as self-imposed.
2. **Quotas.** Longer-window quotas (hourly, daily) may be exhausted when more data
   sooner is worth it. The limiter does not pre-ration them.
3. **The answer to a spent limit.** The client interprets the upstream's 429, and any
   other answer the source documents for a spent limit (Comtrade's 403), in
   `ClientConfig.classify`: a `RateLimitError` whose `retry_after` comes from
   `Retry-After` when upstream sends it, otherwise from the source's quota headers or a
   documented fallback. The client also keeps a per-source quota snapshot from the
   quota headers: limit, remaining, the time it was observed and, after a refusal, its
   `retry_after`; otherwise the documented fallback counted from the observation time.
   Retries honour `retry_after` up to `RetryPolicy.backoff_max`; beyond that the error
   reaches the caller carrying `retry_after`.
4. **No firing into a spent quota.** When the snapshot says nothing remains, the next
   request waits out the remaining wait first if it is within
   `RetryPolicy.backoff_max` (30 s by default); if it is longer, the package raises
   `RateLimitError` with the remaining `retry_after` before sending anything, so a
   sync call or an MCP tool call never blocks for an hour.
5. **Pauses are stated.** A wait within `backoff_max` happens inside the call and is
   logged. A pause handed back to the caller is stated in the error text: MCP
   `error: RateLimitError: <message> (retry after N s)`, HTTP a 429 problem with
   `retry_after` and a `Retry-After` header. Core's adapters write both already.

## Consequences

- Conventions §5 (`RateLimitError`) and §6 (the rate-limiter bullet) are amended to
  this policy (conventions 1.5).
- The template's CLAUDE.md rate-limit row should state where the pace comes from,
  documented or self-imposed; that template item is already queued.
- Core today falls short of decision 3. Its retry loop honours only the `Retry-After`
  header, only on a 429 or 5xx, and before `classify` runs, so a `retry_after` that
  `classify` derives from quota headers or a fallback reaches the caller but never
  sets a retry delay. An answer other than 429 that `classify` maps to
  `RateLimitError` (Comtrade's 403) is not retried at all. A 429 without
  `Retry-After`, api.data.gov's documented case, is retried on the exponential
  backoff: three further requests into the spent quota with the default policy.
- A core helper for the quota snapshot and the pre-request pause follows once
  sdk-usda-psd PR 3 has proven the pattern, and closes that gap. It must observe every
  response, including those requested with `raise_on_error=False` (fixture recording),
  for which `classify` is not called today; it must never take quota headers from a
  cache hit; and the `RateLimitError` it raises before sending says that nothing was
  sent and when the quota is expected back.
- The quota snapshot is per process, so processes and packages that share one key do
  not see each other's spending (api.data.gov counts the quota across every
  api.data.gov API the key is used for, ADR-0009); whether the core helper keys the
  snapshot per key rather than per source is decided when that helper is built.
- Adoption. sdk-usda-psd implements decisions 1–5 in its own client now, as the
  proving package. sdk-usda-esr and sdk-usda-gats copy PSD's client until the core
  helper lands. usda-nass, comtrade and cashctrl adopt decisions 1, 2, 3 and 5 in
  their next PR (the pace's provenance in CLAUDE.md, the spent-limit answer mapped in
  `classify` with `retry_after`) and decision 4 once the core helper exists.
- Nothing about retries on 5xx or on transport failures changes.

Amended by ADR-0011 (2026-10-23): a 5xx and a transport failure are retried for
idempotent methods only.
