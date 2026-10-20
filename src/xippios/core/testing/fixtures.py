"""The recorded fixture format: one JSON file per ``tests/fixtures/<endpoint>/<case>.json``.

A fixture holds the scrubbed request line and the decoded response. Bodies are
stored as text; the headers that describe wire encoding are dropped because the body
is already decoded.
"""

import base64
import json
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from xippios.core.models import utcnow
from xippios.core.testing.scrub import scrub_headers, scrub_url

__all__ = [
    "Fixture",
    "FixtureRequest",
    "FixtureResponse",
    "fixture_path",
    "load_fixture",
    "write_fixture",
]

_WIRE_HEADERS = frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})


class FixtureRequest(BaseModel):
    """The request that produced the fixture, with credentials scrubbed."""

    model_config = ConfigDict(frozen=True)

    method: str
    url: str


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


def fixture_from_response(response: httpx.Response) -> Fixture:
    """Build a scrubbed ``Fixture`` from a fully read ``httpx.Response``."""
    headers = [
        (name, value)
        for name, value in scrub_headers(response.headers.multi_items())
        if name.lower() not in _WIRE_HEADERS
    ]
    try:
        body, is_base64 = response.content.decode("utf-8"), False
    except UnicodeDecodeError:
        body, is_base64 = base64.b64encode(response.content).decode("ascii"), True
    return Fixture(
        recorded_at=utcnow(),
        request=FixtureRequest(method=response.request.method, url=scrub_url(response.request.url)),
        response=FixtureResponse(
            status=response.status_code, headers=headers, body=body, body_base64=is_base64
        ),
    )


def write_fixture(response: httpx.Response, path: Path) -> Fixture:
    """Scrub ``response`` and write it to ``path`` as JSON, creating parent directories."""
    fixture = fixture_from_response(response)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixture.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return fixture


def load_fixture(path: Path) -> Fixture:
    """Read a fixture written by ``write_fixture``."""
    return Fixture.model_validate_json(path.read_text(encoding="utf-8"))
