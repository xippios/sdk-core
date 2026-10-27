from collections.abc import AsyncIterator, Sequence

import pytest

from xippios.core.pagination import collect, paginate_offset

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
