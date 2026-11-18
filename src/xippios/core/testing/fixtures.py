"""The recorded fixture format: one JSON file per ``tests/fixtures/<wrapper>/<case>.json``.

The directory is named after the wrapper function that sends the request, or after the
task for an exchange recorded through a task (conventions §10); the parameter that names
it keeps its name, ``endpoint``, as in ``fixture_path(root, endpoint, case)``. A fixture
holds the scrubbed request (method, URL, body and its content type) and the
decoded response. Bodies are stored as text; the headers that describe wire encoding
are dropped because the body is already decoded, and so are the headers that only
identify a request (``REQUEST_ID_HEADERS``), which change with every recording.

A recording may cut a large body (``max_bytes=``, ADR-0040, decision 5): the response is
then marked ``truncated`` and keeps the full body's size, its sha256 and, for a JSON
array, its length. A source may replace a download's body with a sample of the file it
cut itself, marked ``sample`` with the same three fields (ADR-0020, decision 6, as
amended). A fixture neither cut nor a sample is written without those fields, as
fixtures were before them, and every fixture written before them loads.

``write_fixture`` writes a ``Fixture`` as ``record`` writes it, so a source that rewrites
one before the write lays it out as core does (ADR-0042, decision 4).
"""

import base64
import hashlib
import json
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from xippios.core.client.cache import strip_wire_headers
from xippios.core.models import utcnow
from xippios.core.redaction import scrub_url
from xippios.core.testing.scrub import Scrub, _Scrubber

__all__ = [
    "REQUEST_ID_HEADERS",
    "Fixture",
    "FixtureRequest",
    "FixtureResponse",
    "fixture_from_response",
    "fixture_path",
    "fixture_text",
    "load_fixture",
    "recorded_query",
    "response_from_fixture",
    "write_fixture",
]

REQUEST_ID_HEADERS = frozenset(
    {
        "cf-ray",  # Cloudflare
        "origin-cf-ray",
        "x-amz-cf-id",  # CloudFront
        "x-amz-id-2",  # S3
        "x-amz-request-id",
        "x-amzn-requestid",  # API Gateway, Lambda
        "x-amzn-trace-id",  # AWS's load balancers and X-Ray
        "x-api-umbrella-request-id",  # api.data.gov
        "x-ms-request-id",  # Azure
        "x-oracle-dms-ecid",  # Oracle's middleware
        "x-request-id",
        "x-transaction-id",  # X
        "x-vcap-request-id",  # Cloud Foundry
    }
)
"""The response headers that only identify a request, which the recorder drops.

Each holds a new value in every recording and says nothing about the answer, and the
secret scan reads a long one as a secret (https://github.com/xippios/sdk-core/issues/161).
A header that identifies what was answered, ``ETag`` or S3's ``x-amz-version-id``, is
provenance and stays.
"""


def _recorded_headers(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """``items`` minus the wire-encoding headers and ``REQUEST_ID_HEADERS``, in any case."""
    return [
        (name, value)
        for name, value in strip_wire_headers(items)
        if name.lower() not in REQUEST_ID_HEADERS
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
        headers: Response headers minus the wire-encoding ones and those that only
            identify a request (``REQUEST_ID_HEADERS``), credentials scrubbed.
        body: Decoded body text, or base64 when ``body_base64`` is set; part of
            upstream's body when ``truncated`` or ``sample`` is set.
        body_base64: True when the body was not valid UTF-8 text.
        truncated: True when the recording cut the body (``max_bytes=``): the first
            bytes of a text, or whole elements of a JSON array, the first ones or on
            request the last, the text around the array as upstream wrote it; never all
            of upstream's answer (ADR-0040, decision 5).
        sample: True when the body is a sample of upstream's answer that the source
            cut itself, such as a few pages of an XML file, in place of the body
            recorded, so that a download replays the file its parser tests read
            (ADR-0020, decision 6, as amended). Never with ``truncated``.
        original_bytes: The size of upstream's whole body in bytes, as ``httpx``
            decoded it; set when ``truncated`` or ``sample`` is.
        original_count: The length of upstream's whole JSON array, when an array was
            cut by elements.
        sha256: The hex SHA-256 of upstream's whole body as ``httpx`` decoded it,
            taken before the scrub, so a later recording can tell whether upstream's
            answer changed; set when ``truncated`` or ``sample`` is. A one-way identity
            of the answer.

    Raises:
        pydantic.ValidationError: ``truncated`` and ``sample`` both set; either set
            without ``original_bytes`` and ``sha256``; or one of the three fields that
            describe upstream's whole body set on a body that is neither.
    """

    model_config = ConfigDict(frozen=True)

    status: int
    headers: list[tuple[str, str]]
    body: str
    body_base64: bool = False
    truncated: bool = False
    sample: bool = False
    original_bytes: int | None = None
    original_count: int | None = None
    sha256: str | None = None

    @model_validator(mode="after")
    def _marks_agree(self) -> Self:
        """A body is whole, cut or a sample, and only a part names the whole body."""
        if self.truncated and self.sample:
            raise ValueError(
                "a body is truncated, the recorder's cut, or a sample the source cut, never both"
            )
        if self.truncated or self.sample:
            if self.original_bytes is None or self.sha256 is None:
                raise ValueError(
                    "a truncated or sample body names upstream's whole body: "
                    "original_bytes and sha256"
                )
        elif (self.original_bytes, self.original_count, self.sha256) != (None, None, None):
            raise ValueError(
                "original_bytes, original_count and sha256 describe the whole body of a "
                "truncated or sample body, and this one is neither"
            )
        return self

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
    """``<root>/<wrapper>/<case>.json``, the family's fixture layout (conventions §10).

    Args:
        root: The fixtures directory, e.g. ``Path("tests/fixtures")``.
        endpoint: The fixture directory: the wrapper function's name, e.g. ``"api_get"``
            for sdk-usda-nass's ``/api/api_GET/``, or the task's for an exchange recorded
            through a task.
        case: The case, e.g. ``"corn_2024"``.
    """
    return root / endpoint / f"{case}.json"


def fixture_from_response(
    response: httpx.Response,
    *,
    scrub: Scrub | None = None,
    max_bytes: int | None = None,
    array_key: str | None = None,
    keep: Literal["first", "last"] = "first",
) -> Fixture:
    """Build a scrubbed ``Fixture`` in memory from a fully read ``httpx.Response``.

    Credentials are always scrubbed (``scrub_url``, ``scrub_headers``), and the headers
    that only identify a request are dropped (``REQUEST_ID_HEADERS``). ``scrub`` adds
    the secret values, those it names and those its ``response_secrets`` reads from
    ``response``, and decides about a binary body; ``None`` is ``Scrub()``: nothing
    else replaced, a binary body refused. With secret values, the result is verified
    before it is returned: a secret value still present as given in the URL, a header
    value or a text body refuses the exchange (conventions §10). A source that rewrites
    more, a tenant's host or a field by key, does it on the returned ``Fixture`` and
    writes it with ``write_fixture`` (ADR-0042).

    ``max_bytes`` cuts a response body larger than it before the scrub, which then runs
    on what is kept, as the verify does (ADR-0040, decision 5; conventions §10):

    - a JSON array (a ``Content-Type`` of ``application/json`` or ``...+json``, or a
      body that parses as JSON, a byte order mark allowed) is cut at an element
      boundary in its original text, numbers and spacing as upstream wrote them: the
      first whole elements that fit in ``max_bytes`` bytes of UTF-8 with a closing
      ``]``, or with ``keep="last"`` the last ones after the opening ``[``, and
      ``original_count`` is the array's length; an array whose first (or last) element
      alone does not fit is refused;
    - a JSON object is cut the same way at the array of its top-level key
      ``array_key``, the rest of the object kept as upstream wrote it and counted in
      ``max_bytes``; an object with no ``array_key`` is refused, and so is a key it
      lacks or whose value is no array;
    - any other text is cut at ``max_bytes`` bytes, back to the last whole UTF-8
      character and back to the start of a secret value (``scrub``) that the cut would
      split, so no part of one is kept; a cut that keeps nothing is refused, and so are
      ``array_key`` and ``keep="last"``, which cut JSON alone;
    - another JSON value, and a body declared JSON that does not parse, are refused:
      record a small real answer instead (a short date range, one commodity);
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
        array_key: The top-level key of a JSON object whose array a cut takes, e.g.
            ``"data"`` for ``{"data": [...]}``. ``None`` cuts a body that is an array.
        keep: ``"first"`` keeps an array's first whole elements, ``"last"`` its last,
            for a list ordered oldest first.

    Raises:
        ValueError: ``max_bytes`` below 1, ``keep`` neither ``"first"`` nor ``"last"``,
            or ``array_key`` or ``keep="last"`` without ``max_bytes``; the request or
            response body is not UTF-8 text and ``scrub`` does not set
            ``allow_binary``; ``scrub.response_secrets`` returned an empty value; a
            secret value survived the scrub (the message names where, never the value);
            or ``max_bytes`` cannot cut this body (the message, starting ``max_bytes:``,
            names the format and what to record instead).
        TypeError: ``scrub.response_secrets`` returned one string, or a value that is no
            string.
    """
    _check_cut(max_bytes, array_key, keep)
    request = response.request
    scrubber = _Scrubber(scrub if scrub is not None else Scrub(), response)
    request_body: str | None = None
    request_base64 = False
    if request.content:
        request_body, request_base64 = scrubber.body(request.content)
    content_type = request.headers.get("content-type")
    content, cut = _cut(response, max_bytes, scrubber, array_key, keep)
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
            headers=scrubber.headers(_recorded_headers(response.headers.multi_items())),
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
_SMALL_ANSWER = "record a small real answer instead (a short date range, one commodity)"
_CUT_FILE = "since a cut-off binary or compressed file cannot be parsed"
_MAGIC = (
    (b"\x1f\x8b", "a gzip body"),
    (b"\xd0\xcf\x11\xe0", "an XLS body"),
)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_MARKS = ("truncated", "sample")
_WHOLE_BODY = ("original_bytes", "original_count", "sha256")


def _check_cut(max_bytes: int | None, array_key: str | None, keep: str) -> None:
    """Refuse arguments of a cut that cannot work together, before anything is sent."""
    if max_bytes is not None and max_bytes < 1:
        raise ValueError("max_bytes must be at least 1")
    if keep not in ("first", "last"):
        raise ValueError(f"keep must be 'first' or 'last', not {keep!r}")
    if max_bytes is None and (array_key is not None or keep == "last"):
        raise ValueError(
            "array_key and keep='last' choose what max_bytes cuts, and max_bytes is None"
        )


def _cut(
    response: httpx.Response,
    max_bytes: int | None,
    scrubber: _Scrubber,
    array_key: str | None,
    keep: str,
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
    unmarked = text.removeprefix("﻿")  # a byte order mark, which httpx's json() skips
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
                f"max_bytes: the body is declared {media} but is not JSON; {_SMALL_ANSWER}"
            ) from None
        if array_key is not None:
            raise ValueError(
                "max_bytes: array_key names a top-level key of a JSON object, and the body "
                "is not JSON; leave array_key out to cut the text"
            ) from None
        if keep == "last":
            raise ValueError(
                "max_bytes: keep='last' keeps the last elements of a JSON array, and the "
                "body is not JSON; a text keeps its first bytes"
            ) from None
    else:
        start, count = _array_of(text, payload, array_key)
        kept = _array_cut(text, start, count, max_bytes, keep, keyed=array_key is not None)
        return kept.encode(), marks | {"original_count": count}
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


def _array_of(text: str, payload: object, array_key: str | None) -> tuple[int, int]:
    """The offset in ``text`` of the ``[`` of the array a cut takes, and the array's length.

    ``payload`` is ``text`` decoded: an array, or the object whose top-level
    ``array_key`` holds it.
    """
    if array_key is None:
        if isinstance(payload, list):
            return text.index("["), len(payload)
        if isinstance(payload, dict):
            raise ValueError(
                "max_bytes: a JSON object is cut by the array that a top-level key names, "
                f"and array_key names none; name it, or {_SMALL_ANSWER}"
            )
        raise ValueError(
            "max_bytes: a JSON body that is not an array or an object cannot be cut by "
            f"elements; {_SMALL_ANSWER}"
        )
    if not isinstance(payload, dict):
        raise ValueError(
            "max_bytes: array_key names a top-level key of a JSON object, and the body is "
            "no JSON object; leave array_key out to cut an array"
        )
    if array_key not in payload:
        raise ValueError(f"max_bytes: the JSON object has no top-level key {array_key!r}")
    array = payload[array_key]
    if not isinstance(array, list):
        raise ValueError(f"max_bytes: the top-level key {array_key!r} holds no JSON array")
    return _member_start(text, array_key), len(array)


_SPACE = re.compile(r"[ \t\n\r]*")


def _after_space(text: str, position: int) -> int:
    """The offset of the first character at or after ``position`` that is not JSON space."""
    match = _SPACE.match(text, position)
    return position if match is None else match.end()


def _member_start(text: str, key: str) -> int:
    """The offset in ``text``, a JSON object, of the value of its top-level ``key``.

    Where the key repeats, the last one's, the value ``json.loads`` keeps.
    """
    decoder = json.JSONDecoder()
    position = _after_space(text, text.index("{") + 1)
    found = -1
    while text[position] != "}":
        name, position = decoder.raw_decode(text, position)
        position = _after_space(text, _after_space(text, position) + 1)  # past the ":"
        if name == key:
            found = position
        _, position = decoder.raw_decode(text, position)
        position = _after_space(text, position)
        if text[position] == ",":
            position = _after_space(text, position + 1)
    return found


class _Offsets:
    """The UTF-8 size of a text's head at rising character offsets, counted in one pass."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._at = 0
        self._bytes = 0

    def __call__(self, position: int) -> int:
        """The bytes of ``text[:position]``; ``position`` is never below the last one."""
        self._bytes += len(self._text[self._at : position].encode())
        self._at = position
        return self._bytes


def _array_cut(text: str, start: int, count: int, max_bytes: int, keep: str, *, keyed: bool) -> str:
    """``text`` with its array of ``count`` elements at ``start`` cut to the elements that fit.

    The original text is kept as it is, numbers and spacing included, before and after
    the array too, and ``max_bytes`` counts all of it in UTF-8. The first elements are
    kept up to the end of the last one that fits, then a ``]``; the last ones from the
    first that fits, after the ``[`` and the space that follows it. Each element's end is
    found with ``json.JSONDecoder.raw_decode``.
    """
    decoder = json.JSONDecoder()
    size = _Offsets(text)
    elements: list[tuple[int, int, int, int]] = []  # start and end, in characters and bytes
    position = start + 1
    for _ in range(count):
        position = _after_space(text, position)
        if text[position] == ",":
            position = _after_space(text, position + 1)
        begin = position
        _, position = decoder.raw_decode(text, position)
        elements.append((begin, position, size(begin), size(position)))
    close = _after_space(text, position)  # the array's "]"
    closed = size(close + 1)
    total = size(len(text))
    after = total - closed  # the bytes that follow the array
    if keep == "first":
        kept = 0
        for _, _, _, end_bytes in elements:
            if end_bytes + 1 + after > max_bytes:
                break
            kept += 1
        if kept:
            return text[: elements[kept - 1][1]] + "]" + text[close + 1 :]
    else:
        head = elements[0][2] if elements else 0
        first_kept = count
        for begin_bytes in reversed([element[2] for element in elements]):
            if head + total - begin_bytes > max_bytes:
                break
            first_kept -= 1
        if first_kept < count:
            return text[: elements[0][0]] + text[elements[first_kept][0] :]
    if not count:
        raise ValueError(
            f"max_bytes: the JSON array is empty, so no cut of it brings the body within "
            f"{max_bytes} bytes; raise max_bytes or record a smaller answer"
        )
    rest = " with the rest of the object" if keyed else ""
    raise ValueError(
        f"max_bytes: the JSON array's {keep} element alone is over {max_bytes} bytes{rest}; "
        "raise max_bytes or record a smaller answer"
    )


def fixture_text(fixture: Fixture) -> str:
    """The text of ``fixture`` as ``record`` writes it: indented JSON, keys sorted, a newline.

    A mark, ``truncated`` or ``sample``, is written only when it is set, and the fields
    that describe upstream's whole body only with one, so a fixture that is neither cut
    nor a sample reads as fixtures did before them. A source that rewrites a fixture
    measures this text against the 256 KiB cap or compares it with the file it has.

    Args:
        fixture: The exchange, e.g. from ``fixture_from_response``, rewritten with
            ``model_copy`` (ADR-0042, decision 4).

    Raises:
        ValueError: ``load_fixture`` would not read the text back, as when a
            ``model_copy`` set ``sample`` without ``original_bytes`` and ``sha256``; the
            message names the field and the rule, never a value.
    """
    data = fixture.model_dump(mode="json")
    try:
        Fixture.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_url=False, include_input=False)
        )
        raise ValueError(
            f"the fixture would not load back, so nothing is written: {problems}"
        ) from None
    response = data["response"]
    for name in _MARKS:
        if not response[name]:
            del response[name]
    if not (fixture.response.truncated or fixture.response.sample):
        for name in _WHOLE_BODY:
            del response[name]
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_fixture(fixture: Fixture, path: Path) -> Fixture:
    """Write ``fixture`` to ``path`` as ``record`` writes it, creating directories; ``fixture``.

    The text is ``fixture_text(fixture)``, written once; a refusal writes nothing. A source
    that rewrites values on the ``Fixture`` that ``fixture_from_response`` returns, a
    tenant's host or a field by key, or that replaces a download's body with its sample,
    writes the result with it (ADR-0042, decision 4), e.g.
    ``write_fixture(fixture.model_copy(update={"response": rewritten}), path)``.

    Args:
        fixture: The exchange to write.
        path: Destination file, usually from ``fixture_path``.

    Raises:
        ValueError: ``load_fixture`` would not read the fixture back; see ``fixture_text``.
    """
    text = fixture_text(fixture)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return fixture


def load_fixture(path: Path) -> Fixture:
    """Read a fixture written by ``record`` or ``write_fixture``."""
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
