"""pytest plugin: the ``live`` gate, the offline guarantees and fixture replay (conventions §10).

ADR-0013 decides each guarantee and lists its edges; ``pytest_plugins =
["xippios.core.testing.plugin"]`` in ``tests/conftest.py`` enables it.
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable, Generator, Iterable, Iterator
from pathlib import Path
from typing import Any

import httpcore
import httpx
import pytest
import respx

from xippios.core.client.auth import EnvKeyAuth
from xippios.core.client.cache import _clear_every_cache
from xippios.core.client.quota import QuotaPolicy, _every_policy, _reset_every_policy
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.testing.fixtures import fixture_path
from xippios.core.testing.replay import ReplayFixture, replay

__all__ = ["LIVE_ENV", "PLACEHOLDER_KEY", "live_enabled"]

LIVE_ENV = "XIPPIOS_LIVE_TESTS"
PLACEHOLDER_KEY = "placeholder-for-fixture-replay"
"""The key every ``EnvKeyAuth`` sends in a test not marked ``live``."""
_KEY_ENVS = "xippios_placeholder_key_envs"
PACKAGE_INI = "xippios_package"
"""The ini option naming the package the family check tests (``xippios.core.testing.family``)."""
_REQUEST_LOGGERS = ("httpx", "httpcore")
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
    # Method and path only: the host can name a tenant, the query can carry a key (ADR-0005).
    return RuntimeError(
        f"network access in an offline test: {method} {path}; replay a recorded fixture "
        "through respx, or mark the test 'network'"
    )


class _NetworkGuard:
    """httpcore's connection pools, patched once to refuse the network for the session.

    ADR-0013, decision 1, as amended 2026-10-27: the two pool methods, nothing of httpx's.
    """

    def __init__(self) -> None:
        self.refusing = True
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
        return original(self, request)

    return handle_request


def _pool_guard_async(guard: _NetworkGuard, original: _AsyncPoolSend) -> _AsyncPoolSend:
    async def handle_async_request(
        self: httpcore.AsyncConnectionPool, request: httpcore.Request
    ) -> httpcore.Response:
        __tracebackhide__ = True
        if guard.refusing:
            raise _refused(request.method.decode("ascii", "replace"), _target_path(request))
        return await original(self, request)

    return handle_async_request


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ini options ``xippios_placeholder_key_envs`` and ``xippios_package``."""
    parser.addini(
        _KEY_ENVS,
        "environment variables set to the placeholder key in every test not marked live, "
        "e.g. COMTRADE_API_KEY",
        type="args",
        default=[],
    )
    parser.addini(
        PACKAGE_INI,
        "import path of the source package the family check tests, e.g. xippios.usda.psd; "
        "unset, the one package with a tasks.py under src/xippios/ "
        "(xippios.core.testing.family)",
        type="string",
        default="",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers and refuse the network for the session (``_NetworkGuard``)."""
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)
    guard = _NetworkGuard()
    guard.install()
    config.stash[_GUARD] = guard
    config.stash[_QUOTA_LEFT] = {}


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give httpx and httpcore their own methods back."""
    guard = config.stash.get(_GUARD, None)
    if guard is not None:
        guard.uninstall()
        del config.stash[_GUARD]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    """Refuse or lift for this test before its fixtures: lifted when marked ``network`` or ``live``.

    The state is set for every test, not left over from the previous teardown.
    """
    guard = item.config.stash.get(_GUARD, None)
    if guard is not None:
        marked = any(item.get_closest_marker(name) is not None for name in ("network", "live"))
        guard.refusing = not marked
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, None, None]:
    """Refuse the network again once the test's fixtures are torn down.

    After a ``live`` test that ran, keep every quota policy's reading for the summary.
    """
    try:
        return (yield)
    finally:
        guard = item.config.stash.get(_GUARD, None)
        if guard is not None:
            guard.refusing = True
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
    """After a live run, one line per quota policy: what the live tests left of the quota.

    Times, counts and the policy's source only, never a key, a host or a query
    (ADR-0013, amended 2026-10-27).
    """
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

    ADR-0013, decision 2; a test marked ``rate_limited`` keeps the limiter.
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

    ADR-0013, decision 4 (ADR-0015); a test marked ``rate_limited`` keeps the pause.
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

    ADR-0013, amended 2026-10-27; a ``CacheBackend`` of the source's own is not cleared.
    """
    if _marked(request, "live"):
        yield
        return
    _clear_every_cache()
    yield
    _clear_every_cache()


def _placeholder_key(self: EnvKeyAuth) -> str:
    return PLACEHOLDER_KEY


@pytest.fixture(autouse=True)
def placeholder_api_key(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str | None:
    """Every test but a live one sends ``PLACEHOLDER_KEY``, whatever the shell holds.

    ADR-0013, decision 3: the variables ``xippios_placeholder_key_envs`` names hold it and
    ``EnvKeyAuth.key`` returns it; a module overrides this fixture to resolve keys itself.

    Returns:
        ``PLACEHOLDER_KEY``, or ``None`` in a live test, which uses the key in the
        environment.
    """
    if _marked(request, "live"):
        return None
    for name in request.config.getini(_KEY_ENVS):
        monkeypatch.setenv(name, PLACEHOLDER_KEY)
    monkeypatch.setattr(EnvKeyAuth, "key", _placeholder_key)
    return PLACEHOLDER_KEY


@pytest.fixture(autouse=True)
def _restore_request_logger_levels() -> Iterator[None]:
    """Give the ``httpx`` and ``httpcore`` loggers their levels back after every test.

    ADR-0013, the paragraph after decision 4: live tests included.
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
    """Mount ``tests/fixtures/<endpoint>/<case>.json`` and return the route.

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
