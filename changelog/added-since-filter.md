- `newer_than(since, items, *, released, read)` keeps the items released strictly later than a
  `since` that takes back a `meta.vintage`, read by the source's reader of its vintage text, and
  `naive_time` is core's reader of a release time printed without a zone, a date alone its
  midnight, which refuses a zone and an unreadable text with `InvalidRequestError`. The task
  still sets `meta.vintage` and `meta.published_at` from the whole answer and reads `since`
  before its request. An item without a release time is kept, since it cannot be shown to be
  no newer.
  (ADR-0052, §4, https://github.com/xippios/sdk-core/issues/318)
  - Hand-apply: `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — `_since` and `_SINCE_EXAMPLE`
    → `read_since = partial(naive_time, source=SOURCE)`, called on `since` before the
    request, and the filter of `get_release_dates` → `newer_than(since, releases,
    released=lambda release: release.release_time_stamp, read=read_since)` — the copy core
    now holds.
    `tests/test_tasks.py` (sdk-usda-esr) — the prefix that
    `test_since_is_refused_before_the_request` and `test_release_dates_since_over_mcp` assert
    → core's, `since must be the meta.vintage text of an earlier call, an ISO date and time
    without a time zone such as '2026-10-06T08:00:00'`, in place of the prefix that names
    `get_release_dates` and ESR's example, the class still `InvalidRequestError` and the
    reasons `it is not an ISO date and time` and `it carries a time zone` kept — the refusal
    is core's wording now.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — the `since` test in the filter of
    `get_release_dates` and the all-or-nothing check of `get_latest_release` →
    `newer_than(since, ..., released=_release, read=validate_since)`, with `validate_since`
    still called before the request — the copy core now holds, its wording unchanged.
