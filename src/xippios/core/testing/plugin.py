"""pytest plugin: the ``live`` gate, offline guarantees, and fixture-replay helpers.

Enable it from ``tests/conftest.py`` with ``pytest_plugins = ["xippios.core.testing.plugin"]``.

Every test not marked ``live`` runs offline (ADR-0013): a request through httpx's
default transports is refused unless the test is marked ``network``, and a rate
limiter never waits unless the test is marked ``rate_limited``. A ``live`` test is
skipped unless ``XIPPIOS_LIVE_TESTS=1`` and is left as it is.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path

import httpcore
import httpx
import pytest
import respx

from xippios.core.client import TokenBucket
from xippios.core.testing.fixtures import fixture_path
from xippios.core.testing.replay import replay

__all__ = ["LIVE_ENV", "live_enabled"]

LIVE_ENV = "XIPPIOS_LIVE_TESTS"
_MARKERS = (
    "live: hits the real upstream; skipped unless XIPPIOS_LIVE_TESTS=1",
    "network: may reach the network through httpx's default transports; not refused offline",
    "rate_limited: the rate limiter waits as configured; offline tests skip its waits otherwise",
)

# The originals, taken when pytest loads the plugin and before any test patches them.
_SEND = httpx.HTTPTransport.handle_request
_SEND_ASYNC = httpx.AsyncHTTPTransport.handle_async_request
_POOL_SEND = httpcore.ConnectionPool.handle_request
_POOL_SEND_ASYNC = httpcore.AsyncConnectionPool.handle_async_request


def live_enabled() -> bool:
    """True when live tests are switched on through the environment."""
    return os.environ.get(LIVE_ENV) == "1"


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``live``, ``network`` and ``rate_limited`` markers."""
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)


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


def _refused(request: httpx.Request) -> RuntimeError:
    # Method and path only: the host can name a tenant, the query can carry a key (ADR-0005).
    return RuntimeError(
        f"network access in an offline test: {request.method} {request.url.path}; replay a "
        "recorded fixture through respx, or mark the test 'network'"
    )


def _send_offline(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
    __tracebackhide__ = True
    if httpcore.ConnectionPool.handle_request is _POOL_SEND:
        raise _refused(request)
    return _SEND(self, request)


async def _send_offline_async(
    self: httpx.AsyncHTTPTransport, request: httpx.Request
) -> httpx.Response:
    __tracebackhide__ = True
    if httpcore.AsyncConnectionPool.handle_async_request is _POOL_SEND_ASYNC:
        raise _refused(request)
    return await _SEND_ASYNC(self, request)


@pytest.fixture(autouse=True)
def _refuse_the_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse requests through httpx's default transports in a test not marked ``live``.

    ``httpx.HTTPTransport.handle_request`` and
    ``httpx.AsyncHTTPTransport.handle_async_request`` raise ``RuntimeError`` naming the
    request's method and path, never its host or query (ADR-0005). ``respx``'s default
    mocker answers below them, at httpcore's connection pool: while a ``respx`` router
    is active the pool's entry is respx's, and the request goes down to it, so replayed
    and mocked requests are answered as before. A transport a test passes itself
    (``httpx.MockTransport``, FastAPI's ``TestClient``) never reaches the default ones.
    A ``respx`` route that passes through (``route.pass_through()``) is respx's own
    explicit way out and is not refused. Marked ``network`` or ``live``, a test keeps
    the real transports.
    """
    if _marked(request, "live") or _marked(request, "network"):
        return
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _send_offline)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _send_offline_async)


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


@pytest.fixture
def fixtures_dir(request: pytest.FixtureRequest) -> Path:
    """``tests/fixtures`` under the repository root."""
    return request.config.rootpath / "tests" / "fixtures"


@pytest.fixture
def replay_fixture(respx_mock: respx.MockRouter, fixtures_dir: Path) -> Callable[..., respx.Route]:
    """Mount ``tests/fixtures/<endpoint>/<case>.json`` and return the route.

    Called as ``replay_fixture(endpoint, case, match_params=None)``; ``match_params``
    names recorded query parameters a request must carry too, e.g. ``["countOnly"]``
    (see ``xippios.core.testing.mount_fixture``).
    """

    def _replay(endpoint: str, case: str, match_params: Iterable[str] | None = None) -> respx.Route:
        return replay(
            respx_mock, fixture_path(fixtures_dir, endpoint, case), match_params=match_params
        )

    return _replay
