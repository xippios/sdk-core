"""xippios-core: the shared foundation of the xippios Python SDK family.

The names re-exported here are the public API: what consumers import (ADR-0023,
decision 5). A helper core calls itself and no consumer imports, ``load_csv`` or
``EnvKeyAuth`` say, stays importable from its own module only. The optional adapters
live in their own subpackages and are imported explicitly: ``xippios.core.mcp``,
``xippios.core.http``, ``xippios.core.testing``.
"""

from xippios.core._loop import sync
from xippios.core._version import __version__
from xippios.core.client import (
    Answer,
    AsyncClient,
    BasicKeyAuth,
    BearerAuth,
    ClientConfig,
    Downloaded,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    QuotaPolicy,
    RateLimit,
    RetryPolicy,
    Timeouts,
)
from xippios.core.errors import (
    BODY_LIMIT,
    AuthError,
    ConfigError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UnknownCode,
    UpstreamError,
    ValidationError,
    XippiosError,
    error_from_response,
    parse_retry_after,
)
from xippios.core.models import (
    Result,
    ResultCap,
    ResultMeta,
    UpstreamModel,
    parse,
    parse_decimal,
)
from xippios.core.pagination import collect, paginate_offset
from xippios.core.reference import PackagedList, closest, load_json, load_table, matches

__all__ = [
    "BODY_LIMIT",
    "Answer",
    "AsyncClient",
    "AuthError",
    "BasicKeyAuth",
    "BearerAuth",
    "ClientConfig",
    "ConfigError",
    "Downloaded",
    "HeaderKeyAuth",
    "InvalidRequestError",
    "MemoryCache",
    "NotFoundError",
    "PackagedList",
    "QueryKeyAuth",
    "QuotaPolicy",
    "RateLimit",
    "RateLimitError",
    "Result",
    "ResultCap",
    "ResultMeta",
    "RetryPolicy",
    "Timeouts",
    "TransportError",
    "UnknownCode",
    "UpstreamError",
    "UpstreamModel",
    "ValidationError",
    "XippiosError",
    "__version__",
    "closest",
    "collect",
    "error_from_response",
    "load_json",
    "load_table",
    "matches",
    "paginate_offset",
    "parse",
    "parse_decimal",
    "parse_retry_after",
    "sync",
]
