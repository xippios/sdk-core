import dataclasses
import json

import httpx
import pytest

from xippios.core import redaction
from xippios.core.testing import REDACTED, Scrub, fixture_from_response, scrub
from xippios.core.testing.scrub import _Scrubber


def test_the_scrub_reads_the_one_rule() -> None:
    # The substring rule the recorder kept is gone (ADR-0040, decision 6).
    assert scrub.scrub_params is redaction.scrub_params
    assert scrub.scrub_url is redaction.scrub_url
    assert scrub.scrub_headers is redaction.scrub_headers


def test_scrub_defaults_name_no_secret_and_refuse_binary_bodies() -> None:
    scrub = Scrub()
    assert scrub.secrets == ()
    assert scrub.allow_binary is False


def test_scrub_is_frozen_and_keeps_secrets_as_a_tuple() -> None:
    scrub = Scrub(secrets=["tenant-1", "tenant-2"])
    assert scrub.secrets == ("tenant-1", "tenant-2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        scrub.allow_binary = True  # type: ignore[misc]


def test_scrub_refuses_an_empty_secret() -> None:
    with pytest.raises(ValueError, match="empty string"):
        Scrub(secrets=["value", ""])


def test_scrub_refuses_one_string_as_secrets() -> None:
    one_string = "value"
    with pytest.raises(TypeError, match="not one string"):
        Scrub(secrets=one_string)


def test_scrub_keeps_secrets_out_of_its_repr() -> None:
    scrub = Scrub(secrets=["tenant-name"])
    assert "tenant-name" not in repr(scrub)
    assert repr(scrub) == "Scrub(response_secrets=None, allow_binary=False)"


def test_scrub_refuses_response_secrets_that_cannot_be_called() -> None:
    # https://github.com/xippios/sdk-core/issues/164: a function of the response, e.g. one
    # reading a login answer's tokens, not the values themselves.
    with pytest.raises(TypeError, match=r"^response_secrets is a function of the response"):
        Scrub(response_secrets=["tok-1"])  # type: ignore[arg-type]


# A secret's encoded forms (ADR-0066, decision 11; https://github.com/xippios/sdk-core/issues/483,
# part 4): each character as given, percent-encoded in either hex case, a space as "+", or
# behind a JSON escape, in any mix. The values are invented.

ENCODED = "Ünit 7/b+c"
"""A value with a letter outside ASCII, a space, a slash and a plus, each encoded somewhere."""


def _exchange(content: bytes, **headers: str) -> httpx.Response:
    request = httpx.Request(
        "POST",
        "https://api.example.test/v1/x",
        params={"q": ENCODED},  # httpx writes %C3%9Cnit+7%2Fb%2Bc
        data={"note": ENCODED},
    )
    return httpx.Response(200, headers=headers, content=content, request=request)


def test_a_secret_is_replaced_in_its_percent_encoded_and_json_escaped_forms() -> None:
    body = (
        b'{"org": "\\u00dcnit 7/b+c", "path": "\\u00DCnit 7\\/b+c",'
        b' "link": "https://files.example.test/?q=%c3%9cnit%207%2fB%2bc&n=1"}'
    )
    response = _exchange(body, **{"X-Echo": "%C3%9Cnit%207%2Fb%2Bc"})
    fixture = fixture_from_response(response, scrub=Scrub(secrets=[ENCODED]))
    assert fixture.request.url == f"https://api.example.test/v1/x?q={REDACTED}"
    assert fixture.request.body == f"note={REDACTED}"
    assert dict(fixture.response.headers)["x-echo"] == REDACTED
    assert json.loads(fixture.response.body) == {
        "org": REDACTED,
        "path": REDACTED,
        # %2fB: the letter case given, so "B" is no "b", and the link keeps its value
        "link": "https://files.example.test/?q=%c3%9cnit%207%2fB%2bc&n=1",
    }


def test_the_letter_case_is_the_value_s_and_the_hex_case_either() -> None:
    response = _exchange(b"Key-ab key-ab KEY-AB %4bey-ab %4Bey%2Dab %6Bey-ab")
    fixture = fixture_from_response(response, scrub=Scrub(secrets=["Key-ab"]))
    assert fixture.response.body == f"{REDACTED} key-ab KEY-AB {REDACTED} {REDACTED} %6Bey-ab"


def test_a_json_escape_of_any_character_is_a_form_of_it() -> None:
    # A short escape, a quote and a backslash, and a surrogate pair beyond the BMP.
    value = 'p"q\\r\ts\U0001f600'
    escaped = json.dumps({"v": value, "w": value}, ensure_ascii=True).encode()
    assert b"\\ud83d\\ude00" in escaped
    upper = escaped.replace(b"\\ud83d\\ude00", b"\\uD83D\\uDE00", 1)
    fixture = fixture_from_response(_exchange(upper), scrub=Scrub(secrets=[value]))
    assert json.loads(fixture.response.body) == {"v": REDACTED, "w": REDACTED}


def test_the_verify_refuses_an_encoded_form_that_the_scrub_left(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_Scrubber, "text", lambda self, text: text)  # a scrub that misses
    response = _exchange(b'{"org": "\\u00dcnit 7\\/b+c"}')
    refusal = r"^the scrubbed fixture still holds a secret value in the request URL; it is refused"
    with pytest.raises(ValueError, match=refusal) as refused:
        fixture_from_response(response, scrub=Scrub(secrets=[ENCODED]))
    assert "nit" not in str(refused.value), "the message names the place, never the value"
