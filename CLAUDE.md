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
  _tasks.py          what core reads from a source's tasks.py: tool_functions (tasks.__all__ minus
                     BULK_TASKS), BULK_TASKS for the adapters, NO_TENANT_TASKS for bind_tasks
  contract.py        EnvVar, a variable of the package contract; imports nothing of core's
  errors.py          error taxonomy (UnknownCode: a code a packaged list lacks; QueryTooLarge: a
                     query over upstream's limit), response/exception classifiers,
                     request_description (the method and path a message names)
  redaction.py       the one credential rule (REDACTED, the names QueryKeyAuth registers,
                     register_data_name for a cursor that is data), scrub_params/url/headers;
                     imports nothing of core's
  models.py          UpstreamModel (dump_upstream), ResultMeta (unknown fields refused,
                     published_at_naive, names, request without None and redacted by
                     redaction), Result[T], ResultCap (paged, keep), parse(), newer_than
                     and naive_time; re-exports REDACTED
  pagination.py      paginate_offset (page numbers map onto offsets), collect(), fetch_counted
                     (the count before a query over upstream's limit)
  reference.py       loader for packaged reference data (CSV, JSON); PackagedList (load, meta, parse,
                     write, codes), PackagedCodes (check), names_codes, matches, closest,
                     nearest; render_enums (StrEnum and IntEnum in one module)
  series.py          a series over periods: Ceiling (its check, its option on the MCP server),
                     fetch_periods
  data_gov.py        the api.data.gov gateway: Gateway (key, classify, one QuotaPolicy per process),
                     NoDataForYear (FAS's empty 404 on a data path)
  tenants.py         Tenants (one client per tenant), list_task; TenantLock, bind_tasks and
                     tenant_instructions, a server bound to one tenant
  client/            httpx client: config, retry, ratelimit, cache, quota, auth (env-key helpers,
                     the renewing bearer), download (Downloaded, streaming), _core (AsyncClient
                     with post_json, delete_json, download and get_answer, the generic Answer,
                     decode_json/decode_text/decode_csv)
  mcp/               MCP server helpers: server (register_tasks, tool_functions, the loopback
                     option), toolset (ToolSet), results (caps), errors (to text), cli (main,
                     serve_tenants, LOOPBACK_HOSTS)                                 [extra: mcp]
  http/              FastAPI helpers: router (from tasks), problems (RFC 9457)          [extra: http]
  refresh/           the frames of a source's scripts, imported by the scripts alone: upstream
                     (Snapshot, run, compare_fetched: the snapshot under docs/upstream/ with
                     its FETCHED.md), reference (Listed, Enumeration: the packaged lists and
                     enums.py)
  testing/           pytest plugin (live gate, offline guarantees, anyio_backend), fixtures (the
                     writer, the sample mark, max_bytes truncation), record (a source's rewrite
                     step, send_once, record_task), replay (sent_bodies),
                     scrub (Scrub: named secrets and response_secrets, plain verify; credentials
                     by redaction), adapters (mcp_call, mcp_call_text, assert_write_tools),
                     environment (keep_reserved_tenants), clock (slack for wall-clock reads),
                     built_answers (the mark of a built answer and its census), live (the nightly
                     comparison of a packaged list), family (the conformance check)
                                                                                [extra: testing]
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
  conventions.yml    the organization's conventions check from xippios/.github: the review of a
                     release PR, and of main's range once a package's steps are merged
  adr-index.yml      the organization's check that docs/adr.md and docs/adr.json are current
```

`src/xippios/` has **no** `__init__.py` — it is a PEP 420 namespace package shared
with every `xippios-<source>` distribution. `tests/test_public_surface.py` fails if one
appears.

Rules of the tree (ADR-0029):

- A concern is a subpackage when it has an optional dependency or more than one
  internal module; otherwise it is a single module. Do not add empty directories.
- Imports point downward only: `errors`, `redaction`, `_tasks`, `contract` and `models` at
  the bottom; `client`, `pagination`, `reference`, `series`, `data_gov` and `tenants`
  above; `mcp`, `http`, `testing` and `refresh` on top (ADR-0046, decision 1). Nothing
  below an adapter imports an adapter.
- The MCP adapter targets the official `mcp` SDK 2.x (`mcp.server.mcpserver.MCPServer`).
  `FastMCP` no longer exists there; the standalone `fastmcp` package is not used.
- Constructing an `MCPServer` configures root logging at `INFO`, and httpx, as the `mcp`
  SDK's own httpx2, logs every request URL at `INFO`; URLs can carry a key or a tenant
  host (ADR-0030, decision 4). `build_server` and `main` therefore call
  `quiet_request_logging()`, which sets the `httpx`, `httpcore`, `httpx2` and `httpcore2`
  loggers to `WARNING`. Keep both calls; the tests in `tests/mcp/` guard them, and the
  testing plugin restores the logger levels per test.
- The public surface is the `__all__` of the six `__init__.py` files and nothing else:
  each exports what consumers import (ADR-0023, decision 5), and
  `tests/test_public_surface.py` pins all six. A helper core calls itself stays
  importable from its own module, outside the surface. `xippios.core.mcp`,
  `xippios.core.http`, `xippios.core.testing` and `xippios.core.refresh` are imported
  explicitly by their users, the last by a source's scripts (ADR-0046, decision 1).

## Commands

```bash
uv sync --all-extras          # environment with every optional extra
uv run pytest                 # unit tests (recorded fixtures only)
uv run pytest -m live         # live tests; skipped unless XIPPIOS_LIVE_TESTS=1
uv run ruff check . && uv run ruff format --check .
uv run mypy                   # --strict over src, tests and scripts
uv run pre-commit run --all-files
python3 -I scripts/adr_index.py      # after a record changes; --check verifies the index
```

## Rules of the work

- Commit small, with Conventional Commits messages (`feat(client): add retry budget`).
- Every change brings its changelog entry as a fragment under `changelog/`, in the form
  `changelog/README.md` gives.
- No tag by hand: the release PR's merge runs `publish.yml`, which tags `vX.Y.Z` from
  `pyproject.toml` on the merge commit (conventions §12).
- Never read or print `.envrc`, `.env` or a variable that holds a credential: each one
  the package reads a credential from, and any whose name ends in `_API_KEY`, `_TOKEN` or
  `_SECRET` (conventions §7).
- `ruff` is configured to leave `docs/` and `scripts/adr_index.py` alone: never reformat
  code blocks in the governing documents, and the script is the one file that the
  organization's repositories share byte for byte.
- If a convention seems wrong, say so in the PR description and follow it anyway; changing
  a convention is its own change to `docs/conventions.md` with an ADR.

## When something is unclear

Prefer the smallest change that satisfies the documents above, state the assumption in
the PR description, and stop rather than guess at public API shape. Public surface in
`__init__.py` is the hardest thing to change later.
