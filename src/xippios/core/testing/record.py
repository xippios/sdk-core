"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It goes through the
real client, so retries, rate limits and authentication behave as in production, and
error responses are recorded too rather than raised. The exchange is scrubbed in memory
and written once (``Scrub``).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from xippios.core._loop import sync
from xippios.core.client import AsyncClient, Params, RetryPolicy, Timeouts
from xippios.core.testing.fixtures import Fixture, write_fixture
from xippios.core.testing.scrub import Scrub

__all__ = ["record", "record_sync"]


async def record(
    client: AsyncClient,
    path: str,
    fixture: Path,
    *,
    method: str = "GET",
    params: Params = None,
    json: Any = None,
    data: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    scrub: Scrub | None = None,
    retry: RetryPolicy | None = None,
    timeouts: Timeouts | None = None,
) -> Fixture:
    """Perform one live request and write the scrubbed exchange to ``fixture``.

    With ``retry`` or ``timeouts`` the request goes through ``client.derive(...)``,
    which shares the client's auth, rate limiter and cache and is closed afterwards;
    otherwise through ``client`` itself. ``derive`` returns a plain ``AsyncClient``: the
    request logic of a subclass of ``AsyncClient`` is not carried over, so a source
    that overrides ``request`` records without ``retry`` and ``timeouts``.

    A refusal writes nothing. One raised after the request was sent (a binary body, or
    the verify step finding the original host or a secret value) comes after upstream
    has answered: a write may have been applied all the same.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``.
        fixture: Destination file, usually from ``fixture_path``.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
        data: Form body for write methods, sent form-encoded, e.g. ``{"id": 4}``.
        headers: Extra headers for this request only.
        scrub: What to remove besides credentials, e.g.
            ``Scrub(host="demo.example.test", secrets=[tenant])``; ``None`` is
            ``Scrub()``.
        retry: Retry policy for this recording, e.g. ``RetryPolicy(max_attempts=1)``;
            ``None`` keeps the client's.
        timeouts: Timeouts for this recording, e.g. ``Timeouts(read=300.0)``; ``None``
            keeps the client's.

    Raises:
        ValueError: Both ``json`` and ``data``, before anything is sent. After the
            request: a request or response body that is not UTF-8 text without
            ``Scrub(allow_binary=True)``; the verify step finding the original host
            ("request host") or a secret value ("secret value") left by the scrub; a
            ``Scrub.host`` that is the request's own host.
    """
    if retry is None and timeouts is None:
        response = await client.request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            headers=headers,
            raise_on_error=False,
        )
    else:
        async with client.derive(retry=retry, timeouts=timeouts) as derived:
            response = await derived.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                headers=headers,
                raise_on_error=False,
            )
    return write_fixture(response, fixture, scrub=scrub)


record_sync = sync(record)
