- `PackagedList.codes(code, name=None, *, fold_case=False, list_name=None, source=None)`
  declares a packaged list's code field, name field and folding once, and the `PackagedCodes`
  it returns checks an argument in one call, `check(param, value, *, hints=None,
  otherwise=None, closest=None, reason=None)`, which returns the value as given or raises
  `UnknownCode`. A value of the other type than the list's codes is refused with
  `InvalidRequestError`, which names the integer or the text to pass. `names`, `name_of` and
  `in` read the declared list as the check compares it.
  (ADR-0045, §5, https://github.com/xippios/sdk-core/issues/313)
  - Hand-apply: `src/xippios/usda/esr/params.py` (sdk-usda-esr) — `_codes` and
    `_validate_code` → a declaration per list and `check(param, value, closest=_closest,
    reason=_REASON)`, `_closest` taking a `Mapping` — the copy core now holds, and the tests of
    a text given for an integer code take core's wording.
    `src/xippios/usda/psd/params.py` (sdk-usda-psd) — `_codes` and `_validate_code` → a
    declaration per list and `check(param, value, hints=COUNTRY_HINTS, reason=...)`, and
    `validate_attribute_id` → `check` on the integer list — the copy core now holds.
    `src/xippios/usda/nass/params.py` (sdk-usda-nass) — `_packaged` and `_check_value` → a
    declaration per parameter with `fold_case=True` and `check(param, value,
    otherwise=..., reason=...)` — the copy core now holds.
    `src/xippios/usda/gats/params.py` (sdk-usda-gats) — `_codes`, `validate_country_code` and
    `validate_customs_district_id` → `check(param, value, closest=..., otherwise=...,
    reason=...)` — the copy core now holds.
    `src/xippios/comtrade/params.py` (sdk-comtrade) — the `UnknownCode` branches of
    `_check_list` and `_check_areas` → `check` with `fold_case=True` for `flowCode` and
    `customsCode`, the area codes converted to integers first — the copy core now holds.
    `src/xippios/faostat/tasks.py` (sdk-faostat) — `_check_codes` → `check(dimension, code,
    reason=...)` on a declaration with `list_name=` of its table — the copy core now holds.
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — `_labels` and `_check_code` → `check(param,
    value, hints=..., reason=...)` on a declaration with `list_name=` of its codelist — the
    copy core now holds.
    `src/xippios/usda/wasde/tasks.py` (sdk-usda-wasde) — the refusals of `table` and
    `commodity` → `check(param, value, closest=..., reason=...)`, the closest codes described
    as today — the copy core now holds.
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — the check of `agency_acronym` in
    `list_publications` → `check("agency_acronym", agency_acronym, reason=...)` — the copy core
    now holds.
