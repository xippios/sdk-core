# ADR-0001: Three-layer architecture for source packages

Status: Accepted · Date: 2026-10-20

## Context

Each `xippios-<source>` package must serve three consumers with one codebase: Python
code (scripts, pipelines), AI agents via MCP, and non-Python services (Laravel) via
HTTP. Maintenance is AI-driven; conventions must be mechanical enough that a session
cannot reasonably put logic in the wrong place.

## Decision

Every source package has exactly three layers:

1. Endpoint wrappers (`api/`) — one function per upstream operation, mirroring upstream.
2. Task-shaped functions (`tasks.py`) — the public API; compose wrappers, return `Result[T]`.
3. Adapters (`mcp.py`, `http.py`) — thin registrations over task functions, ≤ 60 lines.

Adapters call only task functions. Task functions call only endpoint wrappers and
reference data. No layer is skipped; no logic lives in an adapter.

## Consequences

- MCP tools and HTTP routes are generated from the same signatures, so they cannot drift.
- Endpoint coverage and task design are reviewed separately: the first is mechanical
  (does it match the docs), the second is domain (is this what a user wants).
- A fourth consumer (CLI, gRPC) is another adapter, not a refactor.
- The cost is some indirection for trivial sources; accepted for uniformity.
