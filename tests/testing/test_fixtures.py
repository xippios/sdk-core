import base64
import gzip
import json
import re
from pathlib import Path

import httpx
import pytest

from xippios.core.testing import REDACTED, Scrub, fixture_path, load_fixture, write_fixture
from xippios.core.testing.fixtures import fixture_from_response

TENANT = "acme.example.test"
PLACEHOLDER = "demo.example.test"


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
    for scrub in (None, Scrub(), Scrub(host=PLACEHOLDER)):
        with pytest.raises(ValueError, match=r"^binary body cannot be scrubbed; pass allow_binary"):
            write_fixture(_response(content=b"\xff\xfe\x00"), path, scrub=scrub)
    assert not path.exists()

    fixture = write_fixture(
        _response(content=b"\xff\xfe\x00"), path, scrub=Scrub(allow_binary=True)
    )
    assert fixture.response.body_base64 is True
    assert fixture.response.content == b"\xff\xfe\x00"
    assert json.loads(path.read_text())["response"]["body_base64"] is True
    assert load_fixture(path).response.content == b"\xff\xfe\x00"


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


def test_placeholder_host_leaves_no_trace_of_the_tenant(tmp_path: Path) -> None:
    # sdk-cashctrl: every organisation is its own subdomain, which names the tenant.
    request = httpx.Request(
        "POST",
        f"https://{TENANT}/api/v1/file/prepare.json",
        params={"return": "https://ACME.example.test/done"},
        data={"callback": "https://Acme.Example.Test/hook", "name": "x"},
    )
    response = httpx.Response(
        302,
        headers={
            "Location": f"https://{TENANT}/next",
            "Content-Location": "https://ACME.EXAMPLE.TEST/x",
            "Link": f"<https://{TENANT}/a>; rel=next",
        },
        content=(
            b'{"self": "https://acme.example.test/api/v1/x",'
            b' "escaped": "https:\\/\\/acme.example.test\\/y",'
            b' "encoded": "https%3A%2F%2Facme%2eexample%2Etest%2Fz"}'
        ),
        request=request,
    )
    path = tmp_path / "f.json"
    fixture = write_fixture(response, path, scrub=Scrub(host=PLACEHOLDER))
    text = path.read_text()
    assert "acme" not in text.lower()
    assert fixture.request.url.startswith(f"https://{PLACEHOLDER}/api/v1/file/prepare.json?")
    assert httpx.URL(fixture.request.url).params["return"] == f"https://{PLACEHOLDER}/done"
    assert fixture.request.body == f"callback=https%3A%2F%2F{PLACEHOLDER}%2Fhook&name=x"
    headers = dict(fixture.response.headers)
    assert headers["location"] == f"https://{PLACEHOLDER}/next"
    assert headers["content-location"] == f"https://{PLACEHOLDER}/x"
    assert headers["link"] == f"<https://{PLACEHOLDER}/a>; rel=next"
    assert json.loads(fixture.response.body) == {
        "self": f"https://{PLACEHOLDER}/api/v1/x",
        "escaped": f"https://{PLACEHOLDER}/y",
        "encoded": f"https%3A%2F%2F{PLACEHOLDER}%2Fz",
    }
    assert load_fixture(path) == fixture


def test_placeholder_host_replaces_the_idna_form_too() -> None:
    request = httpx.Request("GET", "https://bücher.example.test/v1/x")
    response = httpx.Response(
        200,
        content="bücher.example.test xn--bcher-kva.example.test B%C3%BCcher.example.test".encode(),
        request=request,
    )
    fixture = fixture_from_response(response, scrub=Scrub(host=PLACEHOLDER))
    assert fixture.request.url == f"https://{PLACEHOLDER}/v1/x"
    assert fixture.response.body == " ".join([PLACEHOLDER] * 3)


def test_no_placeholder_keeps_the_host() -> None:
    fixture = fixture_from_response(_response(content=b"api.example.test"), scrub=Scrub())
    assert fixture.request.url.startswith("https://api.example.test/")
    assert fixture.response.body == "api.example.test"


SECRET = "s3cr3t value/x+y"  # pragma: allowlist secret
"""Not credential-named anywhere, so only ``Scrub.secrets`` can find it."""


def test_secrets_are_redacted_plain_and_percent_encoded(tmp_path: Path) -> None:
    request = httpx.Request(
        "POST",
        "https://api.example.test/v1/s3cr3t%20value%2Fx+y",
        params={"org": SECRET},
        data={"note": SECRET},
    )
    response = httpx.Response(
        200,
        headers={
            "X-Org": SECRET,
            "Location": "https://api.example.test/v1/x?org=s3cr3t%20value%2fx%2by",
        },
        content=(
            b'{"plain": "s3cr3t value/x+y", "encoded": "s3cr3t%20value%2Fx%2By",'
            b' "form": "s3cr3t+value%2Fx%2By", "escaped": "s3cr3t value\\/x+y"}'
        ),
        request=request,
    )
    path = tmp_path / "f.json"
    fixture = write_fixture(response, path, scrub=Scrub(secrets=[SECRET]))
    assert "s3cr3t" not in path.read_text()
    assert fixture.request.url == f"https://api.example.test/v1/{REDACTED}?org={REDACTED}"
    assert fixture.request.body == f"note={REDACTED}"
    headers = dict(fixture.response.headers)
    assert headers["x-org"] == REDACTED
    assert headers["location"] == f"https://api.example.test/v1/x?org={REDACTED}"
    assert json.loads(fixture.response.body) == {
        "plain": REDACTED,
        "encoded": REDACTED,
        "form": REDACTED,
        "escaped": REDACTED,
    }


def test_secrets_longest_first_and_case_as_given() -> None:
    response = _response(content=b"xabcdefx abc ABC")
    fixture = fixture_from_response(response, scrub=Scrub(secrets=["abc", "abcdef"]))
    assert fixture.response.body == f"x{REDACTED}x {REDACTED} ABC"


def test_host_then_secrets_then_rewrite(tmp_path: Path) -> None:
    # sdk-cashctrl: file/prepare.json answers with signed storage URLs and file/get
    # redirects to one; the source knows how to neutralise them, core runs its hook.
    signed = re.compile(r"(https://storage\.example\.test/[^?\s\"]*)\?[^\s\"]*")
    seen: list[str] = []

    def strip_signature(text: str) -> str:
        seen.append(text)
        return signed.sub(rf"\1?signature={REDACTED}", text)

    location = "https://storage.example.test/f/7?X-Sig=abc123&Expires=60"
    request = httpx.Request(
        "POST",
        f"https://{TENANT}/api/v1/file/get.json",
        params={"id": 7},
        data={"org": "acme"},
    )
    response = httpx.Response(
        302,
        headers={"Location": location, "Content-Location": location},
        content=f'{{"url": "{location}", "home": "https://{TENANT}/"}}'.encode(),
        request=request,
    )
    scrub = Scrub(host=PLACEHOLDER, secrets=["acme"], rewrite=strip_signature)
    path = tmp_path / "f.json"
    fixture = write_fixture(response, path, scrub=scrub)

    stripped = f"https://storage.example.test/f/7?signature={REDACTED}"
    headers = dict(fixture.response.headers)
    assert headers["location"] == stripped
    assert headers["content-location"] == stripped
    assert json.loads(fixture.response.body) == {
        "url": stripped,
        "home": f"https://{PLACEHOLDER}/",
    }
    assert fixture.request.body == f"org={REDACTED}"
    assert "abc123" not in path.read_text()
    # the hook saw request body, header values and response body after host and secrets,
    # and never the request URL
    assert fixture.request.url == f"https://{PLACEHOLDER}/api/v1/file/get.json?id=7"
    assert f"org={REDACTED}" in seen
    assert fixture.request.url not in seen
    assert all("acme" not in text.lower() for text in seen)
    assert any(PLACEHOLDER in text for text in seen)
