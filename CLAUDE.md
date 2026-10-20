# sdk-core — instructions for Claude Code

`xippios-core` is the shared foundation of the xippios Python SDK family: HTTP client,
error taxonomy, base models with release metadata, reference-data loading, and the
helpers that turn SDK functions into MCP tools and FastAPI routes. Every
`xippios-<source>` package depends on it. Nothing in this repo knows about any
particular upstream API.

## Read first, in this order

1. `docs/conventions.md` — the family-wide rules this repo implements and enforces
2. `docs/adr/` — the decisions behind them (0001 layering, 0002 runtime stack, 0003 upstream fidelity)
3. `docs/definition-of-done.md` — what a PR must satisfy before it is opened

The family file `../CLAUDE.md` applies as well.

## Layout

```
src/xippios/core/
  __init__.py        public surface, re-exports only
  client.py          HTTP client (httpx), retries, rate limiting, caching hooks
  config.py          settings loading (env vars), per-source key resolution
  errors.py          error taxonomy
  models.py          ResultMeta, Result[T], base model config
  reference.py       loader for packaged reference data (code lists, calendars)
  pagination.py      page/cursor helpers
  mcp.py             FastMCP helpers: tool registration, result caps, error-to-text   [extra: mcp]
  http.py            FastAPI helpers: router factory from task functions             [extra: http]
  testing.py         respx fixtures and live-test gate shared by all source repos    [extra: testing]
tests/
docs/
  conventions.md  adr/  definition-of-done.md  handover.md
.github/workflows/
  ci.yml             job name MUST be `ci` (the org ruleset requires that check)
  publish.yml        runs in environment `pypi`; triggered by tags v*
```

`src/xippios/` has **no** `__init__.py` — it is a PEP 420 namespace package shared
with every `xippios-<source>` distribution.

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

- Branch from `main` as `feature/<topic>`, `fix/<topic>` or `chore/<topic>`. Never commit to `main`.
- Commit small, with Conventional Commits messages (`feat(client): add retry budget`).
- Open the PR with `gh pr create`, body = the definition-of-done checklist, ticked honestly.
- Never tag, merge, release, force-push, or touch `gh secret`. Those are human actions.
- Never read or print `.envrc`, `.env`, or any variable ending in `_API_KEY`.
- If a convention seems wrong, say so in the PR description and follow it anyway; changing
  a convention is its own PR against `docs/conventions.md` plus an ADR.

## When something is unclear

Prefer the smallest change that satisfies the documents above, state the assumption in
the PR description, and stop rather than guess at public API shape. Public surface in
`__init__.py` is the hardest thing to change later.
