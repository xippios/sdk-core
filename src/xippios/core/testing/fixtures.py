"""The recorded fixture format: one JSON file per ``tests/fixtures/<endpoint>/<case>.json``.

A fixture holds the scrubbed request (method, URL, body and its content type) and the
decoded response. Bodies are stored as text; the headers that describe wire encoding
are dropped because the body is already decoded.

A recording may cut a large body to its first part (``max_bytes=``, ADR-0019, decision
5): the response is then marked ``truncated`` and keeps the full body's size, its sha256
and, for a JSON array, its length. A fixture recorded without a cut is written without
those four fields, as fixtures were before them, and every fixture written before them
loads.
"""

import base64
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from xippios.core.client.cache import strip_wire_headers
from xippios.core.models import utcnow
from xippios.core.redaction import scrub_url
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
        body: Decoded body text, or base64 when ``body_base64`` is set; the first part
            of upstream's body when ``truncated`` is set.
        body_base64: True when the body was not valid UTF-8 text.
        truncated: True when the recording cut the body (``max_bytes=``): it is the
            first part of upstream's answer, the first whole elements of a JSON array
            or the first bytes of a text, never all of it (ADR-0019, decision 5).
        original_bytes: The size of upstream's whole body in bytes, as ``httpx``
            decoded it; set when ``truncated``.
        original_count: The length of upstream's whole JSON array; set when an array
            was cut by elements.
        sha256: The hex SHA-256 of upstream's whole body as ``httpx`` decoded it,
            taken before the scrub, so a later recording can tell whether upstream's
            answer changed; set when ``truncated``. A one-way identity of the answer.
    """

    model_config = ConfigDict(frozen=True)

    status: int
    headers: list[tuple[str, str]]
    body: str
    body_base64: bool = False
    truncated: bool = False
    original_bytes: int | None = None
    original_count: int | None = None
    sha256: str | None = None

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


def fixture_from_response(
    response: httpx.Response, *, scrub: Scrub | None = None, max_bytes: int | None = None
) -> Fixture:
    """Build a scrubbed ``Fixture`` in memory from a fully read ``httpx.Response``.

    Credentials are always scrubbed (``scrub_url``, ``scrub_headers``). ``scrub`` adds
    the secret values and decides about a binary body; ``None`` is ``Scrub()``: nothing
    else replaced, a binary body refused. With ``secrets`` set, the result is verified
    before it is returned: a secret value still present as given in the URL, a header
    value or a text body refuses the exchange (conventions §10). A source that rewrites
    more, a tenant's host or a field by key, does it on the returned ``Fixture`` before
    it writes it (ADR-0024).

    ``max_bytes`` cuts a response body larger than it before the scrub, which then runs
    on what is kept, as the verify does (ADR-0019, decision 5; conventions §10):

    - a JSON array (a ``Content-Type`` of ``application/json`` or ``...+json``, or a
      body that parses as JSON, a byte order mark allowed) is cut at an element
      boundary in its original text, numbers and spacing as upstream wrote them: the
      first whole elements that fit in ``max_bytes`` bytes of UTF-8 with a closing
      ``]``, ``original_count`` the array's length; an array whose first element alone
      does not fit is refused;
    - any other text is cut at ``max_bytes`` bytes, back to the last whole UTF-8
      character and back to the start of a secret value (``scrub``) that the cut would
      split, so no part of one is kept; a cut that keeps nothing is refused;
    - a JSON object, and a body declared JSON that does not parse, are refused: record
      a small real answer instead (a short date range, one commodity), since an
      object's parts are no list to take the first of;
    - XML (``text/xml``, ``application/xml``, ``...+xml``, or a body starting with
      ``<?xml``), ZIP, XLSX, gzip and XLS bodies, and a body that is not UTF-8 text, are
      refused: record a small real sample (a short query, one member of the archive, a
      few rows), since a cut-off XML document is not well-formed and a cut-off binary
      or compressed file cannot be parsed.

    A cut body is marked ``truncated`` with ``original_bytes`` and ``sha256``, both of
    the whole body as ``httpx`` decoded it, before the scrub. A body of ``max_bytes`` or
    fewer bytes is kept whole and unmarked; ``None`` never cuts.

    Args:
        response: The response, with the request that produced it.
        scrub: What else to remove before anything is kept, e.g.
            ``Scrub(secrets=[tenant])``.
        max_bytes: The most bytes of the response body to keep, e.g. ``80_000``. It
            bounds the body, not the fixture file, which writes the body as a JSON
            string: escaping makes text outside ASCII up to three times as long, so
            ``80_000`` keeps a file under the 256 KiB cap. ``None`` keeps it whole.

    Raises:
        ValueError: The request or response body is not UTF-8 text and ``scrub`` does
            not set ``allow_binary``; or a secret value survived the scrub (the message
            names where, never the value); or
            ``max_bytes`` is below 1, or cannot cut this body (the message, starting
            ``max_bytes:``, names the format and what to record instead).
    """
    if max_bytes is not None and max_bytes < 1:
        raise ValueError("max_bytes must be at least 1")
    request = response.request
    scrubber = _Scrubber(scrub if scrub is not None else Scrub())
    request_body: str | None = None
    request_base64 = False
    if request.content:
        request_body, request_base64 = scrubber.body(request.content)
    content_type = request.headers.get("content-type")
    content, cut = _cut(response, max_bytes, scrubber)
    body, is_base64 = scrubber.body(content)
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
            **cut,
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


_SAMPLE = (
    "record a small real sample instead (a short query, one member of the archive, a few rows)"
)
_CUT_FILE = "since a cut-off binary or compressed file cannot be parsed"
_MAGIC = (
    (b"\x1f\x8b", "a gzip body"),
    (b"\xd0\xcf\x11\xe0", "an XLS body"),
)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_TRUNCATION_FIELDS = ("truncated", "original_bytes", "original_count", "sha256")


def _cut(
    response: httpx.Response, max_bytes: int | None, scrubber: _Scrubber
) -> tuple[bytes, dict[str, Any]]:
    """The body to keep and the ``FixtureResponse`` fields that mark a cut; see above."""
    content = response.content
    if max_bytes is None or len(content) <= max_bytes:
        return content, {}
    media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content.startswith(b"PK\x03\x04"):
        kind = "an XLSX body" if media.startswith(_XLSX) else "a ZIP body"
        raise ValueError(f"max_bytes: {kind} cannot be cut, {_CUT_FILE}; {_SAMPLE}")
    for magic, kind in _MAGIC:
        if content.startswith(magic):
            raise ValueError(f"max_bytes: {kind} cannot be cut, {_CUT_FILE}; {_SAMPLE}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"max_bytes: a body that is not UTF-8 text cannot be cut, {_CUT_FILE}; {_SAMPLE}"
        ) from None
    unmarked = text.removeprefix("\ufeff")  # a byte order mark, which httpx's json() skips
    xml = media in ("text/xml", "application/xml") or media.endswith("+xml")
    if xml or unmarked.lstrip().startswith("<?xml"):
        raise ValueError(
            "max_bytes: an XML body cannot be cut, since a cut-off XML document is not "
            f"well-formed; {_SAMPLE}"
        )
    marks: dict[str, Any] = {
        "truncated": True,
        "original_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    declared_json = media == "application/json" or media.endswith("+json")
    try:
        payload = json.loads(unmarked)
    except ValueError:
        if declared_json:
            raise ValueError(
                f"max_bytes: the body is declared {media} but is not JSON; record a small "
                "real answer instead (a short date range, one commodity)"
            ) from None
    else:
        if not isinstance(payload, list):
            raise ValueError(
                "max_bytes: a JSON body that is not an array cannot be cut by elements; "
                "record a small real answer instead (a short date range, one commodity)"
            )
        kept = _first_elements(text, len(payload), max_bytes)
        return kept.encode(), marks | {"original_count": len(payload)}
    end = max_bytes
    while end > 0 and content[end] & 0xC0 == 0x80:  # a UTF-8 continuation byte
        end -= 1
    kept = text[: scrubber.spared_end(text, len(content[:end].decode("utf-8")))]
    if not kept:
        raise ValueError(
            f"max_bytes: a cut at {max_bytes} bytes keeps nothing of the body, not one whole "
            "character, or splits a secret value at its start; raise max_bytes or record a "
            "smaller answer"
        )
    return kept.encode(), marks


_SPACE = re.compile(r"[ \t\n\r]*")


def _after_space(text: str, position: int) -> int:
    """The offset of the first character at or after ``position`` that is not JSON space."""
    match = _SPACE.match(text, position)
    return position if match is None else match.end()


def _first_elements(text: str, count: int, max_bytes: int) -> str:
    """``text``, a JSON array of ``count`` elements, cut after its last whole element that fits.

    The original text is kept as it is, numbers and spacing included, up to the end of
    the last element whose text with a closing ``]`` fits in ``max_bytes`` bytes of
    UTF-8; then the ``]``. Each element's end is found with ``json.JSONDecoder.raw_decode``.
    """
    decoder = json.JSONDecoder()
    cursor = text.index("[") + 1
    cursor_bytes = len(text[:cursor].encode())
    position = cursor
    kept = 0
    for _ in range(count):
        position = _after_space(text, position)
        if text[position] == ",":
            position = _after_space(text, position + 1)
        _, position = decoder.raw_decode(text, position)
        size = cursor_bytes + len(text[cursor:position].encode())
        if size + 1 > max_bytes:
            break
        cursor, cursor_bytes, kept = position, size, kept + 1
    if not kept:
        raise ValueError(
            f"max_bytes: the JSON array's first element alone is over {max_bytes} bytes; "
            "raise max_bytes or record a smaller answer"
        )
    return text[:cursor] + "]"


def write_fixture(response: httpx.Response, path: Path, *, scrub: Scrub | None = None) -> Fixture:
    """Scrub ``response`` in memory, then write it to ``path`` as JSON, creating directories.

    The file is written once, already scrubbed; a refusal writes nothing.

    Args:
        response: The response, with the request that produced it.
        path: Destination file, usually from ``fixture_path``.
        scrub: What else to remove besides credentials; see ``fixture_from_response``.

    Raises:
        ValueError: A binary body without ``Scrub(allow_binary=True)``, or a secret value
            left after the scrub; see ``fixture_from_response``.
    """
    return _write(fixture_from_response(response, scrub=scrub), path)


def _write(fixture: Fixture, path: Path) -> Fixture:
    """Write ``fixture`` to ``path`` as indented JSON, creating directories; ``fixture``.

    The fields that mark a cut are left out of a fixture that was not cut.
    """
    data = fixture.model_dump(mode="json")
    if not fixture.response.truncated:
        for name in _TRUNCATION_FIELDS:
            del data["response"][name]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    """The query parameters the fixture was recorded with, credentials redacted.

    A credential reads ``REDACTED``: the recorder scrubbed it, and the URL is read
    through ``scrub_url`` again, the rule ``sent_query`` applies, so a name the rule
    makes a credential reads ``REDACTED`` in both. The companion of ``sent_query``: a test compares
    what a task sent with what was recorded, ``sent_query(route) ==
    recorded_query(fixture)``.

    Args:
        fixture: The recorded exchange, e.g. from ``load_fixture``.

    Raises:
        AssertionError: A parameter was recorded more than once; read its values with
            ``httpx.URL(fixture.request.url).params.get_list(name)``.
    """
    return _query_of(scrub_url(fixture.request.url))


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
