"""The async client: one request path with retries, rate limiting, caching and errors."""

import asyncio
import contextlib
import csv
import inspect
import io
import json
import os
import tempfile
import threading
import time
import weakref
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Final, Self, final

import httpx

from xippios.core.client.cache import CachedResponse, cache_key, strip_wire_headers
from xippios.core.client.config import ClientConfig
from xippios.core.client.download import (
    Downloaded,
    content_disposition_filename,
    head_of,
    stream_to,
    unread_is_none,
)
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries
from xippios.core.errors import (
    BODY_LIMIT,
    UpstreamError,
    ValidationError,
    XippiosError,
    _raise,
    raise_for_status,
)

__all__ = ["Answer", "AsyncClient", "Params", "decode_csv", "decode_json", "decode_text"]

Params = Mapping[str, Any] | None


@final
class _ClientAuth:
    """The type of the default of ``auth=``: the client's own credentials (ADR-0015).

    Core's own sentinel, so no annotation needs httpx's private ``UseClientDefault``;
    ``request`` maps it to ``httpx.USE_CLIENT_DEFAULT`` where the request is sent.
    """

    def __repr__(self) -> str:
        return "<the client's auth>"


_CLIENT_AUTH: Final = _ClientAuth()

_HTTPX_DEFAULT: Final[object] = httpx.USE_CLIENT_DEFAULT
"""httpx's own spelling of the default, outside the annotation: treated as ``_CLIENT_AUTH``."""


class AsyncClient:
    """Async HTTP client for one upstream (conventions §6).

    One instance can be shared by sync facades and async servers alike: it keeps one
    ``httpx`` connection pool per event loop, while the rate limiter, built from
    ``config.rate_limit``, and the cache are shared across all of them. A call to a
    keyless endpoint on the same host passes ``auth=None`` to this client rather than
    going through a second one (ADR-0015).

    Args:
        config: Base URL, timeouts, retry policy, rate limit, cache and headers.
        auth: An ``httpx.Auth`` adding credentials, e.g. a query key or basic auth.
        transport: Replacement transport, for tests.
        sleep: Async sleep used by retries and the rate limiter, replaceable in tests.
    """

    def __init__(
        self,
        config: ClientConfig,
        *,
        auth: httpx.Auth | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.config = config
        self._auth = auth
        self._transport = transport
        self._sleep = sleep
        self._bucket = None if config.rate_limit is None else TokenBucket(config.rate_limit)
        self._pools: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient] = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.Lock()

    @property
    def source(self) -> str:
        """Source slug from the configuration."""
        return self.config.source

    def _pool(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        with self._lock:
            pool = self._pools.get(loop)
            if pool is None:
                pool = httpx.AsyncClient(
                    base_url=self.config.base_url,
                    headers={"User-Agent": self.config.user_agent, **self.config.headers},
                    timeout=self.config.timeouts.to_httpx(),
                    auth=self._auth,
                    transport=self._transport,
                )
                self._pools[loop] = pool
            return pool

    def _cache_key(self, method: str, url: httpx.URL) -> str | None:
        if method != "GET" or self.config.cache is None:
            return None
        return cache_key(method, url)

    def _cache_key_for(self, probe: httpx.Request) -> str | None:
        """The cache key for ``probe``, or ``None`` when the cache or its filter skips it."""
        key = self._cache_key(probe.method, probe.url)
        cache_filter = self.config.cache_filter
        if key is None or cache_filter is None or cache_filter(probe):
            return key
        return None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        raise_on_error: bool = True,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> httpx.Response:
        """Send one request and return the response.

        Retries, rate limiting and caching (GET only, narrowed by
        ``ClientConfig.cache_filter``, a body over ``ClientConfig.cache_max_bytes`` not
        stored) apply as configured. A cache hit returns at once;
        otherwise ``ClientConfig.before_request`` runs once, before the rate limiter, and
        ``ClientConfig.observe`` sees every response from the wire, retried attempts
        included. The source's ``classify`` hook, if any, is asked before a 429 or 5xx
        is retried (its ``RateLimitError`` sets the wait, an error other than an
        ``UpstreamError`` for a 5xx stops the retries, ADR-0015) and sees the final
        response first; otherwise a 4xx/5xx that survives the retry policy is raised as
        the matching error from the taxonomy; a transport failure as ``TransportError``.

        Args:
            method: HTTP method.
            path: Path joined onto the base URL, e.g. ``"/api/api_GET"``.
            params: Query parameters.
            json: JSON body for write methods, e.g. ``{"name": "Corn"}``.
            data: Form body for write methods, sent form-encoded
                (``application/x-www-form-urlencoded``), e.g. ``{"id": 4, "name": "Corn"}``.
                For upstreams whose writes take form fields, not JSON.
            headers: Extra headers for this request only.
            raise_on_error: ``False`` returns 4xx/5xx responses instead of raising, for
                callers that record fixtures or inspect error bodies; ``classify``
                still decides whether a 429 or 5xx is retried.
            auth: Credentials for this request only, every retry included: left at its
                default it sends the client's ``auth``, ``None`` sends none, for a keyless
                endpoint on the same host, and an ``httpx.Auth`` replaces the client's.
                The default and ``None`` share the cache; a call with an ``httpx.Auth`` of
                its own bypasses it, neither looked up nor stored, since another identity
                may get another answer.

        Raises:
            ValueError: Both ``json`` and ``data`` were given; a request has one body.
        """
        if json is not None and data is not None:
            raise ValueError("pass json= or data=, not both: a request has one body")
        pool = self._pool()
        method = method.upper()
        probe = pool.build_request(method, path, params=params)
        # A call with credentials of its own may get another answer: no cache for it. Any
        # explicit auth counts, also a form httpx accepts beyond the annotation (a tuple).
        own_auth = (
            auth is not None and not isinstance(auth, _ClientAuth) and auth is not _HTTPX_DEFAULT
        )
        sent_auth = httpx.USE_CLIENT_DEFAULT if isinstance(auth, _ClientAuth) else auth
        key = None if own_auth else self._cache_key_for(probe)
        if key is not None and self.config.cache is not None:
            cached = self.config.cache.get(key)
            if cached is not None:
                return _from_cache(cached, probe)
        before_request = self.config.before_request
        if before_request is not None:
            # Built as each attempt is, before auth applies; a change to it is not sent.
            built = pool.build_request(
                method, path, params=params, json=json, data=data, headers=headers
            )
            outcome = before_request(built)
            if inspect.isawaitable(outcome):
                await outcome
        observe = self.config.observe

        async def send() -> httpx.Response:
            if self._bucket is not None:
                await self._bucket.acquire(self._sleep)
            request = pool.build_request(
                method, path, params=params, json=json, data=data, headers=headers
            )
            response = await pool.send(request, auth=sent_auth)
            if observe is not None:
                observe(response)
            return response

        classify = None if self.config.classify is None else _ClassifyOnce(self.config.classify)
        response = await send_with_retries(
            send,
            policy=self.config.retry,
            method=method,
            source=self.source,
            sleep=self._sleep,
            classify=classify,
        )
        if raise_on_error:
            if classify is not None:
                classified = classify(response)
                if classified is not None:
                    raise classified
            raise_for_status(response, source=self.source)
        if (
            key is not None
            and self.config.cache is not None
            and response.status_code == 200
            and len(response.content) <= self.config.cache_max_bytes
        ):
            # The content is already decoded: keeping content-encoding would make the
            # replay decode it a second time (httpx.DecodingError on a gzip answer).
            self.config.cache.set(
                key,
                CachedResponse(
                    status=response.status_code,
                    headers=tuple(strip_wire_headers(response.headers.multi_items())),
                    content=response.content,
                    stored_at=time.time(),
                ),
            )
        return response

    async def get(
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> httpx.Response:
        """``request("GET", ...)``; ``auth=None`` sends no credentials."""
        return await self.request("GET", path, params=params, headers=headers, auth=auth)

    async def get_json(
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> Any:
        """GET and decode a JSON body, raising ``ValidationError`` when it is not JSON.

        ``auth`` as for ``request``: ``None`` sends no credentials. A wrapper whose
        answer may come from the cache calls ``get_answer``, which also says when the
        answer was retrieved.
        """
        response = await self.get(path, params=params, headers=headers, auth=auth)
        return decode_json(response, source=self.source, path=path)

    async def get_answer(
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> "Answer":
        """GET and decode a JSON body with the time it was retrieved (conventions §4).

        ``get_json``'s call and decoding, and the ``retrieved_at`` a task puts into its
        ``ResultMeta``: on a cache hit the time the entry was stored, read from
        ``xippios_cache_stored_at`` (ADR-0015, decision 5), else the time the answer
        arrived. ``auth`` as for ``request``.

        Args:
            path: Path joined onto the base URL, e.g. ``"/api/gats/regions"``.
            params: Query parameters.
            headers: Extra headers for this request only.
            auth: The client's credentials by default, ``None`` for none, an
                ``httpx.Auth`` to replace them.

        Returns:
            The ``Answer``: the decoded payload and ``retrieved_at``, timezone-aware UTC.

        Raises:
            ValidationError: The body is not JSON.
        """
        response = await self.get(path, params=params, headers=headers, auth=auth)
        stored_at = response.extensions.get("xippios_cache_stored_at")
        payload = decode_json(response, source=self.source, path=path)
        if stored_at is None:
            return Answer(payload, datetime.now(UTC))
        return Answer(payload, datetime.fromtimestamp(stored_at, UTC))

    async def download(
        self,
        url: str,
        dest: str | os.PathLike[str],
        *,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> Downloaded:
        """Stream a file to ``dest`` with a GET, never holding its body in memory (ADR-0019).

        The body is written chunk by chunk to a temporary file in ``dest``'s directory
        and renamed to ``dest`` once complete, replacing a file there; on any failure the
        temporary file is removed and ``dest`` is left as it was. The response cache is
        neither looked up nor stored. Otherwise it goes as ``get()`` goes:
        ``ClientConfig.before_request`` runs once, before the rate limiter; the limiter
        paces every attempt; ``ClientConfig.observe`` sees every response from the wire;
        the retry rule of ADR-0011 applies to a GET, so a 429, a 5xx or a transport
        failure, one in the middle of the body included, is retried and the retry
        restarts the file. An error answer is read up to ``BODY_LIMIT`` bytes, for
        ``observe``, ``classify`` and the error's text, and raised through the taxonomy
        as ``get()`` raises it. Two things differ from ``get()``. A success's body goes
        to the file unread, so ``observe`` and ``classify`` see its status and headers
        only: a hook that reads the body finds it unread (``httpx.ResponseNotRead``),
        which counts as nothing observed and as ``None``, and an error ``classify``
        returns is raised before anything is written. And redirects are not followed,
        as for ``get()``, but a 1xx or 3xx answer raises ``UpstreamError`` where
        ``get()`` returns it.

        Args:
            url: An absolute URL, e.g. a file link from a catalog, or a path joined onto
                the base URL, e.g. ``"/files/qs.crops_20261027.txt.gz"``.
            dest: The file to write, e.g. ``tmp_path / "qs.crops.txt.gz"``, in a directory
                that exists.
            auth: Credentials for this download, every retry included, as for
                ``request``: the client's by default, ``None`` for none, an
                ``httpx.Auth`` to replace them. The default sends the client's key to an
                absolute URL on another host too; pass ``None`` for a file link there.

        Returns:
            The ``Downloaded`` file: path, size, content type, file name, ``ETag``,
            ``Last-Modified`` and when it was complete.

        Raises:
            ValueError: ``dest`` is a directory, or its directory does not exist;
                nothing is sent.
            XippiosError: The taxonomy error for the answer (``classify`` first, then the
                status), ``UpstreamError`` for a 1xx or 3xx, ``TransportError`` for a
                transport failure that is not retried; ``dest`` is untouched.
        """
        target = Path(dest)
        if target.is_dir():
            raise ValueError("dest is a directory; name the file to write")
        if not target.parent.is_dir():
            raise ValueError("dest's directory does not exist; create it first")
        pool = self._pool()
        sent_auth = httpx.USE_CLIENT_DEFAULT if isinstance(auth, _ClientAuth) else auth
        handle, name = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.", suffix=".part"
        )
        os.close(handle)
        partial = Path(name)
        try:
            before_request = self.config.before_request
            if before_request is not None:
                outcome = before_request(pool.build_request("GET", url))
                if inspect.isawaitable(outcome):
                    await outcome
            observe = self.config.observe
            classify = (
                None
                if self.config.classify is None
                else _ClassifyOnce(unread_is_none(self.config.classify))
            )
            written = 0

            async def send() -> httpx.Response:
                nonlocal written
                if self._bucket is not None:
                    await self._bucket.acquire(self._sleep)
                request = pool.build_request("GET", url)
                streamed = await pool.send(request, auth=sent_auth, stream=True)
                try:
                    response = streamed if streamed.is_success else await head_of(streamed)
                    if observe is not None:
                        # A success's body goes to the file unread: a hook reading it sees
                        # nothing, as classify does (unread_is_none).
                        with contextlib.suppress(httpx.ResponseNotRead):
                            observe(response)
                    if response.is_success and (classify is None or classify(response) is None):
                        written = await stream_to(response, partial)
                finally:
                    await streamed.aclose()
                return response

            response = await send_with_retries(
                send,
                policy=self.config.retry,
                method="GET",
                source=self.source,
                sleep=self._sleep,
                classify=classify,
            )
            if classify is not None:
                classified = classify(response)
                if classified is not None:
                    raise classified
            raise_for_status(response, source=self.source)
            if not response.is_success:
                raise UpstreamError(
                    f"{response.status_code} from GET {response.request.url.path}: a download "
                    "writes a 2xx answer only, and redirects are not followed",
                    status=response.status_code,
                    body=response.text[:BODY_LIMIT],
                    source=self.source,
                )
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        headers = response.headers
        return Downloaded(
            path=target,
            bytes=written,
            content_type=headers.get("content-type"),
            filename=content_disposition_filename(headers.get("content-disposition")),
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            retrieved_at=datetime.now(UTC),
        )

    async def aclose(self) -> None:
        """Close the connection pool bound to the current event loop.

        A transport passed to this client is closed with it, as httpx does.
        """
        loop = asyncio.get_running_loop()
        with self._lock:
            pool = self._pools.pop(loop, None)
        if pool is not None:
            await pool.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


@dataclass(frozen=True, slots=True)
class Answer:
    """A decoded JSON answer and when it was retrieved: what ``get_answer`` returns.

    Attributes:
        payload: The body as ``get_json`` decodes it, e.g. ``{"data": [...]}``.
        retrieved_at: Timezone-aware UTC: on a cache hit the time the entry was stored,
            else the time the answer arrived; a task's ``ResultMeta.retrieved_at``.
    """

    payload: Any
    retrieved_at: datetime


def decode_json(
    response: httpx.Response, *, source: str | None = None, path: str | None = None
) -> Any:
    """Decode ``response``'s JSON body, raising ``ValidationError`` when it is not JSON.

    What ``get_json`` and ``get_answer`` do after ``get``. A wrapper that needs more of
    the response than its payload and ``get_answer``'s ``retrieved_at`` (a header, say)
    calls ``get`` and then this.

    Args:
        response: A response with its body read, e.g. from ``AsyncClient.get``.
        source: Source slug for the error, e.g. ``"usda-psd"``.
        path: The request path the message names, e.g. ``"/api/psd/regions"``; ``None``
            takes the path of the response's request. Never the host or query
            (conventions §5).

    Raises:
        ValidationError: The body is not JSON; raised ``from None``, the text naming the
            decoder's message and position (``... is not JSON: Expecting value at line 1
            column 1 (char 0)``), ``raw`` the body's text, truncated (queue row 42).
    """
    try:
        return response.json()
    except ValueError as exc:
        _raise(
            ValidationError(
                f"{source + ': ' if source else ''}{_where(response, path)} is not JSON: "
                f"{_reason(exc)}",
                raw=response.text[:BODY_LIMIT],
                source=source,
            )
        )


def _reason(exc: ValueError) -> str:
    """What a decoder said and where, never the text it read (queue row 42)."""
    if isinstance(exc, json.JSONDecodeError):
        return f"{exc.msg} at line {exc.lineno} column {exc.colno} (char {exc.pos})"
    if isinstance(exc, UnicodeDecodeError):
        return f"{exc.reason} at byte {exc.start}"
    return type(exc).__name__


def _where(response: httpx.Response, path: str | None) -> str:
    """``response from <path>`` for an error message, the request's path when not given."""
    if path is None:
        try:
            path = response.request.url.path
        except RuntimeError:  # httpx raises it for a response built without a request
            path = None
    return f"response from {path}" if path else "response"


def decode_text(
    response: httpx.Response, *, source: str | None = None, path: str | None = None
) -> str:
    """``response``'s body as text, in the charset its ``Content-Type`` names (ADR-0019).

    UTF-8 when the header names none; a leading byte order mark is stripped. For a CSV,
    TXT or XML answer read through ``get``; a file streamed to disk is read with
    ``decode_csv(path)`` or by the source.

    Args:
        response: A response with its body read, e.g. from ``AsyncClient.get``.
        source: Source slug for the error, e.g. ``"eurostat"``.
        path: The request path the message names; ``None`` takes the path of the
            response's request. Never the host or query (conventions §5).

    Raises:
        ValidationError: The body is not text in that charset, or the charset is
            unknown; raised ``from None``, the text naming the decoder's reason and the
            byte, ``raw`` the first ``BODY_LIMIT`` bytes (queue row 42).
    """
    charset = response.charset_encoding or "utf-8"
    try:
        text = response.content.decode(charset)
    except (LookupError, UnicodeDecodeError) as exc:
        reason = _reason(exc) if isinstance(exc, UnicodeDecodeError) else "an unknown charset"
        _raise(
            ValidationError(
                f"{source + ': ' if source else ''}{_where(response, path)} is not {charset} "
                f"text: {reason}",
                raw=response.content[:BODY_LIMIT],
                source=source,
            )
        )
    return text.removeprefix("\ufeff")


def decode_csv(
    data: Path | str | httpx.Response, *, delimiter: str = ",", source: str | None = None
) -> Iterator[dict[str, str]]:
    r"""The rows of a CSV file or answer, one mapping per row, headers as upstream prints them.

    The stdlib's ``csv.DictReader`` reads the first row as the header and each further
    row as a mapping from header to text; nothing is converted, renamed or stripped
    (ADR-0003). A row shorter than the header maps the missing columns to ``None``, and
    a longer one keeps the extra values as a list under ``None``, as ``DictReader``
    does. A generator: a file of hundreds of MB is read row by row, never whole, and is
    closed when the generator ends or is closed; ``list(decode_csv(path))`` reads it all.

    Args:
        data: A downloaded file, as a path, read as UTF-8 with a byte order mark
            stripped, e.g. ``downloaded.path``; or a response with its body read,
            decoded by ``decode_text``. A gzip or zip file is opened by the source with
            the stdlib.
        delimiter: The field separator, e.g. ``"\t"`` for a tab-separated file.
        source: Source slug for the error, e.g. ``"usda-nass"``.

    Raises:
        ValidationError: The text is not UTF-8 (or not in the response's charset), or
            not CSV the stdlib can read, e.g. a field over its size limit; raised while
            iterating, at the row where it is found, ``from None``, naming the decoder's
            or the csv module's message, never the text.
    """
    if isinstance(data, httpx.Response):
        text = io.StringIO(decode_text(data, source=source), newline="")
        yield from _rows(text, delimiter, "response", source)
        return
    path = Path(data)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from _rows(handle, delimiter, path.name, source)


def _rows(
    handle: IO[str], delimiter: str, name: str, source: str | None
) -> Iterator[dict[str, str]]:
    prefix = f"{source}: " if source else ""
    try:
        yield from csv.DictReader(handle, delimiter=delimiter)
    except UnicodeDecodeError as exc:
        _raise(
            ValidationError(
                f"{prefix}{name} is not UTF-8 text: {exc.reason}",
                raw=exc.object[:BODY_LIMIT],
                source=source,
            )
        )
    except csv.Error as exc:
        _raise(
            ValidationError(
                f"{prefix}{name} is not CSV the csv module reads: {exc}", raw="", source=source
            )
        )


class _ClassifyOnce:
    """``classify`` called at most once per response.

    The retry loop asks it before a retry and ``request`` asks it for the final
    response, which may be the one the loop asked about last.
    """

    def __init__(self, classify: Callable[[httpx.Response], XippiosError | None]) -> None:
        self._classify = classify
        self._last: tuple[httpx.Response, XippiosError | None] | None = None

    def __call__(self, response: httpx.Response) -> XippiosError | None:
        if self._last is not None and self._last[0] is response:
            return self._last[1]
        classified = self._classify(response)
        self._last = (response, classified)
        return classified


def _from_cache(cached: CachedResponse, request: httpx.Request) -> httpx.Response:
    """The cached entry as a response, marked ``xippios_cache: hit`` with its ``stored_at``.

    ``xippios_cache_stored_at`` is the entry's ``stored_at`` in epoch seconds: on a hit,
    ``get_answer`` reads ``retrieved_at`` from it, not from the clock (conventions §4).
    """
    # Stripped again: a persistent backend may hold entries stored with wire headers (0.1.0).
    response = httpx.Response(
        cached.status,
        headers=strip_wire_headers(cached.headers),
        content=cached.content,
        request=request,
    )
    response.extensions["xippios_cache"] = "hit"
    response.extensions["xippios_cache_stored_at"] = cached.stored_at
    return response
