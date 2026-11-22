- `xippios.core.testing.live` compares each packaged list with the list upstream serves now in
  the nightly run, and a source collects it in `tests/test_live.py` with one line beside
  `LIVE_LISTS`, each compared list with its `PackagedCodes` and the function that fetches it,
  and `NO_LIVE_LIST`, each list left out with its reason. A code gone, new or changed fails the
  run, the failure names codes and never records, and `assert_list_current(codes, current, *,
  packaged=None)` is the assertion underneath. The family check fails at once a packaged list
  that stands in neither declaration and an entry that names no packaged list.
  (ADR-0055, §10, https://github.com/xippios/sdk-core/issues/319)
  - Hand-apply: `tests/test_live.py` (sdk-usda-esr) — delete `LISTS` and
    `test_packaged_list_equals_the_live_list`, collect `xippios.core.testing.live` and declare
    `commodities`, `countries`, `regions` and `unitsOfMeasure` in `LIVE_LISTS`, each with its
    `PackagedCodes` and its `api` wrapper — the copy core now holds, and
    `test_family_every_packaged_list_is_declared_for_the_live_run` fails without the
    declaration.
    `tests/test_live.py` (sdk-usda-psd) — delete `LISTS` and
    `test_packaged_list_equals_the_live_list`, collect the module and declare `commodities`,
    `commodityAttributes`, `countries`, `regions` and `unitsOfMeasure` in `LIVE_LISTS` with
    their `api` wrappers — the copy core now holds, and the family check fails without it.
    `tests/test_live.py` (sdk-usda-gats) — delete `_keyed`, `LISTS` and
    `test_packaged_list_equals_the_live_list`, collect the module and declare
    `HS6Commodities`, `countries`, `customsDistricts`, `regions` and `unitsOfMeasure` in
    `LIVE_LISTS` with their `api` wrappers — the copy core now holds, and the family check
    fails without it.
    `tests/test_live.py` (sdk-comtrade) — delete the comparisons of `test_list_reporters_live`,
    `test_list_partners_live`, `test_list_codes_live` and `test_list_classifications_live`,
    collect the module and declare `Reporters`, `partnerAreas`, `motCode` and
    `ListofReferences` in `LIVE_LISTS`, each fetched from `api.reference_rows` and read
    through its model, as `scripts/refresh_reference.py` writes the list, and not compared as
    the payload, whose `id` stands where the packaged `motCode` list has `motCode` and whose
    `"True"` the packaged `TradeDataItems` holds as `true`, and each of its eleven other lists
    in `LIVE_LISTS` or in `NO_LIVE_LIST` with its reason, as its patch chooses, the four taken
    from the specification in `NO_LIVE_LIST` — the copy core now holds, and the family check
    fails without the declaration (https://github.com/xippios/sdk-comtrade/issues/60).
    `tests/test_live.py` (sdk-usda-esmis) — delete
    `test_the_packaged_agency_table_matches_upstream_live`, collect the module and declare
    `agency` in `LIVE_LISTS` with `api.agency_find_all`, and `publication` in `LIVE_LISTS`, at
    101 requests a fetch, or in `NO_LIVE_LIST` with its reason, as its patch chooses — the copy
    core now holds, and the family check fails without the declaration.
    `tests/test_live.py` (sdk-usda-wasde) — `vocabulary.differences` in `test_list_tables_live`,
    `test_list_commodities_live` and `test_list_regions_live` → `assert_list_current(codes,
    current, packaged=...)`, both sides masked as today, and `table`, `commodity`, `region` and
    `attribute` in `NO_LIVE_LIST`, each reason naming the test that compares it or why none
    does — the lists come from the session's release file, which no entry of `LIVE_LISTS`
    fetches, and the family check fails without the declaration.
    `src/xippios/usda/wasde/_vocabulary.py` (sdk-usda-wasde) — delete `differences` and the
    functions that name its rows — the copy core now holds.
    `tests/test_live.py` (sdk-faostat) — delete the removed-codes assertion of
    `test_list_elements`, collect the module and declare `element_QCL` in `LIVE_LISTS` with a
    fetch of `api.get_code_list.get_code_list("en", "element", "QCL")`, and each of its
    fourteen other tables in `LIVE_LISTS`, 14 more keyed requests a night, or in `NO_LIVE_LIST`
    with its reason, as its patch chooses — the family check fails without the declaration.
    `tests/test_live.py` (sdk-usda-nass) — collect the module and declare the nine lists of
    `PACKAGED_PARAMS` in `LIVE_LISTS`, 9 keyed requests a night, or in `NO_LIVE_LIST` with
    their reasons, as its patch chooses, and `progress_stages` and `condition_categories` in
    `NO_LIVE_LIST`, since no endpoint serves a derived list — the family check fails without
    the declaration.
    `tests/test_live.py` (sdk-eurostat) — collect the module and declare its nineteen packaged
    lists in `LIVE_LISTS`, 15 more files a night, or in `NO_LIVE_LIST` with their reasons, as
    its patch chooses — the family check fails without the declaration.
