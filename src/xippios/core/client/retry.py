"""Retry loop: exponential backoff with jitter, ``Retry-After`` honoured (ADR-0011).

A read, a request of ``IDEMPOTENT_METHODS``, is retried after a 429, a 5xx or a transport
failure. Every other method is a write and is sent once, after a 429 too: a write that met a
5xx or a transport failure may already have been applied, and a repeat can apply it twice
(ADR-0011, amendment 2026-11-24). Before a 429 or 5xx is retried, the source's ``classify``
is asked: its ``RateLimitError`` sets the wait, an ``UpstreamError`` for a 5xx changes
nothing, any other error stops the retries (ADR-0037).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from xippios.core.client.config import RetryPolicy
from xippios.core.errors import (
    IDEMPOTENT_METHODS,
    RateLimitError,
    UpstreamError,
    XippiosError,
    _failed_in_transit,
    error_from_exception,
    parse_retry_after,
)

__all__ = ["is_retryable_status", "send_with_retries"]

logger = logging.getLogger("xippios.core.client")


def is_retryable_status(status: int) -> bool:
    """True for 429 and every 5xx; never for another 4xx (conventions §6).

    Whether it is retried depends on the method too: ``send_with_retries`` repeats a read alone.
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

    Returns the last response; raising for it is the caller's job. A read, a ``method`` of
    ``IDEMPOTENT_METHODS``, is retried after a 429, a 5xx or a transport failure, as the
    policy allows. Any other method is sent once and its response returned, whatever its
    status and whatever the policy allows (ADR-0011, amendment 2026-11-24). A transport
    failure that is not retried is raised as ``TransportError``, a write's saying that the
    request was sent once and that its outcome is unknown, or that nothing was sent where the
    connection failed.

    Before a 429 or 5xx is retried, ``classify`` is called with it, when given
    (ADR-0037). A ``RateLimitError`` it returns sets the wait: its ``retry_after``, else
    the ``Retry-After`` header's, goes to ``policy.delay``, so a wait beyond
    ``policy.backoff_max`` stops the retries. An ``UpstreamError`` for a 5xx, the
    default mapping restated (with a cleaner message, say), and ``None`` keep the rule
    above. Any other error it returns stops them at once: the source says the answer is
    one that waiting will not cure, an ``AuthError`` or an ``InvalidRequestError`` for
    instance. ``classify`` is called at most once per attempt.

    Args:
        send: Performs one attempt and returns the response.
        policy: The attempts, backoff and jitter of a read.
        method: HTTP method, which decides whether anything is retried.
        source: Source slug for errors.
        sleep: Async sleep, replaceable in tests.
        classify: The source's error mapping (``ClientConfig.classify``), consulted
            before a 429 or 5xx is retried; ``None`` retries on the status alone.
    """
    method = method.upper()
    if method not in IDEMPOTENT_METHODS:
        # A write that met a 5xx or a transport failure may have been applied, and a repeat
        # can apply it twice, a booking say; no keyword or mark lets a call ask for one.
        try:
            return await send()
        except httpx.RequestError as exc:
            raise _failed_in_transit(exc, method=method, source=source) from exc
    attempt = 0
    while True:
        attempt += 1
        try:
            response = await send()
        except httpx.RequestError as exc:
            delay = policy.delay(attempt)
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
        if not is_retryable_status(status):
            return response
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        classified = classify(response) if classify is not None else None
        if isinstance(classified, RateLimitError):
            if classified.retry_after is not None:
                retry_after = classified.retry_after
        elif classified is not None and not (
            isinstance(classified, UpstreamError) and status >= 500
        ):
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
