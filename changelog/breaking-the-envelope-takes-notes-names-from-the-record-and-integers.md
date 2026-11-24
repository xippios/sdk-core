- `ResultMeta.notes` holds one sentence per fact that a task says about its answer, a record's
  model names the codes of its rows in `meta.names` by marking a code field
  `Annotated[str, NamedBy(REGIONS)]`, or `NamedBy("item")` where upstream sends the name beside
  the code, and a `Decimal` without fractional digits serialises as a JSON integer, `16217` where
  it read `16217.0`. A row's code that its list lacks is left out and said in a note, and no
  answer is withheld for it. `names_codes` keeps naming a request's codes and loses `separator=`,
  and `UNNAMED_CODES` leaves with the five words of the family check, which reads the model's
  marks as `test_family_code_names_are_declared_on_the_model`.
  (ADR-0067, ADR-0031, §3, §4, https://github.com/xippios/sdk-core/issues/478)
  - Hand-apply: `src/xippios/<source>/models.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) —
    each code of a country, a reporter, a partner or a unit on a record takes
    `Annotated[..., NamedBy(<list>)]` with the packaged list that `params.py` loads for it,
    declared where `models.py` imports it without a cycle: sdk-usda-psd's
    `CommodityData.country_code` (`:152`) and `unit_id` (`:157`),
    `DataReleaseInfo.country_code` (`:190`), `BalanceSheetEntry.unit_id` (`:215`) and
    `BalanceSheet.country_code` (`:244`) by its `countries` and `unitsOfMeasure` lists,
    sdk-usda-esr's `CommodityData.country_code` (`:232`) and `unit_id` (`:241`) and
    `Commodity.unit_id` (`:60`) by the same two, and sdk-usda-gats's `country_code`,
    `reporter_code`, `reporter_country_code`, `partner_country_code` and the two unit ids
    of `CensusExport`, `CensusImport`, `CustomsDistrictExport`, `CustomsDistrictImport`,
    `UNTradeRecord`, `DataReleaseInfo` and `UNTradeDataReleaseInfo` (`:272-564`) by its
    `countries` and `unitsOfMeasure` lists — an answer for every country then names each one of
    its rows — no test breaks but one that compares a whole dumped `meta` of such an answer,
    which sees `names`.
    `src/xippios/faostat/models.py` (sdk-faostat) — `DataRecord.area_code` (`:228`) takes
    `NamedBy("area")`, the field beside it (`:229`), and so do `BulkRecord.area_code` (`:535`)
    and `area_code_m49` (`:536`) by `area` (`:537`), while `get_data` keeps `area_cs` and its
    tasks module holds no `UNNAMED_CODES`, which core 0.4.1's note asked of it — the record's own
    label counts as the code's name — no test breaks.
    `src/xippios/<source>/tasks.py` (sdk-usda-esr, sdk-usda-psd, sdk-usda-nass,
    sdk-usda-esmis) — one sentence in `meta.notes` says what the answer passed over:
    sdk-usda-esr's `get_weekly_series` (`:611`) the market years without data that it passes
    over at `:696-698`, sdk-usda-psd's `get_time_series` (`:460`) those it passes over at
    `:540-546`, sdk-usda-nass's `get_data` (`:375`) under `split_by_year` the years that
    `_split_by_year` skips at `:368-370`, and sdk-usda-esmis's `list_recent_releases` (`:578`)
    the rule by which its walk ended at `:668`, which each docstring says today and no field of
    the answer states — no test breaks but one that compares a whole dumped `meta` of such an
    answer, which sees `notes`.
    `src/xippios/<source>/tasks.py` (sdk-comtrade, sdk-faostat) — the `names_codes` decorators
    that core 0.4.1's note gave `separator=","`, seven of sdk-comtrade's and sdk-faostat's
    `get_series`, take no `separator`, which the decorator refuses with `TypeError` when the
    module is imported, and their tasks take several codes as a list (ADR-0061, decision 1) —
    sdk-comtrade's `test_a_partner_with_a_data_gap_has_a_mirror_of_zero`
    (`tests/test_tasks.py:2903`), which passes `"842,408,4"`, breaks until it passes a list.
    `tests/test_api.py` (sdk-usda-esr) —
    `test_records_serialise_snake_case_with_numbers_and_iso_dates` (`:290`) asserts a float of
    `accumulated_exports`, which upstream sends whole and which dumps as `16217` — it breaks
    until it asserts a JSON number, `int | float`.
    `tests/test_tasks.py` (sdk-usda-esr, sdk-usda-gats, sdk-usda-psd) — sdk-usda-esr's
    `test_mcp_tool_call_end_to_end` (`:453`) and `test_quantities_are_json_numbers_over_http`
    (`:640`) break the same way, and sdk-usda-gats's `test_values_are_json_numbers_over_http`
    (`:1043`), `test_the_reexport_series_tool_end_to_end` (`:1574`),
    `test_the_series_over_http` (`:1617`) and
    `test_the_un_data_tools_name_both_filters_when_cut` (`:2643`) and sdk-usda-psd's
    `test_value_is_a_json_number_through_both_adapters` (`:318`) assert a float that holds
    while their recordings' numbers carry a fractional digit, so all eight assert a JSON
    number — three tests break, and five would on a whole number.
