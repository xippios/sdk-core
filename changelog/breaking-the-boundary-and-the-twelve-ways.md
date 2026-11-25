- Two records state what a source package returns and how each feature works in every source:
  ADR-0060, the boundary of a source package in six sentences, which conventions §14 hold word
  for word, with the four rules of a record that a package shapes itself, and ADR-0061, the one
  way of each of twelve features, each rule standing once in the section of its subject. The
  family check gains two tests that hold a source from its adoption of 0.5.0,
  `test_family_read_tasks_start_with_a_read_verb`, a read task named `list_`, `get_`, `search_`,
  `count_` or `download_`, and `test_family_readings_stand_beside_their_text`, a reading
  `<stem>_number` or `<stem>_label` beside the text field of its stem. ADR-0028, ADR-0001,
  ADR-0020, ADR-0034, ADR-0041, ADR-0047 and ADR-0011 each take one sentence that points to them.
  (ADR-0060, ADR-0061, §1, §2, §3, §4, §5, §6, §8, §10, §14,
  https://github.com/xippios/sdk-core/issues/474)
  - Hand-apply: `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — `export_accounts`,
    `export_journal_entries`, `export_orders` and `export_persons`, which write a file to
    `dest`, renamed `download_accounts`, `download_journal_entries`, `download_orders` and
    `download_persons`, their tools with them, and the problems that `_check_list_arguments`,
    `_report_problems` with `_refuse` and `_check_report_file` gather raised at the first one
    — `test_family_read_tasks_start_with_a_read_verb` fails on each of the four, and
    `tests/test_tasks.py::test_every_problem_is_named_at_once` asserts the joined message
    (ADR-0061, decisions 3 and 7).
    `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — `_refuse` and its `_check_*` and
    `_choices` helpers raise at the first problem —
    `tests/test_tasks_write.py::test_an_update_refuses_its_arguments_before_any_request`,
    `test_update_order_refuses_its_arguments_before_any_request` and
    `test_an_update_refuses_a_wrong_custom_name_before_the_read` assert every problem at once
    (ADR-0061, decision 7).
    `src/xippios/cashctrl/api/_form.py` (sdk-cashctrl) — `_custom_problems` names the first
    problem — the same three tests (ADR-0061, decision 7).
    `src/xippios/usda/wasde/tasks.py` (sdk-usda-wasde) — `read_report_text` renamed
    `get_report_text`, and `get_balance_sheet`, which picks the matrices of a commodity and a
    region for the caller from the packaged list, leaves with its entry of `MCP_CAPS` —
    `test_family_read_tasks_start_with_a_read_verb` fails on `read_report_text`, and the
    `test_*balance_sheet*` tests of `tests/test_tasks.py` and `test_get_balance_sheet_live`
    leave with the task (ADR-0061, decision 3, ADR-0060, decisions 4 and 8).
    `src/xippios/x/tasks.py` (sdk-x) — `lookup_users` renamed `get_users` —
    `test_family_read_tasks_start_with_a_read_verb` fails on `lookup_users`, and
    `tests/test_contract.py` names the tool (ADR-0061, decision 3).
    `src/xippios/<package>/__init__.py` (sdk-cashctrl, sdk-usda-wasde, sdk-x) — the renamed
    tasks re-exported under their new names — an import of an old name fails.
    `README.md` (sdk-cashctrl, sdk-usda-wasde, sdk-x, sdk-usda-nass, sdk-comtrade,
    sdk-eurostat, sdk-usda-psd, sdk-usda-esr) — the status table's rows follow each rename and
    each task that leaves — `test_family_readme_status_table_lists_the_tasks` fails on a stale
    row.
    `tests/test_live.py` (sdk-cashctrl, sdk-usda-wasde, sdk-x) and
    `tests/test_downloads.py` (sdk-cashctrl) — the renamed tasks called by their new names —
    each call of an old name fails.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — the thirteen slices of fixed filters over
    `api_GET` leave, `get_crop_progress`, `get_crop_condition`, `get_county_yield`,
    `get_county_production`, `get_acreage`, `get_acreage_forecasts`, `get_production_forecasts`,
    `get_production`, `get_prices_received`, `get_census_farms`, `get_livestock_inventory`,
    `get_milk_production` and `get_grain_stocks`, with `_slice`, `_weekly_series` and
    `_county_series`. `_split_by_year` sets no sum of its counts as `meta.total`, and
    `cv_percent` of the projected records keeps upstream's text with `cv_percent_number`
    beside it — the slices' tests of `tests/test_tasks.py` leave,
    `test_split_by_year_is_real_end_to_end` and the other split tests assert `meta.total`, and
    `test_census_farms_national` and the other `cv_percent` tests assert the number alone
    (ADR-0060, decisions 1, 4 and 8).
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — the slices `get_bilateral_flows`,
    `get_mirror_flows`, `get_world_trade` and `get_commodity_series` and the ranking
    `get_top_partners` leave, and the comma-separated texts of `get_data`, `get_counts` and the
    Tools tasks, `reporter_code`, `partner_code`, `partner2_code`, `period`, `cmd_code`,
    `flow_code`, `mot_code`, `customs_code` and `aggregate_by`, take lists — the slice and
    mirror tests of `tests/test_tasks.py` leave, and every test that passes a comma-separated
    text breaks (ADR-0060, decisions 4 and 8, ADR-0061, decision 1).
    `src/xippios/comtrade/params.py` (sdk-comtrade) — `SLICE_PINS`, `validate_slice` and
    `validate_mirror_flows` leave with the slices, and the other validators raise at the first
    problem, by core's check where a packaged list judges the value —
    `test_every_list_parameter_is_checked`, `test_every_member_of_an_area_list_is_checked` and
    `test_mirror_flow_problems_are_named_together` assert every problem at once (ADR-0061,
    decision 7).
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — the tasks that fix filters over one
    operation leave, `get_series`, `get_latest_period`, `get_cross_section`,
    `get_sold_production`, `get_total_production`, `get_trade`, `get_trade_hs` and the bulk
    `download_trade`, and so do `list_cn8` and `list_hs`, which cut one codelist by length under
    names that the list does not carry — their tests of `tests/test_tasks.py` leave (ADR-0060,
    decisions 3, 4 and 8).
    `src/xippios/eurostat/models.py` and `src/xippios/eurostat/parse/sdmx_csv.py`
    (sdk-eurostat) — `SdmxCsvRow.obs_value` keeps upstream's text, with `obs_value_number`
    beside it — `test_parse_sdmx_csv_reads_every_row_as_printed` and the other
    `tests/test_parse.py` tests of the row, and `test_download_trade_ds_045409`, assert the
    number in its place (ADR-0060, decisions 1 and 7).
    `src/xippios/faostat/models.py` and `src/xippios/faostat/parse/bulk_csv.py` (sdk-faostat) —
    `DataRecord.value` and `BulkRecord.value` keep upstream's text, with `value_number` beside
    it — `test_get_data_qcl`, `test_get_data_tool_end_to_end`, `test_get_series_qcl` and
    `test_parse_bulk_csv_reads_every_row_as_printed` assert the number in its place (ADR-0060,
    decisions 1 and 7).
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — the ranking `get_top_countries` leaves with
    `GROUPINGS`, and the pivot `get_balance_sheet`, which keys upstream's records by names of
    the package's own, leaves with the slices, and `get_time_series` bounds one tool call over MCP
    to about two dozen requests, where it spends 100 — the `test_top_countries_*` and
    `test_*balance_sheet*` tests of `tests/test_slices.py` leave (ADR-0060, decisions 3, 4 and
    8, ADR-0061, decision 8).
    `src/xippios/usda/psd/params.py` (sdk-usda-psd) — `country_regions` and
    `validate_region_code` leave with the ranking — `test_country_regions_are_the_packaged_list`
    and the `validate_region_code` tests of `tests/test_params.py` leave, and
    `tests/test_live.py` checks `GROUPINGS` and `country_regions` (ADR-0060, decision 8).
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — the ranking `get_top_destinations` and
    `get_latest_week`, which picks the newest week, leave, and `_vintage` leaves, so that
    `get_exports` and `get_weekly_series` leave `meta.vintage` empty and say why —
    the `tests/test_slices.py` tests of the two tasks leave, and
    `test_vintage_is_none_for_empty_answers` and the tests of `get_exports` assert the computed
    week (ADR-0060, decisions 2 and 8).
    `src/xippios/usda/esr/models.py` (sdk-usda-esr) — the private attribute
    `_release_time_stamp_text` and its validator go, `releaseTimeStamp` reads as a time that
    keeps upstream's fraction of a second with no text beside it, and `meta.vintage` of the
    release list stays upstream's text for the answer's newest record —
    `test_the_release_text_round_trips_and_is_not_serialised` and
    `test_the_release_text_through_a_copy_a_dump_and_a_revalidation` of `tests/test_api.py`
    leave, and `tests/test_tasks.py` and `tests/test_live.py` read the property
    `release_time_stamp_text` (ADR-0060, decisions 1 and 8, https://github.com/xippios/sdk-usda-esr/issues/60, part 3).
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) — the six tasks that take their release
    time from another flow's list, `get_census_reexports`, `get_customs_district_exports`,
    `get_customs_district_imports`, `get_customs_district_reexports`,
    `get_census_reexport_series` and `get_un_reexports`, leave `meta.vintage` and
    `published_at` empty and say why, while a series' newest month stays —
    `test_get_census_reexports`, `test_customs_district_tasks`, `test_un_data_tasks`,
    `test_the_un_vintages_are_the_recorded_release_times` and `test_census_series_tasks` assert
    the borrowed release (ADR-0060, decisions 2 and 8).
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — the five call forms
    `get_exports(commodity_code, market_year, *, country_code=None)`,
    `get_weekly_series(commodity_code, country_code, *, start_year, end_year)`,
    `get_release_dates(*, commodity_code=None, since=None)`,
    `list_countries(*, region_id=None, search=None)` and `list_commodities(*, search=None)` —
    a test that passes the country or a filter by position breaks (ADR-0061, decision 5,
    https://github.com/xippios/sdk-usda-esr/issues/60, part 1).
    `src/xippios/<package>/tasks.py` and `tasks_write.py` (every other source) — the arguments
    that identify a record positional, in the order of upstream's path, and every optional
    filter and every other argument of the package's own, `confirm` among them, keyword-only,
    the tenant first and positional as it stands, with one concept at one position in every
    task, which sdk-usda-psd, sdk-comtrade, sdk-x, sdk-eurostat and sdk-usda-gats do not meet
    today — a test that passes a filter by position breaks
    (ADR-0061, decision 5, https://github.com/xippios/sdk-usda-esr/issues/60, part 1).
    `src/xippios/<package>/tasks.py` (sdk-usda-nass, sdk-usda-esmis, sdk-usda-esr) — no data is
    the empty list for a task that returns a list and `NotFoundError` for one that returns a
    record — a test that asserts the other answer breaks (ADR-0061, decision 6).
    `src/xippios/<package>/tasks.py` (sdk-usda-psd, sdk-usda-esmis, sdk-usda-nass,
    sdk-cashctrl) — each task that spends more than one request states the most that one call
    spends, retries counted, in its tool's description, the text of its docstring before
    `Args:` — no test breaks, and the
    review holds it (ADR-0061, decision 8).
    `src/xippios/<package>/tasks.py` (each source with `MCP_CAPS`) — `ResultCap(paged=True)`
    only where a second run sends upstream no request, an answer of a packaged table or of the
    response cache — a test of a paged tool whose task sends a request breaks with its cap
    (ADR-0061, decision 9, ADR-0047 as amended).
    `src/xippios/<package>/tasks.py` (sdk-usda-gats, sdk-eurostat) — a filter of the package's
    own named after upstream's field that it reads, by equality or by prefix, its docstring
    saying that the package filters after the fetch — no test breaks (ADR-0061, decision 2).
    `src/xippios/<package>/_client.py` (sdk-usda-esmis, sdk-usda-esr, sdk-usda-psd,
    sdk-comtrade, sdk-usda-nass) — core's response cache on the client of public data, or one
    sentence of `CLAUDE.md` that says why not — a test that counts a second request to one path
    breaks (ADR-0061, decision 11).
    `tests/` (sdk-cashctrl, sdk-x, sdk-google-mail, sdk-usda-esmis) — an offline test for each
    value set written by hand from upstream's document, which reads it against
    `docs/upstream/` — no test breaks, and the review holds it (ADR-0061, decision 12).
