"""Result caps: never hand an agent more than it can use, never truncate silently."""

import json
from typing import Any

from pydantic_core import to_jsonable_python

from xippios.core.errors import InvalidRequestError
from xippios.core.models import ResultCap

__all__ = ["cap_result"]


_DEFAULT_NOTE = "narrow the query to see the rest"
"""What a capped result tells the agent when its cap has no ``note``: no filter promised."""


def _dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _encode(text: str) -> bytes:
    # surrogatepass: a lone surrogate, which json.loads lets through, counts as its three
    # bytes instead of raising out of the tool.
    return text.encode("utf-8", "surrogatepass")


def _size(text: str) -> int:
    """The length of ``text`` in UTF-8 bytes, the unit of ``max_bytes``."""
    return len(_encode(text))


def _head(text: str, size: int) -> str:
    """The longest start of ``text`` that is at most ``size`` UTF-8 bytes, no character cut."""
    data = _encode(text)
    if len(data) <= size:
        return text
    end = size
    while end > 0 and (data[end] & 0xC0) == 0x80:  # a continuation byte: back to a boundary
        end -= 1
    return data[:end].decode("utf-8", "surrogatepass")


def _how(cap: ResultCap) -> str:
    return _DEFAULT_NOTE if cap.note is None else cap.note


def _window(total: int, offset: int, cap: ResultCap) -> tuple[int, int]:
    """The rows ``[low, high)`` of the task's that a page from ``offset`` may show.

    ``offset`` counts the rows already shown: from the first row where the cap keeps the
    first, from the last where it keeps the last.
    """
    if cap.keep == "first":
        return min(offset, total), total
    return 0, max(total - offset, 0)


def _note(
    cap: ResultCap,
    total: int,
    offset: int,
    shown: tuple[int, int],
    left: int,
    start: int | None,
    *,
    name_row: bool = True,
) -> str:
    """The note of a page that shows the rows ``shown``, ``(first, end)``, of ``total``.

    ``left`` is how many rows ``offset`` leaves to show, ``start`` the integer ``start``
    that ``meta.request`` records, if any. The first page of a cap that keeps
    the first rows reads as it did before paging, ``showing <n> of <total> rows``; every
    other page names its rows, ``showing rows <a> to <b> of <total>``, so a caller tells
    a page from a whole answer by the note alone.
    """
    first, end = shown
    count = end - first
    if left == 0:
        return f"showing 0 of {total} rows; offset {offset} leaves no row to show"
    plain = cap.keep == "first" and offset == 0
    if count and not plain:
        counts = f"showing rows {first + 1} to {end} of {total}"
    else:
        counts = f"showing {count} of {total} rows"
    rest = left - count  # the rows past the page, in the direction the cap reads
    if rest == 0:
        return counts  # the last page: nothing to continue with
    counts += f" (cap: {cap.max_rows} rows or {cap.max_bytes} bytes)"
    if count == 0:
        # No resume offset: it would name the start just used, and a tool that follows
        # the note would ask for the same row again.
        if not name_row:
            return f"{counts}; {_how(cap)}"
        if not plain:
            row = f"row {first + 1 if cap.keep == 'first' else end}"
        elif start is None or cap.paged:
            row = "the first row"
        else:
            row = f"the row at offset {start}"
        past = f"; continue past it with offset={offset + 1}" if cap.paged and rest > 1 else ""
        return f"{counts}; {row} alone exceeds the byte cap; {_how(cap)}{past}"
    if cap.paged:
        more = f"; continue with offset={offset + count}"
    elif plain and start is not None:
        more = f"; resume with start={start + count}"
    else:
        more = ""
    return f"{counts}; {_how(cap)}{more}"


def _start(payload: dict[str, Any]) -> int | None:
    """The integer ``start`` the result's ``meta.request`` records, for the resume hint."""
    meta = payload.get("meta")
    request = meta.get("request") if isinstance(meta, dict) else None
    start = request.get("start") if isinstance(request, dict) else None
    return start if isinstance(start, int) and not isinstance(start, bool) else None


def _rows(payload: Any) -> tuple[list[Any], str | None] | None:
    """The rows a result holds, and the field of its model that holds them.

    ``data`` that is a list is the rows themselves, the field ``None``. ``data`` that is
    an object, a model as dumped, holds rows when one of its fields, and only one, is a
    list: that list, under that field's name. A field left ``None`` is no list. Anything
    else holds no rows.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        lists = [name for name, item in data.items() if isinstance(item, list)]
        if len(lists) == 1:
            return data[lists[0]], lists[0]
    return None


def cap_result(value: Any, cap: ResultCap | None = None, *, offset: int = 0) -> str:
    """Serialise a task result as compact JSON text within ``cap``.

    A ``Result`` whose ``data`` is a list, or a bare list, is cut to the cap and gains a
    ``note``: ``"showing <shown> of <total> rows (cap: <max_rows> rows or <max_bytes>
    bytes); "`` and then the cap's ``note``, or ``"narrow the query to see the rest"``;
    where ``meta.request`` records an integer ``start``, an offset-paged task's, the note
    ends ``"; resume with start=<start + shown>"``. When it shows no row, the note names
    no resume offset: where zero rows with the note fit ``max_bytes``, the counts are
    followed by ``"the first row alone exceeds the byte cap; "``, or by ``"the row at
    offset <start> alone exceeds the byte cap; "`` where ``start`` is recorded, and then
    the cap's ``note``; where they do not, by the cap's ``note`` alone.
    A bare list is wrapped as ``{"data": [...]}`` so the shape is the same either way.

    A paged cap (``ResultCap(paged=True)``, ADR-0047) shows the rows from ``offset``, the
    rows already shown, and its note ends ``"; continue with offset=<offset + shown>"``
    in place of the ``start`` resume while rows are left. A page past the first names
    its rows, ``"showing rows <a> to <b> of <total>"``, the last page with nothing after
    it, so a caller tells a page from a whole answer by the note: an answer without one
    is whole. A row that alone exceeds the byte cap is named by its place, ``"row <n>"``,
    and passed with ``"; continue past it with offset=<offset + 1>"`` where rows follow
    it. An ``offset`` that leaves no row answers no row, ``"showing 0 of <total> rows;
    offset <offset> leaves no row to show"``. A cap that keeps the last rows
    (``keep="last"``) shows the newest rows of a series ordered oldest first, in the
    task's order, its ``offset`` counted from the last row; it names its rows from its
    first page on and never a ``start`` resume.

    A ``Result`` whose ``data`` is a model that holds one list, and no other field a list,
    is cut the same way once its text exceeds the byte cap: its rows are the list's
    items, cut to both bounds, and its other fields are kept whole beside them. Within
    the byte cap it comes back whole, however many rows it holds: a model is one
    upstream answer, often a page whose cursor follows its last row.

    Any other value that exceeds the byte cap, and a model whose other fields alone
    exceed it, is replaced by a note, ``"result is <n> bytes, over the cap of
    <max_bytes>; "`` and the same text, and a preview of its first ``max_bytes`` bytes.
    Bytes are those of the JSON text encoded as UTF-8.

    ``max_bytes`` is a soft bound. A list keeps the most rows whose text, envelope and
    note included, fits it; when not even zero rows fit, a tiny bound or a long note,
    the result is zero rows plus the note, over the bound. A preview is ``max_bytes``
    bytes of the text, and the note and the preview's JSON escaping come on top. Either
    way the result stays bounded and says what it left out; nothing is cut silently
    (conventions §8).

    Args:
        value: What the task function returned; pydantic models are dumped in JSON mode.
        cap: Limits; the defaults are the family's.
        offset: The rows already shown, for a paged cap; the MCP adapter passes the
            tool's argument. 0 shows the first page.

    Raises:
        ValueError: ``offset`` is negative, or above 0 without a paged cap.
        InvalidRequestError: ``offset`` is above 0 and the result holds no rows to
            continue; the MCP adapter answers it as the family's error text.
    """
    cap = cap or ResultCap()
    if offset < 0:
        raise ValueError(f"offset must not be negative, got {offset}")
    if offset and not cap.paged:
        raise ValueError("offset needs a paged cap, ResultCap(paged=True)")
    payload = to_jsonable_python(value)
    if isinstance(payload, list):
        payload = {"data": payload}
    rows, field = _rows(payload) or (None, None)
    if rows is None and offset:
        raise InvalidRequestError(
            "offset: this answer holds no list of rows to continue; call the tool without offset"
        )
    if rows is not None and field is None:
        return _cut(payload, rows, None, cap, offset)  # a list: the row bound applies at any size
    text = _dumps(payload)
    if rows is None:
        return text if _size(text) <= cap.max_bytes else _preview(text, cap)
    page = _render(payload, rows, field, len(rows), cap, offset)  # every row offset leaves
    if _size(page) <= cap.max_bytes:
        return page  # a model within the byte cap: past the row bound, as one upstream answer
    if _size(_render(payload, rows, field, 0, cap, offset)) <= cap.max_bytes:
        return _cut(payload, rows, field, cap, offset)  # a model past the byte cap
    return _preview(text, cap)


def _preview(text: str, cap: ResultCap) -> str:
    size = _size(text)
    return _dumps(
        {
            "note": f"result is {size} bytes, over the cap of {cap.max_bytes}; {_how(cap)}",
            "preview": _head(text, cap.max_bytes),
        }
    )


def _cut(
    payload: dict[str, Any], rows: list[Any], field: str | None, cap: ResultCap, offset: int
) -> str:
    """The most rows, at most ``max_rows``, whose text with the note fits ``max_bytes``.

    The rows are those ``offset`` leaves, taken from the end the cap keeps.
    """
    first, end = _window(len(rows), offset, cap)
    high = min(end - first, cap.max_rows)
    text = _render(payload, rows, field, high, cap, offset)
    if _size(text) <= cap.max_bytes:
        return text
    low = 0
    while high - low > 1:
        mid = (low + high) // 2
        if _size(_render(payload, rows, field, mid, cap, offset)) <= cap.max_bytes:
            low = mid
        else:
            high = mid
    text = _render(payload, rows, field, low, cap, offset)
    if low == 0 and _size(text) > cap.max_bytes:
        # Not even zero rows fit, a tiny bound or a long note: no row is to blame.
        return _render(payload, rows, field, 0, cap, offset, name_row=False)
    return text


def _render(
    payload: dict[str, Any],
    rows: list[Any],
    field: str | None,
    shown: int,
    cap: ResultCap,
    offset: int = 0,
    *,
    name_row: bool = True,
) -> str:
    """The result with ``shown`` of its rows, in ``data`` or in its model's ``field``.

    The rows are those ``offset`` leaves, the first of them or, where the cap keeps the
    last, the last, in the task's order. ``name_row`` says whether a note that shows no
    row blames the next row for it.
    """
    total = len(rows)
    low, high = _window(total, offset, cap)
    shown = min(shown, high - low)
    if offset == 0 and shown == total:
        return _dumps(payload)
    first, end = (low, low + shown) if cap.keep == "first" else (high - shown, high)
    kept = rows[first:end]
    data = kept if field is None else {**payload["data"], field: kept}
    start = _start(payload)
    note = _note(cap, total, offset, (first, end), high - low, start, name_row=name_row)
    return _dumps({**payload, "data": data, "note": note})
