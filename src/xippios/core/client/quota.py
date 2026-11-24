"""A quota policy: the quota headers observed, and no request fired into a spent quota.

ADR-0033 decides how the family spends an upstream's longer-window quota: spend it when
the data is worth it, interpret the refusal, and never fire into a quota known to be
spent. ``QuotaPolicy`` implements that on the client's two hooks (ADR-0037): ``observe``
reads the quota headers of every response from the wire, and ``before_request``, which
runs after the cache lookup, waits a spent quota out when the wait is short and
otherwise refuses without sending::

    policy = QuotaPolicy(
        limit_header="x-ratelimit-limit",
        remaining_header="x-ratelimit-remaining",
        window=3600.0,
        source="example",
    )
    client = AsyncClient(policy.install(config), auth=auth)

The snapshot belongs to the policy: clients that draw on one quota, one key say, share
one policy. A cache hit never waits and never updates the snapshot. Nor does a request
outside the quota: one sent with ``auth=None``, or to an origin other than the client's
base URL's, which the client marks (``xippios_auth``, ``xippios_origin``). The sources that
one key serves share one policy per process for it.
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
from typing import Final

import httpx

from xippios.core.client.config import ClientConfig
from xippios.core.errors import RateLimitError, parse_retry_after

__all__ = ["QuotaPolicy", "QuotaSnapshot"]

logger = logging.getLogger("xippios.core.client")

_TEN_YEARS = 315_360_000.0
"""Seconds in ten years: the longest ``window``, so a ``resumes_at`` can always be computed."""

_PAUSE_CAP: Final = 30.0
"""The longest wait inside a call, in seconds: ``RetryPolicy``'s default ``backoff_max``."""


_POLICIES: "weakref.WeakSet[QuotaPolicy]" = weakref.WeakSet()
"""Every live policy, for the testing plugin's reset between tests (ADR-0035)."""
_POLICIES_LOCK = threading.Lock()


def _every_policy() -> list["QuotaPolicy"]:
    """Every live policy, for the testing plugin (ADR-0035)."""
    with _POLICIES_LOCK:
        return list(_POLICIES)


def _reset_every_policy() -> None:
    """Forget every live policy's snapshot; the testing plugin calls it around each test."""
    for policy in _every_policy():
        policy.reset()


def _outside(request: httpx.Request) -> bool:
    """True for a request outside the quota, as the client marks it.

    Sent with ``auth=None`` (``xippios_auth: "none"``), or to an origin other than the
    base URL's (``xippios_origin: "other"``), where the client's auth never goes: neither
    spends the key's quota (https://github.com/xippios/sdk-core/issues/163). A request
    built without the marks counts.
    """
    extensions = request.extensions
    return extensions.get("xippios_auth") == "none" or extensions.get("xippios_origin") == "other"


def _outside_answer(response: httpx.Response) -> bool:
    """True for the answer to a request outside the quota; a response with no request counts."""
    try:
        request = response.request
    except RuntimeError:  # httpx raises it for a response built without a request
        return False
    return _outside(request)


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
            429's ``Retry-After``, or the seconds ``spent`` named, else the policy's
            ``window`` counted from ``observed_at``, never later than one ``window`` after
            it; ``None`` while requests remain.
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

    Implements ADR-0033's quota rules on ``ClientConfig.observe`` and
    ``ClientConfig.before_request`` (ADR-0037); ``install`` sets both. ``observe`` keeps
    a snapshot of the quota headers of every response from the wire, a recording's
    included, and never of a cache hit. When the snapshot shows the quota spent,
    ``before_request`` waits until it is expected back if that is within 30 seconds,
    ``RetryPolicy``'s default ``backoff_max``, logging one warning, and otherwise raises
    ``RateLimitError`` with ``retry_after`` and sends nothing, so a sync call or an MCP
    tool never blocks for an hour. A request the cache answers never reaches it. The 30
    seconds are the one bound of that wait, wherever the policy is installed.

    A request outside the quota is neither held back nor read: one sent with
    ``auth=None``, a keyless endpoint of the same upstream, and one to an origin other than
    the client's base URL's, a file link on another host, which the client's auth never
    reaches either. Its answer leaves the snapshot alone, and the client's limiter still
    paces it.

    A 429 marks the quota spent by itself, until its ``Retry-After`` or, without one,
    for ``window``. A source whose upstream answers a spent limit otherwise, a 403
    "Quota will be replenished in HH:MM:SS" say, passes ``spent``, which reads that
    answer. The source's ``classify`` still maps the refusal (ADR-0033) and can read
    ``snapshot()`` for its message: ``observe`` runs before it.

    Args:
        limit_header: The header with the quota's size, e.g. ``"x-ratelimit-limit"``;
            ``None``, the default, reads none.
        remaining_header: The header with the requests left, e.g.
            ``"x-ratelimit-remaining"``; ``None``, the default, reads none. Name only a
            header that describes the long-window quota: where upstream's
            ``x-ratelimit-*`` headers describe a per-second or per-minute pace, a
            remaining ``0`` would pause for ``window``. With both ``None`` the policy
            relies on a 429 and ``spent`` alone.
        window: The quota's window in seconds, given always, the one setting for two
            things: how long a spent quota stays spent when neither ``Retry-After`` (on a
            429) nor ``spent`` names a time, and the longest wait either can set, so no
            refusal outlives one window. ``3600.0`` for an hourly quota; ``86400.0`` for a
            daily one, whose answer may name up to 24 hours, which would otherwise be cut
            to one. At most ten years.
        spent: Called by ``observe`` with every response it observes, after the quota
            headers are read: a number of seconds marks the quota spent for that long
            (cut to ``window``, and ahead of ``Retry-After``); ``None`` says the response
            does not tell. E.g. a function that reads "replenished in 01:02:03" from a
            403's body and returns ``3723.0``. An exception it raises propagates, as one
            from any ``observe`` hook does, except on a ``download``'s success, whose
            body goes to the file unread: reading it there is suppressed and counts as
            nothing observed (ADR-0040).
        source: Name for the ``RateLimitError`` and the log line, e.g. ``"usda-psd"``,
            or the gateway's name where one policy serves several sources.
        clock: The current time, timezone-aware, replaceable in tests.
        sleep: Async sleep for the pause, replaceable in tests.

    Attributes:
        limit_header: As given.
        remaining_header: As given.
        window: As given.
        spent: As given.
        source: As given.

    Raises:
        ValueError: A ``window`` that is negative, NaN or longer than ten years.
    """

    def __init__(
        self,
        *,
        limit_header: str | None = None,
        remaining_header: str | None = None,
        window: float,
        spent: Callable[[httpx.Response], float | None] | None = None,
        source: str | None = None,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 <= window <= _TEN_YEARS:
            raise ValueError("window must be between 0 and ten years (315360000 s)")
        self.limit_header = limit_header
        self.remaining_header = remaining_header
        self.window = window
        self.spent = spent
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
        A cache hit is ignored: its headers are as old as the entry (ADR-0033), and so is
        the answer to a request outside the quota, sent with ``auth=None`` or to another
        origin, as the client marks it. The ``ClientConfig.observe`` hook.

        Args:
            response: A response from the wire, any status.
        """
        if response.extensions.get("xippios_cache") == "hit" or _outside_answer(response):
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

    async def before_request(self, request: httpx.Request) -> None:
        """Wait out a spent quota within 30 s; beyond that, refuse without sending.

        The ``ClientConfig.before_request`` hook ``install`` sets, called once per
        request, after the cache lookup. Does nothing while the snapshot shows requests
        left or the quota is expected back already, nor for a request outside the quota,
        sent with ``auth=None`` or to another origin, as the client marks it. Its wait
        and its refusal are the
        pause step, which the testing plugin turns off in offline tests; a subclass's
        override that waits or refuses on its own is not turned off (ADR-0037).

        Args:
            request: The request about to be sent; its method and path name it in the
                log line and the error, never its host or query (conventions §5).

        Raises:
            RateLimitError: The quota is expected back later than 30 s from now;
                ``retry_after`` is the wait, and the message says that nothing was sent and
                when the quota is expected back.
        """
        if _outside(request):
            return
        await self._pause(request)

    def install(self, config: ClientConfig) -> ClientConfig:
        """``config`` with this policy's ``before_request`` and ``observe`` as its hooks.

        Returns ``dataclasses.replace(config, before_request=self.before_request,
        observe=self.observe)``; ``config`` itself is unchanged, and nothing is read from
        it: the pause's bound is 30 s, whatever the config's retry policy. Hooks
        the config had are replaced, so a source that needs hooks of its own as well
        composes them with the policy's itself; installing the policy again changes
        nothing.

        Args:
            config: The source's client configuration.
        """
        return dataclasses.replace(config, before_request=self.before_request, observe=self.observe)

    async def _pause(self, request: httpx.Request) -> None:
        """Wait out a spent quota within 30 s; beyond that, raise without sending."""
        snapshot = self.snapshot()
        wait = self._wait_left(snapshot)
        if snapshot is None or snapshot.resumes_at is None or wait is None:
            return
        where = f"{request.method} {request.url.path}"
        if wait > _PAUSE_CAP:
            raise RateLimitError(
                f"quota spent ({snapshot.describe()}); nothing was sent for "
                f"{where}: the quota is expected back at {_utc(snapshot.resumes_at)}, later "
                f"than a call waits ({_PAUSE_CAP:g} s)",
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

    def _wait_left(self, snapshot: QuotaSnapshot | None) -> float | None:
        """Seconds from the policy's clock until ``snapshot``'s spent quota is back.

        ``None`` while requests remain or once the quota is expected back already.
        """
        if snapshot is None or snapshot.resumes_at is None:
            return None
        wait = (snapshot.resumes_at - self._clock()).total_seconds()
        return wait if wait > 0 else None

    def _cut(self, wait: float) -> float:
        """``wait`` within ``[0, window]``: no refusal outlives one window, no date overflows."""
        if math.isnan(wait):
            raise ValueError("a wait is a number of seconds, not NaN")
        return min(max(wait, 0.0), self.window)

    def _wait(self, response: httpx.Response, now: datetime) -> float:
        """Seconds until a spent quota is back: a 429's ``Retry-After``, else ``window``.

        A ``Retry-After`` is cut to ``window``: a value no upstream means (10**12 s)
        neither refuses for decades nor overflows a date.
        """
        if response.status_code == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"), now=now)
            if retry_after is not None:
                return min(retry_after, self.window)
        return self.window
