# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

### Added

- `xippios.core.mcp.quiet_request_logging()`: sets the `httpx` and `httpcore` loggers
  to `WARNING`. Idempotent; `build_server` and `main` call it.
- `ClientConfig.cache_filter`: called with each GET as built from base URL, path and
  query parameters; the GET is looked up in and stored to the cache only when it
  returns `True`. `None` caches every GET, as before. Cache keys are hashes, so a
  backend cannot tell one path from another, and a source that wanted one cached
  endpoint needed a second client (sdk-usda-psd).
- `limiter` keyword for `AsyncClient` and `Client`: a `TokenBucket` used instead of one
  built from `config.rate_limit`, which is then ignored. `AsyncClient.limiter` returns
  the bucket in use, so a second client can share the first one's pace; before, a
  limiter could not be shared through any public API (sdk-usda-psd).
- `xippios.core.client.WIRE_HEADERS` and `strip_wire_headers`: the headers that describe
  how a body travelled (`content-length`, `content-encoding`, `transfer-encoding`,
  `connection`), dropped from cache entries and recorded fixtures alike.
- `RetryPolicy.retry_non_idempotent` (default `False`): retry a 5xx and a transport
  failure for POST, PUT, PATCH and DELETE too, for sources whose upstream makes a
  repeated write safe, e.g. by an idempotency key, or that only read through POST
  (ADR-0011).
- `ResultMeta.total` (default `None`): upstream's count of the records matching the
  request, when the source reports one. A paginated task sets it from upstream's count
  whether it collects every page or returns one, so the caller can page; it is never
  computed from `len(data)`, and a negative count is refused. `cap_result` keeps it next
  to the capped rows, and HTTP responses carry it, as `null` when unset. Optional, so
  sources on 0.1.0 are unaffected. Needed first by sdk-cashctrl.
- `xippios.core.testing.Scrub(host, secrets, rewrite, allow_binary)`: what a recording
  removes besides credentials, applied in memory to the request URL, request body,
  response headers and response body before the fixture is written once, so the file
  never holds the removed text, not even briefly. `host` replaces the request's host
  with a placeholder and every occurrence of the original host (any letter case, its
  IDNA form too, plain or percent-encoded) with it; `secrets` turns each value into
  `REDACTED`, plain and percent-encoded, the longest first; `rewrite` is a text hook
  for the request body, the response body and every response header value (`Location`
  included), for pre-authenticated URLs. `write_fixture`, `fixture_from_response` and
  `record` take it as `scrub=`. The credential scrubbing of 0.1.0 still always
  applies. Ports the recorder pattern sdk-cashctrl had to keep locally: `write_fixture`
  kept the tenant host in `request.url`, and CashCtrl's `file/prepare.json` answers with
  signed storage URLs that `file/get` redirects to.
- `FixtureRequest.body`, `body_base64` and `content_type`: the request body as scrubbed
  UTF-8 text (the form or JSON text sent; `None` without a body) and the request's
  `Content-Type`, so a write fixture can assert its payload (sdk-cashctrl). Fixtures
  written by 0.1.0 still load.
- `data=` for `AsyncClient.request`, `Client.request`, `record` and `record_sync`: a body
  sent form-encoded (`application/x-www-form-urlencoded`) next to `json=`; passing both
  raises `ValueError`. CashCtrl's writes are form-encoded (sdk-cashctrl).
- `AsyncClient.derive(retry=..., timeouts=...)`: a new client on the same configuration
  with only those replaced, sharing auth, transport, sleep, rate limiter and cache.
- `record` and `record_sync` take `headers=`, `scrub=`, `retry=` and `timeouts=`; an
  override goes through `client.derive`. A recording could not override the client's
  retry policy or timeouts (sdk-comtrade).
- `match_params=` for `mount_fixture`, `replay` and the plugin's `replay_fixture`: names
  of recorded query parameters whose recorded values a request must carry too; a name
  absent from the recorded URL or recorded as `REDACTED` raises `ValueError`. Replay
  matched on method, host and path only, so a count call (`countOnly=true`) and the data
  call on the same path could not be told apart (sdk-comtrade). The request body is
  never matched; a test asserts it from the route's calls.

### Changed

- **Breaking:** a 5xx and a transport failure are retried for GET, HEAD and OPTIONS
  only. A POST, PUT, PATCH or DELETE answered with a 5xx is returned after one attempt
  and raised as `UpstreamError`; a 429 is still retried for every method. Before, every
  5xx was retried for every method, so a POST that upstream had applied before
  answering 502, 503 or 504 was sent again and could duplicate a booking
  (sdk-cashctrl). `RetryPolicy(retry_non_idempotent=True)` retries writes again
  (ADR-0011; conventions 1.6, §6).
- Error messages from `error_from_response` name the method and path, never the host:
  `404 from GET /v1/series: ...`, no longer `404 from GET api.example.org/v1/series: ...`.
  For a multi-tenant source the host names the tenant, which sdk-cashctrl had to mask in
  its own `classify` (ADR-0005 amendment; conventions 1.6, §5). The query string was
  left out before already. `error_from_exception` replaces the request's host with
  `<host>` in a `TransportError` message, since a transport failure's text can quote it
  (a TLS hostname mismatch does).
- Conventions 1.6: §5 and §6 as above; ADR-0011 added.
- Conventions 1.7: §4 lists `ResultMeta.total` with its paginated-task semantics;
  ADR-0012 added.
- **Breaking:** recording a request or response body that is not UTF-8 text raises
  `ValueError` ("binary body cannot be scrubbed") and writes nothing, unless
  `Scrub(allow_binary=True)` is passed; then it is stored base64 with
  `body_base64: true`, unscrubbed, as 0.1.0 stored every such body without asking. No
  scrub can read a binary body (sdk-cashctrl refused them locally).
- **Breaking:** `EnvKeyAuth.apply(self, request)` reads the key itself through
  `self.key()` and no longer takes it as an argument; `auth_flow` calls
  `self.apply(request)`. `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth` and
  `BasicKeyAuth` keep the key in no argument and no local variable. As an argument the
  key was part of every traceback frame through `apply`, and pytest's long tracebacks
  print a frame's arguments, so a failing test could print the shell's key
  (sdk-usda-nass). A subclass outside core that implements `apply(request, key)` drops
  the parameter and calls `self.key()` where it attaches the key; none is known.
- Conventions 1.8: §6 names form bodies next to JSON ones; §10 states the recorder's
  rules (scrub in memory before the one write, a placeholder host for a multi-tenant
  source, no binary body unless flagged).

### Fixed

- A gzip answer replayed from the cache raised `httpx.DecodingError`: the client stored
  the decoded body together with `content-encoding`, so the replay decoded it again.
  Cache entries are stored without wire headers now, and entries a persistent backend
  kept from 0.1.0 are stripped when replayed (sdk-usda-psd PR 3 live tests).
- Taxonomy errors survive `copy.copy`, `copy.deepcopy` and `pickle`: `AuthError`,
  `ValidationError`, `UpstreamError` and source subclasses with keyword-only arguments
  raised `TypeError`, because `Exception` rebuilds with positional arguments only.
  `XippiosError.__reduce__` restores every attribute without calling `__init__`
  (sdk-cashctrl).

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
- `.gitignore` also ignores `.env.*` and `.envrc.*` (sdk-comtrade).
- The secret scan no longer skips paths containing "swagger": detect-secrets'
  `is_swagger_file` filter is dropped from `.secrets.baseline`, because it exempted
  every such path, a verbatim upstream Swagger snapshot included (sdk-usda-psd).
  `.secrets.baseline` and the detect-secrets hook exclude `.copier-answers.yml` with
  sdk-template's pattern, so the template can copy both files verbatim again
  (sdk-comtrade).

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
