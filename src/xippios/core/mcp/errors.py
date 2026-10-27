"""Errors cross the MCP boundary as text, never as exceptions (conventions §8)."""

import pydantic

from xippios.core.errors import InvalidRequestError, RateLimitError, XippiosError

__all__ = ["error_to_text"]


def error_to_text(exc: XippiosError) -> str:
    """``error: <ErrorClass>: <message>``, plus a retry hint for rate limits."""
    text = f"error: {type(exc).__name__}: {exc}"
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        text += f" (retry after {exc.retry_after:.0f} s)"
    return text


def _refused_arguments(exc: pydantic.ValidationError) -> InvalidRequestError:
    """The error for arguments a tool's schema refuses: ``<argument>: <pydantic message>``.

    The first error only, with the count when there are several; never pydantic's URL,
    the input type or the input value, which is the caller's data (queue row 41 a).
    """
    errors = exc.errors(include_url=False, include_context=False, include_input=False)
    first = errors[0]
    argument = ".".join(str(part) for part in first["loc"]) or "arguments"
    more = f" (the first of {len(errors)} errors)" if len(errors) > 1 else ""
    return InvalidRequestError(f"{argument}: {first['msg']}{more}")
