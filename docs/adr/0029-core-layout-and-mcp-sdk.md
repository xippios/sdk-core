# ADR-0029: Core internal layout, dependency direction and MCP SDK choice

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0004

## Context

`xippios-core` carries three optional adapters (MCP, HTTP, testing), each behind an extra,
and a client whose concerns (retries, rate limiting, caching) each grow. The official `mcp`
Python SDK 2.x renamed `FastMCP` to `MCPServer`, which left "FastMCP helpers" ambiguous
between that SDK and the standalone `fastmcp` package. This record states ADR-0004 with its
three amendments of 2026-10-27 as they stand, and changes no decision; their history stays in
ADR-0004.

## Decision

1. **Subpackage rule.** A concern becomes a subpackage when it has an optional dependency or
   more than one internal module; otherwise it stays a single module. By this rule
   `client/`, `mcp/`, `http/` and `testing/` are packages, and `errors`, `models`,
   `pagination`, `reference` and `redaction` are modules, beside the private `_tasks`.
   `client/download.py` holds `Downloaded` and what the streaming `AsyncClient.download` is
   built from, and `reference` holds `PackagedList`, `matches` and `closest`.
2. **Dependency direction.** Imports point downward only: `errors`, `redaction`, `_tasks`
   and `models` at the bottom; `client`, `pagination` and `reference` above them; the
   adapters on top. `redaction`, the one credential rule, is imported by `models`, `client`
   and `testing` and imports nothing of core's; `_tasks` reads a source's `BULK_TASKS` for
   the adapters; `reference` imports `models`, below it. Nothing below an adapter imports
   one. A fourth adapter is a new sibling package and a new extra.
3. **Import paths stay as conventions §8 and §9 name them**: `xippios.core.mcp`,
   `xippios.core.http.router_from_tasks`. No `adapters/` folder above them; the names mirror
   the `mcp.py` and `http.py` every source package has at its top level.
4. **Public surface.** The public surface is the `__all__` of `xippios.core` and of the four
   subpackages `client`, `mcp`, `http` and `testing`, each exporting what consumers import
   (ADR-0023, decision 5). The adapters are never re-exported from `xippios.core`, so
   `import xippios.core` works without any extra installed. `ResultCap` is defined in
   `models`, at the bottom, so `xippios.core` exports it without the `mcp` extra, and
   `xippios.core.mcp` re-exports it; Johannes decided it on 2026-10-27.
5. **MCP SDK**: the official `mcp>=2` (`mcp.server.mcpserver.MCPServer`). The standalone
   `fastmcp` package is not used.
6. **Sync facade**: one daemon thread owns one event loop for the process;
   `xippios.core.sync` derives a sync function from an async one and strips a trailing
   `_async` from its name, and it is the sync facade alone, with no sync client.
   `AsyncClient` keeps one `httpx` pool per event loop, so a single instance serves the sync
   facade and an async server at once.
7. **Base model**: `UpstreamModel` (frozen, unknown fields ignored, population by name or
   alias) is the base for payload models only. `Result` and `ResultMeta` stay plain
   `BaseModel` as conventions §4 writes them, and `ResultMeta` refuses the fields it does
   not define.

## Consequences

- Growth inside a concern (a Redis cache, per-endpoint limits, a write-tool server) adds a
  module to a package; nothing moves.
- `py.typed` ships in the package; without it `mypy --strict` fails in every consumer.

Core's `CLAUDE.md` states its decisions in its layout and its rules of the tree.
