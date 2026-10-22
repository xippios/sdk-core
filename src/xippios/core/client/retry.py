"""Retry loop: exponential backoff with jitter on 429 and 5xx, ``Retry-After`` honoured."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx

from xippios.core.client.config import RetryPolicy
from xippios.core.errors import error_from_exception, parse_retry_after

__all__ = ["IDEMPOTENT_METHODS", "is_retryable_status", "send_with_retries"]

logger = logging.getLogger("xippios.core.client")

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_retryable_status(status: int) -> bool:
    """True for 429 and every 5xx; never for another 4xx (conventions §6)."""
    return status == 429 or 500 <= status < 600


async def send_with_retries(
    send: Callable[[], Awaitable[httpx.Response]],
    *,
    policy: RetryPolicy,
    method: str,
    source: str | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    """Call ``send`` until it yields a non-retryable response or the policy gives up.

    Returns the last response; classifying it is the caller's job. Transport failures
    are retried for idempotent methods when the policy allows, and otherwise raised as
    ``TransportError``.

    Args:
        send: Performs one attempt and returns the response.
        policy: Attempts, backoff and jitter.
        method: HTTP method, used to decide whether transport failures are retried.
        source: Source slug for errors.
        sleep: Async sleep, replaceable in tests.
    """
    method = method.upper()
    attempt = 0
    while True:
        attempt += 1
        try:
            response = await send()
        except httpx.RequestError as exc:
            retryable = policy.retry_transport_errors and method in IDEMPOTENT_METHODS
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
        if not is_retryable_status(response.status_code):
            return response
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
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
