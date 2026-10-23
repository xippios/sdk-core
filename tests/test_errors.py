from datetime import UTC, datetime

import httpx
import pytest

from xippios.core.errors import (
    AuthError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
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
    # sdk-cashctrl, row 7: a multi-tenant source's host names the tenant.
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
