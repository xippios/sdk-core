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

The plugin owns the offline guarantees. For every test not marked `live` it applies, by
autouse fixtures:

1. **No network.** `httpx.HTTPTransport.handle_request` and
   `httpx.AsyncHTTPTransport.handle_async_request` raise `RuntimeError` naming the
   request's method and path, never its host or query (ADR-0005). `respx`'s default
   mocker answers below them, at httpcore's connection pool, so a request is passed down
   while a `respx` router is active: replayed and mocked requests are answered as
   before. A transport a test passes itself never reaches the default ones. The marker
   `network` lifts the block for one test.
2. **No rate-limit wait.** `TokenBucket.acquire` returns at once and takes no token, so
   a limiter a source shares across its tests holds no debt from the replays when a
   live test in the same run uses it. The marker `rate_limited` keeps the limiter for
   one test.
3. **The placeholder key.** `PLACEHOLDER_KEY = "placeholder-for-fixture-replay"`. The
   autouse fixture `placeholder_api_key` sets the variables the ini option
   `xippios_placeholder_key_envs` names to the placeholder and pins `EnvKeyAuth.key` on
   the class, which every auth object of every tenant reads through, cached key or
   not. It returns the placeholder, or `None` in a live test. It has the template's
   name, so a source's own fixture of that name overrides it. `EnvKeyAuth.apply`
   takes the request only and reads `self.key()` itself, and `sent_urls(route)` gives a
   test the URLs a route received as scrubbed strings, so neither the key nor a request
   carrying it has to sit in a test's frame.

Every test, `live` or not, gets the `httpx` and `httpcore` logger levels back when it
ends. The plugin registers `network` and `rate_limited` next to `live`, so a source
running with `--strict-markers` needs no registration of its own. The recorder scrubs
in memory and writes once (`Scrub`, conventions §10).

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
- A test that must reach the network through httpx's default transports is marked
  `network`; a live test is marked `live` and needs nothing else. A test that asserts a
  limiter's waits is marked `rate_limited`. A test module that checks how a key is
  resolved defines a `placeholder_api_key` fixture that pins nothing.
- A `respx` route that passes through (`route.pass_through()`) is respx's own explicit
  way to the network and is not refused. An auth subclass that overrides `key` is not
  pinned.
- A subclass of `EnvKeyAuth` outside core that implements `apply(request, key)` breaks;
  none is known (0.x, conventions §12).
- Conventions §10 states the guarantees and names the markers.
