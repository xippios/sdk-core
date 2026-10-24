# ADR-0007: InvalidRequestError, and POST routes for non-scalar task parameters

Status: Accepted · Date: 2026-10-22

## Context

The first source package (USDA NASS Quick Stats) surfaced two gaps.

1. The taxonomy (§5) covers failures that come back from upstream, but not a request
   the package should refuse before sending it. Quick Stats ignores unknown filter
   columns, so a misspelt key silently counts the whole database; and it caps
   `api_GET` at 50,000 records, which the package checks with `get_counts` first.
   Both refusals had no error class: as a plain `XippiosError` they reached HTTP
   consumers as 500, and a `ValueError` would reach MCP clients as a generic failure.
2. `router_from_tasks` mapped every task to `GET` with query parameters. A task whose
   natural parameter is a mapping (Quick Stats filters) made FastAPI expect a JSON
   body on `GET`, which clients, proxies and Swagger UI handle badly.

## Decision

- `InvalidRequestError(XippiosError)` joins the taxonomy: the request cannot be sent as
  given, because of a bad argument or a query the source documents it will refuse. It
  is raised before any upstream call. Source packages subclass it for their documented
  refusals (`QueryTooLarge` in usda-nass). Adapters map it to text (MCP) and to HTTP
  422 with problem details.
- A task whose parameters are all scalars (`str`, numbers, `bool`, dates, enums, and
  optionals of those) is a `GET` with query parameters. A task with any non-scalar
  parameter is a `POST` whose JSON body is an object keyed by parameter name, so the
  shape is the same whatever the mix of parameters.

## Consequences

- Client-side validation has a home, and sources may validate arguments against
  packaged reference data (column lists, enumerations) without inventing semantics.
- HTTP consumers can tell a caller mistake (422) from an upstream failure (502/504).
- Query-shaped endpoints become `POST` routes; the MCP tools are unaffected, since
  tool arguments are a JSON object already.

## Amendment 2026-10-24

`InvalidRequestError` means that the request as given cannot be served: a bad argument
or a documented refusal, detected before the call or by upstream's own refusal of the
query, which the source maps in `classify` (ADR-0008). "Raised before any upstream call"
did not hold in the family. sdk-usda-nass maps Quick Stats' HTTP 413 ("exceeds
limit=50000") to `QueryTooLarge`, the subclass `get_data` raises from the count before
fetching; sdk-comtrade maps the backend's HTTP 400 `ErrorResponse` ("Invalid or missing
parameters.") to `InvalidRequestError` with upstream's text; sdk-cashctrl's
`RequestRejected` is CashCtrl's HTTP 200 with `"success": false`, its documented answer
to a request it refuses. Either way the caller has to change the request, so agents and
HTTP 422 treat both alike. A subclass for the refusals detected after the call was
considered and not added: no caller would handle it differently. Source packages still
subclass for their documented refusals, and the adapters still answer with text (MCP)
and 422 (HTTP). Raised by sdk-comtrade; conventions §5 states the wording from 1.13 on.
