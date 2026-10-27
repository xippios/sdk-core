"""HTTP client for upstream APIs (conventions §6): httpx, async core.

The sync facade is ``xippios.core.sync``, applied to a task function (ADR-0002).
"""

from xippios.core.client._core import AsyncClient, Params, decode_json
from xippios.core.client.auth import (
    BasicKeyAuth,
    BearerAuth,
    EnvKeyAuth,
    HeaderKeyAuth,
    QueryKeyAuth,
)
from xippios.core.client.cache import (
    WIRE_HEADERS,
    CacheBackend,
    CachedResponse,
    MemoryCache,
    cache_key,
    strip_wire_headers,
)
from xippios.core.client.config import ClientConfig, RateLimit, RetryPolicy, Timeouts
from xippios.core.client.quota import QuotaPolicy, QuotaSnapshot
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.client.retry import send_with_retries

__all__ = [
    "WIRE_HEADERS",
    "AsyncClient",
    "BasicKeyAuth",
    "BearerAuth",
    "CacheBackend",
    "CachedResponse",
    "ClientConfig",
    "EnvKeyAuth",
    "HeaderKeyAuth",
    "MemoryCache",
    "Params",
    "QueryKeyAuth",
    "QuotaPolicy",
    "QuotaSnapshot",
    "RateLimit",
    "RetryPolicy",
    "Timeouts",
    "TokenBucket",
    "cache_key",
    "decode_json",
    "send_with_retries",
    "strip_wire_headers",
]
