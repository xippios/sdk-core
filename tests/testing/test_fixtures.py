import base64
import gzip
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from xippios.core.testing import (
    REDACTED,
    FixtureResponse,
    Scrub,
    fixture_from_response,
    fixture_path,
    fixture_text,
    load_fixture,
    record,
    write_fixture,
)
from xippios.core.testing.fixtures import REQUEST_ID_HEADERS

MARKS = {"truncated", "sample", "original_bytes", "original_count", "sha256"}


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
    written = write_fixture(fixture_from_response(_response()), path)
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


def test_write_fixture_writes_a_rewritten_fixture_as_record_lays_it_out(tmp_path: Path) -> None:
    # Four sources each copied the
    # private writer to write a fixture they had rewritten (ADR-0042, decision 4).
    recorded = fixture_from_response(_response(content=b'{"org": "acme"}'))
    response = recorded.response.model_copy(update={"body": '{"org": "ORG"}'})
    rewritten = recorded.model_copy(update={"response": response})
    path = tmp_path / "account_list" / "one.json"
    assert write_fixture(rewritten, path) == rewritten
    text = path.read_text(encoding="utf-8")
    assert text == fixture_text(rewritten)
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    assert not MARKS & json.loads(text)["response"].keys()  # a fixture not marked
    assert load_fixture(path) == rewritten


def test_the_marks_are_written_for_a_cut_or_a_sample_body_only() -> None:
    rows = ("[" + ", ".join(f'{{"n": {n}}}' for n in range(40)) + "]").encode()
    cut = fixture_from_response(_answer(rows, "application/json"), max_bytes=12)
    written = json.loads(fixture_text(cut))["response"]
    assert MARKS & written.keys() == {"truncated", "original_bytes", "original_count", "sha256"}
    assert (written["truncated"], written["original_count"]) == (True, 40)

    full = b"a,b\n" + b"1,2\n" * 40

    whole = fixture_from_response(_answer(full, "text/csv"))
    marks = {
        "sample": True,
        "original_bytes": len(full),
        "sha256": hashlib.sha256(full).hexdigest(),
    }
    response = whole.response.model_copy(update={"body": "a,b\n1,2\n", **marks})
    sample = whole.model_copy(update={"response": response})
    written = json.loads(fixture_text(sample))["response"]
    assert MARKS & written.keys() == {"sample", "original_bytes", "original_count", "sha256"}
    assert (written["sample"], written["original_bytes"]) == (True, len(full))


def test_a_body_is_cut_or_a_sample_never_both_and_either_names_the_whole_body(
    tmp_path: Path,
) -> None:
    whole = {"original_bytes": 100, "sha256": "0" * 64}
    with pytest.raises(ValidationError, match="never both"):
        FixtureResponse(status=200, headers=[], body="x", truncated=True, sample=True, **whole)
    for mark in ("truncated", "sample"):
        with pytest.raises(ValidationError, match="original_bytes and sha256"):
            FixtureResponse(status=200, headers=[], body="x", **{mark: True})
    with pytest.raises(ValidationError, match="this one is neither"):
        FixtureResponse(status=200, headers=[], body="x", original_count=3)
    # model_copy skips validation; the writer refuses what load_fixture would not read back.
    recorded = fixture_from_response(_response())
    marked = recorded.response.model_copy(update={"sample": True})
    path = tmp_path / "f.json"
    with pytest.raises(
        ValueError, match=r"^the fixture would not load back, so nothing is written"
    ):
        write_fixture(recorded.model_copy(update={"response": marked}), path)
    assert not path.exists()


def test_wire_headers_are_dropped(tmp_path: Path) -> None:
    fixture = write_fixture(
        fixture_from_response(
            _response(gzip.compress(b'{"ok": true}'), headers={"Content-Encoding": "gzip"})
        ),
        tmp_path / "f.json",
    )
    assert fixture.response.body == '{"ok": true}'
    names = {name.lower() for name, _ in fixture.response.headers}
    assert "content-type" in names
    assert not names & {"content-length", "content-encoding", "transfer-encoding"}


def test_the_headers_that_only_identify_a_request_are_dropped() -> None:
    # Two sources' x-amz-cf-id and x-transaction-id, a new value in every
    # recording, each needed an audited entry of the secret scan's baseline.
    ids = {
        "X-Amz-Cf-Id": "request-1",
        "x-amzn-RequestId": "request-2",
        "X-Amzn-Trace-Id": "request-3",
        "X-Request-Id": "request-4",
        "x-transaction-id": "request-5",
        "x-api-umbrella-request-id": "request-6",
        "x-vcap-request-id": "request-7",
    }
    provenance = {"ETag": '"v1"', "X-Amz-Version-Id": "version-1", "X-Amz-Cf-Pop": "FRA56-P1"}
    fixture = fixture_from_response(_response(headers={**ids, **provenance}))
    names = {name for name, _ in fixture.response.headers}
    assert not names & {name.lower() for name in ids}
    assert {name.lower() for name in provenance} <= names
    assert {name.lower() for name in ids} <= REQUEST_ID_HEADERS
    assert all(name == name.lower() for name in REQUEST_ID_HEADERS)


def test_binary_body_is_refused_then_stored_flagged(tmp_path: Path) -> None:
    path = tmp_path / "f.json"
    refusal = (
        r"^a binary body cannot be scrubbed; the recording is refused unless "
        r"Scrub\(allow_binary=True\) stores it base64, flagged$"
    )
    for scrub in (None, Scrub(), Scrub(secrets=["tenant"])):
        with pytest.raises(ValueError, match=refusal):
            fixture_from_response(_response(content=b"\xff\xfe\x00"), scrub=scrub)

    binary = b"\xff\xfe\x00tenant"  # stored as it came: neither scrubbed nor verified
    scrub = Scrub(secrets=["tenant"], allow_binary=True)
    fixture = write_fixture(fixture_from_response(_response(content=binary), scrub=scrub), path)
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


def test_max_bytes_cuts_a_json_array_at_an_element_boundary_of_its_text() -> None:
    # List fixtures over the 256 KiB cap. Upstream's text is kept:
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


def _envelope(rows: str) -> str:
    """An upstream's shape: the rows under ``data`` between two other members."""
    return '{"count": 50, "data": [\n' + rows + '], "note": "Île"}\n'


ROWS = '  {"id": 0, "v": 1.50},\n  {"id": 1, "v": 2.50},\n' + "".join(
    f'  {{"id": {i}, "v": 2.00}},\n' for i in range(2, 49)
)
ENVELOPE = _envelope(ROWS + '  {"id": 49}\n')


def test_max_bytes_keeps_the_last_elements_on_request() -> None:
    # A list ordered oldest first lost the years its tests read.
    array = (
        "[\n" + "".join(f'  {{"year": {1960 + i}}},\n' for i in range(63)) + '  {"year": 2023}\n]\n'
    )
    last = fixture_from_response(
        _answer(array.encode(), "application/json"), max_bytes=40, keep="last"
    )
    assert last.response.body == '[\n  {"year": 2022},\n  {"year": 2023}\n]\n'
    assert (last.response.truncated, last.response.original_count) == (True, 64)


def test_max_bytes_cuts_a_json_array_alone() -> None:
    # ADR-0066, decision 12: a text that is not JSON and a JSON object over the bound are
    # recorded as a small real answer, and array_key is gone with the cut of an object.
    text = ("Région\tValue\n" + "Île-de-France\t1\n" * 50).encode()
    with pytest.raises(ValueError, match=r"^max_bytes: a text that is not JSON cannot be cut"):
        fixture_from_response(_answer(text, "text/plain"), max_bytes=15)
    with pytest.raises(ValueError, match=r"^max_bytes: a JSON body that is not an array cannot"):
        fixture_from_response(_answer(ENVELOPE.encode(), "application/json"), max_bytes=50)
    for function in (fixture_from_response, record):
        assert "array_key" not in inspect.signature(function).parameters


@pytest.mark.parametrize(
    ("body", "options", "reason"),
    [
        (ENVELOPE, {}, "a JSON body that is not an array cannot be cut"),
        (ENVELOPE, {"keep": "last"}, "a JSON body that is not an array cannot be cut"),
        ('"' + "x" * 60 + '"', {}, "a JSON body that is not an array cannot be cut"),
        ("a\tb\n" * 30, {}, "a text that is not JSON cannot be cut"),
        ("a\tb\n" * 30, {"keep": "last"}, "a text that is not JSON cannot be cut"),
        (
            '[{"id": 0, "v": "' + "x" * 60 + '"}]',
            {"keep": "last"},
            "the JSON array's last element alone is over 50 bytes",
        ),
        ("[" + " " * 60 + "]", {}, "the JSON array is empty"),
    ],
)
def test_max_bytes_refuses_a_cut_it_cannot_make_of_a_json_body(
    body: str, options: dict[str, Any], reason: str
) -> None:
    with pytest.raises(ValueError, match=f"^max_bytes: {reason}"):
        fixture_from_response(_answer(body.encode(), "text/plain"), max_bytes=50, **options)


def test_keep_needs_max_bytes() -> None:
    with pytest.raises(ValueError, match=r"^keep='last' chooses what max_bytes cuts, and max_byt"):
        fixture_from_response(_response(), keep="last")
    with pytest.raises(ValueError, match=r"^keep must be 'first' or 'last'"):
        fixture_from_response(_response(), max_bytes=5, keep="middle")  # type: ignore[arg-type]
    whole = fixture_from_response(_response(), max_bytes=100, keep="last")
    assert whole.response.body == '{"ok": true}'  # within max_bytes: neither looked at
    assert not whole.response.truncated


@pytest.mark.parametrize(
    ("content", "content_type", "reason"),
    [
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
    # ADR-0040, decision 5: a small real answer or sample instead.
    with pytest.raises(ValueError, match=f"^max_bytes: {reason}"):
        fixture_from_response(_answer(content, content_type), max_bytes=20)


def test_max_bytes_at_or_above_the_size_keeps_the_body_unmarked(tmp_path: Path) -> None:
    for max_bytes in (12, 13):  # the body is 12 bytes
        whole = fixture_from_response(_response(), max_bytes=max_bytes)
        assert whole.response.body == '{"ok": true}'
        assert (whole.response.truncated, whole.response.sha256) == (False, None)
    write_fixture(fixture_from_response(_response()), tmp_path / "f.json")
    written = json.loads((tmp_path / "f.json").read_text())["response"]
    assert not MARKS & written.keys()
    with pytest.raises(ValueError, match="max_bytes must be at least 1"):
        fixture_from_response(_response(), max_bytes=0)


SECRET = "tenant-7"  # pragma: allowlist secret
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
    fixture = write_fixture(fixture_from_response(response, scrub=Scrub(secrets=[SECRET])), path)
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
import pytest

from xippios.core.testing import Scrub, fixture_from_response, write_fixture
from xippios.core.testing.scrub import _Scrubber

TENANT = "tenant" + "-7"


@pytest.mark.parametrize("where", ["url", "header", "request", "response"])
def test_refused(monkeypatch, where):
    monkeypatch.setattr(_Scrubber, "text", lambda self, text: text)  # a scrub that misses
    url = "https://api.example.test/v1/" + (TENANT if where == "url" else "x")
    sent = TENANT.encode() if where == "request" else None
    request = httpx.Request("POST", url, content=sent)
    headers = {"Location": "/" + TENANT} if where == "header" else {}
    answer = TENANT.encode() if where == "response" else b"{}"
    response = httpx.Response(200, headers=headers, content=answer, request=request)
    fixture = fixture_from_response(response, scrub=Scrub(secrets=[TENANT]))
    write_fixture(fixture, Path(where + ".json"))
"""


def test_the_verify_refuses_a_secret_left_in_the_exchange(pytester: pytest.Pytester) -> None:
    # The backstop of ADR-0030: the refusal names where, never the value, not even in the
    # arguments pytest prints for the frame that raised, and nothing is written.
    pytester.makepyfile(LEAKY_TEST)
    result = pytester.runpytest("--tb=long")
    result.assert_outcomes(failed=4)
    output = result.stdout.str()
    for location in ("request URL", "response header 'location'", "request body", "response body"):
        assert (
            f"ValueError: the scrubbed fixture still holds a secret value in the {location}; "
            "it is refused before anything is written"
        ) in output
    assert SECRET not in output
    assert not list(pytester.path.glob("*.json"))


LEAKY_ANSWER_TEST = """
from pathlib import Path

import httpx

from xippios.core.testing import Scrub, fixture_from_response, write_fixture
from xippios.core.testing.scrub import _Scrubber

TOKEN = "tok" + "-access-1"


def test_refused(monkeypatch):
    monkeypatch.setattr(_Scrubber, "text", lambda self, text: text)  # a scrub that misses
    request = httpx.Request("POST", "https://api.example.test/auth/login")
    answer = {"AccessToken": TOKEN}
    response = httpx.Response(200, headers={"X-Token": TOKEN}, json=answer, request=request)
    scrub = Scrub(response_secrets=lambda got: [got.json()["AccessToken"]])
    write_fixture(fixture_from_response(response, scrub=scrub), Path("login.json"))
"""


def test_the_verify_refuses_a_response_secret_left_in_a_header(
    pytester: pytest.Pytester,
) -> None:
    # https://github.com/xippios/sdk-core/issues/164: the values a function reads from the
    # answer are verified as the named ones are, the location named, never the value.
    pytester.makepyfile(LEAKY_ANSWER_TEST)
    result = pytester.runpytest("--tb=long")
    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert (
        "ValueError: the scrubbed fixture still holds a secret value in the response header "
        "'x-token'; it is refused before anything is written"
    ) in output
    assert "tok-access-1" not in output  # pragma: allowlist secret
    assert not list(pytester.path.glob("*.json"))
