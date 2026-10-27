"""Offset iteration that task functions compose, a page-numbered endpoint included.

The helper is an async generator over items. Task functions drive it and build the
``Result`` themselves; the sync facade comes from ``xippios.core.sync``.
"""

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Sequence

__all__ = ["collect", "paginate_offset"]


async def paginate_offset[T](
    fetch: Callable[[int], Awaitable[Sequence[T]]],
    *,
    page_size: int,
    start: int = 0,
    max_items: int | None = None,
) -> AsyncIterator[T]:
    """Yield items from an offset-paginated endpoint until a short page arrives.

    A page-numbered endpoint maps the offset to its page inside ``fetch``: the offset
    advances by a full page until the short last one, so the page is
    ``first_page + offset // page_size``::

        async def fetch(offset: int) -> list[Row]:
            page = 1 + offset // PAGE_SIZE  # pages 1, 2, 3, ...
            return await list_rows(page=page, per_page=PAGE_SIZE)

        rows = await collect(paginate_offset(fetch, page_size=PAGE_SIZE))

    Args:
        fetch: Async function taking the offset and returning one page of items.
        page_size: Items requested per page, e.g. ``100``; a page shorter than this ends
            iteration.
        start: First offset, usually 0.
        max_items: Stop after this many items, e.g. ``500``; ``None`` yields everything.

    Raises:
        ValueError: ``page_size`` is below 1.
    """
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
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
