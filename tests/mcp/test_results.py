import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

import pytest

from xippios.core.errors import InvalidRequestError
from xippios.core.mcp import cap_result
from xippios.core.models import Result, ResultCap, ResultMeta, UpstreamModel


class Row(UpstreamModel):
    n: int
    when: datetime


def envelope(
    count: int, total: int | None = None, request: dict[str, object] | None = None
) -> Result[list[Row]]:
    meta = ResultMeta(
        source="example",
        endpoint="rows",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
        total=total,
        request=request or {},
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


def test_capped_result_keeps_the_upstream_total() -> None:
    payload = json.loads(cap_result(envelope(500, total=1234), ResultCap(max_rows=10)))
    assert len(payload["data"]) == 10
    assert payload["note"].startswith("showing 10 of 500 rows")
    assert payload["meta"]["total"] == 1234
    assert json.loads(cap_result(envelope(2, total=2)))["meta"]["total"] == 2
    assert json.loads(cap_result(envelope(2)))["meta"]["total"] is None


def test_bare_list_is_wrapped() -> None:
    assert json.loads(cap_result([1, 2, 3])) == {"data": [1, 2, 3]}
    payload = json.loads(cap_result(list(range(50)), ResultCap(max_rows=5)))
    assert payload["data"] == [0, 1, 2, 3, 4]
    assert "showing 5 of 50" in payload["note"]


def test_the_default_note_promises_no_filter() -> None:
    payload = json.loads(cap_result(envelope(500), ResultCap(max_rows=10)))
    assert [row["n"] for row in payload["data"]] == list(range(10))
    assert payload["meta"]["endpoint"] == "rows"
    assert payload["note"] == (
        "showing 10 of 500 rows (cap: 10 rows or 65536 bytes); narrow the query to see the rest"
    )
    assert "filter" not in payload["note"]
    assert "date range" not in payload["note"]


def test_a_capped_list_with_an_integer_start_says_where_to_resume() -> None:
    # An offset-paged task records start in meta.request.
    capped = json.loads(cap_result(envelope(500, request={"start": 100}), ResultCap(max_rows=10)))
    assert capped["note"] == (
        "showing 10 of 500 rows (cap: 10 rows or 65536 bytes); narrow the query to see the "
        "rest; resume with start=110"
    )


def test_no_integer_start_no_resume_hint() -> None:
    requests: list[dict[str, object]] = [{}, {"start": "100"}, {"start": True}]
    for request in requests:
        note = json.loads(cap_result(envelope(50, request=request), ResultCap(max_rows=5)))["note"]
        assert note.endswith("narrow the query to see the rest")
    assert "resume" not in json.loads(cap_result(envelope(5, request={"start": 0})))


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


def _utf8(text: str) -> int:
    return len(text.encode("utf-8"))


def _compact(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _cut_with(rows: list[str], shown: int, cap: ResultCap) -> str:
    """What cap_result returns for ``shown`` of ``rows``, by the documented note format."""
    note = (
        f"showing {shown} of {len(rows)} rows (cap: {cap.max_rows} rows or {cap.max_bytes} "
        "bytes); narrow the query to see the rest"
    )
    return _compact({"data": rows[:shown], "note": note})


def test_the_byte_cap_counts_utf8_bytes_not_characters() -> None:
    rows = ["é" * 50] * 20  # 2 bytes a character
    cap = ResultCap(max_bytes=1500)
    whole = _compact({"data": rows})
    assert len(whole) < 1500 < _utf8(whole)  # fits by characters, not by bytes
    text = cap_result(rows, cap)
    assert _utf8(text) <= 1500
    shown = len(json.loads(text)["data"])
    assert 0 < shown < 20
    assert text == _cut_with(rows, shown, cap)
    assert _utf8(_cut_with(rows, shown + 1, cap)) > 1500  # no row more would have fitted


def test_the_byte_note_counts_utf8_bytes_and_the_preview_cuts_no_character() -> None:
    blob = {"blob": "é" * 100}
    text = json.dumps(blob, ensure_ascii=False, separators=(",", ":"))
    assert len(text) < 150 < _utf8(text)
    payload = json.loads(cap_result(blob, ResultCap(max_bytes=150)))
    assert payload["note"] == (
        f"result is {_utf8(text)} bytes, over the cap of 150; narrow the query to see the rest"
    )
    # 9 bytes of '{"blob":"', then 2-byte characters: byte 150 would split the 71st.
    assert payload["preview"] == '{"blob":"' + "é" * 70
    assert _utf8(payload["preview"]) == 149


def test_a_lone_surrogate_counts_as_three_bytes_and_does_not_raise() -> None:
    text = cap_result({"x": "\ud800" * 30}, ResultCap(max_bytes=20))  # json.loads lets it through
    payload = json.loads(text)
    assert payload["note"].startswith("result is 98 bytes, over the cap of 20; ")
    assert payload["preview"] == '{"x":"' + "\ud800" * 4  # 6 + 4 * 3 bytes


class Page(UpstreamModel):
    """A model that holds one list of rows beside two scalars, as a source's answer holds
    its rows beside upstream's note and request time."""

    requested: str
    count: int
    rows: list[Row]


def page(count: int, request: dict[str, object] | None = None) -> Result[Page]:
    rows = [Row(n=i, when=datetime(2026, 1, 1, tzinfo=UTC)) for i in range(count)]
    data = Page(requested="2026-10-28 16:14:25.593", count=count, rows=rows)
    return Result[Page](data=data, meta=envelope(0, request=request).meta)


def _page_cut_with(result: Result[Page], shown: int, cap: ResultCap) -> str:
    """What cap_result returns for ``shown`` rows of a ``Page``, by the documented format."""
    payload = result.model_dump(mode="json")
    total = len(payload["data"]["rows"])
    note = (
        f"showing {shown} of {total} rows (cap: {cap.max_rows} rows or {cap.max_bytes} "
        "bytes); narrow the query to see the rest"
    )
    data = {**payload["data"], "rows": payload["data"]["rows"][:shown]}
    return _compact({**payload, "data": data, "note": note})


def test_a_model_over_the_byte_cap_has_its_rows_cut_and_its_other_fields_kept() -> None:
    # https://github.com/xippios/sdk-core/issues/131: such a model was a note and a preview.
    cap = ResultCap(max_bytes=2000)
    result = page(100)
    text = cap_result(result, cap)
    assert _utf8(text) <= 2000
    payload = json.loads(text)
    shown = len(payload["data"]["rows"])
    assert 0 < shown < 100
    assert [row["n"] for row in payload["data"]["rows"]] == list(range(shown))
    assert payload["data"]["requested"] == "2026-10-28 16:14:25.593"
    assert payload["data"]["count"] == 100
    assert payload["meta"]["endpoint"] == "rows"
    assert payload["note"] == (
        f"showing {shown} of 100 rows (cap: 200 rows or 2000 bytes); "
        "narrow the query to see the rest"
    )
    assert "preview" not in payload
    assert text == _page_cut_with(result, shown, cap)
    assert _utf8(_page_cut_with(result, shown + 1, cap)) > 2000  # no row more would have fitted


def test_a_model_within_the_byte_cap_comes_back_whole_past_the_row_bound() -> None:
    # A model is one upstream answer, often a page whose cursor follows its last row, so
    # the row bound alone never cuts it.
    text = cap_result(page(300))
    assert _utf8(text) < 65_536
    payload = json.loads(text)
    assert "note" not in payload
    assert len(payload["data"]["rows"]) == 300


def test_a_model_past_the_byte_cap_is_cut_to_the_row_bound_too() -> None:
    whole = _utf8(cap_result(page(300)))
    cap = ResultCap(max_bytes=whole - 1)  # 299 rows would fit the bytes
    payload = json.loads(cap_result(page(300), cap))
    assert len(payload["data"]["rows"]) == 200
    assert payload["data"]["count"] == 300
    assert payload["note"] == (
        f"showing 200 of 300 rows (cap: 200 rows or {whole - 1} bytes); "
        "narrow the query to see the rest"
    )


def test_a_cut_model_whose_request_records_a_start_says_where_to_resume() -> None:
    payload = json.loads(cap_result(page(100, request={"start": 40}), ResultCap(max_bytes=2000)))
    shown = len(payload["data"]["rows"])
    assert 0 < shown < 100
    assert payload["note"].endswith(
        f"narrow the query to see the rest; resume with start={40 + shown}"
    )


class Lookup(UpstreamModel):
    """A model with a second list, as a source's pages carry ``errors`` beside ``data``."""

    rows: list[Row]
    errors: list[str] | None = None


def test_only_a_model_that_holds_one_list_has_its_rows_cut() -> None:
    rows = [Row(n=i, when=datetime(2026, 1, 1, tzinfo=UTC)) for i in range(100)]
    meta = envelope(0).meta
    cap = ResultCap(max_bytes=2000)
    one = json.loads(cap_result(Result[Lookup](data=Lookup(rows=rows), meta=meta), cap))
    assert one["data"]["errors"] is None, "a list field left None holds no list"
    assert 0 < len(one["data"]["rows"]) < 100
    two = Result[Lookup](data=Lookup(rows=rows, errors=["not found"]), meta=meta)
    payload = json.loads(cap_result(two, cap))
    assert set(payload) == {"note", "preview"}
    assert payload["note"].startswith("result is ")
    bare = json.loads(cap_result({"rows": list(range(1000))}, ResultCap(max_bytes=100)))
    assert set(bare) == {"note", "preview"}, "only a result's data holds rows"


def test_a_model_whose_other_fields_alone_pass_the_cap_is_a_preview() -> None:
    # The cut keeps a model's other fields whole, so where they alone pass the cap the
    # preview keeps the result bounded.
    rows = [Row(n=i, when=datetime(2026, 1, 1, tzinfo=UTC)) for i in range(3)]
    result = Result[Page](
        data=Page(requested="x" * 3000, count=3, rows=rows), meta=envelope(0).meta
    )
    payload = json.loads(cap_result(result, ResultCap(max_bytes=2000)))
    assert set(payload) == {"note", "preview"}
    assert _utf8(payload["preview"]) <= 2000


def test_when_no_row_fits_the_note_names_that_row_and_no_resume_offset() -> None:
    # https://github.com/xippios/sdk-core/issues/175: "resume with start=5" sent a tool
    # that follows the note back to the start it had just used.
    result = Result[list[str]](data=["x" * 3000, "y"], meta=envelope(0, request={"start": 5}).meta)
    payload = json.loads(cap_result(result, ResultCap(max_bytes=1000)))
    assert payload["data"] == []
    assert "start=5" not in payload["note"]
    assert "resume" not in payload["note"]
    assert payload["note"] == (
        "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); the row at offset 5 alone "
        "exceeds the byte cap; narrow the query to see the rest"
    )


def test_when_no_row_fits_without_a_start_the_note_names_the_first_row() -> None:
    cap = ResultCap(max_bytes=1000, note="read a long message alone with get_message")
    assert json.loads(cap_result(["x" * 3000, "y"], cap)) == {
        "data": [],
        "note": "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); the first row alone "
        "exceeds the byte cap; read a long message alone with get_message",
    }


def test_when_not_even_zero_rows_fit_the_note_names_no_row_and_no_resume_offset() -> None:
    # A tiny bound: each row is one byte, so no row is to blame, and a cap note that names
    # a tool for one long row would send the agent the wrong way.
    cap = ResultCap(max_bytes=10, note="read a long message alone with get_message")
    assert _utf8(_compact({"data": [1, 2, 3]})) > 10
    assert json.loads(cap_result([1, 2, 3], cap)) == {
        "data": [],
        "note": "showing 0 of 3 rows (cap: 200 rows or 10 bytes); "
        "read a long message alone with get_message",
    }
    result = Result[list[int]](data=[1, 2, 3], meta=envelope(0, request={"start": 5}).meta)
    note = json.loads(cap_result(result, ResultCap(max_bytes=50)))["note"]
    assert (
        note == "showing 0 of 3 rows (cap: 200 rows or 50 bytes); narrow the query to see the rest"
    )


class Thread(UpstreamModel):
    """A model whose one list holds texts, as a thread holds its messages."""

    thread_id: str
    messages: list[str]


def test_a_model_whose_first_row_alone_passes_the_cap_shows_no_row_and_says_so() -> None:
    thread = Thread(thread_id="t1", messages=["x" * 3000, "y"])
    result = Result[Thread](data=thread, meta=envelope(0, request={"start": 7}).meta)
    payload = json.loads(cap_result(result, ResultCap(max_bytes=1000)))
    assert payload["data"] == {"thread_id": "t1", "messages": []}
    assert payload["note"] == (
        "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); the row at offset 7 alone "
        "exceeds the byte cap; narrow the query to see the rest"
    )


# The notes an unpaged cap writes, as main read them at 0.4.0. Sources pin them under
# xippios-core~=0.4.0 (one source's every-country note, another's start notes), so a paged
# cap, sdk-core#362, leaves each byte as it is.
GET_SERIES = "read a long series alone with example_get_series"
COUNTRY = "pass country_code, e.g. 1220 (Canada), for one destination's weeks, up to 54 rows"


@pytest.mark.parametrize(
    ("result", "cap", "note"),
    [
        (envelope(500), ResultCap(),
         "showing 200 of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the "
         "rest"),
        (envelope(498), ResultCap(note=COUNTRY),
         f"showing 200 of 498 rows (cap: 200 rows or 65536 bytes); {COUNTRY}"),
        (envelope(3, request={"start": 4}), ResultCap(max_rows=2, note=GET_SERIES),
         f"showing 2 of 3 rows (cap: 2 rows or 65536 bytes); {GET_SERIES}; resume with start=6"),
        (Result[list[str]](data=["x" * 70_000] * 2, meta=envelope(0, request={"start": 0}).meta),
         ResultCap(note=GET_SERIES),
         "showing 0 of 2 rows (cap: 200 rows or 65536 bytes); the row at offset 0 alone exceeds "
         f"the byte cap; {GET_SERIES}"),
        (["x" * 3000, "y"], ResultCap(max_bytes=1000),
         "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); the first row alone exceeds the "
         "byte cap; narrow the query to see the rest"),
        ([1, 2, 3], ResultCap(max_bytes=10),
         "showing 0 of 3 rows (cap: 200 rows or 10 bytes); narrow the query to see the rest"),
        ({"blob": "x" * 500}, ResultCap(max_bytes=100),
         "result is 511 bytes, over the cap of 100; narrow the query to see the rest"),
    ],
)  # fmt: skip
def test_an_unpaged_note_reads_as_on_main_byte_for_byte(
    result: object, cap: ResultCap, note: str
) -> None:
    assert json.loads(cap_result(result, cap))["note"] == note
    assert "offset=" not in note


def _n(payload: dict[str, Any]) -> list[int]:
    return [row["n"] for row in payload["data"]]


def test_a_paged_cut_names_the_call_for_the_next_rows_and_that_call_answers_them() -> None:
    # https://github.com/xippios/sdk-core/issues/314: a tool of 500 rows answers 200.
    first = json.loads(cap_result(envelope(500), ResultCap(paged=True)))
    assert _n(first) == list(range(200))
    assert first["note"] == (
        "showing 200 of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the "
        "rest; continue with offset=200"
    )
    second = json.loads(cap_result(envelope(500), ResultCap(paged=True), offset=200))
    assert _n(second) == list(range(200, 400))
    assert second["note"] == (
        "showing rows 201 to 400 of 500 (cap: 200 rows or 65536 bytes); narrow the query to "
        "see the rest; continue with offset=400"
    )
    last = json.loads(cap_result(envelope(500), ResultCap(paged=True), offset=400))
    assert _n(last) == list(range(400, 500))
    assert last["note"] == "showing rows 401 to 500 of 500", "a page says so, the last one too"
    assert first["meta"] == second["meta"] == last["meta"], "meta stays the task's"


def test_a_paged_answer_that_fits_is_whole_and_carries_no_note() -> None:
    assert cap_result(envelope(5), ResultCap(paged=True)) == cap_result(envelope(5))
    assert "note" not in json.loads(cap_result(envelope(5), ResultCap(paged=True)))
    assert json.loads(cap_result(envelope(5), ResultCap(paged=True), offset=3))["note"] == (
        "showing rows 4 to 5 of 5"
    )


def test_a_cap_that_keeps_the_last_rows_answers_the_newest_and_walks_to_older() -> None:
    # A weekly series that runs oldest first: the newest 200 come first.
    cap = ResultCap(paged=True, keep="last")
    newest = json.loads(cap_result(envelope(500), cap))
    assert _n(newest) == list(range(300, 500)), "the newest rows, in the task's order"
    assert newest["note"] == (
        "showing rows 301 to 500 of 500 (cap: 200 rows or 65536 bytes); narrow the query to "
        "see the rest; continue with offset=200"
    )
    older = json.loads(cap_result(envelope(500), cap, offset=200))
    assert _n(older) == list(range(100, 300))
    assert older["note"].endswith("; continue with offset=400")
    oldest = json.loads(cap_result(envelope(500), cap, offset=400))
    assert _n(oldest) == list(range(100))
    assert oldest["note"] == "showing rows 1 to 100 of 500"


def test_an_unpaged_cap_that_keeps_the_last_rows_names_them_and_no_continuation() -> None:
    payload = json.loads(cap_result(envelope(500, request={"start": 0}), ResultCap(keep="last")))
    assert _n(payload) == list(range(300, 500))
    assert payload["note"] == (
        "showing rows 301 to 500 of 500 (cap: 200 rows or 65536 bytes); narrow the query to "
        "see the rest"
    ), "start + shown would name rows after the kept end, so no resume either"


def _walk(result: object, cap: ResultCap) -> list[dict[str, Any]]:
    """Every page of ``result``, by the offset each note names, checking each page's bound."""
    pages: list[dict[str, Any]] = []
    offset = 0
    while True:
        text = cap_result(result, cap, offset=offset)
        assert _utf8(text) <= cap.max_bytes
        pages.append(json.loads(text))
        found = re.search(r"; continue with offset=(\d+)$", pages[-1].get("note", ""))
        if found is None:
            return pages
        assert int(found[1]) > offset
        offset = int(found[1])


@pytest.mark.parametrize("keep", ["first", "last"])
def test_the_byte_bound_cuts_a_page_short_and_the_next_offset_is_still_right(
    keep: Literal["first", "last"],
) -> None:
    cap = ResultCap(paged=True, keep=keep, max_bytes=2000)
    pages = _walk(envelope(500), cap)
    assert all(len(page["data"]) < 200 for page in pages), "the byte bound cuts first"
    assert len(pages) > 10
    rows = [_n(page) for page in pages]
    walked = [n for page in (rows if keep == "first" else rows[::-1]) for n in page]
    assert walked == list(range(500)), "no row repeated, none skipped"


def test_a_paged_model_keeps_its_other_fields_on_every_page() -> None:
    cap = ResultCap(paged=True, max_bytes=2000)
    pages = _walk(page(300), cap)
    assert len(pages) > 2
    assert [row["n"] for p in pages for row in p["data"]["rows"]] == list(range(300))
    assert {(p["data"]["requested"], p["data"]["count"]) for p in pages} == {
        ("2026-10-28 16:14:25.593", 300)
    }
    # Within the byte cap a model's page holds every row the offset leaves, past the row
    # bound, as a whole model does.
    rest = json.loads(cap_result(page(300), ResultCap(paged=True), offset=50))
    assert [row["n"] for row in rest["data"]["rows"]] == list(range(50, 300))
    assert rest["note"] == "showing rows 51 to 300 of 300"


def test_a_row_alone_over_the_byte_bound_is_passed_by_offset_plus_one() -> None:
    rows = ["a", "x" * 3000, "b", "c"]
    cap = ResultCap(paged=True, max_bytes=1000)
    assert json.loads(cap_result(rows, cap)) == {
        "data": ["a"],
        "note": "showing 1 of 4 rows (cap: 200 rows or 1000 bytes); narrow the query to see "
        "the rest; continue with offset=1",
    }
    assert json.loads(cap_result(rows, cap, offset=1)) == {
        "data": [],
        "note": "showing 0 of 4 rows (cap: 200 rows or 1000 bytes); row 2 alone exceeds the "
        "byte cap; narrow the query to see the rest; continue past it with offset=2",
    }
    assert json.loads(cap_result(rows, cap, offset=2)) == {
        "data": ["b", "c"],
        "note": "showing rows 3 to 4 of 4",
    }


def test_a_long_first_or_newest_row_is_passed_and_a_long_last_one_ends_the_walk() -> None:
    cap = ResultCap(paged=True, max_bytes=1000)
    assert json.loads(cap_result(["x" * 3000, "b"], cap))["note"] == (
        "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); the first row alone exceeds the "
        "byte cap; narrow the query to see the rest; continue past it with offset=1"
    )
    newest = ResultCap(paged=True, keep="last", max_bytes=1000)
    assert json.loads(cap_result(["a", "b", "x" * 3000], newest))["note"] == (
        "showing 0 of 3 rows (cap: 200 rows or 1000 bytes); row 3 alone exceeds the byte cap; "
        "narrow the query to see the rest; continue past it with offset=1"
    )
    assert json.loads(cap_result(["a", "b", "x" * 3000], newest, offset=1))["data"] == ["a", "b"]
    assert json.loads(cap_result(["a", "x" * 3000], cap, offset=1))["note"] == (
        "showing 0 of 2 rows (cap: 200 rows or 1000 bytes); row 2 alone exceeds the byte cap; "
        "narrow the query to see the rest"
    ), "no row is past it, so no continuation"


def test_a_paged_note_never_names_the_tasks_own_start() -> None:
    payload = json.loads(cap_result(envelope(500, request={"start": 100}), ResultCap(paged=True)))
    assert payload["note"].endswith("narrow the query to see the rest; continue with offset=200")
    assert "start" not in payload["note"]


@pytest.mark.parametrize("keep", ["first", "last"])
def test_an_offset_past_the_end_answers_no_row_and_says_so(
    keep: Literal["first", "last"],
) -> None:
    cap = ResultCap(paged=True, keep=keep)
    for offset in (500, 501, 10_000):
        payload = json.loads(cap_result(envelope(500), cap, offset=offset))
        assert payload["data"] == []
        assert payload["note"] == f"showing 0 of 500 rows; offset {offset} leaves no row to show"
    empty = json.loads(cap_result(envelope(0), cap, offset=3))
    assert (empty["data"], empty["note"]) == (
        [],
        "showing 0 of 0 rows; offset 3 leaves no row to show",
    )


def test_an_offset_is_refused_below_zero_and_without_a_paged_cap() -> None:
    with pytest.raises(ValueError, match=r"^offset must not be negative, got -1$"):
        cap_result(envelope(5), ResultCap(paged=True), offset=-1)
    with pytest.raises(ValueError, match=r"^offset needs a paged cap, ResultCap\(paged=True\)$"):
        cap_result(envelope(5), ResultCap(), offset=1)
    assert cap_result(envelope(5), ResultCap(), offset=0) == cap_result(envelope(5))


def test_an_offset_on_an_answer_without_rows_is_refused() -> None:
    assert json.loads(cap_result({"a": 1}, ResultCap(paged=True))) == {"a": 1}
    with pytest.raises(InvalidRequestError, match=r"^offset: this answer holds no list of rows"):
        cap_result({"a": 1}, ResultCap(paged=True), offset=1)
