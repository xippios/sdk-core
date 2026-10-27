"""xippios-core: the shared foundation of the xippios Python SDK family.

Only names re-exported here are public API. The optional adapters live in their own
subpackages and are imported explicitly: ``xippios.core.mcp``, ``xippios.core.http``,
``xippios.core.testing``.
"""

from xippios.core._loop import sync
from xippios.core._version import __version__
from xippios.core.client import (
    AsyncClient,
    BasicKeyAuth,
    BearerAuth,
    CacheBackend,
    ClientConfig,
    EnvKeyAuth,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    QuotaPolicy,
    QuotaSnapshot,
    RateLimit,
    RetryPolicy,
    Timeouts,
)
from xippios.core.errors import (
    AuthError,
    ConfigError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
    ValidationError,
    XippiosError,
)
from xippios.core.models import Result, ResultMeta, UpstreamModel, parse, parse_decimal
from xippios.core.pagination import collect, paginate_cursor, paginate_offset, paginate_pages
from xippios.core.reference import load_csv, load_json, load_table
from xippios.core.tenants import Tenants

__all__ = [
    "AsyncClient",
    "AuthError",
    "BasicKeyAuth",
    "BearerAuth",
    "CacheBackend",
    "ClientConfig",
    "ConfigError",
    "EnvKeyAuth",
    "HeaderKeyAuth",
    "InvalidRequestError",
    "MemoryCache",
    "NotFoundError",
    "QueryKeyAuth",
    "QuotaPolicy",
    "QuotaSnapshot",
    "RateLimit",
    "RateLimitError",
    "Result",
    "ResultMeta",
    "RetryPolicy",
    "Tenants",
    "Timeouts",
    "TransportError",
    "UpstreamError",
    "UpstreamModel",
    "ValidationError",
    "XippiosError",
    "__version__",
    "collect",
    "load_csv",
    "load_json",
    "load_table",
    "paginate_cursor",
    "paginate_offset",
    "paginate_pages",
    "parse",
    "parse_decimal",
    "sync",
]
