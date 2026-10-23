# ADR-0012: Upstream totals in the result envelope

Status: Accepted · Date: 2026-10-23

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
  paginators and sets `total` from upstream's count. That equals `len(data)` when
  upstream is consistent; a mismatch is upstream's and is not corrected.
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
