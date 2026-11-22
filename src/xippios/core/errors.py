"""Error taxonomy shared by every xippios package (conventions §5).

Source packages subclass these only when upstream has a distinct, documented failure
mode. Adapters convert them to text (MCP) or problem details (HTTP) and never leak
tracebacks.
"""

import email.utils
import math
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, NoReturn

import httpx

__all__ = [
    "BODY_LIMIT",
    "AuthError",
    "ConfigError",
    "InvalidRequestError",
    "NotFoundError",
    "QueryTooLarge",
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
    "request_description",
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
    """The request as given cannot be served (ADR-0007, as amended 2026-10-24 and 2026-11-18).

    A bad argument or a documented refusal, detected before the call, by upstream's own
    refusal of the query, which the source maps in ``ClientConfig.classify``, or from a
    successful answer the task cannot serve as asked. Each way the caller has to change
    the request. Source packages subclass it for their documented refusals. Adapters
    answer with text (MCP) or HTTP 422.
    """


class UnknownCode(InvalidRequestError):
    """A value the packaged reference list does not contain, refused before any call.

    For an upstream that answers an unknown code with an empty result, the same answer as
    a query without data: the source checks the value against its ``PackagedList`` first
    and refuses one the list lacks, naming the closest known codes (ADR-0041). A source
    finds them with ``xippios.core.closest``, with ``xippios.core.nearest`` for integer
    codes, or with a strategy of its own (ISO codes first) and passes the result. The
    message names the value, the parameter, the list with its fetch date, the closest codes
    (``Did you mean 0410000 (Wheat), 0440000 (Corn)?``, and a code whose name is its own
    text named once, ``Did you mean VA?``) unless ``hint`` is given, the ``reason`` when
    given, and that the packaged list is out of date if upstream added the value since. An
    agent reads the message over MCP, so it names no command of the package's maintainers.

    Args:
        param: The parameter, as the package names it, e.g. ``"commodity_code"``.
        value: The value given, e.g. ``"0410001"``, or ``999``.
        list_name: The packaged list checked, as upstream names it, e.g.
            ``"commodities"``.
        fetched: When the list was fetched, ``PackagedList.fetched``; the message names
            its day, e.g. ``2026-10-23``.
        closest: Known codes close to ``value`` with their upstream names, best match
            first, e.g. ``[("0410000", "Wheat")]``, or ``[("VA", "VA")]`` for a list of
            bare values; empty when none is close.
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
            named = (
                str(code) if name == str(code) else f"{code} ({name})" for code, name in closest
            )
            hint = f"Did you mean {', '.join(named)}?"
        article = "an" if param[:1] in set("aeiou") else "a"
        super().__init__(
            f"{value!r} is not {article} {param} in the packaged {list_name} list (fetched "
            f"{fetched:%Y-%m-%d}).{' ' + hint if hint else ''}{' ' + reason if reason else ''} "
            "If upstream added it since, the packaged list is out of date.",
            source=source,
        )
        self.param = param
        self.value = value
        self.list_name = list_name
        self.fetched = fetched
        self.closest = tuple(closest)


class QueryTooLarge(InvalidRequestError):
    """A query over upstream's per-call record limit, refused before its data is fetched.

    Raised by ``fetch_counted`` when upstream's count of the query's records is over the
    limit, by a task whose arguments bound its rows over the limit, with ``bound=True`` and
    before any request, and by a source's ``classify`` for upstream's own refusal of a query
    as too large, with no count (ADR-0053). Core words the message from the fields, in one
    of three forms with ``narrow`` last, so every source's refusal reads alike::

        query would return 5,006,385 records; upstream serves at most 100,000 per call.
        query could return up to 100,008 records, a size read from its arguments with
        nothing counted or sent; upstream serves at most 100,000 per call.
        upstream refused the query as too large; it serves at most 50,000 records per call.

    The error a source's ``classify`` maps from upstream's answer names its request, as
    conventions §5 ask of every message about an answer: given ``request``, the message
    names it where the forms say "the query" or "query", ``upstream refused GET /v1/data
    as too large; ...``. The package's own refusal before its data request names none.

    A source subclasses it for an attribute of its own and words it in ``narrow``, as
    sdk-usda-nass keeps the ``year`` that alone is over the limit.

    Args:
        count: The records the query would return, as upstream counted them, e.g.
            ``5_006_385``; with ``bound``, the most it could return, read from its
            arguments; ``None`` where upstream refused the query as too large without a
            count.
        limit: The most records upstream serves per call, e.g. ``100_000``.
        narrow: What narrows the query, the sentences that end the message, e.g.
            ``"Split by period, then by reporter."``.
        bound: ``True`` where ``count`` was read from the arguments and nothing counted.
        request: The request upstream refused, as ``request_description(response)`` gives
            it, e.g. ``"GET /v1/data"``, for the error a source's ``classify`` maps;
            ``None``, the default, for a refusal before the data request.
        source: Source slug, e.g. ``"comtrade"``.

    Attributes:
        count: As given.
        limit: As given.
        narrow: As given.
        bound: As given.
        request: As given.

    Raises:
        ValueError: ``bound`` is ``True`` and ``count`` is ``None``, since a bound is a
            number, or ``bound`` is ``True`` with a ``request``, since a size read from the
            arguments is refused before any request and names none.
    """

    def __init__(
        self,
        count: int | None,
        *,
        limit: int,
        narrow: str,
        bound: bool = False,
        request: str | None = None,
        source: str | None = None,
    ) -> None:
        if bound and count is None:
            raise ValueError("bound=True needs the count read from the arguments, not None")
        if bound and request is not None:
            raise ValueError(
                "bound=True names no request: a size read from the arguments is refused before "
                "any request is sent"
            )
        query = "query" if request is None else request
        if count is None:
            refused = "the query" if request is None else request
            size = (
                f"upstream refused {refused} as too large; it serves at most {limit:,} records "
                "per call."
            )
        elif bound:
            size = (
                f"query could return up to {count:,} records, a size read from its arguments "
                f"with nothing counted or sent; upstream serves at most {limit:,} per call."
            )
        else:
            size = (
                f"{query} would return {count:,} records; upstream serves at most {limit:,} "
                "per call."
            )
        super().__init__(f"{size} {narrow}", source=source)
        self.count = count
        self.limit = limit
        self.narrow = narrow
        self.bound = bound
        self.request = request


def _refused_arguments(
    errors: Sequence[Mapping[str, Any]], *, source: str | None = None
) -> InvalidRequestError:
    """The error for arguments an adapter refuses before the task runs.

    ``<argument>: <message>`` for the first of ``errors``, with the count when there are
    several, e.g. ``year: Input should be a valid integer (the first of 2 errors)``. Each
    error is read for its ``loc``, the argument's path joined with dots, and its ``msg``
    alone, as pydantic's error details carry them; its input value, input type and URL are
    the caller's data and never read (ADR-0036, decision 12; ADR-0007, amendment
    2026-11-18). Both adapters answer with it, the MCP adapter as text and the HTTP router
    as problem details.

    Args:
        errors: At least one error, each a mapping with ``loc`` and ``msg``.
        source: Source slug, e.g. ``"usda-nass"``, which an HTTP problem names.
    """
    first = errors[0]
    argument = ".".join(str(part) for part in first["loc"]) or "arguments"
    more = f" (the first of {len(errors)} errors)" if len(errors) > 1 else ""
    return InvalidRequestError(f"{argument}: {first['msg']}{more}", source=source)


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


def request_description(response: httpx.Response) -> str:
    """The request ``response`` answers, as error messages name it: its method and path.

    ``GET /v1/x`` for an answer to ``https://host.test/v1/x?year=2024``: never the host,
    which can name a tenant, nor the query, which can carry a key (conventions §5,
    ADR-0030). ``error_from_response`` words its messages with it, and so does a source's
    ``classify`` for the errors it maps (ADR-0030, decision 4).

    Args:
        response: A response with its request, e.g. the one ``classify`` is given.
    """
    request = response.request
    return f"{request.method} {request.url.path}"


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
    message = f"{status} from {request_description(response)}: {snippet or response.reason_phrase}"
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
    a TLS hostname mismatch does: the host may name a tenant (ADR-0030).
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
