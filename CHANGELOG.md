# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: only a breaking change bumps the
minor, conventions §12).

## [Unreleased]

### Documentation

- **ADR-0003, amendment 2026-10-28**: fidelity in names is owed to what a consumer sees,
  `meta.endpoint`, the first line of a wrapper's docstring, the snapshot and the
  packaged parameter names; a layer-1 wrapper's module and function carry the upstream
  operation name in snake case, and its fixtures live in a directory named after it; the
  task layer and the MCP tool names are unchanged. **ADR-0018** gets a dated note under
  amendment (e): the gates repository has been `xippios/sdk-gates` since its rename on
  2026-10-27.
- **Conventions 1.22**: §2 names a wrapper module and its function after the upstream
  operation in snake case, from the operation's id in the snapshot (an OpenAPI
  `operationId`, a WADL method id) or else from the path (an `operationId` that restates
  the path, or an opaque one, counting as absent), without a controller prefix every
  operation of the API shares (the FAS APIs' `ESRData_`, `PSDData_`, `GATSData_`), a run
  of capitals one word, a file suffix that tells operations on one path apart kept as
  the last word (the default `.json` dropped) and upstream's spelling kept; the verbatim
  id stays in the wrapper's docstring and in its `endpoint=`, so `meta.endpoint` does
  not change; where operation ids repeat, one module per service holds them; a second
  function on the same endpoint is named after the wrapper with a suffix that says what
  differs, and a helper that calls no endpoint keeps a plain name; an existing source
  renames in one PR of its own right after its core 0.3.0 adoption, never inside it, or,
  already past that adoption, in the first PR of its next version. §10 keeps a wrapper's
  fixtures under `tests/fixtures/<wrapper>/<case>.json`, the case name in lowercase
  snake case with an upstream code written as upstream writes it, and a fixture recorded
  through a task rather than a wrapper lives under the task's name. §15 item 3 makes
  code core removed for its one consumer part of that consumer's adoption, copied from
  the commit core's handover names and listed file by file in the PR description with
  the ADR that moved it; item 8 excepts 1.22's name rule; §15 names `xippios/sdk-gates`
  as the home of the merge classes.
- The definition of done's Adoption PR block and its copy in
  `.github/PULL_REQUEST_TEMPLATE.md`: a line for code copied in from core, the current
  conventions version applied with 1.22's name rule excepted, and `xippios/sdk-gates` as
  the home of the merge classes.
- The review checklist's item 16: a new wrapper's module, function and fixture directory
  follow the name rule, and the verbatim id stays in the first line of its docstring and
  in `endpoint=`.
- **ADR-0025**: Google Mail, sdk-google-mail's decisions. Its read server is held to
  loopback unless `--allow-remote`, checked in its own `apply_options` until core 0.4.0
  carries the `loopback_only` option (row 282, the host its second consumer by the
  session's recommendation, row 296); `RefreshTokenAuth`, an `EnvKeyAuth` whose key is
  the refresh token and whose `auth_flow` renews the access token in memory, is the
  second consumer of a renewing-bearer base for core 0.4.0; a grant's scopes are
  upstream's to enforce, and `classify` maps the refusal to a re-consent `AuthError`;
  the multi-tenant kit (`Tenants`, `list_task`, the binding lock wrapper,
  `assert_write_tools`, the demo-only conftest strip, the serve command) is copied from
  sdk-cashctrl and returns to core in 0.4.0; `get_message` returns a decoded view, a
  projection by MIME role, the faithful tree on the wrapper.
- **ADR-0026**: the host xippios-mcp, a public package that is no source. 0.1.0 runs on
  today's packages, each package's server mounted by path; a group never mixes read and
  write tools, and the tool lists are checked at startup; per-endpoint auth is none or a
  bearer, the bearer the default, with allowed hosts and `transport_security` for a
  reverse proxy; the host applies the loopback rules itself to an endpoint with `auth:
  none` and is `loopback_only`'s second consumer (row 282), the session's recommendation
  (row 296); `isError` is read once core sets it; the `-read` and `-write` names; the
  template's package contract is its 0.2.0 interface; the sources are extras with `>=`
  bounds, an exception to ADR-0021 for the host alone; claude.ai needs an OAuth
  authorization server in front, Pomerium Core the runbook's choice. `CLAUDE.md` lists
  both ADRs.
- **ADR-0014, ADR-0018, ADR-0021, ADR-0022, ADR-0023 and ADR-0024, amended 2026-10-29**:
  ADR-0024's decision 6 is reversed for the kit that returns to core, as its status line
  now says, with a dated line each under ADR-0014 and ADR-0023; ADR-0014's second line
  makes the host the deployment that protects a write server beyond loopback. ADR-0021
  gains the dependency order (a dependent's adoption release follows a dependency's new
  minor right after, a breaking minor only, since a patch reaches the dependent inside
  its bound), the route for a dependency's new surface and a pointer to the host's
  exception; ADR-0022 a reading of 2026-10-29, a load time is never a vintage for a
  source whose only time is a load time; ADR-0018 (g) the version rule, (h) the refresh
  rule and (i) §15's three routes.
- **Conventions 1.23**: the version line applies the conventions to the host
  `xippios-mcp` where ADR-0026 binds it. §1 names `xippios-<source>-mcp-read` and
  `-write` for a source with a write server, lists `google-mail` (the shared namespace
  `google`, Drive later as `google-drive`) with the dated sentence that `mail` is
  Johannes's name for the product upstream calls Gmail, and names
  `GOOGLE_<NAME>_REFRESH_TOKEN`; §3 makes a MIME message's decoded view a projection by
  role; §4 says a load time is never a vintage, for a source whose only time is the time
  upstream loaded the data; §8 names the servers `-read` and `-write` where a write
  server exists, keeps `server.name` the slug, has a host group never mix read and write
  tools, and has an error answer set `isError` from a source's adoption of the core
  release that carries the code (core 0.4.0 as planned, row 283); §12 states the version
  rule (pre-1.0 only a breaking change bumps the minor), the refresh rule (a PR only
  when a record changed or `fetched` goes from a bare date to the full time, otherwise a
  coordination log line the release PR cites) and the dependency order; §13 gains the
  topic `email`; §15 gains three routes, a core release without a template tag, a
  dependency's minor whose new surface the dependent uses and a source frozen on a
  template tag, item 2 not applicable on the first and the third.
- The definition of done's `copier update` line and its last Process line, and their
  copies in `.github/PULL_REQUEST_TEMPLATE.md`: `copier update` not applicable on §15's
  routes (1) and (3); the reference refresh a PR of its own only when a record changed
  or `fetched` went from a bare date to the full time.
- The review checklist's items 12 (§15's item 2 does not apply on §15's routes (1) and
  (3)) and 13 (the refresh rule), and its leak rule, which names `_REFRESH_TOKEN` and
  `_SECRET` beside `_API_KEY`, as `CLAUDE.md`'s now does.
- `docs/handover.md`, "Adopting core 0.3.0", sdk-cashctrl: two dated brackets, its
  template frozen on v0.2.2 (§15's route (3)) and its copy of `client_for`, which closes
  the replaced client.

## [0.3.0] - 2026-10-27

The family review of 2026-10-25 in one minor: its core items C1 to C11 and C13 to C15
(C12 shipped in 0.2.1), each named below with what it did; the code of ADR-0019 (bulk
downloads and non-JSON payloads) and ADR-0022 (packaged answers and release times),
whose rules 0.2.1 shipped as documentation; and ADR-0024, under which sdk-cashctrl
stands alone: tenants, the tenant lock, `assert_write_tools` and the recorder's host
placeholder, encoded matching, JSON verify and `rewrite` leave core for it. What had no
consumer is deleted and the export lists keep what consumers import (ADR-0023); what
sdk-usda-psd, sdk-usda-esr and sdk-usda-gats carried as copies, the api.data.gov gateway
and the packaged lists with their refusals, is core's now. Conventions 1.16 to 1.21 come
with it (0.2.1 shipped 1.15). While core is 0.x a minor keeps no compatibility with the
one before it (conventions §12): a source moves to `xippios-core~=0.3.0` and adopts this
release in one adoption PR before its next release, through conventions §15 with
`/adopt-release` (ADR-0018), and the rules of ADR-0019 and ADR-0022 bind it from that
adoption (conventions, header of 1.21). "Hand-apply for sources" below lists, per
source, what that PR changes by hand; the section "Adopting core 0.3.0" of
[`docs/handover.md`](https://github.com/xippios/sdk-core/blob/main/docs/handover.md), in
the repository and not in the sdist, walks the same items through §15.

The test suite counts 6,830 lines, from 8,072 at 0.2.1 and 7,546 at 0.2.0, by
`git ls-files 'tests/**/*.py' 'tests/*.py' | xargs cat | wc -l`, against the family
review's target of about 4,500 to 5,000. It stays above the target: the deletions with
no consumer took 834 lines and the move to sdk-cashctrl 1,271, while the tests of the
new code added 863 net, 29 for the gateway module after the slimmed quota policy's tests
went, 494 for the downloads, the recorder's truncation and the redaction rule, 310 for
the packaged answers, and 30 for the renderer, the argument check, the payload-free
parse failures, the cache clearing and the live run's quota summary, after 214 lines of
renderer tests went.

### Removed

- **`xippios.core.config` and the `pydantic-settings` dependency** (the family review's
  C1, a settings module with no consumer; ADR-0002, amendment 2026-10-27; ADR-0023,
  decision 5): `SourceSettings` goes; `resolve_api_key`, whose one caller was
  `EnvKeyAuth`, is folded into `xippios.core.client.auth` as a private helper with the
  same behaviour for that caller and the same `ConfigError` message. `pydantic` stays,
  `SecretStr` with it. Conventions 1.16 §7: the environment is read through the
  `EnvKeyAuth` helpers.
- **The sync `Client`** (the family review's C2, a sync client with no consumer;
  ADR-0002 and ADR-0015, amendments 2026-10-27): every source derives its sync task
  functions with `xippios.core.sync`, which stays. `xippios.core.client` no longer
  re-exports `UseClientDefault`, and core no longer imports it from httpx's private
  `httpx._client`: `auth=` keeps its three states on `AsyncClient.request`, `get` and
  `get_json` and on `record` and `record_sync` (the client's credentials by default,
  `None` for none, an `httpx.Auth` to replace them), its default now a sentinel of
  core's own.
- **`AsyncClient.derive`, the `limiter=` argument and the `limiter` property, and
  `retry=` and `timeouts=` on `record` and `record_sync`** (the family review's C3,
  overrides no source calls; ADR-0015, amendment 2026-10-27; asked for by sdk-comtrade):
  the rate limiter is built from `config.rate_limit` alone, and the testing plugin,
  which patches `TokenBucket.acquire`, needs neither. A recording goes through the
  client it is given; one that must not retry a 5xx records through a client whose
  config says `RetryPolicy(max_attempts=1)`. `auth=` per call stays: sdk-comtrade
  records its keyless reference files with it.
- **`paginate_pages` and `paginate_cursor`** (the family review's C4, page paging folded
  into offset paging and cursor paging deleted; no consumer): `paginate_offset` keeps
  its signature, and its docstring shows how a page-numbered endpoint maps the offset to
  its page, `page = first_page + offset // page_size`. sdk-cashctrl, its one consumer,
  is unaffected.
- **26 names leave the export lists** (the family review's C5, the public surface cut to
  what consumers import; ADR-0023, decision 5: an `__init__.py` exports only what
  consumers import), each still importable from the module that defines it:
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot` and `load_csv` from `xippios.core`;
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot`, `WIRE_HEADERS`, `Params`,
  `TokenBucket`, `send_with_retries` and `strip_wire_headers` from
  `xippios.core.client`; `LIVE_ENV`, `PLACEHOLDER_KEY`, `FixtureRequest`,
  `live_enabled`, `mount_fixture`, `replay`, `write_fixture`, `scrub_headers`,
  `scrub_params` and `scrub_url` from `xippios.core.testing`; `is_write_server`,
  `quiet_request_logging` and `register_tasks` from `xippios.core.mcp`;
  `PROBLEM_MEDIA_TYPE`, `STATUS_BY_ERROR`, `install_error_handlers` and
  `problem_response` from `xippios.core.http`. With the six deleted names above, the
  five lists go from 113 entries (98 names) to 81 (69 names); with the names added below
  and the three that move out, 88 (74) at 0.3.0. No source imports a removed name from a
  package.
- **`QuotaPolicy`'s `reset_header`, with the reset header's three formats** (the family
  review's C6, a slimmer `QuotaPolicy`; ADR-0015, amendment 2026-10-27; no source sets
  it, and api.data.gov sends no reset header): delay-seconds, epoch seconds and an
  HTTP-date are no longer read. A spent quota is back after a 429's `Retry-After`, the
  seconds `spent` names, or `window`, each cut to `window`.
- **`QuotaPolicy.mark_spent`** (the family review's C6; no caller): `spent=` stays, for
  an upstream that answers a spent limit with something other than a 429.
- **The per-config cap and the hook check of `QuotaPolicy.install`** (the family
  review's C6): `install` no longer binds the pause to each config's `retry.backoff_max`
  through a hook of its own, nor refuses with `ValueError` a config that has a
  `before_request` or `observe` hook of its own; `pause_cap=None` and the 30 s of a
  `before_request` called directly go with them (Changed, breaking, below).
- **The recorder's substring credential pattern** (the family review's C10, one
  redaction rule; ADR-0005 and ADR-0019, amendments 2026-10-27; found in the Eurostat
  design round, ADR-0019's context: its SDMX series `key` would have been redacted):
  `scrub_params`, `scrub_url` and every recording no longer redact a query parameter
  whose name merely contains `key`, `pass`, `auth`, `sig`, `cred`, `token` or `secret`
  (`keyword`, `passport`, `author`, `design`); they read the whole-word rule of
  `xippios.core.redaction` (Changed, breaking, below).
- **`is_credential_key` and `redact_credentials` leave `xippios.core.models`** (the
  family review's C10; ADR-0023, decision 5; no consumer): the rule's functions live in
  `xippios.core.redaction`, as `is_credential_name` and `redact_credentials`.
  `xippios.core.models.REDACTED` stays.
- **`render_str_enums` and `render_int_enums`, with the renderers' ruff layout** (the
  family review's C7, a renderer that leaves the layout to ruff; ADR-0008, amendment
  2026-10-27; ADR-0023, decision 5; found by sdk-comtrade and by sdk-template):
  `render_enums` (Added, below) replaces both. The quote choice, the parenthesised and
  split long values, `__all__` sorted as RUF022 sorts it, the wrapped docstrings and the
  refusal of a member name too long for a line go: the refresh script's `ruff format`
  and `ruff check --fix` do that work. Every source re-renders `enums.py` at its
  adoption through the template's script.
- **The testing plugin's patches of httpx's transports** (the family review's C11, the
  network guard on the connection pools only; ADR-0013, amendment 2026-10-27):
  `httpx.HTTPTransport.handle_request` and
  `httpx.AsyncHTTPTransport.handle_async_request` are no longer patched (Changed,
  below).
- **`Tenants` and `list_task` move to sdk-cashctrl** (the family review's C8, the
  multi-tenant pieces with one consumer out of core; ADR-0024, superseding ADR-0014's
  decisions 1 to 4, 6 and 11; Johannes's decision of 2026-10-25 that sdk-cashctrl stands
  alone; found by sdk-cashctrl): `xippios.core.tenants` is deleted and `Tenants` leaves
  `xippios.core`'s export list. The last commit that holds the code is
  `cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff` on `main`, named in `docs/handover.md`'s
  "Adopting core 0.3.0" section:
  `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/tenants.py`,
  tested in `tests/test_tenants.py`. `ResultMeta.tenant` stays.
- **`TenantLock` moves to sdk-cashctrl** (the family review's C8; ADR-0024, superseding
  ADR-0014's decision 7; found by sdk-cashctrl): `build_server` and `register_tasks`
  lose `tenant_lock=`, and the lock's middleware, the refusal of a tenant parameter with
  a default on a locked server, the instructions sentence and the narrowing of a
  `list_task` tool go with it. At that commit: `src/xippios/core/mcp/server.py`
  (`TenantLock`, `_lock_middleware`, `_check_lock`, `_defaulted`, `_declares`,
  `_refusal`, `_lock_sentence`, `_only_the_locked_tenant`, the `narrow` argument of
  `_as_tool`), tested in `tests/mcp/test_lock.py`. `TenantLock` leaves
  `xippios.core.mcp`'s export list. The `confirm` check, `is_write_server`, `main`'s
  loopback rule and option hooks, and `mcp_call` and `mcp_call_text` stay.
- **`assert_write_tools` moves to sdk-cashctrl** (the family review's C8; ADR-0024; the
  write checks found by sdk-cashctrl): with `_tool_names` and `_serves`, at that commit
  in `src/xippios/core/testing/adapters.py`, tested in `tests/testing/test_adapters.py`;
  it leaves `xippios.core.testing`'s export list, and the family check's write-server
  test, which called it, goes (Changed, below).
- **`Scrub(host=...)`, `Scrub(rewrite=...)`, the percent-encoded matching of secrets and
  the JSON-decoded verify move to sdk-cashctrl** (the family review's C9, the recorder's
  extras with one consumer out of core; ADR-0024; ADR-0023, decision 3 (b): a recorder's
  pre-write hooks are the source's; found by sdk-cashctrl): `host` with its checks and
  the placeholder it wrote into the URL, the headers and the bodies, `rewrite`,
  `_plain_or_encoded`, the host forms, `_json_strings` and `_strings`. At that commit:
  `src/xippios/core/testing/scrub.py`, tested in `tests/testing/test_scrub.py`,
  `tests/testing/test_fixtures.py` and `tests/testing/test_record_replay.py`. With the
  three names above, the five export lists hold 41 names in `xippios.core`, 18 in
  `xippios.core.client`, 7 in `xippios.core.mcp`, 3 in `xippios.core.http` and 19 in
  `xippios.core.testing`: 88 entries, 74 names.

### Changed (breaking)

- **`pause_cap` is the one bound of a quota pause** (the family review's C6; ADR-0010,
  decision 4, and ADR-0015, amended 2026-10-27): 30.0 by default, the default
  `backoff_max`, whether `before_request` runs as the hook or is called directly; a
  config's `retry.backoff_max` bounds the retries alone.
- **`QuotaPolicy.install(config)` sets the policy's own hooks** (the family review's
  C6): `dataclasses.replace(config, before_request=policy.before_request,
  observe=policy.observe)`, reading nothing else from the config. Hooks the config had
  are replaced; a source that needs hooks of its own as well composes them itself.
  Installing again changes nothing. Since the hook is `before_request` itself, a
  subclass's override is called through it; the testing plugin still turns off the pause
  step alone.
- **`key` is a credential only where a `QueryKeyAuth` sends it** (the family review's
  C10; ADR-0019, decision 6, amended 2026-10-27; found in the Eurostat design round,
  ADR-0019's context). The one rule of `xippios.core.redaction` names credentials by
  whole words between `_`, `-` or the ends: `api_key` (`apikey`, `api-key`), `token`,
  `secret`, `password`, `passwd`, `pwd`, `auth`, `authorization`, `sig`, `signature`,
  `credential`, `credentials`, and no bare `key`; `sig` and `pwd` are new, for
  pre-signed file links (an Azure SAS carries `sig=`). `QueryKeyAuth(param, ...)`
  registers `param` when it is built, a credential from then on in the whole process, in
  any letter case. USDA NASS's `QueryKeyAuth("key", ...)` keeps its `key` redacted;
  Eurostat, keyless, keeps its SDMX `key` as data; a `sort_key` is data everywhere. A
  process that imports both redacts `key` for both.
- **One rule for the envelope, the recorder and replay** (the family review's C10;
  ADR-0005, amended 2026-10-27): `ResultMeta.request`, the recorder's scrub,
  `sent_urls`, `sent_query`, `recorded_query` and `mount_fixture` read
  `xippios.core.redaction`; `scrub_params`, `scrub_url` and `scrub_headers` move there
  (the header list unchanged) and stay importable from `xippios.core.testing.scrub`;
  `models.REDACTED`, `testing.REDACTED` and `redaction.REDACTED` are one object.
  `recorded_query` reads the recorded URL through `scrub_url` again, and `match_params`
  naming a credential is refused by name ("names a credential, which a fixture holds as
  REDACTED") before its value is looked at.
- **`ResultMeta` refuses a field it does not define** (ADR-0012, amendment 2026-10-27;
  found by sdk-cashctrl): `extra="forbid"`, so a misspelt `totl=3` raises pydantic's
  `ValidationError` ("Extra inputs are not permitted") instead of losing the count
  without a word. The model is otherwise as it was, not frozen.
- **`meta.request` omits a parameter left `None`** (ADR-0022, rule 3; found by
  sdk-usda-psd): `ResultMeta` drops a top-level `None` at construction, before the
  credential rule, so a task passes its parameters as they are and a credential left
  `None` is not recorded as sent; a `None` inside a nested mapping is kept as given.
- **Parse failures print no payload** (conventions §5: errors never leak tracebacks;
  found by sdk-cashctrl in a live test's traceback): `parse`, `UpstreamModel.project`,
  `load_table`, `PackagedList.load`, `decode_json`, `decode_text` and `decode_csv` build
  their `ValidationError` and raise it `from None` through a private helper whose frame
  holds the error alone. The text folds in the cause's location, error type and message
  (`example get_thing: 1 validation error(s); first at 1.value (float_parsing): Input
  should be a valid number, ...`), json's message and position, the decoder's reason or
  the csv module's message, never an input value; the payload stays on `raw`, and the
  error's `repr` is its message. So neither pydantic's chained error, whose text quoted
  every failing value, nor the raising frame's arguments reach a printed traceback:
  under pytest's default `--tb=auto` the function that holds the payload is a middle
  entry, printed short. `project`, `load_table` and `PackagedList.load` raised
  pydantic's own `ValidationError` before and raise the taxonomy's now. The template's
  `--tb=short` on the live run stays as a second guard.
- **Core's recording verify is plain** (the family review's C9; Johannes's decision of
  2026-10-27; ADR-0024, decision 3; ADR-0005, amended 2026-10-27): `Scrub(secrets=...)`
  replaces each value as given, the longest first, in the letter case given, and before
  anything is kept or written the verify searches the URL, every header value and both
  text bodies for each value as given. A hit refuses the exchange with "the scrubbed
  fixture still holds a secret value in the <location>; it is refused before anything is
  written", the location `request URL` (it read `url`), `request header '<name>'`,
  `response header '<name>'`, `request body` or `response body`, never the value. A
  value percent-encoded or behind a JSON escape is no longer found by core, and header
  names are scrubbed but no longer searched.
- **The binary-body refusal is neutral** (ADR-0024, decision 5; found by sdk-cashctrl):
  "a binary body cannot be scrubbed; the recording is refused unless
  Scrub(allow_binary=True) stores it base64, flagged", which no longer tells every
  caller to pass the flag.
- **Arguments a tool's schema refuses are answered in conventions §8's form** (ADR-0014,
  amendment 2026-10-27; found by sdk-usda-esr): `register_tasks`, and `build_server`
  through it, installs one middleware per server that validates a call's arguments with
  the argument model the `mcp` SDK builds for the tool and answers a refusal before the
  tool runs as `error: InvalidRequestError: <argument>: <message>`, the first error with
  the count when there are several. The SDK answered an MCP error, `Error executing tool
  ...` with pydantic's text, its URL and the input value. The SDK runs
  `server.middleware` outermost-first, so a source's own middleware appended later runs
  inside the check, and one placed ahead of it in the list runs first; task errors keep
  their path. A family invariant (ADR-0023, decision 3 (a)).
- **A capped list says where to resume** (ADR-0016, amendment 2026-10-27; found by
  sdk-cashctrl): `cap_result` ends the note of a cut list whose `meta.request` records
  an integer `start`, an offset-paged task's, with `; resume with start=<start +
  shown>`; every other note is unchanged.

### Added

- **`BODY_LIMIT`, `error_from_response` and `parse_retry_after` exported from
  `xippios.core`** (the family review's C5; ADR-0023, decision 5: a name keeps or gains
  its export when a consumer imports it): sdk-cashctrl imports the first two from
  `xippios.core.errors`, and sdk-usda-psd, then sdk-usda-esr and sdk-usda-gats, the
  third. The module path keeps working.
- **`xippios.core.data_gov`, the api.data.gov gateway module** (the family review's C14,
  one module for the gateway three sources copied; ADR-0009, amendment 2026-10-27;
  ADR-0023; found by sdk-usda-psd and by sdk-usda-gats). `Gateway(source)` gives `auth`,
  a `HeaderKeyAuth` on `X-Api-Key` from `DATA_GOV_API_KEY` with the source's slug for
  its `ConfigError`; `classify(response)`, the gateway's `API_KEY_*` answer to a 401 or
  403 as `AuthError`, its 429 as `RateLimitError` and its `NOT_FOUND` 404 as
  `NotFoundError`, in the source's name with the gateway's URL written `<host>`, and
  `None` for every other answer; and `install(config)`, the hooks of `Gateway.policy`,
  one `QuotaPolicy` per process on `x-ratelimit-limit` and `x-ratelimit-remaining` with
  a one-hour window, which every source in the process shares. The policy's refusal
  before sending speaks for `api.data.gov` and names the variable. `API_KEY_ENV`,
  `KEY_HEADER`, `WINDOW`, `LIMIT_HEADER` and `REMAINING_HEADER` come with it. Consumers:
  sdk-usda-psd, sdk-usda-esr and sdk-usda-gats, which carry the same code as copies
  today, and the template's api.data.gov gateway answer of v0.3.0. Imported from its
  module; `xippios.core` does not re-export it.
- **`AsyncClient.download(url, dest, *, auth=)` and `Downloaded`** (the family review's
  C15, bulk downloads and non-JSON payloads; ADR-0019, decision 1; found by
  sdk-usda-nass): a GET through the client's pool, streamed to a temporary file beside
  `dest` and renamed when complete, removed on any failure, never cached and never held
  in memory. `before_request`, the limiter, `observe` and `classify` (both see a
  success's status and headers only; its body goes to the file unread) and the retry
  rule of ADR-0011 apply as for `get()`, a retry restarting the file; an error answer is
  read up to `BODY_LIMIT` bytes and raised through the taxonomy; a 1xx or 3xx raises
  `UpstreamError`, since redirects are not followed; a `dest` that is a directory, or
  whose directory does not exist, is refused with `ValueError` before anything is sent.
  `Downloaded` carries `path`, `bytes`, `content_type`, `filename` (from
  `Content-Disposition`), `etag`, `last_modified` (the header's text) and
  `retrieved_at`; exported from `xippios.core` and `xippios.core.client`. Consumers,
  named by ADR-0019: sdk-usda-esmis, sdk-usda-wasde, sdk-usda-nass's bulk datasets,
  sdk-eurostat and sdk-faostat.
- **`decode_text` and `decode_csv`** (the family review's C15; ADR-0019, decision 2,
  amended 2026-10-27; found by sdk-usda-nass), exported from `xippios.core.client`
  beside `decode_json`: the text in the `Content-Type` charset, UTF-8 by default, a byte
  order mark stripped; and `decode_csv(data, *, delimiter=",", source=None)`,
  `csv.DictReader` rows from a downloaded file (a `Path` or `str`) or a response,
  headers as upstream prints them, a generator that reads a file row by row and closes
  it when it ends.
- **`ClientConfig.cache_max_bytes`** (the family review's C15; ADR-0019, decision 3;
  found by sdk-usda-nass): 8 MiB by default; a larger body is returned and not stored; a
  value below 1 is refused.
- **`BULK_TASKS`** (the family review's C15; ADR-0019, decision 4; found by
  sdk-usda-nass): `register_tasks` and `router_from_tasks` skip a task whose defining
  module names it in `BULK_TASKS`, so the rendered adapters may pass `tasks.__all__`
  whole, and the family check's "`tasks.__all__` minus `BULK_TASKS`" holds for them; a
  cap in `caps` for a bulk task is refused as naming no task, and the refusal now says
  that a task in `BULK_TASKS` is no tool.
- **The recorder's `max_bytes=`** on `record`, `record_sync` and `fixture_from_response`
  (the family review's C15; ADR-0019, decision 5, amended 2026-10-27; found by
  sdk-usda-gats, and the family's finding that a cut-off JSON object, a JSON-stat cube,
  does not decode on replay): a JSON array is cut at an element boundary of its original
  text, its numbers and spacing as upstream wrote them; a text is cut at a UTF-8
  character boundary, never inside a secret value; a JSON object, a body declared JSON
  that does not parse, an array whose first element alone does not fit, a cut that keeps
  nothing, XML, ZIP, XLSX, gzip, XLS and a body that is not UTF-8 text are refused with
  the reason. `max_bytes` bounds the body, not the fixture file, which escapes the body
  as a JSON string. A cut response is marked `truncated` with `original_bytes`, `sha256`
  (of the whole body, before the scrub) and, for an array, `original_count`, new
  optional fields of `FixtureResponse`; a fixture without a cut is written without them,
  so every existing fixture loads and re-records unchanged. Replay serves the body as
  recorded.
- **`xippios.core.redaction`** (the family review's C10; ADR-0019, decision 6; ADR-0023,
  decision 3 (b), credential redaction; found in the Eurostat design round): the one
  `REDACTED`, `is_credential_name`, `register_credential_name`, `redact_credentials` and
  the three `scrub_*` functions, at the bottom of the package. Imported from its module;
  not re-exported.
- **`ResultMeta.published_at_naive`** (ADR-0022, rule 2; found by sdk-usda-gats): a
  naive `published_at`, a release time upstream printed without a zone (FAS:
  `2026-10-06T08:00:00`), is kept as given with the flag set; without the flag it is
  refused as before, and the flag with an aware `published_at` or with none is refused
  too. The HTTP envelope and the MCP text carry it. A family invariant (ADR-0023,
  decision 3 (a)); sdk-usda-esr and sdk-usda-gats fill it at adoption.
- **`PackagedList`** (the family review's C13, one packaged-list class for the sources'
  copies; ADR-0022, rule 1 and amendment 2026-10-27; found by sdk-usda-psd, by
  sdk-usda-esr in the template's scaffold, and by sdk-usda-gats), in
  `xippios.core.reference` and exported from `xippios.core`: one frozen model,
  `PackagedList(param, endpoint, fetched, records)` with an optional free-text `note`,
  for a list fetched from one upstream operation, upstream's records under upstream's
  field names, a list of values being records of one field named by the upstream
  parameter; any other key of a file is refused. `PackagedList.load(package, name)`
  reads `reference/<name>.json` through `load_json` (`name` with or without `.json`);
  `.meta(source, *, request, vintage, published_at, published_at_naive)` builds rule 1's
  `ResultMeta` (`endpoint` the list's operation, `retrieved_at` its `fetched`, `vintage`
  only what the caller passes, `total` `None`); `.parse(model, *, source)` validates the
  records through `parse`; `.write(path)` writes the file (`{"param", "endpoint",
  "fetched", "records"}` and `note` when it is set, indented, non-ASCII text kept,
  `fetched` to the second as `...Z`) for the refresh scripts. Consumers: sdk-usda-psd,
  sdk-usda-esr and sdk-usda-gats, which carry copies, sdk-usda-nass and sdk-comtrade,
  whose value files and tables it reads after their adoption, and the template's refresh
  script.
- **`matches` and `closest`** (the family review's C13; found by sdk-usda-psd and
  sdk-usda-gats), in `xippios.core.reference` and exported from `xippios.core`:
  `matches(search, *fields)`, the `search` filter of the `list_*` tasks (`None` matches
  everything; otherwise a case-folded substring test of each field that is not `None`,
  as text, never joined), and `closest(value, codes, *, n=3)`, sdk-usda-psd's two
  `difflib` passes, by code and then by name, at most `n` `(code, name)` pairs.
  Consumers: sdk-usda-psd, sdk-usda-esr, sdk-usda-gats and sdk-comtrade (`matches`);
  sdk-usda-psd and sdk-usda-gats, the latter behind its three-letter pass (`closest`;
  sdk-usda-esr's is integer-nearest and stays its own).
- **`UnknownCode`** (ADR-0022, amendment 2026-10-27; found by sdk-usda-gats), an
  `InvalidRequestError` in `xippios.core.errors`, exported from `xippios.core`:
  `UnknownCode(param, value, *, list_name, fetched, closest=(), hint=None, reason=None,
  source=None)` refuses a code a packaged list lacks with the copies' common message:
  the value, the parameter, the list and the day it was fetched, "Did you mean A (name),
  B (name)?" from `closest` unless `hint` is given, the `reason`, and that a code
  upstream added since needs a refresh (`/refresh-reference-data`). Attributes `param`,
  `value`, `list_name`, `fetched`, `closest`. No strategy protocol: a source passes the
  closest codes it found. Consumers: sdk-usda-psd, sdk-usda-esr and sdk-usda-gats.
- **`AsyncClient.get_answer(path, *, params, headers, auth)` and `Answer`** (ADR-0015,
  decision 5, amended 2026-10-27; found by sdk-usda-gats): the payload as `get_json`
  decodes it and `retrieved_at`, a cache hit's stored time from
  `xippios_cache_stored_at` as an aware UTC datetime, else the time the answer arrived.
  `Answer(payload, retrieved_at)` is a frozen dataclass, exported from `xippios.core`
  and `xippios.core.client`; `get_json` stays. Consumers: sdk-usda-gats's five cached
  wrappers and sdk-comtrade's cached `list_commodities`.
- **`UpstreamModel.dump_upstream()`** (ADR-0003; found by sdk-template): a record as
  `model_dump(mode="json")` under upstream's field names, the `serialization_alias`,
  else a string `validation_alias`, else the first choice of an `AliasChoices`, else the
  field name; a nested `UpstreamModel`, alone or in a list, likewise; a computed field,
  which is the package's, left out. Consumers: the refresh scripts of sdk-usda-psd,
  sdk-usda-esr, sdk-usda-gats and the template (`upstream_record`), and sdk-comtrade's
  tables (`_columns`).
- **`render_enums(lists, *, fetched, class_names=None, member_names=None,
  generator=...)`** (the family review's C7; ADR-0008, amendment 2026-10-27; found by
  sdk-template and, for the class docstrings, by sdk-usda-gats), in
  `xippios.core.reference`: one module of `StrEnum` and `IntEnum` classes, the kind
  inferred per list, a list of strings or of `(id, name)` pairs as `id_name_pairs`
  builds them; `fetched` one date for the module or one per list; each class docstring
  one line, "Values of ``<key>`` (fetched <date>).", which an MCP tool's input schema
  shows the agent. The output is plain ASCII: values as `ascii()` writes them, one
  member per line, `__all__` in the order of the lists, `# noqa: E501` on a line over
  100 columns, `# noqa: E741` on a member named `I`, `O` or `l`. Refused with
  `ValueError`: an empty list or one that mixes kinds (the message names what it found,
  by type); a key, class name, date or generator text that is not printable ASCII; a
  class name over 84 characters, named `IntEnum` or `StrEnum`, or shared by two lists; a
  repeated id; a member name with nothing to derive it from, or one that collides or an
  enum cannot take; and a key of `fetched`, `class_names` or `member_names` that `lists`
  does not hold. Consumers: every source, through the template's refresh script
  (ADR-0023, decision 1).
- **Every `MemoryCache` cleared around each offline test** (ADR-0013, amendment
  2026-10-27; found by sdk-usda-gats; sdk-comtrade carries the same fixture): a
  `MemoryCache` adds itself to a module-level weak set when it is built, and the
  plugin's autouse fixture clears every registered cache before and after each test not
  marked `live`, next to the quota reset. A `CacheBackend` of the source's own is not
  cleared; the `MemoryCache`s one holds are.
- **The quota a live run left** (ADR-0013, amendment 2026-10-27; found by sdk-usda-esr):
  after each `live` test that ran the plugin keeps every quota policy's source and
  `snapshot().describe()`, and the terminal summary prints one line per policy with a
  reading, `quota after the live run: <source>: <describe()>`: times, counts and the
  source, never a key, a host or a query.

### Changed

- **The api.data.gov 429's wait comes from the quota snapshot** (the family review's
  C14, the gateway module; found by sdk-usda-psd): the gateway's `classify` counts to
  `Gateway.policy.snapshot()`'s `resumes_at` on the policy's clock, since `observe` ran
  before it, instead of restating "`Retry-After`, else the window" as the three copies
  did; no `QuotaPolicy.wait_for` is added. Its message names the gateway's allowance,
  that every package using the key shares it, and the quota as the snapshot reports it,
  or the wait in seconds where no snapshot shows it spent, and no longer says what was
  retried: the retry loop's bound decides that.
- **`ResultCap` is defined in `xippios.core.models` and exported from `xippios.core`**
  (the family review's C5; the per-tool cap of ADR-0016; found by sdk-usda-psd): a
  source's `tasks.py` declares its `MCP_CAPS` without the `mcp` extra and without the
  `ImportError` guard around the import. `xippios.core.mcp` keeps re-exporting it, and
  `cap_result` stays there.
- **A packaged answer's `retrieved_at` is the list's fetch time, read from `fetched`**
  (ADR-0022, rule 1 and amendment 2026-10-27; found by sdk-usda-psd):
  `PackagedList.fetched` is a timezone-aware UTC time, and a file whose `fetched` is a
  bare date, every packaged file so far, reads as 00:00 UTC of that day, the start of
  the day the refresh scripts truncated the time to; a source's next refresh writes the
  full time. The sources answered with the time of the call and put the fetch date into
  `vintage`, which now holds an upstream release identifier only.
- **The network guard sits on httpcore's connection pools only** (the family review's
  C11; ADR-0013, amendment 2026-10-27): `httpcore.ConnectionPool.handle_request` and
  `httpcore.AsyncConnectionPool.handle_async_request`, which every default httpx
  transport sends through, proxies included. The refusal, its message and its edges are
  unchanged: respx answers a mocked request, a route that passes through meets the
  refusal, and a transport a test passes itself bypasses it. The plugin's docstrings
  name the decision of ADR-0013 they implement instead of restating it, and the
  `rate_limited` marker's text names the quota pause it keeps as well.
- **The family check has ten tests** (the family review's C8; Johannes's decision of
  2026-10-27; ADR-0024): `test_family_write_server_serves_the_write_tasks` is gone, and
  a source's write server is its own to test. The write tasks of `tasks_write` stay in
  `test_family_tasks_return_results`, `test_family_tasks_carry_agent_docstrings` and the
  README status table.
- **`.claude/settings.json`** (ADR-0018, amendment (e); found by sdk-template, which
  copies the file verbatim): `gh pr merge --auto` is allowed and `gh pr merge` is no
  longer denied, as in the workspace root's settings. A deny shadows every allow, so the
  session's one merge action, enabling auto-merge (ADR-0018, amendment (e)), was refused
  here.
- **`gates.yml` calls the gates repository under its new name `xippios/sdk-gates`**
  (ADR-0018, amendment (e): the merge classes it calls for; the repository was renamed
  from `.github` on 2026-10-27).

### Documentation

- **ADR-0002, amendment 2026-10-27**: `pydantic-settings` and `xippios.core.config` are
  gone, keys are read by the `EnvKeyAuth` helpers, and the sync facade is
  `xippios.core.sync`.
- **ADR-0015, amended 2026-10-27**: the sync `Client`, `UseClientDefault` and `derive`
  leave decisions 2 and 4 and the consequences; `QuotaSnapshot` is importable from
  `xippios.core.client.quota`. **ADR-0004** and **ADR-0009** get a line each for the
  deleted `config` module and `resolve_api_key`, and **ADR-0012** one for the
  paginators, of which `paginate_offset` remains.
- **Conventions 1.16**: §7 reads the environment through the `EnvKeyAuth` helpers.
- **ADR-0009, ADR-0010 and ADR-0015, amended 2026-10-27**: the gateway module as the
  code side of one key per issuer; the quota pause bounded by `pause_cap`; the removals
  of the family review's C6, `install`'s contract and the 429's wait read from the
  snapshot. **ADR-0016** gets a dated line: a subclass's override of `before_request` is
  called through the hook `install` sets.
- **Conventions 1.17**: §6 bounds the quota pause by the policy's `pause_cap` and says
  that `install` replaces the config's hooks; §7 names `xippios.core.data_gov` for the
  sources behind api.data.gov.
- **ADR-0019, amendment 2026-10-27**: decision 1's `auth=` default is the client's own
  credentials, and what differs from `get()` (the hooks see a success's headers only, a
  1xx or 3xx raises, `dest` refused before sending); decision 2's `decode_csv(data,
  ...)`; decision 5's one `max_bytes=` for texts and arrays, the cut at element
  boundaries, the JSON-object refusal and the XML reason ("a cut-off XML document is not
  well-formed"); decision 6's mechanism and the words `sig` and `pwd`. **ADR-0005** (the
  list without a bare `key`, no second pattern for fixtures), **ADR-0013** (the guard
  covers `download`; replay of a cut body) and **ADR-0004** (`redaction` and `_tasks` at
  the bottom, `client/download.py`) get a dated line each.
- **Conventions 1.18**: §4 states the one rule, every word of it, and when `key` is a
  credential; §6 that a download's hooks see a success's headers only, that a 1xx or 3xx
  raises, and `decode_csv`'s signature; §10 the scrub's rule, the JSON-object refusal,
  the XML reason, the cut at element boundaries, `original_count`, and that `max_bytes`
  bounds the body, not the file.
- **ADR-0022, amendment 2026-10-27**: the five decisions on the code (the `fetched` time
  and its bare-date reading; one `PackagedList` with value lists as one-field records
  and a URL path as `endpoint`; the helpers; `get_answer`; frozen series), the flag's
  refusals, the order of the `None` rule and the credential rule, and three more from
  the review of the code: the period series, found by sdk-usda-gats (the ceiling is the
  most periods one call fetches; an unreleased period is skipped where upstream's empty
  answer can be told from data, else the range is refused), its refusal as
  `NotFoundError` naming the latest released period, and the packaged file's optional
  `note` with every other key refused. **ADR-0015** (decision 5's `get_answer`),
  **ADR-0012** (`ResultMeta` refuses unknown fields) and **ADR-0004** (`reference` above
  `models`) get a dated line each.
- **Conventions 1.19**: §3 the packaged-list file, `reference/<name>.json` with its
  optional `note`; §4 the refusal of unknown fields, `get_answer` for a hit's
  `retrieved_at`, the flag's refusals, `PackagedList`'s methods and the bare-date
  reading, `matches`, the frozen series and the period series (both found by
  sdk-usda-gats); §5 `UnknownCode`, in the taxonomy tree under `InvalidRequestError`; §6
  `get_answer`. The preamble lists these among the rules that bind a source from its
  0.3.0 adoption.
- **ADR-0008, amended 2026-10-27**: `render_enums` replaces the two renderers, the plain
  output and the refresh script's ruff step replace the amendment of 2026-10-24's
  layout. **ADR-0013** (the guard on the pools, the cache clearing, the live summary),
  **ADR-0014** (the argument middleware), **ADR-0016** (the resume hint) and
  **ADR-0018** (amendment (f), the workflow hardening) get a dated line each.
- **Conventions 1.20**: §3 `render_enums` and the module committed as formatted; §8 what
  an enum's class docstring holds (found by sdk-usda-gats), the resume hint and refused
  arguments as `InvalidRequestError` text; §10 the guard on the pools, the cache
  clearing and the live summary; §13 the workflow hardening (the family's own finding):
  actions pinned by SHA, no persisted credentials but the `tag` job's, least
  permissions, no `secrets: inherit`, the gates called at `@main`; §15 item 6 re-renders
  through the template's script. The header binds the renderer rule from the 0.3.0
  adoption.
- `publish.yml`'s `tag` job says in a comment that its checkout keeps its credentials,
  since it pushes the tag with the token (conventions §13; ADR-0018, amendment (f)).
- The definition of done's adoption line and its copy in
  `.github/PULL_REQUEST_TEMPLATE.md`: generated enum files are committed as formatted,
  after the refresh script's `ruff format && ruff check --fix`, as conventions §15 item
  6 says (ADR-0008, amendment 2026-10-27).
- **ADR-0024**: sdk-cashctrl stands alone; tenants, the tenant lock,
  `assert_write_tools` and the recorder's host placeholder, encoded matching, JSON
  verify and `rewrite` leave core, while `ResultMeta.tenant` (a family invariant,
  ADR-0023, decision 3 (a)), the `confirm` check and the loopback rule (conventions §8,
  C8) and the plain verify (secret scrubbing, decision 3 (b)) stay. **ADR-0014** is
  superseded in part (decisions 1 to 4, 6, 7 and 11, and two consequences: the
  template's `multi_tenant` question and `tests/mcp/test_lock.py` as the middleware
  API's guard; 5, 8, 9 and 10 stand); **ADR-0005** (the verify's scope), **ADR-0013**
  (the placeholder host, the verify's forms and the family check's write-server test),
  **ADR-0017** (`rewrite`), **ADR-0019** (the text cut spares secrets only) and
  **ADR-0023** (which of "the write checks" left) get a dated line each. The template's
  `multi_tenant` question ADR-0014 announced (asked for by sdk-cashctrl) is not built.
- **Conventions 1.21**: §1 names a multi-tenant source's key variables as its own
  scheme; §3 makes the rewrite by key the source's recorder step; §7 has a multi-tenant
  source carry its tenant registry and keep `ResultMeta.tenant`; §8 loses the tenant
  list and the lock and keeps the write server's rules; §10 loses the placeholder host
  and the JSON-aware verify, keeps the plain verify and `allow_binary`, and the family
  check no longer names the write server.

### Hand-apply for sources

What a source's adoption of 0.3.0 changes by hand because of the changes above, per
source: every source first, then each by name. Of the names this release deletes, the
sources import the two renderers, in their refresh scripts; sdk-cashctrl imports the
names that move to it. The tests of the api.data.gov sources read a deleted attribute
and texts that change, and every source's tests meet the narrower credential rule.
`docs/handover.md`, "Adopting core 0.3.0", walks the same items through conventions §15.

#### Every source

- `tests/` — a test that expected a name without a credential word redacted (a
  whole-word `key` its own `QueryKeyAuth` does not send, `sort_key`, or a substring
  match such as `keyword` or `author`), in `meta.request`, `sent_urls`, `sent_query` or
  a newly recorded fixture, now sees the value → assert the value; a fixture recorded
  with the substring rule keeps `REDACTED` for such a name, so a `sent_query(route) ==
  recorded_query(fixture)` comparison differs on it until the fixture is re-recorded; a
  test that matched the text "was recorded as REDACTED" for a credential named in
  `match_params` → "names a credential"; a parameter whose name has the whole word `sig`
  or `pwd` now reads `REDACTED` — one redaction rule (C10).
- `tests/` — a `ResultMeta(...)` given a field it does not define now raises: name the
  field right — ADR-0012, amendment 2026-10-27.
- `tests/` — a test that asserted the SDK's answer to an argument the schema refuses
  (`Error executing tool ...`, `is_error`, `mcp_call_text` failing) → the text `error:
  InvalidRequestError: <argument>: <message>` through `mcp_call_text`; `mcp_call` still
  raises `AssertionError` on it — ADR-0014, amendment 2026-10-27.
- `tests/` — a test that matched `parse`'s text "first at <loc>: <msg>" → "first at
  <loc> (<type>): <msg>"; one that read pydantic's error from `__cause__` finds `None`;
  one that expected pydantic's `ValidationError` from `load_table`, `project` or
  `PackagedList.load` expects `xippios.core.errors.ValidationError` — parse failures
  print no payload.
- `scripts/refresh_reference.py` (every source with a generated `enums.py`; the template
  renders it in v0.3.0) — `render_str_enums(...)` and `render_int_enums(...)` → one
  `render_enums(lists, fetched=..., ...)` call, value lists and id lists in one mapping,
  `fetched` one date or one per list, then `ruff format` and `ruff check --fix` on
  `enums.py`, which is re-rendered and committed as formatted — the renderer (C7),
  ADR-0008, amendment 2026-10-27.
- `src/xippios/<pkg>/tasks.py` of a source with a bulk task — `BULK_TASKS =
  frozenset({...})` beside `MCP_CAPS`; `mcp.py` and `http.py` may pass `tasks.__all__`
  whole. Template v0.3.0 renders the `BULK_TASKS = frozenset()` scaffold — bulk
  downloads (C15), ADR-0019, decision 4.
- A source that caches an answer over 8 MiB (none known) — raise
  `ClientConfig(cache_max_bytes=...)` and say why in `CLAUDE.md` — ADR-0019, decision 3.
- The source's own workflows (a `siblings.yml`, a `live.yml` of its own) — checked
  against conventions §13's hardening — ADR-0018, amendment (f).

#### sdk-usda-nass

- `src/xippios/usda/nass/tasks.py` — the `ImportError`-guarded `from xippios.core.mcp
  import ResultCap` → an unguarded `from xippios.core import ResultCap`, and the comment
  that names the `mcp` extra goes — `ResultCap` lives in `xippios.core.models`.
- `src/xippios/usda/nass/tasks.py` and its `reference/*.json` value files — converted,
  without network, to packaged-list files (`{"param", "endpoint", "fetched", "records"}`
  and an optional `note`, a value list as records of one field named by the parameter,
  `fetched` kept as the date it is), `endpoint` the upstream operation,
  `get_param_values`, where nass wrote "reference"; any other key is refused, so nass
  writes its `derived_from` into `note` as text, and its two lists derived from
  `api_GET` records, `condition_categories` and `progress_stages`, keep `param:
  "unit_desc"` and `endpoint: "api_GET"` in files of their own names, which
  `PackagedList.load(package, name)` takes. The list tasks read the files with
  `PackagedList.load` and still return strings — ADR-0022, rule 1 and amendment (2) and
  (8).
- `src/xippios/usda/nass/` — nothing for the credential rule: its `QueryKeyAuth("key",
  ...)` registers `key`, so `meta.request`, `sent_urls`, `sent_query`, `recorded_query`
  and every recording keep `key=REDACTED` — C10.

#### sdk-comtrade

- `src/xippios/comtrade/tasks.py` — `_packaged_meta` and `_matches` →
  `packaged.meta(SOURCE, request=...)` and `matches`; `meta.vintage` becomes `None` and
  `meta.retrieved_at` the list's `fetched`, so the list tasks' docstrings that say
  "``meta.vintage`` is the day the package fetched the list, ``meta.retrieved_at`` when
  this task answered" and the tests that assert it change — ADR-0022, rule 1.
- `src/xippios/comtrade/tasks.py`, its `reference/*.json` value files and its CSV tables
  with `reference/tables.json` — converted, without network, to packaged-list files as
  for sdk-usda-nass, `endpoint` the upstream operation,
  `files/v1/app/reference/<file>.json`, where comtrade wrote a file path; comtrade
  writes its `note` and its `exceptions` into `note` as text, and its `origin` becomes
  `endpoint`. The list tasks read the files with `PackagedList.load` and still return
  strings — ADR-0022, rule 1 and amendment (2) and (8).
- `src/xippios/comtrade/tasks.py` — the cached `list_commodities` reads its answer with
  `client.get_answer(...)` for `retrieved_at` instead of `get()` and `decode_json()` —
  ADR-0015, decision 5, amended 2026-10-27.
- `scripts/refresh_reference.py` — `_columns` and `_write_table` →
  `PackagedList(param=..., endpoint=..., fetched=..., records=...).write(path)`, the
  records under upstream's names by `record.dump_upstream()`, `fetched` =
  `datetime.now(UTC)` to the second; `render_enums` takes the fetch day as text
  (`f"{fetched:%Y-%m-%d}"`) — `dump_upstream`, `PackagedList.write`.
- `scripts/refresh_reference.py` and `.claude/commands/refresh-reference-data.md` — the
  per-class rewrite of each docstring with its list's date → `fetched={name: date,
  ...}`; its notes leave the class docstrings, which reach the agent, for the packaged
  list's `note` (`PackagedList(note=...)`); the command's ruff step and its note on the
  renderer's layout go, since the script runs ruff — C7, conventions §8.
- `tests/` — the snapshot count of packaged lists (38) → structure checks (each record
  carries the list's fields; `endpoint` and `fetched` set) — a list's size changes with
  every refresh, and the next one rewrites every file with the full `fetched` time.
- `tests/conftest.py` (`empty_reference_cache`) — deleted: the plugin clears every
  `MemoryCache` around each offline test — ADR-0013, amendment 2026-10-27.
- Its planned `QuotaPolicy(limit_header=None, remaining_header=None, window=86400,
  spent=...)` — nothing: `spent=` stays — C6.

#### sdk-usda-psd

- `src/xippios/usda/psd/tasks.py` — the `ImportError`-guarded `ResultCap` import → `from
  xippios.core import ResultCap`, as for sdk-usda-nass.
- `src/xippios/usda/psd/_client.py` — the gateway block (`API_KEY_ENV`, `policy =
  QuotaPolicy(...)`, `_URL`, `_gateway_error`, `_over_rate_limit`, the `API_KEY_*`, 429
  and `NOT_FOUND` branches of `classify`, `auth = HeaderKeyAuth(...)`) → `gateway =
  Gateway(SOURCE)` from `xippios.core.data_gov`: `classify` returns
  `gateway.classify(response)` when that is not `None` and keeps its own branches after
  it (psd's empty 404), `config = gateway.install(ClientConfig(...))`, `client =
  AsyncClient(config, auth=gateway.auth)`; where the package keeps the names
  `API_KEY_ENV`, `policy` and `auth`, they become `xippios.core.data_gov.API_KEY_ENV`,
  `Gateway.policy` and `gateway.auth`; the `parse_retry_after` import goes when nothing
  else uses it, and may otherwise come from `xippios.core`; the module docstring's
  "waiting within `RetryPolicy.backoff_max`" reads "waiting within the policy's
  `pause_cap`" — the gateway module replaces the copies (C14, ADR-0023), and the pause
  has one cap (C6).
- `tests/test_client.py` — the wiring test drops `policy.reset_header`, which is gone,
  and may assert `config.before_request == Gateway.policy.before_request` next to
  `config.observe == Gateway.policy.observe`; the assertion on "Nothing was retried"
  goes, since the message no longer speaks of retries; a `retry_after` read through the
  client is the snapshot's wait from now, so `== 3151.0` or `== 3600` becomes a bracket
  with `CLOCK_SLACK`, while `classify` called on its own still gives the exact wait; the
  policy's refusal before sending carries `source == "api.data.gov"`, not the slug, and
  starts "api.data.gov quota of the key in DATA_GOV_API_KEY spent" — C6, C14.
- `CLAUDE.md`, the rate-limit row — "within `RetryPolicy.backoff_max` (30 s by default)"
  → "within the policy's `pause_cap` (30 s by default)", and the gateway's key, answers
  and quota named as `xippios.core.data_gov`'s — ADR-0010, decision 4, amended
  2026-10-27.
- `src/xippios/usda/psd/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)` from `xippios.core`; `_codes` reads
  `packaged.records` as before and keeps `packaged.fetched` (a datetime now, not ISO
  text); `_closest` → `closest(value, codes)` — C13, ADR-0023, decision 4.
- `src/xippios/usda/psd/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, with
  `reason=` and `source=SOURCE` at each raise (or a subclass that fills them in); the
  message reads "... in the packaged commodities list (fetched 2026-10-23). ..." and
  ends "If upstream added it since, the packaged list needs a refresh
  (/refresh-reference-data).", so a test that matched "in PSD's commodities list
  (packaged, fetched ...)" or "If PSD added the code since" matches the new text —
  ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/psd/tasks.py` — `_packaged`, `_packaged_meta` and `_matches` →
  `packaged.parse(Model, source=SOURCE)`, `packaged.meta(SOURCE, request=...)` and
  `matches`; `meta.vintage` becomes `None` and `meta.retrieved_at` the list's `fetched`,
  so the list tasks' docstrings that say "``meta.vintage`` is the day the package
  fetched the list, ``meta.retrieved_at`` when this task answered" and the tests that
  assert it change — ADR-0022, rule 1.
- `src/xippios/usda/psd/tasks.py` — nothing for its `None` filters: `meta.request`
  leaves them out by itself; a test that asserted `{"search": None}` sees `{}` —
  ADR-0022, rule 3.
- `src/xippios/usda/psd/tasks.py`, `get_time_series` — nothing; its docstring already
  states its ceiling and that a market year answering PSD's empty 404 is skipped —
  ADR-0022, amendment (6), conventions §4.
- `scripts/refresh_reference.py` — `upstream_record(record)` → `record.dump_upstream()`;
  `write(...)` → `PackagedList(param=..., endpoint=..., fetched=...,
  records=...).write(path)`, `fetched` = `datetime.now(UTC)` to the second;
  `render_enums` takes the fetch day as text (`f"{fetched:%Y-%m-%d}"`); the refusal of a
  value list and an id list together and `--render-only`'s refusal of lists fetched on
  different days go — `dump_upstream`, `PackagedList.write`, C7.
- `tests/` — the snapshot count of packaged lists (42) → structure checks, as for
  sdk-comtrade.

#### sdk-cashctrl

sdk-cashctrl receives what leaves core, copied from the last commit that holds it,
`cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff` on `main`:
`git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:<path>` (ADR-0024). No other source
imports a moved name.

- `src/xippios/cashctrl/_client.py` (the `Tenants` import, `TENANTS = Tenants(...)`,
  `client_for`) — `Tenants` → a module of its own copied from
  `src/xippios/core/tenants.py`; `client_for` keeps its shape. The copy keeps the
  replaced client dropped without closing until cashctrl decides otherwise — C8.
- `src/xippios/cashctrl/tasks.py` (the module docstring's
  `xippios.core.tenants.list_task`, `from xippios.core.tenants import list_task`,
  `list_organisations = list_task(...)`) → the copy's `list_task` — C8.
- `src/xippios/cashctrl/_cli.py`, `src/xippios/cashctrl/mcp.py`,
  `src/xippios/cashctrl/mcp_write.py` — `from xippios.core.mcp import TenantLock` and
  `build_server(..., tenant_lock=...)` → a lock of its own that is a wrapper binding
  `org` on its tools, no middleware, as the family review's C8 has it; ADR-0014's
  decision 7 no longer binds it. From `src/xippios/core/mcp/server.py` the wrapper keeps
  `TenantLock`'s validation of the parameter and the tenant, `_only_the_locked_tenant`
  for the organisation list, and the instructions sentence (`_lock_sentence`) reworded
  for a bound `org`; the middleware's functions (`_lock_middleware`, `_declares`,
  `_refusal`, `_check_lock`, `_defaulted`) have no part in it — C8.
- `tests/test_adapters.py`, which the update from template v0.2.0 deletes
  (`test_the_write_server_serves_write_tasks_only`) — the write-server test moves to a
  test file of cashctrl's own, such as `tests/test_tasks_write.py`, and calls the copy
  of `assert_write_tools`, from `src/xippios/core/testing/adapters.py`, with a check
  that `confirm` is the last parameter, instead of `from xippios.core.testing import
  assert_write_tools`. The family check no longer tests the write server; this test does
  — C8.
- `tests/test_org_lock.py` — follows the wrapper: a call names no other organisation
  than the one the server binds, so the refusal texts it asserts ("this server is locked
  to org=...; the call named another tenant", "...; the call did not name the tenant")
  and the instructions sentence it asserts change with the wrapper;
  `tests/test_registry.py` — against the package's own registry — C8.
- `scripts/record_fixture.py` — `scrub(key)`'s `Scrub(host=REPLAY_HOST, secrets=[...],
  rewrite=scrub_text, allow_binary=False)` → `Scrub(secrets=[...])`, and a step of the
  recorder's own on the `Fixture` that `fixture_from_response` returns, before its one
  write: the host placeholder, the percent-encoded matching and the JSON-decoded verify,
  copied from `src/xippios/core/testing/scrub.py`, and `scrub_text` over the URL, the
  header values and the bodies, so `scrub_request_url` folds into it;
  `redacted_a_secret`, which scrubs again with `Scrub(host=..., rewrite=...)`, compares
  through the same step; `main`'s prefix before core's binary-body refusal meets the new
  text — C9, ADR-0024, decision 4.
- `tests/test_record_fixture.py` — `test_a_key_the_scrub_cannot_reach_is_never_written`
  asserts that core's JSON verify refuses a key behind a JSON escape ("secret value"):
  core no longer decodes, so the recorder's own verify answers it, in its own words;
  `test_a_binary_body_is_refused` matches "binary body cannot be scrubbed" right after
  the recorder's reason → "a binary body cannot be scrubbed; the recording is refused
  unless Scrub(allow_binary=True) stores it base64, flagged";
  `test_nothing_unscrubbed_touches_disk` holds once the recorder replaces the host
  itself — C9.
- `CLAUDE.md` ("Organisations", "How to record a fixture") — the registry,
  `list_organisations` and the `--org` lock as the package's own; the recorder's
  `Scrub(secrets=[key, its basic-auth token])` with its own host, JSON and
  percent-encoded checks; core's verify searches plain values only — ADR-0024.
- `src/xippios/cashctrl/_client.py`, `src/xippios/cashctrl/api/_form.py`,
  `tests/test_errors.py` — `from xippios.core.errors import BODY_LIMIT,
  error_from_response` may become `from xippios.core import ...` — the names are
  exported now; the module path keeps working (C5).
- `src/xippios/cashctrl/_cli.py` — its module docstring names
  `xippios.core.mcp.quiet_request_logging`, which is importable from
  `xippios.core.mcp.server` only → name that path — docstring only, nothing breaks (C5).
- Where it imports `xippios.core.models.REDACTED` and `xippios.core.testing.REDACTED` —
  nothing: both keep working, one object — C10.
- A test that asserted a capped note of an offset-paged list task in full — the note
  ends `; resume with start=<n>` — ADR-0016, amendment 2026-10-27.
- Every task's `ResultMeta(tenant=org)` — nothing: `ResultMeta.tenant` stays — ADR-0024,
  decision 2.

#### sdk-usda-esr

- `src/xippios/usda/esr/tasks.py` — the `ResultCap` import, as for sdk-usda-nass.
- `src/xippios/usda/esr/_client.py` — the gateway block → `gateway = Gateway(SOURCE)`,
  as for sdk-usda-psd, `classify` keeping esr's 400 after `gateway.classify`;
  `parse_retry_after` and the module docstring as there — C14, C6.
- `tests/test_client.py` and `CLAUDE.md`'s rate-limit row — as for sdk-usda-psd — C6,
  C14.
- `src/xippios/usda/esr/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)`, `_codes` as for sdk-usda-psd; esr keeps its
  integer-nearest `_closest` — C13, ADR-0023, decision 4.
- `src/xippios/usda/esr/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, as for
  sdk-usda-psd — ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/esr/tasks.py` — `_packaged`, `_packaged_meta` and `_matches`, as for
  sdk-usda-psd — ADR-0022, rule 1.
- `src/xippios/usda/esr/tasks.py` — `published_at` from its naive release times with
  `published_at_naive=published_at is not None`, since the flag without a time is
  refused; `vintage` keeps the release text as upstream prints it — ADR-0022, rule 2.
- `scripts/refresh_reference.py` — `upstream_record(record)` → `record.dump_upstream()`;
  `render_enums` takes the fetch day as text; the refusal of a value list and an id list
  together and `--render-only`'s refusal of lists fetched on different days go —
  `dump_upstream`, C7.

#### sdk-usda-gats

- `src/xippios/usda/gats/tasks.py` — the `ResultCap` import, as for sdk-usda-nass.
- `src/xippios/usda/gats/_client.py` — the gateway block → `gateway = Gateway(SOURCE)`,
  as for sdk-usda-psd; `parse_retry_after` and the module docstring as there — C14, C6.
- `tests/test_client.py` and `CLAUDE.md`'s rate-limit row — as for sdk-usda-psd — C6,
  C14; the autouse cache-clearing fixture of `tests/test_client.py` — deleted: the
  plugin clears every `MemoryCache` around each offline test — ADR-0013, amendment
  2026-10-27.
- `tests/test_tasks.py`, the 429 test of `get_census_export_series` —
  `info.value.retry_after == 3151.0` is read through the client, so it becomes the
  snapshot's wait, a fraction under 3151: bracket it with `CLOCK_SLACK` — C14.
- `src/xippios/usda/gats/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)`, `_codes` as for sdk-usda-psd; gats keeps its
  three-letter pass in front of `closest` and its `_nearest` and `_sharing_digits` —
  C13, ADR-0023, decision 4.
- `src/xippios/usda/gats/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, as for
  sdk-usda-psd; gats passes its example codes as `hint=` only when `closest` is empty,
  since a `hint` wins over `closest` — ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/gats/tasks.py` — `_packaged`, `_packaged_meta` and `_matches`, as
  for sdk-usda-psd — ADR-0022, rule 1.
- `src/xippios/usda/gats/api/` — the five wrappers that return `(records, stored_at)` →
  `client.get_answer(path)`, its `retrieved_at` the task's `meta.retrieved_at` on a hit
  and a miss alike; `_client.stored_at` goes — ADR-0015, decision 5, amended 2026-10-27.
- `src/xippios/usda/gats/tasks.py` — `published_at` with `published_at_naive`, as for
  sdk-usda-esr — ADR-0022, rule 2.
- `src/xippios/usda/gats/tasks.py`, `get_census_export_series`,
  `get_census_import_series` and `get_census_reexport_series` — nothing: they already
  refuse a range with an unreleased month with `NotFoundError` naming the released
  months, and their docstrings say so — ADR-0022, amendment (6) and (7).
- `scripts/refresh_reference.py` — as for sdk-usda-esr — `dump_upstream`, C7.

## [0.2.1] - 2026-10-27

This patch release carries the release train, the family conformance check every source
runs, and the shared test helpers brought forward from 0.3.0; `gates.yml` ships switched
off. ADR-0019 to ADR-0023 and conventions 1.14 and 1.15 come as documentation; the code
of ADR-0019 and ADR-0022 ships in 0.3.0. As a patch, it keeps 0.2.0's compatibility
(conventions §12). A source adopts it in one adoption PR with `/adopt-release`, moving
its bound to `xippios-core~=0.2.1` (ADR-0018, amendment (c)); "Hand-apply for sources"
below lists what that PR changes by hand.

### Added

- **The release train** (conventions §12; ADR-0018, amendment (b); Johannes's decision
  of 2026-10-26): `publish.yml` keeps its name and runs on every push to `main` and on
  dispatch. Its `release-check` looks at a push that changed `pyproject.toml` or
  `CHANGELOG.md` (a new source's first release PR changes only the CHANGELOG, since the
  scaffold already says 0.1.0) and lets it through when the version in `pyproject.toml`
  has no tag and `CHANGELOG.md` has its `## [X.Y.Z] - ` heading; a changed
  `pyproject.toml` without that heading leaves a notice, anything else ends quietly.
  Then CI, the annotated tag `vX.Y.Z` on the merge commit with the CHANGELOG section as
  its message, the build checked against that tag, and the `pypi` environment that
  Johannes approves. A session never pushes a tag; sdk-usda-psd's v0.2.0 tag on the
  wrong commit, caught by the old workflow, was the case. `publish.yml` has no
  `concurrency` group, whose one pending run would lose a release run queued behind a
  run waiting at `pypi`. The workflow's header and `docs/handover.md` give the recovery
  path ("Re-run failed jobs" once the tag exists; a build that fails for good after the
  tag needs a patch release) and the race of two pushes to `main` close together (the
  second run's tag push fails red, or tags a later commit when the first run's `ci`
  failed; re-run the failed jobs of the run whose commit is the release, and if the
  other run already tagged a later commit, Johannes rejects its `pypi` deployment and
  the release is re-done as a patch; a release is not merged while another release run
  is waiting).
- **The family conformance check** (conventions §10; ADR-0013, amendment 2026-10-26;
  Johannes's decision of 2026-10-26), `xippios.core.testing.family`: what every source
  shares, tested once, collected with one line,
  `from xippios.core.testing.family import *  # noqa: F403`, in a template-rendered
  `tests/test_family.py`. Empty namespace levels, `py.typed`, `__version__`; `mcp.py`
  and `http.py` serve exactly `tasks.__all__` minus `BULK_TASKS`, the write server
  exactly `tasks_write.__all__`; every task synchronous (no `async_fn` required,
  conventions §6), returning `Result[T]`, with an agent docstring; the README status
  table, in the format of sdk-template's `README.md.jinja`, lists exactly the read and
  the write tasks; `.copier-answers.yml` names a template tag; `pyproject.toml` bounds
  `xippios-core` and its extras with `~=X.Y.Z`. The package under test is the ini option
  `xippios_package`, which the plugin registers, or the one `tasks.py` under
  `src/xippios/`. It replaces the three copies a review across the family counted in
  every source on 2026-10-25, `tests/test_layout.py`, `tests/test_adapters.py` and the
  structural part of `tests/test_tasks.py` (sdk-usda-psd, sdk-usda-nass, sdk-usda-esr,
  sdk-usda-gats, sdk-comtrade, sdk-cashctrl). Two family checks are CI steps instead,
  documented for the template in `docs/handover.md`: a CHANGELOG entry on every PR but a
  release, an adoption or Dependabot's, and the 256 KiB cap on the fixture files a PR
  adds or changes, a moved one included (ADR-0019), a warning in template v0.2.1 and an
  error from v0.3.0.
- **Shared test helpers** (ADR-0023 decision 2, each carried by two sources or more;
  brought forward from 0.3.0 by Johannes's decision of 2026-10-26):
  - the plugin's `anyio_backend`, asyncio, which the conftest of all six sources and of
    the template defined;
  - `sent_query(route)`, the scrubbed query of the last request a route received (asked
    for by sdk-usda-nass; sdk-usda-nass's `sent_query`, sdk-comtrade's `_sent`,
    sdk-cashctrl inline);
  - `recorded_query(fixture)`, the scrubbed query a fixture was recorded with
    (sdk-comtrade's `recorded_params` and `_recorded`, sdk-cashctrl's `recorded_query`);
  - `response_from_fixture(fixture)`, a recorded answer as an `httpx.Response` with its
    request, for calling `classify` (`recorded()` in sdk-usda-psd, sdk-usda-esr,
    sdk-usda-gats and sdk-cashctrl);
  - `url=` on `mount_fixture`, `replay` and the plugin's `replay_fixture`, serving a
    recorded answer at another URL (`_mount_recorded_404` in sdk-usda-psd and
    sdk-usda-esr, found by sdk-usda-esr);
  - `CLOCK_SLACK` and `assert_time_between(value, before, after)`, bracketing a time read
    around a call with five seconds of slack for the WSL2 host's clock, which steps back
    about two seconds (sdk-usda-gats's `CLOCK_SLACK`; the same bracket without slack in
    sdk-usda-psd and sdk-usda-esr).
  A query parameter sent or recorded more than once fails the two query helpers rather
  than losing a value.
- **`.github/workflows/gates.yml`** (Johannes's decision of 2026-10-26, as a fallback;
  ADR-0018, amendment (e): the merge classes its check posts): calls the `merge-class`
  and `family-review` workflows of `xippios/.github` as jobs, each only when the
  repository variable `GATES_CALLER` is `1`, which Johannes sets per repository if the
  ruleset editor offers no "Require workflows" rule. It ships off.

### Changed

- **`ci.yml` has no push trigger** (the release train, above): CI runs once per push to
  `main`, through `publish.yml`, for a release; the strict up-to-date policy tests every
  tree before it merges.
- **Every action in the three workflows is pinned by commit SHA**, its version in a
  comment, as in the `xippios/.github` repository.
- **The sdist's include and exclude patterns are anchored at the root** (found by
  sdk-template): unanchored, `README.md` and `LICENSE` match a file of that name at any
  depth. The sdist's file list is unchanged.
- **The `testing` extra declares `packaging>=22`**, which the family check reads the
  core bound with and which pytest already required; 22.0 is the first release whose
  versions and specifiers are PEP 440 only.

### Documentation

- **ADR-0019, bulk downloads and non-JSON payloads**: a streaming `download` that never
  touches the cache, `decode_text` and `decode_csv`, a byte bound on the cache, bulk
  tasks named in `BULK_TASKS` and skipped by the adapters, the fixture files a PR adds
  or changes under 256 KiB (a fixture over the cap recorded before the rule stays until
  re-recorded; small real samples for XML, ZIP, gzip, XLS and XLSX, never
  byte-truncated, byte truncation for text bodies only; JSON arrays truncated by
  elements and marked), and a `key` parameter that is data when the key is not sent in
  the query. The code ships in 0.3.0.
- **ADR-0020, file-distributed sources**: layer 1 is fetch plus `parse/`, one parser per
  file kind; fidelity applies to files; CSV/TSV, XML, gzip and zip are read with the
  standard library, XLS/XLSX or a hardened XML library through the source's own
  dependency; a PDF yields narrative text only, never numbers; the download's recorded
  exchange is replayed for the download call and the sample file is what the parser
  tests read, its provenance one row in `tests/fixtures/files/README.md`.
- **ADR-0021, dependencies between source packages**: a source may consume another
  source's task layer, bound to one minor, sharing one core minor, the dependency
  tagged first.
- **ADR-0022, packaged answers and release times**: `meta` of a packaged list carries
  the upstream's fetch time, operation and release identifier; `published_at_naive`
  admits a release time printed without a zone; `None` filters are left out of
  `meta.request`. The code ships in 0.3.0.
- **ADR-0023, core scope**: code enters `xippios-core` with two consumers, or one
  consumer for a stated reason from a closed list; a helper is copied to a second
  source at most; a public name with no consumer for two minors is removed.
- **ADR-0003, amendment 2026-10-26**: a source whose API is one part of a shared
  upstream document snapshots its part and records the full document's byte size and
  sha256; a `project` override that drops a personal identifier inside a kept list field
  (`bankAccounts[].iban`) is still parsing only; an adoption PR, which fetches nothing,
  leaves `FETCHED.md` to the next `/refresh-upstream` and ports only the capture
  script's changes.
- **ADR-0018, amendment 2026-10-26**: (a) decision 3 covers sdk-template's release PRs,
  which auto-merge after the reviewer's `ready` like core's and a source's; (b) the
  release train replaces the human tag: the release PR's merge runs `publish.yml`, which
  tags `vX.Y.Z` on the merge commit, and the approval of the `pypi` environment run is
  the human gate; sdk-template tags from its CHANGELOG's top heading with its own
  `release.yml`; until a repository's workflow tags itself, Johannes pushes its tag;
  (c) the core bound may read `~=X.Y.Z` when patch Z shipped what the source adopts,
  still one minor; (d) an adoption PR may delete the fixtures, mounts and tests the
  adoption itself makes dead, and nothing else rides along.
- **`docs/roadmap.md`**: core 0.2.1 and template v0.2.1 as the first step, core 0.3.0
  opening with a PR that deletes what has no consumer, and the order of the next
  sources; faostat's API is keyed by a login bearer token (probed 2026-10-26), and
  wasde's tables come from the release's XLS or XML, decided with Johannes when its work
  starts.
- **Conventions 1.14**: the rules of ADR-0019 and ADR-0022 bind a source from its 0.3.0
  adoption, or, when it starts on a git pin of core 0.3.0, each rule from its first PR
  on a pin that carries the rule's code; `usda-wasde` among the source names (§1;
  ADR-0020, ADR-0021); files and bulk tasks (§2, §3, §6, §8, §9, §10; ADR-0019,
  ADR-0020); a snapshot of one part of a shared upstream document and personal
  identifiers inside a kept list field (§3; ADR-0003 amendment); packaged answers, naive
  release times and the spared `key` (§4; ADR-0019, ADR-0022); source dependencies (§11,
  §12, §15; ADR-0021); the release train and the patch case of the core bound (§12;
  ADR-0018 amendment); copies of a helper (§15; ADR-0023); dead fixtures an adoption PR
  may delete (§15; ADR-0018 amendment); an adoption PR leaves `FETCHED.md` to the next
  `/refresh-upstream` (§15; ADR-0003 amendment).
- **Definition of done**: the fixture cap on the files a PR adds or changes and the
  `truncated` marker, file samples, a core PR's consumer statement in its ADR or
  description, the adoption line per ADR-0023 and the patch case of the bound, the
  live-call count, the `Decisions taken` block with what backs each line (as in the
  review checklist) and the release subset.
- **`docs/review-checklist.md`**: the checklist a reviewer applies to any `sdk-*` PR:
  `main`'s documents for every PR and the branch's own for a PR that changes them, a
  release PR's own tag allowed, a decision backed by a convention, an ADR, a
  coordination rule, a dated decision of Johannes's or a row, and a conventions change
  carrying an ADR or an amendment.
- **`.github/PULL_REQUEST_TEMPLATE.md`** mirrors the definition of done, its Adoption PR
  block included, with the Assumptions, Open questions and Decisions taken headings.
- **Conventions 1.15**: §10 states the one live workflow, `.github/workflows/live.yml`,
  in the shape the template renders, which a source whose secrets differ keeps: one job,
  `contents: read`, nightly and on `workflow_dispatch`, the key reaching only its pytest
  step, sources that share a key staggering their start (ADR-0009 amendment; found by
  sdk-template); §10 names the family conformance check, `xippios.core.testing.family`,
  which the rendered `tests/test_family.py` collects and every source's CI runs
  (ADR-0013 amendment); §15 and the definition of done's Adoption PR intro: the session
  enables auto-merge on an adoption PR only when its merge class is `auto`, and a
  `human` adoption waits for Johannes (ADR-0018, amendment (e); the merge classes of the
  `.github` repository's README), and the definition of done's Process line allows the
  session's one merge action, auto-merge on an adoption or `chore/release-*` PR, only
  when its merge class is `auto` (ADR-0018, amendment (e)).
  `.github/PULL_REQUEST_TEMPLATE.md` mirrors both.
- **ADR-0009, amendment 2026-10-26**: the live workflow's shape is the rule for every
  source, since the nightly live tests spend a shared key too.
- **ADR-0013, amendment 2026-10-26**: the plugin's guarantees extend to the family
  invariants the template-rendered `tests/test_family.py` collects.
- **ADR-0018, amendment (e)**: decision 3's auto-merge of adoption and release PRs after
  the reviewer's `ready` applies only to a PR whose merge class is `auto`; a `human`
  adoption or release (a source-owned workflow, a changed template answer, a protected
  path, a build or install route) waits for Johannes (his merge-class decision of
  2026-10-26).
- **`docs/roadmap.md`**: a pinned new source swaps to `~=0.3.0` in its single v0.3.0
  adoption PR, since a release PR changes only the §12 subset; eurostat's design round
  is the first decision put to Johannes when its work starts; faostat's paging and
  limits are verified with the credential first, once Johannes provides the FAO account
  on approving its package; the release check fires on a change of the version or of
  `CHANGELOG.md`, so a first release tags itself; the snapshot and design-round PRs of
  esmis and eurostat start on template v0.2.1 and core 0.2.1 without a pin, the scaffold
  carries `core_git_ref` only when core's `main` has merged the api.data.gov gateway
  module and the bulk downloads of ADR-0019, else a re-pin PR precedes the first tasks
  PR, and a re-pin to a SHA with ADR-0022's code precedes the reference-data PR;
  eurostat proves a keyless render of template v0.2.1 with `new-source.sh --local-only`,
  and the login-keyed case (faostat) is not a template variant (ADR-0023, ADR-0008).
- **`CLAUDE.md` and `docs/handover.md`** describe the release train: a session never
  tags, the release PR's merge tags, Johannes approves `pypi`. `docs/handover.md` gains
  "Core 0.2.1", with the release's recovery path, and "Adopting core 0.2.1", per source,
  with the template's two CI steps.

### Hand-apply for sources

What a source's adoption of 0.2.1 changes by hand: files the template does not update,
and the values `copier update` takes from the answers; `docs/handover.md`, "Adopting core
0.2.1", names them per source.

- `pyproject.toml` — `xippios-core~=0.2.1` and its extras likewise, from
  `core_version=0.2.1` — `tests/test_family.py` imports what 0.2.0 lacks (ADR-0018,
  amendment (c)).
- `tests/test_tasks.py` — delete `test_package_has_a_version` and
  `test_task_is_a_sync_facade_with_an_agent_docstring` — the family check makes them.
- `tests/test_client.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_errors.py` (sdk-cashctrl) — `recorded()` → `response_from_fixture` — a
  shared test helper (ADR-0023).
- `tests/test_slices.py` (sdk-usda-psd, sdk-usda-esr) — `_mount_recorded_404` →
  `replay_fixture(..., url=...)` — a shared test helper, found by sdk-usda-esr.
- `tests/test_tasks.py` (sdk-usda-nass `sent_query`, sdk-comtrade `_sent`, sdk-cashctrl
  inline) — the query of the last request → `sent_query` — a shared test helper, asked
  for by sdk-usda-nass.
- `tests/conftest.py` and `tests/test_tasks.py` (sdk-comtrade `recorded_params` and
  `_recorded`), `tests/test_tasks.py` (sdk-cashctrl `recorded_query`) — the recorded
  query → `recorded_query` — a shared test helper (ADR-0023).
- `tests/test_lists.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_tasks.py` (sdk-usda-gats) — the `retrieved_at` bracket →
  `assert_time_between`, `CLOCK_SLACK` from core — a shared test helper (ADR-0023).
- `tests/test_adapters.py` (sdk-comtrade, sdk-cashctrl) — the tests of their own move to
  `tests/test_tasks.py` or `tests/test_tasks_write.py` before the update deletes the
  file — the family check makes the rest.

## [0.2.0] - 2026-10-25

What the first four sources, sdk-usda-nass, sdk-comtrade, sdk-usda-psd and sdk-cashctrl,
had to build around core 0.1.0, moved into core: ADR-0009 to ADR-0018, amendments to
ADR-0003, ADR-0005, ADR-0007, ADR-0008, ADR-0010, ADR-0013 and ADR-0015, a follow-up
pointer in ADR-0011, and conventions 1.5 to 1.13 (0.1.0 shipped 1.4). While core is 0.x
a minor keeps no compatibility with the one before it: a source depends on
`xippios-core~=0.2.0` and adopts this release in one adoption PR before its next release
(conventions §12 and §15, ADR-0018). The section "Adopting core 0.2.0" of
[`docs/handover.md`](https://github.com/xippios/sdk-core/blob/main/docs/handover.md), in
the repository and not in the sdist, lists per source what that PR deletes and what
replaces it.

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
  (`"C\xf4te d\u2019Ivoire"`, unchanged at runtime), lays out a long member as ruff
  formats it, sorts `__all__` in ruff's order (RUF022), one name per line, and wraps its
  docstrings at 100 columns. It refuses with `ValueError` what made a file ruff rejects:
  caller text it cannot write as printable ASCII, a `generator`, `fetched` text, key or
  class name (a class name must also be an identifier, no keyword, at most 84
  characters), the error naming the argument and position, never the text; a member name
  over 92 columns, the error naming the key and quoting the value; and a key over 75
  characters, the error quoting the key. A value with nothing to derive a member name
  from (a Greek, Cyrillic or CJK label) is named once through the new `member_names=`. A
  source re-renders its enum file once and commits the one-time diff (sdk-usda-nass's
  first line only); the formatting step after a refresh goes (sdk-comtrade).
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
  `QuotaPolicy(...).install(config)` sets both, and the policy keeps a thread-safe
  snapshot from the quota headers (`limit_header`, `remaining_header`, `reset_header`,
  each `None` to turn it off); a 429, or `remaining` at 0, marks the quota spent until
  `Retry-After`, the reset header or `window` from now, upstream's wait cut to `window`
  (`window=86400` for a daily quota); `spent=` reads any other answer to a spent limit,
  such as sdk-comtrade's 403 "replenished in HH:MM:SS", and `mark_spent()` marks it from
  code. A request into a spent quota waits within `pause_cap` (else
  `retry.backoff_max`), logged once, or raises `RateLimitError` with `retry_after`,
  saying nothing was sent and when the quota is back. `install` refuses a config with a
  hook of its own, and a subclass's `before_request` override is not called through the
  hook it sets; `snapshot()`, `reset()`, and `QuotaSnapshot.describe()`, numbers and
  times only. Replaces sdk-usda-psd's `QuotaAwareClient`, `Quota`, `observe_quota` and
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
  those replaced, sharing auth, transport, sleep, rate limiter and cache. Closing it
  closes its own pools and leaves the borrowed transport open for its parent, as
  `record` needs after a recording with `retry=` or `timeouts=`; a transport a caller
  passed to a client is still closed with that client. `record` and `record_sync` take
  `headers=`, `scrub=`, `retry=` and `timeouts=`, overrides going through `derive`.
- **Upstream totals** (ADR-0012, sdk-cashctrl): `ResultMeta.total`, upstream's count of
  the records matching the request, `None` when it reports none. A paginated task sets
  it from upstream's count whether it returns one page or all, never from
  `len(data)`; a negative count is refused; `cap_result` and HTTP responses keep it.
- **Multi-tenant sources** (ADR-0014, sdk-cashctrl). `ResultMeta.tenant`, the tenant by
  name, never a value (`"tenant": null` for a single-tenant source).
  `xippios.core.Tenants(source, *, list_var, fields, reserved=(), validate=None,
  hints=None)` reads the tenants from the environment, names listed in `list_var` and
  values in `<SOURCE>_<NAME>_<FIELD>`, which `var(name, field)` names, a reserved tenant
  (`demo`) present when its variables are set; `names()`, `require(name)`,
  `field(name, field)` through `validate`, with `hints` text for a refused value,
  `client_for(name, build)`, one client per tenant rebuilt when a value changes,
  `reset()`. `xippios.core.tenants.list_task` is the task behind a
  `<source>_list_<tenants>` tool, names only. `TenantLock(param, value)`, as
  `tenant_lock=` for `build_server` and `register_tasks`, refuses without running the
  tool a call that names another tenant or leaves the tenant out, and names the tenant
  in the instructions; the list tool lists that tenant alone, and a locked server
  refuses a task whose tenant parameter has a default. `main(..., add_options=,
  apply_options=)` and `build_parser(prog, *, add_options=)` put a source's options on
  core's parser, parsed once, a `XippiosError` from `apply_options` exiting with status
  2; `is_write_server(server)` serves the loopback rule. Generalises sdk-cashctrl's
  organisation registry and `--org` lock.
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

- **Conventions 1.5 to 1.13**: 1.5 the key variable per issuer and the rate-limit
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
- **`RateLimit.per_minute`'s docstring**: the pace is the one a source sets within
  upstream's limit, or a self-imposed one (ADR-0010), not upstream's limit.

### Security

- **The MCP servers no longer log request URLs** (ADR-0005). Constructing an `MCPServer`
  configures root logging at `INFO`, and httpx logs every request URL at `INFO`, so
  every `xippios-<source>-mcp` wrote upstream URLs into its MCP client's logs:
  sdk-usda-nass's key, sent as `key=`, and sdk-cashctrl's tenant host.
  `xippios.core.mcp.quiet_request_logging()` sets the `httpx` and `httpcore` loggers to
  `WARNING`; `build_server` calls it after constructing the server, and `main` again
  right before running it, after `apply_options`. A consumer who wants the log raises
  the level and runs the server without `main`.
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
