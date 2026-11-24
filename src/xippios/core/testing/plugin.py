"""pytest plugin: the ``live`` gate, the offline guarantees and fixture replay (conventions §10).

ADR-0035 decides each guarantee and lists its edges; ``pytest_plugins =
["xippios.core.testing.plugin"]`` in ``tests/conftest.py`` enables it.
"""

import asyncio
import importlib
import logging
import os
import re
import threading
from collections import Counter
from collections.abc import Awaitable, Callable, Generator, Iterable, Iterator
from pathlib import Path
from typing import Any

import httpcore
import httpx
import pytest
import respx

from xippios.core.client.auth import EnvKeyAuth, RenewingBearerAuth
from xippios.core.client.cache import _clear_every_cache
from xippios.core.client.quota import QuotaPolicy, _every_policy, _reset_every_policy
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.contract import EnvVar
from xippios.core.tenants import Tenants, _tenants_declared
from xippios.core.testing.built_answers import _install_census
from xippios.core.testing.fixtures import fixture_path
from xippios.core.testing.replay import ReplayFixture, replay

__all__ = ["LIVE_ENV", "PLACEHOLDER_KEY", "live_enabled"]

LIVE_ENV = "XIPPIOS_LIVE_TESTS"
PLACEHOLDER_KEY = "placeholder-for-fixture-replay"
"""The key every ``EnvKeyAuth`` sends in a test not marked ``live``, and every credential that a
``RenewingBearerAuth`` reads."""
_TENANT_NAME = re.compile(r"<[A-Z]+>")
"""The placeholder of a variable per tenant in an ``EnvVar``'s pattern, ``<NAME>``."""
_REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")
"""The loggers ``quiet_request_logging`` sets, the mcp SDK's httpx2 and httpcore2 among them."""
_MARKERS = (
    "live: hits the real upstream; skipped unless XIPPIOS_LIVE_TESTS=1",
    "network: may reach the network through httpx's default transports; refused otherwise",
    "rate_limited: the rate limiter waits and the quota policy pauses as configured; offline "
    "tests skip both otherwise",
)


def live_enabled() -> bool:
    """True when live tests are switched on through the environment."""
    return os.environ.get(LIVE_ENV) == "1"


def _refused(method: str, path: str) -> RuntimeError:
    # Method and path only: the host can name a tenant, the query can carry a key (ADR-0030).
    return RuntimeError(
        f"network access in an offline test: {method} {path}; replay a recorded fixture "
        "through respx, or mark the test 'network'"
    )


class _LiveRequests:
    """The requests that live tests handed to httpcore's pools, by host, for the summary.

    Counted from a live test's setup to its teardown, the gate open, answered or not: every
    hop of a redirect and every attempt of a retry is one. A request that ``respx`` or a
    transport of the test's own answers never reaches a pool and is not counted.
    """

    def __init__(self) -> None:
        self.counting = False
        """A live test is set up, running or being torn down, the gate open."""
        self.ran = False
        """A live test was set up with the gate open, one that skips at its setup included:
        the summary prints the line, ``0`` where nothing was sent."""
        self._by_host: Counter[str] = Counter()
        self._lock = threading.Lock()

    def count(self, request: httpcore.Request) -> None:
        """Count ``request`` under its host while a live test runs."""
        if self.counting:
            host = request.url.host.decode("ascii", "replace")
            with self._lock:
                self._by_host[host] += 1

    def line(self, *, name_hosts: bool) -> str:
        """``requests sent by the live run: <n>``, then each host with its count, by name.

        Without ``name_hosts`` no host is named: a run that built a ``Tenants`` may have
        sent to a tenant's host, which names the tenant (ADR-0030, decision 4).
        """
        total = sum(self._by_host.values())
        line = f"requests sent by the live run: {total}"
        if not total:
            return line
        if not name_hosts:
            return f"{line} (hosts not named: tenants declared)"
        hosts = ", ".join(f"{host}: {sent}" for host, sent in sorted(self._by_host.items()))
        return f"{line} ({hosts})"


class _NetworkGuard:
    """httpcore's connection pools, patched once to refuse the network for the session.

    ADR-0035, decision 1: the two pool methods, nothing of httpx's. What a live test sends
    through them is counted in ``live``.
    """

    def __init__(self) -> None:
        self.refusing = True
        self.live = _LiveRequests()
        self._saved: list[tuple[type[Any], str, Any]] = []

    def install(self) -> None:
        """Patch the two pool methods; each replacement keeps the name respx looks for."""
        patches: list[tuple[type[Any], str, Any]] = [
            (
                httpcore.ConnectionPool,
                "handle_request",
                _pool_guard(self, httpcore.ConnectionPool.handle_request),
            ),
            (
                httpcore.AsyncConnectionPool,
                "handle_async_request",
                _pool_guard_async(self, httpcore.AsyncConnectionPool.handle_async_request),
            ),
        ]
        for owner, name, replacement in patches:
            self._saved.append((owner, name, getattr(owner, name)))
            setattr(owner, name, replacement)

    def uninstall(self) -> None:
        """Put back what ``install`` replaced, in reverse order."""
        while self._saved:
            owner, name, original = self._saved.pop()
            setattr(owner, name, original)


_GUARD = pytest.StashKey[_NetworkGuard]()
_QUOTA_LEFT = pytest.StashKey[dict[int, tuple[str, str]]]()
"""Per live policy, its source and its last quota reading after a ``live`` test."""
_SECRETS = pytest.StashKey[tuple[str, ...]]()
"""The variables that hold ``PLACEHOLDER_KEY`` in a test not marked ``live``, read once."""

_PoolSend = Callable[[httpcore.ConnectionPool, httpcore.Request], httpcore.Response]
_AsyncPoolSend = Callable[
    [httpcore.AsyncConnectionPool, httpcore.Request], Awaitable[httpcore.Response]
]


def _target_path(request: httpcore.Request) -> str:
    return request.url.target.split(b"?", 1)[0].decode("ascii", "replace")


def _pool_guard(guard: _NetworkGuard, original: _PoolSend) -> _PoolSend:
    def handle_request(
        self: httpcore.ConnectionPool, request: httpcore.Request
    ) -> httpcore.Response:
        __tracebackhide__ = True
        if guard.refusing:
            raise _refused(request.method.decode("ascii", "replace"), _target_path(request))
        guard.live.count(request)
        return original(self, request)

    return handle_request


def _pool_guard_async(guard: _NetworkGuard, original: _AsyncPoolSend) -> _AsyncPoolSend:
    async def handle_async_request(
        self: httpcore.AsyncConnectionPool, request: httpcore.Request
    ) -> httpcore.Response:
        __tracebackhide__ = True
        if guard.refusing:
            raise _refused(request.method.decode("ascii", "replace"), _target_path(request))
        guard.live.count(request)
        return await original(self, request)

    return handle_async_request


def _source_packages(root: Path) -> list[Path]:
    """Each directory under ``<root>/src/xippios/`` that holds a ``tasks.py``, in order.

    The layout every source has, ``src/xippios/example/tasks.py`` for ``xippios.example``;
    one of them is the source package that the plugin and the family check read.

    Args:
        root: pytest's rootdir, the repository's root.
    """
    return sorted(path.parent for path in (root / "src" / "xippios").rglob("tasks.py"))


def _secret_variables(root: Path) -> tuple[str, ...]:
    """The variables that hold ``PLACEHOLDER_KEY`` in a test not marked ``live`` (ADR-0035).

    Each secret entry of the source's ``_client.ENV_VARS``: a name as it stands, and a
    pattern such as ``EXAMPLE_<NAME>_API_KEY`` once for each reserved tenant of the
    ``Tenants`` that ``_client`` holds, ``EXAMPLE_DEMO_API_KEY`` for ``demo``, since a test
    reaches no other tenant. The source is the one package with a ``tasks.py`` under
    ``src/xippios/``; a repository with none, core's own say, or with several names none.

    Args:
        root: pytest's rootdir, the repository's root.
    """
    found = _source_packages(root)
    if len(found) != 1:
        return ()
    package = ".".join(found[0].relative_to(root / "src").parts)
    client = importlib.import_module(f"{package}._client")
    reserved = [
        name
        for value in vars(client).values()
        if isinstance(value, Tenants)
        for name in value.reserved
    ]
    names: list[str] = []
    for entry in getattr(client, "ENV_VARS", ()):
        if not (isinstance(entry, EnvVar) and entry.secret):
            continue
        if _TENANT_NAME.search(entry.name_or_pattern) is None:
            names.append(entry.name_or_pattern)
        else:
            names += [_TENANT_NAME.sub(name.upper(), entry.name_or_pattern) for name in reserved]
    return tuple(dict.fromkeys(names))


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers and refuse the network for the session (``_NetworkGuard``).

    It registers the census of replays too, which listens only in a run that collects the
    census test of ``xippios.core.testing.built_answers`` (ADR-0064).
    """
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)
    guard = _NetworkGuard()
    guard.install()
    config.stash[_GUARD] = guard
    config.stash[_QUOTA_LEFT] = {}
    _install_census(config)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give httpx and httpcore their own methods back."""
    guard = config.stash.get(_GUARD, None)
    if guard is not None:
        guard.uninstall()
        del config.stash[_GUARD]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    """Refuse or lift for this test before its fixtures: lifted when marked ``network`` or ``live``.

    The state is set for every test, not left over from the previous teardown. A ``live``
    test with the gate open has its requests counted from here on.
    """
    guard = item.config.stash.get(_GUARD, None)
    if guard is not None:
        marked = any(item.get_closest_marker(name) is not None for name in ("network", "live"))
        guard.refusing = not marked
        live = live_enabled() and item.get_closest_marker("live") is not None
        guard.live.counting = live
        guard.live.ran = guard.live.ran or live
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, None, None]:
    """Refuse the network again, and stop counting, once the test's fixtures are torn down.

    After a ``live`` test that ran, keep every quota policy's reading for the summary.
    """
    try:
        return (yield)
    finally:
        guard = item.config.stash.get(_GUARD, None)
        if guard is not None:
            guard.refusing = True
            guard.live.counting = False
        if live_enabled() and item.get_closest_marker("live") is not None:
            _keep_quota_left(item.config)


def _keep_quota_left(config: pytest.Config) -> None:
    """Each policy's source and ``describe()``, kept past the resets of later offline tests."""
    kept = config.stash.setdefault(_QUOTA_LEFT, {})
    for policy in _every_policy():
        snapshot = policy.snapshot()
        if snapshot is not None:
            kept[id(policy)] = (policy.source or "(no source)", snapshot.describe())


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """After a live run, the requests its live tests sent, then what they left of each quota.

    The requests by host (``_LiveRequests``), no host where the run built a ``Tenants``
    (``_tenants_declared``), never a path or a query (sdk-core#335). It follows a run in
    which a live test was set up with the gate open, one that skips at its setup included,
    so a run whose live tests all skip prints a count of 0; any other run prints no such
    line. Then one line per quota
    policy: times, counts and the policy's source only, never a key, a host or a query
    (ADR-0035, decision 7).
    """
    guard = config.stash.get(_GUARD, None)
    if guard is not None and guard.live.ran:
        terminalreporter.write_line(guard.live.line(name_hosts=not _tenants_declared()))
    for source, left in config.stash.get(_QUOTA_LEFT, {}).values():
        terminalreporter.write_line(f"quota after the live run: {source}: {left}")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests marked ``live`` unless the gate is open.

    The marker decides, not a keyword: a directory or a class named ``live`` does not
    make its tests live.
    """
    if live_enabled():
        return
    skip = pytest.mark.skip(reason=f"live test; set {LIVE_ENV}=1 to run")
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip)


def _marked(request: pytest.FixtureRequest, name: str) -> bool:
    return request.node.get_closest_marker(name) is not None


async def _acquire_without_waiting(
    self: TokenBucket, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
) -> float:
    return 0.0


@pytest.fixture(autouse=True)
def _skip_rate_limit_waits(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """A client's rate limiter neither waits nor takes a token in a test not marked ``live``.

    ADR-0035, decision 2; a test marked ``rate_limited`` keeps the limiter.
    """
    if _marked(request, "live") or _marked(request, "rate_limited"):
        return
    monkeypatch.setattr(TokenBucket, "acquire", _acquire_without_waiting)


async def _pause_without_waiting(self: QuotaPolicy, request: httpx.Request) -> None:
    return None


@pytest.fixture(autouse=True)
def _skip_quota_pauses(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """No quota policy pauses, refuses or stays spent in a test not marked ``live``.

    ADR-0035, decision 4 (ADR-0037); a test marked ``rate_limited`` keeps the pause.
    """
    if _marked(request, "live"):
        yield
        return
    _reset_every_policy()
    if not _marked(request, "rate_limited"):
        monkeypatch.setattr(QuotaPolicy, "_pause", _pause_without_waiting)
    yield
    _reset_every_policy()


@pytest.fixture(autouse=True)
def _clear_response_caches(request: pytest.FixtureRequest) -> Iterator[None]:
    """Every ``MemoryCache`` starts and ends a test not marked ``live`` empty.

    ADR-0035, decision 6; a ``CacheBackend`` of the source's own is not cleared.
    """
    if _marked(request, "live"):
        yield
        return
    _clear_every_cache()
    yield
    _clear_every_cache()


def _placeholder_key(self: EnvKeyAuth) -> str:
    return PLACEHOLDER_KEY


def _placeholder_credential(self: RenewingBearerAuth, name: str) -> str:
    """``PLACEHOLDER_KEY`` for a credential the auth finds, its ``ConfigError`` for another."""
    if not self._holds(name):
        raise self._unset(name)
    return PLACEHOLDER_KEY


@pytest.fixture(autouse=True)
def placeholder_api_key(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str | None:
    """Every test but a live one sends ``PLACEHOLDER_KEY``, whatever the shell holds.

    ADR-0035, decision 3: the secret variables of the source's ``_client.ENV_VARS`` hold
    it, a pattern's once for each reserved tenant (``_secret_variables``),
    ``EnvKeyAuth.key`` returns it, and ``RenewingBearerAuth.credential`` returns it for
    every credential a token request reads, one given to the constructor included, and
    still raises ``ConfigError`` for a variable unset or empty. A module overrides this
    fixture to resolve both itself.

    Returns:
        ``PLACEHOLDER_KEY``, or ``None`` in a live test, which uses the key in the
        environment.
    """
    if _marked(request, "live"):
        return None
    config = request.config
    if _SECRETS not in config.stash:
        config.stash[_SECRETS] = _secret_variables(config.rootpath)
    for name in config.stash[_SECRETS]:
        monkeypatch.setenv(name, PLACEHOLDER_KEY)
    monkeypatch.setattr(EnvKeyAuth, "key", _placeholder_key)
    monkeypatch.setattr(RenewingBearerAuth, "credential", _placeholder_credential)
    return PLACEHOLDER_KEY


@pytest.fixture(autouse=True)
def _restore_request_logger_levels() -> Iterator[None]:
    """Give the request loggers their levels back after every test.

    The four that ``quiet_request_logging`` sets: ``httpx``, ``httpcore``, ``httpx2`` and
    ``httpcore2``.

    ADR-0035, decision 5: live tests included.
    """
    saved = {name: logging.getLogger(name).level for name in _REQUEST_LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    """Run every ``anyio`` test on asyncio, the backend the family's client runs on.

    anyio's own fixture runs each test once per installed backend, trio included where
    it is installed; every source's ``conftest.py`` pinned asyncio with a fixture of its
    own. Module-scoped, as anyio's is, so a module-scoped async fixture can use it. A
    ``conftest.py`` or a test module that defines ``anyio_backend`` overrides this one.

    It wins over anyio's when the plugin is enabled as every source enables it, through
    ``pytest_plugins`` in ``tests/conftest.py``, which registers it after anyio's. Loaded
    earlier, with ``-p xippios.core.testing.plugin``, anyio's comes last and decides.
    """
    return "asyncio"


@pytest.fixture
def fixtures_dir(request: pytest.FixtureRequest) -> Path:
    """``tests/fixtures`` under the repository root."""
    return request.config.rootpath / "tests" / "fixtures"


@pytest.fixture
def replay_fixture(respx_mock: respx.MockRouter, fixtures_dir: Path) -> ReplayFixture:
    """Mount ``tests/fixtures/<wrapper>/<case>.json`` and return the route.

    The directory is the wrapper function's, or the task's for an exchange recorded
    through a task (conventions §10), passed as ``endpoint``, the parameter's name.
    Called as ``replay_fixture(endpoint, case, match_params=None, url=None)``, the last
    two by keyword: ``match_params`` names recorded query parameters a request must carry
    too, e.g. ``["countOnly"]``, and ``url`` serves the recorded answer at another URL,
    e.g. a recorded empty 404 at the path of another year (see
    ``xippios.core.testing.mount_fixture``). A test annotates the fixture as
    ``xippios.core.testing.ReplayFixture``.
    """

    def _replay(
        endpoint: str,
        case: str,
        *,
        match_params: Iterable[str] | None = None,
        url: str | None = None,
    ) -> respx.Route:
        return replay(
            respx_mock,
            fixture_path(fixtures_dir, endpoint, case),
            match_params=match_params,
            url=url,
        )

    return _replay
