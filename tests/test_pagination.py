from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import cast

import pytest

from xippios.core.errors import QueryTooLarge, RateLimitError
from xippios.core.pagination import collect, fetch_counted, paginate_offset

pytestmark = pytest.mark.anyio


async def test_a_page_numbered_endpoint_maps_the_offset_to_its_page() -> None:
    pages: list[int] = []

    async def fetch(offset: int) -> Sequence[int]:
        page = 1 + offset // 3  # the docstring's mapping, first page 1
        pages.append(page)
        return list(range((page - 1) * 3, min(page * 3, 7)))

    assert await collect(paginate_offset(fetch, page_size=3)) == list(range(7))
    assert pages == [1, 2, 3]  # the short third page ends it


async def test_collect_limit() -> None:
    async def gen() -> AsyncIterator[int]:
        for i in range(10):
            yield i

    assert await collect(gen(), limit=3) == [0, 1, 2]
    assert await collect(gen(), limit=0) == []


async def test_page_size_validation() -> None:
    async def fetch(offset: int) -> Sequence[int]:
        return []

    with pytest.raises(ValueError, match="page_size"):
        await collect(paginate_offset(fetch, page_size=0))


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
    assert (info.value.narrow, info.value.bound, info.value.source) == (NARROW, False, "example")
    assert info.value.request is None  # refused before the data request: it names none
    assert str(info.value) == (
        "query would return 5,006,385 records; upstream serves at most 100,000 per call. " + NARROW
    )
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
    """sdk-faostat's upstream counts with a float: its source reads it into an int first."""
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
