"""The recorded fixture format: one JSON file per ``tests/fixtures/<endpoint>/<case>.json``.

A fixture holds the scrubbed request (method, URL, body and its content type) and the
decoded response. Bodies are stored as text; the headers that describe wire encoding
are dropped because the body is already decoded.
"""

import base64
import json
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from xippios.core.client.cache import strip_wire_headers
from xippios.core.models import utcnow
from xippios.core.testing.scrub import Scrub, _Scrubber

__all__ = [
    "Fixture",
    "FixtureRequest",
    "FixtureResponse",
    "fixture_from_response",
    "fixture_path",
    "load_fixture",
    "recorded_query",
    "response_from_fixture",
    "write_fixture",
]


class FixtureRequest(BaseModel):
    """The request that produced the fixture, scrubbed.

    Attributes:
        method: HTTP method.
        url: Request URL, credentials and whatever the ``Scrub`` names removed.
        body: The request body as UTF-8 text, scrubbed, e.g. ``"a=1&b=2"`` for a form
            or the JSON text sent; base64 when ``body_base64`` is set; ``None`` when the
            request had no body. Fixtures written by xippios-core 0.1.0 have none.
        body_base64: True when the body was not UTF-8 text and was stored as it came.
        content_type: The request's ``Content-Type``, e.g.
            ``"application/x-www-form-urlencoded"``; ``None`` when it sent none.
    """

    model_config = ConfigDict(frozen=True)

    method: str
    url: str
    body: str | None = None
    body_base64: bool = False
    content_type: str | None = None


class FixtureResponse(BaseModel):
    """The recorded response.

    Attributes:
        status: HTTP status code.
        headers: Response headers minus wire-encoding ones, credentials scrubbed.
        body: Decoded body text, or base64 when ``body_base64`` is set.
        body_base64: True when the body was not valid UTF-8 text.
    """

    model_config = ConfigDict(frozen=True)

    status: int
    headers: list[tuple[str, str]]
    body: str
    body_base64: bool = False

    @property
    def content(self) -> bytes:
        """The body as bytes."""
        if self.body_base64:
            return base64.b64decode(self.body)
        return self.body.encode("utf-8")


class Fixture(BaseModel):
    """One recorded exchange."""

    model_config = ConfigDict(frozen=True)

    recorded_at: datetime
    request: FixtureRequest
    response: FixtureResponse


def fixture_path(root: Path, endpoint: str, case: str) -> Path:
    """``<root>/<endpoint>/<case>.json``, the family's fixture layout."""
    return root / endpoint / f"{case}.json"


def fixture_from_response(response: httpx.Response, *, scrub: Scrub | None = None) -> Fixture:
    r"""Build a scrubbed ``Fixture`` in memory from a fully read ``httpx.Response``.

    Credentials are always scrubbed (``scrub_url``, ``scrub_headers``). ``scrub`` adds
    the placeholder host, the secret values and the rewrite hook, and decides about a
    binary body; ``None`` is ``Scrub()``: host kept, nothing else replaced, a binary
    body refused. With ``host`` or ``secrets`` set, the result is verified before it is
    returned: the original host or a secret value still present anywhere, a JSON body
    decoded included (e.g. behind a ``\u`` escape), refuses the exchange.

    Args:
        response: The response, with the request that produced it.
        scrub: What else to remove before anything is kept, e.g.
            ``Scrub(host="demo.example.test", secrets=[tenant])``.

    Raises:
        ValueError: The request or response body is not UTF-8 text and ``scrub`` does
            not set ``allow_binary``; or the original host or a secret value survived
            the scrub (the message names which and where, never the value).
    """
    request = response.request
    scrubber = _Scrubber(scrub if scrub is not None else Scrub(), request.url)
    request_body: str | None = None
    request_base64 = False
    if request.content:
        request_body, request_base64 = scrubber.body(request.content)
    content_type = request.headers.get("content-type")
    body, is_base64 = scrubber.body(response.content)
    fixture = Fixture(
        recorded_at=utcnow(),
        request=FixtureRequest(
            method=request.method,
            url=scrubber.url(request.url),
            body=request_body,
            body_base64=request_base64,
            content_type=scrubber.text(content_type) if content_type is not None else None,
        ),
        response=FixtureResponse(
            status=response.status_code,
            headers=scrubber.headers(strip_wire_headers(response.headers.multi_items())),
            body=body,
            body_base64=is_base64,
        ),
    )
    kept = fixture.request.content_type
    scrubber.verify(
        fixture.request.url,
        [("content-type", kept)] if kept is not None else [],
        None if fixture.request.body_base64 else fixture.request.body,
        fixture.response.headers,
        None if fixture.response.body_base64 else fixture.response.body,
    )
    return fixture


def write_fixture(response: httpx.Response, path: Path, *, scrub: Scrub | None = None) -> Fixture:
    """Scrub ``response`` in memory, then write it to ``path`` as JSON, creating directories.

    The file is written once, already scrubbed; a refusal writes nothing.

    Args:
        response: The response, with the request that produced it.
        path: Destination file, usually from ``fixture_path``.
        scrub: What else to remove besides credentials; see ``fixture_from_response``.

    Raises:
        ValueError: A binary body without ``Scrub(allow_binary=True)``, or the original
            host or a secret value left after the scrub; see ``fixture_from_response``.
    """
    fixture = fixture_from_response(response, scrub=scrub)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixture.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return fixture


def load_fixture(path: Path) -> Fixture:
    """Read a fixture written by ``write_fixture``."""
    return Fixture.model_validate_json(path.read_text(encoding="utf-8"))


def response_from_fixture(fixture: Fixture) -> httpx.Response:
    """The recorded response as an ``httpx.Response``, without a request sent.

    Its request is the recorded method and URL, scrubbed, so a test can hand it to a
    source's ``classify`` or to ``error_from_response``, which read both, e.g.
    ``classify(response_from_fixture(load_fixture(path)))``. The recorded request body
    is not attached.

    Args:
        fixture: The recorded exchange, e.g. from ``load_fixture``.
    """
    return httpx.Response(
        fixture.response.status,
        headers=fixture.response.headers,
        content=fixture.response.content,
        request=httpx.Request(fixture.request.method, fixture.request.url),
    )


def recorded_query(fixture: Fixture) -> dict[str, str]:
    """The query parameters the fixture was recorded with, as the recorder scrubbed them.

    A credential reads ``REDACTED``. The companion of ``sent_query``: a test compares
    what a task sent with what was recorded, ``sent_query(route) ==
    recorded_query(fixture)``.

    Args:
        fixture: The recorded exchange, e.g. from ``load_fixture``.

    Raises:
        AssertionError: A parameter was recorded more than once; read its values with
            ``httpx.URL(fixture.request.url).params.get_list(name)``.
    """
    return _query_of(fixture.request.url)


def _query_of(url: str) -> dict[str, str]:
    """``url``'s query as a mapping, blank values kept; a repeated name fails the test."""
    params = httpx.URL(url).params
    repeated = sorted({name for name in params if len(params.get_list(name)) > 1})
    if repeated:
        raise AssertionError(
            f"query parameters sent more than once: {repeated}; read them with "
            "httpx.URL(url).params.get_list(name)"
        )
    return dict(params)
