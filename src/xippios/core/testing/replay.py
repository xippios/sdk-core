"""Serve recorded fixtures through ``respx`` so unit tests never touch the network."""

from pathlib import Path

import httpx
import respx

from xippios.core.testing.fixtures import Fixture, load_fixture

__all__ = ["mount_fixture", "replay"]


def mount_fixture(router: respx.Router, fixture: Fixture) -> respx.Route:
    """Register a route answering the fixture's method, host and path with its response.

    Query parameters are not matched, because recorded ones may be scrubbed.
    """
    url = httpx.URL(fixture.request.url)
    route = router.route(method=fixture.request.method, host=url.host, path=url.path)
    route.mock(
        return_value=httpx.Response(
            fixture.response.status,
            headers=fixture.response.headers,
            content=fixture.response.content,
        )
    )
    return route


def replay(router: respx.Router, path: Path) -> respx.Route:
    """Load the fixture at ``path`` and mount it on ``router``."""
    return mount_fixture(router, load_fixture(path))
