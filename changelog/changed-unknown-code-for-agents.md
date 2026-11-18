- `UnknownCode` names a closest code whose name is its own text once, `Did you mean VA?`
  where it wrote `VA (VA)`, and its tail reads `If upstream added it since, the packaged
  list is out of date.`, where it named the maintainers' `/refresh-reference-data`, which
  an agent cannot run. `closest` takes `cutoff=`, 0.6 by default as before; 0.5 lets a
  code of two characters with one of them wrong match, `VS` naming `VA`.
  (ADR-0022, §5, https://github.com/xippios/sdk-core/issues/111)
  - Hand-apply: `tests/test_tasks.py` (sdk-comtrade) — `REFUSED_756` (lines 275 to 276)
    and `REFUSED_C16` (lines 740 to 741) end with the old tail, so the tests that compare
    a message with them fail: lines 294, 755, 783, 1687, 1860, 2516, 2750, 3292 and 3323
    → the new tail in both constants — core's tail changed.
    `tests/test_tasks.py` (sdk-eurostat) —
    `test_get_total_production_refuses_a_product_its_list_lacks` (lines 1872 to 1873) →
    the new tail — as above.
    `tests/test_params.py` (sdk-usda-esr) —
    `test_the_recorded_unknown_commodity_is_refused_naming_the_nearest` (lines 197 to
    198) → the new tail — as above.
    `tests/test_params.py` (sdk-usda-gats) —
    `test_the_recorded_unknown_partner_is_refused_without_a_close_code` (line 184) and
    `test_an_unknown_customs_district_names_the_nearest_ids` (line 432), which assert
    `/refresh-reference-data` in the message, and
    `test_the_membership_check_names_the_parameter_it_was_given_as` (lines 560 to 561) →
    the new tail — as above.
    `tests/test_params.py` (sdk-usda-psd) — `test_unknown_commodity_code_names_the_closest`
    (lines 133 to 134) and
    `test_an_unknown_code_without_a_close_match_still_reads_as_sentences` (lines 274 to
    275) → the new tail — as above.
    `src/xippios/usda/nass/params.py` (sdk-usda-nass) — `_check_value`'s own
    `Did you mean` hint (lines 122 to 124) → `hint` passed only when `close` is empty, the
    `list_param_values` sentence kept — `UnknownCode` names each bare value once, the same
    text.
