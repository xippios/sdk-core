"""HTTP client for upstream APIs (conventions §6): httpx, async core.

The sync facade is ``xippios.core.sync``, applied to a task function (ADR-0002). This
package exports what consumers import; the helpers the client calls itself
(``EnvKeyAuth``, ``CacheBackend``, ``QuotaSnapshot``, ``TokenBucket``,
``send_with_retries``, ``strip_wire_headers``, ``decode_json``, ...) are importable from
their modules, ``xippios.core.client.auth``, ``.cache``, ``.quota``, ``.ratelimit``,
``.retry``, ``._core`` (ADR-0059, decision 3).
"""

from xippios.core.client._core import Answer, AsyncClient, decode_csv
from xippios.core.client.auth import BearerToken, KeyAuth, RenewingBearerAuth
from xippios.core.client.cache import CachedResponse, MemoryCache, cache_key
from xippios.core.client.config import ClientConfig, RateLimit, RetryPolicy
from xippios.core.client.download import Downloaded
from xippios.core.client.quota import QuotaPolicy

__all__ = [
    "Answer",
    "AsyncClient",
    "BearerToken",
    "CachedResponse",
    "ClientConfig",
    "Downloaded",
    "KeyAuth",
    "MemoryCache",
    "QuotaPolicy",
    "RateLimit",
    "RenewingBearerAuth",
    "RetryPolicy",
    "cache_key",
    "decode_csv",
]
