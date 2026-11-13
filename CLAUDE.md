# sdk-core — instructions for Claude Code

`xippios-core` is the shared foundation of the xippios Python SDK family: HTTP client,
error taxonomy, base models with release metadata, reference-data loading, and the
helpers that turn SDK functions into MCP tools and FastAPI routes. Every
`xippios-<source>` package depends on it. Nothing in this repo knows about any
particular upstream API.

## Documents

The README's [`## Documents`](README.md#documents) lists the documents this repository
follows. Read them before you change a file.

## Layout

```
src/xippios/core/
  __init__.py        public surface, re-exports only; adapters are NOT re-exported
  py.typed           PEP 561 marker; without it mypy --strict fails in every source repo
  _version.py        __version__ from distribution metadata
  _loop.py           one background event loop; sync() derives sync functions from async
  _tasks.py          is_bulk_task: what the adapters read from a source's tasks.py (BULK_TASKS)
  errors.py          error taxonomy (UnknownCode: a code a packaged list lacks), response/exception
                     classifiers
  redaction.py       the one credential rule (REDACTED, the names QueryKeyAuth registers),
                     scrub_params/url/headers; imports nothing of core's
  models.py          UpstreamModel (dump_upstream), ResultMeta (unknown fields refused,
                     published_at_naive, request without None and redacted by redaction),
                     Result[T], ResultCap, parse(); re-exports REDACTED
  pagination.py      paginate_offset (page numbers map onto offsets), collect()
  reference.py       loader for packaged reference data (CSV, JSON); PackagedList (load, meta, parse,
                     write), matches, closest; render_enums (StrEnum and IntEnum in one module)
  data_gov.py        the api.data.gov gateway: Gateway (key, classify, one QuotaPolicy per process)
  client/            httpx client: config, retry, ratelimit, cache, quota, auth (env-key helpers),
                     download (Downloaded, streaming), _core (AsyncClient with download and
                     get_answer, Answer, decode_json/decode_text/decode_csv)
  mcp/               MCP server helpers: server, results (caps), errors (to text), cli   [extra: mcp]
  http/              FastAPI helpers: router (from tasks), problems (RFC 9457)          [extra: http]
  testing/           pytest plugin (live gate, offline guarantees, anyio_backend), fixtures (max_bytes
                     truncation), record, replay, scrub (Scrub: named secrets, plain verify;
                     credentials by redaction), adapters (mcp_call), clock (slack for wall-clock
                     reads), family (the conformance check)                              [extra: testing]
tests/               mirrors the tree: tests/client/, tests/mcp/, tests/http/, tests/testing/
scripts/
  adr_index.py       writes docs/adr.md and docs/adr.json from the records; --check writes nothing
changelog/           one fragment per change, assembled into CHANGELOG.md by the release (README.md)
docs/
  conventions.md  definition-of-done.md  review-checklist.md  handover.md  roadmap.md
  adr/  adr.md  adr.json  reports/
.github/workflows/
  ci.yml             job name MUST be `ci` (the org ruleset requires that check); pull requests, and
                     called by publish.yml; no push trigger of its own
  publish.yml        every push to main: tags vX.Y.Z from pyproject.toml when a release PR merged,
                     builds, waits in environment `pypi` for a maintainer's approval
  gates.yml          the organization's checks of a pull request from xippios/.github: the
                     conventions review and the ADR index
```

`src/xippios/` has **no** `__init__.py` — it is a PEP 420 namespace package shared
with every `xippios-<source>` distribution. `tests/test_public_surface.py` fails if one
appears.

Rules of the tree (ADR-0004):

- A concern is a subpackage when it has an optional dependency or more than one
  internal module; otherwise it is a single module. Do not add empty directories.
- Imports point downward only: `errors`, `redaction`, `_tasks` and `models` at the bottom;
  `client`, `pagination`, `reference`, `data_gov` above; `mcp`, `http`, `testing` on top.
  Nothing below an adapter imports an adapter.
- The MCP adapter targets the official `mcp` SDK 2.x (`mcp.server.mcpserver.MCPServer`).
  `FastMCP` no longer exists there; the standalone `fastmcp` package is not used.
- Constructing an `MCPServer` configures root logging at `INFO`, and httpx logs every
  request URL at `INFO`; URLs can carry a key or a tenant host (ADR-0005). `build_server`
  and `main` therefore call `quiet_request_logging()`. Keep both calls; the tests in
  `tests/mcp/` guard them, and the testing plugin restores the logger levels per test.
- The public surface is the `__all__` of the five `__init__.py` files and nothing else:
  each exports what consumers import (ADR-0023, decision 5), and
  `tests/test_public_surface.py` pins all five. A helper core calls itself stays
  importable from its own module, outside the surface. `xippios.core.mcp`,
  `xippios.core.http` and `xippios.core.testing` are imported explicitly by their users.

## Commands

```bash
uv sync --all-extras          # environment with every optional extra
uv run pytest                 # unit tests (recorded fixtures only)
uv run pytest -m live         # live tests; skipped unless XIPPIOS_LIVE_TESTS=1
uv run ruff check . && uv run ruff format --check .
uv run mypy                   # --strict over src, tests and scripts
uv run pre-commit run --all-files
uv run python scripts/adr_index.py   # after a record changes; --check verifies the index
```

## Rules of the work

- Commit small, with Conventional Commits messages (`feat(client): add retry budget`).
- Every change brings its changelog entry as a fragment under `changelog/`, in the form
  `changelog/README.md` gives.
- No tag by hand: the release PR's merge runs `publish.yml`, which tags `vX.Y.Z` from
  `pyproject.toml` on the merge commit (conventions §12).
- Never read or print `.envrc`, `.env`, or any variable ending in `_API_KEY`,
  `_REFRESH_TOKEN` or `_SECRET`.
- `ruff` is configured to leave `docs/` alone; never reformat code blocks in the
  governing documents.
- If a convention seems wrong, say so in the PR description and follow it anyway; changing
  a convention is its own change to `docs/conventions.md` with an ADR.

## When something is unclear

Prefer the smallest change that satisfies the documents above, state the assumption in
the PR description, and stop rather than guess at public API shape. Public surface in
`__init__.py` is the hardest thing to change later.
