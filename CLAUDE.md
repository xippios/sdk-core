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
  __init__.py           the public surface, re-exports only; the adapters are NOT re-exported
  py.typed              PEP 561 marker; without it mypy --strict fails in every consumer
  _version.py           __version__ from the distribution's metadata
  _loop.py              one background event loop; sync() derives a sync function from an async one
  _tasks.py             what core reads from a source's tasks.py: tool_functions, tool_name and
                        BULK_TASKS, which the adapters skip
  contract.py           EnvVar, a variable of the package contract; imports nothing of core's
  errors.py             the error taxonomy (UnknownCode, QueryTooLarge), the classifiers of a
                        response and an exception, request_description
  redaction.py          the one credential rule: REDACTED, the credential and data names,
                        scrub_params, scrub_url, scrub_headers; imports nothing of core's
  models.py             UpstreamModel, ResultMeta, Result, NamedBy, ResultCap, parse,
                        parse_decimal, newer_than
  pagination.py         fetch_pages, the one walk of pages, and fetch_counted, the count first
  reference.py          the packaged lists: load_json, PackagedList, PackagedCodes, names_codes,
                        matches, closest, nearest
  series.py             a series over periods: Ceiling and fetch_periods
  tenants.py            Tenants, list_task; TenantLock, bind_tasks and tenant_instructions, a
                        server bound to one tenant
  client/
    __init__.py         the client's public names
    _core.py            AsyncClient and its one request path, get_answer, post_json, download,
                        Answer, decode_csv
    auth.py             KeyAuth, the one key class, BearerToken, RenewingBearerAuth, EnvKeyAuth
    cache.py            MemoryCache, a lifetime per path prefix and a bound on its bytes
    config.py           ClientConfig, RetryPolicy, RateLimit
    download.py         Downloaded, check_dest and the streaming of a file to disk
    quota.py            QuotaPolicy, the quota headers observed and no request into a spent quota
    ratelimit.py        TokenBucket, the rate limiter of any thread or event loop
    retry.py            the retry loop: backoff, Retry-After, a write sent once
  mcp/                                                                        [extra: mcp]
    __init__.py         the adapter's public names
    toolset.py          ToolSet, the package contract's tool set, checked when it is built
    server.py           build_server, register_tasks, quiet_request_logging
    cli.py              main, the one entry; build_parser, LOOPBACK_HOSTS
    results.py          the result caps: cap_result
    errors.py           error_to_text
  http/                                                                       [extra: http]
    __init__.py         the adapter's public names
    router.py           router_from_tasks
    problems.py         RFC 9457 problem details: status_for
  refresh/              the frames of a source's two refresh scripts, imported by them alone
    __init__.py         the frames' public names, run among them
    upstream.py         Snapshot, Page: the snapshot under docs/upstream/ with its FETCHED.md
    reference.py        Lists, Listed, Enumeration, run: the packaged lists and enums.py, with
                        render_enums, the renderer that the frame alone calls
  testing/                                                                    [extra: testing]
    __init__.py         the test support's public names
    plugin.py           the pytest plugin: the live gate, the offline guarantees, replay_fixture
    fixtures.py         the fixture format, its writer, the sample mark, the cut by max_bytes
    record.py           record and send_once, sync, with a source's rewrite step
    replay.py           replay, sent_urls, sent_query, sent_bodies
    scrub.py            Scrub: named secrets and those read from the answer, in every encoded form
    adapters.py         mcp_call, mcp_call_text, assert_projection, assert_write_tools
    environment.py      keep_reserved_tenants
    clock.py            assert_time_between and CLOCK_SLACK, for wall-clock reads
    built_answers.py    the mark of a built answer and its census
    live.py             the nightly comparison of a packaged list
    family.py           the family conformance check
tests/                  mirrors the tree: tests/client/, tests/mcp/, tests/http/, tests/refresh/,
                        tests/testing/
scripts/
  adr_index.py          writes docs/adr.md and docs/adr.json from the records; --check only checks
  count_surface.py      counts core's surface in two parts and the consumers of each piece
changelog/
  README.md             the form of a fragment, one per change, which the release assembles
CHANGELOG.md            each release's section
docs/
  conventions.md        the rules every source package is held to
  definition-of-done.md what a change satisfies before its pull request opens
  review-checklist.md   what the review of a pull request checks, in order
  handover.md           what a source's adoption of a core release does
  adr/                  the architecture decision records
  adr.md, adr.json      their index, written by scripts/adr_index.py
  reports/              dated reports, the evidence of a record
.github/
  PULL_REQUEST_TEMPLATE.md  the frame of a pull request's description
  CODEOWNERS            the paths that a maintainer reviews
  workflows/            ci.yml, publish.yml, conventions.yml and adr-index.yml, each told by its
                        paragraph under the README's ## Workflows
```

`src/xippios/` has **no** `__init__.py` — it is a PEP 420 namespace package shared
with every `xippios-<source>` distribution. `tests/test_public_surface.py` fails if one
appears.

Rules of the tree (ADR-0029):

- A concern is a subpackage when it has an optional dependency or more than one
  internal module; otherwise it is a single module. Do not add empty directories.
- Imports point downward only: `errors`, `redaction`, `_tasks`, `contract` and `models` at
  the bottom; `client`, `pagination`, `reference`, `series` and `tenants` above; `mcp`,
  `http`, `testing` and `refresh` on top (ADR-0062, decision 1). Nothing below an adapter
  imports an adapter.
- The MCP adapter targets the official `mcp` SDK 2.x (`mcp.server.mcpserver.MCPServer`).
  `FastMCP` no longer exists there; the standalone `fastmcp` package is not used.
- Constructing an `MCPServer` configures root logging at `INFO`, and httpx, as the `mcp`
  SDK's own httpx2, logs every request URL at `INFO`; URLs can carry a key or a tenant
  host (ADR-0030, decision 4). `build_server` and `main` therefore call
  `quiet_request_logging()`, which sets the `httpx`, `httpcore`, `httpx2` and `httpcore2`
  loggers to `WARNING`. Keep both calls; the tests in `tests/mcp/` guard them, and the
  testing plugin restores the logger levels per test.
- The public surface is the `__all__` of the six `__init__.py` files and nothing else:
  each exports what consumers import (ADR-0059, decision 3), and
  `tests/test_public_surface.py` pins all six. A helper core calls itself stays
  importable from its own module, outside the surface. `xippios.core.mcp`,
  `xippios.core.http`, `xippios.core.testing` and `xippios.core.refresh` are imported
  explicitly by their users, the last by a source's scripts (ADR-0062, decision 1).

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
