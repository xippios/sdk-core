import re

import httpx
import pytest

import xippios.core.models as models
import xippios.core.testing as testing
from xippios.core import KeyAuth, ResultMeta, redaction
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
    "https://example.blob.core.windows.net/files/series.csv"
    "?sv=2024-11-04&se=2026-11-18T09%3A00%3A00Z&sp=r&sig=c2lnbmF0dXJl"
)
S3_LINK = (
    "https://example.s3.amazonaws.com/series.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=AKIDEXAMPLE%2F20261118&X-Amz-Date=20261118T080000Z"
    "&X-Amz-Expires=3600&X-Amz-Signature=5f2b"
)


def test_one_redacted_everywhere() -> None:
    # A source imports both spellings.
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
    # An SDMX series key is data (ADR-0040, decision 6); sort_key with it.
    assert not is_credential_name(name)


def test_a_query_key_auth_makes_its_parameter_a_credential_of_its_source() -> None:
    # example sends its key as ?key=...; the name is exact, in any letter case.
    KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example")
    assert is_credential_name("key", source="example")
    assert is_credential_name("KEY", source="example")
    assert not is_credential_name("sort_key", source="example")
    register_credential_name("Key", source="example")  # again: nothing changes
    assert scrub_params([("key", "s"), ("year", "2024")], source="example") == [
        ("key", REDACTED),
        ("year", "2024"),
    ]


def test_redact_credentials_copies_at_any_depth() -> None:
    register_credential_name("key", source="example")
    request = {"key": "S", "q": "corn", "nested": {"ok": [{"token": "T"}, 1]}, "sort_key": "id"}
    assert redact_credentials(request, source="example") == {
        "key": REDACTED,
        "q": "corn",
        "nested": {"ok": [{"token": REDACTED}, 1]},
        "sort_key": "id",
    }
    assert request["key"] == "S"


def test_result_meta_reads_the_rule_of_its_own_source() -> None:
    meta = ResultMeta(source="example", endpoint="get_series", request={"key": "M.DE.CP00"})
    assert meta.request == {"key": "M.DE.CP00"}
    register_credential_name("key", source="example")
    meta = ResultMeta(source="example", endpoint="get_series", request={"key": "SECRET"})
    assert meta.request == {"key": REDACTED}
    assert "SECRET" not in meta.model_dump_json()


# -- the registries are kept for each source (ADR-0040, decision 6) ------------------------


def test_one_source_s_key_name_leaves_another_source_s_data_as_sent() -> None:
    # Two invented sources in one process, as a host loads them: example sends its key as
    # ?key=..., and sibling sends a series key under the same name, which is data.
    KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example")
    keyed = ResultMeta(source="example", endpoint="get_series", request={"key": "SECRET"})
    keyless = ResultMeta(source="sibling", endpoint="get_series", request={"key": "M.DE.CP00"})
    assert keyed.request == {"key": REDACTED}
    assert keyless.request == {"key": "M.DE.CP00"}
    assert not is_credential_name("key", source="sibling")
    assert scrub_url("https://api.example.org/v1/x?key=M.DE", source="sibling") == (
        "https://api.example.org/v1/x?key=M.DE"
    )
    link = {"url": "https://api.example.org/v1/x?key=M.DE"}
    assert redact_credentials(link, source="sibling") == link
    assert redact_credentials(link, source="example") == {
        "url": f"https://api.example.org/v1/x?key={REDACTED}"
    }


def test_one_source_s_data_name_leaves_another_source_s_credential_redacted() -> None:
    register_data_name("next_token", source="sibling")
    assert not is_credential_name("next_token", source="sibling")
    assert is_credential_name("next_token", source="example")
    meta = ResultMeta(source="example", endpoint="list_regions", request={"next_token": "T"})
    assert meta.request == {"next_token": REDACTED}


def test_a_reader_without_a_source_reads_every_source_s_names() -> None:
    # The testing helpers read a sent or a recorded request without its source: a name that
    # any source sends a key under stays a credential there.
    KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example")
    register_data_name("next_token", source="sibling")
    register_data_name("page_token", source="sibling")
    register_credential_name("page_token", source="example")
    assert is_credential_name("key")
    assert not is_credential_name("next_token")
    assert is_credential_name("page_token"), "a credential of any source wins"
    assert scrub_params([("key", "s"), ("next_token", "n")]) == [
        ("key", REDACTED),
        ("next_token", "n"),
    ]
    assert redaction._registered == {"example": frozenset({"key", "page_token"})}
    assert redaction._data_names == {"sibling": frozenset({"next_token", "page_token"})}


def test_a_name_registers_for_one_source_by_keyword() -> None:
    with pytest.raises(TypeError):
        register_credential_name("key")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        register_data_name("next_token")  # type: ignore[call-arg]


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
    # Imported by its path, from the module's own list (ADR-0059, decision 3).
    assert "register_data_name" in redaction.__all__


def test_a_declared_data_name_is_data_in_the_envelope_the_recorder_and_replay() -> None:
    # example pages with next_token and pagination_token, which a caller reads to page on.
    assert is_credential_name("next_token", source="example")
    register_data_name("next_token", source="example")
    register_data_name("pagination_token", source="example")
    assert not is_credential_name("next_token", source="example")
    assert not is_credential_name("NEXT_TOKEN", source="example"), "exactly, in any case"
    assert is_credential_name("page_token", source="example"), "undeclared: a credential"
    assert is_credential_name("access_token", source="example")
    meta = ResultMeta(
        source="example",
        endpoint="list_regions",
        request={"next_token": "b26v89c19zqg8o3f", "access_token": "T"},
    )
    assert meta.request == {"next_token": "b26v89c19zqg8o3f", "access_token": REDACTED}
    url = "https://api.example.org/v1/regions?next_token=b26v&access_token=T"
    assert scrub_url(url, source="example") == (
        f"https://api.example.org/v1/regions?next_token=b26v&access_token={REDACTED}"
    )
    assert scrub_params([("pagination_token", "p2")], source="example") == [
        ("pagination_token", "p2")
    ]
    register_data_name("Next_Token", source="example")  # again, in another case: no change
    assert not is_credential_name("next_token", source="example")


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
        register_data_name(name, source="example")
    assert redaction._data_names == {}


def test_a_registered_credential_name_stays_one_though_declared_data() -> None:
    register_data_name("next_token", source="example")
    register_credential_name("next_token", source="example")
    assert is_credential_name("next_token", source="example")
    register_credential_name("pagination_token", source="example")
    register_data_name("pagination_token", source="example")
    assert is_credential_name("pagination_token", source="example")


# -- a signed link in meta.request (https://github.com/xippios/sdk-core/issues/163) -------


def test_a_signed_link_in_the_request_reads_its_signature_redacted() -> None:
    meta = ResultMeta(
        source="example",
        endpoint="series.csv",
        request={"url": AZURE_LINK, "mirrors": [{"href": S3_LINK}], "year": 2026},
    )
    assert meta.request["url"] == (
        "https://example.blob.core.windows.net/files/series.csv"
        f"?sv=2024-11-04&se=2026-11-18T09%3A00%3A00Z&sp=r&sig={REDACTED}"
    )
    (mirror,) = meta.request["mirrors"]
    assert mirror["href"] == (
        "https://example.s3.amazonaws.com/series.csv?X-Amz-Algorithm=AWS4-HMAC-SHA256"
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


# One credential word per spelling the rule takes: the rule and register_data_name read the
# same words (findings of https://github.com/xippios/sdk-core/pull/275).
WORD_SAMPLES = [
    "api_key", "apikey", "api-key", "token", "secret", "password", "passwd", "pwd", "auth",
    "authorization", "sig", "signature", "credential", "credentials",
]  # fmt: skip


def test_every_credential_word_has_a_sample() -> None:
    for word in redaction._CREDENTIAL_WORDS:
        assert any(re.fullmatch(f"(?i){word}", sample) for sample in WORD_SAMPLES), word


@pytest.mark.parametrize("word", [sample for sample in WORD_SAMPLES if sample != "token"])
def test_a_token_name_with_any_other_credential_word_stays_a_credential(word: str) -> None:
    assert is_credential_name(word)
    name = f"next_token_{word}"
    with pytest.raises(ValueError, match="cannot be declared data"):
        register_data_name(name, source="example")
    assert is_credential_name(name)
