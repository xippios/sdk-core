"""The helpers of a fetch that task functions compose: offset paging and a count first.

``paginate_offset`` is an async generator over the items of an offset-paginated endpoint, a
page-numbered one included, and ``fetch_counted`` counts a query's records before it fetches
them, so a query over upstream's limit is refused before its data request (ADR-0053). Task
functions drive them and build the ``Result`` themselves; the sync facade comes from
``xippios.core.sync``.
"""

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Sequence

from xippios.core.errors import QueryTooLarge

__all__ = ["collect", "fetch_counted", "paginate_offset"]


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


async def fetch_counted[T](
    count: Callable[[], Awaitable[int]],
    fetch: Callable[[], Awaitable[T]],
    *,
    limit: int,
    empty: T,
    narrow: str,
    source: str | None = None,
) -> tuple[T, int]:
    """Count a query's records, then fetch them only when upstream serves them in one call.

    For an upstream that counts a query's records on request and serves at most ``limit`` of
    them per call (ADR-0053). A count of 0 returns the task's ``empty`` answer without the data
    request, a count over ``limit`` raises ``QueryTooLarge`` before it, and any other count,
    ``limit`` itself included, fetches. The count comes back beside the data: it is upstream's
    count of the records matching the request, which the task sets as ``meta.total``
    (conventions §4)::

        async def count() -> int:
            return (await api.get_count(**request)).count  # read as an int by its model

        async def fetch() -> list[Record]:
            return (await api.get(**request)).data

        rows, total = await fetch_counted(
            count, fetch, limit=RECORD_LIMIT, empty=[], narrow=NARROW, source=SOURCE
        )
        meta = ResultMeta(source=SOURCE, endpoint=ENDPOINT, request=request, total=total)

    An error that ``count`` or ``fetch`` raises passes as raised, upstream's own refusal of the
    query that a source's ``classify`` maps to ``QueryTooLarge`` included.

    Args:
        count: Async function of no argument that sends the count request and returns
            upstream's count, an ``int`` the source read from upstream's answer.
        fetch: Async function of no argument that sends the data request and returns the
            data.
        limit: The most records upstream serves per call, e.g. ``100_000``.
        empty: The task's answer to a query that nothing matches, e.g. ``[]``.
        narrow: What narrows the query, the sentences that end the refusal, e.g.
            ``"Split by period, then by reporter."``.
        source: Source slug the refusal carries, e.g. ``"comtrade"``.

    Returns:
        The data and the count, and ``(empty, 0)`` for a count of 0.

    Raises:
        QueryTooLarge: The count is over ``limit``; the data was not requested.
        TypeError: ``count`` gave no ``int``: a float, a whole one such as ``1234.0``
            included, or a ``bool``. A fault of the source's code, which reads upstream's
            count into an ``int`` where it parses the answer, as a pydantic ``int`` field
            reads ``1234.0`` and refuses ``1234.5``.
        ValueError: ``limit`` is below 1, raised before the count, or ``count`` gave a
            negative number.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, not {limit!r}")
    counted: object = await count()
    if isinstance(counted, bool) or not isinstance(counted, int):
        raise TypeError(
            f"count() gave {counted!r} ({type(counted).__name__}), and the runner takes "
            "upstream's count as an int: read it into an int where the answer is parsed"
        )
    if counted < 0:
        raise ValueError(f"count() gave {counted!r}, and a count of records is 0 or more")
    if counted == 0:
        return empty, 0
    if counted > limit:
        raise QueryTooLarge(counted, limit=limit, narrow=narrow, source=source)
    return await fetch(), counted
