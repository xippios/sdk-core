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


def _note(shown: int, total: int, cap: ResultCap, start: int | None) -> str:
    resume = "" if start is None else f"; resume with start={start + shown}"
    return (
        f"showing {shown} of {total} rows (cap: {cap.max_rows} rows or {cap.max_bytes} bytes); "
        f"{_how(cap)}{resume}"
    )


def _start(payload: dict[str, Any]) -> int | None:
    """The integer ``start`` the result's ``meta.request`` records, for the resume hint."""
    meta = payload.get("meta")
    request = meta.get("request") if isinstance(meta, dict) else None
    start = request.get("start") if isinstance(request, dict) else None
    return start if isinstance(start, int) and not isinstance(start, bool) else None


def cap_result(value: Any, cap: ResultCap | None = None) -> str:
    """Serialise a task result as compact JSON text within ``cap``.

    A ``Result`` whose ``data`` is a list, or a bare list, is cut to the cap and gains a
    ``note``: ``"showing <shown> of <total> rows (cap: <max_rows> rows or <max_bytes>
    bytes); "`` and then the cap's ``note``, or ``"narrow the query to see the rest"``;
    where ``meta.request`` records an integer ``start``, an offset-paged task's, the note
    ends ``"; resume with start=<start + shown>"``.
    A bare list is wrapped as ``{"data": [...]}`` so the shape is the same either way.
    Any other value that exceeds the byte cap is replaced by a note, ``"result is <n>
    bytes, over the cap of <max_bytes>; "`` and the same text, and a preview of its first
    ``max_bytes`` bytes. Bytes are those of the JSON text encoded as UTF-8.

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
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        text = _dumps(payload)
        size = _size(text)
        if size <= cap.max_bytes:
            return text
        return _dumps(
            {
                "note": f"result is {size} bytes, over the cap of {cap.max_bytes}; {_how(cap)}",
                "preview": _head(text, cap.max_bytes),
            }
        )

    total = len(rows)
    high = min(total, cap.max_rows)
    text = _render(payload, rows, high, total, cap)
    if _size(text) <= cap.max_bytes:
        return text
    low = 0
    while high - low > 1:
        mid = (low + high) // 2
        if _size(_render(payload, rows, mid, total, cap)) <= cap.max_bytes:
            low = mid
        else:
            high = mid
    return _render(payload, rows, low, total, cap)


def _render(
    payload: dict[str, Any], rows: list[Any], shown: int, total: int, cap: ResultCap
) -> str:
    if shown >= total:
        return _dumps(payload)
    note = _note(shown, total, cap, _start(payload))
    return _dumps({**payload, "data": rows[:shown], "note": note})
