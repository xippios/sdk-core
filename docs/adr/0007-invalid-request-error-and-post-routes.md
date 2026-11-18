# ADR-0007: InvalidRequestError, and POST routes for non-scalar task parameters

Status: Accepted · Date: 2026-10-22 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

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
and 422 (HTTP). Raised by sdk-comtrade; Johannes decided on 2026-10-23, wording over a
subclass; conventions §5 states the wording from 1.13 on.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps each
add their points here.

(a) **A refused argument as problem details** (the decision's first point and the
amendment of 2026-10-24; step 2, https://github.com/xippios/sdk-core/issues/66, found by
sdk-eurostat). FastAPI refuses an argument that a route's typed parameter refuses, a value
outside an enum, a missing one or a body that is no JSON object, before the endpoint runs,
and its own handler answered a `detail` list that echoes the input. `router_from_tasks`
gives its routes a class that answers it as an `InvalidRequestError`, the caller's mistake
this record maps to 422: status 422, `application/problem+json`, title
`InvalidRequestError`, detail `<argument>: <message>` with the count when there are
several, as the MCP adapter words it (ADR-0014, amendment 2026-10-27), `source` the
router's slug, and no input value, input type or pydantic URL. The argument is named
without the part of the request it came in, and `body` names the body as a whole. A route
keeps the `Annotated` metadata of a parameter, so its constraints hold in the route as in
the tool (ADR-0014, amendment 2026-11-18, (b)). A query parameter or a body key that the
task does not declare stays ignored: the refusal of ADR-0014's amendment of 2026-11-18, (a),
answers an agent that misspells an argument of a tool, and an HTTP client or a proxy may
add a parameter of its own.

(b) **The third point, and a refusal's text** (the amendment of 2026-10-24; step 16;
https://github.com/xippios/sdk-core/issues/69, found by sdk-eurostat, with sdk-usda-gats).
The amendment of 2026-10-24 names two points at which the error is detected, before the
call and in `classify`. sdk-eurostat's `get_series` refuses at a third: its one request
succeeds, and an answer in which a dimension other than time holds more than one code
spans several series, which the task cannot return as one, so it raises
`InvalidRequestError` after the request, naming each such dimension for the caller to pin.
The error is raised before the call, in `classify`, or from a successful answer that the
task cannot serve as asked; the caller has to change the request at each. A refusal of a
code names what the caller can send in its place: `UnknownCode` the closest known codes
(ADR-0022), and sdk-usda-gats's refusal of a discontinued partner, a leaf that is no other
code's parent, for a month after its last, names the leaf's parent where it has one, which
it accepts for every month, and the codes listed under the same name, or `list_countries`
where no other code carries its name. A refusal that lists the codes an upstream answer
holds, whose number the package does not fix, lists at most 20 of each list and then how
many more, `and 180 more`: sdk-eurostat's datasets have dimensions of hundreds of codes
(`ef_m_farmleg`), and `get_series` lists the first 20 of each dimension it names, so the
text stays one an agent reads whole, the reason conventions §8 bounds a tool's result. A
refusal that names every value of a parameter whose values the package fixes, a packaged
list or an enumeration, keeps its form: no source's such refusal was found to grow past
what an agent reads, and bounding it would change what sdk-comtrade's and sdk-x's users
read, which no decision settles. Conventions §5 states the point from 1.28 on, and the
README and `InvalidRequestError`'s docstring its third point.
