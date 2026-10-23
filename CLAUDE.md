# sdk-core — instructions for Claude Code

`xippios-core` is the shared foundation of the xippios Python SDK family: HTTP client,
error taxonomy, base models with release metadata, reference-data loading, and the
helpers that turn SDK functions into MCP tools and FastAPI routes. Every
`xippios-<source>` package depends on it. Nothing in this repo knows about any
particular upstream API.

## Read first, in this order

1. `docs/conventions.md` — the family-wide rules this repo implements and enforces
2. `docs/adr/` — the decisions behind them (0001 layering, 0002 runtime stack,
   0003 upstream fidelity, 0004 core layout and MCP SDK, 0005 no credentials in the envelope,
   0006 nested import paths, 0007 InvalidRequestError and POST routes,
   0008 hardening from the first source, 0009 one key variable per issuer,
   0010 rate-limit policy, 0011 retries and non-idempotent methods,
   0012 upstream totals in the result envelope)
3. `docs/definition-of-done.md` — what a PR must satisfy before it is opened

The family file `../CLAUDE.md` applies as well.

## Layout

```
src/xippios/core/
  __init__.py        public surface, re-exports only; adapters are NOT re-exported
  py.typed           PEP 561 marker; without it mypy --strict fails in every source repo
  _version.py        __version__ from distribution metadata
  _loop.py           one background event loop; sync() derives sync functions from async
  errors.py          error taxonomy, response/exception classifiers
  models.py          UpstreamModel, ResultMeta, Result[T], parse()
  config.py          SourceSettings base, resolve_api_key()
  pagination.py      offset / page-number / cursor iterators, collect()
  reference.py       loader for packaged reference data (CSV, JSON)
  client/            httpx client: config, retry, ratelimit, cache, auth (env-key helpers), _core, Client
  mcp/               MCP server helpers: server, results (caps), errors (to text), cli   [extra: mcp]
  http/              FastAPI helpers: router (from tasks), problems (RFC 9457)          [extra: http]
  testing/           pytest plugin (live gate), fixtures, record, replay, scrub, adapters [extra: testing]
tests/               mirrors the tree: tests/client/, tests/mcp/, tests/http/, tests/testing/
docs/
  conventions.md  adr/  definition-of-done.md  handover.md
.github/workflows/
  ci.yml             job name MUST be `ci` (the org ruleset requires that check)
  publish.yml        runs in environment `pypi`; triggered by tags v*
```

`src/xippios/` has **no** `__init__.py` — it is a PEP 420 namespace package shared
with every `xippios-<source>` distribution. `tests/test_public_surface.py` fails if one
appears.

Rules of the tree (ADR-0004):

- A concern is a subpackage when it has an optional dependency or more than one
  internal module; otherwise it is a single module. Do not add empty directories.
- Imports point downward only: `errors` and `models` at the bottom; `config`, `client`,
  `pagination`, `reference` above; `mcp`, `http`, `testing` on top. Nothing below an
  adapter imports an adapter.
- The MCP adapter targets the official `mcp` SDK 2.x (`mcp.server.mcpserver.MCPServer`).
  `FastMCP` no longer exists there; the standalone `fastmcp` package is not used.
- Constructing an `MCPServer` configures root logging at `INFO`, and httpx logs every
  request URL at `INFO`; URLs can carry a key or a tenant host (ADR-0005). `build_server`
  and `main` therefore call `quiet_request_logging()`. Keep both calls; the tests in
  `tests/mcp/` guard them, and the testing plugin restores the logger levels per test.
- The public surface is `__init__.py` and nothing else. `xippios.core.mcp`,
  `xippios.core.http` and `xippios.core.testing` are imported explicitly by their users.

## Commands

```bash
uv sync --all-extras          # environment with every optional extra
uv run pytest                 # unit tests (recorded fixtures only)
uv run pytest -m live         # live tests; skipped unless XIPPIOS_LIVE_TESTS=1
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pre-commit run --all-files
```

## Workflow rules

- Branch from `main` as `feature/<topic>`, `fix/<topic>`, `chore/<topic>` or `docs/<topic>`.
  Never commit to `main`.
- Commit small, with Conventional Commits messages (`feat(client): add retry budget`).
- Open the PR with `gh pr create`, body = the definition-of-done checklist, ticked honestly.
- Never tag, merge, release, force-push, or touch `gh secret`. Those are human actions.
- Never read or print `.envrc`, `.env`, or any variable ending in `_API_KEY`.
- `ruff` is configured to leave `docs/` alone; never reformat code blocks in the
  governing documents.
- If a convention seems wrong, say so in the PR description and follow it anyway; changing
  a convention is its own PR against `docs/conventions.md` plus an ADR.

## When something is unclear

Prefer the smallest change that satisfies the documents above, state the assumption in
the PR description, and stop rather than guess at public API shape. Public surface in
`__init__.py` is the hardest thing to change later.
