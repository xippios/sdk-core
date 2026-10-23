"""Error taxonomy shared by every xippios package (conventions §5).

Source packages subclass these only when upstream has a distinct, documented failure
mode. Adapters convert them to text (MCP) or problem details (HTTP) and never leak
tracebacks.
"""

import email.utils
from datetime import UTC, datetime
from typing import Any

import httpx

__all__ = [
    "BODY_LIMIT",
    "AuthError",
    "ConfigError",
    "InvalidRequestError",
    "NotFoundError",
    "RateLimitError",
    "TransportError",
    "UpstreamError",
    "ValidationError",
    "XippiosError",
    "error_from_exception",
    "error_from_response",
    "parse_retry_after",
    "raise_for_status",
]

BODY_LIMIT = 16_384
"""Characters of an upstream response body kept on an error."""

_SNIPPET = 200


class XippiosError(Exception):
    """Base class for every error raised by the xippios SDK family.

    Attributes:
        message: Human-readable description, safe to show to an agent.
        source: Source slug such as ``"usda-nass"`` when known.
    """

    def __init__(self, message: str, *, source: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.source = source

    def __str__(self) -> str:
        return self.message

    def __reduce__(self) -> tuple[Any, ...]:
        # Exception's default rebuilds with cls(*args), which the keyword-only arguments
        # of AuthError, ValidationError, UpstreamError and source subclasses refuse
        # (TypeError). Rebuild without __init__, then restore every attribute, so copy,
        # deepcopy and pickle work for the whole taxonomy.
        return (_rebuild, (type(self), self.args), self.__dict__)


def _rebuild(cls: type[XippiosError], args: tuple[Any, ...]) -> XippiosError:
    """An instance of ``cls`` with ``args`` and no attributes yet; see ``__reduce__``."""
    return cls.__new__(cls, *args)


class ConfigError(XippiosError):
    """A key is missing or the settings are invalid."""


class AuthError(XippiosError):
    """Upstream rejected our credentials (401 or 403).

    Attributes:
        status: The HTTP status code upstream returned.
    """

    def __init__(self, message: str, *, status: int, source: str | None = None) -> None:
        super().__init__(message, source=source)
        self.status = status


class RateLimitError(XippiosError):
    """Upstream rate limit reached (429).

    Attributes:
        retry_after: Seconds to wait before retrying, when upstream said so.
    """

    def __init__(
        self, message: str, *, retry_after: float | None = None, source: str | None = None
    ) -> None:
        super().__init__(message, source=source)
        self.retry_after = retry_after


class NotFoundError(XippiosError):
    """Upstream signals absence: 404, or an empty result where that means not found."""


class ValidationError(XippiosError):
    """We could not parse what upstream returned.

    Attributes:
        raw: The decoded payload (or body text) that failed to validate.
    """

    def __init__(self, message: str, *, raw: object, source: str | None = None) -> None:
        super().__init__(message, source=source)
        self.raw = raw


class UpstreamError(XippiosError):
    """Any other 4xx or 5xx from upstream.

    Attributes:
        status: The HTTP status code.
        body: The response body, truncated to ``BODY_LIMIT`` characters.
    """

    def __init__(self, message: str, *, status: int, body: str, source: str | None = None) -> None:
        super().__init__(message, source=source)
        self.status = status
        self.body = body


class TransportError(XippiosError):
    """Network failure or timeout before a usable response arrived."""


class InvalidRequestError(XippiosError):
    """The request cannot be sent as given (ADR-0007).

    A bad argument, or a query the source documents it will refuse, detected before any
    upstream call. Source packages subclass it for their documented refusals. Adapters
    answer with text (MCP) or HTTP 422.
    """


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Convert a ``Retry-After`` header into seconds to wait.

    Args:
        value: The header value, either delay-seconds (``"120"``) or an HTTP-date.
        now: Reference time for HTTP-date values; defaults to the current UTC time.

    Returns:
        Non-negative seconds, or ``None`` when the header is absent or unparseable.
    """
    if value is None:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    return max(0.0, (when - reference).total_seconds())


def _body_text(response: httpx.Response) -> str:
    try:
        return response.text[:BODY_LIMIT]
    except (httpx.ResponseNotRead, UnicodeDecodeError):
        return ""


def _where(response: httpx.Response) -> str:
    # Method and path only: the host may name a tenant (ADR-0005), the query may carry a key.
    url = response.request.url
    return f"{response.request.method} {url.path}"


def error_from_response(
    response: httpx.Response, *, source: str | None = None
) -> XippiosError | None:
    """Classify an HTTP response into the taxonomy.

    Args:
        response: A fully read ``httpx.Response``.
        source: Source slug to attach to the error.

    Returns:
        The matching error for a 4xx/5xx status, or ``None`` for a success.
    """
    status = response.status_code
    if status < 400:
        return None
    body = _body_text(response)
    snippet = " ".join(body[:_SNIPPET].split())
    message = f"{status} from {_where(response)}: {snippet or response.reason_phrase}"
    if status in (401, 403):
        return AuthError(message, status=status, source=source)
    if status == 429:
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        return RateLimitError(message, retry_after=retry_after, source=source)
    if status == 404:
        return NotFoundError(message, source=source)
    return UpstreamError(message, status=status, body=body, source=source)


def raise_for_status(response: httpx.Response, *, source: str | None = None) -> None:
    """Raise the classified error for a 4xx/5xx response; do nothing on success."""
    error = error_from_response(response, source=source)
    if error is not None:
        raise error


def error_from_exception(exc: httpx.RequestError, *, source: str | None = None) -> TransportError:
    """Wrap an ``httpx`` request failure (timeout, connection, protocol) as TransportError."""
    return TransportError(f"{type(exc).__name__}: {exc}", source=source)
