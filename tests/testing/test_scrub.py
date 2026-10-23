import dataclasses

import httpx
import pytest

from xippios.core.testing import REDACTED, Scrub, scrub_headers, scrub_params, scrub_url


def test_scrub_params_matches_credential_like_names() -> None:
    items = [
        ("key", "s"),
        ("api_key", "s"),
        ("access_token", "s"),
        ("commodity", "corn"),
        ("x", "1"),
    ]
    assert scrub_params(items) == [
        ("key", REDACTED),
        ("api_key", REDACTED),
        ("access_token", REDACTED),
        ("commodity", "corn"),
        ("x", "1"),
    ]


def test_scrub_url_keeps_structure() -> None:
    url = httpx.URL("https://api.example.test/v1/x?key=SECRET&year=2024&client_secret=S2")
    assert scrub_url(url) == (
        f"https://api.example.test/v1/x?key={REDACTED}&year=2024&client_secret={REDACTED}"
    )


def test_scrub_url_redacts_userinfo() -> None:
    cleaned = scrub_url("https://user:pw@api.example.test/v1")
    assert "pw" not in cleaned
    assert cleaned.startswith(f"https://{REDACTED}:{REDACTED}@api.example.test/v1")


def test_scrub_headers() -> None:
    items = [
        ("Authorization", "Bearer x"),
        ("Content-Type", "application/json"),
        ("Set-Cookie", "a=b"),
    ]
    assert scrub_headers(items) == [
        ("Authorization", REDACTED),
        ("Content-Type", "application/json"),
        ("Set-Cookie", REDACTED),
    ]


def test_scrub_defaults_keep_the_host_and_refuse_binary_bodies() -> None:
    scrub = Scrub()
    assert scrub.host is None
    assert scrub.secrets == ()
    assert scrub.rewrite is None
    assert scrub.allow_binary is False


def test_scrub_is_frozen_and_keeps_secrets_as_a_tuple() -> None:
    scrub = Scrub(host="demo.example.test", secrets=["a", "b"])
    assert scrub.secrets == ("a", "b")
    with pytest.raises(dataclasses.FrozenInstanceError):
        scrub.host = "other.example.test"  # type: ignore[misc]


def test_scrub_refuses_an_empty_secret() -> None:
    with pytest.raises(ValueError, match="empty string"):
        Scrub(secrets=["value", ""])


def test_scrub_refuses_one_string_as_secrets() -> None:
    one_string = "value"
    with pytest.raises(TypeError, match="not one string"):
        Scrub(secrets=one_string)


@pytest.mark.parametrize(
    "host", ["", "demo.example.test:8443", "https://demo.example.test", "demo/x", "a b", "-a"]
)
def test_scrub_refuses_a_host_that_is_not_a_plain_name(host: str) -> None:
    with pytest.raises(ValueError, match="plain host name"):
        Scrub(host=host)
