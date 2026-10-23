"""Serve recorded fixtures through ``respx`` so unit tests never touch the network."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx
import respx

from xippios.core.testing.fixtures import Fixture, load_fixture
from xippios.core.testing.scrub import REDACTED

__all__ = ["mount_fixture", "replay"]


def mount_fixture(
    router: respx.Router, fixture: Fixture, *, match_params: Iterable[str] | None = None
) -> respx.Route:
    """Register a route answering the fixture's method, host and path with its response.

    Query parameters are not matched unless named in ``match_params``, because recorded
    ones may be scrubbed; the request body is never matched. A test asserts what was
    sent from the route's calls, e.g. ``route.calls.last.request.content`` against
    ``fixture.request.body``.

    Args:
        router: The ``respx`` router, usually the ``respx_mock`` fixture.
        fixture: The recorded exchange.
        match_params: Names of recorded query parameters whose recorded values a request
            must carry too, e.g. ``["countOnly"]`` where two calls share one path.
            ``None`` matches method, host and path only.

    Raises:
        ValueError: A name in ``match_params`` is not a query parameter of the recorded
            URL, or was recorded as ``REDACTED``; the message names the parameter.
        TypeError: ``match_params`` is one string instead of a collection of names.
    """
    url = httpx.URL(fixture.request.url)
    pattern: dict[str, Any] = {"method": fixture.request.method, "host": url.host, "path": url.path}
    if match_params is not None:
        if isinstance(match_params, str):
            raise TypeError("match_params is a collection of names, e.g. ['countOnly']")
        recorded: list[tuple[str, str]] = []
        for name in match_params:
            values = url.params.get_list(name)
            if not values:
                raise ValueError(
                    f"match_params: {name!r} is not a query parameter of the recorded request"
                )
            if REDACTED in values:
                raise ValueError(
                    f"match_params: {name!r} was recorded as {REDACTED}; it cannot be matched"
                )
            recorded.extend((name, value) for value in values)
        if recorded:
            pattern["params"] = httpx.QueryParams(tuple(recorded))
    route = router.route(**pattern)
    route.mock(
        return_value=httpx.Response(
            fixture.response.status,
            headers=fixture.response.headers,
            content=fixture.response.content,
        )
    )
    return route


def replay(
    router: respx.Router, path: Path, *, match_params: Iterable[str] | None = None
) -> respx.Route:
    """Load the fixture at ``path`` and mount it on ``router``; see ``mount_fixture``."""
    return mount_fixture(router, load_fixture(path), match_params=match_params)
