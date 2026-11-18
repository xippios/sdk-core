"""Errors cross the MCP boundary as text, never as exceptions (conventions §8)."""

from mcp.types import CallToolResult, TextContent

from xippios.core.errors import RateLimitError, XippiosError

__all__ = ["error_to_text"]


def error_to_text(exc: XippiosError) -> str:
    """``error: <ErrorClass>: <message>``, plus a retry hint for rate limits."""
    text = f"error: {type(exc).__name__}: {exc}"
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        text += f" (retry after {exc.retry_after:.0f} s)"
    return text


def _error_answer(exc: XippiosError) -> CallToolResult:
    """The family's error text as a tool's answer flagged ``is_error``, not an MCP error.

    A client tells the answer from data by the flag and an agent reads the text, which
    stays conventions §8's (https://github.com/xippios/sdk-core/issues/168; ADR-0026,
    decision 6 and its amendment of 2026-11-18).
    """
    return CallToolResult(
        content=[TextContent(type="text", text=error_to_text(exc))], is_error=True
    )
