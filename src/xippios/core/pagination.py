"""The helpers of a fetch that task functions compose: one walk of pages and a count first.

``fetch_pages`` collects the items of an offset-paginated endpoint, a page-numbered one
included, and refuses once it needs more pages than its bound (ADR-0034, amendment
2026-11-24), and ``fetch_counted`` counts a query's records before it fetches them, so a
query over upstream's limit is refused before its data request (ADR-0053). Task functions
drive them and build the ``Result`` themselves; the sync facade comes from
``xippios.core.sync``.
"""

import math
from collections.abc import Awaitable, Callable, Hashable, Sequence

from xippios.core.errors import InvalidRequestError, QueryTooLarge

__all__ = ["fetch_counted", "fetch_pages"]


async def fetch_pages[T](
    fetch: Callable[[int], Awaitable[tuple[Sequence[T], int | None]]],
    *,
    page_size: int,
    most: int,
    paging: str,
    start: int = 0,
    stop: Callable[[Sequence[T]], bool] | None = None,
    key: Callable[[T], Hashable] | None = None,
    source: str | None = None,
) -> tuple[list[T], int | None]:
    """Collect every page of an offset-paginated list, or refuse past the bound with nothing.

    ``fetch(offset)`` sends the request of one page and answers the page's items with
    upstream's count of the records matching the request, ``None`` where upstream sends no
    count. The walk starts at ``start``, advances by the items each page held, and ends on a
    page shorter than ``page_size``, before any request at or past upstream's count, or after
    the page that ``stop`` marks. A page-numbered endpoint maps the offset to its page inside
    ``fetch``, the page being ``first_page + offset // page_size``::

        async def fetch(offset: int) -> tuple[list[Region], int | None]:
            answer = await api.list_regions(page=offset // PAGE_SIZE, per_page=PAGE_SIZE)
            return answer.data, answer.total  # pages 0, 1, 2, ... and upstream's count

        regions, total = await fetch_pages(fetch, page_size=PAGE_SIZE, most=24, paging="page")

    ``most`` is the bound: the most pages, so the most requests, that one call fetches, which
    the task states as the most requests one call spends (ADR-0061, decision 8). The client
    tries each request up to ``RetryPolicy.max_attempts`` times, so with retries counted one
    call spends at most ``most`` times that, 96 attempts for 24 pages at the default of 4.
    Without ``stop``, the walk refuses as soon as upstream's count shows that the pages from
    ``start`` are more than ``most``, after the first page; with ``stop``, or without a
    count, it refuses where it has fetched ``most`` pages and needs another. It then raises
    ``InvalidRequestError`` and returns nothing, and the message names the bound, upstream's
    count with its total of pages, the page the walk reached, counted from 1 in upstream's
    whole list, the requests it sent and ``paging``, the task's argument that fetches one
    page::

        the walk needs more than the 24 pages that one call fetches: upstream counts 703
        records on 29 pages of 25, and the walk reached page 1 of 29 after 1 request. It
        returns nothing; pass page to fetch one page at a time.

    ``stop`` has one consumer, the source that ADR-0034's amendment of 2026-11-24 names, and
    ``key`` none yet; both are built, since nothing leaves by the count alone (ADR-0059,
    decision 6).

    Args:
        fetch: Async function taking the offset and returning one page's items with
            upstream's count, e.g. ``(answer.data, answer.total)``.
        page_size: Items requested per page, e.g. ``100``; a shorter page ends the walk.
        most: The most pages that one call fetches, the task's bound of requests, e.g.
            ``24``.
        paging: The task's argument that fetches one page, as the refusal names it, e.g.
            ``"page"`` or ``"start with limit"``.
        start: The offset of the first item, ``0`` by default.
        stop: Takes each page's items and answers ``True`` where that page is the last one
            the task wants, e.g. one that reaches back before its ``since``; ``None``, the
            default, walks to the end.
        key: Takes an item and answers what tells it apart, e.g. ``lambda row: row.id``; an
            item whose key an earlier item had is dropped, as a list that changes between two
            requests repeats one. ``None``, the default, keeps every item.
        source: Source slug the refusal carries, e.g. ``"example"``.

    Returns:
        The items in upstream's order and the count upstream answered on the last page
        fetched, which the task sets as ``meta.total`` (ADR-0034, decision 2).

    Raises:
        InvalidRequestError: The walk needs more pages than ``most``; nothing is returned.
        ValueError: ``page_size`` or ``most`` is below 1, raised before any request.
    """
    if page_size < 1:
        raise ValueError(f"page_size must be at least 1, not {page_size!r}")
    if most < 1:
        raise ValueError(f"most must be at least 1, not {most!r}")
    items: list[T] = []
    seen: set[Hashable] = set()
    offset = start
    sent = 0
    while True:
        page, count = await fetch(offset)
        sent += 1
        reached = offset // page_size + 1
        for item in page:
            if key is not None:
                if (mark := key(item)) in seen:
                    continue
                seen.add(mark)
            items.append(item)
        offset += len(page)
        if len(page) < page_size or (count is not None and offset >= count):
            return items, count
        if stop is not None and stop(page):
            return items, count
        left = None if count is None else math.ceil((count - offset) / page_size)
        if sent >= most or (stop is None and left is not None and sent + left > most):
            raise _beyond(most, count, page_size, reached, sent, paging, source)


def _beyond(
    most: int,
    count: int | None,
    page_size: int,
    reached: int,
    sent: int,
    paging: str,
    source: str | None,
) -> InvalidRequestError:
    """The walk's refusal at its bound, which names what a caller needs to page on purpose."""
    requests = f"{sent:,} request{'' if sent == 1 else 's'}"
    bound = f"{most:,} page{'' if most == 1 else 's'}"
    if count is None:
        where = (
            "upstream sends no count of its records, so its total of pages is unknown, and the "
            f"walk reached page {reached:,} after {requests}"
        )
    else:
        pages = math.ceil(count / page_size)
        where = (
            f"upstream counts {count:,} records on {pages:,} pages of {page_size:,}, and the "
            f"walk reached page {reached:,} of {pages:,} after {requests}"
        )
    return InvalidRequestError(
        f"the walk needs more than the {bound} that one call fetches: {where}. It "
        f"returns nothing; pass {paging} to fetch one page at a time.",
        source=source,
    )


async def fetch_counted[T, E](
    count: Callable[[], Awaitable[int]],
    fetch: Callable[[], Awaitable[T]],
    *,
    limit: int,
    empty: E,
    narrow: str,
    source: str | None = None,
) -> tuple[T | E, int]:
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
        The data and the count, and ``(empty, 0)`` for a count of 0. ``empty`` is typed apart
        from the data, so ``empty=[]`` beside a ``fetch`` of ``list[Record]`` gives
        ``list[Record]`` under mypy, which one type for both would infer as ``list[Never]``.

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
