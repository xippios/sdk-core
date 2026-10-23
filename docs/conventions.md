# xippios SDK family — conventions

Version 1.8 · 2026-10-23 · applies to every `sdk-*` repository under github.com/xippios.
Changes to this file require an ADR in `docs/adr/` and a PR against `sdk-core`.

## 1. Naming

| Thing | Pattern | Example |
| --- | --- | --- |
| GitHub repo | `sdk-<source>` | `sdk-usda-nass` |
| PyPI distribution | `xippios-<source>` | `xippios-usda-nass` |
| Import path | `xippios.<source>`; a provider with several APIs nests: `xippios.<provider>.<api>` | `xippios.comtrade`, `xippios.usda.nass` |
| MCP entry point | `xippios-<source>-mcp` | `xippios-usda-nass-mcp` |
| MCP tool | `<source>_<verb>_<noun>` | `usda_nass_get_series` |
| Env var for a key | `<SOURCE>_API_KEY`, or the issuer's variable when one key serves several sources (ADR-0009) | `COMTRADE_API_KEY`, `DATA_GOV_API_KEY` |

`<source>` names the data provider and, where one provider has several APIs, the API:
`usda-nass`, `usda-psd`, `usda-esr`, `usda-gats`, `usda-esmis`, `comtrade`, `eurostat`,
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

## 3. Upstream fidelity (ADR-0003)

- Names and semantics come from the upstream documentation, which is snapshotted in
  `docs/upstream/` with a `FETCHED.md` recording date and URL. The snapshot is the
  reference for the agent; refresh it deliberately, by PR, and diff it.
- Within-source hygiene is required: dates → `datetime.date`/`datetime`, numbers →
  `int`/`Decimal`/`float` as appropriate, upstream enums → `StrEnum`, pagination
  resolved, errors typed. Field names are upstream names in snake_case. A `Decimal`
  field of an `UpstreamModel` serialises as a JSON number in every adapter
  (ADR-0008); Python keeps the `Decimal`.
- Task-shaped functions may return a *projection* of an upstream record: a subset of
  its columns under their upstream names, typed, built with `UpstreamModel.project`.
  Nothing is renamed or computed; parsing a value is the only permitted override.
- **No cross-source normalization.** A USDA `marketing_year` stays a USDA concept.
  Mapping between sources is business logic and lives outside this family.
- Reference data (commodity codes, country codes, report calendars) ships inside the
  package under `reference/` as CSV or JSON, loaded via `xippios.core.reference`, and
  is versioned with the package.

## 4. Result envelope and metadata

Every task function returns `xippios.core.models.Result[T]`:

```python
class ResultMeta(BaseModel):
    source: str                   # "usda-nass"
    endpoint: str                 # upstream operation name
    retrieved_at: datetime        # UTC, when we fetched it
    published_at: datetime | None # upstream publication/release time if known
    vintage: str | None           # upstream release identifier if the source has one
    request: dict[str, Any]       # the parameters used, for reproducibility
    total: int | None             # upstream's record count, if it reports one

class Result(BaseModel, Generic[T]):
    data: T
    meta: ResultMeta
```

`meta` is never optional. It is what makes a later as-of/vintage store possible.

`request` never carries credentials (ADR-0005). `ResultMeta` redacts the value of any
key that looks like one (`key`, `api_key`, `token`, `secret`, `password`, `auth`,
`signature`, `credential`) to `"REDACTED"` at construction, so an envelope is safe to
hand to an agent, return over HTTP, or write to a store. A task that wants the
credential's provenance records the variable name, never the value.

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
└── InvalidRequestError  the request cannot be sent as given: a bad argument, or a query
                         the source documents it will refuse (ADR-0007); raised before
                         any upstream call
```

Source packages subclass only when upstream has a distinct, documented failure mode;
a refusal the package makes itself, such as a query over a documented record limit or
an unknown filter name, subclasses `InvalidRequestError`. Adapters convert these to
structured text (MCP) or problem+json (HTTP; `InvalidRequestError` is 422); they never
leak tracebacks. An error message names the request's method and path, never its host
or query string: the host can name a tenant, the query can carry a key (ADR-0005).

## 6. HTTP client (`xippios.core.client`)

- `httpx`, async core, sync facade (ADR-0002). Source packages expose sync functions;
  async variants are optional and suffixed `_async`.
- Retries with exponential backoff and jitter: a 429 for every method; a 5xx and a
  transport failure for idempotent methods only (GET, HEAD, OPTIONS), unless the source
  sets `RetryPolicy.retry_non_idempotent` because upstream makes a repeated write safe,
  or because the source only reads through POST (ADR-0011); never another 4xx.
- A source maps its documented error shapes once, in `ClientConfig.classify`, which
  sees every response before the default status mapping (ADR-0008); endpoint
  wrappers then use `get_json` and never inspect status codes themselves.
- A per-source rate limiter sets a fast pace within the source's documented per-second
  or per-minute limit or, where none is documented, a self-imposed pace that the
  package's CLAUDE.md names as such; longer-window quotas (hourly, daily) may be
  exhausted, not rationed (ADR-0010). `classify` interprets the upstream's 429, or its
  documented answer to a spent limit, as `RateLimitError` with `retry_after` (from
  `Retry-After`, the quota headers or a documented fallback), the client keeps a
  per-source quota snapshot from the quota headers, and retries honour `retry_after`
  up to `backoff_max` (core today: the `Retry-After` header on a 429; follow-up in
  ADR-0010). A request into a quota the snapshot shows spent waits it out inside the
  call, logged, when the wait is within `backoff_max`, and otherwise raises
  `RateLimitError` with `retry_after` without sending; a pause handed back to the
  caller is stated in the error text.
- Optional response cache (in-memory by default, pluggable) keyed on method+URL+params.
- One `User-Agent`: `xippios-<source>/<version> (+https://github.com/xippios)`.
- Timeouts explicit; defaults 10 s connect, 60 s read.
- A request body is JSON (`json=`) or form-encoded (`data=`, for an upstream whose
  writes take form fields), as upstream documents it; never both.

## 7. Configuration

`pydantic-settings`; keys read from `<SOURCE>_API_KEY`, or the issuer's variable where
ADR-0009 applies, overridable by constructor argument. No config files, no dotenv
loading inside the package — the environment is the contract (direnv in development,
secrets in CI).

## 8. MCP conventions

- Register task functions, not endpoint wrappers. Tool name `<source>_<verb>_<noun>`.
- The function docstring is the tool description: first line one sentence, then an
  `Args:` block explaining every parameter with examples of valid values. Agents read
  this; write it for them.
- Read-only by default. A tool that writes to the upstream (CashCtrl) lives in a
  separate server entry point (`xippios-<source>-mcp-write`), takes `confirm: bool`
  and returns a dry-run preview when `confirm=False`.
- Result cap: default 200 rows or 64 KB, whichever first. Over the cap, return the
  first page plus a note on how to narrow the query. Never truncate silently.
- Reference lookups are tools too: `<source>_list_<thing>` (commodities, countries,
  attributes). Agents need them to form valid calls.
- Errors return as text starting with `error: <ErrorClass>: <message>`; never raise
  through the MCP boundary.
- Entry point `xippios-<source>-mcp` runs stdio by default; `--http` for streamable HTTP.

## 9. HTTP adapter conventions

FastAPI router generated from task functions via `xippios.core.http.router_from_tasks`;
one tag per source; responses are the `Result[T]` envelope; errors as RFC 9457
problem details. A task whose parameters are all scalars is a `GET` with query
parameters; a task with any non-scalar parameter (a mapping, a list, a model) is a
`POST` whose JSON body is an object keyed by parameter name (ADR-0007). Mounted by the
consumer, never served standalone from the package.

## 10. Testing

- Unit tests run offline against recorded fixtures (`respx`); fixtures live in
  `tests/fixtures/<endpoint>/<case>.json` and are recorded by the `record-fixture`
  command, never hand-written.
- Replay matches a fixture on method, host and path, and on the recorded query
  parameters a test names (`match_params`). A parameter's absence cannot be matched:
  where two fixtures share a path, the more specific one is mounted first, since `respx`
  tries routes in the order they were added.
- The recorder scrubs in memory and writes once, so nothing unscrubbed touches disk: a
  multi-tenant source records with a placeholder host that its offline tests replay
  against, and names the values that must never be written (`xippios.core.testing.Scrub`).
  The scrubbed exchange is verified before the write, a JSON body also decoded; the
  original host or a named value still present refuses it, the error naming where.
  A body that is not UTF-8 text cannot be scrubbed and is refused unless the recording
  flags it (`allow_binary=True`, stored base64 with `body_base64`).
- Live tests are marked `@pytest.mark.live`, skipped unless `XIPPIOS_LIVE_TESTS=1`,
  and run in CI only on a nightly schedule with org secrets.
- The pytest plugin (`pytest_plugins = ["xippios.core.testing.plugin"]`) guarantees
  every test not marked `live` an offline run without real keys (ADR-0013):
  - No network: a request through httpx's default transports raises `RuntimeError`
    naming its method and path; `respx` answers replayed and mocked requests as
    before, and a transport the test passes itself is untouched. A test that must
    reach the network is marked `network`.
  - No rate-limit wait: a client's limiter neither waits nor takes a token. A test
    that asserts the limiter's waits is marked `rate_limited`.
  - Placeholder key: every `EnvKeyAuth` sends `PLACEHOLDER_KEY`, pinned on the class,
    and the variables named in the ini option `xippios_placeholder_key_envs` hold it;
    the fixture `placeholder_api_key` returns it, `None` in a live test. A source names
    its key variable there and carries no placeholder fixture of its own.
  - Logger levels: the `httpx` and `httpcore` logger levels are restored after every
    test, live ones included.
- Every task function has at least one fixture-backed test and one live smoke test.
- Coverage is reported, not gated; mypy strict and ruff are gated.

## 11. Tooling

`uv` for everything (lock, sync, build, publish). Python ≥ 3.12. `ruff` (lint +
format, line length 100), `mypy --strict`, `pre-commit` with those two plus
`detect-secrets`. Dependencies pinned by `uv.lock`; runtime deps declared with
lower bounds only.

## 12. Versioning and releases

- SemVer. Pre-1.0: breaking changes bump minor. Post-1.0: breaking changes bump major.
- An upstream API change that changes our public surface is a breaking change.
- `CHANGELOG.md` in Keep a Changelog format; every PR adds an entry under Unreleased.
- Release = human tags `vX.Y.Z` on `main` → `publish.yml` → environment `pypi` →
  human approves → trusted publisher uploads. No tokens anywhere.

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
