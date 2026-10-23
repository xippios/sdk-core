"""pytest plugin: the ``live`` marker, its gate, and fixture-replay helpers.

Enable it from ``tests/conftest.py`` with ``pytest_plugins = ["xippios.core.testing.plugin"]``.
"""

import os
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
import respx

from xippios.core.testing.fixtures import fixture_path
from xippios.core.testing.replay import replay

__all__ = ["LIVE_ENV", "live_enabled"]

LIVE_ENV = "XIPPIOS_LIVE_TESTS"
_MARKER = "live: hits the real upstream; skipped unless XIPPIOS_LIVE_TESTS=1"


def live_enabled() -> bool:
    """True when live tests are switched on through the environment."""
    return os.environ.get(LIVE_ENV) == "1"


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``live`` marker."""
    config.addinivalue_line("markers", _MARKER)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``live`` tests unless the gate is open."""
    if live_enabled():
        return
    skip = pytest.mark.skip(reason=f"live test; set {LIVE_ENV}=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


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
