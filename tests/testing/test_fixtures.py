import base64
import gzip
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from xippios.core.testing import REDACTED, Scrub, fixture_path, load_fixture
from xippios.core.testing.fixtures import fixture_from_response, write_fixture


def _response(
    content: bytes = b'{"ok": true}', headers: dict[str, str] | None = None
) -> httpx.Response:
    request = httpx.Request(
        "GET",
        "https://api.example.test/v1/x?api_key=SECRET&year=2024",
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
        "url": f"https://api.example.test/v1/x?api_key={REDACTED}&year=2024",
        "body": None,
        "body_base64": False,
        "content_type": None,
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


def test_binary_body_is_refused_then_stored_flagged(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    refusal = (
        r"^a binary body cannot be scrubbed; the recording is refused unless "
        r"Scrub\(allow_binary=True\) stores it base64, flagged$"
    )
    for scrub in (None, Scrub(), Scrub(secrets=["tenant"])):
        with pytest.raises(ValueError, match=refusal):
            write_fixture(_response(content=b"\xff\xfe\x00"), path, scrub=scrub)
    assert not path.exists()

    binary = b"\xff\xfe\x00tenant"  # stored as it came: neither scrubbed nor verified
    scrub = Scrub(secrets=["tenant"], allow_binary=True)
    fixture = write_fixture(_response(content=binary), path, scrub=scrub)
    assert fixture.response.body_base64 is True
    assert fixture.response.content == binary
    assert json.loads(path.read_text())["response"]["body_base64"] is True
    assert load_fixture(path).response.content == binary


def test_binary_request_body_is_refused_then_stored_flagged() -> None:
    request = httpx.Request(
        "POST",
        "https://api.example.test/v1/upload",
        content=b"\x89PNG\xff",
        headers={"Content-Type": "image/png"},
    )
    response = httpx.Response(201, json={"id": 1}, request=request)
    with pytest.raises(ValueError, match="binary body cannot be scrubbed"):
        fixture_from_response(response)
    fixture = fixture_from_response(response, scrub=Scrub(allow_binary=True))
    assert fixture.request.body_base64 is True
    assert fixture.request.body is not None
    assert base64.b64decode(fixture.request.body) == b"\x89PNG\xff"
    assert fixture.request.content_type == "image/png"
    assert (fixture.response.body, fixture.response.body_base64) == ('{"id":1}', False)


def test_request_body_and_content_type_are_recorded() -> None:
    url = "https://api.example.test/v1/x"
    form = fixture_from_response(
        httpx.Response(200, request=httpx.Request("POST", url, data={"a": 1, "b": 2}))
    ).request
    assert (form.body, form.content_type) == ("a=1&b=2", "application/x-www-form-urlencoded")
    sent = fixture_from_response(
        httpx.Response(200, request=httpx.Request("POST", url, json={"a": 1}))
    ).request
    assert (sent.body, sent.content_type) == ('{"a":1}', "application/json")
    read = fixture_from_response(httpx.Response(200, request=httpx.Request("GET", url))).request
    assert (read.body, read.body_base64, read.content_type) == (None, False, None)


FIXTURE_0_1_0 = """{
  "recorded_at": "2026-10-22T09:00:00Z",
  "request": {
    "method": "GET",
    "url": "https://api.example.test/v1/x?key=REDACTED&year=2024"
  },
  "response": {
    "body": "{\\"ok\\": true}",
    "body_base64": false,
    "headers": [["content-type", "application/json"]],
    "status": 200
  }
}
"""


def test_a_fixture_written_by_0_1_0_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(FIXTURE_0_1_0)
    fixture = load_fixture(path)
    assert fixture.request.method == "GET"
    assert (fixture.request.body, fixture.request.body_base64) == (None, False)
    assert fixture.request.content_type is None
    assert fixture.response.content == b'{"ok": true}'


def _answer(content: bytes, content_type: str) -> httpx.Response:
    request = httpx.Request("GET", "https://api.example.test/v1/file")
    headers = {"Content-Type": content_type}
    return httpx.Response(200, content=content, headers=headers, request=request)


def test_max_bytes_cuts_a_text_at_a_character_boundary(tmp_path: Path) -> None:
    # Row 46 (sdk-usda-nass): a bulk text file of hundreds of MB as a fixture.
    full = "Région\tValue\n" + "Île-de-France\t1\n" * 50
    fixture = fixture_from_response(_answer(full.encode(), "text/plain"), max_bytes=15)
    assert fixture.response.body == "Région\tValue\n"  # 14 bytes: byte 15 is half of "Î"
    response = fixture.response
    assert (response.truncated, response.original_bytes) == (True, len(full.encode()))
    assert response.sha256 == hashlib.sha256(full.encode()).hexdigest()
    assert response.original_count is None
    path = tmp_path / "f.json"
    path.write_text(json.dumps(fixture.model_dump(mode="json")))
    assert load_fixture(path) == fixture


def test_max_bytes_cuts_a_json_array_at_an_element_boundary_of_its_text() -> None:
    # Row 43 (sdk-usda-gats): list fixtures over the 256 KiB cap. Upstream's text is kept:
    # 1.50 stays 1.50 and a long figure keeps its digits, as a Decimal parser needs.
    body = '\ufeff[\n  {"id": 0, "v": 1.50},\n  {"id": 1, "v": 12345678901234567890.1},\n'
    body += "".join(f'  {{"id": {i}, "v": 2.00}},\n' for i in range(2, 50)) + '  {"id": 50}\n]'
    fixture = fixture_from_response(_answer(body.encode(), "application/json"), max_bytes=80)
    kept = '\ufeff[\n  {"id": 0, "v": 1.50},\n  {"id": 1, "v": 12345678901234567890.1}]'
    assert fixture.response.body == kept  # 75 bytes; the third element would end at 101
    assert (fixture.response.truncated, fixture.response.original_count) == (True, 51)
    assert httpx.Response(200, content=kept.encode()).json()[1]["v"] == 12345678901234567890.1
    with pytest.raises(ValueError, match=r"^max_bytes: the JSON array's first element alone"):
        fixture_from_response(_answer(body.encode(), "application/json"), max_bytes=20)


def test_max_bytes_never_keeps_part_of_a_secret() -> None:
    request = httpx.Request("GET", "https://api.example.test/v1/export")
    answer = httpx.Response(200, content=b"name\nacme-tenant\n" * 20, request=request)
    scrub = Scrub(secrets=["acme-tenant"])
    fixture = fixture_from_response(answer, scrub=scrub, max_bytes=13)  # "...\nacme-ten"
    assert fixture.response.body == "name\n"
    fixture = fixture_from_response(answer, scrub=scrub, max_bytes=19)  # "...-tenant\nna"
    assert fixture.response.body == f"name\n{REDACTED}\nna"
    first = httpx.Response(200, content=b"acme-tenant\n" * 20, request=request)
    with pytest.raises(ValueError, match=r"^max_bytes: a cut at 5 bytes keeps nothing"):
        fixture_from_response(first, scrub=scrub, max_bytes=5)
    with pytest.raises(ValueError, match=r"^max_bytes: a cut at 1 bytes keeps nothing"):
        fixture_from_response(_answer("Île".encode() * 10, "text/plain"), max_bytes=1)


@pytest.mark.parametrize(
    ("content", "content_type", "reason"),
    [
        (
            json.dumps({"data": list(range(30))}).encode(),
            "application/json",
            "a JSON body that is not an array",
        ),
        (b"[1, 2, 3" + b", 4" * 20, "application/json", "the body is declared application/json"),
        (b"<data>" + b"<row/>" * 20 + b"</data>", "application/xml", "an XML body"),
        (b"<?xml version='1.0'?><data/>" + b" " * 50, "text/plain", "an XML body"),
        (b"PK\x03\x04" + b"\x00" * 60, "application/zip", "a ZIP body"),
        (
            b"PK\x03\x04" + b"\x00" * 60,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "an XLSX body",
        ),
        (gzip.compress(b"a\tb\n" * 100), "application/gzip", "a gzip body"),
        (b"\xd0\xcf\x11\xe0" + b"\x00" * 60, "application/vnd.ms-excel", "an XLS body"),
        (b"\xff\xfe" + "a,b\n".encode("utf-16-le") * 20, "text/csv", "a body that is not UTF-8"),
    ],
)
def test_max_bytes_refuses_what_a_cut_would_break(
    content: bytes, content_type: str, reason: str
) -> None:
    # ADR-0019, decision 5, as amended: a small real answer or sample instead.
    with pytest.raises(ValueError, match=f"^max_bytes: {reason}"):
        fixture_from_response(_answer(content, content_type), max_bytes=20)


def test_max_bytes_at_or_above_the_size_keeps_the_body_unmarked(tmp_path: Path) -> None:
    for max_bytes in (12, 13):  # the body is 12 bytes
        whole = fixture_from_response(_response(), max_bytes=max_bytes)
        assert whole.response.body == '{"ok": true}'
        assert (whole.response.truncated, whole.response.sha256) == (False, None)
    write_fixture(_response(), tmp_path / "f.json")
    written = json.loads((tmp_path / "f.json").read_text())["response"]
    assert not {"truncated", "original_bytes", "original_count", "sha256"} & written.keys()
    with pytest.raises(ValueError, match="max_bytes must be at least 1"):
        fixture_from_response(_response(), max_bytes=0)


SECRET = "tenant-7"
"""Not credential-named anywhere, so only ``Scrub.secrets`` can find it."""


def test_secrets_are_redacted_as_given_in_url_headers_and_bodies(tmp_path: Path) -> None:
    request = httpx.Request(
        "POST",
        f"https://api.example.test/v1/{SECRET}/x",
        params={"org": SECRET},
        data={"note": SECRET},
    )
    response = httpx.Response(
        200,
        headers={"X-Org": SECRET, "Location": f"/v1/x?org={SECRET}"},
        content=b'{"org": "tenant-7"}',
        request=request,
    )
    path = tmp_path / "f.json"
    fixture = write_fixture(response, path, scrub=Scrub(secrets=[SECRET]))
    assert SECRET not in path.read_text()
    assert fixture.request.url == f"https://api.example.test/v1/{REDACTED}/x?org={REDACTED}"
    assert fixture.request.body == f"note={REDACTED}"
    headers = dict(fixture.response.headers)
    assert (headers["x-org"], headers["location"]) == (REDACTED, f"/v1/x?org={REDACTED}")
    assert json.loads(fixture.response.body) == {"org": REDACTED}


def test_secrets_longest_first_and_case_as_given() -> None:
    response = _response(content=b"xabcdefx abc ABC")
    fixture = fixture_from_response(response, scrub=Scrub(secrets=["abc", "abcdef"]))
    assert fixture.response.body == f"x{REDACTED}x {REDACTED} ABC"
    # REDACTED holds "ACT", and the verify does not count it.
    fixture = fixture_from_response(_response(content=b"ACT"), scrub=Scrub(secrets=["ACT"]))
    assert fixture.response.body == REDACTED


LEAKY_TEST = """
from pathlib import Path

import httpx

from xippios.core.testing import Scrub
from xippios.core.testing.fixtures import write_fixture
from xippios.core.testing.scrub import _Scrubber


def test_refused(monkeypatch):
    monkeypatch.setattr(_Scrubber, "text", lambda self, text: text)  # a scrub that misses
    request = httpx.Request("GET", "https://api.example.test/v1/x")
    response = httpx.Response(200, content=b'{"org": "tenant' + b'-7"}', request=request)
    write_fixture(response, Path("f.json"), scrub=Scrub(secrets=["tenant" + "-7"]))
"""


def test_the_verify_refuses_a_secret_left_in_a_body(pytester: pytest.Pytester) -> None:
    # The backstop of ADR-0005: the refusal names where, never the value, not even in the
    # arguments pytest prints for the frame that raised, and nothing is written.
    pytester.makepyfile(LEAKY_TEST)
    result = pytester.runpytest("--tb=long")
    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert (
        "ValueError: the scrubbed fixture still holds a secret value in the response body; "
        "it is refused before anything is written"
    ) in output
    assert SECRET not in output
    assert not (pytester.path / "f.json").exists()
