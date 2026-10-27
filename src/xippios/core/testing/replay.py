"""Serve recorded fixtures through ``respx`` so unit tests never touch the network."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

import httpx
import respx

from xippios.core.testing.fixtures import Fixture, _query_of, load_fixture
from xippios.core.testing.scrub import REDACTED, scrub_url

__all__ = ["ReplayFixture", "mount_fixture", "replay", "sent_query", "sent_urls"]


class ReplayFixture(Protocol):
    """The type of the plugin's ``replay_fixture`` fixture, for a test's annotation.

    ``replay_fixture("api_GET", "corn_2024")`` mounts
    ``tests/fixtures/api_GET/corn_2024.json`` on the ``respx_mock`` router and returns
    the route; ``match_params`` and ``url`` are passed on to ``mount_fixture``.
    """

    def __call__(
        self,
        endpoint: str,
        case: str,
        *,
        match_params: Iterable[str] | None = None,
        url: str | None = None,
    ) -> respx.Route:
        """Mount the fixture ``<endpoint>/<case>.json`` and return its route."""
        ...


def mount_fixture(
    router: respx.Router,
    fixture: Fixture,
    *,
    match_params: Iterable[str] | None = None,
    url: str | None = None,
) -> respx.Route:
    """Register a route answering the fixture's method, host and path with its response.

    Query parameters are not matched unless named in ``match_params``, because recorded
    ones may be scrubbed; the request body is never matched. A test asserts what was
    sent from the route's calls: the URLs with ``sent_urls(route)``, the body inline,
    e.g. ``route.calls.last.request.content`` against ``fixture.request.body``.

    ``match_params`` cannot say that a parameter must be absent. Where one recorded
    request carries a parameter that another on the same path lacks (a
    ``countOnly=true`` count and the data call), mount the more specific fixture, with
    ``match_params``, first: ``respx`` tries routes in the order they were added, and the
    first that matches answers.

    Args:
        router: The ``respx`` router, usually the ``respx_mock`` fixture.
        fixture: The recorded exchange.
        match_params: Names of recorded query parameters whose recorded values a request
            must carry too, e.g. ``["countOnly"]`` where two calls share one path.
            ``None`` matches method, host and path only.
        url: Serve the recorded answer at this URL instead of the recorded one, e.g. an
            empty 404 recorded for one market year standing in for another year inside a
            range; the method stays the fixture's, and ``match_params`` then names query
            parameters of this URL. The answer is moved, never written by hand. ``None``
            serves it where it was recorded.

    Raises:
        ValueError: A name in ``match_params`` is not a query parameter of the URL served
            (the recorded one, or ``url``), or its value holds ``REDACTED`` (whole, or a
            scrubbed secret inside it); the message names the parameter.
        TypeError: ``match_params`` is one string instead of a collection of names.
    """
    served = httpx.URL(fixture.request.url if url is None else url)
    pattern: dict[str, Any] = {
        "method": fixture.request.method,
        "host": served.host,
        "path": served.path,
    }
    if match_params is not None:
        if isinstance(match_params, str):
            raise TypeError("match_params is a collection of names, e.g. ['countOnly']")
        recorded: list[tuple[str, str]] = []
        for name in match_params:
            values = served.params.get_list(name)
            if not values:
                where = "the recorded request" if url is None else "the URL given"
                raise ValueError(f"match_params: {name!r} is not a query parameter of {where}")
            if any(REDACTED in value for value in values):
                raise ValueError(
                    f"match_params: {name!r} was recorded as {REDACTED}, in whole or in part; "
                    "it cannot be matched"
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
    router: respx.Router,
    path: Path,
    *,
    match_params: Iterable[str] | None = None,
    url: str | None = None,
) -> respx.Route:
    """Load the fixture at ``path`` and mount it on ``router``; see ``mount_fixture``."""
    return mount_fixture(router, load_fixture(path), match_params=match_params, url=url)


def sent_urls(route: respx.Route) -> list[str]:
    """The URLs ``route`` received, oldest first, as text with credentials redacted.

    Each URL goes through ``scrub_url``, so a key sent as a query parameter reads
    ``REDACTED``. A test compares these strings instead of keeping a request from
    ``route.calls`` in its own frame, where a failing assertion or ``pytest -l`` would
    print it with its URL, key included.

    Args:
        route: A ``respx`` route, e.g. from ``replay_fixture`` or ``respx_mock.get(url)``.
    """
    return [scrub_url(call.request.url) for call in route.calls]


def sent_query(route: respx.Route) -> dict[str, str]:
    """The query of the last request ``route`` received, credentials redacted.

    Read from ``sent_urls(route)``, so a key sent as a query parameter reads
    ``REDACTED`` and no request carrying it sits in the test's frame; blank values are
    kept. Compare it with a mapping, or with ``recorded_query(fixture)``. Each call's
    query, oldest first: ``[httpx.URL(url).params for url in sent_urls(route)]``.

    Args:
        route: A ``respx`` route, e.g. from ``replay_fixture``.

    Raises:
        AssertionError: The route received no request, or a parameter was sent more
            than once (read its values with ``httpx.URL(...).params.get_list(name)``).
    """
    urls = sent_urls(route)
    if not urls:
        raise AssertionError("the route received no request")
    return _query_of(urls[-1])
