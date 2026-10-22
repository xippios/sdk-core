import gzip
import json
from pathlib import Path

import httpx

from xippios.core.testing import REDACTED, fixture_path, load_fixture, write_fixture


def _response(
    content: bytes = b'{"ok": true}', headers: dict[str, str] | None = None
) -> httpx.Response:
    request = httpx.Request(
        "GET",
        "https://api.example.test/v1/x?key=SECRET&year=2024",
        headers={"Authorization": "Bearer SECRET"},
    )
    return httpx.Response(
        200,
        content=content,
        headers={"Content-Type": "application/json", "Set-Cookie": "sid=SECRET", **(headers or {})},
        request=request,
    )


def test_fixture_path_layout(tmp_path: Path) -> None:
    assert fixture_path(tmp_path, "api_GET", "corn_2024") == tmp_path / "api_GET" / "corn_2024.json"


def test_write_scrubs_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "api_GET" / "case.json"
    written = write_fixture(_response(), path)
    text = path.read_text()
    assert "SECRET" not in text
    assert text.endswith("\n")
    raw = json.loads(text)
    assert raw["request"] == {
        "method": "GET",
        "url": f"https://api.example.test/v1/x?key={REDACTED}&year=2024",
    }
    assert raw["response"]["status"] == 200
    assert raw["response"]["body"] == '{"ok": true}'
    assert ["set-cookie", REDACTED] in raw["response"]["headers"]
    assert load_fixture(path) == written
    assert written.recorded_at.tzinfo is not None


def test_wire_headers_are_dropped(tmp_path: Path) -> None:
    fixture = write_fixture(
        _response(gzip.compress(b'{"ok": true}'), headers={"Content-Encoding": "gzip"}),
        tmp_path / "f.json",
    )
    assert fixture.response.body == '{"ok": true}'
    names = {name.lower() for name, _ in fixture.response.headers}
    assert "content-type" in names
    assert not names & {"content-length", "content-encoding", "transfer-encoding"}


def test_binary_bodies_use_base64(tmp_path: Path) -> None:
    fixture = write_fixture(_response(content=b"\xff\xfe\x00"), tmp_path / "f.json")
    assert fixture.response.body_base64 is True
    assert fixture.response.content == b"\xff\xfe\x00"
    assert load_fixture(tmp_path / "f.json").response.content == b"\xff\xfe\x00"
