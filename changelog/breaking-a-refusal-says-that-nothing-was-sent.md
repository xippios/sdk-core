- Each of core's refusals before a request says `Nothing was sent.` after its first sentence:
  `UnknownCode`, the check's refusal of a value of the other type, the refusal of a bad `dest`
  and that of an unknown tenant, while `names_codes`, which checks after the call, says that
  upstream was asked. `check(param, value)` takes one code or a list of codes and refuses the
  first code that it refuses and an empty list, and `check_dest(dest, *, source=None)`,
  exported from `xippios.core`, is the check of a download's `dest` that a task calls before
  its first request. `QueryTooLarge` loses `bound` with its form for a size read from the
  arguments, `closest` loses `cutoff`, and `PackagedCodes` loses `name`, `fold_case`, `source`,
  `names` and the `in` test, which no caller read.
  (ADR-0045, ADR-0053, §5, https://github.com/xippios/sdk-core/issues/481)
  - Hand-apply: `src/xippios/<source>/params.py` (sdk-comtrade, sdk-usda-esr, sdk-usda-gats,
    sdk-usda-nass, sdk-usda-psd) — each refusal that a validator makes before a request says
    `Nothing was sent.` after its first sentence, 12, 4, 10, 2 and 7 raise sites at their
    `main`, an `UnknownCode` among them saying it by itself, and sdk-comtrade's `_check_list`
    (`:222-243`) and `_check_areas` (`:341-348`) become one call of `check` with the list,
    whose refusal of an empty list replaces the module's own — conventions §5 ask the sentence
    of a refusal of the call as given, and core gives no helper for it.
    `src/xippios/<source>/tasks.py` (sdk-cashctrl, sdk-eurostat, sdk-faostat, sdk-google-mail,
    sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd, sdk-usda-wasde) —
    each refusal before the task's first request says the sentence the same way, 5, 11, 8, 3,
    9, 5, 5, 6, 6 and 4 raise sites, and a refusal after a request words what was sent itself,
    as sdk-cashctrl's `_report_refusal` after the report tree is read and sdk-usda-nass's split
    of `year__GE` alone after its count do. sdk-usda-gats's `_un_ranked` (`:1355-1402`) asks
    for the UN release list before it raises the `UnknownCode` that its check built, so it
    checks first or words that refusal itself. The loops over codes become one call of `check`
    with the list, each with its refusal of an empty list: sdk-eurostat's `_checked`
    (`:1096-1099`) and `_production` (`:1146-1147`), sdk-faostat's `_check_codes`
    (`:253-271`) and sdk-usda-psd's `_attribute_ids` (`:444-457`). sdk-faostat's `_target`
    (`:623-637`) and sdk-usda-esmis's (`:340-344`) give way to `check_dest`, the latter keeping
    its refusal of no `dest` at all — one check of a list and of a `dest` in core, one wording.
    `src/xippios/cashctrl/api/_download.py` (sdk-cashctrl) — its `check_dest` (`:90-105`) gives
    way to core's `check_dest(dest, source=SOURCE)`, which `tasks.py` calls at `:2143`,
    `:2208` and `:2253` and `api/__init__.py` exports — core's says that nothing was sent, and
    `tests/test_downloads.py` matches the first sentence alone, so no test breaks.
    `src/xippios/<source>/tasks_write.py` (sdk-cashctrl, sdk-google-mail) — each refusal before
    a request says the sentence, 2 raise sites in sdk-cashctrl's and 6 through sdk-google-mail's
    `_refuse`, while sdk-cashctrl's six refusals after a read keep their words — no test breaks.
    `src/xippios/cashctrl/api/_form.py` (sdk-cashctrl) — `custom_xml` says the sentence, and
    `_number`, which refuses before a create and after the record's read for an update, says
    what was sent in each case — no test breaks.
    `src/xippios/google/mail/_compose.py` (sdk-google-mail) — its `_refuse` (`:72-73`) adds the
    sentence to its eight refusals — no test breaks.
    `src/xippios/x/api/_query.py` (sdk-x) — its `_refuse` (`:24-25`) adds the sentence to its
    thirteen refusals — no test breaks.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `_bounded` (`:137`), the one caller of a
    size read from the arguments, leaves with the four tasks that the boundary of a source
    package takes out — `QueryTooLarge` has no `bound`, and `tests/test_tasks.py` loses its
    assertions of `.bound` at `:318`, `:2482` and `:3324`.
    `tests/test_tasks.py` (sdk-comtrade, sdk-eurostat, sdk-usda-esmis, sdk-usda-wasde) — each
    pin of a refusal across the end of its first sentence takes `Nothing was sent.` there:
    sdk-comtrade's constants `REFUSED_756` and `REFUSED_C16` with the 13 tests that compare
    them, sdk-eurostat's five refusals of a code and its two pairs of `dest` messages in
    `test_download_dataset_refuses_a_directory_or_a_missing_one` and
    `test_download_trade_refuses_a_directory_or_a_missing_one`, sdk-usda-wasde's
    `test_get_table_refuses_a_page_list_tables_lacks` and
    `test_get_balance_sheet_refuses_a_near_miss_naming_the_closest`, and sdk-usda-esmis's
    `test_a_bad_dest_is_refused_before_any_request` and
    `test_a_bad_dest_is_refused_as_core_refuses_it` — each fails on the message.
    `tests/test_params.py` (sdk-usda-esr, sdk-usda-gats, sdk-usda-psd) — the same pins:
    sdk-usda-esr's `test_the_recorded_unknown_commodity_is_refused_naming_the_nearest`,
    sdk-usda-gats's `test_an_unknown_customs_district_names_the_nearest_ids` and
    `test_a_full_hs6_code_the_list_lacks_names_the_codes_sharing_its_digits`, and
    sdk-usda-psd's `test_unknown_commodity_code_names_the_closest`,
    `test_unknown_attribute_id_names_the_closest`,
    `test_an_unknown_code_without_a_close_match_still_reads_as_sentences` and
    `test_the_world_region_is_refused_with_a_hint` — each fails on the message.
