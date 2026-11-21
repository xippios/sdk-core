# xippios SDK family — conventions

Version 1.28 · 2026-11-18 · applies to every `sdk-*` repository under
github.com/xippios, and to the host `xippios-mcp` where ADR-0026 binds it.
Changes to this file require an ADR in `docs/adr/` and a PR against `sdk-core`. A
convention that seems wrong is followed, and said in the pull request that meets it, until
its ADR and its change of this file land (ADR-0039, decision 9).
The rules of ADR-0040 and ADR-0041, all of them (the download and decode calls, the
cache bound, `BULK_TASKS`, the fixture cap and the `truncated` marker, the file-fixture
rules, the spared `key`, the packaged-answer rule and the packaged-list file,
`published_at_naive`, the `None`-filter rule, `get_answer`, `matches` (§4), `UnknownCode`
(§5), the frozen series and the period series (§4)), and ADR-0031's rules of 1.20
(`render_enums`, the module committed as formatted, and what an enum's class docstring
holds, §8), bind a source from its 0.3.0 adoption (§15), since the code that serves them
ships in core 0.3.0; until then a source records what its upstream answers and names a
fixture over the cap in the PR
description.

## 1. Naming

| Thing | Pattern | Example |
| --- | --- | --- |
| GitHub repo | `sdk-<source>` | `sdk-usda-nass` |
| PyPI distribution | `xippios-<source>` | `xippios-usda-nass` |
| Import path | `xippios.<source>`; a provider with several APIs nests: `xippios.<provider>.<api>` | `xippios.comtrade`, `xippios.usda.nass` |
| MCP entry point | `xippios-<source>-mcp`; a source with a write server: `xippios-<source>-mcp-read` and `xippios-<source>-mcp-write` (§8, ADR-0026) | `xippios-usda-nass-mcp`, `xippios-google-mail-mcp-read` |
| MCP tool | `<source>_<verb>_<noun>` | `usda_nass_get_series` |
| Env var for a key | `<SOURCE>_API_KEY`, or the issuer's variable when one key serves several sources (ADR-0032); per tenant of a multi-tenant source in the source's own scheme, sdk-cashctrl's `CASHCTRL_<NAME>_API_KEY` (§7, ADR-0042) and sdk-google-mail's `GOOGLE_<NAME>_REFRESH_TOKEN`, under the `GOOGLE_` prefix every Google source shares (ADR-0025) | `COMTRADE_API_KEY`, `DATA_GOV_API_KEY`, `CASHCTRL_ACME_API_KEY`, `GOOGLE_WORK_REFRESH_TOKEN` |

`<source>` names the data provider and, where one provider has several APIs, the API:
`usda-nass`, `usda-psd`, `usda-esr`, `usda-gats`, `usda-esmis`, `usda-wasde` (a parser
package that depends on `usda-esmis`; ADR-0020, ADR-0021), `comtrade`, `eurostat`,
`faostat`, `cashctrl`, `google-mail` (one repository per Google API under the shared
namespace `google`, as the USDA sources share `usda`; Google Drive later as
`google-drive`; ADR-0025), `x` (ADR-0027). The names are upstream's, with one departure
dated 2026-10-29: in `google-mail`, `mail` is the family's name for the product upstream
calls Gmail (ADR-0025).
No domain prefixes (`ag`, `agri`): sources are domain-neutral; grouping happens via
GitHub topics (`xippios-sdk`) and the org README.

The import path nests only where one provider has several APIs (ADR-0006): `usda-nass`
imports as `xippios.usda.nass`, `google-mail` as `xippios.google.mail`, `comtrade` as
`xippios.comtrade`. Repository and distribution names stay flat and hyphenated
(`sdk-google-mail`, `xippios-google-mail`). Each generated repository records its
import path explicitly (`import_path` in `.copier-answers.yml`); the default turns every
hyphen into a dot, and a single-API provider whose name carries a hyphen overrides it
(`world-bank` → `xippios.world_bank`). MCP tool names keep the flat prefix
(`usda_nass_get_data`).

`src/xippios/` is a PEP 420 namespace package, and so is every provider level such as
`src/xippios/usda/`: **no** `__init__.py` at those levels in any repo. Only the package
itself (`src/xippios/usda/nass/`) has one.

## 2. Layering (ADR-0001)

Every source package has three layers, top to bottom, and nothing skips a layer.
`<pkg>` below is the import path under `xippios` as a directory: `comtrade`, `usda/nass`.

1. **Endpoint wrappers** — `xippios/<pkg>/api/*.py`. One function per upstream endpoint,
   parameters as upstream names them (snake_cased), returning typed models that mirror
   the upstream payload. The module and the function carry the upstream operation name
   in snake case (ADR-0028, decision 2): from the operation's id in the
   snapshot (an OpenAPI `operationId`, a WADL method id), else from the path, minus a
   controller prefix that every operation of the API shares (the Swagger controllers of
   the FAS APIs, `ESRData_`, `PSDData_`, `GATSData_`), so
   `PSDData_GetCommodityDataByYear` is `get_commodity_data_by_year` in
   `api/get_commodity_data_by_year.py`. An `operationId` that restates the path, with or
   without the HTTP method (a generator's slug: sdk-comtrade's `get-getda`,
   `getmetadata`), or an opaque id (sdk-comtrade's hex ids), is not a name and counts as
   absent, so the path rule applies. A name from the path drops the server's base path,
   or the prefix every operation of the service shares, and a parameter segment such as
   `{typeCode}`, turns `/` into `_` and drops a file suffix such as `.json`:
   sdk-cashctrl's `/api/v1/account/category/list.json` is `account_category_list`,
   sdk-comtrade's `/data/v1/getDa` is `get_da`, sdk-usda-nass's `/api/api_GET/` is
   `api_get`. A file suffix that tells operations on one path apart stays as the last
   word, the default `.json` dropped: sdk-cashctrl's `order/document/read.json` is
   `order_document_read`, `read.pdf` is `order_document_read_pdf`; `journal/list.json`
   is `journal_list`, `list.xlsx` is `journal_list_xlsx`. A run of capitals is one word:
   `GATSData_GetHS6Commodities` is `get_hs6_commodities`, `GATSData_GetUNTradeExports`
   is `get_un_trade_exports`. Upstream's spelling survives the transform, so a singular
   stays singular (`GATSData_GetCensusImport` is `get_census_import`). The verbatim id
   stays in the first line of the wrapper function's docstring and in the `endpoint=` it
   passes, so `meta.endpoint` keeps upstream's exact name (§4); the task layer and the
   MCP tool names are unchanged by the rule. Where an API's operation ids repeat, across
   its services or across the resources of one service, the wrappers of such a service
   share one module named after the service (sdk-eurostat's `api/statistics.py` and
   `api/sdmx.py`); ids counted as absent do not trigger it (sdk-comtrade's data wrappers
   stay one module per operation); another service of the same API may keep its service
   module (sdk-eurostat's `api/catalogue.py` holds the wrapper of `getTocXml` alone and
   stays). A module may hold, beside its wrapper, a second function on the same
   endpoint, named after the wrapper with a suffix that says what differs (sdk-comtrade's
   `api/get.py` holds `get` and `get_count_only`, its `api/reference.py` `reference` and
   `reference_rows`); a helper that calls no endpoint is not a wrapper and keeps a plain
   name (sdk-eurostat's `codelist_path` and `data_path` in `api/sdmx.py`). An existing
   source applies the rule to its wrappers and fixture directories in one PR of its own,
   never inside an adoption PR: right after its core 0.3.0 adoption, or, when it is past
   that adoption as 1.22 lands, right after its next adoption PR, or in the first PR of
   its next version when no adoption is pending; an adoption PR is judged against the
   rest of 1.22 until the rename PR merges.
2. **Task-shaped functions** — `xippios/<pkg>/tasks.py`. The functions a person
   or an agent actually wants: `get_balance_sheet(commodity, marketing_year)`. They
   compose endpoint wrappers, handle pagination and reference lookups, and return
   `Result[T]`. This is the public API and the only layer adapters may call. A task may
   compose another task of its own `tasks.py`, so that the request, its refusals before
   sending and the meta live once, in the task it composes (sdk-eurostat's slices and
   sdk-faostat's `get_series` compose `get_data`); it awaits that task's `_async`
   function, since the sync facade refuses a call from inside core's loop, and builds its
   meta as §4 says; a task of another package is composed only as §12 allows (ADR-0001,
   amendment 2026-11-18, point a; ADR-0021).
3. **Adapters** — `xippios/<pkg>/mcp.py` and `xippios/<pkg>/http.py`.
   Thin: register task functions, apply result caps, map errors. Target ≤ 60 lines
   each. If logic appears here, it belongs in `tasks.py`.

Supporting modules: `models.py` (pydantic models), `reference/` (packaged data files
plus a loader), `_client.py` (the configured `xippios.core.client` instance).

Task code may send, beside its base URL, to a second base URL on the host of the first,
from which upstream serves part of its data, and to an origin or mirror that the publisher
runs itself where its canonical host refuses automated requests, never to a mirror that
anyone else runs (ADR-0033, decision 1;
https://github.com/xippios/sdk-core/issues/239).
A source that depends on another sends nothing to a host that its dependency sends to,
and reaches that host through the dependency's tasks alone (ADR-0021, §12). §6 gives
each case its client and its pace.

A file-distributed source, whose upstream publishes files rather than answering with
records, keeps the three layers (ADR-0020). Its layer 1 has two parts: `api/` wraps the
HTTP endpoints it has (a catalog), and the download goes through core's `download` (§6)
or through the retrieval package the source depends on (§12, ADR-0021); `parse/` holds
one module per file kind, `parse/<file_kind>.py`, with one function,
`parse_<file_kind>(path) -> list[Model]`. A parser of a bulk file kind, a file that a
bulk task downloads, may return `Iterator[Model]` instead, a generator that reads the file
as the records are taken, closes it when it ends or is closed, and says so in its
docstring (sdk-eurostat's `parse_sdmx_csv`, sdk-faostat's `parse_bulk_csv`; ADR-0020,
amendment 2026-11-18, point b). A parser's library (a spreadsheet reader,
`pypdf`) is the source's dependency, never core's. A PDF is read for its narrative text
only, never for numbers: a figure a task returns comes from the XLS, XML, CSV or TXT the
release carries, or is not returned (ADR-0020). A bulk task, which returns
`Result[Downloaded]` or `Result[list[T]]` read from a file, lives in `tasks.py` like
every task and is named in `BULK_TASKS`, a frozenset beside `MCP_CAPS`; the adapters
skip it (§8, §9; ADR-0040).

## 3. Upstream fidelity (ADR-0028)

- Names and semantics come from the upstream documentation, which is snapshotted in
  `docs/upstream/` with a `FETCHED.md` recording the UTC time and the URL of the fetch.
  The snapshot is the reference for the agent; refresh it deliberately, by PR, and diff
  it.
- `Fetched` in `FETCHED.md` is the UTC time of the run in ISO 8601 with an explicit `Z`
  (`2026-10-24T09:15:00Z`), never a local date or time. A table that a Markdown pipe
  table cannot hold, one with merged cells (`rowspan`, `colspan`) or with a table nested
  in it, is kept as its HTML in the Markdown snapshot, and one line in `FETCHED.md` says
  so (ADR-0028, decision 4).
- A vendor's documentation is reproduced in the snapshot for reference (ADR-0028,
  decision 4): `FETCHED.md` carries the copyright line as the documentation
  states it (`© 2026 CashCtrl Ltd.`) and the URL the text was fetched from. A vendor's
  objection is honoured by replacing the snapshot with a summary that keeps the names and
  semantics the wrappers rely on.
- A source whose API is one part of a shared upstream document (several FAS APIs
  described in one OpenAPI document) snapshots its own part and records the full
  document's byte size and sha256 in `FETCHED.md`, so a refresh can tell the part from
  the whole (ADR-0028, decision 4).
- What a source observed of upstream that no page of the documentation states goes in one
  hand-written file, `docs/upstream/OBSERVED.md`, the only file under `docs/upstream/`
  written by hand: the capture script neither writes nor checks it, and `FETCHED.md`
  lists it in a row of its own that says so (ADR-0028, decision 5).
  Each note names its evidence. A way the live API departs from its documentation, such
  as a type, a field, an answer's shape or a refusal, names the probe that showed it: its
  date, its operation and its sample, a request or the fixture that holds the answer. A
  file layout that no upstream page documents names the release files it was written
  from, with their ids or URLs, bytes and sha256. A parameter or a default traceable to a
  note there is traceable to `docs/upstream/`. A source that keeps such notes elsewhere,
  in its README or its capture script, moves them into the file with its next refresh.
- A page that the documentation links and the snapshot deliberately does not request,
  such as a feed, a third-party specification (cited, not snapshotted), an API answer or
  a page that is not API documentation, has a row with its reason in a table of
  `FETCHED.md` headed `Not fetched`. A page that an anonymous client cannot read is
  requested once, without credentials: the capture follows no redirect to another host
  and imitates no browser, the page's row records the status and the host it redirects
  to, and the public pages that state the same facts are the snapshot's statement of the
  subject (ADR-0028, decision 6).
- A small answer of the API, kept verbatim under `docs/upstream/samples/`, documents the
  answer's shape and is not a test fixture: its row in `FETCHED.md`'s file table gives
  the URL it was requested from and says that it is a sample. A sample whose operation
  needs the source's credentials is requested with them; only the samples' requests send
  a credential, and neither a credential nor a token is written (ADR-0028,
  decision 7).
- Within-source hygiene is required: dates → `datetime.date`/`datetime`, numbers →
  `int`/`Decimal`/`float` as appropriate, upstream enums → `StrEnum`, pagination
  resolved, errors typed. An upstream enum of integer ids becomes an `IntEnum` instead,
  so a member compares equal to the id in upstream's data (ADR-0031). Field names are
  upstream names in snake_case. A `Decimal` field of an `UpstreamModel` serialises as a
  JSON number in every adapter (ADR-0031); Python keeps the `Decimal`.
- Task-shaped functions may return a *projection* of an upstream record: a subset of its
  columns under their upstream names, typed, built with `UpstreamModel.project`. Nothing
  is renamed or computed; parsing a value is the only permitted override. A MIME
  message's decoded view is a projection by role: decoding the MIME tree is parsing a
  value, the view picks the tree's parts by their MIME role, under the role's name
  (sdk-google-mail's `text`, the first `text/plain` part), and the faithful tree stays
  on the wrapper (ADR-0025).
- Fidelity, the hygiene above included, applies to files (ADR-0020): a model mirrors the
  file, its field names the column headers snake_cased, sheet and table names kept on the
  record as upstream prints them, units and footnote markers kept as text; nothing is
  renamed, converted or joined across files. `docs/upstream/` snapshots the file-format
  documentation (layout notes, a dataset's README) the way it snapshots API
  documentation.
- Documented personal identifiers stay out of the projections tasks return (ADR-0017):
  `ssn`, `iban` and what the source judges equivalent (a national identification number,
  a bank account number, a tax number), unless a task fetches them deliberately and says
  so in its docstring; a write task that takes one as a parameter does not echo it in
  `meta.request` either (§4). The rule reaches nested fields: a `project` override that
  drops an identifier inside a kept list field (`bankAccounts[].iban`) is still parsing
  only in the sense of the projection rule above (ADR-0028, decision 1). The
  endpoint wrappers' read models stay faithful and carry them. Fixtures never carry their
  values: the recording names them in `Scrub(secrets=...)` or rewrites them by key in
  its own recorder step, on the `Fixture` before the write (ADR-0017, ADR-0042).
- **No cross-source normalization.** A USDA `marketing_year` stays a USDA concept.
  Mapping between sources is business logic and lives outside this family.
- Reference data (commodity codes, country codes, report calendars) ships inside the
  package under `reference/` as CSV or JSON, loaded via `xippios.core.reference`, and is
  versioned with the package. A list fetched from one upstream operation is a packaged
  list, `reference/<name>.json` with `{"param", "endpoint", "fetched", "records"}` and
  an optional `"note"`, free-text provenance (what a derived list is derived from, how a
  list was reconciled with upstream's documentation), and no other key: upstream's
  records under upstream's field names (`UpstreamModel.dump_upstream`), a list of values
  as records of one field named by the upstream parameter, a table as records of its
  columns. `<name>` is the parameter, or a name of the list's own where two lists derive
  from one parameter. The refresh script writes it with `PackagedList.write`, `fetched`
  the UTC time of the fetch to the second; the package reads it with
  `PackagedList.load(package, name)` (ADR-0041, decisions 4 and 5). Enums are
  generated from it with one `xippios.core.reference.render_enums` call: one module, a
  `StrEnum` per value list and an `IntEnum` per list of `(id, name)` pairs, each class
  docstring naming its list and fetch date. The whole generated module, docstrings
  included, is ASCII-only and passes `ruff check` and `ruff format --check` as committed,
  after the refresh script's `ruff format && ruff check --fix` (ADR-0031,
  decision 6).

## 4. Result envelope and metadata

Every task function returns `xippios.core.models.Result[T]`:

```python
class ResultMeta(BaseModel):
    source: str                       # "usda-nass"
    endpoint: str                     # upstream operation name, or a file's name (ADR-0020)
    retrieved_at: datetime            # UTC, when we fetched it
    published_at: datetime | None     # upstream publication/release time if known
    published_at_naive: bool = False  # True for upstream's wall-clock text, no zone
    vintage: str | None               # upstream release identifier if the source has one
    request: dict[str, Any]           # the parameters used, for reproducibility
    total: int | None                 # upstream's record count, if it reports one
    tenant: str | None                # the tenant the data came from, by name (§7)

class Result(BaseModel, Generic[T]):
    data: T
    meta: ResultMeta
```

`meta` is never optional. It is what makes a later as-of/vintage store possible.
`ResultMeta` refuses a field it does not define, so a misspelt one is an error, never
dropped (ADR-0034, decision 1). On a cache hit, `retrieved_at` is the time the
entry was stored, which the client puts on the response as
`extensions["xippios_cache_stored_at"]` (ADR-0037); a wrapper reads it with
`get_answer()`, whose `Answer` carries the payload and that `retrieved_at` (§6). The miss
that stored the entry carries the same time, one reading of the clock for both, taken
when the answer arrived (ADR-0037, decision 5).

`published_at` carries a zone. A naive value, a time upstream printed without one (FAS:
`2026-10-06T08:00:00`), is accepted only with `published_at_naive=True` and is stored as
given, no zone attached; a naive value without the flag is refused, and so is the flag
with an aware value or with none. The flag says the time is upstream's text, not
comparable across sources; a consumer that knows the publisher's zone assigns it outside
the family (ADR-0028, ADR-0041). The flag also marks a time whose printed zone
upstream's own calendar and files contradict: the task keeps the printed wall-clock time
with its offset dropped, never converted, and sets the flag, and the wrapper's model
keeps the time as printed (ESMIS prints `+0000` for a release that its calendar and its
files' times put at noon Eastern; ADR-0041, decision 2). `vintage`
keeps the release identifier as upstream names it; where that identifier is the
timestamp text, `vintage` holds the text and `published_at` its parsed value with the
flag. A release identifier that is a day or a month, with no time, stays in `vintage` as
upstream gives it (sdk-faostat's `date_update` as printed, `2025-12-31`; sdk-usda-psd's
release month, which it writes as `2026-10` from two fields of upstream's records), and
`published_at` stays empty: the flag covers a time printed without a zone, not a day,
and 00:00 of the day or the first of the month would date the release before it
happened (ADR-0041, decision 2). A load time is never a vintage: a
source whose only time is the time upstream loaded the data (sdk-usda-nass's
`load_time`) leaves `vintage` and `published_at` empty, and a newest load time computed
across datasets is no release time either (ADR-0041, decision 1).

A parameter that takes the `meta.vintage` of an earlier call to return only what changed
since (sdk-usda-esr's and sdk-usda-psd's `since`) takes the text as `vintage` wrote it
and keeps what is strictly later, an equal release being no newer. `meta.vintage` and
`meta.published_at` stay those of the whole upstream answer, not of the filtered subset,
so an empty answer still carries the marker to store for the next call. Against a naive
release time, a value with a zone is refused with `InvalidRequestError`, never
converted, and so is a text the parameter cannot read (ADR-0007; ADR-0041,
decision 2).

A task that answers from packaged reference data (§3) fills `meta` by ADR-0041, decision 1:
`retrieved_at` is the time the packaged list was fetched from upstream (the file's
`fetched` value, as a cache hit uses the entry's stored time); `endpoint` names the
upstream operation the list came from (operationId or path, or the full URL for a list
fetched from a second base URL, since the path alone names the first base's operation;
ADR-0033, decision 1), or, for a list packaged from a released file,
that file's name as a task that reads it sets it (below; ADR-0020, amendment 2026-11-18,
point c), never "reference" or a file path; `vintage` is an upstream release identifier,
or `None` when upstream has none, since a fetch date is not a vintage; `total` is `None`
unless upstream reports a count (ADR-0034). `PackagedList` builds this meta, so no source
writes it by hand: `PackagedList.load(package, name)` reads the file (§3),
`.meta(source, request=..., vintage=...)` builds the meta and `.parse(Model, source=...)`
the records. A `fetched` that is a bare date, as refresh scripts wrote it before template
v0.3.0, reads as 00:00 UTC of that day, the start of the day the old scripts truncated
the time to, until the source's next refresh writes the full time (ADR-0041, decision 4).
A `list_*` task's `search` keeps a record when the text occurs in one of its
fields, ignoring case (`xippios.core.matches`).

A frozen series, one upstream no longer updates (a discontinued report, a dataset
upstream stopped publishing), is marked where agents and readers look: its task's row in
the README status table carries a status that names the last release (`frozen, last
release 2024-09`), the task's docstring says so, and `vintage` holds that release's
identifier. `ResultMeta` has no field for it (ADR-0041, decision 10). Where each
answer of a frozen feed carries its own release, as a reporter-year of sdk-usda-gats's UN
Trade data does, `vintage` keeps that answer's release, and the feed's last release goes
to the README status value and the docstring only; the feed's list of release dates keeps
`vintage` empty, since it is no single release (ADR-0041, decision 10).

A task that assembles a period series from one upstream call per period (a month, a
marketing year) states its ceiling, the most periods one call fetches (the MCP tool's,
where it is smaller: sdk-usda-gats fetches at most 60 months, 24 on the MCP server), and
sets `vintage` to the newest release among the periods returned. Its docstring says what
a period inside the range that upstream has not released answers: the period is skipped
where upstream's empty answer can be told from data (sdk-usda-psd's empty 404), and the
whole range is refused, naming the latest released period, where it cannot (an
unreleased month answers sdk-usda-gats with `[]`, as a month without trade does). The
refusal is `NotFoundError` naming the latest released period; `InvalidRequestError`
stays for a malformed request (ADR-0007). An empty answer that cannot be told from no
data is never passed off as data (ADR-0041, decision 6). Four cases read as
the sources apply them (ADR-0041, decision 6;
https://github.com/xippios/sdk-core/issues/238):

- Where upstream names no release, so the latest released period is unknown, a range
  ends at the current period, and a period that counts zero is skipped, the docstring
  saying that a zero may be a period not yet released (sdk-usda-nass's `split_by_year`
  refuses a year past the current UTC year and skips a year counting 0).
- A task that fetches one period refuses a period after the latest released one where it
  knows that period, with `NotFoundError` (sdk-usda-gats's month tasks); where it does
  not know it, its docstring says that an empty answer may be a period not yet released.
- A split mode of a free-form query task is a period series, with its ceiling
  (sdk-usda-nass's `split_by_year`: 20 years, 5 on the MCP server).
- The note that states a period-series tool's ceiling counts the upstream calls that one
  tool call spends at that ceiling (sdk-usda-nass's 5 years on the MCP server: at most 11
  keyed calls, a first count and two calls a year; sdk-usda-gats's 24 months: 24
  requests).

A task that reads a file (§2) sets `endpoint` to the file's name as upstream names it,
which may change with each release and carry a revision's suffix (`wasde1026.xml` and
`wasde0626v2.xml` as ESMIS catalogs them), `vintage` to the release identifier (an ESMIS
release id, a report date as printed), `published_at` to the catalog's release time, and
`request` to the file's URL or release id plus the filters applied in Python (ADR-0020;
amendment 2026-11-18, point c; https://github.com/xippios/sdk-core/issues/244). A
narrative read from a PDF that prints a date but no month label keeps the ESMIS release
id as `vintage`. A file it downloads from another origin than the base URL's, a link a
catalog names, goes without the client's credentials (§6): `endpoint` is named as above
all the same, `request` holds the link as `ResultMeta` writes it, a signature in its
query `REDACTED`, and the fixture of that download carries no key, neither the
placeholder nor a credential header, so a leak check counts none in it (ADR-0037,
decision 4). A download of an
operation's answer is no file upstream names and keeps the operation's name
(sdk-eurostat's `dataQuery`). Where upstream's file name carries the dataset's name,
`endpoint` names the part that every dataset's file shares, and the dataset stays in
`request`: sdk-faostat's `download_dataset` names `All_Data_(Normalized).csv` for
FAOSTAT's `<Name>_E_All_Data_(Normalized).csv`, with the domain and the file's URL in
`request` (ADR-0020, amendment 2026-11-18, point c;
https://github.com/xippios/sdk-core/issues/280). A file read from an origin or mirror that
the publisher runs (§6) keeps the file's name in `endpoint`, and the mirror's URL goes in
`request` (ADR-0020, amendment 2026-11-18, point c;
https://github.com/xippios/sdk-core/issues/276).

`request` records what was sent: a parameter the caller left `None` is omitted
(ADR-0041, decision 3). `ResultMeta` drops a top-level `None` at construction, so a task
passes its parameters as they are; a `None` inside a nested mapping is kept as given. It
never carries credentials (ADR-0030). `ResultMeta` redacts the value of any key that
names one, at any depth, to `"REDACTED"` at construction, by the one rule of
`xippios.core.redaction` (a whole word `api_key`, `apikey`, `api-key`, `token`,
`secret`, `password`, `passwd`, `pwd`, `auth`, `authorization`, `sig`, `signature`,
`credential` or `credentials`, between `_`, `-` or the ends of the name), so an envelope
is safe to hand to an agent, return over HTTP, or write to a store; personal identifiers
in upstream data stay out of it by §3's rule for projections (ADR-0017). A bare `key` is
not on the list: it is a credential in a process where a `QueryKeyAuth` sends the key
under that name (USDA NASS), which registers it when built, and data elsewhere, as
Eurostat's SDMX series `key` is (ADR-0040, decision 6). A source declares a
name with a whole-word `token` data where its value is data, a paging cursor such as X's
`next_token` and `pagination_token`, once, with
`xippios.core.redaction.register_data_name`: the envelope, the recorder and replay keep
its value. Every other name with a whole-word `token` stays a credential, and `token`,
`access_token`, `refresh_token` and `id_token` cannot be declared (ADR-0040,
decision 6). A link in `request`, a file's signed URL say, keeps its
path and its other parameters and reads each credential of its query `REDACTED`, an
Azure SAS `sig` or an S3 `X-Amz-Signature`, as `scrub_url` writes it, so a task records
the link it sent (ADR-0040, decision 6). A task that wants the
credential's provenance records the variable name, never the value. A task that composes
another (§2) and extends the composed answer's `request` builds a new `ResultMeta`
through the constructor, `ResultMeta(**answer.meta.model_dump(exclude={"request"}),
request={**answer.meta.request, "since": since})`, never with `model_copy`, which runs no
validator, so the drop of a top-level `None` and the redaction reach what it adds
(ADR-0001, amendment 2026-11-18, point a).

`tenant` is the name of the tenant a multi-tenant source served the data for (§7),
never a credential, a host or another of the tenant's values; `None` for a
single-tenant source and for the list of tenants.

`total` is upstream's count of the records matching the request, or `None` when the
source reports none or the count is unknown (ADR-0034). A paginated task called without
its page parameter collects every page; called with one, it returns that page. For
offset paging, `limit` given means one page starting at `start` (default 0); `limit`
omitted means every page from `start` onward. Either way `total` is upstream's count for
the whole request, so the caller can page deliberately. It is provenance like the rest
of `meta`: set only from what upstream reports, never computed from `len(data)`. When
every page is collected, the count kept is the one upstream reported on the last page
fetched, and a mismatch with `len(data)` is upstream's and is not corrected; a task that
returns one page, or caps what it collects, can have `total > len(data)` by design.

A paginated task may instead return one upstream page per call and collect nothing in
the two cases where collecting would cost what no call bounds: a list unbounded by
nature, where collecting would spend hundreds of calls for a result the cap cuts at 200
rows (sdk-google-mail's `list_messages`, a mailbox), and a metered upstream, which bills
per resource returned (sdk-x; ADR-0027, decision 4). The cursor upstream returns stays
on its data under upstream's name (`next_page_token`, sdk-x's `data.meta.next_token`),
the caller passes it back to the page parameter upstream names, and the docstring says
that the task returns one page and collects nothing (ADR-0034, decision 2).

## 5. Errors (`xippios.core.errors`)

```
XippiosError
├── ConfigError          missing key, bad settings
├── AuthError            401/403
├── RateLimitError       429, or a source's documented answer to a spent limit
│                        (ADR-0033); carries retry_after
├── NotFoundError        404 or empty where upstream signals absence
├── ValidationError      we could not parse what upstream returned (carries raw body)
├── UpstreamError        other 4xx/5xx (carries status, body)
├── TransportError       network, timeout
└── InvalidRequestError  the request as given cannot be served: a bad argument or a
    │                    documented refusal, detected before the call, by upstream's
    │                    own refusal of the query or from its answer (ADR-0007)
    └── UnknownCode      a code the packaged list lacks, refused before the call
                         (ADR-0041)
```

Source packages subclass only when upstream has a distinct, documented failure mode;
a refusal the package makes itself, such as a query over a documented record limit or
an unknown filter name, subclasses `InvalidRequestError`. A code the packaged list lacks,
where upstream answers an unknown code with an empty result, is refused before the call
with core's `UnknownCode`, naming the list, its fetch date and the closest known codes
(`xippios.core.closest`, `xippios.core.nearest` for integer codes nearest by number, or a
strategy of the source's own) (ADR-0041, decision 8), a code whose name is its own text
named once (`Did you mean VA?`), and that the
packaged list is out of date if upstream added the code since, naming no command of the
package's maintainers (ADR-0041, decision 8). A source checks an argument against a packaged
list with core's one check, `check(param, value)` of the list's declaration
`PackagedList.codes(code, name, fold_case=...)`, which returns the value as the caller gave it
or raises `UnknownCode` (ADR-0045). Upstream's own refusal of
the query as given is mapped to `InvalidRequestError`, or a subclass, in `classify` (§6):
usda-nass's HTTP 413 over the record limit, comtrade's HTTP 400, cashctrl's
`RequestRejected`. A refusal the package makes from a successful answer that the task
cannot serve as asked is raised after the request (sdk-eurostat's `get_series`, whose
answer spans more than one series), so `InvalidRequestError` is raised at three points:
before the call, in `classify`, and from the answer (ADR-0007, amendment 2026-11-18,
point b). Agents and HTTP 422 treat the three alike: the caller has to change the
request. Adapters convert errors to structured text (MCP) or problem+json (HTTP;
`InvalidRequestError` is 422); they never leak tracebacks. An error message names the
request's method and path, never its host or query string: the host can name a tenant,
the query can carry a key (ADR-0030). `xippios.core.errors.request_description(response)`
gives that description, `GET /v1/series`: core's messages about an answer use it, and a
source's `classify` words the errors it maps with it, not with a copy of its own. A
message written before any answer exists, such as a quota policy's refusal of a request
it does not send, names the request's method and path from the request itself (ADR-0030,
decision 4).

A refusal of a code names what the caller can send in its place: the closest known codes
(`UnknownCode`), or the refused code's parent and the codes listed under its name, as
sdk-usda-gats's refusal of a discontinued partner names them. A refusal that lists the
codes an upstream answer holds, whose number the package does not fix, lists at most 20
of each list and then how many more (`and 180 more`), so that an agent reads it whole
(sdk-eurostat's `get_series`, over dimensions of hundreds of codes) (ADR-0007, amendment
2026-11-18, point b).

Where the packaged-list check applies (ADR-0041, decision 8):
`UnknownCode` also refuses a code whose answer from upstream was never recorded, its
`reason` saying so (sdk-comtrade's `customs_code` and `mot_code`), and a value list that
upstream refuses itself keeps that refusal, mapped in `classify`, or a check of the
source's own that raises `InvalidRequestError` (sdk-comtrade's `cl_code` and `flow_code`,
which upstream answers with HTTP 400). In free-form filters the value of a key that names
a packaged parameter is checked, and a key with an operator is checked as a key only
(sdk-usda-nass's `validate_filters`). A code sent under a coding system the packaged list
does not hold goes unchecked, and the task's docstring says so (sdk-faostat's area and
item codes under another system than FAO's). A code the packaged list holds and upstream's
live answer lacks is `NotFoundError`, naming the code and the operation (sdk-usda-esr's
commodity that ESR's release list lacks). A value is compared with the list as upstream
compares it, case ignored only where upstream ignores it, and it is sent, and recorded in
`meta.request`, as the caller gave it (sdk-usda-nass's values, which Quick Stats compares
without case).

## 6. HTTP client (`xippios.core.client`)

- `httpx`, async core, sync facade (ADR-0002). Source packages expose sync functions;
  async variants are optional and suffixed `_async`.
- Retries with exponential backoff and jitter: a 429 for every method; a 5xx and a
  transport failure for idempotent methods only (GET, HEAD, OPTIONS), unless the source
  sets `RetryPolicy.retry_non_idempotent` because upstream makes a repeated write safe,
  or because the source only reads through POST (ADR-0011); never another 4xx.
- A source maps its error shapes once, in `ClientConfig.classify`, which sees every
  response before the default status mapping (ADR-0031): the shapes upstream documents
  and, where upstream documents none for an answer, the shapes the source recorded, each
  backed by a fixture of that answer that a test passes to `classify` through
  `response_from_fixture` (ADR-0031, decision 2). Its endpoint
  wrappers then use `get_json`, and a write wrapper `post_json` or `delete_json`, which
  return `None` for an answer with no body (ADR-0037, decision 7),
  and never inspect status codes themselves. A wrapper
  whose answer may come from the cache calls `get_answer()`: its `Answer(payload,
  retrieved_at)` carries a hit's stored time, from `xippios_cache_stored_at`, or else
  the arrival time, for `meta.retrieved_at` (ADR-0037, decision 5); one that
  needs more of the response calls `get()`, then `decode_json()`. `Answer` is generic
  over its payload: `get_answer(path, parse=list[Region], endpoint="regions")` parses
  the payload with `parse` and returns an `Answer[list[Region]]`, and a wrapper that
  returns a value it derives from the payload returns `Answer(value,
  answer.retrieved_at)`, never a pair of its own (ADR-0037, decision 5).
- A per-source rate limiter sets a fast pace within the source's documented per-second
  or per-minute limit or, where none is documented, a self-imposed pace that the
  package's CLAUDE.md names as such; longer-window quotas (hourly, daily) may be
  exhausted, not rationed (ADR-0033), and per-endpoint windows shorter than an hour
  (X's 15-minute windows) are left to `classify`, with no `QuotaPolicy` until a policy
  keyed per endpoint exists (ADR-0033, decision 2). `classify`
  interprets the upstream's 429, or its documented answer to a spent limit, as
  `RateLimitError` with `retry_after` (from `Retry-After`, the quota headers or a
  documented fallback), the client keeps a quota snapshot from the quota headers
  (`QuotaPolicy`, ADR-0037), and retries honour `retry_after` up to `backoff_max`. A
  request into a quota the snapshot shows spent waits it out inside the call, logged,
  when the wait is within the policy's `pause_cap` (30 s by default), and otherwise
  raises `RateLimitError` with `retry_after` without sending; a pause handed back to the
  caller is stated in the error text.
- One limiter paces each host a source sends to, and core builds one per client
  (ADR-0033, decision 1). A second base URL on the host of the first
  (Eurostat's `https://ec.europa.eu/eurostat/api/comext/dissemination` beside
  `https://ec.europa.eu/eurostat/api/dissemination`) is requested through the source's
  one client by its absolute URL, which httpx takes over the base URL: one limiter, one
  cache and one `classify`, whose path checks name both bases. A request to an origin or
  mirror that the publisher runs itself (§2) takes the canonical host's pace, one limiter
  for both hosts where the source sends to both; its `meta.endpoint` names the URL sent,
  but a file keeps the file's name there, the mirror's URL going in `meta.request` (§4;
  https://github.com/xippios/sdk-core/issues/276), and `docs/upstream/` names both hosts
  (sdk-usda-wasde's USDA CDN origin for `www.usda.gov`). A dependent's own client sends nothing to its dependency's host, which
  the dependency's limiter alone paces, since a second limiter there would allow up to
  twice the pace each package meant.
- Two hooks on `ClientConfig` see what passes through the client (ADR-0037):
  `before_request`, called once per call after the cache lookup and before the rate
  limiter, may wait or raise a taxonomy error, and then nothing is sent; `observe` sees
  every response from the wire, retried attempts and raw responses included and a cache
  hit never, before `classify`. `QuotaPolicy(...).install(config)` sets both to the
  policy's own, replacing any the config had, and is the family's implementation of the
  quota rules above (ADR-0033); a source whose answer to a spent limit is not a 429
  passes `spent=`, which reads that answer. No source subclasses `AsyncClient` for them.
  Every request the client builds says where its credentials go in two extensions, which
  both hooks read (`observe` on `response.request`): `xippios_auth`, `client`, `none` or
  `own`, and `xippios_origin`, `base` or `other` (ADR-0037, decision 4).
  Before a 429 or 5xx is retried, the client asks `classify`: a `RateLimitError` sets the
  wait from its `retry_after`; an `UpstreamError` for a 5xx changes nothing; any other
  error ends the retries.
- Optional response cache (in-memory by default, pluggable) keyed on method+URL+params.
  A body larger than `ClientConfig.cache_max_bytes` (default 8 MiB) passes through and
  is not stored; `cache_filter` stays for finer rules. A source that wants a larger
  answer cached raises the bound and says why in its `CLAUDE.md` (ADR-0040). Every GET
  reads the cache, and only `get_answer()` stores an answer in it: a 200 once its body
  decoded and, with `parse=`, its payload parsed, so a body that fails is requested
  again on the next call; `get()`, `get_json()` and `request()` store nothing
  (ADR-0037, decision 5).
- A file is downloaded, never held in memory (ADR-0040): `download(url, dest, *,
  auth=...) -> Downloaded` streams the body to `dest` under a temporary name, renames it
  when complete and removes it on failure, and never touches the response cache. The
  limiter, the hooks (`before_request`, `observe`), `classify` and the retry rule apply
  as they do to `get()`, and `auth` works as it does there; a retry restarts the file;
  except that `observe` and `classify` see a success's status and headers only, its
  body going to the file unread, and a 1xx or 3xx raises `UpstreamError`, since
  redirects are not followed (ADR-0040, decision 1). A `dest` that is a
  directory, or whose directory does not exist, is refused with `InvalidRequestError`
  before anything is sent, and the file is written with mode `0600` (ADR-0040,
  decision 1). `Downloaded` carries `path`, `bytes`, `content_type`, the file
  name from `Content-Disposition` when sent, `etag`, `last_modified` and `retrieved_at`.
- `decode_text(response)` (charset from `Content-Type`, UTF-8 by default, a BOM
  stripped) and `decode_csv(data, *, delimiter=",", source=None)` (a path, a response or
  an open text stream, such as a gzip or ZIP member the source opens, ADR-0040,
  decision 2; the stdlib's `csv.DictReader`, headers as upstream
  prints them) sit beside `decode_json`. The source opens gzip and zip with the stdlib;
  core ships no XML, spreadsheet or PDF parser (ADR-0040, ADR-0020).
- Credentials come from the client's `auth`, which goes to the base URL's origin, its
  scheme, host and port, and to no other: a request to another origin, a file link on
  another host, is sent without them, and a call that must send credentials there passes
  an `httpx.Auth` of its own (ADR-0037, decision 4). A call to a
  keyless endpoint on the same host passes `auth=None` and is sent without them; another
  `httpx.Auth` replaces them for one call; no second client is needed to leave the key
  off (ADR-0037). `auth=None` and the client's own share the cache; a call with an
  `httpx.Auth` of its own bypasses it, neither looked up nor stored. A request sent with
  `auth=None` or to another origin spends no quota: the `QuotaPolicy` neither holds it
  back nor reads its answer, and the limiter still paces it (ADR-0037,
  decision 2).
- One `User-Agent`: `xippios-<source>/<version> (+https://github.com/xippios)`.
- Timeouts explicit; defaults 10 s connect, 60 s read.
- A request body is JSON (`json=`) or form-encoded (`data=`, for an upstream whose
  writes take form fields), as upstream documents it; never both.

## 7. Configuration

The environment is read through the `EnvKeyAuth` helpers (`QueryKeyAuth`,
`HeaderKeyAuth`, `BearerAuth`, `BasicKeyAuth`), on the first request: keys from
`<SOURCE>_API_KEY`, or the issuer's variable where ADR-0032 applies, overridable by
constructor argument (`key=`; ADR-0002, amendment 2026-10-27). An upstream that exchanges a
long-lived credential for a short-lived bearer, a login or a refresh token, is served by a
subclass of `RenewingBearerAuth`: the source writes its token request (`token_request`) and
the reading of the answer (`read_token` for an HTTP 200, `token_refused` for any other
status, by default the taxonomy error of the status, quoting nothing of the answer), and
reads each credential through `credential(name)`, from `credentials=` or else from the
variable, when it builds the request. The base keeps the bearer until `margin` seconds, 60
by default, before its `expires_in` runs out, and on a status of `renew_on`, 401 by
default, exchanges once more and sends the request again, once (ADR-0025, amendment
2026-11-18, point c). No config files, no dotenv loading inside the package — the
environment is the contract (direnv in development, secrets in CI). A source behind
api.data.gov takes its key, its gateway answers and its
quota from `xippios.core.data_gov`: `Gateway(SOURCE)` gives the `auth` on
`DATA_GOV_API_KEY`, the `classify` its own `classify` asks first, and `install`, which puts
the one `QuotaPolicy` per process for that key on its config (ADR-0032, decision 5). The
gateway's `classify` reads the answers of the base URL's origin alone, and
`Gateway(SOURCE, data_path=...)` maps FAS's empty `text/plain` 404 on the source's data
paths to `xippios.core.data_gov.NoDataForYear`, a `NotFoundError` that says the year holds
no data (ADR-0032, decision 5).

Whoever works in a repository of the family, a person or an agent, never reads or prints
`.envrc`, `.env` or a variable that holds a credential: each one the package reads a
credential from, and any whose name ends in `_API_KEY`, `_TOKEN` or `_SECRET`, a
`_REFRESH_TOKEN` among them. A leak check greps the files for key patterns; it never
compares against a key (ADR-0030, decision 6).

A multi-tenant source, whose upstream serves each tenant from a host or under a key of
its own (CashCtrl's organisations, Gmail's accounts), declares its tenants with core's
`Tenants`, one client each, and names the tenant of every result in `ResultMeta.tenant`
(§4; ADR-0036, decisions 1 to 5); its messages and
results name tenants and variables, never a value (ADR-0030). Its `tests/conftest.py`
calls `keep_reserved_tenants(TENANTS)` from `xippios.core.testing` when pytest imports it,
so that no fixture and no test sees a tenant but the reserved one, `demo`: the list
variable and every other tenant's variables are removed, by the registry's scheme, and
the rest of the prefix stays (ADR-0042, decision 1). The registry, the
strip and §8's lock and serve command bind such a source from its adoption of core 0.4.0,
which deletes its copies (ADR-0025, amendment 2026-11-18, points b and d).

One tenant per call, in core and in a multi-tenant source's own tasks: no task, tool or
helper in core works across tenants (ADR-0036, decision 11), and each task of the source
takes exactly one tenant, required, the tenant list returns names only, and nothing is
shared between tenants (ADR-0036, decision 13). The source declares the parameter that
names a tenant once, on its registry, `Tenants(..., param="org")`, required: the family
check, the serve command's option and every `TenantLock`, which takes the registry, read it
there, so none names another. Core checks the rule where it can break unseen.
`bind_tasks` refuses, naming the task and the parameter, a task that lacks the lock's
parameter, unless it is the tenant list or its module declares it by name as touching no
tenant, in `NO_TENANT_TASKS`, a frozenset beside `BULK_TASKS` in `tasks.py` or
`tasks_write.py`; a bound server serves a task so declared as it is. The family check holds
every task of a source with a `Tenants` registry to the rule, with no opt-in: the
registry's `param` once, required with no default, of a type that names one tenant, a `str`, the
tenant list and the declared tasks excepted (ADR-0036, decision 13). Both read signatures:
a task that takes one tenant and opens another's client is the review's to find
(https://github.com/xippios/sdk-core/issues/302). The rule binds a source from its adoption
of core 0.4.0.

A source's `_client.py` declares the variables it needs as `EnvVar` entries,
`xippios.core.EnvVar(name_or_pattern, *, secret, required)`: a variable's name, or a pattern
with a placeholder such as `<NAME>` for one variable per tenant (`CASHCTRL_<NAME>_API_KEY`),
with whether it is a secret and whether it is required, which each entry states. An `EnvVar`
names a variable and never reads one. The rule binds a source from its adoption of core 0.4.0
with sdk-template 0.4.0, which renders it (ADR-0026, amendment 2026-11-18, point c).

## 8. MCP conventions

- Register task functions, not endpoint wrappers. Tool name `<source>_<verb>_<noun>`.
- The function docstring is the tool description: first line one sentence, then an
  `Args:` block explaining every parameter with examples of valid values. Agents read
  this; write it for them.
- An enum's class docstring reaches the tool's input schema through the parameter type,
  so it holds what an agent needs, what the values are and the upstream list they come
  from with its fetch date (what `render_enums` writes); maintainers' notes go into
  comments, never into the docstring (ADR-0031, decision 6).
- Read-only by default. A tool that writes to the upstream (CashCtrl) lives in a
  separate server entry point (`xippios-<source>-mcp-write`), takes `confirm: bool`
  and returns a dry-run preview when `confirm=False`. `register_tasks(read_only=False)`
  enforces it: a task without `confirm: bool = False` is refused before anything is
  registered (ADR-0036). A write server carries no authentication, so `--http` serves
  it on a loopback host only (`LOOPBACK_HOSTS`: `127.0.0.1`, `localhost`, `::1`) unless
  `--allow-remote` is passed, with a gateway in front. A read server that reaches what
  no deployment may serve without authentication, sdk-google-mail's mailboxes, is built
  with `build_server(..., loopback_only=True)` and held the same way; `is_loopback_only`
  tells a host either kind (ADR-0025, D-a, and amendment 2026-11-18, point a). A write server exposes write tools only; reference tools
  stay on the read server. A source tests its write server with
  `xippios.core.testing.assert_write_tools`: a write server, its tools exactly the write
  tasks, each taking `confirm: bool = False` as its last parameter, and none of them a
  tool of the read server or a route of the router (ADR-0042, decision 1).
- Server names (ADR-0026): a source with a write server names its servers
  `xippios-<source>-mcp-read` and `xippios-<source>-mcp-write`, with no alias for the
  old name; a read-only source keeps `xippios-<source>-mcp`. `server.name` stays the
  slug the server is built with (`build_server`'s `xippios-<source>` unless the source
  names it), whatever its entry point is called. A group of the host xippios-mcp follows
  the rule (`accounting-read`, `accounting-write`) and never mixes read and write tools;
  the host refuses one that does at startup. The rule binds sdk-cashctrl at its own
  0.4.0, a breaking change of an entry point (§12), and sdk-google-mail from its 0.1.0.
- Result cap: default 200 rows or 64 KB, whichever first, bytes counted in the UTF-8
  encoding of the compact JSON text. Over the cap, return the first page plus a note on
  how to narrow the query. Never truncate silently. A result whose `data` is a model that
  holds one list of rows, and no other field a list, returns whole within the byte bound
  and past it is cut by those rows, its other fields whole; any other result past the
  byte bound is the note and a preview of its first bytes (ADR-0038, decision 4). A
  reference tool whose whole list an agent needs gets a cap of its
  own, keyed by the task function's name, with the rows and bytes the source judges it
  needs (`register_tasks(..., caps={"list_partners": ResultCap(max_rows=400,
  max_bytes=100_000)})`). So does a tool whose result is one upstream page that must
  return whole, a cursor-paged page with the `next_token` the caller needs for the next
  page or a bounded lookup, which a cut at the default would turn into a preview or cut
  by its rows, its cursor then past the rows the cut left out: a byte bound of its own,
  the row bound unchanged (sdk-x's post tools and `lookup_users`; ADR-0038,
  decision 4). So does a tool whose result is one upstream document or table that an
  agent reads whole, a report or a statement (sdk-cashctrl's `get_report_data`, 131,072
  bytes) or a table's page or a matrix (sdk-usda-wasde's `get_table`, 400 rows, and
  `get_balance_sheet`, 300 rows, each 131,072 bytes): the rows and bytes the source judges
  it needs, and a note that says how to read a part of it (ADR-0038, decision 4). A
  byte bound above the default is a deliberate choice for that
  tool, and every other tool keeps the default (ADR-0038).
  The note never promises a filter the tool lacks: the default says "narrow the query to
  see the rest", and a tool with filters names them in its cap's `note`. A cut list whose
  `meta.request` records an integer `start`, an offset-paged task's, ends its note with
  `; resume with start=<start + shown>` (ADR-0038, decision 3). A cut that
  shows no row, since the first row alone passes the byte bound, says so, naming the row
  at that `start`, and names no resume offset (ADR-0038, decision 3).
  Since a cap's note names a task's filters, a source keeps its caps with its tasks, as
  `MCP_CAPS: Mapping[str, ResultCap]` in `tasks.py` next to `__all__`, and its `mcp.py`
  passes them through as `caps=getattr(tasks, "MCP_CAPS", None)`.
- A task named in `BULK_TASKS` (a frozenset in `tasks.py` beside `MCP_CAPS`) is not a
  tool: `register_tasks` skips it (ADR-0040), and `tool_functions(tasks)` gives
  `tasks.__all__` without it. No tool returns a file path to an agent. A task's name is
  its entry in `__all__`, and its function's `__name__` is the same, which
  `tool_functions` checks: a tool's name, an `MCP_CAPS` key and a `BULK_TASKS` entry read
  that `__name__` (ADR-0026, amendment 2026-11-18).
  The MCP surface of a bulk source is its catalog tasks (which files exist, with sizes
  and release identifiers) and, where the slice fits the result cap, a filtered read of
  the file.
- Reference lookups are tools too: `<source>_list_<thing>` (commodities, countries,
  attributes). Agents need them to form valid calls.
- A multi-tenant source's tenants are such a tool, `list_task(TENANTS, name=...)`
  (`cashctrl_list_organisations`, `google_mail_list_accounts`), on the read server
  (ADR-0036, decision 6). Its servers take `--<param>`, sdk-cashctrl's `--org` and
  sdk-google-mail's `--account`, which binds a server to one tenant: the entry point runs
  `serve_tenants(server, build, TENANTS, check=...)` from `xippios.core.mcp`, its option
  the registry's `param` (ADR-0036, decision 13), and `build(lock)` passes the tasks through `bind_tasks(tasks, lock)` and the
  instructions through `tenant_instructions(text, lock, bound=...)` and returns its tool
  set, from which `serve_tenants` builds the bound server, named as `server` is (ADR-0026,
  amendment 2026-11-18, point d). No tool of a bound
  server takes the tenant's argument, so a call that names it is refused as an argument
  the tool does not declare; the tenant list lists the bound tenant alone; and the
  instructions end with a sentence that names the tenant, after `bound`, the bound
  server's own text, where the source gives one. An undeclared tenant, or an error of the
  source's startup `check`, stops the process with exit status 2 before the bound server
  is built. The HTTP router takes no lock (ADR-0036, decision 7).
- Errors return as text starting with `error: <ErrorClass>: <message>`; never raise
  through the MCP boundary. Arguments a tool's schema refuses are answered the same way,
  before the tool runs, by a middleware `register_tasks` installs once per server:
  `error: InvalidRequestError: <argument>: <message>`, the first error with the count
  when there are several, never pydantic's rendered error (its URL, input type or input
  value) (ADR-0036, decision 12). So is an argument the tool does not declare,
  named with the ones it declares (`error: InvalidRequestError: yaer: Not an argument of
  this tool; it takes series_id, year`), and a constraint that an `Annotated` parameter
  declares holds in the tool's schema and in the check (ADR-0036, decision 12).
  An error answer also sets `isError` on its tool result, which core 0.4.0 carries and
  which binds a source from its adoption of that release
  (https://github.com/xippios/sdk-core/issues/168; ADR-0026, decision 6, and amendment
  2026-11-18, point b); until then a client tells an error answer by the text.
- An error that a tool can return and that names another task, the one to call instead or
  the list task that names the known values, names that task's MCP tool too, as
  sdk-usda-nass's refusal of a value its packaged list lacks does:
  `list_param_values('state_alpha') lists the known values (over MCP, the tool
  usda_nass_list_param_values).` A task of `BULK_TASKS` has no tool, and an error names it
  alone (ADR-0041, decision 11).
- An entry point, `xippios-<source>-mcp` or, for a source with a write server,
  `xippios-<source>-mcp-read` and `xippios-<source>-mcp-write`, runs stdio by default;
  `--http` for streamable HTTP.
  A source's own options reach core's `main` through `add_options` and `apply_options`,
  parsed once with core's; an error applying them stops the process with exit status 2.
  A source's `mcp.py` defines `build(**options)`, its options keyword arguments with
  defaults, a multi-tenant source's `lock: TenantLock | None = None`, which returns its
  `ToolSet` (`xippios.core.mcp`): its tasks as its lock binds them, `caps`, `instructions`,
  `version`, `read_only`, `loopback_only` and the two hooks. Its module-level `server` is
  `build_server(build())`, and its entry point passes the tool set's hooks to `main`.
  `build` takes no `transport_security`, which a host passes to `streamable_http_app`. The
  rule binds a source from its adoption of core 0.4.0 with sdk-template 0.4.0 (ADR-0026,
  amendment 2026-11-18, point c). A host builds one server from the tool sets of several
  packages with `register_tasks(server, tool_set)`, each tool with its own package's caps,
  and applies a package's hooks as its entry point does without options, with
  `tool_set.option_defaults()` (ADR-0026, amendment 2026-11-18, point d).

## 9. HTTP adapter conventions

FastAPI router generated from task functions via `xippios.core.http.router_from_tasks`;
one tag per source; responses are the `Result[T]` envelope; errors as RFC 9457
problem details. A task whose parameters are all scalars is a `GET` with query
parameters; a task with any non-scalar parameter (a mapping, a list, a model) is a
`POST` whose JSON body is an object keyed by parameter name (ADR-0007). An argument that
a route's typed parameter refuses is answered before the task runs as problem details,
status 422 with the title `InvalidRequestError` and the detail `<argument>: <message>` of
§8, never with the input, and a parameter's `Annotated` metadata holds in the route as in
the tool (ADR-0007, amendment 2026-11-18). Mounted by the consumer, never served
standalone from the package. A task named in `BULK_TASKS` gets no route:
`router_from_tasks` skips it, and no route returns a file path (ADR-0040).

## 10. Testing

- Unit tests run offline against recorded fixtures (`respx`); fixtures live in
  `tests/fixtures/<wrapper>/<case>.json`, the directory named after the wrapper function
  (§2; ADR-0028, decision 3), and are recorded by the `record-fixture`
  command, never hand-written. `<case>` is lowercase snake case for the words the source
  chooses; an upstream code inside it is written as upstream writes it
  (`CH_2026_8.json`). A fixture recorded through a task rather than a wrapper, such as a
  download's metadata or a helper's answer, lives under the task's name; file samples
  keep `tests/fixtures/files/<file_kind>/` as before (ADR-0020). Three further cases
  name their directory as follows (ADR-0028, decision 3). A wrapper
  whose every exchange is recorded through a task has no directory of its own
  (sdk-google-mail's `messages_get`, recorded through `get_message` and
  `search_messages`). Where two wrappers of a package carry one name, as the wrappers of
  two service modules can (§2), each one's directory is `<service>_<wrapper>`,
  `<service>` its module's name, and the PR that adds the second wrapper moves the first
  one's fixtures. An exchange of an auth flow, a login or a token refresh, which goes
  through neither a wrapper nor a task, lives under the name a wrapper of its operation
  carries by §2 (sdk-faostat's login under `auth_login`, its wrapper's), and one sent to
  another host than the base URL's under that host's first label and its path
  (sdk-google-mail's refresh at `https://oauth2.googleapis.com/token` under
  `oauth2_token`).
- A test may serve or read a body that was not recorded where and as the test uses it,
  of five kinds, and says where the body comes from where it builds it, as the sources'
  `NOT RECORDED` docstrings do (ADR-0028, decision 8):
  - a body that `docs/upstream/` documents and upstream will not produce on request,
    read verbatim from the snapshot at test time (sdk-eurostat's asynchronous
    `warning`);
  - a body composed from what the snapshot documents, a row of a documented table or a
    documented error, in the shape upstream was recorded answering (sdk-eurostat's
    fault-table rows; api.data.gov's `NOT_FOUND` in sdk-usda-psd, sdk-usda-esr and
    sdk-usda-gats);
  - a recorded answer or sample served at another URL, with `url=` or in memory, for a
    state upstream answers alike there, within one operation or behind one gateway
    (sdk-usda-esr's empty answer at other market years, sdk-usda-gats's api.data.gov 429
    as sdk-usda-psd recorded it), or anywhere for a test that asserts only what was sent
    (sdk-eurostat's codelist query on the Comext base); never one operation's answer
    for a state another operation was never seen in
    (https://github.com/xippios/sdk-core/issues/121);
  - a recorded answer or sample changed in memory, served at another status, with a
    header replaced or removed, or with a field, a cell or a byte changed, for a form
    upstream was not seen to send (sdk-eurostat's asynchronous `error` array at HTTP 200,
    sdk-usda-psd's empty 404 with its content type upper-cased, sdk-faostat's samples
    changed to show a parser's refusal);
  - a body of no shape upstream sends, to show that the source leaves it to core
    (sdk-usda-esr's 400 in another shape).

  The test asserts what the source does with such a body, never that upstream sends it.
  Once upstream is recorded giving a documented answer, the recording replaces the test's
  documented body; a documented shape never seen keeps its test where the recorded answer
  takes another shape (sdk-eurostat's `warning`, beside its recorded `error` array).
- A PR deletes a recorded fixture that no test replays after its change and names it in
  its description; a fixture that a test or a document still cites stays
  (sdk-usda-nass's `get_param_values/statisticcat_desc.json`, replayed by nothing once
  the list was packaged; ADR-0039, decision 8).
- A fixture file a PR adds or changes stays under 256 KiB (ADR-0040). A file the PR only
  moves, its content unchanged, is neither, so a fixture over the cap recorded before the
  rule bound moves with its directory (§2) and stays until a PR re-records it. A download
  fixture holds a small real answer (a short date range, one commodity), the sample of
  the file that its parser tests read, marked `sample: true` as the next bullet says, or
  the first N rows or bytes of the file: the recorder truncates on request
  (`max_bytes=`), marks the fixture `truncated: true` and keeps `original_bytes` and the
  sha256 of the full file.
  An XML, ZIP, gzip, XLS or XLSX fixture is a small real sample (a short query, one
  member of the archive, a few rows), never a byte-truncated file, since a cut-off binary
  or compressed file cannot be parsed and a cut-off XML document is not well-formed; byte
  truncation (`max_bytes=`) applies to text bodies, and the recorder refuses it for those
  formats and for a body that is not UTF-8 text; a JSON array is truncated by elements:
  the recorder cuts its original text after the first N elements that fit, or keeps the
  last N on request (`keep="last"`, for a list ordered oldest first), never
  re-serialising them, marks `truncated: true` and records the full count
  (`original_count`) and the sha256; a JSON object is cut so at the array that a
  top-level key names (`array_key=`), the rest of the object kept as upstream wrote it,
  and an object with no key named is refused, and the source records a small real
  answer (ADR-0040, decision 5). `max_bytes` bounds the body,
  not the fixture file, which escapes the body as a JSON string.
  A test on a sample or a truncated fixture asserts the parser's shape, never a size.
- A file-distributed source keeps a sample of each file kind under
  `tests/fixtures/files/<file_kind>/<case>.*` with a provenance line: the release id, the
  URL, the sha256 and bytes of the full file, and the fetched time in UTC with `Z`
  (ADR-0020). A binary file carries no comment, so the lines are one row per file in
  `tests/fixtures/files/README.md`. Its parser tests read the sample; the download call
  replays the recorded exchange of the bullet above. One live test per file kind fetches
  the current release and checks that the parser still reads it: shape, headers and
  sheet names, never values. The recorded exchange of a download may carry that sample
  as its body, so that the download replays the file the parser tests read; it is then
  marked `sample: true` with the full file's `original_bytes` and sha256, never
  `truncated`, which stays the recorder's cut (ADR-0020, amendment 2026-11-18, point a).
  Where the file a test needs is over the cap and its format cannot be cut by bytes, a
  script writes the sample from one download, never by hand: a workbook rewritten with
  the sheets and cells the tests need, which the script reads back and compares with the
  original cell for cell (sdk-usda-wasde's XLS, copied into a workbook written with
  xlwt), an archive rebuilt around one member cut to its header and first rows as
  printed (sdk-faostat's RL ZIP), or an XML document cut by whole elements as the file
  has them (sdk-usda-wasde's `<srNN>` pages). The sample's row adds a column that says
  what it keeps (sdk-usda-wasde's `Kept`, sdk-faostat's `What`) (ADR-0020, amendment
  2026-11-18, point d).
- Replay matches a fixture on method, host and path, and on the recorded query
  parameters a test names (`match_params`); a parameter whose recorded value holds
  `REDACTED` cannot be matched and is refused by name. A parameter's absence cannot be
  matched: where two fixtures share a path, the more specific one is mounted first,
  since `respx` tries routes in the order they were added. What a route received reads
  as plain values: `sent_urls` and `sent_query` the URLs, `sent_bodies` the bodies, a
  JSON body decoded and a form as a mapping of its fields, each with credentials redacted
  by the rule of §4 (ADR-0035, decision 9).
- The recorder sends one request through the source's client and records the answer
  whatever its status: never retried, whatever the client's `RetryPolicy` says, and never
  answered from the cache, so a recording spends one request and needs no client of its
  own (ADR-0037, decision 6). It reads at most `max_read_bytes` of the body,
  32 MiB by default: past it the reading stops, and the recording is refused before
  anything is written (ADR-0040, decision 5).
- The recorder scrubs in memory and writes once, so nothing unscrubbed touches disk, and
  names the values that must never be written (`xippios.core.testing.Scrub(secrets=...)`),
  or reads those known only from the answer, such as a login's or a refresh's tokens
  (`Scrub(response_secrets=...)`, ADR-0042, decision 3), each replaced as
  given. The scrubbed exchange is verified before the write: a named or read value still
  present as given in the URL, a header value or a text body refuses it, the error
  naming where, never the value. The verify is a backstop, with the fixture grep of
  the definition of done; a form the source's values take that differs from them
  (percent-encoded, behind a JSON escape), or a tenant's host to replace, the source
  rewrites in its own recorder step, on the `Fixture`, and writes it with core's
  `write_fixture`, laid out as the recorder writes it (ADR-0042, decision 4).
  A body that is not UTF-8 text cannot be scrubbed and is refused unless the recording
  flags it (`allow_binary=True`, stored base64 with `body_base64`). The recorder drops
  the response headers that only identify a request (`x-request-id`, `x-amz-cf-id`,
  `x-transaction-id` and the others `REQUEST_ID_HEADERS` names), which change with every
  recording and trip the secret scan (ADR-0040, decision 5).
  The scrub redacts credentials by the rule `ResultMeta` applies (§4): a parameter named
  `key` is data unless a `QueryKeyAuth` sends the key under that name (ADR-0040), and a
  `token` name its source declared data is written as sent, so replay can match it
  (ADR-0040, decision 6).
- Live tests are marked `@pytest.mark.live`, skipped unless `XIPPIOS_LIVE_TESTS=1`,
  and run in CI only in the one live workflow, `.github/workflows/live.yml`, in the shape
  the template renders (a source whose secrets differ keeps that shape): one job,
  `contents: read`, on a nightly schedule and on `workflow_dispatch`, never on a pull
  request. The key reaches only that job's `uv run pytest -m live` step, from the org
  secret; checkout, setup-uv and `uv sync` never see it. Sources that share a key stagger
  their nightly start, so that they do not draw on the shared quota together; the
  template derives the time from the slug (ADR-0032, decision 6). Every live
  run takes `--tb=short --assert=plain`, since the log of a public repository is public:
  the first keeps a failing test's frame arguments out of it, a raw upstream payload among
  them, and the second the values a failed `assert` compares. A live test asserts on
  shapes and counts, never on a raw payload (ADR-0032, decision 6).
- The pytest plugin (`pytest_plugins = ["xippios.core.testing.plugin"]`) keeps the
  default run offline and free of real keys (ADR-0035):
  - No network, from `pytest_configure` on: while test modules are collected, in a
    fixture of any scope and in a test, a request through httpx's default transports
    raises `RuntimeError` naming its method and path; the plugin patches httpcore's two
    connection-pool methods, through which every default transport sends, proxies
    included (ADR-0035, decision 1). `respx` answers replayed and
    mocked requests as before, a `respx` route that passes through is refused like any
    other request, and a transport the test passes itself is untouched. A test that
    must reach the network is marked `network` (or `live`), and is let through with
    its fixtures. Exactly that and no more: pytest's own failure report may still
    print httpx's request repr (offline the key in it is the placeholder); a request
    made while a `conftest.py` is imported, before the plugin is configured, is not
    refused; a fixture of wider scope runs under the marking of the test that sets it
    up, and its teardown under the last test's, so a live clean-up fixture is
    function-scoped or runs in the separate nightly `-m live` job.
  - No rate-limit wait, in every test not marked `live`: a client's limiter neither
    waits nor takes a token. A test that asserts the limiter's waits is marked
    `rate_limited`.
  - No quota pause and no quota left spent, in every test not marked `live`: every
    `QuotaPolicy`'s snapshot is forgotten before and after the test, so a replayed 429
    cannot refuse the tests after it, and a policy neither waits nor refuses. A test
    that asserts the pause or the refusal is marked `rate_limited` (ADR-0037); the
    edges, snapshots shared by consecutive live tests, a quota spent by a fixture of
    wider scope, a subclass's override of `before_request`, are listed in ADR-0035 and
    ADR-0037.
  - Response caches, in every test not marked `live`: every `MemoryCache` is cleared
    before and after the test, so an answer one test cached never answers the route the
    next test mounts; a `CacheBackend` of the source's own is not cleared, and a source
    that keeps one clears it itself (ADR-0035, decision 6).
  - After a live run, the terminal summary prints one line per quota policy a live test
    left a reading on, `quota after the live run: <source>: <describe()>`, times, counts
    and the source only, for the release PR's report of the quota left (ADR-0035,
    decision 7).
  - Placeholder key, in every test not marked `live`: every `EnvKeyAuth` sends
    `PLACEHOLDER_KEY`, pinned on the class, and the variables named in the ini option
    `xippios_placeholder_key_envs` hold it; the fixture `placeholder_api_key` returns
    it, `None` in a live test. A source names there every variable that holds a
    credential of its own, its key's or several (sdk-google-mail's refresh token, client
    id and secret, sdk-faostat's user name and password; ADR-0035, decision 3), and
    carries no placeholder fixture of its own. Every credential that a
    `RenewingBearerAuth` reads through `credential` is the placeholder too, one given to
    the constructor included, and a variable unset or empty is still its `ConfigError`,
    so a source names each variable of its token request there (ADR-0035,
    decision 3).
  - Logger levels: the `httpx`, `httpcore`, `httpx2` and `httpcore2` logger levels are
    restored after every test, live ones included (ADR-0035, decision 5). They are saved per test, after fixtures of wider scope
    are set up, so one of those that changes a level leaves it behind.
- The family conformance check, `xippios.core.testing.family`, tests once, in core, what
  every source shares: the empty namespace levels, `py.typed` and `__version__`; the
  tasks `mcp.py` and `http.py` serve (`tasks.__all__` minus `BULK_TASKS`); every task,
  `tasks_write.__all__` included, synchronous, returning `Result[T]`, with an agent
  docstring; the README status table listing exactly the tasks; the template tag in
  `.copier-answers.yml`; the core bound of §12. The template renders
  `tests/test_family.py`, which collects it with one line
  (`from xippios.core.testing.family import *  # noqa: F403`), so it runs in every
  source's CI, and a source keeps no copy of its checks. The plugin's ini option
  `xippios_package` names the package under test where `src/xippios/` holds more than
  one `tasks.py` (ADR-0035, decision 8). A source's write server is its own to
  test (ADR-0042).
- Every task function has at least one fixture-backed test and one live smoke test.
- Coverage is reported, not gated; mypy strict and ruff are gated.

## 11. Tooling

`uv` for everything (lock, sync, build, publish). Python ≥ 3.12. `ruff` (lint +
format, line length 100), `mypy --strict`, `pre-commit` with those two plus
`detect-secrets`. Dependencies pinned by `uv.lock`; runtime deps declared with
lower bounds only, except `xippios-core` and a source package the source depends on,
which §12 bounds to one minor.

## 12. Versioning and releases

- SemVer. Pre-1.0: only a breaking change bumps the minor, as `/release-prep` step 4
  reads; added tasks or parameters make a patch, which reaches every dependent inside
  its `~=X.Y.0` bound (ADR-0039, decision 1). A source's adoption of a core minor is a
  breaking change of the source and takes a minor, whatever else its release brings: it
  moves the source's core bound to the new minor, so its release no longer installs beside
  a package still bound to the old one (ADR-0039, decision 1).
  Post-1.0: breaking changes bump major.
- An upstream API change that changes our public surface is a breaking change.
- A source depends on one core minor with an upper bound, `xippios-core~=0.2.0`, and its
  extras likewise (`xippios-core[mcp]~=0.2.0`); the template renders it as `~=X.Y.0`,
  or `~=X.Y.Z` when patch Z shipped what the source adopts, still one minor
  (ADR-0039, decision 1). Core patch releases stay compatible. While core is
  0.x it keeps no backward compatibility across minors: a new core minor may break, and
  a source adopts it through §15 before its next release. From 1.0 a breaking change
  bumps the major (SemVer), and the `~=` bound stays. A source already published with an
  open bound stays as published and gets the bound with its next release.
- `CHANGELOG.md` in Keep a Changelog format. Every PR but a release's and Dependabot's
  brings its entry as a fragment, a file of its own under `changelog/` that holds the
  entry's bullet, in the form `changelog/README.md` gives; the release PR assembles the
  fragments into its section of `CHANGELOG.md` and deletes them (ADR-0039, decision 6).
  A repository that keeps no `changelog/` yet, a source before its adoption
  of the template release that brings the folder, adds its entry under
  `## [Unreleased]` of `CHANGELOG.md` instead. A release's section says an internal
  label, such as a decision's number or a plan's item, in plain words, since
  `publish.yml` makes the section the message of the tag it pushes (ADR-0039,
  decision 6).
- The release train (ADR-0039, decision 6): the reference-data refresh, where
  a source has one, runs before the release. It is a PR of its own, merged before the
  release PR, only when a record changed or `fetched` goes from a bare date to the full
  time (§4); otherwise the run gets no PR of its own and the release PR cites it,
  "unchanged" meaning the records, not the files (ADR-0039, decision 6). A release PR
  changes only `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`,
  `docs/handover.md` and the fragments under `changelog/`, which it deletes. Release =
  the release PR merges on `main` → `publish.yml` tags `vX.Y.Z` from `pyproject.toml` on
  the merge commit → environment `pypi` → a human approves → the trusted publisher
  uploads. A tag ruleset admits no other `v*` tag. sdk-template, which publishes nothing
  to PyPI, tags from the top `## [X.Y.Z] - ` heading of its `CHANGELOG.md` with its own
  `release.yml`, under the same ruleset. Yanks are a human action. No tokens anywhere.
- A source may depend on another source package, consuming its task layer only: it
  imports `xippios.<dep>.tasks` and its models, never `api/` or `_client`, and declares
  `xippios-<dep>~=X.Y.0`, one minor, like core (ADR-0021). Both share one core minor:
  the dependent adopts a core minor only after the dependency has released on it, and a
  new minor of the dependency reaches it through an adoption PR (§15). The dependency
  tags first; the dependent's release PR pins the published version. The dependent's
  adoption release follows the dependency's new minor right after, so the latest of both
  install together; a dependent that bundles the adoption with feature work says so in
  its release's section of `CHANGELOG.md` and accepts the window (ADR-0039,
  decision 6). A patch reaches the dependent inside its bound, so the adoption release
  follows a breaking minor only (ADR-0021, amendment 2026-10-29). The dependent's
  servers register its own tasks only; no cycles, one level only.

## 13. Repository hygiene

- Trunk-based: `main` protected by the org ruleset, a change reaching it through a pull
  request. Conventional Commits.
- Required files: `README.md`, `CHANGELOG.md`, `LICENSE` (Apache-2.0), `CLAUDE.md`,
  `docs/upstream/FETCHED.md`, `pyproject.toml`, `uv.lock`. `sdk-core` wraps no upstream
  and is exempt from `docs/upstream/` (ADR-0030).
- README structure: what it wraps · install (`uv add xippios-<source>[mcp]`) ·
  30-second example · MCP client config snippet · status table of covered endpoints ·
  upstream terms and attribution · licence.
- Topics on GitHub: `xippios-sdk`, `python`, `mcp`, plus the domain (`agriculture`,
  `trade-data`, `accounting`, `email` (ADR-0025), `social-media` (ADR-0027)) as
  appropriate.
- Workflows are hardened (ADR-0039, decision 7). Every action is pinned to a
  commit SHA with its version in a comment, and bumped deliberately. Every checkout sets
  `persist-credentials: false`, except in a job that pushes with the token (the release
  train's `tag` job), which says so in a comment. Every workflow declares
  `permissions: contents: read` at the top, and a job adds only what it needs. No
  `secrets: inherit`: a secret is passed by name to the one job that uses it. The
  reusable workflows of the organization's repository `xippios/.github` are called at
  `@main` by design, since they read their own `main`: the one reference to another
  repository that is not pinned.

## 14. What this family is not

Not a place for normalization across sources, scheduling, storage, or any product
logic. Those live in product repositories that depend on these packages.

## 15. Adopting a core or template release

A source adopts a new core minor, and the sdk-template release that goes with it, in one
adoption PR before its next release (§12, ADR-0039). The PR is judged against this list;
a template-only update, with no new core minor, is judged against the items it touches.

1. The core floor is raised: `xippios-core` and each of its extras name the new minor
   with the bound of §12 (`xippios-core~=0.2.0`), and, where the source depends on
   another source package, that package's minor likewise (ADR-0021); resolved from PyPI
   with no git pin left in `[tool.uv.sources]`, and `uv.lock` is updated.
2. `copier update` brings the repository to the template release, its conflicts
   resolved (not on routes (1) and (3) below).
3. Every local workaround that a core change replaced is deleted, its tests with it, and
   the PR description names the core change for each (`QuotaAwareClient` → `QuotaPolicy`,
   ADR-0037); the release's ADRs and CHANGELOG list them per source. In the other
   direction, code that core removed for its one consumer (ADR-0023, decision 5) is
   copied into that consumer as part of its adoption, from the commit core's handover
   names (`git show <sha>:<path>`); the PR description lists every copied file with the
   ADR that moved it (ADR-0042 for sdk-cashctrl at 0.3.0), and the reviewer judges the
   copy against that list.
4. Logic duplicated across sources is moved into core or dropped: what core now provides
   is dropped here; what it does not provide yet is carried by the source, named in the
   PR description and in an issue of sdk-core; a second source may carry the same helper
   when the issue names both; a third never: core takes it in that minor (ADR-0023). An
   issue of sdk-core names its consumers (ADR-0023).
5. Every test that asserted a limiter wait, a quota pause or key resolution is marked or
   overridden: a limiter wait or a quota pause marked `rate_limited` (ADR-0035,
   ADR-0037), key resolution given a module-level `placeholder_api_key` override that
   pins nothing (ADR-0035).
6. Generated enum files are re-rendered once with the release's renderer, through the
   template's refresh script, and committed as formatted, after the script's
   `ruff format && ruff check --fix` (ADR-0031, decision 6).
7. `mypy --strict` covers `scripts/` too (`files = ["src", "tests", "scripts"]`).
8. The current conventions version is applied (1.22's name rule excepted, §2): every rule
   changed since the version the source last applied holds in the source.
9. The PR's changelog entry, a fragment under `changelog/` (§12), names the core,
   template and conventions versions adopted.

Three routes depart from the list (ADR-0039, decision 2):

- (1) **A core release without a template tag**: the bound is raised with
  `copier update --vcs-ref=:current: -d core_version=X.Y.Z`, so `.copier-answers.yml`
  does not drift, and item 2 is not applicable. A core minor without its template
  release is no adoption until the template follows.
- (2) **A dependency's minor whose new surface the dependent uses**: the adoption PR
  stays pure, and the use is the next PR (ADR-0021, amendment 2026-10-29).
- (3) **A source frozen on a template tag** (sdk-cashctrl on template v0.2.2): no
  `copier update`, so item 2 is not applicable, and the core floor of item 1 is raised
  by hand. The template-rendered files are the source's own and listed in its
  `CLAUDE.md`; the template changes the new conventions version needs are hand-applied
  and listed file by file in the PR description, as
  https://github.com/xippios/sdk-cashctrl/pull/18 did.

The host `xippios-mcp`, scaffolded by hand from the template's shared files (ADR-0026,
decision 1), adopts a core minor in an adoption PR of its own without `copier update`,
judged against items 1, 3, 4, 7, 8 and 9: item 1 raises the bound of `xippios-core` and of
each of its extras, while its sources keep the `>=` floors of ADR-0026, decision 9, and item
9's fragment names the core and conventions versions it adopts. Items 2, 5 and 6 have
nothing to bind in it. The template changes that the new conventions version needs in the
files it was scaffolded from are hand-applied and listed file by file in the PR
description, as on route (3) (ADR-0026, amendment 2026-11-18, point e).

An adoption PR changes nothing else: no new endpoints, tasks or fixtures ride along. It
may delete the fixtures, mounts and tests that the adoption itself makes dead, and
nothing more (ADR-0039, decision 2). An adoption PR, which fetches nothing,
leaves `docs/upstream/FETCHED.md` to the next `/refresh-upstream` and ports only the
capture script's changes (ADR-0028, decision 4). The reviewer judges it
against this list and nothing else (definition of done, block "Adoption PR").
