# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

### Added

- `xippios.core.mcp.quiet_request_logging()`: sets the `httpx` and `httpcore` loggers
  to `WARNING`. Idempotent; `build_server` and `main` call it.
- `ResultMeta.total` (default `None`): upstream's count of the records matching the
  request, when the source reports one. A paginated task sets it from upstream's count
  whether it collects every page or returns one, so the caller can page; it is never
  computed from `len(data)`, and a negative count is refused. `cap_result` keeps it next
  to the capped rows, and HTTP responses carry it, as `null` when unset. Optional, so
  sources on 0.1.0 are unaffected (sdk-cashctrl).
- ADR-0012, upstream totals in the result envelope; conventions 1.7 lists `total` in
  §4 with its paginated-task semantics.

### Security

- The MCP servers no longer log request URLs. Constructing an `MCPServer` (`mcp` SDK
  2.x) configures root logging at `INFO` on stderr, and httpx logs every request at
  `INFO` with its full URL, so every `xippios-<source>-mcp` entry point wrote each
  upstream URL to stderr, which MCP clients keep in their logs. For a source that sends
  its key as a query parameter (`QueryKeyAuth`; usda-nass sends `key=`) that put the
  API key into the client's logs; for a multi-tenant source (cashctrl) it put the tenant
  host there. `build_server` now sets the `httpx` and `httpcore` loggers to `WARNING`
  right after constructing the server, and `main` does so again before running it
  (ADR-0005). A consumer who wants the request log raises the level after building the
  server and runs it without `main`.

## [0.1.0] - 2026-10-22

First release, cut after the first source package (sdk-usda-nass) had exercised it.

### Added

- `xippios.core.errors`: the family error taxonomy (`XippiosError` and seven
  subclasses), `error_from_response`, `raise_for_status`, `parse_retry_after`.
- `xippios.core.models`: `UpstreamModel`, `ResultMeta`, `Result[T]`, `parse`.
- `xippios.core.config`: `SourceSettings` base and `resolve_api_key`.
- `xippios.core.sync`: derive a sync function from an async one on a shared
  background event loop.
- `xippios.core.client`: `AsyncClient` and `Client` with `ClientConfig`, `Timeouts`,
  `RetryPolicy`, `RateLimit`, `MemoryCache` and the `CacheBackend` protocol.
- `xippios.core.client.auth`: `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth`,
  `BasicKeyAuth` and the `EnvKeyAuth` base, resolving the key from the environment on
  the first request. Re-exported from `xippios.core`.
- `ResultMeta` redacts credential-like keys in `request` at construction (ADR-0005).
- `resolve_api_key` is typed to return `SecretStr` when the key is required.
- `xippios.core.pagination`: `paginate_offset`, `paginate_pages`, `paginate_cursor`,
  `collect`.
- `xippios.core.reference`: `load_csv`, `load_json`, `load_table`.
- `xippios.core.mcp` (extra `mcp`): `build_server`, `register_tasks`, `cap_result`,
  `error_to_text`, `main`.
- `xippios.core.http` (extra `http`): `router_from_tasks`, `problem_response`,
  `install_error_handlers`.
- `xippios.core.testing` (extra `testing`): pytest plugin with the `live` gate,
  fixture format, `record`, `replay`, scrubbing helpers.
- CI on Python 3.12, 3.13 and 3.14; trusted publishing on `v*` tags.
- `UpstreamModel` serialises `Decimal` fields as JSON numbers in both adapters
  (ADR-0008); `UpstreamModel.project` builds projections; `parse_decimal` reads
  published figures with separators or suppression codes.
- `ClientConfig.classify`: a source's error mapping, called on every response before
  the default status mapping.
- `xippios.core.reference.render_str_enums` and `enum_member_name`: generated
  `StrEnum` source for packaged value lists.
- `xippios.core.testing.assert_projection` and `mcp_call`.
- `InvalidRequestError` in the taxonomy (ADR-0007): a request refused before it is
  sent; HTTP 422, MCP text. Re-exported from `xippios.core`.
- `xippios.core.http.is_scalar`.

### Changed

- `router_from_tasks`: a task with any non-scalar parameter becomes a `POST` route whose
  JSON body is an object keyed by parameter name; scalar-only tasks stay `GET`.
