"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It sends one request
through the source's client, its base URL, authentication, rate limit and hooks as in
production, and records the answer, an error response included, rather than raising it.
A recording is one live exchange: never retried and never answered from the cache, so a
5xx spends no second request on an upstream that counts a quota or bills a call
(ADR-0015, amendment 2026-11-18 (f)). The body is read up to a bound
(``MAX_READ_BYTES``), and the exchange is scrubbed in memory and written once
(``Scrub``).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal

import httpx

from xippios.core._loop import sync
from xippios.core.client import AsyncClient
from xippios.core.client._core import _CLIENT_AUTH, Params, _ClientAuth
from xippios.core.testing.fixtures import (
    Fixture,
    _check_cut,
    fixture_from_response,
    write_fixture,
)
from xippios.core.testing.scrub import Scrub

__all__ = ["MAX_READ_BYTES", "record", "record_sync"]

MAX_READ_BYTES: Final = 32 * 1024 * 1024
"""The most bytes of a body a recording reads by default, 32 MiB.

Four times the largest body a source records whole (sdk-usda-gats, 7.6 MB), and a
fifth of the unfiltered Eurostat dataset upstream may answer at once, 145 MB
(https://github.com/xippios/sdk-core/issues/62; ADR-0019, amendment 2026-11-18 (e)).
"""


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
    array_key: str | None = None,
    keep: Literal["first", "last"] = "first",
    max_read_bytes: int | None = MAX_READ_BYTES,
) -> Fixture:
    """Send one live request through ``client`` and write the scrubbed exchange.

    The request is sent once, whatever ``client.config.retry`` says, and never answered
    from the cache nor stored in it: a 429 or a 5xx is recorded as it came, so a
    recording needs no client of its own (ADR-0015, amendment 2026-11-18 (f)). The
    client's base URL, timeouts, rate limit, ``before_request`` and ``observe`` apply as
    for any request. The file is laid out as ``write_fixture`` writes it, without the
    response headers that only identify a request (``REQUEST_ID_HEADERS``).

    A refusal writes nothing. One raised after the request was sent (a body over
    ``max_read_bytes``, a binary body, a body ``max_bytes`` cannot cut, or the verify
    step finding a secret value) comes after upstream has answered: a write may have
    been applied all the same.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``.
        fixture: Destination file, usually from ``fixture_path``.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
        data: Form body for write methods, sent form-encoded, e.g. ``{"id": 4}``.
        headers: Extra headers for this request only.
        scrub: What to remove besides credentials, e.g. ``Scrub(secrets=[tenant])``, or
            a login answer's tokens with ``Scrub(response_secrets=...)``; ``None`` is
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
        array_key: The top-level key of a JSON object whose array ``max_bytes`` cuts,
            the rest of the object kept as upstream wrote it, e.g. ``"data"`` for
            ``{"data": [...]}``. ``None`` cuts a body that is an array.
        keep: ``"first"`` keeps an array's first whole elements, ``"last"`` its last,
            for a list ordered oldest first.
        max_read_bytes: The most bytes of the response body to read, as decoded, the
            measure of ``original_bytes``: past it the reading stops, the rest of the
            body is never fetched, and the recording raises, so an answer far larger
            than expected costs neither its download nor the memory to hold it
            (ADR-0019, amendment 2026-11-18 (e)). ``MAX_READ_BYTES``, 32 MiB, by default;
            ``None`` reads the body whole.

    Raises:
        ValueError: Both ``json`` and ``data``, ``max_bytes`` or ``max_read_bytes``
            below 1, ``keep`` neither ``"first"`` nor ``"last"``, or ``array_key`` or
            ``keep="last"`` without ``max_bytes``, before anything is sent. After the
            request: a body over ``max_read_bytes``, the message naming the request's
            method and path and the bound; a request or response body that is not UTF-8
            text without ``Scrub(allow_binary=True)``; a value ``Scrub.response_secrets``
            returned empty; the verify step finding a secret value left by the scrub; a
            body ``max_bytes`` cannot cut (a JSON object without ``array_key``, XML, ZIP,
            XLSX, gzip, XLS, or not UTF-8 text: record a small real answer or sample
            instead).
        TypeError: ``Scrub.response_secrets`` returned one string, or a value that is no
            string, after the request.
        XippiosError: ``before_request`` refused the request (a ``QuotaPolicy``'s
            ``RateLimitError``), or ``TransportError`` for a failure in transit.
    """
    _check_cut(max_bytes, array_key, keep)
    if max_read_bytes is not None and max_read_bytes < 1:
        raise ValueError("max_read_bytes must be at least 1")
    response = await client._send_once(
        method,
        path,
        params=params,
        json=json,
        data=data,
        headers=headers,
        auth=auth,
        max_read_bytes=max_read_bytes,
    )
    recorded = fixture_from_response(
        response, scrub=scrub, max_bytes=max_bytes, array_key=array_key, keep=keep
    )
    return write_fixture(recorded, fixture)


record_sync = sync(record)
