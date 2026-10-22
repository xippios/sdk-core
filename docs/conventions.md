# xippios SDK family — conventions

Version 1.0 · 2026-10-20 · applies to every `sdk-*` repository under github.com/xippios.
Changes to this file require an ADR in `docs/adr/` and a PR against `sdk-core`.

## 1. Naming

| Thing | Pattern | Example |
| --- | --- | --- |
| GitHub repo | `sdk-<source>` | `sdk-usda-nass` |
| PyPI distribution | `xippios-<source>` | `xippios-usda-nass` |
| Import path | `xippios.<source>` (underscores) | `xippios.usda_nass` |
| MCP entry point | `xippios-<source>-mcp` | `xippios-usda-nass-mcp` |
| MCP tool | `<source>_<verb>_<noun>` | `usda_nass_get_series` |
| Env var for a key | `<SOURCE>_API_KEY` | `NASS_API_KEY` |

`<source>` names the data provider and, where one provider has several APIs, the API:
`usda-nass`, `usda-fas`, `usda-esmis`, `comtrade`, `eurostat`, `faostat`, `cashctrl`.
No domain prefixes (`ag`, `agri`): sources are domain-neutral; grouping happens via
GitHub topics (`xippios-sdk`) and the org README.

`src/xippios/` is a PEP 420 namespace package: **no** `src/xippios/__init__.py` in any repo.

## 2. Layering (ADR-0001)

Every source package has three layers, top to bottom, and nothing skips a layer:

1. **Endpoint wrappers** — `xippios/<source>/api/*.py`. One function per upstream
   endpoint, named after the upstream operation, parameters as upstream names them
   (snake_cased), returning typed models that mirror the upstream payload.
2. **Task-shaped functions** — `xippios/<source>/tasks.py`. The functions a person
   or an agent actually wants: `get_balance_sheet(commodity, marketing_year)`. They
   compose endpoint wrappers, handle pagination and reference lookups, and return
   `Result[T]`. This is the public API and the only layer adapters may call.
3. **Adapters** — `xippios/<source>/mcp.py` and `xippios/<source>/http.py`.
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
  resolved, errors typed. Field names are upstream names in snake_case.
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

class Result(BaseModel, Generic[T]):
    data: T
    meta: ResultMeta
```

`meta` is never optional. It is what makes a later as-of/vintage store possible.

## 5. Errors (`xippios.core.errors`)

```
XippiosError
├── ConfigError          missing key, bad settings
├── AuthError            401/403
├── RateLimitError       429, carries retry_after
├── NotFoundError        404 or empty where upstream signals absence
├── ValidationError      we could not parse what upstream returned (carries raw body)
├── UpstreamError        other 4xx/5xx (carries status, body)
└── TransportError       network, timeout
```

Source packages subclass only when upstream has a distinct, documented failure mode.
Adapters convert these to structured text (MCP) or problem+json (HTTP); they never
leak tracebacks.

## 6. HTTP client (`xippios.core.client`)

- `httpx`, async core, sync facade (ADR-0002). Source packages expose sync functions;
  async variants are optional and suffixed `_async`.
- Retries with exponential backoff and jitter on 429 and 5xx; never on 4xx otherwise.
- A per-source rate limiter configured from the source's documented limits.
- Optional response cache (in-memory by default, pluggable) keyed on method+URL+params.
- One `User-Agent`: `xippios-<source>/<version> (+https://github.com/xippios)`.
- Timeouts explicit; defaults 10 s connect, 60 s read.

## 7. Configuration

`pydantic-settings`; keys read from `<SOURCE>_API_KEY`, overridable by constructor
argument. No config files, no dotenv loading inside the package — the environment is
the contract (direnv in development, secrets in CI).

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
problem details. Mounted by the consumer, never served standalone from the package.

## 10. Testing

- Unit tests run offline against recorded fixtures (`respx`); fixtures live in
  `tests/fixtures/<endpoint>/<case>.json` and are recorded by the `record-fixture`
  command, never hand-written.
- Live tests are marked `@pytest.mark.live`, skipped unless `XIPPIOS_LIVE_TESTS=1`,
  and run in CI only on a nightly schedule with org secrets.
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
  `docs/upstream/FETCHED.md`, `pyproject.toml`, `uv.lock`.
- README structure: what it wraps · install (`uv add xippios-<source>[mcp]`) ·
  30-second example · MCP client config snippet · status table of covered endpoints ·
  upstream terms and attribution · licence.
- Topics on GitHub: `xippios-sdk`, `python`, `mcp`, plus the domain (`agriculture`,
  `trade-data`, `accounting`) as appropriate.

## 14. What this family is not

Not a place for normalization across sources, scheduling, storage, or any product
logic. Those live in product repositories that depend on these packages.
