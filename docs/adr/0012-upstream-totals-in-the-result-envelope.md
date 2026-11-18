# ADR-0012: Upstream totals in the result envelope

Status: Superseded by ADR-0034 · Date: 2026-10-23 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

## Context

CashCtrl answers its list operations with `{"total": <int>, "data": [...]}`, and its
journal, person and order lists paginate by offset with `start` and `limit`. A task
that returns one page, because the caller gave `limit`, must say how many records match
the request, or the caller cannot page deliberately: it cannot tell a last page from a
full one, nor how much is left. A task that collects every page has `total == len(data)`
when upstream is consistent, but the count is still upstream's statement.

`ResultMeta` (conventions §4) has no place for that count. It is a plain pydantic model
that drops unknown fields, so a source cannot carry the count today.

Two alternatives were rejected:

- A nested envelope, `Result[ListPage[T]]` with the count and the records inside
  `data`. It breaks the one shape the family has, and it defeats `cap_result`, which
  counts rows only when `data` is a list: a nested page falls to the byte cap and is
  replaced by a note and a preview instead of being cut to the row cap.
- Dropping the count. The caller loses the paging information, and an agent handed one
  page cannot tell whether it has everything.

## Decision

- `ResultMeta` gains `total: int | None = None`: upstream's count of the records
  matching the request, when the source reports one; `None` when it does not or the
  count is unknown. A negative count is refused at construction.
- A paginated task called without its page parameter collects every page with core's
  paginators and sets `total` from the count upstream reported on the last page fetched.
  That equals `len(data)` when upstream is consistent; a mismatch is upstream's and is
  not corrected.
- A paginated task called with a page parameter returns that page, and `total` is
  upstream's count for the whole request, so the caller can page.
- `total` is provenance like the rest of `meta`: set only from what upstream reports,
  never computed by the package from `len(data)`.

## Consequences

- Conventions §4 lists the field and states the paginated-task semantics (conventions
  1.7).
- Sources set `total` from upstream's count where upstream reports one; sdk-cashctrl
  does so first, for its list tasks (PR 4). A source whose upstream reports no count
  leaves it `None`.
- `cap_result` is unchanged. Its note says how many rows were shown of the rows
  returned; `meta.total` says how many records upstream counts, and both arrive in the
  same envelope.
- The HTTP router returns the envelope unchanged: `meta.total` appears in every response
  and in the OpenAPI schema as an integer or `null`, and is `null` when unset.
- Core's paginators are unchanged; they yield items, so a task that collects every page
  keeps upstream's count from the pages its own `fetch` receives. Page-numbered and
  cursor-paginated sources are unaffected and set `total` the same way when their
  upstream reports a count.
- The field is optional with a default, so this is not a breaking change: sources on
  core 0.1.0 are unaffected and adopt the field with the next core release.

Amended by ADR-0023, decision 5 (2026-10-27, core 0.3.0): of core's paginators only
`paginate_offset` remains, `paginate_pages` and `paginate_cursor` deleted for want of a
consumer; a page-numbered source maps the offset to its page in its `fetch`, and a
cursor-paginated source drives its own loop, both setting `total` as above.

Amended 2026-10-27 (core 0.3.0; queue row 21 a, found by sdk-cashctrl, decided by
Johannes on 2026-10-27): the context's "a plain pydantic model that drops unknown fields"
no longer holds. `ResultMeta` refuses a field it does not define (`extra="forbid"`), so
a misspelt field is an error at construction, never a value lost without a word;
conventions 1.19 §4 says so.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **A task that returns one upstream page per call** (decision 2; step 15;
https://github.com/xippios/sdk-core/issues/177, found by sdk-google-mail, with sdk-x).
Decision 2 has a paginated task called without its page parameter collect every page, and
the amendment by ADR-0023 extends it to a cursor-paginated source's own loop. Two kinds of
list make collecting cost what no call bounds. A list unbounded by nature would spend
hundreds of calls for a result the MCP cap cuts at 200 rows: a mailbox holds tens of
thousands of messages, so sdk-google-mail's `list_messages` (`messages.list`, up to 500
ids a page, five quota units a call) returns one page, as Johannes approved its
parameters at the source's G1 on 2026-10-29. A metered upstream bills per resource
returned, so no call would bound what collecting costs: sdk-x returns one page per call,
and ADR-0027, decision 4 (Johannes, gate P, 2026-10-29) rejected collecting against this
decision. A task over a list of either kind may return one upstream page per call and
collect nothing: the cursor upstream returns stays on its data under upstream's name
(sdk-google-mail's `next_page_token`, sdk-x's `data.meta.next_token`), the caller passes
it back to the page parameter upstream names, and the docstring says that the task
returns one page and collects nothing. `total` stays upstream's count for the whole
request, or `None`, as decision 3 has it for a task that returns one page. Conventions §4
states it from 1.28 on.
