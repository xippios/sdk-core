"""Errors cross the MCP boundary as text, never as exceptions (conventions §8)."""

from xippios.core.errors import RateLimitError, XippiosError

__all__ = ["error_to_text"]


def error_to_text(exc: XippiosError) -> str:
    """``error: <ErrorClass>: <message>``, plus a retry hint for rate limits."""
    text = f"error: {type(exc).__name__}: {exc}"
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        text += f" (retry after {exc.retry_after:.0f} s)"
    return text
