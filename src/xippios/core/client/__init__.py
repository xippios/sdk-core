"""HTTP client for upstream APIs (conventions §6): httpx, async core, sync facade."""

from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self

import httpx

from xippios.core._loop import run
from xippios.core.client._core import AsyncClient, Params
from xippios.core.client.cache import CacheBackend, CachedResponse, MemoryCache, cache_key
from xippios.core.client.config import ClientConfig, RateLimit, RetryPolicy, Timeouts
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries

__all__ = [
    "AsyncClient",
    "CacheBackend",
    "CachedResponse",
    "Client",
    "ClientConfig",
    "MemoryCache",
    "Params",
    "RateLimit",
    "RetryPolicy",
    "Timeouts",
    "TokenBucket",
    "cache_key",
    "send_with_retries",
]


class Client:
    """Synchronous facade over ``AsyncClient`` (ADR-0002).

    Every call runs on the family's background event loop, so it works from scripts,
    notebooks and inside other event loops. ``async_client`` exposes the underlying
    instance for code that wants to await natively.

    Args:
        config: Base URL, timeouts, retry policy, rate limit, cache and headers.
        auth: An ``httpx.Auth`` adding credentials.
        transport: Replacement transport, for tests.
    """

    def __init__(
        self,
        config: ClientConfig,
        *,
        auth: httpx.Auth | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.async_client = AsyncClient(config, auth=auth, transport=transport)

    @property
    def config(self) -> ClientConfig:
        """The configuration in use."""
        return self.async_client.config

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Params = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        raise_on_error: bool = True,
    ) -> httpx.Response:
        """See ``AsyncClient.request``."""
        return run(
            self.async_client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
                raise_on_error=raise_on_error,
            )
        )

    def get(
        self, path: str, *, params: Params = None, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        """See ``AsyncClient.get``."""
        return run(self.async_client.get(path, params=params, headers=headers))

    def get_json(
        self, path: str, *, params: Params = None, headers: Mapping[str, str] | None = None
    ) -> Any:
        """See ``AsyncClient.get_json``."""
        return run(self.async_client.get_json(path, params=params, headers=headers))

    def close(self) -> None:
        """Close the background loop's connection pool."""
        run(self.async_client.aclose())

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
