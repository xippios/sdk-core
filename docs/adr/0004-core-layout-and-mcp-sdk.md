# ADR-0004: Core internal layout, dependency direction and MCP SDK choice

Status: Accepted · Date: 2026-10-20

## Context

`xippios-core` carries three optional adapters (MCP, HTTP, testing), each behind an
extra, and a client whose concerns (retries, rate limiting, caching) will each grow.
The first layout listed them as single modules. Meanwhile the official `mcp` Python
SDK released 2.x, which renamed `FastMCP` to `MCPServer` and changed field names to
snake_case; the earlier wording "FastMCP helpers" became ambiguous between that SDK
and the standalone `fastmcp` package.

## Decision

- **Subpackage rule.** A concern becomes a subpackage when it has an optional
  dependency or more than one internal module; otherwise it stays a single module.
  Today: `client/`, `mcp/`, `http/`, `testing/` are packages; `errors`, `models`,
  `config`, `pagination`, `reference` are modules.
- **Dependency direction.** Imports point downward only: `errors`, `models` at the
  bottom; `config`, `client`, `pagination`, `reference` above them; the adapters on
  top. Nothing below an adapter imports one. A fourth adapter is a new sibling
  package and a new extra.
- **Import paths stay as conventions §8–§9 name them**: `xippios.core.mcp`,
  `xippios.core.http.router_from_tasks`. No `adapters/` folder above them; the names
  mirror the `mcp.py` / `http.py` every source package has at its top level.
- **Public surface** is `xippios.core.__init__` only. Adapters are never re-exported
  there, so `import xippios.core` works without any extra installed.
- **MCP SDK**: the official `mcp>=2` (`mcp.server.mcpserver.MCPServer`). The
  standalone `fastmcp` package is not used.
- **Sync facade**: one daemon thread owns one event loop for the process;
  `xippios.core.sync` derives a sync function from an async one and strips a trailing
  `_async` from its name. `AsyncClient` keeps one `httpx` pool per event loop so a
  single instance serves the sync facade and an async server at once.
- **Base model**: `UpstreamModel` (frozen, unknown fields ignored, population by
  name or alias) is the base for payload models only. `Result` and `ResultMeta` stay
  plain `BaseModel` as conventions §4 writes them.

## Consequences

- Growth inside a concern (a Redis cache, per-endpoint limits, a write-tool server)
  adds a module to a package; nothing moves.
- `py.typed` ships in the package; without it `mypy --strict` fails in every
  consumer.
- The layout block in `CLAUDE.md` was updated; conventions.md did not change.
