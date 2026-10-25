# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

## [0.2.0] - 2026-10-25

What the first four sources, sdk-usda-nass, sdk-comtrade, sdk-usda-psd and sdk-cashctrl,
had to build around core 0.1.0, moved into core: ADR-0009 to ADR-0018, amendments to
ADR-0003, ADR-0005, ADR-0007, ADR-0008, ADR-0010, ADR-0011, ADR-0013 and ADR-0015, and
conventions 1.4 to 1.13. While core is 0.x a minor keeps no compatibility with the one
before it: a source depends on `xippios-core~=0.2.0` and adopts this release in one
adoption PR before its next release (conventions §12 and §15, ADR-0018).
`docs/handover.md`, "Adopting core 0.2.0", lists per source what that PR deletes and
what replaces it.

### Breaking changes

- **Writes are not retried after a 5xx** (ADR-0011): a 5xx and a transport failure are
  retried for GET, HEAD and OPTIONS only; a POST, PUT, PATCH or DELETE answered with a
  5xx is raised as `UpstreamError` after one attempt, so a write upstream applied before
  answering 502 is not sent twice (sdk-cashctrl). A 429 is still retried for every
  method. `RetryPolicy(retry_non_idempotent=True)` retries writes again, for an upstream
  that makes a repeated write safe or a source that only reads through POST.
- **Error messages name no host** (ADR-0005 amendment): `error_from_response` writes
  `404 from GET /v1/series: ...`, and `error_from_exception` writes `<host>` where a
  transport failure's text quotes the host. A multi-tenant source's host names the
  tenant; sdk-cashctrl had to mask it in its own `classify`.
- **Binary bodies are refused when recording** (ADR-0013): a body that is not UTF-8 text
  raises `ValueError` ("binary body cannot be scrubbed") and nothing is written, unless
  `Scrub(allow_binary=True)` stores it base64, flagged `body_base64: true` and
  unscrubbed, as 0.1.0 stored every such body (sdk-cashctrl).
- **`EnvKeyAuth.apply(self, request)`**: `apply` reads the key through `self.key()`
  instead of taking it as an argument, which pytest's long tracebacks printed
  (sdk-usda-nass); core's auth classes keep the key in no argument and no local
  variable. A subclass outside core that implements `apply(request, key)` drops the
  parameter; none is known.
- **The pytest plugin keeps the default run offline on its own** (ADR-0013, decision 4
  added by ADR-0015). In every test not marked `live`: a request through httpx's default
  transports or httpcore's pools raises `RuntimeError` naming method and path, from
  `pytest_configure` on, fixtures and collection included (`respx` answers and a
  transport a test passes itself are unaffected; a `respx` pass-through is refused); a
  rate limiter neither waits nor takes a token; every `QuotaPolicy` snapshot is
  forgotten before and after the test, and no policy waits or refuses; every
  `EnvKeyAuth` sends `PLACEHOLDER_KEY`, pinned on the class, and the variables named in
  the ini option `xippios_placeholder_key_envs` hold it. The `httpx` and `httpcore`
  logger levels come back after every test. A test that must reach the network is
  marked `network`; one that asserts a limiter wait, a quota pause or a quota refusal
  is marked `rate_limited`; a module that tests key resolution overrides
  `placeholder_api_key` with a fixture that pins nothing. A source deletes its own
  placeholder fixture, which could not reach one auth object per tenant (sdk-comtrade,
  sdk-cashctrl), and its replays stop waiting behind its limiter (sdk-comtrade,
  sdk-usda-psd).
- **`confirm: bool = False` is enforced at registration** (ADR-0014):
  `register_tasks(..., read_only=False)`, and so `build_server`, refuses with
  `ValueError`, before registering anything, a task without a parameter `confirm`
  annotated `bool` (`Annotated[bool, ...]` counts, `bool | None` does not) defaulting
  to `False`; before, only `assert_write_tools` caught it, in a test (sdk-cashctrl).
- **Write servers listen on loopback only** (ADR-0014): `main` serves a write server
  over `--http` on `127.0.0.1`, `localhost` or `::1` and otherwise exits with status 2,
  unless `--allow-remote` is passed: a write server carries no authentication, so
  beyond loopback a gateway in front of it has to. Read-only servers and stdio are
  unaffected.
- **`mcp_call` runs the server's middleware** (ADR-0014): it calls the tool through an
  in-process `mcp.Client` instead of `MCPServer.call_tool`, so a tenant lock applies
  (sdk-cashctrl). An MCP error, arguments the tool's schema refuses or an unknown tool
  now fail the test with `AssertionError` instead of raising the SDK's `ToolError`, and
  the server must be one `mcp.Client` connects to (an `MCPServer` or a low-level
  `Server`).
- **`classify` shapes retries** (ADR-0015): before a 429 or 5xx is retried, the client
  asks `classify`, also with `raise_on_error=False`. A `RateLimitError` sets the wait
  from its `retry_after`, so a wait beyond `RetryPolicy.backoff_max` is raised after
  one attempt; an `UpstreamError` for a 5xx, or `None`, keeps the status rule; any other
  error, an `AuthError` say, ends the retries. api.data.gov's 429 without `Retry-After`
  was sent three more times into the spent quota (sdk-usda-psd). `send_with_retries`
  takes `classify=`.
- **Result caps count UTF-8 bytes and promise no filter** (ADR-0016): `cap_result`
  measures `max_bytes` in UTF-8 bytes of the compact JSON text, as the convention said,
  not in characters, so non-ASCII text keeps fewer rows; the preview cuts no character.
  The default note ends "narrow the query to see the rest" ("showing {shown} of {total}
  rows (cap: {max_rows} rows or {max_bytes} bytes); ...", for a non-list result "result
  is {n} bytes, over the cap of {max_bytes}; ..."), where it suggested "more filters or
  a shorter date range" that a reference list does not have (sdk-comtrade). A test that
  asserts the old text changes; none is known.
- **Generated enum modules are ASCII-only and pass ruff as rendered** (ADR-0008
  amendment): `render_str_enums` writes each value as `ascii()` does
  (`"C\xf4te d’Ivoire"`, unchanged at runtime), lays out a long member as ruff
  formats it, sorts `__all__` in ruff's order (RUF022), one name per line, and wraps its
  docstrings at 100 columns. It refuses with `ValueError`, naming the argument, key and
  position, never the text, what made a file ruff rejects: a member name over 92
  columns, a key over 75 characters, a `generator`, `fetched` text, key or class name
  it cannot write as printable ASCII (a class name must also be an identifier, no
  keyword, at most 84 characters). A value with nothing to derive a member name from (a
  Greek, Cyrillic or CJK label) is named once through the new `member_names=`. A source
  re-renders its enum file once and commits the one-time diff (sdk-usda-nass's first
  line only); the formatting step after a refresh goes (sdk-comtrade).
- **`Tenants` splits the caller's mistake from the operator's** (ADR-0014): new in this
  release, so it breaks only a source that moves its own tenant registry onto it. An
  undeclared tenant is `InvalidRequestError` (MCP text, HTTP 422), "unknown tenant ...";
  a missing or malformed variable of a declared one is `ConfigError` naming the
  variable, never the value (sdk-cashctrl, on its git pin already).
- **Personal identifiers stay out of task projections** (ADR-0017, conventions §3), a
  rule for sources: documented personal identifiers (CashCtrl's `ssn` and `iban`, and
  what a source judges equivalent) are left out of the projections tasks return unless
  a task fetches them deliberately and says so, and a write task does not echo one in
  `meta.request`; read models stay faithful; fixtures never carry the values, which a
  recording names in `Scrub(secrets=...)` or rewrites with `Scrub(rewrite=...)`.
  Nothing in core changes.

### Added

- **Request hooks and a quota policy** (ADR-0015, sdk-usda-psd).
  `ClientConfig.before_request` runs once per call, after the cache lookup and before
  the rate limiter, with no credentials on the request yet; sync or async, it may wait,
  or raise a taxonomy error and nothing is sent. `ClientConfig.observe` sees every
  response from the wire, retried attempts and raw responses included, a cache hit
  never, before `classify`. `QuotaPolicy` and `QuotaSnapshot` (in `xippios.core` and
  `xippios.core.client`) implement ADR-0010's quota rules on them:
  `QuotaPolicy(...).install(config)` keeps a thread-safe snapshot from the quota
  headers (`limit_header`, `remaining_header`, `reset_header`, each `None` to turn it
  off); a 429, or `remaining` at 0, marks the quota spent until `Retry-After`, the reset
  header or `window` from now, upstream's wait cut to `window` (`window=86400` for a
  daily quota); `spent=` reads any other answer to a spent limit, such as
  sdk-comtrade's 403 "replenished in HH:MM:SS", and `mark_spent()` marks it from code.
  A request into a spent quota waits within `pause_cap` (else `retry.backoff_max`),
  logged once, or raises `RateLimitError` with `retry_after`, saying nothing was sent
  and when the quota is back. `install` refuses a config with a hook of its own, and a
  subclass's `before_request` override is not called through the hook it sets;
  `snapshot()`, `reset()`, and `QuotaSnapshot.describe()`, numbers and times only.
  Replaces sdk-usda-psd's `QuotaAwareClient`, `Quota`, `observe_quota` and
  `quota_pause`, which sdk-usda-esr and sdk-usda-gats would otherwise copy.
- **Keyless calls on a keyed client** (ADR-0015, sdk-comtrade): `auth=` per call on
  `request`, `get` and `get_json` of `AsyncClient` and `Client`, and on `record` and
  `record_sync`, default `httpx.USE_CLIENT_DEFAULT` (its type, `UseClientDefault`, is
  re-exported from `xippios.core.client`). `None` sends the call, retries included,
  without the client's credentials and shares the cache; an `httpx.Auth` replaces them
  for that call and bypasses the cache. sdk-comtrade needed a second client to keep its
  key off public files on its data API's host.
- **Cache provenance and a cache filter** (ADR-0015, sdk-usda-psd): a cache hit carries
  `extensions["xippios_cache_stored_at"]`, the entry's time in epoch seconds, from which
  a task sets `retrieved_at` (conventions §4); `xippios.core.client.decode_json` is
  `get_json`'s decoding for a wrapper that calls `get` to read it.
  `ClientConfig.cache_filter` decides which GETs the cache takes, so one endpoint can be
  cached without a second client. `WIRE_HEADERS` and `strip_wire_headers` name the
  headers dropped from cache entries and fixtures (`content-length`,
  `content-encoding`, `transfer-encoding`, `connection`).
- **A shared pace** (sdk-usda-psd): `limiter=` for `AsyncClient` and `Client` takes a
  `TokenBucket` instead of building one from `config.rate_limit`, and
  `AsyncClient.limiter` returns the bucket in use, so two clients can share one pace.
- **Form bodies and retried writes** (ADR-0011, sdk-cashctrl): `data=` on
  `AsyncClient.request`, `Client.request`, `record` and `record_sync` sends a
  form-encoded body (passing `json=` too raises `ValueError`); `RetryPolicy`'s
  `retry_non_idempotent` (default `False`) retries a 5xx and a transport failure for
  POST, PUT, PATCH and DELETE too.
- **`AsyncClient.derive(retry=..., timeouts=...)`** (sdk-comtrade): a client with only
  those replaced, sharing auth, transport, sleep, rate limiter and cache; `record` and
  `record_sync` take `headers=`, `scrub=`, `retry=` and `timeouts=`, overrides going
  through `derive`.
- **Upstream totals** (ADR-0012, sdk-cashctrl): `ResultMeta.total`, upstream's count of
  the records matching the request, `None` when it reports none. A paginated task sets
  it from upstream's count whether it returns one page or all, never from
  `len(data)`; a negative count is refused; `cap_result` and HTTP responses keep it.
- **Multi-tenant sources** (ADR-0014, sdk-cashctrl). `ResultMeta.tenant`, the tenant by
  name, never a value (`"tenant": null` for a single-tenant source).
  `xippios.core.Tenants(source, *, list_var, fields, reserved=(), validate=None,
  hints=None)` reads the tenants from the environment, names listed in `list_var` and
  values in `<SOURCE>_<NAME>_<FIELD>`, a reserved tenant (`demo`) present when its
  variables are set; `names()`, `require(name)`, `field(name, field)` through
  `validate`, with `hints` text for a refused value, `client_for(name, build)`, one
  client per tenant rebuilt when a value changes, `reset()`.
  `xippios.core.tenants.list_task` is the task behind a `<source>_list_<tenants>` tool,
  names only. `TenantLock(param, value)`, as `tenant_lock=` for `build_server` and
  `register_tasks`, refuses without running the tool a call that names another tenant
  or leaves the tenant out, names the tenant in the instructions and lists it alone; a
  locked server refuses a task whose tenant parameter has a default.
  `main(..., add_options=, apply_options=)` and `build_parser(prog, *, add_options=)`
  put a source's options on core's parser, parsed once, a `XippiosError` from
  `apply_options` exiting with status 2; `is_write_server(server)` serves the loopback
  rule. Generalises sdk-cashctrl's organisation registry and `--org` lock.
- **Per-tool result caps** (ADR-0016, sdk-comtrade, sdk-usda-psd): `caps=` on
  `register_tasks` and `build_server` maps a task function's `__name__`
  (`list_partners`, not the tool name) to a `ResultCap` replacing `cap` for that tool;
  an unknown name is refused before anything is registered. A source keeps it as
  `MCP_CAPS` in `tasks.py`, passed by its `mcp.py` as
  `caps=getattr(tasks, "MCP_CAPS", None)`. `ResultCap(note=...)` replaces the text after
  the counts. The default, 200 rows or 65,536 bytes, cut `comtrade_list_reporters` (255
  rows, 69,011 bytes) and `comtrade_list_partners` (310 rows, 83,270 bytes) at 200
  rows, and `usda_psd_list_countries` (251 rows) before the United States.
- **Integer-id enums** (ADR-0008 amendment, sdk-usda-psd):
  `xippios.core.reference.render_int_enums` renders one `IntEnum` per list of
  `(id, name)` pairs, values the ids in upstream order, so a member equals the id in
  upstream's data; member names come from the names, `_<id>` appended to a name several
  ids share (`TOTAL_DISAPPEARANCE_126`); layout, `member_names=` and refusals as in
  `render_str_enums`, and an id listed twice is refused. `id_name_pairs(records, *,
  id_field, name_field)` builds the pairs, refusing a bad record by field and position,
  never by content. Replaces sdk-usda-psd's `render_id_enums`.
- **Scrubbed recording** (ADR-0013, sdk-cashctrl): `xippios.core.testing.Scrub(host=,
  secrets=, rewrite=, allow_binary=)`, as `scrub=` on `write_fixture`, `record` and
  `fixture_from_response` (now exported from `xippios.core.testing`), removes in memory,
  before the one write, what credential scrubbing does not: the request's host, replaced
  by a placeholder in every form (letter case, IDNA, percent-encoded), named values made
  `REDACTED`, and a text hook for bodies and response headers, for signed URLs. The
  scrubbed exchange is then verified, a JSON body also decoded; a host or value left
  raises `ValueError` saying where, never what, and nothing is written. A placeholder
  that would write what it hides is refused; one that contains the original host
  (`demo.example.test` for `example.test`) is allowed. `Scrub`'s `repr` leaves `secrets`
  out. `FixtureRequest.body`, `body_base64` and `content_type` keep the scrubbed request
  body for a write test to assert; fixtures from 0.1.0 still load. Ports the recorder
  sdk-cashctrl kept locally.
- **Replay by query parameter** (ADR-0013, sdk-comtrade): `match_params=` on
  `mount_fixture`, `replay` and the plugin's `replay_fixture` names recorded query
  parameters a request must carry too, so a count call (`countOnly=true`) and the data
  call on one path are told apart; a name not recorded, or recorded as `REDACTED`, is
  refused. Absence cannot be matched: the more specific fixture is mounted first.
  `ReplayFixture` types the fixture.
- **`xippios.core.testing.sent_urls(route)`** (sdk-usda-nass): the URLs a `respx` route
  received, through `scrub_url`, for a test to compare instead of keeping a request,
  key included, in its frame, which a failing assertion or `pytest -l` prints.
- **Offline-test names** (ADR-0013): `xippios.core.testing.PLACEHOLDER_KEY`
  (`"placeholder-for-fixture-replay"`), the ini option `xippios_placeholder_key_envs`
  and the markers `network` and `rate_limited`, described under Breaking changes.
- **Write-server checks** (sdk-cashctrl): `xippios.core.testing.assert_write_tools(
  write_server, write_tasks, *, source, read_server=None, router=None)` fails a test,
  naming the tool, unless the server is a write server whose tools are exactly the write
  tasks, each with `confirm: bool = False`, and no write tool is on the read server or
  the router. `mcp_call_text(server, name, arguments)` returns a tool's text through
  the same in-process client as `mcp_call`, for asserting an `error:` text.
- **ADR-0009 and ADR-0010** (sdk-usda-psd, sdk-comtrade): one key variable per issuer
  when one key serves several sources (`DATA_GOV_API_KEY`), and the rate-limit policy:
  a fast pace within a documented limit or a stated self-imposed one, longer-window
  quotas spent rather than rationed, the answer to a spent limit interpreted in
  `classify`, no request fired into a spent quota, pauses stated.
- **ADR-0018, core versioning and source adoption**: a source depends on one core minor
  (`xippios-core~=X.Y.0`) and adopts each new minor in one adoption PR against
  conventions §15, the definition of done's "Adoption PR" block. Adoption
  (`chore/template-update*`) and `chore/release-*` PRs are auto-merged after the
  reviewer's `ready`.

### Changed

- **Conventions 1.4 to 1.13**: 1.5 the key variable per issuer and the rate-limit
  policy (§1, §5, §6, §7; ADR-0009, ADR-0010); 1.6 error messages without the host and
  the retry rule (§5, §6; ADR-0011); 1.7 `ResultMeta.total` (§4; ADR-0012); 1.8 form
  bodies, the recorder's rules and the plugin's guarantees (§6, §10; ADR-0013); 1.9
  tenants, the `confirm` check, the loopback rule, the tenant lock and the option hooks
  (§1, §4, §7, §8, §10; ADR-0014); 1.10 the hooks, `QuotaPolicy`, `classify` in retries,
  `auth=` per call and a cache hit's `retrieved_at` (§4, §6, §10; ADR-0015); 1.11 the
  UTF-8 byte cap, per-tool caps in `MCP_CAPS` and a note that promises no filter (§8;
  ADR-0016); 1.12 `IntEnum` for integer ids and ASCII-only, ruff-clean enum modules
  (§3; ADR-0008 amendment); 1.13 `Fetched` as a UTC time with `Z`, HTML for tables a
  pipe table cannot hold, vendor snapshots (§3; ADR-0003 amendment), personal
  identifiers out of task projections (§3, §4; ADR-0017), `InvalidRequestError` also
  for upstream's own refusal mapped in `classify` (§5; ADR-0007 amendment, its
  docstring and the README with it), the one-minor core bound and the 0.x rule (§11,
  §12) and the adoption checklist (§15; ADR-0018). The definition of done gains the
  "Adoption PR" block, and its fixture grep covers the identifiers' values.
- **The edges of the plugin's quota guarantee are documented** (ADR-0013 and ADR-0015,
  amended by ADR-0016): consecutive live tests share every policy's snapshot; a quota
  spent while a fixture of wider scope is set up is forgotten before the body of the
  next test not marked `live`; a `QuotaPolicy` subclass's `before_request` override is
  neither called through `install`'s hook nor neutralised.
- **`main` quiets the request log after `apply_options`**, right before the server
  runs, instead of first thing.
- **The `testing` extra declares `httpcore>=1.0`**, which the plugin patches and which
  only httpx's own dependency provided before.
- **CI runs `uv run pre-commit run --all-files`** after the tests, so the definition of
  done's "Enforced by CI" block holds.

### Fixed

- **A gzip answer replayed from the cache** raised `httpx.DecodingError`: the decoded
  body was stored with `content-encoding`. Entries are stored without wire headers, and
  those a persistent backend kept from 0.1.0 are stripped when replayed (sdk-usda-psd).
- **`parse_retry_after`** let `ValueError` or `OverflowError` out of the retry loop for
  non-ASCII digits (`"²"`) or an HTTP-date with a huge zone offset, and returned an
  infinite `retry_after` for a value too long for a finite float. It reads ASCII digits
  only and returns `None` for what it cannot read.
- **The live gate** skipped every test under a directory named `live`, marked or not;
  it follows the marker now.
- **Taxonomy errors survive `copy.copy`, `copy.deepcopy` and `pickle`**: errors with
  keyword-only arguments raised `TypeError`; `XippiosError.__reduce__` restores every
  attribute (sdk-cashctrl).
- **A client from `AsyncClient.derive` no longer closes a transport it did not create**,
  which closed it under its parent, as `record` did after a recording with `retry=` or
  `timeouts=`.
- **`RateLimit.per_minute`'s docstring**: the pace is the one a source sets within
  upstream's limit, or a self-imposed one (ADR-0010), not upstream's limit.

### Security

- **The MCP servers no longer log request URLs** (ADR-0005). Constructing an
  `MCPServer` configures root logging at `INFO`, and httpx logs every request URL at
  `INFO`, so every `xippios-<source>-mcp` wrote upstream URLs into its MCP client's
  logs: sdk-usda-nass's key, sent as `key=`, and sdk-cashctrl's tenant host.
  `xippios.core.mcp.quiet_request_logging()` sets the `httpx` and `httpcore` loggers to
  `WARNING`; `build_server` calls it after constructing the server and `main` before
  running it. A consumer who wants the log raises the level and runs the server without
  `main`.
- **`.gitignore`** also ignores `.env.*` and `.envrc.*` (sdk-comtrade).
- **The secret scan no longer skips paths containing "swagger"**: detect-secrets'
  `is_swagger_file` filter, which exempted a verbatim upstream Swagger snapshot, is
  dropped (sdk-usda-psd); `.secrets.baseline` and the detect-secrets hook exclude
  `.copier-answers.yml` with sdk-template's pattern, so the template copies both files
  verbatim again (sdk-comtrade).

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
