- `ResultCap(paged=True)` gives an MCP tool the adapter's own `offset`, the rows of the answer
  already shown, so the task runs again and the note of a cut answer names the call for the
  next rows, `continue with offset=200`. `ResultCap(keep="last")` keeps the newest rows of a
  series ordered oldest first, and its `offset` counts from the last row, so a continuation
  walks to older rows. Both default to what every cap does today, a tool without them
  declares no `offset` and writes its notes as before, and a write task or a task that takes
  `offset` itself is refused a paged cap.
  (ADR-0047, §8, https://github.com/xippios/sdk-core/issues/314)
  - Hand-apply: `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — `paged=True` in `MCP_CAPS`
    for `list_accounts`, `list_cost_centers`, `list_custom_fields` and the other lists that
    upstream returns whole, the four lists that record `start` left as they are — their cut
    lists reach the last row over MCP (https://github.com/xippios/sdk-cashctrl/issues/87).
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `paged=True` in `MCP_CAPS` for
    `get_world_trade`, `get_data`, `get_data_availability`, `get_bilateral_data` and
    `get_mirror_flows` — each cut answer reaches its last row
    (https://github.com/xippios/sdk-comtrade/issues/35).
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — `paged=True, keep="last"` for
    `get_series`, and `paged=True` for `get_data` where its answer is a list of rows or a
    model of one list — a series shows its latest period first
    (https://github.com/xippios/sdk-eurostat/issues/51).
    `src/xippios/faostat/tasks.py` (sdk-faostat) — `paged=True` for `get_data`, `list_items`
    and the other list tools, `keep="last"` for `get_series` — the notes that named
    `page_number` or a raised bound shrink to the filters
    (https://github.com/xippios/sdk-faostat/issues/32).
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — no entry, since `get_thread` keeps
    its `start` and `get_message` is one record, which a paged cap does not reach — its notes
    stay as they read (https://github.com/xippios/sdk-google-mail/issues/38).
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — `paged=True` for
    `list_publications`, which reads the packaged table, the three tools that take `page`
    left as they are — all 2,008 rows of one agency are reachable
    (https://github.com/xippios/sdk-usda-esmis/issues/34).
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — `paged=True, keep="last"` for
    `get_exports`, whose every-country answer is one request, and `keep="last"` alone for
    `get_weekly_series`, which stays unpaged since a second run spends one request per market
    year, up to 11 — the newest weeks come first
    (https://github.com/xippios/sdk-usda-esr/issues/28).
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) — `paged=True` for the sixteen cut tools
    its issue counts, `get_census_exports` among them, and `keep="last"` for the three series
    tools — each continuation downloads the answer again, since no data answer is cached
    (https://github.com/xippios/sdk-usda-gats/issues/32).
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — `paged=True` for `list_param_values`,
    nine of whose lists are packaged and the rest one keyed call, `get_data` left unpaged,
    whose second run split by year spends up to 41 keyed calls that are never cached, and
    `get_county_yield`, `get_county_production` and `get_census_farms` paged only where one
    run is one keyed call — a list past 1,000 values reaches its last value
    (https://github.com/xippios/sdk-usda-nass/issues/55).
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — `paged=True` for `get_latest_release`,
    `get_data`, `get_release_dates` and `get_time_series`, and `keep="last"` for the two
    ordered oldest first where the patch keeps the newest — every cut answer reaches its last
    row (https://github.com/xippios/sdk-usda-psd/issues/31).
    `src/xippios/x/tasks.py` (sdk-x) — no entry, since X bills every page that a second run
    fetches, and a page with two lists stays a preview — its notes stay as they read
    (https://github.com/xippios/sdk-x/issues/35).
