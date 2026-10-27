"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It goes through the
real client, so retries, rate limits and authentication behave as in production, and
error responses are recorded too rather than raised. The exchange is scrubbed in memory
and written once (``Scrub``).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from xippios.core._loop import sync
from xippios.core.client import AsyncClient, Params
from xippios.core.client._core import _CLIENT_AUTH, _ClientAuth
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
    auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
) -> Fixture:
    """Perform one live request through ``client`` and write the scrubbed exchange.

    The client's own retry policy and timeouts apply. A recording that should spend no
    retry on a 5xx, or needs a longer read timeout, records through a client built for
    it, e.g. on ``dataclasses.replace(config, retry=RetryPolicy(max_attempts=1))``.

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
        auth: Credentials for this recording only, as for ``AsyncClient.request``:
            ``None`` records a keyless endpoint without the client's key, an
            ``httpx.Auth`` replaces it; the default sends the client's.

    Raises:
        ValueError: Both ``json`` and ``data``, before anything is sent. After the
            request: a request or response body that is not UTF-8 text without
            ``Scrub(allow_binary=True)``; the verify step finding the original host
            ("request host") or a secret value ("secret value") left by the scrub; a
            ``Scrub.host`` that is the request's own host.
    """
    response = await client.request(
        method,
        path,
        params=params,
        json=json,
        data=data,
        headers=headers,
        raise_on_error=False,
        auth=auth,
    )
    return write_fixture(response, fixture, scrub=scrub)


record_sync = sync(record)
