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
  `REDACTED`, plain and percent-encoded, the longest first; `rewrite` is a text hook for
  the request body, the response body and every response header value (`Location`
  included), for pre-authenticated URLs. `write_fixture`, `fixture_from_response` and
  `record` take it as `scrub=`. The credential scrubbing of 0.1.0 still always applies.
  Ports the recorder pattern sdk-cashctrl had to keep locally: `write_fixture` kept the
  tenant host in `request.url`, and CashCtrl's `file/prepare.json` answers with signed
  storage URLs that `file/get` redirects to. With `host` or `secrets` set, the scrubbed
  exchange is verified before anything is kept: the URL, every header and both bodies
  are searched raw and, for a JSON body, decoded, so a host or value behind a `\uXXXX`
  escape is found; one still present raises `ValueError` naming the kind ("request host"
  or "secret value") and the location, never the value, and nothing is written; the
  checking frames are hidden from pytest's report, which would print the refused text as
  their arguments. Modelled on sdk-cashctrl's final check. A placeholder that would
  write what it hides is refused with `ValueError`, naming neither: a `host` that
  contains one of the `secrets` (any letter case) when the `Scrub` is built, and a
  `host` that is the request's own host (`url.host` or its IDNA form) when the exchange
  is scrubbed. A placeholder that ends with the original host stays allowed. `Scrub`'s
  `repr` leaves `secrets` out.
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
- `match_params=` (keyword-only) for `mount_fixture`, `replay` and the plugin's
  `replay_fixture`: names of recorded query parameters whose recorded values a request
  must carry too; a name absent from the recorded URL, or whose recorded value holds
  `REDACTED` in whole or in part, raises `ValueError` naming it. Replay matched on
  method, host and path only, so a count call (`countOnly=true`) and the data call on
  the same path could not be told apart (sdk-comtrade). Absence cannot be matched: the
  more specific fixture is mounted first, since `respx` tries routes in order. The
  request body is never matched; a test asserts it from the route's calls.
- `xippios.core.testing.sent_urls(route)`: the URLs a `respx` route received, oldest
  first, as strings through `scrub_url`, so a key sent as a query parameter reads
  `REDACTED`. A test compares these instead of keeping a request from `route.calls` in
  its own frame, where a failing assertion or `pytest -l` prints it, key included
  (sdk-usda-nass).
- `xippios.core.testing.PLACEHOLDER_KEY` (`"placeholder-for-fixture-replay"`, also in
  the plugin) and the plugin's ini option `xippios_placeholder_key_envs` (type `args`,
  default empty): the key offline tests send and the variables that hold it; see the
  placeholder pin under Changed.
- `xippios.core.testing.assert_write_tools(write_server, write_tasks, *, source,
  read_server=None, router=None)`: fails the test, naming the offending tool, unless
  the write server was registered with `read_only=False` (`is_write_server`, which the
  loopback rule of `main` reads), its tools are exactly the write tasks by `tool_name`,
  every write task takes `confirm: bool = False`, and, when given, no write tool is on
  the read server and no route of the router serves a write task. Works in sync and
  async tests.
  Conventions §8's write-server rules had no check in `xippios.core.testing`
  (sdk-cashctrl).
- `xippios.core.testing.ReplayFixture`: a `Protocol` for the plugin's `replay_fixture`
  fixture, `(endpoint, case, *, match_params=None) -> respx.Route`, so a source's test
  can annotate it; the fixture is annotated with it instead of `Callable[..., Route]`.
- `fixture_from_response` is exported from `xippios.core.testing`; sdk-cashctrl's
  recorder imported it from `xippios.core.testing.fixtures`.
- `ResultMeta.tenant` (default `None`): the tenant the data came from, by name, for a
  multi-tenant source; never a credential, a host or another of the tenant's values.
  A source carried the tenant only inside `request` (`request.org` in sdk-cashctrl),
  where nothing marked it as the tenant. Single-tenant sources leave it `None` (every
  envelope's JSON now carries `"tenant": null`); conventions §4 lists it.
- `xippios.core.Tenants(source, *, list_var, fields, reserved=(), validate=None)`: the
  tenants a multi-tenant source declares in the environment, and one client per tenant
  (conventions §7). `list_var` lists the names, comma-separated, `^[a-z0-9_]+$`; each
  tenant's values sit in `<SOURCE>_<NAME>_<FIELD>` (`var(name, field)` gives the
  variable's name). `names()` reads the list on every call, in declared order, and
  appends each reserved name whose field variables are all set; a reserved name in the
  list, a malformed name or a name listed twice is a `ConfigError`. `require(name)`
  returns a declared name or raises `InvalidRequestError`, the caller's bad argument
  (MCP text, HTTP 422), listing the declared names, or the variables to set when there
  are none. `field(name, field)` returns a value stripped and passed through
  `validate[field]`; a missing value of a declared tenant, or one the check refuses, is
  a `ConfigError` naming the variable, never the value. `client_for(name, build)` builds a
  tenant's client with `build(name)` on first use and keeps it, thread-safe, under a
  digest of the tenant's current values, so a changed value builds a new client;
  `reset()` drops them. Generalises sdk-cashctrl's organisation registry (`orgs()`,
  `require_org()`, `client_for()`), which every multi-tenant source would otherwise
  write again.
- `xippios.core.tenants.list_task(tenants, *, name, doc=None)`: a synchronous task named
  `name` (`list_organisations`) that returns the declared tenants' names in the
  envelope, names only (ADR-0005), for a `<source>_list_<tenants>` reference tool. Its
  default docstring is written for agents. On a server locked to one tenant its tool
  lists that tenant only.
- `xippios.core.mcp.TenantLock(param, value)` and `tenant_lock=` for `build_server` and
  `register_tasks` (ADR-0014): installs, once per server, a middleware that answers a
  tool call naming another tenant with `error: InvalidRequestError: this server is
  locked to <param>=<value>; the call named another tenant` without running the tool,
  and a call that leaves out a `param` the tool's input schema declares with `...; the
  call did not name the tenant`, also when that schema lookup fails; a call to a tool
  without `param` passes unless it names another tenant, and listing tools is left
  alone. On a locked server, `register_tasks` refuses with `ValueError` a task whose
  `param` has a default, and the lock on a server that has one: a tool that takes the
  tenant parameter must receive it. `build_server` adds "This server is locked to
  <param> <value>; every tool call that takes <param> must pass <param>=<value>." to the
  instructions. sdk-cashctrl wrote the same lock itself, set the instructions through
  the SDK's private low-level server and parsed the command line twice.
- `main(server, argv=None, *, add_options=None, apply_options=None)` and
  `build_parser(prog, *, add_options=None)`: `add_options` puts a source's arguments on
  core's parser, so the command line is parsed once and `--help` lists every option;
  `apply_options(namespace, server)` returns the server to run. A `XippiosError` it
  raises, such as an undeclared tenant, exits with status 2 and the message on stderr,
  like an argparse error.
- `--allow-remote` for `main`, and `xippios.core.mcp.is_write_server(server)`: true once
  tasks were registered on the server with `read_only=False`. See Changed for the rule.
- `xippios.core.testing.mcp_call_text(server, name, arguments)`: the tool's text, through
  the same in-process client as `mcp_call`, so a test can assert a refusal or any other
  `error:` text.
- `ClientConfig.before_request` and `ClientConfig.observe` (ADR-0015). `before_request`
  is called once per `request()` call, not per retry, after the cache lookup (a cache
  hit returns before it) and before the rate limiter, with the request as built and no
  credentials on it yet; it may be sync or async, may wait, and may raise a taxonomy
  error, in which case nothing is sent. `observe` is called with every response from
  the wire, each retried attempt included and a cache hit never, before `classify` and
  the retry decision, also with `raise_on_error=False`; an exception from it propagates.
  sdk-usda-psd had to subclass `AsyncClient` and override `request` to pause before a
  request, and called its quota observer from `classify`, which a raw response skips.
- `auth=` per request for `AsyncClient.request`, `get` and `get_json`, `Client.request`,
  `get` and `get_json`, and `record`/`record_sync`, typed as httpx types it:
  `httpx.Auth | UseClientDefault | None`, default `httpx.USE_CLIENT_DEFAULT`
  (`UseClientDefault`, private in httpx, is re-exported from `xippios.core.client`).
  `None` sends the request, every retry included, without the client's credentials, an
  `httpx.Auth` replaces them for that call, the default sends the client's. `None` and
  the default share the cache; a call with an `httpx.Auth` of its own bypasses it,
  neither looked up nor stored, since another identity may get another answer.
  sdk-comtrade fetches its public reference files from the same host as its keyed data
  API and needed a second client to keep the key off them.
- `response.extensions["xippios_cache_stored_at"]` on a cache hit, next to
  `"xippios_cache": "hit"`: the entry's `stored_at`, in epoch seconds. On a hit a task
  sets `retrieved_at` from it, since the data was fetched then, not now (conventions
  §4). sdk-usda-psd's tasks could only stamp a hit with the current time.
- `xippios.core.client.decode_json(response, *, source=None, path=None)`: the JSON
  decoding of `get_json`, with its `ValidationError` for a body that is not JSON, for a
  wrapper that calls `get` because it needs the response too, e.g. a cache hit's
  `xippios_cache_stored_at` (conventions §6). `get_json` calls it.
- `QuotaPolicy` and `QuotaSnapshot`, exported from `xippios.core` and
  `xippios.core.client`: ADR-0010's quota rules on the two hooks (ADR-0015).
  `QuotaPolicy(*, limit_header="x-ratelimit-limit",
  remaining_header="x-ratelimit-remaining", reset_header=None, window=3600.0,
  spent=None, pause_cap=None, source=None, clock=..., sleep=asyncio.sleep)`, either
  header name `None` to turn its reading off: `observe(response)` keeps a thread-safe
  `QuotaSnapshot(limit, remaining, observed_at, resumes_at)` from the quota headers of
  every response from the wire, never from a cache hit; a 429, or a response that leaves
  nothing, marks the quota spent until `Retry-After` (on a 429), else the reset header
  (delay-seconds, epoch seconds as GitHub sends them, or an HTTP-date), else `window`
  from now; a wait from upstream, through a header or `spent=`, is cut to `window`, the
  one setting for the fallback and that ceiling (a daily quota sets `window=86400`), and
  a count that is not ASCII digits is ignored. `spent=`, a callable asked about every
  observed response, marks the quota spent for the seconds it returns, for an upstream
  whose spent limit is not a 429 (sdk-comtrade's 403 "replenished in HH:MM:SS");
  `mark_spent(retry_after)` does it from code. `before_request(request)` waits a spent
  quota out when it is back within `pause_cap`, logging one warning with the method and
  path, and otherwise raises `RateLimitError` with `retry_after`, saying that nothing
  was sent and when the quota is expected back. `install(config)` returns the config
  with both hooks set, the pause bound to that config's cap (`pause_cap`, else its
  `retry.backoff_max`), and refuses with `ValueError` a config that has a hook of its
  own. `snapshot()`, `reset()`; `QuotaSnapshot.describe()` names numbers and times only.
  Generalises sdk-usda-psd's `Quota`, `observe_quota`, `quota_pause` and
  `QuotaAwareClient`, which sdk-usda-esr and sdk-usda-gats would otherwise copy.
- The pytest plugin keeps quota policies out of offline tests (ADR-0013 decision 4,
  added by ADR-0015): in every test not marked `live`, every `QuotaPolicy`'s snapshot
  is forgotten before and after the test, so a replayed 429 cannot leave a source's
  module-level policy spent for the tests after it, and unless the test is marked
  `rate_limited` a policy neither waits nor refuses.
- `Tenants(..., hints=None)`: per field, static text appended to the `ConfigError` that
  `field()` raises when `validate` refuses a value ("...; <hint>"), so the operator
  learns what the variable should hold; the check's own message, which may quote the
  value, is still never used, and the value never appears. A hint for a field not in
  `fields`, or for one without a `validate` check, where it could never be shown, is a
  `ValueError` at construction. Carried over from the `Tenants` work of ADR-0014.
- `caps=` for `register_tasks` and `build_server` (ADR-0016): a mapping from a task
  function's `__name__` (`list_partners`, not the tool name `comtrade_list_partners`) to
  a `ResultCap` that replaces `cap` for that tool; every other tool keeps `cap`. A key
  that names none of the tasks is refused with `ValueError`, naming it, before anything
  is registered. For a reference tool whose whole list an agent needs: a per-tool cap
  raises the rows, and its byte bound stays at the default 64 KB, the family's bound for
  every tool. The one cap of a server cut `comtrade_list_reporters` (255 rows) and
  `comtrade_list_partners` (310) at 200 (sdk-comtrade).
- `ResultCap(note=...)`: the text after the counts when the cap cuts a result, used
  verbatim, in the note of a cut list and in that of a non-list result over the byte
  cap, e.g. `"filter by period or by reporter to see the rest"` for a tool with those
  filters. `None`, the default, keeps the default text; a blank note is refused with
  `ValueError`.

### Changed

- **Breaking:** the pytest plugin keeps the default run offline and free of real keys
  on its own (ADR-0013). A source's tests that hit the network, assert a rate
  limiter's waits or test how a key is resolved must mark or override accordingly:
  mark them `network`, mark them `rate_limited`, or override `placeholder_api_key` in
  their module with a fixture that pins nothing. A `live` test needs nothing.
  - Network: from configuration on, httpx's default transports and httpcore's
    connection pools raise `RuntimeError` naming the request's method and path, never
    its host or query, during collection, in a fixture of any scope and in a test. The
    refusal is lifted while a test marked `network` or `live` is set up, run and torn
    down; ADR-0013 states the edges (a conftest's import, wider-scoped fixtures).
    Requests `respx` answers, replayed fixtures included, and transports a test passes
    itself (`httpx.MockTransport`, FastAPI's `TestClient`) are unaffected; a `respx`
    route that passes through is refused unless the test is marked `network`. Nothing
    enforced the definition of done's "no network in the default test run"
    (sdk-cashctrl).
  - Rate limiter: in a test not marked `live`, `TokenBucket.acquire` returns at once
    and takes no token, so a limiter a source shares across its tests holds no debt
    from the replays when a live test in the same run uses it; the marker
    `rate_limited` keeps the limiter. A source paced at one request a second waited a
    second per replayed request (sdk-comtrade, sdk-usda-psd).
  - Placeholder pin: the autouse fixture `placeholder_api_key` makes every test not
    marked `live` send `PLACEHOLDER_KEY`: it sets the variables
    `xippios_placeholder_key_envs` names and pins `EnvKeyAuth.key` on the class, so
    every auth object of every tenant sends the placeholder even after a live test
    cached the real key on it. It returns the placeholder, or `None` in a live test. A
    source's own fixture of the same name overrides it; with this release a source
    deletes the one sdk-template 0.1.5 had it carry by hand, which pinned one
    module-level `auth` and could not reach a source with one auth object per tenant
    (sdk-comtrade, sdk-cashctrl).
  - Logger levels: the `httpx` and `httpcore` loggers get their levels back after
    every test, live ones included. Building an MCP server sets both to `WARNING`, and
    only core's own `tests/conftest.py` restored them, so a source test that built a
    server left httpx at `WARNING` for the rest of the run (sdk-cashctrl).
- The `testing` extra declares `httpcore>=1.0`: the plugin patches httpcore's
  connection pools and imports it, which only httpx's own dependency provided before.
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
  source, no binary body unless flagged) and the plugin's offline guarantees with the
  markers `network` and `rate_limited`; ADR-0013 added.
- **Breaking:** `register_tasks(..., read_only=False)`, and so
  `build_server(..., read_only=False)`, refuses a task without a parameter `confirm`
  annotated `bool` (resolved with `typing.get_type_hints`, so `Annotated[bool, ...]`
  counts and `bool | None` does not) with the default `False`: it raises `ValueError`
  naming the tool and the rule before any task is registered. A write server could
  register a task that writes on its first call, which conventions §8 forbids and only
  `assert_write_tools` caught, in a test (sdk-cashctrl). `assert_write_tools` uses the
  same check. Read-only servers are unaffected.
- **Breaking:** `main` serves a write server over `--http` on a loopback `--host` only
  (`127.0.0.1`, `localhost`, `::1`) and otherwise exits with status 2, unless
  `--allow-remote` is passed. A write server carries no authentication; beyond loopback
  a gateway in front of it has to provide it (ADR-0014). Read-only servers and stdio
  are unaffected.
- `xippios.core.testing.mcp_call` calls the tool through `mcp.Client(server)` connected
  in-process instead of `MCPServer.call_tool`, so the server's middleware runs, a tenant
  lock included; `MCPServer.call_tool` bypasses it (sdk-cashctrl drove `mcp.Client` by
  hand). It returns the decoded JSON as before and fails on `error:` text as before. A
  call the server answers with an MCP error, arguments the tool's schema refuses or an
  unknown tool, now fails with `AssertionError` instead of raising the SDK's
  `ToolError`, and the server must be one `mcp.Client` connects to (an `MCPServer` or
  a low-level `Server`).
- `main` quiets the httpx and httpcore loggers right before the server runs, after
  `apply_options`, instead of first thing.
- Conventions 1.9: §1 names the per-tenant variables, §4 lists `ResultMeta.tenant`, §7
  states the tenant scheme and the error split, §8 the `confirm` check at
  registration, the loopback rule, the tenant list tool, the tenant lock and the option
  hooks; §10 states that a placeholder host that contains the original host is allowed
  and written as such. ADR-0014 added.
- A 429 or 5xx that `ClientConfig.classify` maps to an error other than an
  `UpstreamError` for a 5xx is no longer retried blindly (ADR-0015). Before each retry
  the loop asks `classify`, at most once per attempt and also with
  `raise_on_error=False`: a `RateLimitError` sets the wait from its `retry_after` (else
  the `Retry-After` header's), so a wait beyond `RetryPolicy.backoff_max` is raised
  after one attempt; an `UpstreamError` for a 5xx and `None` keep the status rule, so a
  5xx is retried when the method allows; any other error, an `AuthError` or an
  `InvalidRequestError` say, stops the retries. `send_with_retries` takes the mapping as
  `classify=`. A 429 without `Retry-After`, api.data.gov's answer to a spent hourly
  quota, was retried three more times into the spent quota before `classify` could say
  "one hour" (sdk-usda-psd). sdk-cashctrl, which maps every 5xx to `UpstreamError` to
  keep its tenant host out of the message, keeps its retries.
- Conventions 1.10: §4 names `xippios_cache_stored_at` as the `retrieved_at` of a cache
  hit; §6 states the `before_request` and `observe` hooks, `QuotaPolicy` as the
  implementation of ADR-0010's quota rules, `classify`'s part in retries, and `auth=`
  per request; §10 the plugin's quota guarantee. ADR-0015 added; ADR-0013 gains its
  decision 4.
- The note of a capped MCP result promises no filter: "showing {shown} of {total} rows
  (cap: {max_rows} rows or {max_bytes} bytes); narrow the query to see the rest", and
  for a non-list result over the byte cap "result is {n} bytes, over the cap of
  {max_bytes}; narrow the query to see the rest". It read "narrow the query, for example
  with more filters or a shorter date range, to see the rest", which sent an agent
  looking for filters a reference list does not have (sdk-comtrade). A cap's `note`
  replaces the text after the counts.
- Conventions 1.11: §8 states the per-tool row cap for a reference tool whose whole list
  an agent needs, with the byte cap kept for every tool, and that the note never
  promises a filter the tool lacks. ADR-0016 added.

### Fixed

- `parse_retry_after` raised `ValueError` for a `Retry-After` of non-ASCII digits such
  as `"²"`, which `str.isdigit` accepts and `float` refuses, so the retry loop raised it
  out of a request; it reads ASCII digits only now and returns `None` for anything
  else, and for a value too long to be a finite float, which made `retry_after`
  infinite (the HTTP adapter's `int(retry_after)` then raised `OverflowError`). An
  HTTP-date whose zone offset is a huge number made `parsedate_to_datetime` raise
  `OverflowError` out of the retry loop; it is unparseable now, `None` like any other.
- The live gate skipped every test under a directory named `live`, marked or not: it
  matched the keyword `live`, which a directory's name adds. It follows the marker now.
- A gzip answer replayed from the cache raised `httpx.DecodingError`: the client stored
  the decoded body together with `content-encoding`, so the replay decoded it again.
  Cache entries are stored without wire headers now, and entries a persistent backend
  kept from 0.1.0 are stripped when replayed (sdk-usda-psd PR 3 live tests).
- Taxonomy errors survive `copy.copy`, `copy.deepcopy` and `pickle`: `AuthError`,
  `ValidationError`, `UpstreamError` and source subclasses with keyword-only arguments
  raised `TypeError`, because `Exception` rebuilds with positional arguments only.
  `XippiosError.__reduce__` restores every attribute without calling `__init__`
  (sdk-cashctrl).
- A client from `AsyncClient.derive` no longer closes a transport it did not create.
  It shares the parent's transport, and closing the derived client, as `record` does
  after a recording with `retry=` or `timeouts=`, closed that transport under the
  parent, which still uses it. The derived client's pools are still
  closed; the borrowed transport is left for the parent's `aclose`. A transport passed
  to a client by its own caller is still closed with that client.

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
