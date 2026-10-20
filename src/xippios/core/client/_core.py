"""The async client: one request path with retries, rate limiting, caching and errors."""

import asyncio
import threading
import time
import weakref
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Any, Self

import httpx

from xippios.core.client.cache import CachedResponse, cache_key
from xippios.core.client.config import ClientConfig
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries
from xippios.core.errors import BODY_LIMIT, ValidationError, raise_for_status

__all__ = ["AsyncClient", "Params"]

Params = Mapping[str, Any] | None


class AsyncClient:
    """Async HTTP client for one upstream (conventions §6).

    One instance can be shared by sync facades and async servers alike: it keeps one
    ``httpx`` connection pool per event loop, while the rate limiter and the cache are
    shared across all of them.

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
        self._bucket = TokenBucket(config.rate_limit) if config.rate_limit is not None else None
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

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Send one request and return the successful response.

        Retries, rate limiting and caching apply as configured. A 4xx/5xx that survives
        the retry policy is raised as the matching error from the taxonomy; a transport
        failure as ``TransportError``.

        Args:
            method: HTTP method.
            path: Path joined onto the base URL, e.g. ``"/api/api_GET"``.
            params: Query parameters.
            json: JSON body for write methods.
            headers: Extra headers for this request only.
        """
        pool = self._pool()
        method = method.upper()
        probe = pool.build_request(method, path, params=params)
        key = self._cache_key(method, probe.url)
        if key is not None and self.config.cache is not None:
            cached = self.config.cache.get(key)
            if cached is not None:
                return _from_cache(cached, probe)

        async def send() -> httpx.Response:
            if self._bucket is not None:
                await self._bucket.acquire(self._sleep)
            request = pool.build_request(method, path, params=params, json=json, headers=headers)
            return await pool.send(request)

        response = await send_with_retries(
            send, policy=self.config.retry, method=method, source=self.source, sleep=self._sleep
        )
        raise_for_status(response, source=self.source)
        if key is not None and self.config.cache is not None and response.status_code == 200:
            self.config.cache.set(
                key,
                CachedResponse(
                    status=response.status_code,
                    headers=tuple(response.headers.multi_items()),
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
        """Close the connection pool bound to the current event loop."""
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


def _from_cache(cached: CachedResponse, request: httpx.Request) -> httpx.Response:
    response = httpx.Response(
        cached.status, headers=list(cached.headers), content=cached.content, request=request
    )
    response.extensions["xippios_cache"] = "hit"
    return response
