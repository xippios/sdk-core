import json
from datetime import UTC, datetime

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
    # Row 21 b (sdk-cashctrl): an offset-paged task records start in meta.request.
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
    """A model that holds one list of rows beside two scalars, as sdk-comtrade's
    ``BilateralData`` holds its rows beside upstream's note and request time."""

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
    """A model with a second list, as sdk-x's pages carry ``errors`` beside ``data``."""

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
