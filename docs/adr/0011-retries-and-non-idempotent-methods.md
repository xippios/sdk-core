# ADR-0011: Retries — a 429 for every method, a 5xx and a transport failure for idempotent ones

Status: Accepted · Date: 2026-10-23

## Context

Core's retry loop (`send_with_retries`) retried a 429 and every 5xx for every method,
and a transport failure (timeout, connection error) for GET, HEAD and OPTIONS only.
For a read that is harmless: a repeated GET returns the same data and costs at most one
more call against a quota.

sdk-cashctrl writes (found in the review of sdk-cashctrl's first endpoints,
2026-10-23). CashCtrl's create, update and delete operations are POST requests
(`docs/upstream/` in sdk-cashctrl). A 502, 503 or 504 says that something between the
client and the application failed, not that the application did nothing: a gateway that
gives up waiting answers 504 while the application completes the write behind it.
Retrying such a POST can book the same journal entry twice. A read timeout on a POST is
the same case: the request went out and may have been applied.

A 429 is different. The upstream or its gateway refused the request before acting on
it; that is what a rate limit means, and repeating the request after `Retry-After` is
the documented way on (ADR-0010).

ADR-0010 closed with "Nothing about retries on 5xx or on transport failures changes".
This ADR changes them.

## Decision

1. **A 429 is retried for every method**, as before, honouring `Retry-After` up to
   `RetryPolicy.backoff_max`.
2. **A 5xx and a transport failure are retried for idempotent methods only**:
   `IDEMPOTENT_METHODS`, that is GET, HEAD and OPTIONS. Any other method answered with a
   5xx is returned after one attempt, so the caller sees the `UpstreamError` (or what
   `classify` makes of it); a transport failure is raised as `TransportError`.
3. **`RetryPolicy.retry_non_idempotent: bool = False`.** `True` lifts the method
   restriction of decision 2, for a 5xx and a transport failure alike.
   `retry_transport_errors` keeps its meaning: transport retries on or off, for the
   methods decisions 2 and 3 allow.
4. The method decision lives in the retry loop. `send_with_retries` keeps its
   signature, `is_retryable_status` its meaning (429 and every 5xx).

## Consequences

- A write that meets a 5xx or a transport failure is reported, not repeated. Whether it
  was applied is for the caller to find out, by reading back, before it sends again.
- A source whose writes carry an idempotency key that upstream honours (an
  `Idempotency-Key` header, or a client-chosen id upstream deduplicates on) may set
  `retry_non_idempotent=True` on the client that sends those writes, and names in its
  CLAUDE.md the upstream documentation that makes a repeat safe. The same holds for a
  source that only reads, but reads through POST (a query with a JSON body). A source
  that reads through POST and also writes uses two clients.
- RFC 9110 calls PUT and DELETE idempotent as well. The family does not rely on that: an
  upstream's PUT or DELETE is not guaranteed to follow it, so `IDEMPOTENT_METHODS`
  stays GET, HEAD and OPTIONS.
- A connection that failed before anything was sent (`httpx.ConnectError`,
  `httpx.ConnectTimeout`) would be safe to repeat for any method. The policy does not
  tell it apart from other transport failures, which keeps the rule to one sentence; a
  source that needs the distinction asks for it here first.
- Reads are unchanged: every source in the family reads with GET, retried as before.
  A caller that relied on a POST's 5xx being retried sees the error instead, a breaking
  change for 0.x (conventions §12).
- Conventions §6 states the retry rule this way (conventions 1.6).
