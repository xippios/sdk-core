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
    RateLimitError,
    TransportError,
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
    # sdk-cashctrl: a multi-tenant source's host names the tenant.
    request = httpx.Request(
        "POST", "https://acme-holding.cashctrl.test/api/v1/journal/create.json?lang=de"
    )
    response = httpx.Response(status, text="refused", request=request)
    error = error_from_response(response, source="example")
    assert isinstance(error, cls)
    message = str(error)
    assert message == f"{status} from POST /api/v1/journal/create.json: refused"
    assert "acme-holding" not in message
    assert "cashctrl.test" not in message
    assert "lang=" not in message


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


@pytest.mark.parametrize("value", [None, "", "soon", "-5"])
def test_parse_retry_after_unparseable(value: str | None) -> None:
    assert parse_retry_after(value) is None


def test_transport_error_from_httpx() -> None:
    request = httpx.Request("GET", "https://api.example.test/")
    exc = httpx.ConnectTimeout("timed out", request=request)
    error = error_from_exception(exc, source="example")
    assert isinstance(error, TransportError)
    assert str(error) == "ConnectTimeout: timed out"
    assert error.source == "example"


def test_transport_error_never_names_the_host() -> None:
    # CPython's text for a TLS hostname mismatch quotes the host, here a tenant's.
    request = httpx.Request("GET", "https://tenant.cashctrl.com/x")
    exc = httpx.ConnectError(
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, "
        "certificate is not valid for 'tenant.cashctrl.com'. (TENANT.CASHCTRL.COM)",
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
        for name in ("status", "retry_after", "raw", "body", "fields", "upstream_message"):
            assert getattr(clone, name, None) == getattr(error, name, None)


def test_every_taxonomy_class_is_covered() -> None:
    taxonomy = {
        cls
        for name in errors.__all__
        if isinstance(cls := getattr(errors, name), type) and issubclass(cls, XippiosError)
    }
    assert len(taxonomy) == 9
    assert {type(error) for error in ERRORS} == taxonomy | {RequestRejected}
