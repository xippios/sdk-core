import dataclasses
import json
from urllib.parse import quote

import httpx
import pytest

from xippios.core import redaction
from xippios.core.testing import REDACTED, Fixture, Scrub, fixture_from_response, scrub
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


# A percent-encoding behind a JSON escape (ADR-0066, decision 11;
# https://github.com/xippios/sdk-core/issues/581): the scrub replaces the sign of a
# percent-encoding written as a JSON escape, and the verify searches a JSON body's keys and
# strings decoded, and percent-decoded, so a nesting that the scrub leaves is refused. The
# key is invented.

INVENTED = "k3y-INVENTED-0001"
"""An invented key, its letters in both cases, a digit and a hyphen."""


def _percent(value: str) -> str:
    """``value`` percent-encoded whole, each UTF-8 byte as ``%XX`` in upper hex."""
    return "".join(f"%{byte:02X}" for byte in value.encode())


def _answer(response_body: str, request_body: str = "") -> httpx.Response:
    """A JSON answer to a POST whose URL names no secret, its JSON body ``request_body``."""
    request = httpx.Request(
        "POST",
        "https://api.example.test/v1/x",
        content=request_body.encode(),
        headers={"content-type": "application/json"},
    )
    return httpx.Response(200, content=response_body.encode(), request=request)


@pytest.mark.parametrize(
    ("secret", "encoded"),
    [
        (INVENTED, _percent(INVENTED).replace("%", "\\u0025")),
        (INVENTED, _percent(INVENTED).lower().replace("%", "\\u0025", 1)),
        ("k3y INVENTED 0002", "k3y\\u002BINVENTED\\u002b0002"),
    ],
    ids=["every-sign-escaped-upper-hex", "one-sign-escaped-lower-hex", "a-space-s-plus-escaped"],
)
def test_a_percent_encoding_behind_a_json_escape_is_replaced(secret: str, encoded: str) -> None:
    # A JSON body that echoes the query it was sent, its "%" or "+" written as % or +.
    body = '{"link": "https://files.example.test/?k=' + encoded + '&n=1"}'
    fixture = fixture_from_response(_answer(body), scrub=Scrub(secrets=[secret]))
    assert json.loads(fixture.response.body) == {
        "link": f"https://files.example.test/?k={REDACTED}&n=1"
    }


@pytest.mark.parametrize(
    "nested",
    [
        _percent(INVENTED).replace("%6B", "%\\u0036B", 1),
        _percent(INVENTED).replace("%", "%25"),
        "%5Cu006B" + INVENTED[1:],
    ],
    ids=[
        "a-hex-digit-behind-a-json-escape",
        "percent-encoded-twice",
        "a-json-escape-percent-encoded",
    ],
)
@pytest.mark.parametrize(
    ("side", "template"),
    [("response body", '{{"link": "{}"}}'), ("request body", '{{"{}": 1}}')],
    ids=["a-string-of-the-response-body", "a-key-of-the-request-body"],
)
def test_the_verify_refuses_a_nesting_that_the_scrub_leaves(
    nested: str, side: str, template: str
) -> None:
    # The scrub replaces none of these in the raw text; decoded, and percent-decoded, each is
    # a form of the key, and the verify refuses it before anything is written.
    text = template.format(nested)
    response = _answer(text, "") if side == "response body" else _answer("{}", text)
    refusal = (
        rf"^the scrubbed fixture still holds a secret value in the {side}, decoded; it is "
        r"refused before anything is written$"
    )
    with pytest.raises(ValueError, match=refusal) as refused:
        fixture_from_response(response, scrub=Scrub(secrets=[INVENTED]))
    assert "INVENTED" not in str(refused.value), "the message names the place, never the value"


@pytest.mark.parametrize(
    "form",
    [
        INVENTED,
        _percent(INVENTED),
        _percent(INVENTED).lower(),
        "\\u006b3y\\u002dINVENTED-0001",
        "k3y%2DINVENTED\\u002d0001",
    ],
    ids=["as-given", "percent-encoded-upper", "percent-encoded-lower", "json-escaped", "a-mix"],
)
@pytest.mark.parametrize("is_json", [True, False], ids=["a-json-body", "a-text-body"])
def test_the_forms_that_stood_are_replaced_and_pass_the_decoded_search(
    form: str, is_json: bool
) -> None:
    # The decoded search refuses nothing that the scrub replaced: REDACTED in a decoded string,
    # or in it percent-decoded, is masked as in the raw text, and a text body is not decoded.
    body = '{"link": "?k=' + form + '&n=1"}' if is_json else f"k={form}&n=1"
    fixture = fixture_from_response(_answer(body), scrub=Scrub(secrets=[INVENTED]))
    assert fixture.response.body == body.replace(form, REDACTED)


# The verify decodes every place it reads, JSON-unescaping and percent-decoding in either order
# until the text no longer changes, eight rounds at most, and refuses a text that still changes
# after the eighth (ADR-0066, decision 11; the review of
# https://github.com/xippios/sdk-core/pull/587, findings 1 to 3). The keys are invented.


def _q(value: str, times: int = 1) -> str:
    """``value`` percent-encoded ``times`` times, as a query encodes it, ``/`` included."""
    for _ in range(times):
        value = quote(value, safe="")
    return value


def _refusal(place: str) -> str:
    """The verify's refusal of a secret found in ``place`` decoded, as a pattern."""
    return (
        rf"^the scrubbed fixture still holds a secret value in the {place}, decoded; it is "
        r"refused before anything is written$"
    )


def _sent(
    url: str = "https://api.example.test/v1/x",
    request_body: str = "",
    content_type: str = "application/json",
    response_body: str = "{}",
    **headers: str,
) -> httpx.Response:
    """An exchange of a POST with ``request_body`` and an answer with ``headers``."""
    request = httpx.Request(
        "POST", url, content=request_body.encode(), headers={"content-type": content_type}
    )
    return httpx.Response(200, content=response_body.encode(), headers=headers, request=request)


TWICE = _q(ENCODED, 2)
"""The value with a space, a slash and a plus, percent-encoded twice: %25C3%259Cnit%2520..."""


@pytest.mark.parametrize(
    ("place", "response"),
    [
        (
            "request URL",
            _sent(url="https://api.example.test/v1/x?next=" + _q("/cb?t=" + _q(ENCODED))),
        ),
        (
            "request body",
            _sent(request_body=f"next={TWICE}", content_type="application/x-www-form-urlencoded"),
        ),
        ("response body", _sent(response_body=f'<a href="/go?next={TWICE}">go</a>')),
        (
            "response header 'link'",
            _sent(link=f'<https://api.example.test/?n={TWICE}>; rel="next"'),
        ),
    ],
    ids=["a-callback-in-the-request-url", "a-form-body", "an-html-body", "a-link-header"],
)
def test_the_verify_percent_decodes_every_place_it_reads(
    place: str, response: httpx.Response
) -> None:
    # Finding 1: percent-encoded twice outside a JSON body, which the scrub does not replace.
    with pytest.raises(ValueError, match=_refusal(place)) as refused:
        fixture_from_response(response, scrub=Scrub(secrets=[ENCODED]))
    assert "nit" not in str(refused.value), "the message names the place, never the value"


THIRD_LAYERS = {
    "percent-encoded-three-times": (ENCODED, _q(ENCODED, 3)),
    "a-json-escape-percent-encoded-twice": (INVENTED, _q("\\", 2) + "u006B" + INVENTED[1:]),
    "json-stringified-twice": (
        INVENTED,
        json.dumps(json.dumps('{"k": "k3y\\u002dINVENTED-0001"}'))[1:-1],
    ),
}
"""Three layers of the two encodings, each in a JSON string, a pair of the secret and its form."""


@pytest.mark.parametrize(("secret", "nested"), THIRD_LAYERS.values(), ids=THIRD_LAYERS.keys())
def test_the_verify_decodes_a_third_layer_in_a_json_string(secret: str, nested: str) -> None:
    # Finding 2: decoded until it no longer changes, not once.
    response = _sent(response_body='{"q": "' + nested + '"}')
    with pytest.raises(ValueError, match=_refusal("response body")):
        fixture_from_response(response, scrub=Scrub(secrets=[secret]))


def test_the_verify_reads_the_first_of_a_repeated_key() -> None:
    # Finding 3: json.loads keeps a repeated key's last value; the verify reads the text.
    response = _sent(response_body='{"next": "' + TWICE + '", "next": "x"}')
    with pytest.raises(ValueError, match=_refusal("response body")):
        fixture_from_response(response, scrub=Scrub(secrets=[ENCODED]))


def test_the_check_of_a_rewrite_step_reads_the_first_of_a_repeated_key() -> None:
    # Finding 3: the step says it replaced the title, which stands JSON-escaped in the first of
    # two "title" keys; every pair of the body is read, not the last one alone.
    def rewrite(fixture: Fixture) -> tuple[Fixture, list[str]]:
        return fixture, ["Zürich"]

    response = _sent(response_body='{"title": "Z\\u00fcrich", "title": "x"}')
    refusal = (
        r"^the rewritten fixture still holds a value the rewrite step replaced, in the response "
        r"body, a decoded JSON string; nothing is written$"
    )
    with pytest.raises(ValueError, match=refusal):
        fixture_from_response(response, rewrite=rewrite)


def test_a_text_that_still_decodes_after_eight_rounds_is_refused() -> None:
    # Nine layers of percent-encoding over "A": the verify stops at its bound and refuses the
    # text rather than pass what it has not read to the end.
    deep = _q("%41", 9)
    response = _sent(response_body='{"q": "' + deep + '"}')
    refusal = (
        r"^the scrubbed fixture holds text in the response body that still decodes after 8 "
        r"rounds of JSON-unescaping and percent-decoding; it is refused before anything is "
        r"written$"
    )
    with pytest.raises(ValueError, match=refusal):
        fixture_from_response(response, scrub=Scrub(secrets=[INVENTED]))
