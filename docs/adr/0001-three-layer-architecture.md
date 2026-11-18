# ADR-0001: Three-layer architecture for source packages

Status: Accepted · Date: 2026-10-20 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

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

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **A task may compose a task of its own module** (step 14;
https://github.com/xippios/sdk-core/issues/70, found by sdk-eurostat, with sdk-faostat
its second consumer). "Task functions call only endpoint wrappers and reference data" left
a task that slices or extends another task's answer to repeat that task's calls of the
wrappers. sdk-eurostat's `get_series`, `get_latest_period` and `get_cross_section` compose
its `get_data`, and sdk-faostat's `get_series` composes its `get_data` with one request
over a year list: the composed task owns the request, its refusals before sending, the
`classify` mapping it relies on and the meta, so each lives in one place. A task may
therefore compose another task of its own `tasks.py`. It awaits the other task's `_async`
function, since the sync facade refuses a call from inside core's loop. A task of another
package is composed only as ADR-0021, decision 1 allows it. A composing task that extends
the composed answer's `meta.request` builds a new `ResultMeta` through the constructor
from that answer's meta, never with `model_copy`, which runs no validator: the drop of a
top-level `None` (ADR-0022) and the redaction of credentials (ADR-0005) then reach what
it adds. Conventions §2 and §4 state it from 1.28 on.
