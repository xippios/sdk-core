"""A quota policy: the quota headers observed, and no request fired into a spent quota.

ADR-0010 decides how the family spends an upstream's longer-window quota: spend it when
the data is worth it, interpret the refusal, and never fire into a quota known to be
spent. ``QuotaPolicy`` implements that on the client's two hooks (ADR-0015): ``observe``
reads the quota headers of every response from the wire, and ``before_request``, which
runs after the cache lookup, waits a spent quota out when the wait is short and
otherwise refuses without sending::

    policy = QuotaPolicy(window=3600.0, source="usda-psd")
    client = AsyncClient(policy.install(config), auth=auth)

The snapshot belongs to the policy: clients that draw on one quota, one key say, share
one policy. A cache hit never waits and never updates the snapshot.
"""

import asyncio
import dataclasses
import logging
import math
import threading
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from xippios.core.client.config import ClientConfig, RetryPolicy
from xippios.core.errors import RateLimitError, parse_retry_after

__all__ = ["QuotaPolicy", "QuotaSnapshot"]

logger = logging.getLogger("xippios.core.client")

_DEFAULT_PAUSE_CAP = RetryPolicy().backoff_max
"""The cap of ``before_request`` called directly on a policy given none: 30 s."""
_TEN_YEARS = 315_360_000.0
"""Seconds in ten years: the longest ``window``, so a ``resumes_at`` can always be computed.

Also where a reset header's integer stops being a delay and becomes an epoch timestamp:
no quota resets in more than ten years, and no epoch timestamp since 1980 is smaller.
"""


_POLICIES: "weakref.WeakSet[QuotaPolicy]" = weakref.WeakSet()
"""Every live policy, for the testing plugin's reset between tests (ADR-0013)."""
_POLICIES_LOCK = threading.Lock()


def _reset_every_policy() -> None:
    """Forget every live policy's snapshot; the testing plugin calls it around each test."""
    with _POLICIES_LOCK:
        policies = list(_POLICIES)
    for policy in policies:
        policy.reset()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _header_count(response: httpx.Response, name: str | None) -> int | None:
    """The count in header ``name``; ``None`` when that header's reading is off (``None``)."""
    return None if name is None else _count(response.headers.get(name))


def _count(value: str | None) -> int | None:
    """A header's non-negative integer in ASCII digits, or ``None`` when absent or not one.

    ``str.isdigit`` alone accepts ``"²"``, which ``int`` refuses; more than 18 digits is
    no count, and ``int`` refuses more than 4,300.
    """
    if value is None:
        return None
    text = value.strip()
    if not (text.isascii() and text.isdigit()) or len(text) > 18:
        return None
    return int(text)


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    """An upstream's request quota as the last response from the wire reported it.

    Attributes:
        limit: The quota's size from the limit header, e.g. ``1000``; kept from an earlier
            response when the latest one omits it; ``None`` when none reported it.
        remaining: Requests left from the remaining header, e.g. ``999``; ``0`` after a
            429, whatever the header said; ``None`` when the latest response omitted it.
        observed_at: When the response that reported it was observed, UTC.
        resumes_at: While ``remaining`` is ``0``, when the quota is expected back: from a
            429's ``Retry-After``, else the policy's reset header, else its ``window``
            counted from ``observed_at``, never later than one ``window`` after it;
            ``None`` while requests remain.
    """

    limit: int | None
    remaining: int | None
    observed_at: datetime
    resumes_at: datetime | None

    def describe(self) -> str:
        """One line of numbers and times, for messages and logs.

        E.g. ``"0 of 1000 requests left as of 2026-10-23T08:00:00Z, expected back at
        2026-10-23T09:00:00Z"``; an unknown number reads ``?``. Never a header's text.
        """
        left = "?" if self.remaining is None else str(self.remaining)
        limit = "?" if self.limit is None else str(self.limit)
        text = f"{left} of {limit} requests left as of {_utc(self.observed_at)}"
        if self.resumes_at is not None:
            text += f", expected back at {_utc(self.resumes_at)}"
        return text


class QuotaPolicy:
    """An upstream's request quota observed from its headers, and requests paced to it.

    Implements ADR-0010's quota rules on ``ClientConfig.observe`` and
    ``ClientConfig.before_request`` (ADR-0015); ``install`` sets both. ``observe`` keeps
    a snapshot of the quota headers of every response from the wire, raw ones
    (``raise_on_error=False``) included, and never of a cache hit. When the snapshot
    shows the quota spent, ``before_request`` waits until it is expected back if that
    is within ``pause_cap``, logging one warning, and otherwise raises
    ``RateLimitError`` with ``retry_after`` and sends nothing, so a sync call or an MCP
    tool never blocks for an hour. A request the cache answers never reaches it.

    A 429 marks the quota spent by itself. A source whose upstream answers a spent
    limit otherwise, UN Comtrade's 403 "Quota will be replenished in HH:MM:SS" for one,
    passes ``spent``, which reads that answer; code that learns of a spent quota some
    other way calls ``mark_spent``. The source's ``classify`` still maps the refusal
    (ADR-0010) and can read ``snapshot()`` for its message: ``observe`` runs before it.

    Args:
        limit_header: The header with the quota's size, e.g. ``"x-ratelimit-limit"``;
            ``None`` turns its reading off.
        remaining_header: The header with the requests left, e.g.
            ``"x-ratelimit-remaining"``; ``None`` turns its reading off. Read only a
            header that describes the long-window quota: where upstream's
            ``x-ratelimit-*`` headers describe a per-second or per-minute pace (UN
            Comtrade's), a remaining ``0`` would pause for ``window``. With both
            ``None`` the policy relies on a 429, ``spent`` and ``mark_spent`` alone.
        reset_header: The header saying when a spent quota comes back, e.g.
            ``"x-ratelimit-reset"``, in any of three formats: delay-seconds (``"120"``),
            epoch seconds (``"1761206400"``, as GitHub sends it; an integer above ten
            years of seconds is read as one), or an HTTP-date. ``None`` when upstream
            sends none, as api.data.gov does.
        window: The quota's window in seconds, the one setting for two things: how long
            a spent quota stays spent when neither ``Retry-After`` (on a 429), the reset
            header nor ``spent`` names a time, and the longest wait any of those can
            set, so no refusal outlives one window. ``3600.0`` for an hourly quota
            (api.data.gov); ``86400.0`` for a daily one, e.g. UN Comtrade's, whose 403
            names up to 24 hours and would otherwise be cut to one. At most ten years.
        spent: Called by ``observe`` with every response it observes, after the quota
            headers are read: a number of seconds marks the quota spent for that long
            (cut to ``window``, and ahead of ``Retry-After`` and the reset header);
            ``None`` says the response does not tell. E.g. a function that reads
            "replenished in 01:02:03" from a 403's body and returns ``3723.0``. An
            exception it raises propagates, as one from any ``observe`` hook does.
        pause_cap: The longest wait inside a call, in seconds, e.g. ``30.0``. ``None``
            takes the ``retry.backoff_max`` of each config the policy is installed on,
            the bound the retry loop uses for a ``Retry-After``; called directly,
            ``before_request`` then uses 30 s.
        source: Source slug for the ``RateLimitError`` and the log line, e.g.
            ``"usda-psd"``.
        clock: The current time, timezone-aware, replaceable in tests.
        sleep: Async sleep for the pause, replaceable in tests.

    Attributes:
        limit_header: As given.
        remaining_header: As given.
        reset_header: As given.
        window: As given.
        spent: As given.
        pause_cap: As given.
        source: As given.

    Raises:
        ValueError: A ``window`` that is negative or longer than ten years, or a
            negative ``pause_cap``.
    """

    def __init__(
        self,
        *,
        limit_header: str | None = "x-ratelimit-limit",
        remaining_header: str | None = "x-ratelimit-remaining",
        reset_header: str | None = None,
        window: float = 3600.0,
        spent: Callable[[httpx.Response], float | None] | None = None,
        pause_cap: float | None = None,
        source: str | None = None,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 <= window <= _TEN_YEARS:
            raise ValueError("window must be between 0 and ten years (315360000 s)")
        if pause_cap is not None and pause_cap < 0:
            raise ValueError("pause_cap must be non-negative")
        self.limit_header = limit_header
        self.remaining_header = remaining_header
        self.reset_header = reset_header
        self.window = window
        self.spent = spent
        self.pause_cap = pause_cap
        self.source = source
        self._clock = clock
        self._sleep = sleep
        self._snapshot: QuotaSnapshot | None = None
        self._lock = threading.Lock()
        with _POLICIES_LOCK:
            _POLICIES.add(self)

    def snapshot(self) -> QuotaSnapshot | None:
        """The quota as the last response reported it; ``None`` before the first one."""
        with self._lock:
            return self._snapshot

    def reset(self) -> None:
        """Forget the snapshot, e.g. between tests; the next response starts a new one."""
        with self._lock:
            self._snapshot = None

    def observe(self, response: httpx.Response) -> None:
        """Update the snapshot from ``response``'s quota headers and status.

        A response with neither quota header leaves the snapshot alone, unless it is a
        429 or ``spent`` returns a number for it, either of which marks the quota spent.
        A cache hit is ignored: its headers are as old as the entry (ADR-0010). The
        ``ClientConfig.observe`` hook.

        Args:
            response: A response from the wire, any status.
        """
        if response.extensions.get("xippios_cache") == "hit":
            return
        limit = _header_count(response, self.limit_header)
        remaining = _header_count(response, self.remaining_header)
        limited = response.status_code == 429
        named = self.spent(response) if self.spent is not None else None
        if limit is None and remaining is None and not limited and named is None:
            return
        now = self._clock()
        if limited or named is not None:
            remaining = 0
        resumes_at = None
        if remaining == 0:
            wait = self._cut(named) if named is not None else self._wait(response, now)
            resumes_at = now + timedelta(seconds=wait)
        with self._lock:
            if limit is None and self._snapshot is not None:
                limit = self._snapshot.limit
            self._snapshot = QuotaSnapshot(
                limit=limit, remaining=remaining, observed_at=now, resumes_at=resumes_at
            )

    def mark_spent(self, retry_after: float) -> None:
        """Mark the quota spent from now, for ``retry_after`` seconds cut to ``window``.

        For a spent quota the policy cannot see in a response, e.g. one a task learns
        from a payload it parses itself. The last limit is kept; ``remaining`` is ``0``.

        Args:
            retry_after: Seconds until the quota is expected back, e.g. ``3600.0``; a
                negative wait is ``0``.

        Raises:
            ValueError: ``retry_after`` is NaN.
        """
        now = self._clock()
        resumes_at = now + timedelta(seconds=self._cut(retry_after))
        with self._lock:
            limit = self._snapshot.limit if self._snapshot is not None else None
            self._snapshot = QuotaSnapshot(
                limit=limit, remaining=0, observed_at=now, resumes_at=resumes_at
            )

    async def before_request(self, request: httpx.Request) -> None:
        """Wait out a spent quota within ``pause_cap``; beyond it, refuse without sending.

        Called once per request, after the cache lookup. ``install`` sets a hook that
        does the same with the cap of the config it was installed on; called directly,
        the cap is ``pause_cap``, or 30 s when that is ``None``. Does nothing while the
        snapshot shows requests left or the quota is expected back already.

        Args:
            request: The request about to be sent; its method and path name it in the
                log line and the error, never its host or query (conventions §5).

        Raises:
            RateLimitError: The quota is expected back later than the cap from now;
                ``retry_after`` is the wait, and the message says that nothing was sent
                and when the quota is expected back.
        """
        cap = self.pause_cap if self.pause_cap is not None else _DEFAULT_PAUSE_CAP
        await self._pause(request, cap)

    def install(self, config: ClientConfig) -> ClientConfig:
        """``config`` with this policy's ``before_request`` and ``observe`` hooks.

        Returns ``dataclasses.replace(config, before_request=..., observe=...)``;
        ``config`` itself is unchanged. The ``before_request`` hook is bound to this
        config's cap: ``pause_cap`` when the policy was given one, else
        ``config.retry.backoff_max``, so one policy installed on two configs pauses each
        within its own bound, and a client from ``AsyncClient.derive`` keeps its
        parent's hooks and cap. Installing the policy again on a config it is installed
        on is allowed.

        Args:
            config: The source's client configuration.

        Raises:
            ValueError: ``config`` has a ``before_request`` or ``observe`` hook that is
                not this policy's; combine them in hooks of the source's own instead.
        """
        foreign = [
            name
            for name, hook in (
                ("before_request", config.before_request),
                ("observe", config.observe),
            )
            if hook is not None and not self._owns(hook)
        ]
        if foreign:
            raise ValueError(
                f"the config already has hooks of its own ({', '.join(foreign)}); a "
                "QuotaPolicy installs before_request and observe, so combine them in hooks "
                "of your own instead"
            )
        cap = self.pause_cap if self.pause_cap is not None else config.retry.backoff_max
        return dataclasses.replace(
            config, before_request=_InstalledPause(self, cap), observe=self.observe
        )

    async def _pause(self, request: httpx.Request, cap: float) -> None:
        """Wait out a spent quota within ``cap`` seconds; beyond it, raise without sending."""
        snapshot = self.snapshot()
        if snapshot is None or snapshot.resumes_at is None:
            return
        wait = (snapshot.resumes_at - self._clock()).total_seconds()
        if wait <= 0:
            return
        where = f"{request.method} {request.url.path}"
        if wait > cap:
            raise RateLimitError(
                f"quota spent ({snapshot.describe()}); nothing was sent for {where}: the "
                f"quota is expected back at {_utc(snapshot.resumes_at)}, later than a call "
                f"waits ({cap:g} s)",
                retry_after=wait,
                source=self.source,
            )
        logger.warning(
            "%squota spent (%s); waiting %.0f s before %s",
            f"{self.source}: " if self.source else "",
            snapshot.describe(),
            wait,
            where,
        )
        await self._sleep(wait)

    def _owns(self, hook: object) -> bool:
        """True for a hook this policy set or is: an installed pause, or a bound method."""
        if isinstance(hook, _InstalledPause):
            return hook.policy is self
        return hook == self.before_request or hook == self.observe

    def _cut(self, wait: float) -> float:
        """``wait`` within ``[0, window]``: no refusal outlives one window, no date overflows."""
        if math.isnan(wait):
            raise ValueError("a wait is a number of seconds, not NaN")
        return min(max(wait, 0.0), self.window)

    def _wait(self, response: httpx.Response, now: datetime) -> float:
        """Seconds until a spent quota is back: ``Retry-After``, the reset header, ``window``.

        A wait read from a header is cut to ``window``: a value no upstream means (a
        ``Retry-After`` of 10**12 s) neither refuses for decades nor overflows a date.
        """
        if response.status_code == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"), now=now)
            if retry_after is not None:
                return min(retry_after, self.window)
        if self.reset_header is not None:
            reset = _reset_wait(response.headers.get(self.reset_header), now)
            if reset is not None:
                return min(reset, self.window)
        return self.window


def _reset_wait(value: str | None, now: datetime) -> float | None:
    """Seconds from ``now`` to a reset header's time: delay, epoch seconds or HTTP-date."""
    seconds = parse_retry_after(value, now=now)
    if seconds is None or value is None or seconds <= _TEN_YEARS or not value.strip().isdigit():
        return seconds
    # An integer beyond ten years is an epoch timestamp (GitHub's x-ratelimit-reset).
    return max(0.0, seconds - now.timestamp())


@dataclass(frozen=True, slots=True)
class _InstalledPause:
    """The ``before_request`` hook ``QuotaPolicy.install`` sets: the pause at one config's cap.

    A value, so a config installed twice compares equal, and a ``derive``d config, which
    copies its hooks, keeps the cap of the config it came from.
    """

    policy: QuotaPolicy
    cap: float

    async def __call__(self, request: httpx.Request) -> None:
        await self.policy._pause(request, self.cap)
