import httpx

from xippios.core.testing import REDACTED, scrub_headers, scrub_params, scrub_url


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
