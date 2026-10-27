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

## Amendment 2026-10-27

Two lines of the decision describe code that core 0.3.0 deletes for want of a consumer
(ADR-0023, decision 5; `docs/roadmap.md` §3, item 0, decided by Johannes on
2026-10-26):

- "`pydantic-settings` for configuration": `xippios.core.config`, with `SourceSettings`
  and the public `resolve_api_key`, is deleted and `pydantic-settings` leaves the
  dependencies; no source subclassed `SourceSettings`. A key is read from the
  environment by the `EnvKeyAuth` helpers on the first request, an explicit key
  winning, as conventions §7 states from 1.16 on. `pydantic` v2 stays for every model,
  `SecretStr` with it.
- "The sync facade runs the async core via a managed event loop": the sync facade is
  `xippios.core.sync`, which derives a sync function from an async one and runs it on
  the one background loop (ADR-0004). The synchronous `Client` over `AsyncClient` is
  deleted; every source derives its sync task functions with `sync`.
