"""Error taxonomy shared by every xippios package (conventions §5).

Source packages subclass these only when upstream has a distinct, documented failure
mode. Adapters convert them to text (MCP) or problem details (HTTP) and never leak
tracebacks.
"""

import email.utils
import math
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any, NoReturn

import httpx

__all__ = [
    "BODY_LIMIT",
    "AuthError",
    "ConfigError",
    "InvalidRequestError",
    "NotFoundError",
    "RateLimitError",
    "TransportError",
    "UnknownCode",
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


# Part of the pickle format: every pickled error names xippios.core.errors._rebuild, so
# renaming or moving it breaks unpickling errors written by an earlier version.
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

    Its ``str`` and ``repr`` are the message alone; the payload is on ``raw`` only.

    Attributes:
        raw: The decoded payload (or body text) that failed to validate.
    """

    def __init__(self, message: str, *, raw: object, source: str | None = None) -> None:
        super().__init__(message, source=source)
        self.raw = raw


def _raise(error: XippiosError) -> NoReturn:
    """Raise ``error`` without a chained cause, from a frame that holds nothing else.

    A printed traceback shows the raising frame in full, its arguments included (pytest's
    default ``--tb=auto``). Raised here, that frame holds the error alone, whose ``repr``
    is its message, and the caller's frame, which holds the payload, is a middle entry
    printed short: no upstream data reaches the report (queue row 42).
    """
    raise error from None


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
    """The request as given cannot be served (ADR-0007, as amended 2026-10-24).

    A bad argument or a documented refusal, detected before the call or by upstream's own
    refusal of the query, which the source maps in ``ClientConfig.classify``. Either way
    the caller has to change the request. Source packages subclass it for their
    documented refusals. Adapters answer with text (MCP) or HTTP 422.
    """


class UnknownCode(InvalidRequestError):
    """A value the packaged reference list does not contain, refused before any call.

    For an upstream that answers an unknown code with an empty result, the same answer as
    a query without data: the source checks the value against its ``PackagedList`` first
    and refuses one the list lacks, naming the closest known codes (ADR-0022). A source
    finds them with ``xippios.core.closest`` or with a strategy of its own (nearest by
    number, ISO codes first) and passes the result. The message names the value, the
    parameter, the list with its fetch date, the closest codes (``Did you mean 0410000
    (Wheat), 0440000 (Corn)?``) unless ``hint`` is given, the ``reason`` when given, and
    that a code upstream added since needs a refresh of the packaged list
    (``/refresh-reference-data``).

    Args:
        param: The parameter, as the package names it, e.g. ``"commodity_code"``.
        value: The value given, e.g. ``"0410001"``, or ``999``.
        list_name: The packaged list checked, as upstream names it, e.g.
            ``"commodities"``.
        fetched: When the list was fetched, ``PackagedList.fetched``; the message names
            its day, e.g. ``2026-10-23``.
        closest: Known codes close to ``value`` with their upstream names, best match
            first, e.g. ``[("0410000", "Wheat")]``; empty when none is close.
        hint: A sentence that explains the value instead of the closest codes, e.g.
            ``"Omit country_code for every country."``; when given, ``closest`` is not
            named in the message.
        reason: Why the package refuses the value rather than asking upstream, e.g.
            ``"PSD answers unknown codes with an empty result, so the package refuses
            them."``.
        source: Source slug, e.g. ``"usda-psd"``.

    Attributes:
        param: As given.
        value: As given.
        list_name: As given.
        fetched: As given.
        closest: As given, a tuple.
    """

    def __init__(
        self,
        param: str,
        value: str | int,
        *,
        list_name: str,
        fetched: date,
        closest: Sequence[tuple[str | int, str]] = (),
        hint: str | None = None,
        reason: str | None = None,
        source: str | None = None,
    ) -> None:
        if hint is None and closest:
            hint = "Did you mean " + ", ".join(f"{code} ({name})" for code, name in closest) + "?"
        article = "an" if param[:1] in set("aeiou") else "a"
        super().__init__(
            f"{value!r} is not {article} {param} in the packaged {list_name} list (fetched "
            f"{fetched:%Y-%m-%d}).{' ' + hint if hint else ''}{' ' + reason if reason else ''} "
            "If upstream added it since, the packaged list needs a refresh "
            "(/refresh-reference-data).",
            source=source,
        )
        self.param = param
        self.value = value
        self.list_name = list_name
        self.fetched = fetched
        self.closest = tuple(closest)


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Convert a ``Retry-After`` header into seconds to wait.

    Args:
        value: The header value, either delay-seconds (``"120"``) or an HTTP-date.
        now: Reference time for HTTP-date values; defaults to the current UTC time.

    Returns:
        Non-negative, finite seconds, or ``None`` when the header is absent or
        unparseable: delay-seconds are ASCII digits only (``"²"`` is not a number of
        seconds), and one too long to be a float is ignored.
    """
    if value is None:
        return None
    text = value.strip()
    if text.isascii() and text.isdigit():
        seconds = float(text)
        return seconds if math.isfinite(seconds) else None
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):  # a huge zone offset overflows
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
    """Wrap an ``httpx`` request failure (timeout, connection, protocol) as TransportError.

    The request's host is replaced by ``<host>`` wherever the failure's text quotes it, as
    a TLS hostname mismatch does: the host may name a tenant (ADR-0005).
    """
    text = str(exc)
    for host in _hosts(exc):
        text = re.sub(re.escape(host), "<host>", text, flags=re.IGNORECASE)
    return TransportError(f"{type(exc).__name__}: {text}", source=source)


def _hosts(exc: httpx.RequestError) -> set[str]:
    """The request's host as written and in its ASCII (IDNA) form; empty without a request."""
    try:
        url = exc.request.url
    except RuntimeError:  # httpx raises it when no request is attached
        return set()
    return {host for host in (url.host, url.raw_host.decode("ascii")) if host}
