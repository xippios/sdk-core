"""The async client: one request path with retries, rate limiting, caching and errors."""

import asyncio
import dataclasses
import inspect
import threading
import time
import weakref
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Any, Self

import httpx

from xippios.core.client.cache import CachedResponse, cache_key, strip_wire_headers
from xippios.core.client.config import ClientConfig, RetryPolicy, Timeouts
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries
from xippios.core.errors import BODY_LIMIT, ValidationError, raise_for_status

__all__ = ["AsyncClient", "Params"]

Params = Mapping[str, Any] | None


class AsyncClient:
    """Async HTTP client for one upstream (conventions §6).

    One instance can be shared by sync facades and async servers alike: it keeps one
    ``httpx`` connection pool per event loop, while the rate limiter and the cache are
    shared across all of them. Clients that must share one pace, say a keyed and a
    keyless client of the same upstream, share one ``TokenBucket`` through ``limiter``.

    Args:
        config: Base URL, timeouts, retry policy, rate limit, cache and headers.
        auth: An ``httpx.Auth`` adding credentials, e.g. a query key or basic auth.
        transport: Replacement transport, for tests.
        sleep: Async sleep used by retries and the rate limiter, replaceable in tests.
        limiter: A ``TokenBucket`` to use instead of one built from
            ``config.rate_limit``, which is then ignored; pass another client's
            ``limiter`` to share its pace.
    """

    def __init__(
        self,
        config: ClientConfig,
        *,
        auth: httpx.Auth | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        limiter: TokenBucket | None = None,
    ) -> None:
        self.config = config
        self._auth = auth
        self._transport = transport
        # Set by derive: the transport belongs to the parent, and aclose leaves it open.
        self._transport_borrowed = False
        self._sleep = sleep
        if limiter is None and config.rate_limit is not None:
            limiter = TokenBucket(config.rate_limit)
        self._bucket = limiter
        self._pools: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient] = (
            weakref.WeakKeyDictionary()
        )
        self._lock = threading.Lock()

    @property
    def source(self) -> str:
        """Source slug from the configuration."""
        return self.config.source

    @property
    def limiter(self) -> TokenBucket | None:
        """The rate limiter every request waits on; ``None`` when there is none."""
        return self._bucket

    def derive(
        self, *, retry: RetryPolicy | None = None, timeouts: Timeouts | None = None
    ) -> "AsyncClient":
        """A new client like this one with another retry policy or other timeouts.

        The new client runs on ``dataclasses.replace(self.config, ...)`` with only the
        given values changed, and shares this client's auth, sleep and rate limiter,
        and through the configuration its cache: a request through either waits on the
        same pace and finds the same cache entries. It shares this client's transport,
        when one was passed, without closing it: the transport stays this client's to
        close. It keeps connection pools of its own (they carry the timeouts); close
        them with ``aclose`` or ``async with``. It is a plain ``AsyncClient``: a
        subclass's own behaviour is not carried over.

        Args:
            retry: The retry policy for the new client, e.g.
                ``RetryPolicy(max_attempts=1)``; ``None`` keeps this client's.
            timeouts: The timeouts for the new client, e.g. ``Timeouts(read=300.0)``;
                ``None`` keeps this client's.
        """
        changes: dict[str, Any] = {}
        if retry is not None:
            changes["retry"] = retry
        if timeouts is not None:
            changes["timeouts"] = timeouts
        derived = AsyncClient(
            dataclasses.replace(self.config, **changes),
            auth=self._auth,
            transport=self._transport,
            sleep=self._sleep,
            limiter=self._bucket,
        )
        derived._transport_borrowed = True
        return derived

    def _pool(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        with self._lock:
            pool = self._pools.get(loop)
            if pool is None:
                transport = self._transport
                if transport is not None and self._transport_borrowed:
                    transport = _BorrowedTransport(transport)
                pool = httpx.AsyncClient(
                    base_url=self.config.base_url,
                    headers={"User-Agent": self.config.user_agent, **self.config.headers},
                    timeout=self.config.timeouts.to_httpx(),
                    auth=self._auth,
                    transport=transport,
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
    ) -> httpx.Response:
        """Send one request and return the response.

        Retries, rate limiting and caching (GET only, narrowed by
        ``ClientConfig.cache_filter``) apply as configured. A cache hit returns at once;
        otherwise ``ClientConfig.before_request`` runs once, before the rate limiter, and
        ``ClientConfig.observe`` sees every response from the wire, retried attempts
        included. The source's ``classify`` hook, if any, sees the response first;
        otherwise a 4xx/5xx that survives the retry policy is raised as the matching
        error from the taxonomy; a transport failure as ``TransportError``.

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
                callers that record fixtures or inspect error bodies.

        Raises:
            ValueError: Both ``json`` and ``data`` were given; a request has one body.
        """
        if json is not None and data is not None:
            raise ValueError("pass json= or data=, not both: a request has one body")
        pool = self._pool()
        method = method.upper()
        probe = pool.build_request(method, path, params=params)
        key = self._cache_key_for(probe)
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
            response = await pool.send(request)
            if observe is not None:
                observe(response)
            return response

        response = await send_with_retries(
            send, policy=self.config.retry, method=method, source=self.source, sleep=self._sleep
        )
        if raise_on_error:
            if self.config.classify is not None:
                classified = self.config.classify(response)
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
        self, path: str, *, params: Params = None, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        """``request("GET", ...)``."""
        return await self.request("GET", path, params=params, headers=headers)

    async def get_json(
        self, path: str, *, params: Params = None, headers: Mapping[str, str] | None = None
    ) -> Any:
        """GET and decode a JSON body, raising ``ValidationError`` when it is not JSON."""
        response = await self.get(path, params=params, headers=headers)
        try:
            return response.json()
        except ValueError as exc:
            raise ValidationError(
                f"{self.source}: response from {path} is not JSON",
                raw=response.text[:BODY_LIMIT],
                source=self.source,
            ) from exc

    async def aclose(self) -> None:
        """Close the connection pool bound to the current event loop.

        A transport passed to this client is closed with it, as httpx does; one borrowed
        from the parent through ``derive`` is left open for the parent to close.
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


class _BorrowedTransport(httpx.AsyncBaseTransport):
    """Another client's transport: requests go through it, closing leaves it open."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Send ``request`` through the owner's transport."""
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        """Do nothing: the owner closes its transport with its own ``aclose``."""


def _from_cache(cached: CachedResponse, request: httpx.Request) -> httpx.Response:
    # Stripped again: a persistent backend may hold entries stored with wire headers (0.1.0).
    response = httpx.Response(
        cached.status,
        headers=strip_wire_headers(cached.headers),
        content=cached.content,
        request=request,
    )
    response.extensions["xippios_cache"] = "hit"
    return response
