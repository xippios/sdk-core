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
   naming the request's method and path, never its host or query (ADR-0005), while test
   modules are collected, in a fixture of any scope and in a test.
   `pytest_runtest_setup` sets the refusal for each test before its fixtures are set up,
   lifted for a test marked `network` or `live`, and `pytest_runtest_teardown` restores
   it after they are torn down. `respx` patches the
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
4. **No quota pause, no quota left spent** (added by ADR-0015, 2026-10-24). For every
   test not marked `live`, by an autouse fixture, every `QuotaPolicy`'s snapshot is
   forgotten before and after the test, so a replayed 429 cannot leave a source's
   module-level policy spent for the tests after it, a live one included; and, unless
   the test is marked `rate_limited`, the policy's pause does nothing: `before_request`
   and the hook `install` sets return at once, neither waiting nor raising
   `RateLimitError`. `observe` keeps the snapshot during the test, for a test that
   asserts it. The marker `rate_limited` keeps the pause for one test, as it keeps the
   limiter.

Every test, `live` or not, gets the `httpx` and `httpcore` logger levels back when it
ends. The plugin registers `network` and `rate_limited` next to `live`, so a source
running with `--strict-markers` needs no registration of its own. The recorder scrubs
in memory, verifies the result (the original host or a secret value still present, a
JSON body decoded included, refuses the exchange) and writes once (`Scrub`, conventions
§10).

This ADR also covers the conventions 1.8 additions that came with the change. §6 names
form bodies next to JSON ones: a request body goes as `data=` (form-encoded) or as
`json=`, never both. §10 states how replay matches: `match_params` names recorded query
parameters whose recorded values a request must carry, a parameter whose recorded value
holds `REDACTED` is refused by name, absence cannot be expressed, and where two
fixtures share a path the more specific one is mounted first, since `respx` tries
routes in order. §10 also states the recorder's rules (scrub in memory, a placeholder
host for a multi-tenant source, named secret values, no binary body unless flagged, one
write) and the verify step before the write. The verify is best effort: one JSON-aware
pass over the URL, the headers and the bodies with the scrub's own patterns. The
backstops are recording only against synthetic or demo tenants, and the definition of
done's grep of every fixture for key patterns before it is committed.

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
  `live` and needs nothing else. Network access during collection or in a fixture
  outside a marked test moves into a marked test or a recorded fixture. A test that asserts a
  limiter's waits is marked `rate_limited`. A test module that checks how a key is
  resolved defines a `placeholder_api_key` fixture that pins nothing.
- What the plugin guarantees is exactly the above, and these are its edges:
  - The refusal's message names the method and path only. pytest's own failure report
    may still print httpx's request repr, query included; offline, the key in it is the
    placeholder.
  - The guard is active from `pytest_configure` on. A request made while a
    `conftest.py` is imported, before the plugin is configured, is not refused.
  - A fixture of wider scope runs under the marking of the test that sets it up, and
    its teardown under the marking of the last test that uses it. A live clean-up
    fixture is therefore function-scoped, or runs in the separate nightly `-m live`
    job.
  - The logger levels are saved per test, after fixtures of wider scope are set up; one
    of those that changes a level leaves it behind.
  - The quota snapshots are forgotten for every policy alive when a test not marked
    `live` starts and ends. A live test keeps them, so consecutive live tests share
    every policy's snapshot: a quota one live test spends makes the next one wait within
    the cap, or raise `RateLimitError` without sending.
  - The reset runs in a test's setup after the fixtures of wider scope, so a policy that
    such a fixture spends while it is set up is forgotten in the setup of the first test
    not marked `live` from then on, the one that set it up included, and never reaches
    that test's body; a fixture that hands an offline test a spent quota is
    function-scoped.
- A subclass of `EnvKeyAuth` outside core that implements `apply(request, key)` breaks;
  none is known (0.x, conventions §12).
- Conventions §10 states the guarantees and names the markers.

Amended by ADR-0015 (2026-10-24): decision 4, no quota pause and no quota left spent.

Amended by ADR-0016 (2026-10-24): two edges of decision 4, the snapshots consecutive
live tests share and when a quota spent by a fixture of wider scope is forgotten.

## Amendment 2026-10-26

The plugin's guarantees extend to the family invariants that the template-rendered
`tests/test_family.py` collects. Core's `testing` extra ships the family conformance
check, `xippios.core.testing.family`, and the rendered file collects it with one line,
`from xippios.core.testing.family import *  # noqa: F403`, so every source's default run,
in its CI, tests what every source shares: the empty namespace levels, `py.typed` and
`__version__`, the tasks the adapters and the write server serve, `Result[T]` and the
agent docstrings, the README status table, the template tag and the core bound. Each
source carried these checks as its own `tests/test_layout.py` and
`tests/test_adapters.py`; a check added in a later core release now reaches every source
with the core update, as the guarantees above do. The plugin registers the ini option
`xippios_package`, which names the package under test where `src/xippios/` holds more
than one `tasks.py`. Johannes decided on 2026-10-26 that a family conformance check ships
in core's `testing` extra and runs in every source's CI; conventions §10 names it from
1.15 on.

Amended 2026-10-27 (core 0.3.0, ADR-0019): `AsyncClient.download` streams through the
client's pool and httpx's default transport, so decision 1 covers it unchanged: an
unmocked download in an offline test is refused with the same `RuntimeError`, and a
`respx` route answers a mocked one. Replay serves a fixture's body as recorded, a body
the recorder cut (`truncated`) included. `sent_urls`, `sent_query` and `recorded_query`
redact by the one rule of `xippios.core.redaction` (ADR-0005, amendment 2026-10-27).

Amended 2026-10-27 (core 0.3.0; the family review's C11; queue rows 39 b, found by
sdk-usda-gats, and 44 b, found by sdk-usda-esr; decided by Johannes on 2026-10-27): decision
1 patches httpcore's two pool methods only, `httpcore.ConnectionPool.handle_request` and
`httpcore.AsyncConnectionPool.handle_async_request`; httpx's transport methods are no
longer patched. Every default httpx transport sends through an httpcore pool, its proxies
included (`HTTPProxy` and `SOCKSProxy` are pools), and respx's default mocker patches the
same two methods and hands a route that passes through to the guard, so the refusal and
its edges are as above; a transport a test passes itself bypasses both, as before. Every
`MemoryCache` registers itself when it is built, and an autouse fixture clears every
registered cache before and after each test not marked `live`, beside the quota reset of
decision 4, so an answer one test cached never answers the route the next test mounts; a
`CacheBackend` of a source's own is not covered, and the fixture's docstring says so.
After each `live` test that ran, the plugin keeps every quota policy's source and
`snapshot().describe()`, the last reading kept past the resets of later offline tests,
and `pytest_terminal_summary` prints one line per policy, `quota after the live run:
<source>: <describe()>`: times, counts and the source, never a key, a host or a query.
The marker `rate_limited` names the quota pause it keeps as well. The plugin's docstrings
point to the decisions above instead of restating them; the edges stay listed here and
in ADR-0015.
Consumers: sdk-usda-gats and sdk-comtrade clear their caches in fixtures of their own,
and the plugin, which the template's `tests/conftest.py` enables in every source, is a
family invariant (ADR-0023, decisions 1 and 3 (a)). Conventions §10 states the clearing
and the summary from 1.20 on.

Amended 2026-10-27 (ADR-0024; core 0.3.0; the family review's C9; decided by Johannes on
2026-10-25 and 2026-10-27): the recorder's placeholder host and the verify's JSON-decoded,
percent-encoded and host forms leave core for sdk-cashctrl's recorder. The scrub replaces
each named value as given, and the verify searches the URL, the header values and the text
bodies for each as given, refusing the exchange with the location named; the "one JSON-aware
pass" and the placeholder host of the decision above no longer describe core. Conventions
§10 states it from 1.21 on.
