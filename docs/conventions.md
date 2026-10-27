# xippios SDK family — conventions

Version 1.19 · 2026-10-27 · applies to every `sdk-*` repository under github.com/xippios.
Changes to this file require an ADR in `docs/adr/` and a PR against `sdk-core`.
The rules of ADR-0019 and ADR-0022, all of them (the download and decode calls, the
cache bound, `BULK_TASKS`, the fixture cap and the `truncated` marker, the file-fixture
rules, the spared `key`, the packaged-answer rule and the packaged-list file,
`published_at_naive`, the `None`-filter rule, `get_answer`, `matches` (§4), `UnknownCode`
(§5), the frozen series and the period series (§4)), bind a source from its 0.3.0
adoption (§15), since the code that serves them ships in core 0.3.0; until then a source
records what its upstream answers and names a fixture over the cap in the PR
description; a source that starts on a git pin of core 0.3.0 (the roadmap's pin rule) is
bound by each rule from its first PR on a pin that carries the rule's code.

## 1. Naming

| Thing | Pattern | Example |
| --- | --- | --- |
| GitHub repo | `sdk-<source>` | `sdk-usda-nass` |
| PyPI distribution | `xippios-<source>` | `xippios-usda-nass` |
| Import path | `xippios.<source>`; a provider with several APIs nests: `xippios.<provider>.<api>` | `xippios.comtrade`, `xippios.usda.nass` |
| MCP entry point | `xippios-<source>-mcp` | `xippios-usda-nass-mcp` |
| MCP tool | `<source>_<verb>_<noun>` | `usda_nass_get_series` |
| Env var for a key | `<SOURCE>_API_KEY`, or the issuer's variable when one key serves several sources (ADR-0009); per tenant of a multi-tenant source `<SOURCE>_<NAME>_API_KEY`, its other values `<SOURCE>_<NAME>_<FIELD>` (ADR-0014, §7) | `COMTRADE_API_KEY`, `DATA_GOV_API_KEY`, `CASHCTRL_ACME_API_KEY` |

`<source>` names the data provider and, where one provider has several APIs, the API:
`usda-nass`, `usda-psd`, `usda-esr`, `usda-gats`, `usda-esmis`, `usda-wasde` (a parser
package that depends on `usda-esmis`; ADR-0020, ADR-0021), `comtrade`, `eurostat`,
`faostat`, `cashctrl`.
No domain prefixes (`ag`, `agri`): sources are domain-neutral; grouping happens via
GitHub topics (`xippios-sdk`) and the org README.

The import path nests only where one provider has several APIs (ADR-0006): `usda-nass`
imports as `xippios.usda.nass`, `comtrade` as `xippios.comtrade`. Repository and
distribution names stay flat and hyphenated. Each generated repository records its
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

1. **Endpoint wrappers** — `xippios/<pkg>/api/*.py`. One function per upstream
   endpoint, named after the upstream operation, parameters as upstream names them
   (snake_cased), returning typed models that mirror the upstream payload.
2. **Task-shaped functions** — `xippios/<pkg>/tasks.py`. The functions a person
   or an agent actually wants: `get_balance_sheet(commodity, marketing_year)`. They
   compose endpoint wrappers, handle pagination and reference lookups, and return
   `Result[T]`. This is the public API and the only layer adapters may call.
3. **Adapters** — `xippios/<pkg>/mcp.py` and `xippios/<pkg>/http.py`.
   Thin: register task functions, apply result caps, map errors. Target ≤ 60 lines
   each. If logic appears here, it belongs in `tasks.py`.

Supporting modules: `models.py` (pydantic models), `reference/` (packaged data files
plus a loader), `_client.py` (the configured `xippios.core.client` instance).

A file-distributed source, whose upstream publishes files rather than answering with
records, keeps the three layers (ADR-0020). Its layer 1 has two parts: `api/` wraps the
HTTP endpoints it has (a catalog), and the download goes through core's `download` (§6)
or through the retrieval package the source depends on (§12, ADR-0021); `parse/` holds
one module per file kind, `parse/<file_kind>.py`, with one function,
`parse_<file_kind>(path) -> list[Model]`. A parser's library (a spreadsheet reader,
`pypdf`) is the source's dependency, never core's. A PDF is read for its narrative text
only, never for numbers: a figure a task returns comes from the XLS, XML, CSV or TXT the
release carries, or is not returned (ADR-0020). A bulk task, which returns
`Result[Downloaded]` or `Result[list[T]]` read from a file, lives in `tasks.py` like
every task and is named in `BULK_TASKS`, a frozenset beside `MCP_CAPS`; the adapters
skip it (§8, §9; ADR-0019).

## 3. Upstream fidelity (ADR-0003)

- Names and semantics come from the upstream documentation, which is snapshotted in
  `docs/upstream/` with a `FETCHED.md` recording the UTC time and the URL of the fetch.
  The snapshot is the reference for the agent; refresh it deliberately, by PR, and diff
  it.
- `Fetched` in `FETCHED.md` is the UTC time of the run in ISO 8601 with an explicit `Z`
  (`2026-10-24T09:15:00Z`), never a local date or time. A table that a Markdown pipe
  table cannot hold, one with merged cells (`rowspan`, `colspan`) or with a table nested
  in it, is kept as its HTML in the Markdown snapshot, and one line in `FETCHED.md` says
  so (ADR-0003, amendment 2026-10-24).
- A vendor's documentation is reproduced in the snapshot for reference (ADR-0003,
  amendment 2026-10-24): `FETCHED.md` carries the copyright line as the documentation
  states it (`© 2026 CashCtrl Ltd.`) and the URL the text was fetched from. A vendor's
  objection is honoured by replacing the snapshot with a summary that keeps the names and
  semantics the wrappers rely on.
- A source whose API is one part of a shared upstream document (several FAS APIs
  described in one OpenAPI document) snapshots its own part and records the full
  document's byte size and sha256 in `FETCHED.md`, so a refresh can tell the part from
  the whole (ADR-0003, amendment 2026-10-26).
- Within-source hygiene is required: dates → `datetime.date`/`datetime`, numbers →
  `int`/`Decimal`/`float` as appropriate, upstream enums → `StrEnum`, pagination
  resolved, errors typed. An upstream enum of integer ids becomes an `IntEnum` instead,
  so a member compares equal to the id in upstream's data (ADR-0008). Field names are
  upstream names in snake_case. A `Decimal` field of an `UpstreamModel` serialises as a
  JSON number in every adapter (ADR-0008); Python keeps the `Decimal`.
- Task-shaped functions may return a *projection* of an upstream record: a subset of
  its columns under their upstream names, typed, built with `UpstreamModel.project`.
  Nothing is renamed or computed; parsing a value is the only permitted override.
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
  only in the sense of the projection rule above (ADR-0003, amendment 2026-10-26). The
  endpoint wrappers' read models stay faithful and carry them. Fixtures never carry their
  values: the recording names them in `Scrub(secrets=...)` or rewrites them by key
  (`Scrub(rewrite=...)`).
- **No cross-source normalization.** A USDA `marketing_year` stays a USDA concept.
  Mapping between sources is business logic and lives outside this family.
- Reference data (commodity codes, country codes, report calendars) ships inside the
  package under `reference/` as CSV or JSON, loaded via `xippios.core.reference`, and is
  versioned with the package. A list fetched from one upstream operation is a packaged
  list, `reference/<name>.json` with `{"param", "endpoint", "fetched", "records"}` and an
  optional `"note"`, free-text provenance (what a derived list is derived from, how a
  list was reconciled with upstream's documentation), and no other key: upstream's
  records under upstream's field names (`UpstreamModel.dump_upstream`), a list of values
  as records of one field named by the upstream parameter, a table as records of its
  columns. `<name>` is the parameter, or a name of the list's own where two lists derive
  from one parameter. The refresh script writes it with `PackagedList.write`, `fetched`
  the UTC time of the fetch to the second; the package reads it with
  `PackagedList.load(package, name)` (ADR-0022, amendment 2026-10-27). Enums are
  generated from it with
  `xippios.core.reference` (`render_str_enums`, `render_int_enums`), and the whole
  generated module, docstrings included, is ASCII-only and passes `ruff check` and
  `ruff format --check` as rendered (ADR-0008).

## 4. Result envelope and metadata

Every task function returns `xippios.core.models.Result[T]`:

```python
class ResultMeta(BaseModel):
    source: str                       # "usda-nass"
    endpoint: str                     # upstream operation name, or a file kind (ADR-0020)
    retrieved_at: datetime            # UTC, when we fetched it
    published_at: datetime | None     # upstream publication/release time if known
    published_at_naive: bool = False  # True when upstream printed it without a zone
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
dropped (ADR-0012, amendment 2026-10-27). On a cache hit, `retrieved_at` is the time the
entry was stored, which the client puts on the response as
`extensions["xippios_cache_stored_at"]` (ADR-0015); a wrapper reads it with
`get_answer()`, whose `Answer` carries the payload and that `retrieved_at` (§6).

`published_at` carries a zone. A naive value, a time upstream printed without one (FAS:
`2026-10-06T08:00:00`), is accepted only with `published_at_naive=True` and is stored as
given, no zone attached; a naive value without the flag is refused, and so is the flag
with an aware value or with none. The flag says the time is upstream's text, not
comparable across sources; a consumer that knows the publisher's zone assigns it outside
the family (ADR-0003, ADR-0022). `vintage` keeps the release identifier as upstream
names it; where that identifier is the timestamp text, `vintage` holds the text and
`published_at` its parsed value with the flag.

A task that answers from packaged reference data (§3) fills `meta` by ADR-0022:
`retrieved_at` is the time the packaged list was fetched from upstream (the file's
`fetched` value, as a cache hit uses the entry's stored time); `endpoint` names the
upstream operation the list came from (operationId or path), never "reference" or a
file path; `vintage` is an upstream release identifier, or `None` when upstream has
none, since a fetch date is not a vintage; `total` is `None` unless upstream reports a
count (ADR-0012). `PackagedList` builds this meta, so no source writes it by hand:
`PackagedList.load(package, name)` reads the file (§3), `.meta(source, request=...,
vintage=...)` builds the meta and `.parse(Model, source=...)` the records. A `fetched`
that is a bare date, as refresh scripts wrote it before template v0.3.0, reads as 00:00
UTC of that day, the start of the day the old scripts truncated the time to, until the
source's next refresh writes the full time (ADR-0022, amendment 2026-10-27). A `list_*`
task's `search` keeps a record when the text occurs in one of its fields, ignoring case
(`xippios.core.matches`).

A frozen series, one upstream no longer updates (a discontinued report, a dataset
upstream stopped publishing), is marked where agents and readers look: its task's row in
the README status table carries a status that names the last release (`frozen, last
release 2024-09`), the task's docstring says so, and `vintage` holds that release's
identifier. `ResultMeta` has no field for it (ADR-0022, amendment 2026-10-27).

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
data is never passed off as data (ADR-0022, amendment 2026-10-27).

A task that reads a file (§2) sets `endpoint` to the file kind as upstream names it
(`wasde.xls`, `qs.crops`), `vintage` to the release identifier (an ESMIS release id, a
report date as printed), `published_at` to the catalog's release time, and `request` to
the file's URL or release id plus the filters applied in Python (ADR-0020).

`request` records what was sent: a parameter the caller left `None` is omitted
(ADR-0022, rule 3). `ResultMeta` drops a top-level `None` at construction, so a task
passes its parameters as they are; a `None` inside a nested mapping is kept as given. It
never carries credentials (ADR-0005). `ResultMeta` redacts the value of any key that
names one, at any depth, to `"REDACTED"` at construction, by the one rule of
`xippios.core.redaction` (a whole word `api_key`, `apikey`, `api-key`, `token`,
`secret`, `password`, `passwd`, `pwd`, `auth`, `authorization`, `sig`, `signature`,
`credential` or `credentials`, between `_`, `-` or the ends of the name), so an envelope
is safe to hand to an agent, return over HTTP, or write to a store; personal identifiers
in upstream data stay out of it by §3's rule for projections (ADR-0017). A bare `key` is
not on the list: it is a credential in a process where a `QueryKeyAuth` sends the key
under that name (USDA NASS), which registers it when built, and data elsewhere, as
Eurostat's SDMX series `key` is (ADR-0019, amendment 2026-10-27). A task that wants the
credential's provenance records the variable name, never the value.

`tenant` is the name of the tenant a multi-tenant source served the data for (§7),
never a credential, a host or another of the tenant's values; `None` for a
single-tenant source and for the list of tenants.

`total` is upstream's count of the records matching the request, or `None` when the
source reports none or the count is unknown (ADR-0012). A paginated task called without
its page parameter collects every page; called with one, it returns that page. For
offset paging, `limit` given means one page starting at `start` (default 0); `limit`
omitted means every page from `start` onward. Either way `total` is upstream's count for
the whole request, so the caller can page deliberately. It is provenance like the rest
of `meta`: set only from what upstream reports, never computed from `len(data)`. When
every page is collected, the count kept is the one upstream reported on the last page
fetched, and a mismatch with `len(data)` is upstream's and is not corrected; a task that
returns one page, or caps what it collects, can have `total > len(data)` by design.

## 5. Errors (`xippios.core.errors`)

```
XippiosError
├── ConfigError          missing key, bad settings
├── AuthError            401/403
├── RateLimitError       429, or a source's documented answer to a spent limit
│                        (ADR-0010); carries retry_after
├── NotFoundError        404 or empty where upstream signals absence
├── ValidationError      we could not parse what upstream returned (carries raw body)
├── UpstreamError        other 4xx/5xx (carries status, body)
├── TransportError       network, timeout
└── InvalidRequestError  the request as given cannot be served: a bad argument or a
    │                    documented refusal, detected before the call or by upstream's
    │                    own refusal of the query (ADR-0007)
    └── UnknownCode      a code the packaged list lacks, refused before the call
                         (ADR-0022)
```

Source packages subclass only when upstream has a distinct, documented failure mode;
a refusal the package makes itself, such as a query over a documented record limit or
an unknown filter name, subclasses `InvalidRequestError`. A code the packaged list lacks,
where upstream answers an unknown code with an empty result, is refused before the call
with core's `UnknownCode`, naming the list, its fetch date and the closest known codes
(`xippios.core.closest`, or a strategy of the source's own) (ADR-0022, amendment
2026-10-27). Upstream's own refusal of
the query as given is mapped to `InvalidRequestError`, or a subclass, in `classify` (§6):
usda-nass's HTTP 413 over the record limit, comtrade's HTTP 400, cashctrl's
`RequestRejected`. Agents and HTTP 422 treat both alike: the caller has to change the
request. Adapters convert these to structured text (MCP) or problem+json (HTTP;
`InvalidRequestError` is 422); they never leak tracebacks. An error message names the
request's method and path, never its host or query string: the host can name a tenant,
the query can carry a key (ADR-0005).

## 6. HTTP client (`xippios.core.client`)

- `httpx`, async core, sync facade (ADR-0002). Source packages expose sync functions;
  async variants are optional and suffixed `_async`.
- Retries with exponential backoff and jitter: a 429 for every method; a 5xx and a
  transport failure for idempotent methods only (GET, HEAD, OPTIONS), unless the source
  sets `RetryPolicy.retry_non_idempotent` because upstream makes a repeated write safe,
  or because the source only reads through POST (ADR-0011); never another 4xx.
- A source maps its documented error shapes once, in `ClientConfig.classify`, which
  sees every response before the default status mapping (ADR-0008); endpoint
  wrappers then use `get_json` and never inspect status codes themselves. A wrapper
  whose answer may come from the cache calls `get_answer()`: its `Answer(payload,
  retrieved_at)` carries a hit's stored time, from `xippios_cache_stored_at`, or else
  the arrival time, for `meta.retrieved_at` (ADR-0015, amendment 2026-10-27); one that
  needs more of the response calls `get()`, then `decode_json()`.
- A per-source rate limiter sets a fast pace within the source's documented per-second
  or per-minute limit or, where none is documented, a self-imposed pace that the
  package's CLAUDE.md names as such; longer-window quotas (hourly, daily) may be
  exhausted, not rationed (ADR-0010). `classify` interprets the upstream's 429, or its
  documented answer to a spent limit, as `RateLimitError` with `retry_after` (from
  `Retry-After`, the quota headers or a documented fallback), the client keeps a
  quota snapshot from the quota headers (`QuotaPolicy`, ADR-0015), and retries honour
  `retry_after` up to `backoff_max`. A request into a quota the snapshot shows spent
  waits it out inside the call, logged, when the wait is within the policy's
  `pause_cap` (30 s by default), and otherwise raises `RateLimitError` with
  `retry_after` without sending; a pause handed back to the caller is stated in the
  error text.
- Two hooks on `ClientConfig` see what passes through the client (ADR-0015):
  `before_request`, called once per call after the cache lookup and before the rate
  limiter, may wait or raise a taxonomy error, and then nothing is sent; `observe` sees
  every response from the wire, retried attempts and raw responses included and a cache
  hit never, before `classify`. `QuotaPolicy(...).install(config)` sets both to the
  policy's own, replacing any the config had, and is the family's implementation of the
  quota rules above (ADR-0010); a source whose answer to a spent limit is not a 429
  passes `spent=`, which reads that answer. No source subclasses `AsyncClient` for them.
  Before a 429 or 5xx is retried, the client asks `classify`: a `RateLimitError` sets the
  wait from its `retry_after`; an `UpstreamError` for a 5xx changes nothing; any other
  error ends the retries.
- Optional response cache (in-memory by default, pluggable) keyed on method+URL+params.
  A body larger than `ClientConfig.cache_max_bytes` (default 8 MiB) passes through and
  is not stored; `cache_filter` stays for finer rules. A source that wants a larger
  answer cached raises the bound and says why in its `CLAUDE.md` (ADR-0019).
- A file is downloaded, never held in memory (ADR-0019): `download(url, dest, *,
  auth=...) -> Downloaded` streams the body to `dest` under a temporary name, renames it
  when complete and removes it on failure, and never touches the response cache. The
  limiter, the hooks (`before_request`, `observe`), `classify` and the retry rule apply
  as they do to `get()`, and `auth` works as it does there; a retry restarts the file;
  except that `observe` and `classify` see a success's status and headers only, its
  body going to the file unread, and a 1xx or 3xx raises `UpstreamError`, since
  redirects are not followed (ADR-0019, amendment 2026-10-27). `Downloaded` carries `path`, `bytes`, `content_type`, the file name from
  `Content-Disposition` when sent, `etag`, `last_modified` and `retrieved_at`.
- `decode_text(response)` (charset from `Content-Type`, UTF-8 by default, a BOM
  stripped) and `decode_csv(data, *, delimiter=",", source=None)` (a path or a response;
  the stdlib's `csv.DictReader`, headers as upstream prints them) sit beside
  `decode_json`. The source opens gzip and
  zip with the stdlib; core ships no XML, spreadsheet or PDF parser (ADR-0019,
  ADR-0020).
- Credentials come from the client's `auth`. A call to a keyless endpoint on the same
  host passes `auth=None` and is sent without them; another `httpx.Auth` replaces them
  for one call; no second client is needed to leave the key off (ADR-0015). `auth=None`
  and the client's own share the cache; a call with an `httpx.Auth` of its own bypasses
  it, neither looked up nor stored.
- One `User-Agent`: `xippios-<source>/<version> (+https://github.com/xippios)`.
- Timeouts explicit; defaults 10 s connect, 60 s read.
- A request body is JSON (`json=`) or form-encoded (`data=`, for an upstream whose
  writes take form fields), as upstream documents it; never both.

## 7. Configuration

The environment is read through the `EnvKeyAuth` helpers (`QueryKeyAuth`,
`HeaderKeyAuth`, `BearerAuth`, `BasicKeyAuth`), on the first request: keys from
`<SOURCE>_API_KEY`, or the issuer's variable where ADR-0009 applies, overridable by
constructor argument (`key=`; ADR-0002, amendment 2026-10-27). No config files, no dotenv
loading inside the package — the environment is the contract (direnv in development,
secrets in CI). A source behind api.data.gov takes its key, its gateway answers and its
quota from `xippios.core.data_gov`: `Gateway(SOURCE)` gives the `auth` on
`DATA_GOV_API_KEY`, the `classify` its own `classify` asks first, and `install`, which puts
the one `QuotaPolicy` per process for that key on its config (ADR-0009, amendment
2026-10-27).

A multi-tenant source, whose upstream serves each tenant from a host or under a key of
its own (CashCtrl's organisations), declares its tenants with `xippios.core.Tenants`
(ADR-0014). One variable lists the tenant names, comma-separated, lower-case letters,
digits and underscores (`CASHCTRL_ORGS=acme,acme_test`); each tenant's values sit in
`<SOURCE>_<NAME>_<FIELD>`, source and name upper-cased and `-` made `_`
(`CASHCTRL_ACME_SUBDOMAIN`, `CASHCTRL_ACME_API_KEY`). The reserved test tenant (`demo`)
is declared by its own variables alone and never listed: it exists when all of them
are set. Every tenant has one client of its own, with its own rate limiter and no cache
shared with another tenant, built on first use and rebuilt when one of its values
changes. A name that is not declared is the caller's mistake, `InvalidRequestError`; a
missing or malformed variable of a declared tenant is the operator's, `ConfigError`.
Messages and results name tenants and variables, never a value.

## 8. MCP conventions

- Register task functions, not endpoint wrappers. Tool name `<source>_<verb>_<noun>`.
- The function docstring is the tool description: first line one sentence, then an
  `Args:` block explaining every parameter with examples of valid values. Agents read
  this; write it for them.
- Read-only by default. A tool that writes to the upstream (CashCtrl) lives in a
  separate server entry point (`xippios-<source>-mcp-write`), takes `confirm: bool`
  and returns a dry-run preview when `confirm=False`. `register_tasks(read_only=False)`
  enforces it: a task without `confirm: bool = False` is refused before anything is
  registered (ADR-0014). A write server carries no authentication, so `--http` serves
  it on a loopback host only (`127.0.0.1`, `localhost`, `::1`) unless `--allow-remote`
  is passed, with a gateway in front. A write server exposes write tools only;
  reference tools, the tenant list among them, stay on the read server.
- Result cap: default 200 rows or 64 KB, whichever first, bytes counted in the UTF-8
  encoding of the compact JSON text. Over the cap, return the first page plus a note on
  how to narrow the query. Never truncate silently. A reference tool whose whole list an
  agent needs gets a cap of its own, keyed by the task function's name, with the rows
  and bytes the source judges it needs (`register_tasks(..., caps={"list_partners":
  ResultCap(max_rows=400, max_bytes=100_000)})`); a byte bound above the default is a
  deliberate choice for that tool, and every other tool keeps the default (ADR-0016).
  The note never promises a filter the tool lacks: the default says "narrow the query to
  see the rest", and a tool with filters names them in its cap's `note`. Since that note
  names a task's filters, a source keeps its caps with its tasks, as `MCP_CAPS:
  Mapping[str, ResultCap]` in `tasks.py` next to `__all__`, and its `mcp.py` passes them
  through as `caps=getattr(tasks, "MCP_CAPS", None)`.
- A task named in `BULK_TASKS` (a frozenset in `tasks.py` beside `MCP_CAPS`) is not a
  tool: `register_tasks` skips it (ADR-0019). No tool returns a file path to an agent.
  The MCP surface of a bulk source is its catalog tasks (which files exist, with sizes
  and release identifiers) and, where the slice fits the result cap, a filtered read of
  the file.
- Reference lookups are tools too: `<source>_list_<thing>` (commodities, countries,
  attributes). Agents need them to form valid calls. A multi-tenant source lists its
  tenants the same way, names only (`list_task`, `cashctrl_list_organisations`).
- A multi-tenant source's servers take an option that locks them to one tenant
  (`--org acme`), passed to `build_server` as `TenantLock` (ADR-0014): a tool call
  naming another tenant is refused with `error: InvalidRequestError: ...` before the
  tool runs, the instructions name the tenant, and the list tool lists it alone. A tool
  that takes the tenant parameter must receive it on a locked server; a default is
  refused.
- Errors return as text starting with `error: <ErrorClass>: <message>`; never raise
  through the MCP boundary.
- Entry point `xippios-<source>-mcp` runs stdio by default; `--http` for streamable HTTP.
  A source's own options reach core's `main` through `add_options` and `apply_options`,
  parsed once with core's; an error applying them stops the process with exit status 2.

## 9. HTTP adapter conventions

FastAPI router generated from task functions via `xippios.core.http.router_from_tasks`;
one tag per source; responses are the `Result[T]` envelope; errors as RFC 9457
problem details. A task whose parameters are all scalars is a `GET` with query
parameters; a task with any non-scalar parameter (a mapping, a list, a model) is a
`POST` whose JSON body is an object keyed by parameter name (ADR-0007). Mounted by the
consumer, never served standalone from the package. A task named in `BULK_TASKS` gets no
route: `router_from_tasks` skips it, and no route returns a file path (ADR-0019).

## 10. Testing

- Unit tests run offline against recorded fixtures (`respx`); fixtures live in
  `tests/fixtures/<endpoint>/<case>.json` and are recorded by the `record-fixture`
  command, never hand-written.
- A fixture file a PR adds or changes stays under 256 KiB (ADR-0019); a fixture over the
  cap recorded before the rule bound stays until a PR re-records it. A download fixture
  holds a small real answer (a short date range, one commodity) or the first N rows or
  bytes of the file: the recorder truncates on request (`max_bytes=`), marks the fixture
  `truncated: true` and keeps `original_bytes` and the sha256 of the full file. An XML,
  ZIP, gzip, XLS or XLSX fixture is a small real sample (a short query, one member of
  the archive, a few rows), never a byte-truncated file, since a cut-off binary or
  compressed file cannot be parsed and a cut-off XML document is not well-formed; byte
  truncation (`max_bytes=`) applies to text bodies, and the recorder refuses it for those
  formats and for a body that is not UTF-8 text; a JSON array is truncated by elements:
  the recorder cuts its original text after the first N elements that fit, never
  re-serialising them, marks `truncated: true` and records the full count
  (`original_count`) and the sha256; a JSON object is refused, and the source records a
  small real answer (ADR-0019, amendment 2026-10-27). `max_bytes` bounds the body, not
  the fixture file, which escapes the body as a JSON string.
  A test on a sample or a truncated fixture asserts the parser's shape, never a size.
- A file-distributed source keeps a sample of each file kind under
  `tests/fixtures/files/<file_kind>/<case>.*` with a provenance line: the release id, the
  URL, the sha256 and bytes of the full file, and the fetched time in UTC with `Z`
  (ADR-0020). A binary file carries no comment, so the lines are one row per file in
  `tests/fixtures/files/README.md`. Its parser tests read the sample; the download call
  replays the recorded exchange of the bullet above. One live test per file kind fetches
  the current release and checks that the parser still reads it: shape, headers and
  sheet names, never values.
- Replay matches a fixture on method, host and path, and on the recorded query
  parameters a test names (`match_params`); a parameter whose recorded value holds
  `REDACTED` cannot be matched and is refused by name. A parameter's absence cannot be
  matched: where two fixtures share a path, the more specific one is mounted first,
  since `respx` tries routes in the order they were added.
- The recorder scrubs in memory and writes once, so nothing unscrubbed touches disk: a
  multi-tenant source records with a placeholder host that its offline tests replay
  against, and names the values that must never be written (`xippios.core.testing.Scrub`).
  A placeholder that contains the original host (`demo.example.test` for
  `example.test`) is allowed and written as such, never scrubbed again; one that is the
  original host is refused. The scrubbed exchange is verified before the write, a JSON
  body also decoded; the original host or a named value still present refuses it, the
  error naming where.
  The verify is best effort, one JSON-aware pass over URL, headers and bodies; the
  backstops are recording only against synthetic or demo tenants and the fixture grep
  of the definition of done.
  A body that is not UTF-8 text cannot be scrubbed and is refused unless the recording
  flags it (`allow_binary=True`, stored base64 with `body_base64`).
  The scrub redacts credentials by the rule `ResultMeta` applies (§4): a parameter named
  `key` is data unless a `QueryKeyAuth` sends the key under that name (ADR-0019).
- Live tests are marked `@pytest.mark.live`, skipped unless `XIPPIOS_LIVE_TESTS=1`,
  and run in CI only in the one live workflow, `.github/workflows/live.yml`, in the shape
  the template renders (a source whose secrets differ keeps that shape): one job,
  `contents: read`, on a nightly schedule and on `workflow_dispatch`, never on a pull
  request. The key reaches only that job's `uv run pytest -m live` step, from the org
  secret; checkout, setup-uv and `uv sync` never see it. Sources that share a key stagger
  their nightly start, so that they do not draw on the shared quota together; the
  template derives the time from the slug (ADR-0009, amendment 2026-10-26).
- The pytest plugin (`pytest_plugins = ["xippios.core.testing.plugin"]`) keeps the
  default run offline and free of real keys (ADR-0013):
  - No network, from `pytest_configure` on: while test modules are collected, in a
    fixture of any scope and in a test, a request through httpx's default transports
    raises `RuntimeError` naming its method and path. `respx` answers replayed and
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
    that asserts the pause or the refusal is marked `rate_limited` (ADR-0015); the
    edges, snapshots shared by consecutive live tests, a quota spent by a fixture of
    wider scope, a subclass's override of `before_request`, are listed in ADR-0013 and
    ADR-0015.
  - Placeholder key, in every test not marked `live`: every `EnvKeyAuth` sends
    `PLACEHOLDER_KEY`, pinned on the class, and the variables named in the ini option
    `xippios_placeholder_key_envs` hold it; the fixture `placeholder_api_key` returns
    it, `None` in a live test. A source names its key variable there and carries no
    placeholder fixture of its own.
  - Logger levels: the `httpx` and `httpcore` logger levels are restored after every
    test, live ones included. They are saved per test, after fixtures of wider scope
    are set up, so one of those that changes a level leaves it behind.
- The family conformance check, `xippios.core.testing.family`, tests once, in core, what
  every source shares: the empty namespace levels, `py.typed` and `__version__`; the
  tasks `mcp.py` and `http.py` serve (`tasks.__all__` minus `BULK_TASKS`) and those the
  write server serves (`tasks_write.__all__`); every task synchronous, returning
  `Result[T]`, with an agent docstring; the README status table listing exactly the
  tasks; the template tag in `.copier-answers.yml`; the core bound of §12. The template
  renders `tests/test_family.py`, which collects it with one line
  (`from xippios.core.testing.family import *  # noqa: F403`), so it runs in every
  source's CI, and a source keeps no copy of its checks. The plugin's ini option
  `xippios_package` names the package under test where `src/xippios/` holds more than
  one `tasks.py` (ADR-0013, amendment 2026-10-26).
- Every task function has at least one fixture-backed test and one live smoke test.
- Coverage is reported, not gated; mypy strict and ruff are gated.

## 11. Tooling

`uv` for everything (lock, sync, build, publish). Python ≥ 3.12. `ruff` (lint +
format, line length 100), `mypy --strict`, `pre-commit` with those two plus
`detect-secrets`. Dependencies pinned by `uv.lock`; runtime deps declared with
lower bounds only, except `xippios-core` and a source package the source depends on,
which §12 bounds to one minor.

## 12. Versioning and releases

- SemVer. Pre-1.0: breaking changes bump minor. Post-1.0: breaking changes bump major.
- An upstream API change that changes our public surface is a breaking change.
- A source depends on one core minor with an upper bound, `xippios-core~=0.2.0`, and its
  extras likewise (`xippios-core[mcp]~=0.2.0`); the template renders it as `~=X.Y.0`,
  or `~=X.Y.Z` when patch Z shipped what the source adopts, still one minor
  (ADR-0018, amendment 2026-10-26). Core patch releases stay compatible. While core is
  0.x it keeps no backward compatibility across minors: a new core minor may break, and
  a source adopts it through §15 before its next release. From 1.0 a breaking change
  bumps the major (SemVer), and the `~=` bound stays. A source already published with an
  open bound stays as published and gets the bound with its next release.
- `CHANGELOG.md` in Keep a Changelog format; every PR adds an entry under Unreleased.
- The release train (ADR-0018, amendment 2026-10-26): the reference-data refresh, where
  a source has one, is its own PR before the release PR, and a release PR changes only
  `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `CLAUDE.md` and
  `docs/handover.md` (and `scripts/check-siblings.sh` until the siblings check is
  template-owned). Release = the release PR merges on `main` → `publish.yml` tags
  `vX.Y.Z` from `pyproject.toml` on the merge commit → environment `pypi` → a human
  approves → the trusted publisher uploads. A tag ruleset admits no other `v*` tag.
  sdk-template, which publishes nothing to PyPI, tags from the top `## [X.Y.Z] - `
  heading of its `CHANGELOG.md` with its own `release.yml`, under the same ruleset.
  Until a repository's workflow tags itself (core 0.2.1 and template v0.2.1 ship it),
  its tag is pushed by Johannes from his own account. Yanks are a human action. No
  tokens anywhere.
- A source may depend on another source package, consuming its task layer only: it
  imports `xippios.<dep>.tasks` and its models, never `api/` or `_client`, and declares
  `xippios-<dep>~=X.Y.0`, one minor, like core (ADR-0021). Both share one core minor:
  the dependent adopts a core minor only after the dependency has released on it, and a
  new minor of the dependency reaches it through an adoption PR (§15). The dependency
  tags first; the dependent's release PR pins the published version. The dependent's
  servers register its own tasks only; no cycles, one level only.

## 13. Repository hygiene

- Branches: trunk-based. `main` protected by the org ruleset; feature branches
  `feature/`, `fix/`, `chore/`, `docs/`. Conventional Commits.
- Required files: `README.md`, `CHANGELOG.md`, `LICENSE` (Apache-2.0), `CLAUDE.md`,
  `docs/upstream/FETCHED.md`, `pyproject.toml`, `uv.lock`. `sdk-core` wraps no upstream
  and is exempt from `docs/upstream/` (ADR-0005).
- README structure: what it wraps · install (`uv add xippios-<source>[mcp]`) ·
  30-second example · MCP client config snippet · status table of covered endpoints ·
  upstream terms and attribution · licence.
- Topics on GitHub: `xippios-sdk`, `python`, `mcp`, plus the domain (`agriculture`,
  `trade-data`, `accounting`) as appropriate.

## 14. What this family is not

Not a place for normalization across sources, scheduling, storage, or any product
logic. Those live in product repositories that depend on these packages.

## 15. Adopting a core or template release

A source adopts a new core minor, and the sdk-template release that goes with it, in one
adoption PR before its next release (§12, ADR-0018). The PR description is this
checklist, ticked; an unticked item needs a one-line reason, an item the release does
not touch included. A template-only update, with no new core minor, is judged against
the items it touches. sdk-template's `/adopt-release` command walks the list step by
step. An adoption PR is a `chore/template-update*` PR: when its merge class is `auto` the
session enables auto-merge after the reviewer's `ready`, and GitHub merges it once `ci` is
green and review threads are resolved; a `human` adoption (a source-owned workflow, a
changed template answer, a protected path, a build or install route) waits for Johannes
(ADR-0018, amendment (e); the merge classes are in the README of the organisation's
`.github` repository).

1. The core floor is raised: `xippios-core` and each of its extras name the new minor
   with the bound of §12 (`xippios-core~=0.2.0`), and, where the source depends on
   another source package, that package's minor likewise (ADR-0021); resolved from PyPI
   with no git pin left in `[tool.uv.sources]`, and `uv.lock` is updated.
2. `copier update` brings the repository to the template release, its conflicts
   resolved.
3. Every local workaround that a core change replaced is deleted, its tests with it, and
   the PR description names the core change for each (`QuotaAwareClient` → `QuotaPolicy`,
   ADR-0015); the release's ADRs and CHANGELOG list them per source.
4. Logic duplicated across sources is moved into core or dropped: what core now provides
   is dropped here; what it does not provide yet is carried by the source, named in the
   PR description and in a queue row; a second source may carry the same helper when
   the row names both; a third never: core takes it in that minor (ADR-0023). A core row
   names its consumers (ADR-0023).
5. Every test that asserted a limiter wait, a quota pause or key resolution is marked or
   overridden: a limiter wait or a quota pause marked `rate_limited` (ADR-0013,
   ADR-0015), key resolution given a module-level `placeholder_api_key` override that
   pins nothing (ADR-0013).
6. Generated enum files are re-rendered once with the release's renderers and committed
   as rendered.
7. `mypy --strict` covers `scripts/` too (`files = ["src", "tests", "scripts"]`).
8. The current conventions version is applied: every rule changed since the version the
   source last applied holds in the source.
9. `CHANGELOG.md` has a line under Unreleased naming the core, template and conventions
   versions adopted.

An adoption PR changes nothing else: no new endpoints, tasks or fixtures ride along. It
may delete the fixtures, mounts and tests that the adoption itself makes dead, and
nothing more (ADR-0018, amendment 2026-10-26). An adoption PR, which fetches nothing,
leaves `docs/upstream/FETCHED.md` to the next `/refresh-upstream` and ports only the
capture script's changes (ADR-0003, amendment 2026-10-26). The reviewer judges it
against this list and nothing else (definition of done, block "Adoption PR").
