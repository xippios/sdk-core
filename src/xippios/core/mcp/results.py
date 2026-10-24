"""Result caps: never hand an agent more than it can use, never truncate silently."""

import json
from dataclasses import dataclass
from typing import Any

from pydantic_core import to_jsonable_python

__all__ = ["ResultCap", "cap_result"]


_DEFAULT_NOTE = "narrow the query to see the rest"
"""What a capped result tells the agent when its cap has no ``note``: no filter promised."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultCap:
    """Limits for one tool result, and what to tell the agent when they cut it (conventions §8).

    The defaults are the family's: 200 rows or 64 KB. A reference tool whose whole list
    an agent needs gets a cap of its own with more rows, through ``caps=`` of
    ``register_tasks`` or ``build_server`` (ADR-0016); its byte bound stays at the
    default, the family's global one.

    Attributes:
        max_rows: Most items of a list result that are returned.
        max_bytes: Most bytes of JSON text that are returned.
        note: The text after the counts when the cap cuts a result, used verbatim, e.g.
            ``"filter by period or by reporter to see the rest"`` for a tool that has
            those filters. ``None`` says ``"narrow the query to see the rest"``, which
            promises no filter the tool may lack.

    Raises:
        ValueError: ``max_rows`` or ``max_bytes`` is below 1, or ``note`` is blank.
    """

    max_rows: int = 200
    max_bytes: int = 65_536
    note: str | None = None

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.max_bytes < 1:
            raise ValueError("max_rows and max_bytes must be at least 1")
        if self.note is not None and not self.note.strip():
            raise ValueError("note must say how to see the rest; None keeps the default")


def _dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _how(cap: ResultCap) -> str:
    return _DEFAULT_NOTE if cap.note is None else cap.note


def _note(shown: int, total: int, cap: ResultCap) -> str:
    return (
        f"showing {shown} of {total} rows (cap: {cap.max_rows} rows or {cap.max_bytes} bytes); "
        f"{_how(cap)}"
    )


def cap_result(value: Any, cap: ResultCap | None = None) -> str:
    """Serialise a task result as compact JSON text within ``cap``.

    A ``Result`` whose ``data`` is a list, or a bare list, is cut to the cap and gains a
    ``note``: ``"showing <shown> of <total> rows (cap: <max_rows> rows or <max_bytes>
    bytes); "`` and then the cap's ``note``, or ``"narrow the query to see the rest"``.
    A bare list is wrapped as ``{"data": [...]}`` so the shape is the same either way.
    Any other value that exceeds the byte cap is replaced by a note, ``"result is <n>
    bytes, over the cap of <max_bytes>; "`` and the same text, and a preview.

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
                f"{_how(cap)}",
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
