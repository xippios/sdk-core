# ADR-0034: Upstream totals in the result envelope

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0012 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/474 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/480

## Context

A task that returns one page of a paginated list must say how many records match the
request, or the caller cannot page deliberately; a task that collects every page still
reports upstream's count as upstream's statement. A nested envelope would break the family's
one shape and defeat `cap_result`'s row cap, and dropping the count would leave an agent
unable to tell whether it has everything. This record states ADR-0012 with ADR-0023's
amendment of 2026-10-27 and its amendments of 2026-10-27 and 2026-11-18 as they stand, and
changes no decision; their history stays in ADR-0012.

## Decision

1. **The field.** `ResultMeta` has `total: int | None = None`: upstream's count of the
   records matching the request, when the source reports one; `None` when it does not or the
   count is unknown. A negative count is refused at construction. `ResultMeta` refuses a
   field it does not define (`extra="forbid"`), so a misspelt field is an error at
   construction, never a value lost without a word; Johannes decided it on 2026-10-27.
2. **A task that collects.** A paginated task called without its page parameter collects
   every page and sets `total` from the count upstream reported on the last page fetched:
   with `paginate_offset`, core's one paginator, where a page-numbered source maps the
   offset to its page in its `fetch`, or in its own loop where the source is
   cursor-paginated. That equals `len(data)` when upstream is consistent; a mismatch is
   upstream's and is not corrected. A task over a list unbounded by nature, such as a
   mailbox, or over a metered upstream that bills per resource returned, so that no call
   bounds what collecting costs, may instead return one upstream page per call and collect
   nothing: the cursor upstream returns stays on its data under upstream's name
   (sdk-google-mail's `next_page_token`, sdk-x's `data.meta.next_token`), the caller passes
   it back to the page parameter upstream names, and the docstring says that the task
   returns one page and collects nothing. Johannes approved sdk-google-mail's parameters
   at its G1 on 2026-10-29, and decision 4 of sdk-x's first record,
   https://github.com/xippios/sdk-x/blob/main/docs/adr/0001-x-metered-content-source.md
   (Johannes, gate P, 2026-10-29), rejected collecting for sdk-x.
3. **A task that returns a page.** A paginated task called with a page parameter returns that
   page, and `total` is upstream's count for the whole request, or `None`, so the caller can
   page.
4. **Provenance.** `total` is provenance like the rest of `meta`: set only from what upstream
   reports, never computed by the package from `len(data)`.

## Consequences

- Conventions §4 lists the field and states the paginated-task semantics.
- Sources set `total` from upstream's count where upstream reports one; a source whose
  upstream reports no count leaves it `None`.
- `cap_result`'s note says how many rows were shown of the rows returned; `meta.total` says
  how many records upstream counts, and both arrive in the same envelope.
- The HTTP router returns the envelope unchanged: `meta.total` appears in every response and
  in the OpenAPI schema as an integer or `null`, and is `null` when unset.
- `paginate_offset` yields items, so a task that collects every page keeps upstream's count
  from the pages its own `fetch` receives.

Conventions §4, the README and the docstrings of `ResultMeta` state its decisions from 1.28
on.

## Amendment 2026-11-24

Amended by ADR-0060, decision 8 (https://github.com/xippios/sdk-core/issues/474): decision 4's
`total`, never computed, is not summed either, so a task that assembles its answer from several
requests, as a split by year does, leaves `total` `None` unless upstream counts the whole
request, while decisions 1 to 3 stand as written.

Amended by https://github.com/xippios/sdk-core/issues/480: decision 2's paginator,
`paginate_offset` with `collect`, gives way to `fetch_pages`, core's one walk of offset pages,
which sends no request at or past upstream's count and returns nothing where it needs more pages
than its bound, the most requests that a call spends by ADR-0061, decision 8, refusing with
`InvalidRequestError` once the count shows it or at the bound where a stop rule runs, while its
stop rule has one consumer, sdk-usda-esmis, whose walks of its release lists stop at a date, and
its key, which drops an item that a later page repeats, has no consumer yet, both built since
nothing leaves by the count alone (ADR-0059, decision 6), and the rest of decision 2 stands as
written.
