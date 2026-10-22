# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

### Added

- `xippios.core.errors`: the family error taxonomy (`XippiosError` and seven
  subclasses), `error_from_response`, `raise_for_status`, `parse_retry_after`.
- `xippios.core.models`: `UpstreamModel`, `ResultMeta`, `Result[T]`, `parse`.
- `xippios.core.config`: `SourceSettings` base and `resolve_api_key`.
- `xippios.core.sync`: derive a sync function from an async one on a shared
  background event loop.
- `xippios.core.client`: `AsyncClient` and `Client` with `ClientConfig`, `Timeouts`,
  `RetryPolicy`, `RateLimit`, `MemoryCache` and the `CacheBackend` protocol.
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
