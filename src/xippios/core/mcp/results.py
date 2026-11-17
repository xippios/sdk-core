"""Result caps: never hand an agent more than it can use, never truncate silently."""

import json
from typing import Any

from pydantic_core import to_jsonable_python

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


def _note(
    shown: int, total: int, cap: ResultCap, start: int | None, *, name_row: bool = True
) -> str:
    counts = f"showing {shown} of {total} rows (cap: {cap.max_rows} rows or {cap.max_bytes} bytes)"
    if shown == 0:
        # No resume offset: it would name the start just used, and a tool that follows
        # the note would ask for the same row again.
        if not name_row:
            return f"{counts}; {_how(cap)}"
        row = "the first row" if start is None else f"the row at offset {start}"
        return f"{counts}; {row} alone exceeds the byte cap; {_how(cap)}"
    resume = "" if start is None else f"; resume with start={start + shown}"
    return f"{counts}; {_how(cap)}{resume}"


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


def cap_result(value: Any, cap: ResultCap | None = None) -> str:
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
    """
    cap = cap or ResultCap()
    payload = to_jsonable_python(value)
    if isinstance(payload, list):
        payload = {"data": payload}
    rows, field = _rows(payload) or (None, None)
    if rows is not None and field is None:
        return _cut(payload, rows, None, cap)  # a list: the row bound applies at any size
    text = _dumps(payload)
    if _size(text) <= cap.max_bytes:
        return text
    if rows is not None and _size(_render(payload, rows, field, 0, cap)) <= cap.max_bytes:
        return _cut(payload, rows, field, cap)  # a model past the byte cap
    return _preview(text, cap)


def _preview(text: str, cap: ResultCap) -> str:
    size = _size(text)
    return _dumps(
        {
            "note": f"result is {size} bytes, over the cap of {cap.max_bytes}; {_how(cap)}",
            "preview": _head(text, cap.max_bytes),
        }
    )


def _cut(payload: dict[str, Any], rows: list[Any], field: str | None, cap: ResultCap) -> str:
    """The most rows, at most ``max_rows``, whose text with the note fits ``max_bytes``."""
    high = min(len(rows), cap.max_rows)
    text = _render(payload, rows, field, high, cap)
    if _size(text) <= cap.max_bytes:
        return text
    low = 0
    while high - low > 1:
        mid = (low + high) // 2
        if _size(_render(payload, rows, field, mid, cap)) <= cap.max_bytes:
            low = mid
        else:
            high = mid
    text = _render(payload, rows, field, low, cap)
    if low == 0 and _size(text) > cap.max_bytes:
        # Not even zero rows fit, a tiny bound or a long note: no row is to blame.
        return _render(payload, rows, field, 0, cap, name_row=False)
    return text


def _render(
    payload: dict[str, Any],
    rows: list[Any],
    field: str | None,
    shown: int,
    cap: ResultCap,
    *,
    name_row: bool = True,
) -> str:
    """The result with its first ``shown`` rows, in ``data`` or in its model's ``field``.

    ``name_row`` says whether a note that shows no row blames the first row for it.
    """
    total = len(rows)
    if shown >= total:
        return _dumps(payload)
    kept = rows[:shown]
    data = kept if field is None else {**payload["data"], field: kept}
    note = _note(shown, total, cap, _start(payload), name_row=name_row)
    return _dumps({**payload, "data": data, "note": note})
