"""Page and cursor iteration helpers that task functions compose.

Each helper is an async generator over items. Task functions drive them and build
the ``Result`` themselves; the sync facade comes from ``xippios.core.sync``.
"""

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Sequence

__all__ = ["collect", "paginate_cursor", "paginate_offset", "paginate_pages"]


def _check_page_size(page_size: int) -> None:
    if page_size < 1:
        raise ValueError("page_size must be at least 1")


async def paginate_offset[T](
    fetch: Callable[[int], Awaitable[Sequence[T]]],
    *,
    page_size: int,
    start: int = 0,
    max_items: int | None = None,
) -> AsyncIterator[T]:
    """Yield items from an offset-paginated endpoint until a short page arrives.

    Args:
        fetch: Async function taking the offset and returning one page of items.
        page_size: Items requested per page; a page shorter than this ends iteration.
        start: First offset, usually 0.
        max_items: Stop after this many items; ``None`` yields everything.
    """
    _check_page_size(page_size)
    offset = start
    yielded = 0
    while max_items is None or yielded < max_items:
        page = await fetch(offset)
        for item in page:
            if max_items is not None and yielded >= max_items:
                return
            yield item
            yielded += 1
        if len(page) < page_size:
            return
        offset += len(page)


async def paginate_pages[T](
    fetch: Callable[[int], Awaitable[Sequence[T]]],
    *,
    page_size: int,
    start: int = 1,
    max_items: int | None = None,
) -> AsyncIterator[T]:
    """Yield items from a page-numbered endpoint until a short page arrives.

    Args:
        fetch: Async function taking the page number and returning one page of items.
        page_size: Items requested per page; a page shorter than this ends iteration.
        start: First page number, usually 1.
        max_items: Stop after this many items; ``None`` yields everything.
    """
    _check_page_size(page_size)
    number = start
    yielded = 0
    while max_items is None or yielded < max_items:
        page = await fetch(number)
        for item in page:
            if max_items is not None and yielded >= max_items:
                return
            yield item
            yielded += 1
        if len(page) < page_size:
            return
        number += 1


async def paginate_cursor[T](
    fetch: Callable[[str | None], Awaitable[tuple[Sequence[T], str | None]]],
    *,
    max_items: int | None = None,
) -> AsyncIterator[T]:
    """Yield items from a cursor-paginated endpoint until no cursor is returned.

    Args:
        fetch: Async function taking the cursor (``None`` first) and returning the page
            and the next cursor, or ``None`` when there is no further page.
        max_items: Stop after this many items; ``None`` yields everything.
    """
    cursor: str | None = None
    yielded = 0
    while max_items is None or yielded < max_items:
        page, next_cursor = await fetch(cursor)
        for item in page:
            if max_items is not None and yielded >= max_items:
                return
            yield item
            yielded += 1
        if next_cursor is None or next_cursor == cursor:
            return
        cursor = next_cursor


async def collect[T](items: AsyncIterable[T], *, limit: int | None = None) -> list[T]:
    """Drain an async iterable into a list, optionally stopping after ``limit`` items."""
    out: list[T] = []
    if limit is not None and limit <= 0:
        return out
    async for item in items:
        out.append(item)
        if limit is not None and len(out) >= limit:
            break
    return out
