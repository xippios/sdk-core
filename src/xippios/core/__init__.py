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
    Client,
    ClientConfig,
    EnvKeyAuth,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    RateLimit,
    RetryPolicy,
    Timeouts,
)
from xippios.core.config import SourceSettings, resolve_api_key
from xippios.core.errors import (
    AuthError,
    ConfigError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
    ValidationError,
    XippiosError,
)
from xippios.core.models import Result, ResultMeta, UpstreamModel, parse
from xippios.core.pagination import collect, paginate_cursor, paginate_offset, paginate_pages
from xippios.core.reference import load_csv, load_json, load_table

__all__ = [
    "AsyncClient",
    "AuthError",
    "BasicKeyAuth",
    "BearerAuth",
    "CacheBackend",
    "Client",
    "ClientConfig",
    "ConfigError",
    "EnvKeyAuth",
    "HeaderKeyAuth",
    "MemoryCache",
    "NotFoundError",
    "QueryKeyAuth",
    "RateLimit",
    "RateLimitError",
    "Result",
    "ResultMeta",
    "RetryPolicy",
    "SourceSettings",
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
    "resolve_api_key",
    "sync",
]
