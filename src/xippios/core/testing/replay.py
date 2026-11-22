"""Serve recorded fixtures through ``respx`` so unit tests never touch the network."""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl

import httpx
import respx

from xippios.core.redaction import (
    REDACTED,
    _redact_value,
    is_credential_name,
    scrub_params,
    scrub_url,
)
from xippios.core.testing.fixtures import Fixture, _query_of, load_fixture

__all__ = ["ReplayFixture", "mount_fixture", "replay", "sent_bodies", "sent_query", "sent_urls"]

_mounted: list[tuple[Fixture, respx.Route, int]] | None = None
"""What ``mount_fixture`` mounted in the running test, each with its route's count of calls at
the mount, kept while the census of ``xippios.core.testing.built_answers`` listens, and
``None`` otherwise (ADR-0049)."""


class ReplayFixture(Protocol):
    """The type of the plugin's ``replay_fixture`` fixture, for a test's annotation.

    ``replay_fixture("api_get", "corn_2024")`` mounts
    ``tests/fixtures/api_get/corn_2024.json`` on the ``respx_mock`` router and returns
    the route; ``match_params`` and ``url`` are passed on to ``mount_fixture``. The
    directory is the wrapper function's, here sdk-usda-nass's ``api_get``, or the task's
    for an exchange recorded through a task (conventions §10).
    """

    def __call__(
        self,
        endpoint: str,
        case: str,
        *,
        match_params: Iterable[str] | None = None,
        url: str | None = None,
    ) -> respx.Route:
        """Mount the fixture ``<wrapper>/<case>.json`` and return its route.

        ``endpoint`` is the fixture's directory, the wrapper's name or the task's.
        """
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
    sent with ``sent_urls(route)`` or ``sent_query(route)`` for the URLs and
    ``sent_bodies(route)`` for the bodies, never with a request kept from
    ``route.calls``, which a failing assertion or ``pytest -l`` would print.

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
        url: Serve the recorded answer at this URL instead of the recorded one, for a
            state upstream answers alike there, within the fixture's operation or behind
            one gateway, e.g. an empty 404 recorded for one market year standing in for
            another year inside a range, or anywhere for a test that asserts only what
            was sent; never as one operation's answer for a state another operation was
            never seen in (conventions §10). The test says that the answer is not
            recorded there. The method stays the fixture's, and ``match_params`` then
            names query parameters of this URL. The answer is moved, never written by
            hand. ``None`` serves it where it was recorded.

    Raises:
        ValueError: A name in ``match_params`` is not a query parameter of the URL served
            (the recorded one, or ``url``), names a credential by the rule of
            ``xippios.core.redaction`` (``api_key``; ``key`` where a ``QueryKeyAuth``
            sends it; not a ``token`` name the source declared data), or its value holds
            ``REDACTED`` (whole, or a scrubbed secret inside it, or a data name recorded
            before its declaration); the message names the parameter.
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
            if is_credential_name(name):
                raise ValueError(
                    f"match_params: {name!r} names a credential, which a fixture holds as "
                    f"{REDACTED}; it cannot be matched"
                )
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
    if _mounted is not None:  # the census compares what the route answers with the recording
        # respx gives back the route it holds for an equal pattern: the calls from here on
        # are this recording's.
        _mounted.append((fixture, route, route.call_count))
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

    Each URL goes through ``scrub_url``, the rule of ``xippios.core.redaction``, so a key
    sent as a query parameter reads ``REDACTED`` (``key`` where a ``QueryKeyAuth`` sends
    it, ``api_key`` always). A test compares these strings instead of keeping a request from
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


_FORM = "application/x-www-form-urlencoded"


def sent_bodies(route: respx.Route) -> list[Any]:
    """The bodies ``route`` received, oldest first, decoded, credentials redacted.

    A body is read by its ``Content-Type``: JSON (``application/json`` or ``...+json``)
    as ``json.loads`` decodes it, the value of every key that names a credential
    ``REDACTED`` at any depth; a form (``application/x-www-form-urlencoded``) as a mapping
    of its fields, blank values kept and a credential field ``REDACTED``. The rule is that
    of ``xippios.core.redaction``, which ``sent_urls`` applies to the URLs, so no request
    sits in a test's frame, where a failing assertion or ``pytest -l`` would print it
    (https://github.com/xippios/sdk-core/issues/183). A request without a body gives
    ``None``, at its place. A test compares a body with the one it expects, e.g.
    ``sent_bodies(route)[-1] == {"name": "Corn", "n": "2"}``; a form's values are text.

    Args:
        route: A ``respx`` route, e.g. from ``replay_fixture`` or ``respx_mock.post(url)``.

    Raises:
        AssertionError: A body that is neither JSON nor a form, a body declared JSON that
            does not parse, or a form that sends a field more than once; the message
            names the call, counted from 1, and never the body.
    """
    return [_decoded(index, call.request) for index, call in enumerate(route.calls, start=1)]


def _decoded(index: int, request: httpx.Request) -> Any:
    """``request``'s body as ``sent_bodies`` gives it; see there."""
    content = request.content
    if not content:
        return None
    declared = request.headers.get("content-type")
    media = (declared or "").split(";", 1)[0].strip().lower()
    if media == "application/json" or media.endswith("+json"):
        try:
            payload = json.loads(content)
        except ValueError:
            raise AssertionError(
                f"call {index} sent a body declared {media} that is not JSON"
            ) from None
        return _redact_value(payload)
    if media == _FORM:
        # Percent-encoded UTF-8, as httpx encodes data=; a declared charset changes nothing.
        fields = parse_qsl(content.decode("utf-8"), keep_blank_values=True)
        names = [name for name, _ in fields]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise AssertionError(f"call {index} sent form fields more than once: {repeated}")
        return dict(scrub_params(fields))
    kind = f"a {media} body" if media else "a body without a content type"
    raise AssertionError(f"call {index} sent {kind}; sent_bodies decodes JSON and forms")
