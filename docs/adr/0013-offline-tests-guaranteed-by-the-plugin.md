# ADR-0013: Offline tests guaranteed by the plugin

Status: Accepted · Date: 2026-10-23

## Context

Conventions §10 has unit tests run offline against recorded fixtures, and the definition
of done lists "unit tests pass offline (no network in the default test run)" among the
items CI enforces. Nothing enforced it. `xippios.core.testing.plugin` gated live tests
and mounted fixtures; everything else a source needed to keep its default run offline
and free of real keys, it wrote into its own `tests/conftest.py`:

- **The placeholder key.** sdk-usda-nass, sdk-usda-psd and sdk-comtrade carry the
  `placeholder_api_key` fixture sdk-template 0.1.5 introduced: it sets the source's key
  variable to a placeholder and pins `key` on the one module-level `auth` object,
  because an auth object resolves its key once and caches it, so a live test earlier in
  the run would leave the real key in place for every later test. sdk-cashctrl holds one
  `BasicKeyAuth` per organisation and no module-level `auth`, so it wrote a fixture of
  its own that drops every cached client before and after each test. The template
  marks `tests/**` as `_skip_if_exists`, so its fix reached no existing source through
  `copier update`: four sources were patched by hand, and the next fix to the fixture
  would have to be patched by hand four times again. The template's
  `test_replay_tests_send_the_placeholder_key` keeps the request it checks in its
  locals, and core's `EnvKeyAuth.apply(request, key)` took the key as an argument, so a
  failing test could print the shell's key (sdk-usda-nass).
- **The rate limiter.** A replayed request still waited on the source's limiter: a
  source paced at one request a second waited a second per replayed request
  (sdk-comtrade, sdk-usda-psd), and there was no public switch to stop it.
- **The network.** A test that forgot to mount a fixture sent its request to the
  upstream, with whatever key the shell held, or failed on name resolution in CI. No
  test could tell.
- **The request loggers.** Building an MCP server sets the `httpx` and `httpcore`
  loggers to `WARNING`; core restored them per test in its own conftest only, so a
  source test that built a server changed the level for the rest of the run
  (sdk-cashctrl).
- **The recorder** kept the tenant's host in a fixture's URL and wrote a fixture before
  the source could scrub it (sdk-cashctrl); the first half of this change moved the
  scrub into core (`Scrub`, conventions 1.8).

## Decision

The plugin owns the offline guarantees.

1. **No network, for the whole session.** When pytest is configured, the plugin patches
   httpx's default transports (`httpx.HTTPTransport.handle_request`,
   `httpx.AsyncHTTPTransport.handle_async_request`) and httpcore's connection pools
   (`httpcore.ConnectionPool.handle_request`,
   `httpcore.AsyncConnectionPool.handle_async_request`) once. They raise `RuntimeError`
   naming the request's method and path, never its host or query (ADR-0005): at import,
   in a fixture of any scope, in a test. `pytest_runtest_setup` lifts the refusal for a
   test marked `network` or `live` before its fixtures are set up, and
   `pytest_runtest_teardown` restores it after they are torn down. `respx` patches the
   same pool methods on top when a router starts: a replayed or mocked request is
   answered by respx, and a route that passes through (`route.pass_through()`) reaches
   the refusal like any other request unless the test is marked `network`. A transport
   a test passes itself never reaches the default ones.
2. **No rate-limit wait.** For every test not marked `live`, by an autouse fixture,
   `TokenBucket.acquire` returns at once and takes no token, so a limiter a source
   shares across its tests holds no debt from the replays when a live test in the same
   run uses it. The marker `rate_limited` keeps the limiter for one test.
3. **The placeholder key.** `PLACEHOLDER_KEY = "placeholder-for-fixture-replay"`. For
   every test not marked `live`, the autouse fixture `placeholder_api_key` sets the
   variables the ini option `xippios_placeholder_key_envs` names to the placeholder and
   pins `EnvKeyAuth.key` on the class, which every auth object of every tenant reads
   through, cached key or not; an auth subclass that overrides `key` reads its own way.
   It returns the placeholder, or `None` in a live test. It has the template's name, so
   a source's own fixture of that name overrides it, and a test module that needs real
   key resolution overrides it with one that pins nothing. `EnvKeyAuth.apply` takes the
   request only and reads `self.key()` itself, and `sent_urls(route)` gives a test the
   URLs a route received as scrubbed strings, so neither the key nor a request carrying
   it has to sit in a test's frame.

Every test, `live` or not, gets the `httpx` and `httpcore` logger levels back when it
ends. The plugin registers `network` and `rate_limited` next to `live`, so a source
running with `--strict-markers` needs no registration of its own. The recorder scrubs
in memory, verifies the result (the original host or a secret value still present, a
JSON body decoded included, refuses the exchange) and writes once (`Scrub`, conventions
§10).

## Consequences

- A source adopting core 0.2.0 deletes from its `tests/conftest.py` the
  `placeholder_api_key` fixture, its `PLACEHOLDER_KEY` constant and the imports of
  `API_KEY_ENV` and `auth` that served only them, and names its key variable in its
  pytest configuration instead:
  `xippios_placeholder_key_envs = ["COMTRADE_API_KEY"]` under
  `[tool.pytest.ini_options]`. A fixture it keeps overrides core's without error. The
  template's `test_replay_tests_send_the_placeholder_key` can go with it: core's own
  tests prove the pin.
- sdk-cashctrl keeps its demo-only handling (which organisations exist in a test, the
  placeholder subdomain, the cached clients); none of it is about keys alone. Its keys
  are pinned by the class-level pin whichever organisation's auth object sends them.
- A test that must reach the network through httpx's default transports, a `respx`
  route that passes through included, is marked `network`; a live test is marked
  `live` and needs nothing else. Network access at import or in a fixture outside a
  marked test moves into a marked test or a recorded fixture. A test that asserts a
  limiter's waits is marked `rate_limited`. A test module that checks how a key is
  resolved defines a `placeholder_api_key` fixture that pins nothing.
- A subclass of `EnvKeyAuth` outside core that implements `apply(request, key)` breaks;
  none is known (0.x, conventions §12).
- Conventions §10 states the guarantees and names the markers.
