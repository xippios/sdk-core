# ADR-0002: Runtime stack — Python 3.12, httpx, pydantic v2, sync facade over async core

Status: Accepted · Date: 2026-10-20

## Context

Consumers range from one-off scripts to agent servers. Public SDKs that force async
on callers see lower adoption; async-only servers are nonetheless the norm for MCP.

## Decision

- Python floor 3.12 (`StrEnum`, modern typing, `tomllib`).
- `httpx` as the only HTTP library; an async client at the core.
- Public task functions are synchronous; an `_async` twin is provided where the
  adapter benefits (MCP server, HTTP router). The sync facade runs the async core
  via a managed event loop in `xippios.core.client`.
- `pydantic` v2 for all models and settings; `pydantic-settings` for configuration.
- `uv` for environment, lock, build and publish; `ruff` and `mypy --strict` gated in CI.

## Consequences

- One code path for retries, rate limits and caching.
- Sync callers never see an event loop; async callers get native performance.
- Pydantic models double as MCP tool schemas and OpenAPI schemas.
- Rejected: `requests` (no async), `aiohttp` (no sync story), dataclasses (no validation).
