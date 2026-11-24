"""What ``AsyncClient.download`` returns, and the streaming it is built from (ADR-0040).

A file is streamed to disk, never held in memory: the body goes chunk by chunk into a
temporary file beside the destination, which is renamed when the body is complete. An
error answer is read up to ``BODY_LIMIT`` bytes, enough for the error's text, and no
further.
"""

import email.message
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from xippios.core.client.cache import strip_wire_headers
from xippios.core.errors import _UNSENT, BODY_LIMIT, InvalidRequestError, XippiosError

__all__ = ["Downloaded", "check_dest"]


def check_dest(dest: str | os.PathLike[str], *, source: str | None = None) -> Path:
    """``dest`` as a ``Path``, once it names a file in a directory that exists.

    ``AsyncClient.download`` checks its ``dest`` with it before anything is sent. A task
    that sends a request of its own before its download, a listing that finds the file
    say, calls it before that first request, so a bad ``dest`` sends nothing and its
    refusal's ``Nothing was sent.`` is true (conventions §5; ADR-0045, amendment
    2026-11-24)::

        target = check_dest(dest, source="example")  # before the listing's request
        listing = await client.get_answer("/files")
        got = await client.download(listing.payload["url"], target)

    Args:
        dest: The file to write, e.g. ``Path("report.pdf")``, in a directory that exists.
        source: Source slug the refusal carries, e.g. ``"example"``.

    Returns:
        ``Path(dest)``.

    Raises:
        InvalidRequestError: ``dest`` is a directory, or its directory does not exist,
            a bad argument (conventions §5), the refusal saying that nothing was sent.
    """
    target = Path(dest)
    if target.is_dir():
        raise InvalidRequestError(
            f"dest is a directory; name the file to write. {_UNSENT}", source=source
        )
    if not target.parent.is_dir():
        raise InvalidRequestError(
            f"dest's directory does not exist; create it first. {_UNSENT}", source=source
        )
    return target


@dataclass(frozen=True, slots=True, kw_only=True)
class Downloaded:
    """A file ``AsyncClient.download`` wrote, with what upstream said about it.

    A bulk task returns it as ``Result[Downloaded]`` (conventions §2, ADR-0040); the
    adapters never serve it.

    Attributes:
        path: The file written, ``dest`` as given to ``download``, with mode ``0600``,
            its owner's alone, as ``tempfile.mkstemp`` creates it.
        bytes: Its size in bytes, as written: the body with any ``Content-Encoding``
            undone, a ``.gz`` file served as ``application/gzip`` left compressed.
        content_type: The ``Content-Type`` header as sent, e.g. ``"text/csv;
            charset=utf-8"``; ``None`` when upstream sent none.
        filename: The file name from ``Content-Disposition`` (``filename*=`` decoded,
            else ``filename=``), upstream's text and not a safe path; ``None`` when the
            header or the name is absent.
        etag: The ``ETag`` header as sent, quotes included; ``None`` when absent.
        last_modified: The ``Last-Modified`` header's text as sent, e.g.
            ``"Tue, 27 Oct 2026 08:00:00 GMT"``, not parsed; ``None`` when absent.
        retrieved_at: When the file was complete, timezone-aware UTC.
    """

    path: Path
    bytes: int
    content_type: str | None
    filename: str | None
    etag: str | None
    last_modified: str | None
    retrieved_at: datetime


def content_disposition_filename(value: str | None) -> str | None:
    """The file name a ``Content-Disposition`` header gives, or ``None``.

    RFC 6266: ``filename*`` (RFC 5987, ``UTF-8''...``) wins over ``filename``.
    """
    if not value:
        return None
    message = email.message.Message()
    message["content-disposition"] = value
    return message.get_filename() or None


async def head_of(response: httpx.Response) -> httpx.Response:
    """``response``'s status and headers with at most ``BODY_LIMIT`` bytes of its body.

    For an error answer to a download: enough body for the error's text and for
    ``classify``, never the whole stream. ``response`` is left for the caller to close.
    """
    head = bytearray()
    async for chunk in response.aiter_bytes():
        head += chunk
        if len(head) >= BODY_LIMIT:
            break
    return httpx.Response(
        response.status_code,
        headers=strip_wire_headers(response.headers.multi_items()),
        content=bytes(head[:BODY_LIMIT]),
        request=response.request,
    )


async def stream_to(response: httpx.Response, path: Path) -> int:
    """Write ``response``'s body to ``path``, truncating it first; the bytes written."""
    written = 0
    with path.open("wb") as handle:
        async for chunk in response.aiter_bytes():
            handle.write(chunk)
            written += len(chunk)
    return written


def unread_is_none(
    classify: Callable[[httpx.Response], XippiosError | None],
) -> Callable[[httpx.Response], XippiosError | None]:
    """``classify``, counting a success it could not read the body of as ``None``.

    A download's success goes to the file unread, so ``classify`` sees its status and
    headers only; one that reads the body meets ``httpx.ResponseNotRead``, which says
    nothing about the answer.
    """

    def classify_headers(response: httpx.Response) -> XippiosError | None:
        try:
            return classify(response)
        except httpx.ResponseNotRead:
            return None

    return classify_headers
