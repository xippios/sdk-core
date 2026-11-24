# ADR-0035: Offline tests guaranteed by the plugin

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0013 ·
Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/475

## Context

Conventions §10 has unit tests run offline against recorded fixtures, and the definition of
done counts "unit tests pass offline" among the items CI enforces. Each source kept its
default run offline and free of real keys with fixtures of its own, which the template could
not reach once rendered, while a replayed request still waited on the limiter and a test that
forgot a fixture reached the upstream. This record states ADR-0013 with ADR-0015's and
ADR-0016's amendments of 2026-10-24 and its amendments of 2026-10-26, 2026-10-27 (three) and
2026-11-18 as they stand, and changes no decision; their history stays in ADR-0013.

## Decision

The plugin owns the offline guarantees.

1. **No network, for the whole session.** When pytest is configured, the plugin patches
   httpcore's two pool methods, `httpcore.ConnectionPool.handle_request` and
   `httpcore.AsyncConnectionPool.handle_async_request`, once; every default httpx transport
   sends through an httpcore pool, its proxies included (`HTTPProxy` and `SOCKSProxy` are
   pools). They raise `RuntimeError` naming the request's method and path, never its host or
   query (ADR-0030), while test modules are collected, in a fixture of any scope and in a
   test. `pytest_runtest_setup` sets the refusal for each test before its fixtures are set
   up, lifted for a test marked `network` or `live`, and `pytest_runtest_teardown` restores
   it after they are torn down. respx's default mocker patches the same two methods and
   hands a route that passes through (`route.pass_through()`) to the guard: a replayed or
   mocked request is answered by respx, and a route that passes through reaches the refusal
   like any other request unless the test is marked `network`. A transport a test passes
   itself bypasses both. `AsyncClient.download` streams through the client's pool and
   httpx's default transport, so an unmocked download in an offline test is refused with the
   same `RuntimeError`, and a `respx` route answers a mocked one. Johannes decided the two
   pool methods on 2026-10-27.
2. **No rate-limit wait.** For every test not marked `live`, by an autouse fixture,
   `TokenBucket.acquire` returns at once and takes no token, so a limiter a source shares
   across its tests holds no debt from the replays when a live test in the same run uses it.
   The marker `rate_limited` keeps the limiter for one test.
3. **The placeholder key.** `PLACEHOLDER_KEY = "placeholder-for-fixture-replay"`. For every
   test not marked `live`, the autouse fixture `placeholder_api_key` sets the variables the
   ini option `xippios_placeholder_key_envs` names to the placeholder and pins two methods on
   their classes: `EnvKeyAuth.key`, which every auth object of every tenant reads through,
   cached key or not, and `RenewingBearerAuth.credential`, so every credential that a token
   request reads is the placeholder, one given to the constructor included (ADR-0025,
   amendment 2026-11-18, point c). An auth subclass that overrides `key` reads its own way.
   The pin replaces the value and keeps the check: a variable unset or empty is still the
   `ConfigError` that names it, so a source tests that refusal without an override, and it
   names each variable a token request reads in the ini option, since one it leaves out is
   refused where the shell does not hold it, in CI say, and sent as the placeholder where it
   does. The fixture returns the placeholder, or `None` in a live test. It has the
   template's name, so a source's own fixture of that name overrides it, and a test module
   that needs real resolution overrides it with one that pins nothing, which lifts both
   pins. `EnvKeyAuth.apply` takes the request only and reads `self.key()` itself, and
   `sent_urls(route)` gives a test the URLs a route received as scrubbed strings, so neither
   the key nor a request carrying it has to sit in a test's frame.
4. **No quota pause, no quota left spent.** For every test not marked `live`, by an autouse
   fixture, every `QuotaPolicy`'s snapshot is forgotten before and after the test, so a
   replayed 429 cannot leave a source's module-level policy spent for the tests after it, a
   live one included; and, unless the test is marked `rate_limited`, the policy's pause does
   nothing: `before_request` and the hook `install` sets return at once, neither waiting nor
   raising `RateLimitError`. `observe` keeps the snapshot during the test, for a test that
   asserts it. The marker `rate_limited` keeps the pause for one test, as it keeps the
   limiter.
5. **The request loggers and the markers.** Every test, `live` or not, gets the `httpx`,
   `httpcore`, `httpx2` and `httpcore2` logger levels back when it ends, the four that
   `quiet_request_logging` sets to `WARNING`, since the `mcp` SDK 2.x builds its own HTTP
   client on httpx2, which logs each request's full URL at `INFO` as httpx does. The plugin
   registers `network` and `rate_limited` next to `live`, so a source running with
   `--strict-markers` needs no registration of its own.
6. **No answer cached across tests.** Every `MemoryCache` registers itself when it is built,
   and an autouse fixture clears every registered cache before and after each test not
   marked `live`, beside the quota reset of decision 4, so an answer one test cached never
   answers the route the next test mounts. A `CacheBackend` of a source's own is not
   covered, and the fixture's docstring says so.
7. **The quota after a live run.** After each `live` test that ran, the plugin keeps every
   quota policy's source and `snapshot().describe()`, the last reading kept past the resets
   of later offline tests, and `pytest_terminal_summary` prints one line per policy, `quota
   after the live run: <source>: <describe()>`: times, counts and the source, never a key, a
   host or a query.
8. **The family conformance check.** Core's `testing` extra ships the family conformance
   check, `xippios.core.testing.family`, and the template-rendered `tests/test_family.py`
   collects it with one line, `from xippios.core.testing.family import *  # noqa: F403`, so
   every source's default run, in its CI, tests what every source shares: the empty
   namespace levels, `py.typed` and `__version__`, the tasks the adapters serve, `Result[T]`
   and the agent docstrings, the README status table, the template tag and the core bound. A
   check added in a later core release reaches every source with the core update. It tests
   no write server: a source's write server is its own to test, and the write tasks stay in
   the task checks and the status table. The plugin registers the ini option
   `xippios_package`, which names the package under test where `src/xippios/` holds more
   than one `tasks.py`. Johannes decided on 2026-10-26 that a family conformance check ships
   in core's `testing` extra and runs in every source's CI, and on 2026-10-27 that it tests
   no write server.
9. **Replay and recording.**
   - Replay serves a fixture's body as recorded, a body the recorder cut (`truncated`)
     included. `match_params` names recorded query parameters whose recorded values a
     request must carry, a parameter whose recorded value holds `REDACTED` is refused by
     name, a parameter's absence cannot be expressed, and where two fixtures share a path
     the more specific one is mounted first, since `respx` tries routes in order.
   - `sent_urls`, `sent_query` and `recorded_query` redact by the one rule of
     `xippios.core.redaction` (ADR-0030, decision 1), and so does `sent_bodies(route)`,
     which gives each body a route received, oldest first: a JSON body (`application/json`
     or `...+json`) decoded, the value of every key that names a credential `REDACTED` at
     any depth; a form (`application/x-www-form-urlencoded`) as a mapping of its fields,
     blank values kept and a credential field `REDACTED`; and `None` for a request without a
     body. A body of another type, a body declared JSON that does not parse and a form that
     sends a field twice fail the test, the message naming the call and never the body. So
     a test asserts a write's body without keeping a request from `route.calls` in its
     frame, where a failing assertion or `pytest -l` would print it.
   - A request body goes as `data=` (form-encoded) or as `json=`, never both (conventions
     §6).
   - The recorder scrubs in memory, replaces each named secret value as given, refuses a
     binary body unless flagged, verifies the result and writes once (`Scrub`, conventions
     §10): the verify searches the URL, the header values and the text bodies for each
     named value as given, refusing the exchange with the location named. The backstops are
     recording only against synthetic or demo tenants, and the definition of done's grep of
     every fixture for key patterns before it is committed.

## Consequences

- A source names its key variables in its pytest configuration,
  `xippios_placeholder_key_envs = ["COMTRADE_API_KEY"]` under `[tool.pytest.ini_options]`,
  and a `placeholder_api_key` fixture it keeps overrides core's without error. sdk-cashctrl's
  keys are pinned by the class-level pin whichever organisation's auth object sends them.
- A test that must reach the network through httpx's default transports, a `respx` route
  that passes through included, is marked `network`; a live test is marked `live` and needs
  nothing else. Network access during collection or in a fixture outside a marked test moves
  into a marked test or a recorded fixture. A test that asserts a limiter's waits is marked
  `rate_limited`. A test module that checks how a key is resolved defines a
  `placeholder_api_key` fixture that pins nothing.
- What the plugin guarantees is exactly the above, and these are its edges:
  - The refusal's message names the method and path only. pytest's own failure report may
    still print httpx's request repr, query included; offline, the key in it is the
    placeholder.
  - The guard is active from `pytest_configure` on. A request made while a `conftest.py` is
    imported, before the plugin is configured, is not refused.
  - A fixture of wider scope runs under the marking of the test that sets it up, and its
    teardown under the marking of the last test that uses it. A live clean-up fixture is
    therefore function-scoped, or runs in the separate nightly `-m live` job.
  - The logger levels are saved per test, after fixtures of wider scope are set up; one of
    those that changes a level leaves it behind.
  - The quota snapshots are forgotten for every policy alive when a test not marked `live`
    starts and ends. A live test keeps them, so consecutive live tests share every policy's
    snapshot: a quota one live test spends makes the next one wait within the cap, or raise
    `RateLimitError` without sending.
  - The reset runs in a test's setup after the fixtures of wider scope, so a policy that such
    a fixture spends while it is set up is forgotten in the setup of the first test not
    marked `live` from then on, the one that set it up included, and never reaches that
    test's body; a fixture that hands an offline test a spent quota is function-scoped.
- The plugin's docstrings point to the decisions above instead of restating them; the edges
  stay listed here and in ADR-0037.
- Conventions §10 states the guarantees and names the markers.

Conventions §10 and §15, the definition of done's Adoption PR block, the README and the
docstrings of `xippios.core.testing`, the testing plugin, `MemoryCache`, `QuotaPolicy` and
`RenewingBearerAuth` state its decisions from 1.28 on.

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/475: in decision 3 the
variables that hold the placeholder are each secret variable of the source's `_client.ENV_VARS`,
a pattern such as `EXAMPLE_<NAME>_API_KEY` once for each reserved tenant of the `Tenants` that
`_client.py` holds, `EXAMPLE_DEMO_API_KEY` for `demo`, a pattern with its two consumers,
sdk-cashctrl and sdk-google-mail, the source being the one package with a `tasks.py` under
`src/xippios/`, so that a repository with none or several names no variable, and a source's own
fixture that sets one of them, a reserved tenant's recorded host say, runs after the plugin's
and keeps its value, while the ini option `xippios_placeholder_key_envs` leaves, since a source
declares its variables once and in the seven sources with a credential and no tenants the two
lists were equal, by part 6 of the answer; in decision 8 the ini option `xippios_package`
leaves, which no source set, so that the package under test is that one package and none or
several fail every test of the family check, by part 7 of the answer; and in the first
consequence a source declares its key variables secret in `_client.ENV_VARS` in place of its
pytest configuration, where pytest warns on an option that leaves, while decisions 1, 2, 4 to 7
and 9, the rest of decisions 3 and 8 and the other consequences stand as written.
