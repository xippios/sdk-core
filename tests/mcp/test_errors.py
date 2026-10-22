from xippios.core.errors import InvalidRequestError, NotFoundError, RateLimitError, UpstreamError
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
