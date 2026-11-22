- `Ceiling(most, *, unit, mcp=None, option=None, help=None, source=None)` declares the ceiling
  of a period series once, and its `check` refuses a range over the ceiling in force before the
  first request, naming the range, the ceiling and its unit and, below `most`, the option that
  raises it, then saying that nothing was sent, before its advice, and its `add_options` and
  `apply_options` are a tool set's two hooks for `main`. `fetch_periods(periods, fetch, *,
  skip=())` sends one request per period in the order given, passes over a period whose fetch
  raises one of `skip`, and returns the periods with their answers for the task to assemble,
  its vintage included. When a fetch after the first fails, it returns nothing and raises the
  same error, its message naming the periods answered before it by their count, the first and
  the last.
  (ADR-0054, §4, https://github.com/xippios/sdk-core/issues/315,
  https://github.com/xippios/sdk-core/issues/438)
  - Hand-apply: `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — the ceiling of
    `_series_range` → `Ceiling(10, unit="market years", source=SOURCE)` and its `check`, and
    the loop of `get_weekly_series` → `fetch_periods(..., skip=(NoDataForYear,))`, the order
    of the range and the release list kept — the copy core now holds.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — the ceiling of `get_time_series` →
    `Ceiling(100, unit="market years", source=SOURCE)` and its `check`, and its loop →
    `fetch_periods(..., skip=(NoDataForYear,))` — the copy core now holds.
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) — `series_ceiling`, `set_series_ceiling`,
    `mcp_add_options`, `mcp_apply_options` and the span check of `_series_months` → one
    `Ceiling(60, unit="months", mcp=24, option="--series-months", help=..., source=SOURCE)`,
    its two hooks under the two names, and the month loop of `_series` → `fetch_periods` over
    the month codes — the copy core now holds, and the removal of `series_ceiling` and
    `set_series_ceiling`, which its changelog and its README name, breaks a caller's call, so
    it takes a `breaking` entry and a minor (§12) unless the port keeps the two names.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — `split_ceiling`, `set_split_ceiling`,
    `mcp_add_options`, `mcp_apply_options` and the check of `_split_by_year` → one
    `Ceiling(20, unit="years", mcp=5, option="--split-years", help=..., source=SOURCE)`, its
    two hooks under the two names, and its two passes → `fetch_periods` — the copy core now
    holds, and the removal of `split_ceiling` and `set_split_ceiling`, which its 0.2.0 entry
    named, breaks a caller's call, so it takes a `breaking` entry and a minor (§12) unless the
    port keeps the two names (https://github.com/xippios/sdk-usda-nass/issues/86).
    `tests/test_tasks.py` (sdk-usda-gats, sdk-usda-nass) — the refusal of a range over the
    ceiling, the setter's refusal and the option's help → core's wording, the class
    `InvalidRequestError` and the option's name unchanged — the refusals are core's wording
    now.
    `tests/test_slices.py` (sdk-usda-esr, sdk-usda-psd) — the refusals of a range over the
    ceiling → core's wording, the class `InvalidRequestError` unchanged, and the test that
    lowers the ceiling by patching `SERIES_MAX_YEARS`, sdk-usda-esr's
    `test_the_ceiling_counts_market_years_ends_included` and sdk-usda-psd's
    `test_a_series_may_span_exactly_the_bound`, sets the `Ceiling` instead, neither source
    having a setter or an option — the refusals are core's wording now, and the `Ceiling`
    reads no module constant (https://github.com/xippios/sdk-usda-esr/issues/59).
