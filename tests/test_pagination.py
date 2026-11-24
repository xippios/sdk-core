from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

import pytest

from xippios.core.errors import InvalidRequestError, QueryTooLarge, RateLimitError
from xippios.core.pagination import fetch_counted, fetch_pages

pytestmark = pytest.mark.anyio


class Pages:
    """An upstream list of ``rows`` served by offset, each answer with ``counts``'s next count.

    ``counts`` gives the count each request answers, in order, its last one repeated; ``None``
    stands for an upstream that sends no count. ``sent`` notes each offset asked for.
    """

    def __init__(self, rows: Sequence[int], *, size: int, counts: Sequence[int | None]) -> None:
        self.rows = list(rows)
        self.size = size
        self.counts = list(counts)
        self.sent: list[int] = []

    async def fetch(self, offset: int) -> tuple[list[int], int | None]:
        count = self.counts[min(len(self.sent), len(self.counts) - 1)]
        self.sent.append(offset)
        return self.rows[offset : offset + self.size], count


async def test_the_walk_collects_every_page_with_the_count_of_the_last_one() -> None:
    upstream = Pages(range(7), size=3, counts=[7])
    rows, total = await fetch_pages(upstream.fetch, page_size=3, most=3, paging="page")
    assert (rows, total) == (list(range(7)), 7)
    assert upstream.sent == [0, 3, 6]  # the short third page is the last


async def test_a_page_numbered_endpoint_maps_the_offset_to_its_page() -> None:
    pages: list[int] = []

    async def fetch(offset: int) -> tuple[list[int], int | None]:
        page = 1 + offset // 3  # the docstring's mapping, first page 1
        pages.append(page)
        return list(range((page - 1) * 3, min(page * 3, 7))), 7

    rows, _ = await fetch_pages(fetch, page_size=3, most=3, paging="page")
    assert rows == list(range(7))
    assert pages == [1, 2, 3]


async def test_no_request_is_sent_at_or_past_upstream_s_count() -> None:
    upstream = Pages(range(6), size=3, counts=[6])
    rows, total = await fetch_pages(upstream.fetch, page_size=3, most=5, paging="page")
    assert (rows, total) == (list(range(6)), 6)
    assert upstream.sent == [0, 3], "the full second page reaches the count: no empty third"


async def test_the_count_of_the_last_page_is_kept_and_never_corrected() -> None:
    upstream = Pages(range(7), size=3, counts=[7, 7, 6])
    rows, total = await fetch_pages(upstream.fetch, page_size=3, most=3, paging="page")
    assert (len(rows), total) == (7, 6)  # upstream's mismatch stays (ADR-0034, decision 2)


async def test_a_count_of_as_many_pages_as_the_bound_fetches_them_all() -> None:
    upstream = Pages(range(75), size=25, counts=[75])
    rows, total = await fetch_pages(upstream.fetch, page_size=25, most=3, paging="page")
    assert (len(rows), total) == (75, 75)
    assert upstream.sent == [0, 25, 50]


async def test_a_count_over_the_bound_is_refused_after_the_first_page_with_nothing() -> None:
    upstream = Pages(range(703), size=25, counts=[703])
    with pytest.raises(InvalidRequestError) as info:
        await fetch_pages(upstream.fetch, page_size=25, most=24, paging="page", source="example")
    assert str(info.value) == (
        "the walk needs more than the 24 pages that one call fetches: upstream counts 703 "
        "records on 29 pages of 25, and the walk reached page 1 of 29 after 1 request. It "
        "returns nothing; pass page to fetch one page at a time."
    )
    assert type(info.value) is InvalidRequestError
    assert info.value.source == "example"
    assert upstream.sent == [0], "the count shows the bound passed: no second request"


async def test_from_start_the_bound_counts_the_pages_the_walk_needs() -> None:
    upstream = Pages(range(100), size=10, counts=[100])
    rows, _ = await fetch_pages(upstream.fetch, page_size=10, most=5, start=50, paging="start")
    assert rows == list(range(50, 100))
    assert upstream.sent == [50, 60, 70, 80, 90]
    upstream = Pages(range(100), size=10, counts=[100])
    with pytest.raises(InvalidRequestError) as info:
        await fetch_pages(upstream.fetch, page_size=10, most=4, start=50, paging="start")
    assert "the walk reached page 6 of 10 after 1 request" in str(info.value)
    assert upstream.sent == [50]


class Catalog:
    """A catalog of releases, newest first, paged as a pager answers: 0-based pages of 25.

    One release a day back from ``newest``, ``count`` of them; ``sent`` notes each page asked.
    """

    def __init__(self, newest: date, count: int) -> None:
        self.newest = newest
        self.count = count
        self.sent: list[int] = []

    async def fetch_page(self, page: int) -> tuple[list[date], int]:
        self.sent.append(page)
        first = page * 25
        days = range(first, min(first + 25, self.count))
        return [self.newest - timedelta(days=day) for day in days], self.count


async def test_a_stop_rule_ends_the_walk_after_the_page_it_marks() -> None:
    """A pager's walk to ``since``: the count shows far more pages than the bound, and the
    stop rule ends the walk on the first page that reaches back before ``since``."""
    catalog = Catalog(date(2026, 10, 9), count=1_542_025)
    since = date(2026, 8, 25)  # page 0 runs back to 2026-09-15, page 1 to 2026-08-21

    async def fetch(offset: int) -> tuple[list[date], int | None]:
        return await catalog.fetch_page(offset // 25)  # the page as upstream numbers it

    def older_than_since(page: Sequence[date]) -> bool:
        return bool(page) and min(page) < since

    days, total = await fetch_pages(
        fetch, page_size=25, most=24, stop=older_than_since, paging="page"
    )
    assert catalog.sent == [0, 1], "page 1 reaches back before since: the walk ends there"
    assert len(days) == 50, "the page the rule marks is kept whole"
    assert total == 1_542_025


async def test_with_a_stop_rule_the_walk_refuses_at_its_bound() -> None:
    catalog = Catalog(date(2026, 10, 9), count=1_000)

    async def fetch(offset: int) -> tuple[list[date], int | None]:
        return await catalog.fetch_page(offset // 25)

    with pytest.raises(InvalidRequestError) as info:
        await fetch_pages(
            fetch, page_size=25, most=4, stop=lambda page: False, paging="page (0 for the first)"
        )
    assert str(info.value) == (
        "the walk needs more than the 4 pages that one call fetches: upstream counts 1,000 "
        "records on 40 pages of 25, and the walk reached page 4 of 40 after 4 requests. It "
        "returns nothing; pass page (0 for the first) to fetch one page at a time."
    )
    assert catalog.sent == [0, 1, 2, 3]


async def test_without_a_count_the_walk_ends_on_a_short_page() -> None:
    upstream = Pages(range(7), size=3, counts=[None])
    rows, total = await fetch_pages(upstream.fetch, page_size=3, most=3, paging="page")
    assert (rows, total) == (list(range(7)), None)
    assert upstream.sent == [0, 3, 6]


async def test_without_a_count_the_walk_refuses_at_its_bound() -> None:
    upstream = Pages(range(100), size=10, counts=[None])
    with pytest.raises(InvalidRequestError) as info:
        await fetch_pages(upstream.fetch, page_size=10, most=2, paging="start with limit")
    assert str(info.value) == (
        "the walk needs more than the 2 pages that one call fetches: upstream sends no count "
        "of its records, so its total of pages is unknown, and the walk reached page 2 after "
        "2 requests. It returns nothing; pass start with limit to fetch one page at a time."
    )
    assert upstream.sent == [0, 10]


@pytest.mark.parametrize(
    ("count", "where"),
    [
        (50, "upstream counts 50 records on 2 pages of 25, and the walk reached page 1 of 2"),
        (
            None,
            "upstream sends no count of its records, so its total of pages is unknown, and the "
            "walk reached page 1",
        ),
    ],
    ids=["counted", "uncounted"],
)
async def test_a_bound_of_one_page_is_named_in_the_singular(count: int | None, where: str) -> None:
    upstream = Pages(range(50), size=25, counts=[count])
    with pytest.raises(InvalidRequestError) as info:
        await fetch_pages(upstream.fetch, page_size=25, most=1, paging="page")
    assert str(info.value) == (
        f"the walk needs more than the 1 page that one call fetches: {where} after 1 request. "
        "It returns nothing; pass page to fetch one page at a time."
    )
    assert upstream.sent == [0]


async def test_a_key_drops_an_item_that_a_later_page_repeats() -> None:
    """A record added at the top between two requests shifts the list: page 2 repeats 3."""
    answers = {0: [1, 2, 3], 3: [3, 4, 5], 6: [6]}
    sent: list[int] = []

    async def fetch(offset: int) -> tuple[list[int], int | None]:
        sent.append(offset)
        return answers[offset], 8

    rows, total = await fetch_pages(fetch, page_size=3, most=3, key=lambda row: row, paging="p")
    assert (rows, total) == ([1, 2, 3, 4, 5, 6], 8)
    assert sent == [0, 3, 6], "the offset follows what upstream sent, the repeat included"
    sent.clear()
    rows, _ = await fetch_pages(fetch, page_size=3, most=3, paging="p")
    assert rows == [1, 2, 3, 3, 4, 5, 6], "without a key every item is kept"


async def test_an_error_of_a_page_passes_as_raised_and_nothing_is_returned() -> None:
    refused = RateLimitError("429 from GET /v1/regions: slow down", source="example")
    sent: list[int] = []

    async def fetch(offset: int) -> tuple[list[int], int | None]:
        sent.append(offset)
        if offset:
            raise refused
        return [0, 1, 2], 9

    with pytest.raises(RateLimitError) as info:
        await fetch_pages(fetch, page_size=3, most=3, paging="page")
    assert info.value is refused
    assert sent == [0, 3]


@pytest.mark.parametrize(("page_size", "most"), [(0, 3), (3, 0)], ids=["page_size", "most"])
async def test_a_page_size_or_a_bound_below_1_is_refused_before_any_request(
    page_size: int, most: int
) -> None:
    upstream = Pages(range(7), size=3, counts=[7])
    name = "page_size" if page_size < 1 else "most"
    with pytest.raises(ValueError, match=name):
        await fetch_pages(upstream.fetch, page_size=page_size, most=most, paging="page")
    assert upstream.sent == []


NARROW = "Split by period, then by reporter."
"""What narrows the query, as a source words it: the error's last sentence."""


class Upstream:
    """A count and a data request that note what was sent, in order (ADR-0053)."""

    def __init__(self, answer: object, rows: list[str] | None = None) -> None:
        self.answer = answer
        self.rows = rows if rows is not None else ["row"]
        self.sent: list[str] = []

    async def count(self) -> int:
        self.sent.append("count")
        return cast(int, self.answer)  # what upstream's count gave, whatever its type

    async def fetch(self) -> list[str]:
        self.sent.append("data")
        return self.rows


async def test_a_count_of_0_answers_the_empty_answer_without_the_data_request() -> None:
    upstream = Upstream(0)
    empty: list[str] = []
    data, count = await fetch_counted(
        upstream.count, upstream.fetch, limit=100_000, empty=empty, narrow=NARROW
    )
    assert data is empty  # the task's own empty answer, as it passed it
    assert count == 0
    assert upstream.sent == ["count"]


async def test_a_count_over_the_limit_raises_with_both_numbers_before_the_data_request() -> None:
    upstream = Upstream(5_006_385)
    with pytest.raises(QueryTooLarge) as info:
        await fetch_counted(
            upstream.count,
            upstream.fetch,
            limit=100_000,
            empty=[],
            narrow=NARROW,
            source="example",
        )
    assert (info.value.count, info.value.limit) == (5_006_385, 100_000)
    assert (info.value.narrow, info.value.source) == (NARROW, "example")
    assert info.value.request is None  # refused before the data request: it names none
    assert upstream.sent == ["count"]


async def test_a_count_within_the_limit_fetches_and_returns_the_count_beside_the_data() -> None:
    upstream = Upstream(3, rows=["a", "b", "c"])
    data, count = await fetch_counted(
        upstream.count, upstream.fetch, limit=100_000, empty=[], narrow=NARROW
    )
    assert (data, count) == (["a", "b", "c"], 3)  # the count is meta.total's (ADR-0034)
    assert upstream.sent == ["count", "data"]


async def test_a_count_equal_to_the_limit_fetches() -> None:
    upstream = Upstream(50_000)
    data, count = await fetch_counted(
        upstream.count, upstream.fetch, limit=50_000, empty=[], narrow=NARROW
    )
    assert (data, count) == (["row"], 50_000)  # the limit is the most upstream serves
    assert upstream.sent == ["count", "data"]


async def test_an_error_of_the_count_passes_as_raised_and_nothing_is_fetched() -> None:
    refused = RateLimitError("429 from GET /v1/count: slow down", source="example")
    fetched: list[str] = []

    async def count() -> int:
        raise refused

    async def fetch() -> list[str]:
        fetched.append("data")
        return []

    with pytest.raises(RateLimitError) as info:
        await fetch_counted(count, fetch, limit=10, empty=[], narrow=NARROW)
    assert info.value is refused
    assert fetched == []


async def test_an_error_of_the_data_request_passes_as_raised() -> None:
    """Upstream's own refusal, as a source's classify maps it, is not the runner's to word."""
    refused = QueryTooLarge(None, limit=50_000, narrow=NARROW, source="example")

    async def count() -> int:
        return 10

    async def fetch() -> list[str]:
        raise refused

    with pytest.raises(QueryTooLarge) as info:
        await fetch_counted(count, fetch, limit=50_000, empty=[], narrow="Not this one.")
    assert info.value is refused
    assert info.value.count is None


@pytest.mark.parametrize(
    "answer",
    [1234.0, 12.5, True, "12", None, Decimal("12")],
    ids=["whole-float", "fraction", "bool", "text", "none", "decimal"],
)
async def test_a_count_that_is_no_int_is_the_source_s_fault(answer: object) -> None:
    """An upstream that counts with a float: its source reads it into an int first."""
    upstream = Upstream(answer)
    with pytest.raises(TypeError) as info:
        await fetch_counted(upstream.count, upstream.fetch, limit=100, empty=[], narrow=NARROW)
    assert repr(answer) in str(info.value)
    assert type(answer).__name__ in str(info.value)
    assert upstream.sent == ["count"]  # nothing fetched on a count the runner cannot read


async def test_a_negative_count_is_the_source_s_fault() -> None:
    upstream = Upstream(-1)
    with pytest.raises(ValueError, match="-1"):
        await fetch_counted(upstream.count, upstream.fetch, limit=100, empty=[], narrow=NARROW)
    assert upstream.sent == ["count"]


async def test_a_limit_below_1_is_refused_before_the_count() -> None:
    upstream = Upstream(0)
    with pytest.raises(ValueError, match="limit"):
        await fetch_counted(upstream.count, upstream.fetch, limit=0, empty=[], narrow=NARROW)
    assert upstream.sent == []
