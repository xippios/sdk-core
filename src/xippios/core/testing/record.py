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
from xippios.core.client import AsyncClient
from xippios.core.client._core import _CLIENT_AUTH, Params, _ClientAuth
from xippios.core.testing.fixtures import Fixture, _write, fixture_from_response
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
    max_bytes: int | None = None,
) -> Fixture:
    """Perform one live request through ``client`` and write the scrubbed exchange.

    The client's own retry policy and timeouts apply. A recording that should spend no
    retry on a 5xx, or needs a longer read timeout, records through a client built for
    it, e.g. on ``dataclasses.replace(config, retry=RetryPolicy(max_attempts=1))``.

    A refusal writes nothing. One raised after the request was sent (a binary body, a
    body ``max_bytes`` cannot cut, or the verify step finding the original host or a
    secret value) comes after upstream has answered: a write may have been applied all
    the same.

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
        max_bytes: Keep at most this many bytes of a large response body, e.g.
            ``80_000``: a JSON array keeps its first whole elements, a text its first
            bytes, and the fixture is marked ``truncated`` with the whole body's size,
            sha256 and, for an array, length (ADR-0019, decision 5; see
            ``fixture_from_response``). It bounds the body, not the file, which escapes
            the body as a JSON string, text outside ASCII up to three times as long:
            ``80_000`` keeps a file under the 256 KiB cap. ``None`` keeps it whole.

    Raises:
        ValueError: Both ``json`` and ``data``, or ``max_bytes`` below 1, before anything
            is sent. After the request: a request or response body that is not UTF-8
            text without ``Scrub(allow_binary=True)``; the verify step finding the
            original host ("request host") or a secret value ("secret value") left by
            the scrub; a ``Scrub.host`` that is the request's own host; a body
            ``max_bytes`` cannot cut (a JSON object, XML, ZIP, XLSX, gzip, XLS, or not
            UTF-8 text: record a small real answer or sample instead).
    """
    if max_bytes is not None and max_bytes < 1:
        raise ValueError("max_bytes must be at least 1")
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
    return _write(fixture_from_response(response, scrub=scrub, max_bytes=max_bytes), fixture)


record_sync = sync(record)
