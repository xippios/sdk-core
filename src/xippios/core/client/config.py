"""Value objects configuring a client: retry policy, rate limit, cache, read timeout."""

import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field

import httpx

from xippios.core.client.cache import CacheBackend
from xippios.core.errors import XippiosError

__all__ = ["ClientConfig", "RateLimit", "RetryPolicy"]


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryPolicy:
    """Exponential backoff with jitter for a read (conventions §6, ADR-0011).

    A read, a ``GET``, ``HEAD`` or ``OPTIONS`` request, is retried after a 429, a 5xx or a
    transport failure, and never after another 4xx. A write, a request of any other method,
    is sent once whatever the policy says, since a repeat can apply it twice (ADR-0011,
    amendment 2026-11-24).

    Attributes:
        max_attempts: Total attempts of a read, the first included; ``1`` sends every
            request once, as the client of a source whose reads upstream bills does.
        backoff_base: Delay in seconds before the first retry, doubled on each further one.
        backoff_max: Upper bound for one delay. A ``Retry-After`` beyond it stops retrying,
            so the caller sees the ``RateLimitError`` instead of a long silent wait.
        jitter: Randomise each delay within ``[delay / 2, delay]``.
    """

    max_attempts: int = 4
    backoff_base: float = 0.5
    backoff_max: float = 30.0
    jitter: bool = True

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
        per_minute: Sustained requests per minute: the pace the source sets within
            upstream's documented per-second or per-minute limit, or a self-imposed pace
            (ADR-0033).
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
        source: Source slug, e.g. ``"example"``; used in the User-Agent and in errors.
        version: Version of the source package, for the User-Agent.
        base_url: Upstream base URL; request paths are joined onto it.
        read_timeout: Seconds to wait for the next bytes of an answer, 60 by default
            (conventions §6); a source whose upstream builds a large answer slowly raises
            it, e.g. ``180.0``. Connecting, sending a request and waiting for a pooled
            connection take 10 s each, the family's.
        retry: Retry policy of a read after a 429, a 5xx or a transport failure.
        rate_limit: Client-side limit; ``None`` disables it.
        cache: Backend for GET responses; ``None`` disables caching. Every GET looks
            it up, and ``get_answer`` alone stores in it, a 200 once the body decoded,
            for as long as the cache keeps its path, ``MemoryCache(lifetimes=...)``; a
            path the cache keeps for no time is never stored (ADR-0040, decision 3).
        cache_max_bytes: The largest body the cache stores, in bytes as ``httpx``
            decoded them; 8 MiB by default (ADR-0040, decision 3). A larger answer is
            returned as usual and not stored, so the next call fetches it again. A
            source that wants a larger answer cached raises the bound and says why in
            its ``CLAUDE.md``. ``download`` never touches the cache.
        headers: Extra headers sent with every request.
        classify: The source's own error mapping (ADR-0031): called with every response
            before the default status mapping; return a taxonomy error to raise it, or
            ``None`` to fall through. Where a source states its documented error shapes,
            including errors upstream sends with a 200. It is also asked before a 429 or
            5xx is retried (ADR-0037): a
            ``RateLimitError`` sets the wait from its ``retry_after``, so one beyond
            ``retry.backoff_max`` is not retried; an ``UpstreamError`` for a 5xx and
            ``None`` leave the decision to the retry policy; any other error stops the
            retries. At most once per response.
        before_request: Called once per call, downloads and recordings too, not per retry, after the
            cache lookup (a cache hit returns before it) and before the rate limiter,
            with the request as built from base URL, path, query parameters, body and
            headers; credentials from ``auth`` are not on it yet, and changes to it are
            not sent. Its extensions say where the credentials go: ``xippios_auth``
            (``"client"``, ``"none"`` for ``auth=None``, ``"own"``) and ``xippios_origin``
            (``"base"``, or ``"other"`` for another origin than the base URL's, where the
            client's auth is not sent). It may be sync or async (an awaitable result is
            awaited), may wait, e.g. for a spent quota (ADR-0033), and may raise a
            taxonomy error, in which case nothing is sent. ``QuotaPolicy.install`` sets
            it (ADR-0037).
        observe: Called with every response that came from the wire, each retried
            attempt included and a cache hit never, before ``classify`` and before the
            retry decision, also for a recording's answer, which nothing raises
            (``xippios.core.testing.send_once``); its ``request`` carries the extensions
            ``before_request`` reads. For reading, e.g. quota headers; it returns
            nothing, and an exception it raises propagates as the programming error it
            is, except on a ``download``'s success, whose body goes to the file unread:
            a hook that reads it there is suppressed and counts as nothing observed
            (``httpx.ResponseNotRead``, ADR-0040). ``QuotaPolicy.install`` sets it
            (ADR-0037).
    """

    source: str
    version: str
    base_url: str
    read_timeout: float = 60.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    rate_limit: RateLimit | None = None
    cache: CacheBackend | None = None
    cache_max_bytes: int = 8 * 1024 * 1024
    headers: Mapping[str, str] = field(default_factory=dict)
    classify: Callable[[httpx.Response], XippiosError | None] | None = None
    before_request: Callable[[httpx.Request], Awaitable[None] | None] | None = None
    observe: Callable[[httpx.Response], None] | None = None

    def __post_init__(self) -> None:
        if self.read_timeout <= 0:
            raise ValueError("read_timeout must be above 0 seconds")
        if self.cache_max_bytes < 1:
            raise ValueError("cache_max_bytes must be at least 1")

    @property
    def user_agent(self) -> str:
        """The family's one User-Agent format."""
        return f"xippios-{self.source}/{self.version} (+https://github.com/xippios)"
