"""HTTP client for upstream APIs (conventions §6): httpx, async core.

The sync facade is ``xippios.core.sync``, applied to a task function (ADR-0002). This
package exports what consumers import; the helpers the client calls itself
(``EnvKeyAuth``, ``CacheBackend``, ``QuotaSnapshot``, ``TokenBucket``,
``send_with_retries``, ``strip_wire_headers``, ...) are importable from their modules,
``xippios.core.client.auth``, ``.cache``, ``.quota``, ``.ratelimit``, ``.retry``.
"""

from xippios.core.client._core import AsyncClient, decode_csv, decode_json, decode_text
from xippios.core.client.auth import BasicKeyAuth, BearerAuth, HeaderKeyAuth, QueryKeyAuth
from xippios.core.client.cache import CachedResponse, MemoryCache, cache_key
from xippios.core.client.config import ClientConfig, RateLimit, RetryPolicy, Timeouts
from xippios.core.client.download import Downloaded
from xippios.core.client.quota import QuotaPolicy

__all__ = [
    "AsyncClient",
    "BasicKeyAuth",
    "BearerAuth",
    "CachedResponse",
    "ClientConfig",
    "Downloaded",
    "HeaderKeyAuth",
    "MemoryCache",
    "QueryKeyAuth",
    "QuotaPolicy",
    "RateLimit",
    "RetryPolicy",
    "Timeouts",
    "cache_key",
    "decode_csv",
    "decode_json",
    "decode_text",
]
