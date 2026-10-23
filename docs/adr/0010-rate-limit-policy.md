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
- api.data.gov, the gateway in front of the FAS APIs, enforces a rolling hourly quota
  per key (1,000 requests by default), reports it in `X-RateLimit-Limit` and
  `X-RateLimit-Remaining` on every response, and answers 429 with the error code
  `OVER_RATE_LIMIT` once it is spent. It documents no `Retry-After`; the block lifts
  within the hour.

A limiter sized never to reach an hourly quota, about 16 requests per minute for 1,000
per hour, spends most of the hour idle when a short burst would deliver the data sooner;
a per-minute token bucket cannot express a daily quota at all. Core has the pieces but
no policy: `RateLimit` is a token bucket per minute, the retry loop honours
`Retry-After` up to `RetryPolicy.backoff_max` and beyond it hands the `RateLimitError`
to the caller, and `ClientConfig.classify` (ADR-0008) can map any documented answer to
a `RateLimitError` with `retry_after`.

## Decision

Taken by Johannes Didaskalu on 2026-10-23, for every package in the family.

1. **Pace.** The limiter sets a fast pace within any documented per-second or
   per-minute limit. Where the source documents none, the package sets a stated
   self-imposed pace, and its CLAUDE.md names it as self-imposed.
2. **Quotas.** Longer-window quotas (hourly, daily) may be exhausted when more data
   sooner is worth it. The limiter does not pre-ration them.
3. **The answer to a spent limit.** The client interprets the upstream's 429, and any
   other answer the source documents for a spent limit (Comtrade's 403), in
   `ClientConfig.classify`: a `RateLimitError` whose `retry_after` comes from
   `Retry-After` when upstream sends it, otherwise from the source's quota headers or a
   documented fallback. The client also reads the quota headers into a per-source quota
   snapshot: limit, remaining, and the time it was observed. Core's retry honours
   `retry_after` up to `RetryPolicy.backoff_max`; beyond that the error reaches the
   caller carrying `retry_after`.
4. **No firing into a spent quota.** When the snapshot says nothing remains, the next
   request waits `retry_after` first instead of drawing another refusal.
5. **Never silent.** Adapters state the pause in their error text: MCP
   `error: RateLimitError: <message> (retry after N s)`, HTTP a 429 problem with
   `retry_after` and a `Retry-After` header. Core's adapters write both already.

## Consequences

- Conventions §6's rate-limiter bullet is rewritten to this policy (conventions 1.5).
- The template's CLAUDE.md rate-limit row should state where the pace comes from,
  documented or self-imposed; that template item is already queued.
- A core helper for the quota snapshot and the pre-request pause is a follow-up, once
  sdk-usda-psd PR 3 has proven the pattern in one package; until then that package
  carries both. Core's retry loop reads `Retry-After` from the response before
  `classify` runs, so a `retry_after` that `classify` derives from quota headers or a
  fallback reaches the caller but does not set the retry delay, and a 429 without
  `Retry-After` is retried on the exponential backoff. The follow-up closes that gap.
- Existing sources (usda-nass, comtrade, cashctrl) adopt the policy in their next PR:
  a pace stated as documented or self-imposed, and their rate-limit answers read in
  `classify`.
- Nothing about retries on 5xx or on transport failures changes.
