- `fetch_pages` is the one walk of offset pages and takes the place of `paginate_offset` with
  `collect`, which leave with their `max_items` and `limit`: its `fetch` answers a page's items
  with upstream's count, it sends no request at or past that count, and it refuses with
  `InvalidRequestError` and returns nothing once it needs more pages than its bound `most`. The
  refusal names the count, the bound, the task's paging argument, the requests sent, the page
  reached and the total of pages, and a stop rule and a key that drops a repeated item come
  with the walk, the first with one consumer and the second with none yet.
  (ADR-0034, ADR-0061, ADR-0059, §4, https://github.com/xippios/sdk-core/issues/480)
  - Hand-apply: `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — `_offset_pages` collects
    through `fetch_pages(fetch, page_size=PAGE_SIZE, most=..., paging="start with limit",
    source=SOURCE)`, its `fetch` answering `(page.data, page.total)`, so that its list of totals
    and its guard past the count leave while its branch for one page stays, about 36 lines
    less, and `list_journal_entries`, `list_persons`, `list_orders` and `list_history`, the four
    tasks that call it, state the bound in their docstrings and their tools' notes, while the
    module docstring's paragraph on the lists (lines 28 to 39 on its `main`) and the `limit` of
    `_offset_pages`'s docstring (lines 299 and 300) name `fetch_pages` and the bound in place of
    `paginate_offset` — every test that imports `tasks.py` fails at the import of `collect` and
    `paginate_offset` until the port stands, and the walk's tests of `tests/test_tasks.py`,
    among them `test_collecting_stops_at_upstreams_total_without_a_further_request` and
    `test_the_count_kept_is_the_last_pages_and_never_corrected`, pass after it unchanged, and no
    test reads the two docstrings.
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — `_Pages` leaves, about 40 lines, and
    `search_publications`, `list_releases` and `list_recent_releases` call `fetch_pages` with a
    `fetch` that sends the page `offset // PAGE_SIZE` and answers `(answer.results,
    _total(answer.pager))`, with `paging="page"` and a bound each, the two release lists passing
    `older_than_since` and `_newest_before(since)` as `stop=`, typed over `Sequence[Release]`,
    only where `since` is given, so that a walk without it is refused by the count after its
    first page, as `list_releases` for WASDE's 703 releases on 29 pages is where the bound is two
    dozen, and the module docstring's item on paging (lines 35 and 36 on its `main`) names
    `fetch_pages` and the bound in place of `_Pages`, whose docstring (lines 205 to 243) leaves
    with it — every test that imports `tasks.py` fails at the import of `collect` and
    `paginate_offset` until the port stands, and
    `test_the_walk_stops_at_total_pages_without_a_request_past_it` calls `tasks._Pages` and is
    written again on `fetch_pages`, and no test reads the module docstring.
    `CLAUDE.md` (sdk-usda-esmis) — the item Tasks of ESMIS specifics (lines 267 to 274 on its
    `main`) says that a paged task without `page` walks with core's `fetch_pages`, under its
    bound and upstream's count and with the two release lists' stop rules, in place of
    `tasks._Pages` with core's `paginate_offset` and `pager.total_pages` — no test breaks, and
    the review holds it.
    `src/xippios/usda/wasde/tasks.py` (sdk-usda-wasde) — `list_releases` without `since` meets
    that refusal of sdk-usda-esmis's walk, so its docstring's 29 requests and the note of its
    tool name the bound and `since`, and `get_release` words its own refusal of a month older
    than the bound's pages reach back to, since the walk's refusal names esmis's `page`, which
    `get_release` does not take — no test breaks offline, since
    `test_list_releases_re_shapes_esmis_releases` walks one page.
