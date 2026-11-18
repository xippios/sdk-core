import httpx
import pytest

import xippios.core.models as models
import xippios.core.testing as testing
from xippios.core import QueryKeyAuth, ResultMeta, redaction
from xippios.core.redaction import (
    REDACTED,
    is_credential_name,
    redact_credentials,
    register_credential_name,
    register_data_name,
    scrub_headers,
    scrub_params,
    scrub_url,
)
from xippios.core.testing import scrub

# A signed link as Azure Blob Storage and Amazon S3 write one: the signature and the
# credential are in the query, beside parameters that only describe the grant.
AZURE_LINK = (
    "https://example.blob.core.windows.net/files/psd.csv"
    "?sv=2024-11-04&se=2026-11-18T09%3A00%3A00Z&sp=r&sig=c2lnbmF0dXJl"
)
S3_LINK = (
    "https://example.s3.amazonaws.com/psd.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=AKIDEXAMPLE%2F20261118&X-Amz-Date=20261118T080000Z"
    "&X-Amz-Expires=3600&X-Amz-Signature=5f2b"
)


def test_one_redacted_everywhere() -> None:
    # sdk-cashctrl imports both spellings.
    assert models.REDACTED is testing.REDACTED is scrub.REDACTED is REDACTED


@pytest.mark.parametrize(
    "name",
    ["api_key", "apikey", "API_KEY", "x-api-key", "api-key", "access_token", "client_secret",
     "password", "passwd", "pwd", "auth", "Authorization", "sig", "X-Amz-Signature",
     "credential", "credentials"],
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


# -- names a source declares as data (https://github.com/xippios/sdk-core/issues/184) -----


def test_register_data_name_is_the_module_s() -> None:
    # Imported by its path, as xippios.core.data_gov is (ADR-0009, amendment 2026-10-27).
    assert "register_data_name" in redaction.__all__


def test_a_declared_data_name_is_data_in_the_envelope_the_recorder_and_replay() -> None:
    # sdk-x pages with X's next_token and pagination_token, which a caller reads to page on.
    assert is_credential_name("next_token")
    register_data_name("next_token")
    register_data_name("pagination_token")
    assert not is_credential_name("next_token")
    assert not is_credential_name("NEXT_TOKEN"), "matched exactly, in any letter case"
    assert is_credential_name("page_token"), "a name nobody declared stays a credential"
    assert is_credential_name("access_token")
    meta = ResultMeta(
        source="x",
        endpoint="searchPostsRecent",
        request={"next_token": "b26v89c19zqg8o3f", "access_token": "T"},
    )
    assert meta.request == {"next_token": "b26v89c19zqg8o3f", "access_token": REDACTED}
    url = "https://api.x.com/2/tweets/search/recent?next_token=b26v&access_token=T"
    assert scrub_url(url) == (
        f"https://api.x.com/2/tweets/search/recent?next_token=b26v&access_token={REDACTED}"
    )
    assert scrub_params([("pagination_token", "p2")]) == [("pagination_token", "p2")]
    register_data_name("Next_Token")  # again, in another case: nothing changes
    assert not is_credential_name("next_token")


@pytest.mark.parametrize(
    "name",
    [
        "token",  # the word alone names nothing but the credential
        "access_token",  # OAuth 2.0's (RFC 6749)
        "refresh_token",
        "id_token",  # OpenID Connect's
        "Access_Token",
        "x-auth-token",  # a second credential word, auth
        "client_secret_token",
        "api_key",  # no token in it
        "page_number",
        "tokens",  # token is no whole word in it
    ],
)
def test_only_a_name_with_token_and_no_other_credential_word_is_declared_data(
    name: str,
) -> None:
    with pytest.raises(ValueError, match="cannot be declared data"):
        register_data_name(name)
    assert redaction._data_names == frozenset()


def test_a_registered_credential_name_stays_one_though_declared_data() -> None:
    register_data_name("next_token")
    register_credential_name("next_token")
    assert is_credential_name("next_token")
    register_credential_name("pagination_token")
    register_data_name("pagination_token")
    assert is_credential_name("pagination_token")


# -- a signed link in meta.request (https://github.com/xippios/sdk-core/issues/163) -------


def test_a_signed_link_in_the_request_reads_its_signature_redacted() -> None:
    meta = ResultMeta(
        source="example",
        endpoint="psd.csv",
        request={"url": AZURE_LINK, "mirrors": [{"href": S3_LINK}], "year": 2026},
    )
    assert meta.request["url"] == (
        "https://example.blob.core.windows.net/files/psd.csv"
        f"?sv=2024-11-04&se=2026-11-18T09%3A00%3A00Z&sp=r&sig={REDACTED}"
    )
    (mirror,) = meta.request["mirrors"]
    assert mirror["href"] == (
        "https://example.s3.amazonaws.com/psd.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256"
        f"&X-Amz-Credential={REDACTED}&X-Amz-Date=20261118T080000Z"
        f"&X-Amz-Expires=3600&X-Amz-Signature={REDACTED}"
    )
    assert meta.request["year"] == 2026
    assert "c2lnbmF0dXJl" not in meta.model_dump_json()
    assert "5f2b" not in meta.model_dump_json()


@pytest.mark.parametrize(
    "value",
    [
        "https://files.example.test/bulk/qs.crops_20261027.txt.gz",
        "https://files.example.test/a%20b.csv?q=a+b&sort_key=id",  # left byte for byte
        "HTTPS://files.example.test/x?year=2024",
        "ftp://files.example.test/x?sig=S",  # no http link
        "corn?sig=S",
    ],
)
def test_a_value_that_is_no_signed_link_is_kept_as_given(value: str) -> None:
    meta = ResultMeta(source="example", endpoint="x", request={"url": value})
    assert meta.request == {"url": value}


def test_a_link_httpx_cannot_read_is_redacted_whole() -> None:
    # Its credentials cannot be told from the rest, so none of it is kept.
    meta = ResultMeta(source="example", endpoint="x", request={"url": "https://x:abc/f?sig=S"})
    assert meta.request == {"url": REDACTED}


def test_a_link_with_userinfo_reads_it_redacted() -> None:
    meta = ResultMeta(
        source="example", endpoint="x", request={"url": "https://u:p@files.example.test/x"}
    )
    assert meta.request == {"url": f"https://{REDACTED}:{REDACTED}@files.example.test/x"}


def test_redact_credentials_scrubs_a_signed_link_at_any_depth() -> None:
    request = {"links": [AZURE_LINK], "nested": {"url": S3_LINK}}
    redacted = redact_credentials(request)
    assert redacted["links"] == [scrub_url(AZURE_LINK)]
    assert redacted["nested"] == {"url": scrub_url(S3_LINK)}
    assert request["links"] == [AZURE_LINK], "the mapping given is not changed"
