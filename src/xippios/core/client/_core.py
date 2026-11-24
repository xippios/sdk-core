"""The async client: one request path with retries, rate limiting, caching and errors."""

import asyncio
import codecs
import contextlib
import contextvars
import csv
import inspect
import io
import json
import os
import tempfile
import threading
import time
import weakref
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import IO, Any, Final, cast, final, overload

import httpx

from xippios.core.client.cache import CachedResponse, cache_key, strip_wire_headers
from xippios.core.client.config import ClientConfig, RetryPolicy
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
    InvalidRequestError,
    UpstreamError,
    ValidationError,
    XippiosError,
    _failed_in_transit,
    _raise,
    raise_for_status,
    request_description,
)
from xippios.core.models import parse as parse_payload

__all__ = ["Answer", "AsyncClient", "Params", "decode_csv", "decode_json"]

Params = Mapping[str, Any] | None

_TIMEOUT: Final = 10.0
"""Seconds to connect, to send a request and to wait for a pooled connection (conventions §6)."""


@final
class _ClientAuth:
    """The type of the default of ``auth=``: the client's own credentials (ADR-0037).

    Core's own sentinel, so no annotation needs httpx's private ``UseClientDefault``;
    ``request`` maps it to ``httpx.USE_CLIENT_DEFAULT`` where the request is sent.
    """

    def __repr__(self) -> str:
        return "<the client's auth>"


_CLIENT_AUTH: Final = _ClientAuth()

_HTTPX_DEFAULT: Final[object] = httpx.USE_CLIENT_DEFAULT
"""httpx's own spelling of the default, outside the annotation: treated as ``_CLIENT_AUTH``."""


@final
class _Collector:
    """The answers a recorded task's clients read, in the order they arrived (ADR-0057).

    ``answers`` holds each answer read whole; ``download`` the number of the exchange and the
    request, ``GET <path>``, of the first download refused while collecting; ``closed`` is set
    once the recording ended, so a task that outlives it hands nothing over.
    """

    __slots__ = ("answers", "closed", "download")

    def __init__(self) -> None:
        self.answers: list[httpx.Response] = []
        self.download: tuple[int, str] | None = None
        self.closed = False


_COLLECTOR: Final[contextvars.ContextVar[_Collector | None]] = contextvars.ContextVar(
    "xippios_core_collector", default=None
)
"""The collector of the running context: a recording's, ``None`` outside one."""

_ONE_ATTEMPT: Final = RetryPolicy(max_attempts=1)
"""The policy of every request while a task is recorded: one attempt, never retried."""


def _collector() -> _Collector | None:
    """The open collector of the running context, or ``None`` outside a recording."""
    collector = _COLLECTOR.get()
    return None if collector is None or collector.closed else collector


@contextlib.contextmanager
def _collecting() -> Iterator[_Collector]:
    """Collect what every ``AsyncClient`` of the running context reads, until the block ends.

    ``xippios.core.testing.record_task`` records a task inside it (ADR-0057). Meanwhile each
    client hands every answer it read whole to the collector, in the order the answers
    arrived, the answers of ``request``, its helpers and ``send_once`` alike; sends each
    request once, whatever its ``RetryPolicy`` says; and neither reads nor fills the response
    cache. Its ``before_request``, limiter and ``observe`` run as for any request. A download
    is refused before it is sent, since its success streams its body to a file unread, and
    the refusal is kept in ``download``. A token request inside an auth flow, and an answer
    an auth flow handles before it sends the request again, never reach the collector: httpx
    answers them inside the flow.

    The collector is held in a context variable, so it reaches the code that runs in the
    block's context and the tasks started from it, which inherit it, and nothing else: a
    request of another task is never collected, and two recordings at once never mix. On
    leaving the block, whatever it raised, the collector is closed and the context's is
    restored, so the client sends, retries and caches as before, a task that outlives the
    block included.

    Raises:
        RuntimeError: The block would open inside another one's context; nothing is
            collected.
    """
    if _collector() is not None:
        raise RuntimeError(
            "a task is recorded inside another recording, whose collector would miss its "
            "exchanges: record one task at a time"
        )
    collector = _Collector()
    token = _COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        collector.closed = True
        _COLLECTOR.reset(token)


def _origin(url: httpx.URL) -> tuple[str, str, int | None]:
    """Scheme, host and port: httpx writes the first two in lower case, a default port ``None``."""
    return url.scheme, url.host, url.port


@final
@dataclass(frozen=True, slots=True)
class _Reach:
    """Where one call's credentials go: what its requests carry, and their marks.

    ``auth`` is what the call asked for, ``"client"`` (the default), ``"none"``
    (``auth=None``) or ``"own"`` (an ``httpx.Auth`` of its own); ``sent`` what httpx is
    given for a request to ``url``: the client's auth reaches the base URL's origin only
    (https://github.com/xippios/sdk-core/issues/163).
    """

    auth: str
    sent: Any
    base: tuple[str, str, int | None]

    def for_url(self, url: httpx.URL) -> tuple[Any, str]:
        """The auth httpx sends with a request to ``url``, and its origin mark."""
        if _origin(url) == self.base:
            return self.sent, "base"
        return (None if self.auth == "client" else self.sent), "other"

    def mark(self, request: httpx.Request) -> Any:
        """Mark ``request`` for the hooks, and return the auth httpx sends with it."""
        sent, origin = self.for_url(request.url)
        request.extensions["xippios_auth"] = self.auth
        request.extensions["xippios_origin"] = origin
        return sent


@final
@dataclass(frozen=True, slots=True)
class _Slot:
    """Where the cache may keep one answer: its key, and the path the cache reads."""

    key: str
    path: str


class AsyncClient:
    """Async HTTP client for one upstream (conventions §6).

    One instance can be shared by sync facades and async servers alike: it keeps one
    ``httpx`` connection pool per event loop, while the rate limiter, built from
    ``config.rate_limit``, and the cache are shared across all of them. A call to a
    keyless endpoint on the same host passes ``auth=None`` to this client rather than
    going through a second one (ADR-0037). The client's ``auth`` goes to the base URL's
    origin only, its scheme, host and port: a request to any other origin, a file link on
    another host say, is sent without it unless the call passes an ``httpx.Auth`` of its
    own.

    Every request it builds tells the hooks where its credentials go, in two extensions:
    ``xippios_auth`` is ``"client"`` for the default, ``"none"`` for ``auth=None`` and
    ``"own"`` for an ``httpx.Auth`` of the call's own; ``xippios_origin`` is ``"base"`` for
    the base URL's origin and ``"other"`` for any other. ``QuotaPolicy`` skips a request
    marked ``"none"`` or ``"other"``, and the api.data.gov gateway's ``classify`` reads no
    answer marked ``"other"``.

    While ``xippios.core.testing.record_task`` records a task, every client the task's
    context reaches hands each answer it read whole to the recording, in the order the
    answers arrived, sends each request once whatever ``config.retry`` says, neither reads
    nor fills the cache, and refuses a download before it is sent (ADR-0057). Outside a
    recording nothing of this applies.

    Args:
        config: Base URL, read timeout, retry policy, rate limit, cache and headers.
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
        self._base = _origin(httpx.URL(config.base_url))
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
                    timeout=httpx.Timeout(_TIMEOUT, read=self.config.read_timeout),
                    auth=self._auth,
                    transport=self._transport,
                )
                self._pools[loop] = pool
            return pool

    def _reach(self, auth: "httpx.Auth | _ClientAuth | None") -> _Reach:
        """Where a call with ``auth`` sends credentials (``_Reach``)."""
        if isinstance(auth, _ClientAuth) or auth is _HTTPX_DEFAULT:
            return _Reach("client", httpx.USE_CLIENT_DEFAULT, self._base)
        if auth is None:
            return _Reach("none", None, self._base)
        return _Reach("own", auth, self._base)

    def _cache_slot(self, probe: httpx.Request) -> _Slot | None:
        """Where the cache may keep the answer to ``probe``: a GET's key and path.

        ``None`` for any other method or a client without a cache. Whether the path is
        kept, and for how long, is the cache's own (``MemoryCache(lifetimes=...)``).
        """
        if probe.method != "GET" or self.config.cache is None:
            return None
        return _Slot(cache_key(probe.method, probe.url), probe.url.path)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> httpx.Response:
        """Send one request and return the response.

        Retries, rate limiting and the cache lookup (GET only) apply as configured. A
        cache hit returns at once;
        otherwise ``ClientConfig.before_request`` runs once, before the rate limiter, and
        ``ClientConfig.observe`` sees every response from the wire, retried attempts
        included. The source's ``classify`` hook, if any, is asked before a 429 or 5xx
        is retried (its ``RateLimitError`` sets the wait, an error other than an
        ``UpstreamError`` for a 5xx stops the retries, ADR-0037) and sees the final
        response first; otherwise a 4xx/5xx that survives the retry policy is raised as
        the matching error from the taxonomy; a transport failure as ``TransportError``.
        A write, any method but ``GET``, ``HEAD`` and ``OPTIONS``, is sent once, and the
        error of one that met a 5xx or failed in transit says what became of it (ADR-0011,
        amendment 2026-11-24).
        Nothing is stored in the cache here: ``get_answer`` stores an answer once it has
        decoded it, so a body that fails to decode is requested again (conventions §6).

        Args:
            method: HTTP method.
            path: Path joined onto the base URL, e.g. ``"/api/api_GET"``.
            params: Query parameters.
            json: JSON body for write methods, e.g. ``{"name": "Corn"}``.
            data: Form body for write methods, sent form-encoded
                (``application/x-www-form-urlencoded``), e.g. ``{"id": 4, "name": "Corn"}``.
                For upstreams whose writes take form fields, not JSON.
            headers: Extra headers for this request only.
            auth: Credentials for this request only, every retry included: left at its
                default it sends the client's ``auth`` to the base URL's origin and none
                to another, ``None`` sends none, for a keyless endpoint on the same host,
                and an ``httpx.Auth`` replaces the client's, to any origin. The default
                and ``None`` share the cache; a call with an ``httpx.Auth`` of its own
                bypasses it, neither looked up nor stored, since another identity may get
                another answer.

        Raises:
            ValueError: Both ``json`` and ``data`` were given; a request has one body.
        """
        response, _ = await self._request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            headers=headers,
            auth=auth,
        )
        return response

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> tuple[httpx.Response, "_Slot | None"]:
        """``request``'s work, and where ``get_answer`` stores the answer.

        The slot is ``None`` for an answer from the cache, which is stored already, and
        for a request that the cache or an ``auth`` of the call's own leaves out.
        """
        if json is not None and data is not None:
            raise ValueError("pass json= or data=, not both: a request has one body")
        pool = self._pool()
        method = method.upper()
        probe = pool.build_request(method, path, params=params)
        # A call with credentials of its own may get another answer: no cache for it. Any
        # explicit auth counts, also a form httpx accepts beyond the annotation (a tuple).
        # A recorded task's request neither reads nor fills it (ADR-0057).
        reach = self._reach(auth)
        collector = _collector()
        uncached = reach.auth == "own" or collector is not None
        slot = None if uncached else self._cache_slot(probe)
        if slot is not None and self.config.cache is not None:
            cached = self.config.cache.get(slot.key)
            if cached is not None:
                return _from_cache(cached, probe), None
        before_request = self.config.before_request
        if before_request is not None:
            # Built as each attempt is, before auth applies; a change to it is not sent.
            built = pool.build_request(
                method, path, params=params, json=json, data=data, headers=headers
            )
            reach.mark(built)
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
            response = await pool.send(request, auth=reach.mark(request))
            if observe is not None:
                observe(response)
            if collector is not None:
                collector.answers.append(response)
            return response

        classify = None if self.config.classify is None else _ClassifyOnce(self.config.classify)
        response = await send_with_retries(
            send,
            policy=self.config.retry if collector is None else _ONE_ATTEMPT,
            method=method,
            source=self.source,
            sleep=self._sleep,
            classify=classify,
        )
        if classify is not None:
            classified = classify(response)
            if classified is not None:
                raise classified
        raise_for_status(response, source=self.source)
        return response, slot

    def _store(self, slot: "_Slot", response: httpx.Response, stored_at: float) -> None:
        """Keep a 200 within ``cache_max_bytes`` in ``slot``, stored at ``stored_at``."""
        cache = self.config.cache
        if (
            cache is None
            or response.status_code != 200
            or len(response.content) > self.config.cache_max_bytes
        ):
            return
        # The content is already decoded: keeping content-encoding would make the replay
        # decode it a second time (httpx.DecodingError on a gzip answer).
        cache.set(
            slot.key,
            CachedResponse(
                status=response.status_code,
                headers=tuple(strip_wire_headers(response.headers.multi_items())),
                content=response.content,
                stored_at=stored_at,
            ),
            path=slot.path,
        )

    async def _send_once(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
        max_read_bytes: int | None = None,
    ) -> httpx.Response:
        """The recorder's request: sent once, its answer returned whatever its status.

        ``xippios.core.testing.send_once`` sends through it, and ``record`` through that,
        which refuses an answer of a 1xx or a 3xx status (ADR-0048, decision 4), so a
        recording is one live exchange (ADR-0037, decision 6): never retried, whatever
        ``config.retry`` says, and never answered from the cache nor stored in it.
        ``before_request`` runs once and the limiter paces the request, as for
        ``request``, and ``observe`` sees the answer; ``classify`` is not asked, since
        nothing is retried or raised. The client's auth reaches the base URL's origin
        only, and the request carries the marks ``xippios_auth`` and ``xippios_origin``,
        as every request the client builds does (ADR-0037, decision 4). The body is read up
        to ``max_read_bytes`` as decoded, and no further (ADR-0040, decision 5).

        Args:
            method: HTTP method.
            path: Path joined onto the base URL, e.g. ``"/api/api_GET"``.
            params: Query parameters.
            json: JSON body.
            data: Form body.
            headers: Extra headers for this request only.
            auth: As for ``request``.
            max_read_bytes: The most bytes of the body to read; ``None`` reads it whole.

        Returns:
            The answer with its body read, without the wire-encoding headers, since the
            body is decoded, and with the request as sent, credentials included.

        Raises:
            ValueError: Both ``json`` and ``data``, before anything is sent; or the body
                passes ``max_read_bytes``, once that much is read: ``observe`` has seen
                the answer's status and headers, its body unread.
            TransportError: The request or its body failed in transit; a write's says that
                the request was sent once and that its outcome is unknown, or that nothing
                was sent where the connection failed.
        """
        if json is not None and data is not None:
            raise ValueError("pass json= or data=, not both: a request has one body")
        pool = self._pool()
        method = method.upper()
        reach = self._reach(auth)
        before_request = self.config.before_request
        if before_request is not None:
            built = pool.build_request(
                method, path, params=params, json=json, data=data, headers=headers
            )
            reach.mark(built)
            outcome = before_request(built)
            if inspect.isawaitable(outcome):
                await outcome
        if self._bucket is not None:
            await self._bucket.acquire(self._sleep)
        request = pool.build_request(
            method, path, params=params, json=json, data=data, headers=headers
        )
        try:
            streamed = await pool.send(request, auth=reach.mark(request), stream=True)
            try:
                body = await _read_within(streamed, max_read_bytes)
            finally:
                await streamed.aclose()
        except httpx.RequestError as exc:
            raise _failed_in_transit(exc, method=method, source=self.source) from exc
        observe = self.config.observe
        if body is None:
            if observe is not None:
                with contextlib.suppress(httpx.ResponseNotRead):
                    observe(streamed)
            raise ValueError(
                f"{request_description(streamed)} answered a body over {max_read_bytes} "
                "bytes, the recording's max_read_bytes; reading stopped there and nothing is "
                "written: narrow the request, or raise max_read_bytes and cut the body with "
                "max_bytes"
            )
        response = httpx.Response(
            streamed.status_code,
            headers=strip_wire_headers(streamed.headers.multi_items()),
            content=body,
            request=streamed.request,
        )
        if observe is not None:
            observe(response)
        collector = _collector()
        if collector is not None:
            collector.answers.append(response)
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

    async def post_json(
        self,
        path: str,
        *,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> Any:
        """POST and decode a JSON answer, ``None`` for an answer with no body.

        ``request("POST", ...)``, so ``classify``, the hooks and the limiter apply as they
        do there, the request is sent once, after a 429 or a 5xx too, its error saying what
        became of it (ADR-0011), and the cache is neither read nor written. An answer with
        no body at all, a 204 say, returns ``None``; any other body is decoded as
        ``get_answer``
        decodes it.

        Args:
            path: Path joined onto the base URL, e.g. ``"/drafts"``.
            json: JSON body, e.g. ``{"message": {"raw": raw}}``.
            data: Form body, sent form-encoded, e.g. ``{"title": "Corn"}``, for an
                upstream whose writes take form fields; never with ``json``.
            params: Query parameters.
            headers: Extra headers for this request only.
            auth: As for ``request``: the client's credentials by default, ``None`` for
                none, an ``httpx.Auth`` to replace them.

        Raises:
            ValueError: Both ``json`` and ``data`` were given; nothing is sent.
            ValidationError: The answer has a body that is not JSON, naming ``path``.
        """
        response = await self.request(
            "POST", path, params=params, json=json, data=data, headers=headers, auth=auth
        )
        return _json_or_none(response, source=self.source, path=path)

    @overload
    async def get_answer(
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> "Answer[Any]": ...

    @overload
    async def get_answer[T](
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
        parse: type[T],
        endpoint: str,
    ) -> "Answer[T]": ...

    async def get_answer(
        self,
        path: str,
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
        parse: type[Any] | None = None,
        endpoint: str | None = None,
    ) -> "Answer[Any]":
        """GET and decode a JSON body with the time it was retrieved (conventions §4).

        The client's one reader of JSON (conventions §6): ``get``'s call, the body decoded
        and refused with ``ValidationError`` where it is not JSON, the parse into
        ``parse`` when it is given, and the ``retrieved_at`` a task puts into its
        ``ResultMeta``, the client's fact for every answer: on a cache hit the time
        the entry was stored, read from ``xippios_cache_stored_at`` (ADR-0037, decision
        5), else the time the answer arrived, read before the decode and the parse. A 200
        from the wire is stored in the cache, where the cache takes it, only once its
        body decoded and its payload parsed, at the time its ``retrieved_at`` carries:
        one reading of the clock for both, and a body that fails is requested again on
        the next call (ADR-0037, decision 5). ``auth`` as for ``request``.

        Args:
            path: Path joined onto the base URL, e.g. ``"/v1/regions"``.
            params: Query parameters.
            headers: Extra headers for this request only.
            auth: The client's credentials by default, ``None`` for none, an
                ``httpx.Auth`` to replace them.
            parse: The type the payload is parsed into with ``parse``, a model or a
                generic such as ``list[Region]``; ``None`` leaves it as decoded.
            endpoint: The upstream operation that ``parse``'s error names, e.g.
                ``"regions"``; given with ``parse`` and only then.

        Returns:
            The ``Answer``: the payload, ``Answer[T]`` for ``parse=T``, and
            ``retrieved_at``, timezone-aware UTC.

        Raises:
            TypeError: ``parse`` was given without ``endpoint``; nothing is sent.
            ValidationError: The body is not JSON, or its payload is not a ``parse``.
        """
        if parse is not None and endpoint is None:
            raise TypeError("get_answer() takes endpoint= with parse=, for the parse's error")
        response, slot = await self._request("GET", path, params=params, headers=headers, auth=auth)
        stored_at = response.extensions.get("xippios_cache_stored_at")
        if stored_at is None:
            # When the answer arrived: a slow decode or parse must not move it later.
            stored_at = time.time()
        payload = decode_json(response, source=self.source, path=path)
        if parse is not None and endpoint is not None:
            payload = parse_payload(parse, payload, source=self.source, endpoint=endpoint)
        if slot is not None:  # from the wire, and the cache takes it
            self._store(slot, response, stored_at)
        return Answer(payload, datetime.fromtimestamp(stored_at, UTC))

    async def download(
        self,
        url: str,
        dest: str | os.PathLike[str],
        *,
        params: Params = None,
        headers: Mapping[str, str] | None = None,
        auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    ) -> Downloaded:
        """Stream a file to ``dest`` with a GET, never holding its body in memory (ADR-0040).

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

        The file is written with mode ``0600``, readable and writable by its owner alone,
        as ``tempfile.mkstemp`` creates the temporary file, whose mode the rename keeps:
        not the ``0644`` a new file gets under the usual umask of ``022``, nor the mode of
        a file it replaces. A caller that shares the file sets its mode itself.

        Args:
            url: An absolute URL, e.g. a file link from a catalog, or a path joined onto
                the base URL, e.g. ``"/files/qs.crops_20261027.txt.gz"``.
            dest: The file to write, e.g. ``tmp_path / "qs.crops.txt.gz"``, in a directory
                that exists.
            params: Query parameters, as for ``get``, e.g. ``{"year": "2025"}``.
            headers: Extra headers for this request only, as for ``get``.
            auth: Credentials for this download, every retry included, as for
                ``request``: the client's by default, to the base URL's origin only, so a
                file link on another host goes without them; ``None`` for none; an
                ``httpx.Auth`` to replace them, sent to whatever origin ``url`` names.

        Returns:
            The ``Downloaded`` file: path, size, content type, file name, ``ETag``,
            ``Last-Modified`` and when it was complete.

        While a task is recorded (``xippios.core.testing.record_task``), a download is
        refused before anything is sent: its success's body goes to the file unread, and no
        fixture of the task could keep it (ADR-0057).

        Raises:
            InvalidRequestError: ``dest`` is a directory, or its directory does not
                exist, a bad argument (conventions §5); nothing is sent, the hooks
                included.
            ValueError: A task is being recorded; nothing is sent, the message naming the
                method and the path.
            XippiosError: The taxonomy error for the answer (``classify`` first, then the
                status), ``UpstreamError`` for a 1xx or 3xx, ``TransportError`` for a
                transport failure that is not retried; ``dest`` is untouched.
        """
        collector = _collector()
        if collector is not None:
            described = f"GET {self._pool().build_request('GET', url).url.path}"
            if collector.download is None:
                collector.download = (len(collector.answers) + 1, described)
            raise ValueError(
                f"{described}: a download is refused while a task is recorded, before it is "
                "sent: its body goes to a file unread, which no fixture of the task keeps "
                "(ADR-0057)"
            )
        target = Path(dest)
        if target.is_dir():
            raise InvalidRequestError(
                "dest is a directory; name the file to write", source=self.source
            )
        if not target.parent.is_dir():
            raise InvalidRequestError(
                "dest's directory does not exist; create it first", source=self.source
            )
        pool = self._pool()
        reach = self._reach(auth)
        handle, name = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.", suffix=".part"
        )
        os.close(handle)
        partial = Path(name)
        try:
            before_request = self.config.before_request
            if before_request is not None:
                built = pool.build_request("GET", url, params=params, headers=headers)
                reach.mark(built)
                outcome = before_request(built)
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
                request = pool.build_request("GET", url, params=params, headers=headers)
                streamed = await pool.send(request, auth=reach.mark(request), stream=True)
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
                    f"{response.status_code} from {request_description(response)}: a download "
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


@dataclass(frozen=True, slots=True)
class Answer[T]:
    """An answer's payload and when it was retrieved: what ``get_answer`` returns.

    Generic over the payload: ``get_answer(path)`` gives an ``Answer[Any]``,
    ``get_answer(path, parse=list[Region], endpoint="regions")`` an
    ``Answer[list[Region]]``. A wrapper that returns a value it derives from the payload
    keeps the time with it as ``Answer(value, answer.retrieved_at)``, an ``Answer`` of
    the value's type, and needs no pair of its own.

    Attributes:
        payload: The body as ``decode_json`` decodes it, e.g. ``{"data": [...]}``, or as
            ``parse`` reads it, e.g. ``[Region(...), ...]``.
        retrieved_at: Timezone-aware UTC: on a cache hit the time the entry was stored,
            else the time the answer arrived, which a miss stores; a task's
            ``ResultMeta.retrieved_at``.
    """

    payload: T
    retrieved_at: datetime


def decode_json(
    response: httpx.Response, *, source: str | None = None, path: str | None = None
) -> Any:
    """Decode ``response``'s JSON body, raising ``ValidationError`` when it is not JSON.

    What ``get_answer`` and ``post_json`` do after the request: a helper the client calls
    itself, outside the lists (ADR-0059, decision 3).

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
                f"{source + ': ' if source else ''}{_response_from(response, path)} is not JSON: "
                f"{_reason(exc)}",
                raw=response.text[:BODY_LIMIT],
                source=source,
            )
        )


def _json_or_none(response: httpx.Response, *, source: str, path: str) -> Any:
    """``decode_json`` for ``post_json``'s answer, ``None`` when it has no body at all.

    A 204 has none, and an upstream may answer a write with an empty 200 or 202; a body
    of whitespace is a body, and not JSON.
    """
    if not response.content:
        return None
    return decode_json(response, source=source, path=path)


def _reason(exc: ValueError) -> str:
    """What a decoder said and where, never the text it read (queue row 42)."""
    if isinstance(exc, json.JSONDecodeError):
        return f"{exc.msg} at line {exc.lineno} column {exc.colno} (char {exc.pos})"
    if isinstance(exc, UnicodeDecodeError):
        return f"{exc.reason} at byte {exc.start}"
    return type(exc).__name__


def _response_from(response: httpx.Response, path: str | None) -> str:
    """``response from <path>``, the decoders' subject, the request's path when not given.

    No request description (``request_description``): a decoder names a path its caller
    may give, for a response built without a request.
    """
    if path is None:
        try:
            path = response.request.url.path
        except RuntimeError:  # httpx raises it for a response built without a request
            path = None
    return f"response from {path}" if path else "response"


def decode_csv(
    data: Path | str | IO[str],
    *,
    source: str | None = None,
) -> Iterator[dict[str, str]]:
    """The rows of a CSV file or text stream, one mapping per row, headers as printed.

    The stdlib's ``csv.DictReader`` reads the first row as the header and each further
    row as a mapping from header to text, its fields separated by commas; nothing is
    converted, renamed or stripped (ADR-0028). A row shorter than the header maps the
    missing columns to ``None``, and a longer one keeps the extra values as a list under
    ``None``, as ``DictReader`` does. A generator: a file of hundreds of MB is read row by
    row, never whole, and a path is closed when the generator ends or is closed;
    ``list(decode_csv(path))`` reads it all.

    Args:
        data: A downloaded file, as a path, read as UTF-8 with a byte order mark
            stripped, e.g. ``downloaded.path``; or an open text stream, such as a gzip or
            ZIP member the source opens with the stdlib, e.g.
            ``io.TextIOWrapper(gzip.open(path), encoding="utf-8-sig", newline="")``. A
            stream is read from where it stands, a leading byte order mark stripped, and
            left open, for the caller that opened it to close. A binary stream is refused
            with ``TypeError`` at the first row: an ``io.RawIOBase`` or
            ``io.BufferedIOBase`` by its class, before it is read, and any other once its
            first line reads as ``bytes``.
        source: Source slug for the error, e.g. ``"example"``.

    Raises:
        ValidationError: The text is not UTF-8 (or not in the stream's encoding), or not
            CSV the stdlib can read, e.g. a field over its size limit; raised while
            iterating, at the row where it is found, ``from None``, naming the file's name
            (a stream's, ``stream`` for one without a name) and the decoder's or the csv
            module's message, never the text.
    """
    given: object = data  # typing's IO is no runtime class: the checks read the object
    if isinstance(given, io.IOBase) or hasattr(given, "read"):
        if isinstance(given, io.RawIOBase | io.BufferedIOBase):
            raise TypeError(_binary_refusal(given))
        stream = cast(IO[str], given)
        yield from _rows(stream, _stream_name(stream), source, from_stream=True)
        return
    path = Path(cast("str | os.PathLike[str]", data))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from _rows(handle, path.name, source)


def _stream_name(stream: IO[str]) -> str:
    """The name a stream's errors carry: its file's name without the directories.

    ``gzip.open(path, "rt")`` names the path, a ZIP member's ``TextIOWrapper`` the
    member; a stream without a ``str`` name, a ``StringIO`` say, is ``stream``.
    """
    name = getattr(stream, "name", None)
    if isinstance(name, str) and name:
        return PurePath(name).name or name
    return "stream"


def _binary_refusal(stream: object) -> str:
    """The ``TypeError`` text for a binary stream, which names the wrapper that reads it."""
    return (
        f"decode_csv reads text, and {type(stream).__name__} is a binary stream: wrap it in "
        "io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')"
    )


def _without_bom(handle: IO[str]) -> Iterator[str]:
    """``handle``'s lines, a byte order mark at the start of the first one stripped.

    A stream's: a path is opened as ``utf-8-sig``, so it does not pass through here. A
    stream that is binary by what it reads, not by its class, such as a
    ``tempfile.SpooledTemporaryFile`` in ``"w+b"``, gives ``bytes`` for its first line and
    is refused there.
    """
    lines = iter(handle)
    first: object = next(lines, None)
    if first is None:
        return
    if not isinstance(first, str):
        raise TypeError(_binary_refusal(handle))
    yield first.removeprefix("\ufeff")
    yield from lines


def _charset(handle: IO[str]) -> str:
    """The encoding an error names: ``UTF-8`` for UTF-8 with or without a signature."""
    encoding = getattr(handle, "encoding", None)
    if not isinstance(encoding, str):
        return "UTF-8"
    try:
        known = codecs.lookup(encoding).name
    except LookupError:
        return encoding
    return "UTF-8" if known in ("utf-8", "utf-8-sig") else encoding


def _rows(
    handle: IO[str],
    name: str,
    source: str | None,
    *,
    from_stream: bool = False,
) -> Iterator[dict[str, str]]:
    prefix = f"{source}: " if source else ""
    lines: Iterable[str] = _without_bom(handle) if from_stream else handle
    try:
        yield from csv.DictReader(lines)
    except UnicodeDecodeError as exc:
        _raise(
            ValidationError(
                f"{prefix}{name} is not {_charset(handle)} text: {exc.reason}",
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


async def _read_within(response: httpx.Response, limit: int | None) -> bytes | None:
    """``response``'s body as decoded, or ``None`` once it passes ``limit`` bytes.

    The reading stops at the chunk that passes the limit: the rest is never fetched.
    """
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if limit is not None and len(body) > limit:
            return None
    return bytes(body)


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
    ``get_answer`` reads ``retrieved_at`` from it, not from the clock (conventions §4). The
    headers are the ones ``_store`` kept, without the wire's encoding headers.
    """
    response = httpx.Response(
        cached.status,
        headers=cached.headers,
        content=cached.content,
        request=request,
    )
    response.extensions["xippios_cache"] = "hit"
    response.extensions["xippios_cache_stored_at"] = cached.stored_at
    return response
