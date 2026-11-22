- `QueryTooLarge(count, *, limit, narrow, bound=False, source=None)`, an `InvalidRequestError`,
  refuses a query over upstream's per-call record limit, and core words its message from the
  count, the limit and what narrows the query. `fetch_counted(count, fetch, *, limit, empty,
  narrow, source=None)` sends the count first, answers a count of 0 with the task's empty answer
  and no data request, refuses a count over the limit before the data request and returns the
  data with the count, for `meta.total`. A count that is no `int`, a float such as `1234.0`
  included, raises `TypeError`, a fault of the source's code, which reads upstream's count into
  an `int`.
  (ADR-0053, §5, https://github.com/xippios/sdk-core/issues/317)
  - Hand-apply: `src/xippios/comtrade/errors.py` (sdk-comtrade) — `QueryTooLarge` deleted,
    `RECORD_LIMIT` and `MAX_PERIODS` kept, and its two pieces of advice kept as the texts its
    tasks pass as `narrow` — core's class now.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — the gate of `get_data` →
    `fetch_counted(count, fetch, limit=RECORD_LIMIT, empty=[], narrow=..., source=SOURCE)`,
    which may set `meta.total` from the count, and `_bounded` → core's `QueryTooLarge(bound,
    limit=RECORD_LIMIT, narrow=..., bound=True, source=SOURCE)` — the copy core now holds.
    `tests/test_tasks.py` (sdk-comtrade) — `test_query_too_large_is_an_invalid_request_for_http_too`
    and `test_a_refusal_that_names_another_task_names_a_served_tool` build the error with
    `limit=` and `narrow=`, and the import of `QueryTooLarge` comes from `xippios.core` — the
    class takes core's arguments.
    `src/xippios/usda/nass/errors.py` (sdk-usda-nass) — `QueryTooLarge` → a subclass of core's
    that keeps `year` and words it in `narrow`, its signature `(count, *, year=None)` unchanged
    — core words the message.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — the gate of `get_data` → `fetch_counted`
    in a `try` whose `except QueryTooLarge` raises an error with a count of `None`, upstream's
    413 from the data request, as it is, and otherwise raises the subclass for the whole query
    or for one year, or splits by year — the copy core now holds.
    `tests/test_tasks.py` (sdk-usda-nass) — the prefix that
    `test_split_refuses_a_year_over_the_limit_before_fetching` asserts → core's `query would
    return 57,873,464 records`, the year named in `narrow` — core words the message.
    `src/xippios/eurostat/_client.py` (sdk-eurostat) — its patch decides whether `classify`
    maps upstream's refusal over its limit to `QueryTooLarge` with the count and the limit read
    from upstream's own refusal, or a task raises it before the request with `bound=True` from
    an estimate read from its arguments, and it takes no runner — it cannot count before it
    asks.
    `src/xippios/faostat/tasks.py` (sdk-faostat) — its patch decides whether `get_data` counts
    with `no_records=true`, its float read into an `int`, against a limit of its own — its
    upstream has no limit, and the runner takes an `int`.
