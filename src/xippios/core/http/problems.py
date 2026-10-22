"""Taxonomy errors as RFC 9457 problem details, with one status table for the family."""

from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

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
)

__all__ = [
    "PROBLEM_MEDIA_TYPE",
    "STATUS_BY_ERROR",
    "install_error_handlers",
    "problem_response",
    "status_for",
]

PROBLEM_MEDIA_TYPE = "application/problem+json"

STATUS_BY_ERROR: dict[type[XippiosError], int] = {
    ConfigError: 500,
    AuthError: 502,
    RateLimitError: 429,
    NotFoundError: 404,
    ValidationError: 502,
    UpstreamError: 502,
    TransportError: 504,
    InvalidRequestError: 422,
    XippiosError: 500,
}
"""HTTP status for each error class. Subclasses inherit their nearest ancestor's."""


def status_for(exc: XippiosError) -> int:
    """The status code for ``exc``, walking its class hierarchy."""
    for cls in type(exc).__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return 500  # pragma: no cover - XippiosError itself is in the table


def problem_response(exc: XippiosError) -> JSONResponse:
    """A problem-details response for ``exc``.

    The ``type`` is a stable URN naming the error class; ``title`` is the class name;
    ``detail`` is the message. ``source``, ``retry_after`` and ``upstream_status`` are
    added when the error carries them.
    """
    name = type(exc).__name__
    status = status_for(exc)
    body: dict[str, Any] = {
        "type": f"urn:xippios:error:{name}",
        "title": name,
        "status": status,
        "detail": exc.message,
    }
    headers: dict[str, str] = {}
    if exc.source is not None:
        body["source"] = exc.source
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        body["retry_after"] = exc.retry_after
        headers["Retry-After"] = str(int(exc.retry_after))
    if isinstance(exc, UpstreamError | AuthError):
        body["upstream_status"] = exc.status
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=headers
    )


async def _handle(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, XippiosError):  # pragma: no cover - registered for XippiosError only
        raise exc
    return problem_response(exc)


def install_error_handlers(app: FastAPI) -> None:
    """Make ``app`` answer every ``XippiosError`` with problem details."""
    app.add_exception_handler(XippiosError, _handle)
