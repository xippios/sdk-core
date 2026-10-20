"""Result caps: never hand an agent more than it can use, never truncate silently."""

import json
from dataclasses import dataclass
from typing import Any

from pydantic_core import to_jsonable_python

__all__ = ["ResultCap", "cap_result"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultCap:
    """Limits for one tool result (conventions §8 defaults).

    Attributes:
        max_rows: Most items of a list result that are returned.
        max_bytes: Most bytes of JSON text that are returned.
    """

    max_rows: int = 200
    max_bytes: int = 65_536

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.max_bytes < 1:
            raise ValueError("max_rows and max_bytes must be at least 1")


def _dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _note(shown: int, total: int, cap: ResultCap) -> str:
    return (
        f"showing {shown} of {total} rows (cap: {cap.max_rows} rows or {cap.max_bytes} bytes); "
        "narrow the query, for example with more filters or a shorter date range, to see the rest"
    )


def cap_result(value: Any, cap: ResultCap | None = None) -> str:
    """Serialise a task result as compact JSON text within ``cap``.

    A ``Result`` whose ``data`` is a list, or a bare list, is cut to the cap and gains a
    ``note`` saying how many rows were omitted and how to narrow the query. A bare
    list is wrapped as ``{"data": [...]}`` so the shape is the same either way. Any
    other value that exceeds the byte cap is replaced by a note and a preview.

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
        if len(text) <= cap.max_bytes:
            return text
        return _dumps(
            {
                "note": f"result is {len(text)} bytes, over the cap of {cap.max_bytes}; "
                "narrow the query",
                "preview": text[: cap.max_bytes],
            }
        )

    total = len(rows)
    high = min(total, cap.max_rows)
    text = _render(payload, rows, high, total, cap)
    if len(text) <= cap.max_bytes:
        return text
    low = 0
    while high - low > 1:
        mid = (low + high) // 2
        if len(_render(payload, rows, mid, total, cap)) <= cap.max_bytes:
            low = mid
        else:
            high = mid
    return _render(payload, rows, low, total, cap)


def _render(
    payload: dict[str, Any], rows: list[Any], shown: int, total: int, cap: ResultCap
) -> str:
    if shown >= total:
        return _dumps(payload)
    return _dumps({**payload, "data": rows[:shown], "note": _note(shown, total, cap)})
