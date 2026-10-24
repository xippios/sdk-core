"""Retry loop: exponential backoff with jitter, ``Retry-After`` honoured (ADR-0011).

A 429 is retried for every method: upstream refused it before acting. A 5xx and a
transport failure are retried for idempotent methods only, unless the policy sets
``retry_non_idempotent``: a write that met them may already have been applied. Before a
429 or 5xx is retried, the source's ``classify`` is asked: its ``RateLimitError`` sets
the wait, any other error stops the retries (ADR-0015).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from xippios.core.client.config import RetryPolicy
from xippios.core.errors import (
    RateLimitError,
    XippiosError,
    error_from_exception,
    parse_retry_after,
)

__all__ = ["IDEMPOTENT_METHODS", "is_retryable_status", "send_with_retries"]

logger = logging.getLogger("xippios.core.client")

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_retryable_status(status: int) -> bool:
    """True for 429 and every 5xx; never for another 4xx (conventions §6).

    Whether a 5xx is retried also depends on the method; ``send_with_retries`` decides.
    """
    return status == 429 or 500 <= status < 600


async def send_with_retries(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    policy: RetryPolicy,
    method: str,
    source: str | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    classify: Callable[[httpx.Response], XippiosError | None] | None = None,
) -> httpx.Response:
    """Call ``send`` until it yields a non-retryable response or the policy gives up.

    Returns the last response; raising for it is the caller's job. A 429 is retried for
    every method. A 5xx is retried, and a transport failure too when
    ``policy.retry_transport_errors`` is set, for ``IDEMPOTENT_METHODS`` only, unless
    ``policy.retry_non_idempotent`` lifts that restriction (ADR-0011). A transport
    failure that is not retried is raised as ``TransportError``.

    Before a 429 or 5xx is retried, ``classify`` is called with it, when given
    (ADR-0015). A ``RateLimitError`` it returns sets the wait: its ``retry_after``, else
    the ``Retry-After`` header's, goes to ``policy.delay``, so a wait beyond
    ``policy.backoff_max`` stops the retries. Any other error it returns stops them at
    once: the source says the answer is one that waiting will not cure. ``None`` keeps
    the rule above. ``classify`` is called at most once per attempt.

    Args:
        send: Performs one attempt and returns the response.
        policy: Attempts, backoff, jitter and what is retried.
        method: HTTP method, used to decide whether a 5xx or a transport failure is
            retried.
        source: Source slug for errors.
        sleep: Async sleep, replaceable in tests.
        classify: The source's error mapping (``ClientConfig.classify``), consulted
            before a 429 or 5xx is retried; ``None`` retries on the status alone.
    """
    method = method.upper()
    # A write that met a 5xx or a transport failure may have been applied; repeating it
    # can apply it twice (a duplicate booking, sdk-cashctrl). A 429 was refused unapplied.
    may_repeat = method in IDEMPOTENT_METHODS or policy.retry_non_idempotent
    attempt = 0
    while True:
        attempt += 1
        try:
            response = await send()
        except httpx.RequestError as exc:
            retryable = policy.retry_transport_errors and may_repeat
            delay = policy.delay(attempt) if retryable else None
            if delay is None:
                raise error_from_exception(exc, source=source) from exc
            logger.debug(
                "%s: retrying %s after %s (attempt %d/%d) in %.2fs",
                source,
                method,
                type(exc).__name__,
                attempt,
                policy.max_attempts,
                delay,
            )
            await sleep(delay)
            continue
        status = response.status_code
        if not is_retryable_status(status) or (status != 429 and not may_repeat):
            return response
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        classified = classify(response) if classify is not None else None
        if isinstance(classified, RateLimitError):
            if classified.retry_after is not None:
                retry_after = classified.retry_after
        elif classified is not None:
            return response
        delay = policy.delay(attempt, retry_after=retry_after)
        if delay is None:
            return response
        await response.aclose()
        logger.debug(
            "%s: retrying %s after HTTP %d (attempt %d/%d) in %.2fs",
            source,
            method,
            response.status_code,
            attempt,
            policy.max_attempts,
            delay,
        )
        await sleep(delay)
