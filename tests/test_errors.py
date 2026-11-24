import copy
import pickle
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from xippios.core import errors
from xippios.core.errors import (
    AuthError,
    ConfigError,
    InvalidRequestError,
    NotFoundError,
    QueryTooLarge,
    RateLimitError,
    TransportError,
    UnknownCode,
    UpstreamError,
    ValidationError,
    XippiosError,
    error_from_exception,
    error_from_response,
    parse_retry_after,
    raise_for_status,
)


def _response(status: int, body: str = "", headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.example.test/v1/thing?key=not-for-the-message")
    return httpx.Response(status, text=body, headers=headers, request=request)


@pytest.mark.parametrize(
    ("status", "cls"),
    [
        (401, AuthError),
        (403, AuthError),
        (404, NotFoundError),
        (429, RateLimitError),
        (400, UpstreamError),
        (418, UpstreamError),
        (500, UpstreamError),
        (503, UpstreamError),
    ],
)
def test_classification_table(status: int, cls: type[XippiosError]) -> None:
    error = error_from_response(_response(status, "boom"), source="example")
    assert isinstance(error, cls)
    assert error.source == "example"
    assert str(error).startswith(f"{status} from GET /v1/thing: ")


def test_success_is_none() -> None:
    assert error_from_response(_response(200)) is None
    raise_for_status(_response(204))


def test_message_never_contains_query_string() -> None:
    error = error_from_response(_response(500, "server said no"))
    assert error is not None
    assert "key=" not in str(error)
    assert "server said no" in str(error)


@pytest.mark.parametrize(
    ("status", "cls"),
    [(401, AuthError), (404, NotFoundError), (429, RateLimitError), (503, UpstreamError)],
)
def test_message_names_method_and_path_never_the_host(status: int, cls: type[XippiosError]) -> None:
    # A multi-tenant source's host names the tenant.
    request = httpx.Request(
        "POST", "https://acme-holding.example.test/api/v1/journal/create.json?lang=de"
    )
    response = httpx.Response(status, text="refused", request=request)
    error = error_from_response(response, source="example")
    assert isinstance(error, cls)
    message = str(error)
    said = f". {SENT_ONCE}" if status >= 500 else ""  # a write's 5xx says it was sent once
    assert message == f"{status} from POST /api/v1/journal/create.json: refused{said}"
    assert "acme-holding" not in message
    assert "example.test" not in message
    assert "lang=" not in message


def test_request_description_is_the_method_and_path_error_messages_name() -> None:
    # https://github.com/xippios/sdk-core/issues/62: two sources each kept a copy, `_where`,
    # and two more wrote it inline in `classify`.
    request = httpx.Request("GET", "https://host.test/v1/x?year=2024&api_key=not-named")
    response = httpx.Response(404, text="no such series", request=request)
    assert errors.request_description(response) == "GET /v1/x"
    assert str(error_from_response(response)) == (
        f"404 from {errors.request_description(response)}: no such series"
    )
    tenant = httpx.Request("post", "https://acme.example.test/api/v1/a%20b/list.json?lang=de")
    described = errors.request_description(httpx.Response(200, request=tenant))
    assert described == "POST /api/v1/a b/list.json"


def test_upstream_error_carries_status_and_body() -> None:
    error = error_from_response(_response(502, "x" * 20_000))
    assert isinstance(error, UpstreamError)
    assert error.status == 502
    assert len(error.body) == 16_384


def test_auth_error_status() -> None:
    error = error_from_response(_response(403))
    assert isinstance(error, AuthError)
    assert error.status == 403


def test_rate_limit_retry_after_seconds() -> None:
    error = error_from_response(_response(429, headers={"Retry-After": "7"}))
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 7.0


def test_raise_for_status_raises() -> None:
    with pytest.raises(NotFoundError):
        raise_for_status(_response(404))


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    value = "Tue, 20 Oct 2026 12:01:30 GMT"
    assert parse_retry_after(value, now=now) == 90.0


def test_parse_retry_after_past_date_is_zero() -> None:
    now = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after("Tue, 20 Oct 2026 11:00:00 GMT", now=now) == 0.0


HUGE_ZONE = "Fri, 23 Oct 2026 08:00:00 +9999999999999999999999999"


@pytest.mark.parametrize("value", [None, "", "soon", "-5", "²", "٣", "1²", "9" * 400, HUGE_ZONE])
def test_parse_retry_after_unparseable(value: str | None) -> None:
    # "²" and "٣" pass str.isdigit(); int("²") raised, and "9" * 400 is float("inf");
    # HUGE_ZONE made parsedate_to_datetime raise OverflowError.
    assert parse_retry_after(value) is None


def test_a_429_with_an_overflowing_date_is_a_rate_limit_error() -> None:
    error = error_from_response(_response(429, headers={"Retry-After": HUGE_ZONE}))
    assert isinstance(error, RateLimitError)
    assert error.retry_after is None


def test_parse_retry_after_keeps_a_large_finite_delay() -> None:
    assert parse_retry_after(str(10**12)) == 1e12


SENT_ONCE = "The request was sent once and its outcome is unknown."


def _answer(method: str, status: int, body: str = "") -> httpx.Response:
    return httpx.Response(
        status, text=body, request=httpx.Request(method, "https://api.example.test/v1/x")
    )


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_a_5xx_to_a_write_says_it_was_sent_once_and_its_outcome_is_unknown(method: str) -> None:
    # The client sends a write once (ADR-0011, amendment 2026-11-24): a gateway's 502 can
    # stand in front of a write that the application completed.
    error = error_from_response(_answer(method, 502, "bad gateway"), source="example")
    assert isinstance(error, UpstreamError)
    assert str(error) == f"502 from {method} /v1/x: bad gateway. {SENT_ONCE}"


def test_upstream_s_sentence_keeps_its_one_full_stop() -> None:
    error = error_from_response(_answer("POST", 503, "Try again later."))
    assert str(error) == f"503 from POST /v1/x: Try again later. {SENT_ONCE}"


def test_a_5xx_without_a_body_or_a_reason_leaves_no_empty_colon() -> None:
    assert _answer("POST", 599).reason_phrase == ""
    assert str(error_from_response(_answer("POST", 599))) == f"599 from POST /v1/x. {SENT_ONCE}"


@pytest.mark.parametrize(
    ("method", "status"),
    [("GET", 503), ("HEAD", 500), ("OPTIONS", 504), ("POST", 400), ("POST", 429), ("DELETE", 404)],
)
def test_a_read_s_5xx_and_a_write_s_4xx_keep_their_words(method: str, status: int) -> None:
    # A read is repeated, and upstream refused a 4xx before acting on it.
    response = _answer(method, status)
    assert str(error_from_response(response)) == (
        f"{status} from {method} /v1/x: {response.reason_phrase}"
    )


def test_transport_error_from_httpx() -> None:
    request = httpx.Request("GET", "https://api.example.test/")
    exc = httpx.ConnectTimeout("timed out", request=request)
    error = error_from_exception(exc, source="example")
    assert isinstance(error, TransportError)
    assert str(error) == "ConnectTimeout: timed out"
    assert error.source == "example"


def test_transport_error_never_names_the_host() -> None:
    # CPython's text for a TLS hostname mismatch quotes the host, here a tenant's.
    request = httpx.Request("GET", "https://tenant.example.org/x")
    exc = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, "
        "certificate is not valid for 'tenant.example.org'. (TENANT.EXAMPLE.ORG)",
        request=request,
    )
    message = str(error_from_exception(exc, source="example"))
    assert message == (
        "ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname "
        "mismatch, certificate is not valid for '<host>'. (<host>)"
    )
    assert "tenant" not in message.lower()


def test_transport_error_masks_the_ascii_form_of_an_idn_host() -> None:
    request = httpx.Request("GET", "https://bücher.example/x")
    exc = httpx.ConnectError("not valid for 'xn--bcher-kva.example'", request=request)
    assert str(error_from_exception(exc)) == "ConnectError: not valid for '<host>'"


def test_transport_error_without_a_request() -> None:
    error = error_from_exception(httpx.ConnectError("connection refused"), source="example")
    assert isinstance(error, TransportError)
    assert str(error) == "ConnectError: connection refused"


class RequestRejected(InvalidRequestError):
    """A source's subclass with keyword-only attributes of its own (module level: picklable)."""

    def __init__(
        self,
        message: str,
        *,
        fields: tuple[str, ...],
        upstream_message: str | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(message, source=source)
        self.fields = fields
        self.upstream_message = upstream_message


class YearTooLarge(QueryTooLarge):
    """A source's shape: core's error, the year that alone is over the limit kept."""

    def __init__(self, count: int | None, *, year: int | None = None) -> None:
        narrow = "Narrow the filters."
        if year is not None:
            narrow = f"Year {year} alone is over it, so split_by_year cannot fetch it. {narrow}"
        super().__init__(count, limit=50_000, narrow=narrow, source="example")
        self.year = year


ERRORS = [
    XippiosError("something failed", source="example"),
    ConfigError("EXAMPLE_API_KEY is not set"),
    AuthError("401 from GET /v1/x: denied", status=401, source="example"),
    RateLimitError("429 from GET /v1/x: slow down", retry_after=2.5, source="example"),
    NotFoundError("404 from GET /v1/x: gone", source="example"),
    ValidationError("not a list", raw={"rows": [1, "x"]}, source="example"),
    UpstreamError("503 from GET /v1/x: busy", status=503, body="busy", source="example"),
    TransportError("ConnectError: nope", source="example"),
    InvalidRequestError("year must have four digits", source="example"),
    RequestRejected("rejected", fields=("amount",), upstream_message="Too big.", source="ex"),
    UnknownCode(
        "country_code",
        "ZZ",
        list_name="countries",
        fetched=datetime(2026, 10, 23, tzinfo=UTC),
        closest=[("ZA", "South Africa")],
        source="example",
    ),
    QueryTooLarge(200_000, limit=100_000, narrow="Split by period.", source="example"),
    QueryTooLarge(None, limit=50_000, narrow="Narrow.", request="GET /v1/x", source="example"),
    YearTooLarge(57_873_464, year=2021),
]


def _pickled(error: XippiosError) -> list[XippiosError]:
    return [
        pickle.loads(pickle.dumps(error, protocol=protocol))
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1)
    ]


@pytest.mark.parametrize("error", ERRORS, ids=lambda error: type(error).__name__)
@pytest.mark.parametrize(
    "round_trip",
    [lambda e: [copy.copy(e)], lambda e: [copy.deepcopy(e)], _pickled],
    ids=["copy", "deepcopy", "pickle"],
)
def test_errors_survive_copy_and_pickle(
    error: XippiosError, round_trip: Callable[[XippiosError], list[XippiosError]]
) -> None:
    for clone in round_trip(error):
        assert type(clone) is type(error)
        assert clone is not error
        assert str(clone) == str(error)
        assert clone.message == error.message
        assert clone.source == error.source
        assert clone.args == error.args
        assert vars(clone) == vars(error)
        for name in (
            "status", "retry_after", "raw", "body", "fields", "upstream_message", "closest",
            "count", "limit", "narrow", "year", "request",
        ):  # fmt: skip
            assert getattr(clone, name, None) == getattr(error, name, None)


def test_every_taxonomy_class_is_covered() -> None:
    taxonomy = {
        cls
        for name in errors.__all__
        if isinstance(cls := getattr(errors, name), type) and issubclass(cls, XippiosError)
    }
    assert len(taxonomy) == 11
    assert {type(error) for error in ERRORS} == taxonomy | {RequestRejected, YearTooLarge}


FETCHED = datetime(2026, 10, 23, 9, 15, tzinfo=UTC)
REFRESH = "If upstream added it since, the packaged list is out of date."
"""The tail every refusal ends with: no maintainer's command, which an agent cannot run."""

UNSENT = "Nothing was sent."
"""The sentence after the first of every refusal made before a request (conventions §5)."""


def test_unknown_code_says_nothing_was_sent_then_names_the_closest_codes() -> None:
    # The copies of three sources, one message (ADR-0041), which
    # says after its first sentence that nothing was sent
    # (https://github.com/xippios/sdk-core/issues/481). Core's tests hold the message here alone.
    closest = [("0410000", "Wheat"), ("0440000", "Corn")]
    error = UnknownCode(
        "commodity_code",
        "0410001",
        list_name="commodities",
        fetched=FETCHED,
        closest=closest,
        source="example",
    )
    assert isinstance(error, InvalidRequestError)
    assert str(error) == (
        "'0410001' is not a commodity_code in the packaged commodities list (fetched "
        "2026-10-23). Nothing was sent. Did you mean 0410000 (Wheat), 0440000 (Corn)? " + REFRESH
    )
    assert (error.param, error.value, error.fetched) == ("commodity_code", "0410001", FETCHED)
    assert (error.list_name, error.source) == ("commodities", "example")
    assert error.closest == tuple(closest)


def test_unknown_code_takes_a_hint_over_the_closest_and_a_reason() -> None:
    error = UnknownCode(
        "attribute_id",
        999,
        list_name="commodityAttributes",
        fetched=FETCHED,
        closest=[(99, "Other")],
        hint="Omit attribute_id for every attribute.",
        reason="An id the list lacks selects nothing, so the package refuses it.",
    )
    assert str(error) == (
        "999 is not an attribute_id in the packaged commodityAttributes list (fetched "
        "2026-10-23). Nothing was sent. Omit attribute_id for every attribute. An id the list "
        "lacks selects nothing, so the package refuses it. " + REFRESH
    )
    bare = UnknownCode("partner_code", "ZZ", list_name="countries", fetched=FETCHED)
    assert str(bare) == (
        "'ZZ' is not a partner_code in the packaged countries list (fetched 2026-10-23). "
        f"{UNSENT} {REFRESH}"
    )
    assert bare.closest == ()


def test_unknown_code_of_a_value_that_is_no_code_leaves_out_the_lists_age() -> None:
    # A value a source's hint table holds, such as an ISO alpha-3 code for upstream's
    # integers: no refresh makes it a code (https://github.com/xippios/sdk-core/issues/430,
    # ADR-0041, amendment 2026-11-22). The keyword names the sentence it keeps or leaves out,
    # as closest, hint and reason name theirs.
    error = UnknownCode(
        "reporter_code",
        "CHE",
        list_name="Reporters",
        fetched=FETCHED,
        hint="CHE is the ISO alpha-3 code of 757 (Switzerland): pass 757.",
        reason="Upstream answers a code it does not have with count 0.",
        source="example",
        outdated=False,
    )
    assert str(error) == (
        "'CHE' is not a reporter_code in the packaged Reporters list (fetched 2026-10-23). "
        "Nothing was sent. CHE is the ISO alpha-3 code of 757 (Switzerland): pass 757. "
        "Upstream answers a code it does not have with count 0."
    )
    assert (error.param, error.value, error.closest) == ("reporter_code", "CHE", ())
    for clone in [copy.deepcopy(error), *_pickled(error)]:
        assert str(clone) == str(error)
    plain = UnknownCode("reporter_code", 0, list_name="Reporters", fetched=FETCHED, outdated=False)
    assert str(plain) == (
        f"0 is not a reporter_code in the packaged Reporters list (fetched 2026-10-23). {UNSENT}"
    )
    kept = UnknownCode("reporter_code", 0, list_name="Reporters", fetched=FETCHED, outdated=True)
    assert str(kept).endswith(f"(fetched 2026-10-23). {UNSENT} {REFRESH}")  # the default, aloud


def test_unknown_code_names_a_bare_code_once_and_no_command_of_a_maintainer() -> None:
    # A list of bare values, a source's state_alpha: each value is its own name
    # (https://github.com/xippios/sdk-core/issues/111).
    closest = [("VA", "VA"), ("VT", "Vermont")]
    error = UnknownCode(
        "state_alpha", "VS", list_name="state_alpha", fetched=FETCHED, closest=closest
    )
    assert str(error) == (
        "'VS' is not a state_alpha in the packaged state_alpha list (fetched 2026-10-23). "
        f"{UNSENT} Did you mean VA, VT (Vermont)? {REFRESH}"
    )
    assert "/refresh-reference-data" not in str(error)
    assert error.closest == tuple(closest)
    by_id = UnknownCode("attribute_id", 98, list_name="ids", fetched=FETCHED, closest=[(99, "99")])
    assert "Did you mean 99? " in str(by_id)


def test_query_too_large_words_the_count_the_limit_and_what_narrows_the_query() -> None:
    # A source's gate on its countOnly count (ADR-0053, decision 1).
    narrow = "Split by period (max 12 per call), then by reporter."
    error = QueryTooLarge(5_006_385, limit=100_000, narrow=narrow, source="example")
    assert isinstance(error, InvalidRequestError)
    assert str(error) == (
        "query would return 5,006,385 records; upstream serves at most 100,000 per call. " + narrow
    )
    assert (error.count, error.limit, error.narrow) == (5_006_385, 100_000, narrow)
    assert error.source == "example"


def test_query_too_large_takes_no_size_read_from_the_arguments() -> None:
    # The form of a bound read from the arguments had one caller, whose tasks the boundary of
    # a source package takes out (https://github.com/xippios/sdk-core/issues/481, part 3).
    with pytest.raises(TypeError, match="bound"):
        QueryTooLarge(  # type: ignore[call-arg]
            100_008, limit=100_000, narrow="Name fewer.", bound=True
        )
    assert not hasattr(QueryTooLarge(5, limit=1, narrow="Split."), "bound")


def test_query_too_large_without_a_count_says_upstream_refused_the_query() -> None:
    # A source's classify, for upstream's HTTP 413 over the record limit.
    error = QueryTooLarge(None, limit=50_000, narrow="Narrow the filters.")
    assert str(error) == (
        "upstream refused the query as too large; it serves at most 50,000 records per call. "
        "Narrow the filters."
    )
    assert (error.count, error.limit) == (None, 50_000)


def test_query_too_large_names_no_request_unless_given() -> None:
    # The package's own refusals, before the data request, name none (conventions §5).
    for error in (
        QueryTooLarge(5_006_385, limit=100_000, narrow="Split."),
        QueryTooLarge(None, limit=50_000, narrow="Narrow."),
    ):
        assert error.request is None
        assert "GET" not in str(error)


def test_query_too_large_from_classify_names_its_request_without_a_count() -> None:
    # A source's classify, for upstream's HTTP 413 (conventions §5; ADR-0043).
    response = _response(413, '{"error": ["exceeds limit=50000"]}')
    error = QueryTooLarge(
        None,
        limit=50_000,
        narrow="Narrow the filters.",
        request=errors.request_description(response),
        source="example",
    )
    assert str(error) == (
        "upstream refused GET /v1/thing as too large; it serves at most 50,000 records per "
        "call. Narrow the filters."
    )
    assert error.request == "GET /v1/thing"
    assert "api.example.test" not in str(error)
    assert "not-for-the-message" not in str(error)


def test_query_too_large_from_classify_names_its_request_beside_upstream_s_count() -> None:
    # A source's classify, for upstream's refusal that prints its estimate.
    request = errors.request_description(_response(413))
    error = QueryTooLarge(13_344_840, limit=5_000_000, narrow="Name fewer.", request=request)
    assert str(error) == (
        "GET /v1/thing would return 13,344,840 records; upstream serves at most 5,000,000 per "
        "call. Name fewer."
    )


def test_a_source_s_subclass_keeps_its_own_attribute_and_core_s_wording() -> None:
    error = YearTooLarge(57_873_464, year=2021)
    assert isinstance(error, QueryTooLarge)
    assert (error.count, error.limit, error.year) == (57_873_464, 50_000, 2021)
    assert str(error) == (
        "query would return 57,873,464 records; upstream serves at most 50,000 per call. "
        "Year 2021 alone is over it, so split_by_year cannot fetch it. Narrow the filters."
    )
