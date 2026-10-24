import json
from datetime import UTC, datetime

import pytest

from xippios.core.mcp import ResultCap, cap_result
from xippios.core.models import Result, ResultMeta, UpstreamModel


class Row(UpstreamModel):
    n: int
    when: datetime


def envelope(count: int, total: int | None = None) -> Result[list[Row]]:
    meta = ResultMeta(
        source="example",
        endpoint="rows",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
        total=total,
    )
    return Result[list[Row]](
        data=[Row(n=i, when=datetime(2026, 1, 1, tzinfo=UTC)) for i in range(count)], meta=meta
    )


def test_small_result_is_compact_json_untouched() -> None:
    text = cap_result(envelope(2))
    payload = json.loads(text)
    assert "note" not in payload
    assert payload["data"][1] == {"n": 1, "when": "2026-01-01T00:00:00Z"}
    assert payload["meta"]["source"] == "example"
    assert ": " not in text


def test_row_cap_adds_note() -> None:
    payload = json.loads(cap_result(envelope(500), ResultCap(max_rows=10)))
    assert len(payload["data"]) == 10
    assert payload["data"][9]["n"] == 9
    assert payload["note"].startswith("showing 10 of 500 rows")
    assert "narrow the query" in payload["note"]
    assert payload["meta"]["endpoint"] == "rows"


def test_capped_result_keeps_the_upstream_total() -> None:
    payload = json.loads(cap_result(envelope(500, total=1234), ResultCap(max_rows=10)))
    assert len(payload["data"]) == 10
    assert payload["note"].startswith("showing 10 of 500 rows")
    assert payload["meta"]["total"] == 1234
    assert json.loads(cap_result(envelope(2, total=2)))["meta"]["total"] == 2
    assert json.loads(cap_result(envelope(2)))["meta"]["total"] is None


def test_byte_cap_shrinks_rows_to_fit() -> None:
    cap = ResultCap(max_rows=1000, max_bytes=2000)
    text = cap_result(envelope(500), cap)
    assert len(text) <= 2000
    payload = json.loads(text)
    shown = len(payload["data"])
    assert 0 < shown < 500
    assert payload["note"].startswith(f"showing {shown} of 500 rows")


def test_bare_list_is_wrapped() -> None:
    assert json.loads(cap_result([1, 2, 3])) == {"data": [1, 2, 3]}
    payload = json.loads(cap_result(list(range(50)), ResultCap(max_rows=5)))
    assert payload["data"] == [0, 1, 2, 3, 4]
    assert "showing 5 of 50" in payload["note"]


def test_non_list_payload_passes_or_previews() -> None:
    assert json.loads(cap_result({"a": 1})) == {"a": 1}
    text = cap_result({"blob": "x" * 500}, ResultCap(max_bytes=100))
    payload = json.loads(text)
    assert payload["note"].startswith("result is ")
    assert len(payload["preview"]) == 100


def test_cap_validation() -> None:
    with pytest.raises(ValueError, match="max_rows"):
        ResultCap(max_rows=0)


def test_the_default_note_promises_no_filter() -> None:
    payload = json.loads(cap_result(envelope(500), ResultCap(max_rows=10)))
    assert payload["note"] == (
        "showing 10 of 500 rows (cap: 10 rows or 65536 bytes); narrow the query to see the rest"
    )
    assert "filter" not in payload["note"]
    assert "date range" not in payload["note"]


def test_a_cap_note_is_used_verbatim_after_the_counts() -> None:
    cap = ResultCap(max_rows=10, note="filter by period or by reporter to see the rest")
    payload = json.loads(cap_result(envelope(500), cap))
    assert len(payload["data"]) == 10
    assert payload["note"] == (
        "showing 10 of 500 rows (cap: 10 rows or 65536 bytes); "
        "filter by period or by reporter to see the rest"
    )


def test_a_cap_note_counts_against_the_byte_cap() -> None:
    cap = ResultCap(max_rows=1000, max_bytes=2000, note="filter by period to see the rest")
    text = cap_result(envelope(500), cap)
    assert len(text) <= 2000
    payload = json.loads(text)
    shown = len(payload["data"])
    assert 0 < shown < 500
    assert payload["note"] == (
        f"showing {shown} of 500 rows (cap: 1000 rows or 2000 bytes); "
        "filter by period to see the rest"
    )


def test_the_byte_cap_note_promises_no_filter_or_uses_the_cap_note() -> None:
    blob = {"blob": "x" * 500}
    size = len(json.dumps(blob, separators=(",", ":")))
    payload = json.loads(cap_result(blob, ResultCap(max_bytes=100)))
    assert payload["note"] == (
        f"result is {size} bytes, over the cap of 100; narrow the query to see the rest"
    )
    noted = json.loads(cap_result(blob, ResultCap(max_bytes=100, note="ask for one blob")))
    assert noted["note"] == f"result is {size} bytes, over the cap of 100; ask for one blob"
    assert noted["preview"] == payload["preview"]


def test_a_cap_note_is_not_shown_when_nothing_is_cut() -> None:
    cap = ResultCap(note="filter by period to see the rest")
    assert "note" not in json.loads(cap_result(envelope(3), cap))
    assert json.loads(cap_result({"a": 1}, cap)) == {"a": 1}


@pytest.mark.parametrize("note", ["", "   "])
def test_a_blank_note_is_refused(note: str) -> None:
    with pytest.raises(ValueError, match="note must say how to see the rest"):
        ResultCap(note=note)
