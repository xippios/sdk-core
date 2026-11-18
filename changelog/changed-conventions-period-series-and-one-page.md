- Conventions §4 reads the period-series rules for an upstream with no release calendar,
  a task that fetches one period, a split mode of a free-form query and the note on a
  series tool's ceiling, which counts the upstream calls one tool call spends. A
  paginated task over a list unbounded by nature or a metered upstream may return one
  upstream page per call, its cursor on its data, and collect nothing.
  (ADR-0012, ADR-0022, §4, https://github.com/xippios/sdk-core/issues/136,
  https://github.com/xippios/sdk-core/issues/238,
  https://github.com/xippios/sdk-core/issues/177)
  - Hand-apply: `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — the docstrings of
    `get_exports`, `get_latest_week` and `get_top_destinations` say that an empty list
    may be a market year not yet released — they answer one market year without reading
    the release list, and ESR answers an unreleased year with `[]`.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — the docstring of each task that
    fetches one year says that an empty answer may be a year not yet released — Quick
    Stats names no release.
