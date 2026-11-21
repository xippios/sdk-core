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
    BearerToken,
    ClientConfig,
    Downloaded,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    QuotaPolicy,
    RateLimit,
    RenewingBearerAuth,
    RetryPolicy,
    Timeouts,
)
from xippios.core.contract import EnvVar
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
    request_description,
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
from xippios.core.reference import (
    PackagedCodes,
    PackagedList,
    closest,
    load_json,
    load_table,
    matches,
    nearest,
)
from xippios.core.tenants import TenantLock, Tenants, bind_tasks, list_task, tenant_instructions

__all__ = [
    "BODY_LIMIT",
    "Answer",
    "AsyncClient",
    "AuthError",
    "BasicKeyAuth",
    "BearerAuth",
    "BearerToken",
    "ClientConfig",
    "ConfigError",
    "Downloaded",
    "EnvVar",
    "HeaderKeyAuth",
    "InvalidRequestError",
    "MemoryCache",
    "NotFoundError",
    "PackagedCodes",
    "PackagedList",
    "QueryKeyAuth",
    "QuotaPolicy",
    "RateLimit",
    "RateLimitError",
    "RenewingBearerAuth",
    "Result",
    "ResultCap",
    "ResultMeta",
    "RetryPolicy",
    "TenantLock",
    "Tenants",
    "Timeouts",
    "TransportError",
    "UnknownCode",
    "UpstreamError",
    "UpstreamModel",
    "ValidationError",
    "XippiosError",
    "__version__",
    "bind_tasks",
    "closest",
    "collect",
    "error_from_response",
    "list_task",
    "load_json",
    "load_table",
    "matches",
    "nearest",
    "paginate_offset",
    "parse",
    "parse_decimal",
    "parse_retry_after",
    "request_description",
    "sync",
    "tenant_instructions",
]
