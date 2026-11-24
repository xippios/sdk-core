"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It sends one request
through the source's client, its base URL, authentication, rate limit and hooks as in
production, and records the answer, an error response included, rather than raising it.
A recording is one live exchange: never retried and never answered from the cache, so a
5xx spends no second request on an upstream that counts a quota or bills a call
(ADR-0037, decision 6). The body is read up to a bound (``MAX_READ_BYTES``), and the
exchange is scrubbed in memory, rewritten by the source's own step where it passes one,
checked and written once (``Scrub``, ``rewrite=``; ADR-0066). ``send_once`` is that one
request without the write, for a source that needs the answer itself; an answer of a 1xx
or a 3xx status, no final answer of its operation, is refused on every path.

``record`` and ``send_once`` are sync functions, as a task's sync form is, and a caller on
an event loop awaits ``record.async_fn`` or ``send_once.async_fn`` (ADR-0066, decision 8).
A task of several requests is recorded by its source's own capture, built on
``fixture_from_response`` and ``write_fixture`` (decision 9).
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
    Rewrite,
    _check_cut,
    _check_rewrite,
    _refuse_interim,
    fixture_from_response,
    write_fixture,
)
from xippios.core.testing.scrub import Scrub

__all__ = ["MAX_READ_BYTES", "record", "send_once"]

MAX_READ_BYTES: Final = 32 * 1024 * 1024
"""The most bytes of a body a recording reads by default, 32 MiB.

Four times the largest body a source records whole, 7.6 MB, and a fifth of the largest
unfiltered dataset that an upstream may answer at once, 145 MB
(https://github.com/xippios/sdk-core/issues/62; ADR-0040, decision 5).
"""


@sync
async def send_once(
    client: AsyncClient,
    path: str,
    *,
    method: str = "GET",
    params: Params = None,
    json: Any = None,
    data: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    auth: httpx.Auth | _ClientAuth | None = _CLIENT_AUTH,
    max_read_bytes: int | None = MAX_READ_BYTES,
) -> httpx.Response:
    """Send a recording's one request through ``client`` and return its answer, nothing written.

    The request ``record`` sends, for a source that needs the answer itself before or
    instead of a fixture, such as the bytes it cuts a sample from or a write's answer it
    reports, and that builds the fixture with ``fixture_from_response`` (ADR-0066, decision
    3). A sync function: a caller on an event loop awaits ``send_once.async_fn`` with the
    same arguments (decision 8). It is sent once, whatever ``client.config.retry`` says,
    and never answered from the cache nor stored in it, so no recorder of one exchange
    needs a client built for one attempt; the client's base URL, timeouts, rate limit,
    ``before_request`` and ``observe`` apply as for any request (ADR-0037, decision 6).
    The answer is returned whatever its final status, a 4xx or a 5xx included, its body
    read and decoded, with the request as sent.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``, or an absolute URL on another host.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
        data: Form body for write methods, sent form-encoded, e.g. ``{"id": 4}``.
        headers: Extra headers for this request only.
        auth: Credentials for this request only, as for ``AsyncClient.request``: ``None``
            sends none, an ``httpx.Auth`` replaces the client's; the default sends the
            client's to the base URL's origin.
        max_read_bytes: The most bytes of the response body to read, as decoded:
            ``MAX_READ_BYTES``, 32 MiB, by default; ``None`` reads the body whole.

    Raises:
        ValueError: Both ``json`` and ``data``, or ``max_read_bytes`` below 1, before
            anything is sent. After the request: a body over ``max_read_bytes``, the
            message naming the method, the path and the bound; an answer of a 1xx or a 3xx
            status, which is no final answer of its operation (ADR-0066, decision 4), the
            message naming the method, the path and the status, never a header's value,
            and what to record instead. ``observe`` has seen the answer either way.
        RuntimeError: Called from the thread of core's own event loop, where
            ``send_once.async_fn`` is awaited instead.
        XippiosError: ``before_request`` refused the request (a ``QuotaPolicy``'s
            ``RateLimitError``), or ``TransportError`` for a failure in transit.
    """
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
    _refuse_interim(response)
    return response


@sync
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
    keep: Literal["first", "last"] = "first",
    max_read_bytes: int | None = MAX_READ_BYTES,
    rewrite: Rewrite | None = None,
) -> Fixture:
    """Send one live request through ``client`` and write the scrubbed exchange.

    The request is the one ``send_once`` sends: once, whatever ``client.config.retry``
    says, and never answered from the cache nor stored in it, so a 429 or a 5xx is
    recorded as it came, and a recording needs no client of its own (ADR-0037, decision
    6). The client's base URL, timeouts, rate limit, ``before_request`` and ``observe``
    apply as for any request. The order is fixed: the scrub, the source's ``rewrite``
    step, the check that no value the step replaced survives, the one write (ADR-0066,
    decisions 1 and 2). A sync function: a caller on an event loop awaits
    ``record.async_fn`` with the same arguments (decision 8). The file is laid out as
    ``write_fixture`` writes it, without the response headers that only identify a
    request (``REQUEST_ID_HEADERS``).

    A refusal writes nothing. One raised after the request was sent (a 1xx or a 3xx, a
    body over ``max_read_bytes``, a binary body, a body ``max_bytes`` cannot cut, the
    verify step finding a secret value, or the rewrite step's refusal or a value it
    replaced left in the fixture) comes after upstream has answered: a write may have
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
        max_bytes: Keep at most this many bytes of a large response body that is a JSON
            array, e.g. ``80_000``: its first whole elements are kept, and the fixture is
            marked ``truncated`` with the whole body's size, sha256 and length (ADR-0066,
            decision 12; see ``fixture_from_response``). It bounds the body, not the file,
            which escapes the body as a JSON string, text outside ASCII up to three times
            as long: ``80_000`` keeps a file under the 256 KiB cap. ``None`` keeps it whole.
        keep: ``"first"`` keeps an array's first whole elements, ``"last"`` its last,
            for a list ordered oldest first.
        max_read_bytes: The most bytes of the response body to read, as decoded, the
            measure of ``original_bytes``: past it the reading stops, the rest of the
            body is never fetched, and the recording raises, so an answer far larger
            than expected costs neither its download nor the memory to hold it
            (ADR-0040, decision 5). ``MAX_READ_BYTES``, 32 MiB, by default;
            ``None`` reads the body whole.
        rewrite: The source's own step for what it replaces beyond the secret values, a
            tenant's host or a field by key: a function of the scrubbed ``Fixture`` that
            returns it rewritten and the values it replaced, ``(fixture, [value, ...])``,
            and raises ``ValueError`` to refuse (see ``fixture_from_response``). ``None``
            rewrites nothing.

    Raises:
        ValueError: Both ``json`` and ``data``, ``max_bytes`` or ``max_read_bytes``
            below 1, ``keep`` neither ``"first"`` nor ``"last"``, or ``keep="last"``
            without ``max_bytes``, before anything is sent. After the request: an answer of
            a 1xx or a 3xx status, no final answer of its operation (ADR-0066, decision 4);
            a body over ``max_read_bytes``, the message naming the request's method and
            path and the bound; a request or response body that is not UTF-8 text without
            ``Scrub(allow_binary=True)``; a value
            ``Scrub.response_secrets`` returned empty; the verify step finding a secret
            value left by the scrub or brought back by the step; the step's refusal; a
            value the step replaced left in the URL, a header value or a body, the
            message naming the place, never the value; a body ``max_bytes`` cannot cut (one
            that is no JSON array: a JSON object, a text, XML, ZIP, XLSX, gzip, XLS, or not
            UTF-8 text: record a small real answer or sample instead).
        TypeError: ``rewrite`` is no function, before anything is sent. After the
            request: ``Scrub.response_secrets`` returned one string, or a value that is
            no string; the step returned no pair of a ``Fixture`` and its values, one
            string for its values, or a value that is no string.
        XippiosError: ``before_request`` refused the request (a ``QuotaPolicy``'s
            ``RateLimitError``), or ``TransportError`` for a failure in transit.
        RuntimeError: Called from the thread of core's own event loop, where
            ``record.async_fn`` is awaited instead.
    """
    _check_cut(max_bytes, keep)
    _check_rewrite(rewrite)
    response = await send_once.async_fn(
        client,
        path,
        method=method,
        params=params,
        json=json,
        data=data,
        headers=headers,
        auth=auth,
        max_read_bytes=max_read_bytes,
    )
    recorded = fixture_from_response(
        response, scrub=scrub, max_bytes=max_bytes, keep=keep, rewrite=rewrite
    )
    return write_fixture(recorded, fixture)
