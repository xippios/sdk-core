# ADR-0027: X as a metered, content-bearing source

Status: Accepted · Date: 2026-10-30 · Decided by Johannes on 2026-10-29 and 2026-10-30
(sdk-x's G1 and G5 answers, gate P with its bounds, the per-tool caps; drafted by the
family from the sdk-x plan's §11 and queue row 336; the usage-cap fallback, the
recorder's search and List guards, the List posts fixture and `lookup_users`'
`most_recent_post` are the sdk-x session's, queue rows 330 and 338)

## Context

sdk-x wraps X API v2 (`https://api.x.com/2`, whose OpenAPI document is the snapshot's
spec) as a secondary, read-only source: posts point at primary data the family already
wraps and are never data themselves (the plan,
`coordination/reviews/2026-10-29-sdk-x-plan.md` in the coordination repository, §3). It
is the family's first upstream that bills in money rather than by quota. sdk-x's
snapshot (`docs/upstream/`, of 2026-10-29, refreshed 2026-10-30) states:

- Reads bill per resource returned, 0.005 USD a post and 0.010 USD a user; post counts
  bill per request, 0.005 USD on `GET /2/tweets/counts/recent` and 0.010 USD on
  `GET /2/tweets/counts/all`. A resource read again within the same UTC day is not
  billed again, a soft guarantee; a counts request is priced per request, and the
  deduplication is stated for resources (the plan, §2, reads it as billed every
  time). Creating a post costs 0.015 USD, 0.200 USD with a URL. Only successful
  responses that return data are billed. Pay-per-usage plans are capped at 3 million
  post reads a billing cycle, and once the console's spending limit per cycle is
  reached, requests are blocked until the next cycle (`pages/pricing.md`,
  `pages/usage-and-billing.md`).
- The rate limits are windows of 15 minutes, per endpoint and per app: 300 requests on
  `GET /2/users/by`, 3,500 on `GET /2/tweets`, 10,000 on `GET /2/users/:id/tweets`,
  and so on for each operation. A spent window is answered with a 429 carrying
  `x-rate-limit-limit`, `x-rate-limit-remaining` and `x-rate-limit-reset`, the last a
  Unix timestamp; the page documents no `Retry-After`, and no per-second or per-minute
  limit applies to the operations sdk-x wraps (`pages/rate-limits.md`).
- An app-only Bearer Token, which X calls the App only Access Token, covers public
  reads (`pages/application-only.md`); posting and owned reads need user context,
  OAuth 2.0 with PKCE or OAuth 1.0a (the plan, §2).
- Posts, their ids and profile information are X Content (the Developer Agreement,
  I.12), the documentation is X API (I.10), both are Licensed Material (I.4), and
  III.A (d) forbids distributing Licensed Material to any third party, in whole or in
  part, except as the Agreement permits; the Developer Policy's "Content
  redistribution" lets X Content reach third parties as Post, Direct Message and User
  IDs (`terms/`).

Core's limiter and `QuotaPolicy` (ADR-0010, ADR-0015) bound calls, not spend, and a
policy keeps one snapshot per client, so it cannot track windows per endpoint (queue row
318). The family's fixtures live in public repositories. Posting has cost and
reputational effects a read source does not have: the account it posts as and the
automation label an automated account carries (the plan, §2).

Johannes answered the sdk-x briefing's interview items, cited here as sdk-x D1 to D8,
with the 429 handling and the recording accounts, at its G1 and G5 of 2026-10-29.
Gate P, the probe of 2026-10-29 over 59 curated accounts (345 requests, 5.74 USD),
measured 49 of them, 36 active and 32 core in 9 categories, and Johannes answered go on
2026-10-29, bounding a tool call at 0.50 USD for posts and 1.00 USD for users (decision
4). On 2026-10-30 he kept the per-tool caps.
The coordination log of sdk-x and sdk-x's `CLAUDE.md` record each answer.

## Decision

1. **App-only reads.** The first release reads with the app's Bearer Token in
   `X_API_KEY`, `api_key_location=bearer`, which core's `BearerAuth` sends as
   `Authorization: Bearer` (sdk-x D7; sdk-x D2, settled by the scaffold's evidence: no
   prefix is missing from core). Its MCP server is read-only. Posting, user-context
   auth and owned reads wait for their own ADR, which settles the posting account, the
   automation label and the OAuth flow.
2. **Spend is bounded outside the code.** The console's per-cycle spending limit is the
   hard stop. Every briefing that spends X credit carries a dollar budget line (the
   briefings README's rule 4, commit 2f748a4 in the coordination repository); the
   session logs `GET /2/usage/tweets` after each spending step, and a script that
   spends prints its estimate before its first request. `live.yml` makes at most one
   billable call a night (sdk-x D3): the `GET /2/users/by` lookup of @XDevelopers,
   about 0.010 USD; the other smoke tests skip on the schedule and run on
   `workflow_dispatch` and locally (queue row 337 asks conventions §10 how a metered
   upstream's live smoke tests read). The pace is self-imposed, 60 requests a minute
   with a burst of 1 (ADR-0010, decision 1). The 15-minute windows are left to
   `classify`, a 429's `x-rate-limit-reset` read as `retry_after` with the window,
   900 s, as the fallback, and never rationed ahead; no `QuotaPolicy` is installed
   (ADR-0010 decision 2, as its amendment of 2026-10-30 reads it; queue row 304; a
   policy keyed per endpoint is row 318). X's `usage-capped` problem is a
   `RateLimitError` too, its fallback the 31-day billing cycle (row 330, item 2).
3. **Fixtures from three accounts, X Content rewritten** (sdk-x D1, extended by Johannes
   on 2026-10-29). Fixtures are recorded only from @XDevelopers, @USDA and @FAO. The
   recorder rewrites, by key on the `Fixture` before the write (ADR-0024, decision 4),
   every `text` and `description` at any depth and the `name`, `username` and `location`
   of every user other than the three, verifies that no rewritten value survives and
   never writes the unrewritten body; counts stay as sent. It refuses before the request
   what could bring in another account's content: an expansion other than
   `most_recent_post_id` (`referenced_posts` refused, Johannes 2026-10-29), a search
   query other than `from:` one of the three, alone or with `-is:retweet` and
   `-is:reply`, a List none of them owns, a conversation not started by a post of theirs
   (queue row 330, items 6 and 8; the conversation guard Johannes's, 2026-10-29). The
   List members and conversation fixtures keep other accounts' members and posts with
   every free text rewritten and their ids, times and public metrics as sent (Johannes,
   2026-10-29); the List posts fixture does the same, the session's (row 330, item 10),
   which Johannes can overturn at G3 of the conventions 1.25 PR. The snapshot of X's
   documentation stays under ADR-0003's amendment of 2026-10-24: reproduced for
   reference with its attribution, the Developer Agreement's I.4, I.10, I.12 and III.A
   (d) cited in sdk-x's `CLAUDE.md`, and X's objection honoured by a summary that keeps
   the names and semantics the wrappers rely on (Johannes, 2026-10-29); queue row 320
   asks ADR-0003 for the general rule.
4. **One page per call** (gate P, Johannes 2026-10-29). A task returns one upstream page
   as X sends it: a post task's `max_results` defaults to 10 and is bounded by the spec,
   at most 100, `lookup_users` takes up to 100 usernames, and paging is explicit, the
   caller passing the previous page's `next_token` to the token parameter the operation
   names. One tool call so spends at most 0.50 USD for posts or 1.00 USD for users, and
   the counts task reads one page of up to 31 days for 0.010 USD. `lookup_users`'
   optional `most_recent_post`, off by default, adds up to 0.50 USD, 1.50 USD for 100
   users, above gate P's bound for users: the session's decision (queue row 338, item
   6), which Johannes can overturn at G3 of the conventions 1.25 PR. Ranking,
   summarising or storing posts is the consumer's. The docstrings name the price per
   result. The per-tool byte caps stand: 128,000 bytes for the four post tools, so that
   a whole page of 100 posts returns with its `next_token` (for Latin-script text), and
   160,000 for `lookup_users`, whose `GET /2/users/by` has no `next_token` and whose 100
   users fit, about 70 with `most_recent_post`; the counts task and `get_usage` stay at
   the family default (ADR-0016, decision 4 and its amendment of 2026-10-30; Johannes
   2026-10-30, superseding gate P's "MCP_CAPS keep the family default"; row 338, item
   3). The nouns are the snapshot's, posts, users and Lists, never tweets or accounts
   (ADR-0003). Queue row 339 asks conventions §4 for the one-page-per-call reading of a
   metered source, beside row 315's for a list unbounded by nature.
5. **Curated account lists are product data**, never packaged (sdk-x D4): the list the
   probe reads through `--accounts` lives in sdk-x's `.local/`, gitignored, and so do
   the probe's cache and its report.

Rejected:

- a `QuotaPolicy` on X's windows (decision 2): its one snapshot would let a spent
  `GET /2/users/by` window refuse `GET /2/tweets`, whose window is not spent, and it
  reads no Unix reset timestamp (row 318); without it a spent window costs one 429,
  which X does not bill;
- a pace rationed within the tightest window (decision 2), the sdk-x briefing's first
  draft, against ADR-0010 decision 2 (row 304);
- collecting every page when the token is omitted (decision 4; conventions §4, and
  ADR-0012's decision that a paginated task called without its page parameter collects
  every page, which its amendment by ADR-0023 extends to a cursor-paginated source's own
  loop), whose spend no call bounds (row 339);
- `MCP_CAPS` at the family default (decision 4), under which a page of more than about
  50 posts is cut to a preview that loses its `next_token` (Johannes, 2026-10-30).

## Consequences

- Nothing in `xippios.core` changes: `BearerAuth` sends the token (decision 1), and the
  429 and the usage cap are `classify`'s (decision 2). The plan's §11 expected a gap row
  for a header prefix in `EnvKeyAuth`; sdk-x D2's evidence made it unnecessary.
- Conventions 1.24: §1 lists `x` among the sources; §6 leaves per-endpoint windows
  shorter than an hour to `classify`, with no `QuotaPolicy` until row 318, as the dated
  line under ADR-0010 states decision 2's reading for them (queue row 304); §13 gains
  the topic `social-media` (sdk-x D8), as ADR-0025 brought `email`. Conventions 1.25:
  §8 gives a tool whose result is one upstream page that must return whole a byte bound
  of its own, as the dated line under ADR-0016 adds that case to its decision 4 (row
  338, item 3).
- Open questions, each a queue row: 318 (a `QuotaPolicy` keyed per endpoint group, with
  a reset header read as a Unix timestamp, waiting for a second consumer, ADR-0023), 320
  (ADR-0003 and conventions §3 for an accepted agreement that classes documentation as
  Licensed Material), 326 (core's redaction writes `next_token` and `pagination_token`
  as `REDACTED` in recorded URLs and in `meta.request`), 337 (conventions §10's nightly
  live run for a metered upstream) and 339 (conventions §4 for one page per call, a
  cursor on `ResultMeta`, MCP text without `None` fields).
- sdk-x 0.1.0 (queue row 301) is the first consumer; its release PR follows this ADR on
  sdk-core `main`.
- A write tool for X waits for the posting ADR of decision 1 (the plan, §12: the
  account, OAuth 2.0 with PKCE and refresh tokens, the automation label, the 0.200 USD
  URL price, a write tool with `confirm` last).
