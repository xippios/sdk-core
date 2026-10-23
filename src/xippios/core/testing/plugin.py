"""pytest plugin: the ``live`` gate, offline guarantees, and fixture-replay helpers.

Enable it from ``tests/conftest.py`` with ``pytest_plugins = ["xippios.core.testing.plugin"]``.

The whole session runs offline (ADR-0013): from configuration to the end, a request
through httpx's default transports is refused, at import, in a fixture of any scope
and in a test, unless a test marked ``network`` or ``live`` is running. Every test not
marked ``live`` also gets a rate limiter that never waits unless it is marked
``rate_limited``, and every ``EnvKeyAuth`` sends ``PLACEHOLDER_KEY``
(``placeholder_api_key``). A ``live`` test is skipped unless ``XIPPIOS_LIVE_TESTS=1``.
Every test, ``live`` or not, gets the ``httpx`` and ``httpcore`` logger levels back
when it ends.
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

from xippios.core.client import EnvKeyAuth, TokenBucket
from xippios.core.testing.fixtures import fixture_path
from xippios.core.testing.replay import ReplayFixture, replay

__all__ = ["LIVE_ENV", "PLACEHOLDER_KEY", "live_enabled"]

LIVE_ENV = "XIPPIOS_LIVE_TESTS"
PLACEHOLDER_KEY = "placeholder-for-fixture-replay"
"""The key every ``EnvKeyAuth`` sends in a test not marked ``live``."""
_KEY_ENVS = "xippios_placeholder_key_envs"
_REQUEST_LOGGERS = ("httpx", "httpcore")
_MARKERS = (
    "live: hits the real upstream; skipped unless XIPPIOS_LIVE_TESTS=1",
    "network: may reach the network through httpx's default transports; refused otherwise",
    "rate_limited: the rate limiter waits as configured; offline tests skip its waits otherwise",
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
    """httpx's default transports and httpcore's pools, refusing for the whole session.

    ``install`` patches ``httpx.HTTPTransport.handle_request``,
    ``httpx.AsyncHTTPTransport.handle_async_request``,
    ``httpcore.ConnectionPool.handle_request`` and
    ``httpcore.AsyncConnectionPool.handle_async_request`` once, when pytest is
    configured; while ``refusing`` is set, each raises ``RuntimeError`` naming the
    request's method and path, never its host or query (ADR-0005). Otherwise each hands
    the request to the method it replaced. ``pytest_runtest_setup`` clears ``refusing``
    for a test marked ``network`` or ``live`` and ``pytest_runtest_teardown`` sets it
    again, so a fixture of any scope is refused unless a marked test is being set up.

    ``respx``'s default mocker patches the same httpcore pool methods when a router
    starts, on top of these: a mocked or replayed request is answered by respx and never
    reaches them, and a route that passes through (``route.pass_through()``) lands on
    the refusal unless the test is marked ``network``. The transport methods refuse
    themselves only when nothing sits on top of the pool's; otherwise they hand the
    request down. A transport a test passes itself (``httpx.MockTransport``, FastAPI's
    ``TestClient``) never reaches any of them.
    """

    def __init__(self) -> None:
        self.refusing = True
        self._saved: list[tuple[type[Any], str, Any]] = []

    def install(self) -> None:
        """Patch the four methods; each replacement keeps the name respx looks for."""
        pool = _pool_guard(self, httpcore.ConnectionPool.handle_request)
        pool_async = _pool_guard_async(self, httpcore.AsyncConnectionPool.handle_async_request)
        patches: list[tuple[type[Any], str, Any]] = [
            (httpcore.ConnectionPool, "handle_request", pool),
            (httpcore.AsyncConnectionPool, "handle_async_request", pool_async),
            (
                httpx.HTTPTransport,
                "handle_request",
                _transport_guard(self, httpx.HTTPTransport.handle_request, pool),
            ),
            (
                httpx.AsyncHTTPTransport,
                "handle_async_request",
                _transport_guard_async(
                    self, httpx.AsyncHTTPTransport.handle_async_request, pool_async
                ),
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


def _transport_guard(
    guard: _NetworkGuard,
    original: Callable[[httpx.HTTPTransport, httpx.Request], httpx.Response],
    pool: _PoolSend,
) -> Callable[[httpx.HTTPTransport, httpx.Request], httpx.Response]:
    def handle_request(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        __tracebackhide__ = True
        if guard.refusing and httpcore.ConnectionPool.handle_request is pool:
            raise _refused(request.method, request.url.path)
        return original(self, request)

    return handle_request


def _transport_guard_async(
    guard: _NetworkGuard,
    original: Callable[[httpx.AsyncHTTPTransport, httpx.Request], Awaitable[httpx.Response]],
    pool: _AsyncPoolSend,
) -> Callable[[httpx.AsyncHTTPTransport, httpx.Request], Awaitable[httpx.Response]]:
    async def handle_async_request(
        self: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        __tracebackhide__ = True
        if guard.refusing and httpcore.AsyncConnectionPool.handle_async_request is pool:
            raise _refused(request.method, request.url.path)
        return await original(self, request)

    return handle_async_request


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ini option ``xippios_placeholder_key_envs``."""
    parser.addini(
        _KEY_ENVS,
        "environment variables set to the placeholder key in every test not marked live, "
        "e.g. COMTRADE_API_KEY",
        type="args",
        default=[],
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers and refuse the network for the session (``_NetworkGuard``)."""
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)
    guard = _NetworkGuard()
    guard.install()
    config.stash[_GUARD] = guard


def pytest_unconfigure(config: pytest.Config) -> None:
    """Give httpx and httpcore their own methods back."""
    guard = config.stash.get(_GUARD, None)
    if guard is not None:
        guard.uninstall()
        del config.stash[_GUARD]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    """Lift the refusal for a test marked ``network`` or ``live``, before its fixtures."""
    guard = item.config.stash.get(_GUARD, None)
    if guard is not None and any(item.get_closest_marker(name) for name in ("network", "live")):
        guard.refusing = False
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, None, None]:
    """Refuse the network again once the test's fixtures are torn down."""
    try:
        return (yield)
    finally:
        guard = item.config.stash.get(_GUARD, None)
        if guard is not None:
            guard.refusing = True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``live`` tests unless the gate is open."""
    if live_enabled():
        return
    skip = pytest.mark.skip(reason=f"live test; set {LIVE_ENV}=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


def _marked(request: pytest.FixtureRequest, name: str) -> bool:
    return request.node.get_closest_marker(name) is not None


async def _acquire_without_waiting(
    self: TokenBucket, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
) -> float:
    return 0.0


@pytest.fixture(autouse=True)
def _skip_rate_limit_waits(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Let a client's rate limiter never wait in a test not marked ``live``.

    ``TokenBucket.acquire`` returns ``0.0`` at once, without taking a token: replayed
    requests need no pace, and a source paced at one request a second waited a second
    per replayed request (sdk-comtrade, sdk-usda-psd). No token is taken either, so a
    limiter a source shares across its tests holds no debt from the replays when a
    ``live`` test in the same run uses it. Marked ``rate_limited`` or ``live``, a test
    keeps the limiter as configured.
    """
    if _marked(request, "live") or _marked(request, "rate_limited"):
        return
    monkeypatch.setattr(TokenBucket, "acquire", _acquire_without_waiting)


def _placeholder_key(self: EnvKeyAuth) -> str:
    return PLACEHOLDER_KEY


@pytest.fixture(autouse=True)
def placeholder_api_key(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str | None:
    """Every test but a live one sends the placeholder key, whatever the shell holds.

    The variables the ini option ``xippios_placeholder_key_envs`` names (e.g.
    ``xippios_placeholder_key_envs = COMTRADE_API_KEY``) are set to ``PLACEHOLDER_KEY``,
    and ``EnvKeyAuth.key``, through which every ``xippios.core`` auth class reads its
    key, returns it; both come back after the test.

    The key is pinned on the class, not on an auth object. A source may hold one auth
    object per tenant (sdk-cashctrl builds a ``BasicKeyAuth`` per organisation) and no
    module-level ``auth`` to patch, and an auth object resolves its key once and caches
    it, so a live test earlier in the run may have cached the real key on any of them;
    setting the variables alone would leave that key in place. A subclass that overrides
    ``key`` itself is not pinned.

    A ``live`` test is exempt: nothing is set or pinned, and it uses the key in the
    environment. There is no marker to lift the pin for one test: a test that needs
    real key resolution (a missing key raising ``ConfigError``, an explicit key winning)
    lives in a module that overrides this fixture with one that pins nothing::

        @pytest.fixture
        def placeholder_api_key() -> None:
            return None  # the tests in this module resolve keys themselves

    A ``placeholder_api_key`` fixture in a source's ``conftest.py`` overrides this one
    the same way, as pytest overrides any fixture by name.

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

    Building an MCP server sets both to ``WARNING`` (``quiet_request_logging``), so a
    test that builds one left them there for the rest of the run (sdk-cashctrl). Live
    tests included: restoring a level reaches nothing outside the process.
    """
    saved = {name: logging.getLogger(name).level for name in _REQUEST_LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


@pytest.fixture
def fixtures_dir(request: pytest.FixtureRequest) -> Path:
    """``tests/fixtures`` under the repository root."""
    return request.config.rootpath / "tests" / "fixtures"


@pytest.fixture
def replay_fixture(respx_mock: respx.MockRouter, fixtures_dir: Path) -> ReplayFixture:
    """Mount ``tests/fixtures/<endpoint>/<case>.json`` and return the route.

    Called as ``replay_fixture(endpoint, case, match_params=None)``, ``match_params`` by
    keyword; it names recorded query parameters a request must carry too, e.g.
    ``["countOnly"]`` (see ``xippios.core.testing.mount_fixture``). A test annotates the
    fixture as ``xippios.core.testing.ReplayFixture``.
    """

    def _replay(
        endpoint: str, case: str, *, match_params: Iterable[str] | None = None
    ) -> respx.Route:
        return replay(
            respx_mock, fixture_path(fixtures_dir, endpoint, case), match_params=match_params
        )

    return _replay
