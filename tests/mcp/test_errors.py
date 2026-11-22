from xippios.core.errors import (
    InvalidRequestError,
    NotFoundError,
    QueryTooLarge,
    RateLimitError,
    UpstreamError,
)
from xippios.core.mcp import error_to_text


def test_error_text_format() -> None:
    assert error_to_text(NotFoundError("no series X")) == "error: NotFoundError: no series X"
    assert error_to_text(UpstreamError("502 from host", status=502, body="")) == (
        "error: UpstreamError: 502 from host"
    )


def test_rate_limit_hint() -> None:
    assert error_to_text(RateLimitError("slow down", retry_after=30)) == (
        "error: RateLimitError: slow down (retry after 30 s)"
    )
    assert error_to_text(RateLimitError("slow down")) == "error: RateLimitError: slow down"


def test_invalid_request_text() -> None:
    assert error_to_text(InvalidRequestError("unknown column 'bad'")) == (
        "error: InvalidRequestError: unknown column 'bad'"
    )


def test_query_too_large_is_printed_by_the_name_both_sources_print() -> None:
    error = QueryTooLarge(85_535, limit=50_000, narrow="Narrow the filters.")
    assert error_to_text(error) == (
        "error: QueryTooLarge: query would return 85,535 records; upstream serves at most "
        "50,000 per call. Narrow the filters."
    )
