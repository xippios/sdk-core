from collections.abc import AsyncIterator, Sequence

import pytest

from xippios.core.pagination import collect, paginate_cursor, paginate_offset, paginate_pages

pytestmark = pytest.mark.anyio


async def test_offset_stops_on_short_page() -> None:
    calls: list[int] = []

    async def fetch(offset: int) -> Sequence[int]:
        calls.append(offset)
        return list(range(offset, min(offset + 3, 7)))

    assert await collect(paginate_offset(fetch, page_size=3)) == list(range(7))
    assert calls == [0, 3, 6]


async def test_offset_respects_max_items_without_extra_fetch() -> None:
    calls: list[int] = []

    async def fetch(offset: int) -> Sequence[int]:
        calls.append(offset)
        return list(range(offset, offset + 3))

    assert await collect(paginate_offset(fetch, page_size=3, max_items=4)) == [0, 1, 2, 3]
    assert calls == [0, 3]


async def test_offset_exact_multiple_fetches_one_empty_page() -> None:
    async def fetch(offset: int) -> Sequence[int]:
        return list(range(offset, min(offset + 2, 4)))

    assert await collect(paginate_offset(fetch, page_size=2)) == [0, 1, 2, 3]


async def test_pages_start_at_one() -> None:
    calls: list[int] = []

    async def fetch(number: int) -> Sequence[str]:
        calls.append(number)
        return ["a", "b"] if number < 3 else ["c"]

    assert await collect(paginate_pages(fetch, page_size=2)) == ["a", "b", "a", "b", "c"]
    assert calls == [1, 2, 3]


async def test_cursor_until_none() -> None:
    pages = {None: (["a"], "c1"), "c1": (["b"], "c2"), "c2": (["c"], None)}

    async def fetch(cursor: str | None) -> tuple[Sequence[str], str | None]:
        return pages[cursor]

    assert await collect(paginate_cursor(fetch)) == ["a", "b", "c"]


async def test_cursor_guards_against_repeating_cursor() -> None:
    async def fetch(cursor: str | None) -> tuple[Sequence[str], str | None]:
        return (["x"], "same")

    assert await collect(paginate_cursor(fetch)) == ["x", "x"]


async def test_cursor_max_items() -> None:
    async def fetch(cursor: str | None) -> tuple[Sequence[int], str | None]:
        return ([1, 2, 3], "next")

    assert await collect(paginate_cursor(fetch, max_items=5)) == [1, 2, 3, 1, 2]


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
