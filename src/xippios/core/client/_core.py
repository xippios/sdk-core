"""The async client: one request path with retries, rate limiting, caching and errors."""

import asyncio
import inspect
import threading
import time
import weakref
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Any, Final, Self, final

import httpx

from xippios.core.client.cache import CachedResponse, cache_key, strip_wire_headers
from xippios.core.client.config import ClientConfig
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries
from xippios.core.errors import BODY_LIMIT, ValidationError, XippiosError, raise_for_status

__all__ = ["AsyncClient", "Params", "decode_json"]

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
        ``ClientConfig.cache_filter``) apply as configured. A cache hit returns at once;
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
        if key is not None and self.config.cache is not None and response.status_code == 200:
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

        ``auth`` as for ``request``: ``None`` sends no credentials. A wrapper that needs
        the response too, e.g. a cache hit's ``xippios_cache_stored_at``, calls ``get``
        and then ``decode_json``.
        """
        response = await self.get(path, params=params, headers=headers, auth=auth)
        return decode_json(response, source=self.source, path=path)

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


def decode_json(
    response: httpx.Response, *, source: str | None = None, path: str | None = None
) -> Any:
    """Decode ``response``'s JSON body, raising ``ValidationError`` when it is not JSON.

    What ``get_json`` does after ``get``. A wrapper that needs the response as well as
    its payload, such as a cache hit's ``response.extensions["xippios_cache_stored_at"]``
    for ``retrieved_at`` (conventions §4), calls ``get`` and then this.

    Args:
        response: A response with its body read, e.g. from ``AsyncClient.get``.
        source: Source slug for the error, e.g. ``"usda-psd"``.
        path: The request path the message names, e.g. ``"/api/psd/regions"``; ``None``
            takes the path of the response's request. Never the host or query
            (conventions §5).

    Raises:
        ValidationError: The body is not JSON; ``raw`` holds its text, truncated.
    """
    try:
        return response.json()
    except ValueError as exc:
        if path is None:
            try:
                path = response.request.url.path
            except RuntimeError:  # httpx raises it for a response built without a request
                path = None
        where = f"response from {path}" if path else "response"
        raise ValidationError(
            f"{source + ': ' if source else ''}{where} is not JSON",
            raw=response.text[:BODY_LIMIT],
            source=source,
        ) from exc


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
    a task sets ``retrieved_at`` from it, not from the clock (conventions §4).
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
