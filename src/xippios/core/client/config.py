"""Value objects configuring a client: timeouts, retry policy, rate limit, cache."""

import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

import httpx

from xippios.core.client.cache import CacheBackend
from xippios.core.errors import XippiosError

__all__ = ["ClientConfig", "RateLimit", "RetryPolicy", "Timeouts"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Timeouts:
    """Explicit timeouts in seconds; the defaults are the family's (conventions §6)."""

    connect: float = 10.0
    read: float = 60.0
    write: float = 10.0
    pool: float = 10.0

    def to_httpx(self) -> httpx.Timeout:
        """The equivalent ``httpx.Timeout``."""
        return httpx.Timeout(connect=self.connect, read=self.read, write=self.write, pool=self.pool)


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryPolicy:
    """Exponential backoff with jitter (conventions §6, ADR-0011).

    A 429 is retried for every method. A 5xx and a transport failure are retried for
    idempotent methods only (GET, HEAD, OPTIONS) unless ``retry_non_idempotent`` is set.
    Another 4xx is never retried.

    Attributes:
        max_attempts: Total attempts including the first; ``1`` disables retries.
        backoff_base: Delay in seconds before the first retry, doubled on each further one.
        backoff_max: Upper bound for one delay. A ``Retry-After`` beyond it stops retrying,
            so the caller sees the ``RateLimitError`` instead of a long silent wait.
        jitter: Randomise each delay within ``[delay / 2, delay]``.
        retry_transport_errors: Also retry timeouts and connection failures; for which
            methods follows ``retry_non_idempotent``.
        retry_non_idempotent: Also retry a 5xx and a transport failure for the other
            methods (POST, PUT, PATCH, DELETE). Off by default: such a request may have
            been applied before the failure, and a repeat can apply it twice. Set it
            only where upstream makes a repeated write safe, e.g. by an idempotency key
            it honours, or where the client only reads through POST.
    """

    max_attempts: int = 4
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    jitter: bool = True
    retry_transport_errors: bool = True
    retry_non_idempotent: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_base < 0 or self.backoff_max < 0:
            raise ValueError("backoff values must be non-negative")

    def delay(self, attempt: int, *, retry_after: float | None = None) -> float | None:
        """Seconds to wait after failed attempt number ``attempt``, or ``None`` to stop.

        Args:
            attempt: The attempt that just failed, counting from 1.
            retry_after: Upstream's ``Retry-After`` in seconds, when it sent one.
        """
        if attempt >= self.max_attempts:
            return None
        if retry_after is not None and retry_after > self.backoff_max:
            return None
        delay = min(self.backoff_max, self.backoff_base * 2.0 ** (attempt - 1))
        if self.jitter:
            delay = random.uniform(delay / 2, delay)
        if retry_after is not None:
            delay = max(delay, retry_after)
        return delay


@dataclass(frozen=True, slots=True, kw_only=True)
class RateLimit:
    """Client-side rate limit as a token bucket.

    Attributes:
        per_minute: Sustained requests per minute, from the upstream's documented limit.
        burst: Requests allowed at once; defaults to ``per_minute``.
    """

    per_minute: int
    burst: int | None = None

    def __post_init__(self) -> None:
        if self.per_minute < 1:
            raise ValueError("per_minute must be at least 1")
        if self.burst is not None and self.burst < 1:
            raise ValueError("burst must be at least 1")

    @property
    def capacity(self) -> int:
        """Bucket size."""
        return self.burst if self.burst is not None else self.per_minute

    @property
    def per_second(self) -> float:
        """Refill rate."""
        return self.per_minute / 60.0


@dataclass(frozen=True, slots=True, kw_only=True)
class ClientConfig:
    """Everything a client needs to talk to one upstream.

    Attributes:
        source: Source slug, e.g. ``"usda-nass"``; used in the User-Agent and in errors.
        version: Version of the source package, for the User-Agent.
        base_url: Upstream base URL; request paths are joined onto it.
        timeouts: Connect/read/write/pool timeouts.
        retry: Retry policy for 429, 5xx and transport failures.
        rate_limit: Client-side limit; ``None`` disables it.
        cache: Backend for GET responses; ``None`` disables caching.
        cache_filter: Which GET requests the cache takes: called with the request as
            built from the base URL, path and query parameters (``request.url.path``,
            ``request.url.params``; credentials from ``auth`` are not on it yet); a GET
            is looked up and stored only when it returns ``True``. ``None`` caches every
            GET. Lets one client cache a reference endpoint and nothing else.
        headers: Extra headers sent with every request.
        classify: The source's own error mapping (ADR-0008): called with every response
            before the default status mapping; return a taxonomy error to raise it, or
            ``None`` to fall through. Where a source states its documented error shapes,
            including errors upstream sends with a 200. It is also asked before a 429 or
            5xx is retried, ``raise_on_error=False`` or not (ADR-0015): a
            ``RateLimitError`` sets the wait from its ``retry_after``, so one beyond
            ``retry.backoff_max`` is not retried; any other error stops the retries;
            ``None`` leaves the decision to the retry policy. At most once per response.
        before_request: Called once per ``request()`` call, not per retry, after the
            cache lookup (a cache hit returns before it) and before the rate limiter,
            with the request as built from base URL, path, query parameters, body and
            headers; credentials from ``auth`` are not on it yet, and changes to it are
            not sent. It may be sync or async (an awaitable result is awaited), may wait,
            e.g. for a spent quota (ADR-0010), and may raise a taxonomy error, in which
            case nothing is sent. ``QuotaPolicy.install`` sets it (ADR-0015).
        observe: Called with every response that came from the wire, each retried
            attempt included and a cache hit never, before ``classify`` and before the
            retry decision, also when the caller asked for the raw response
            (``raise_on_error=False``). For reading, e.g. quota headers; it returns
            nothing, and an exception it raises propagates as the programming error it
            is. ``QuotaPolicy.install`` sets it (ADR-0015).
    """

    source: str
    version: str
    base_url: str
    timeouts: Timeouts = field(default_factory=Timeouts)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    rate_limit: RateLimit | None = None
    cache: CacheBackend | None = None
    cache_filter: Callable[[httpx.Request], bool] | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    classify: Callable[[httpx.Response], XippiosError | None] | None = None
    before_request: Callable[[httpx.Request], Awaitable[None] | None] | None = None
    observe: Callable[[httpx.Response], None] | None = None

    @property
    def user_agent(self) -> str:
        """The family's one User-Agent format."""
        return f"xippios-{self.source}/{self.version} (+https://github.com/xippios)"
