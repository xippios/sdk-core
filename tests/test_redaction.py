import httpx
import pytest

import xippios.core.models as models
import xippios.core.testing as testing
from xippios.core import QueryKeyAuth, ResultMeta
from xippios.core.redaction import (
    REDACTED,
    is_credential_name,
    redact_credentials,
    register_credential_name,
    scrub_headers,
    scrub_params,
    scrub_url,
)
from xippios.core.testing import scrub


def test_one_redacted_everywhere() -> None:
    # sdk-cashctrl imports both spellings.
    assert models.REDACTED is testing.REDACTED is scrub.REDACTED is REDACTED


@pytest.mark.parametrize(
    "name",
    ["api_key", "apikey", "API_KEY", "x-api-key", "api-key", "access_token", "client_secret",
     "password", "passwd", "auth", "Authorization", "signature", "credential", "credentials"],
)  # fmt: skip
def test_a_credential_word_is_always_a_credential(name: str) -> None:
    assert is_credential_name(name)


@pytest.mark.parametrize(
    "name",
    ["key", "sort_key", "keyword", "author", "tokens_used", "design", "commodity_desc", "year"],
)
def test_a_name_without_a_credential_word_is_data(name: str) -> None:
    # Eurostat's SDMX series key is data (ADR-0019, decision 6); sort_key with it.
    assert not is_credential_name(name)


def test_a_query_key_auth_makes_its_parameter_a_credential() -> None:
    # USDA NASS sends its key as ?key=...; the name is exact, in any letter case.
    QueryKeyAuth("key", "EXAMPLE_API_KEY")
    assert is_credential_name("key")
    assert is_credential_name("KEY")
    assert not is_credential_name("sort_key")
    register_credential_name("Key")  # again: nothing changes
    assert scrub_params([("key", "s"), ("year", "2024")]) == [("key", REDACTED), ("year", "2024")]


def test_redact_credentials_copies_at_any_depth() -> None:
    register_credential_name("key")
    request = {"key": "S", "q": "corn", "nested": {"ok": [{"token": "T"}, 1]}, "sort_key": "id"}
    assert redact_credentials(request) == {
        "key": REDACTED,
        "q": "corn",
        "nested": {"ok": [{"token": REDACTED}, 1]},
        "sort_key": "id",
    }
    assert request["key"] == "S"


def test_result_meta_reads_the_rule() -> None:
    meta = ResultMeta(source="eurostat", endpoint="data", request={"key": "M.DE.CP00"})
    assert meta.request == {"key": "M.DE.CP00"}
    register_credential_name("key")
    meta = ResultMeta(source="usda-nass", endpoint="api_GET", request={"key": "SECRET"})
    assert meta.request == {"key": REDACTED}
    assert "SECRET" not in meta.model_dump_json()


def test_scrub_url_redacts_credentials_and_userinfo() -> None:
    url = httpx.URL("https://user:pw@api.example.test/v1/x?key=M.DE&year=2024&client_secret=S2")
    assert scrub_url(url) == (
        f"https://{REDACTED}:{REDACTED}@api.example.test/v1/x?key=M.DE&year=2024"
        f"&client_secret={REDACTED}"
    )


def test_scrub_headers() -> None:
    items = [("Authorization", "Bearer x"), ("Content-Type", "text/csv"), ("Set-Cookie", "a=b")]
    assert scrub_headers(items) == [
        ("Authorization", REDACTED),
        ("Content-Type", "text/csv"),
        ("Set-Cookie", REDACTED),
    ]
