- `ResultMeta.names` maps each country parameter of a request to its codes and the names that
  its packaged list holds, `{"country_code": {"CN": "Comoros"}}`, and `names_codes(**codes,
  separator=None)` fills it from the call's arguments on every answer of a task, one
  `PackagedCodes` per parameter. A code the list lacks that reaches the answer unchecked
  withholds the answer with the list's refusal, and an empty `names` is left out of a dumped
  answer, so an answer of a task without such a parameter dumps as before. The family check
  fails at once a task whose parameter holds `country`, `countries`, `area`, `reporter` or
  `partner`, in any case, and is neither named nor exempt in `UNNAMED_CODES` of its tasks
  module with the reason.
  (ADR-0056, §4, https://github.com/xippios/sdk-core/issues/316)
  - Hand-apply: `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) —
    `names_codes(country_code=COUNTRIES)` on `get_balance_sheet`, `get_data`,
    `get_release_dates` and `get_time_series`, `COUNTRIES` declared from `countries` by
    `countryCode` and `countryName` — `test_family_country_codes_are_named_in_the_answer`
    fails without it.
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) — `names_codes(partner_code=COUNTRIES)`
    on the six Census tasks and the three customs-district tasks, and
    `names_codes(reporter_code=COUNTRIES, partner_code=COUNTRIES)` on `get_un_exports`,
    `get_un_imports` and `get_un_reexports` and `names_codes(reporter_code=COUNTRIES)` on
    `get_un_release_dates`, `COUNTRIES` declared from `countries` by `countryCode` and
    `countryName` — the family check fails without it on all 13 tasks.
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — `names_codes(country_code=COUNTRIES)` on
    `get_exports` and `get_weekly_series`, `COUNTRIES` declared from `countries` by
    `countryCode` and `countryDescription` — the family check fails without it.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `names_codes(..., separator=",")` on
    `get_data`, `get_counts`, `get_data_availability`, `get_metadata`, `get_trade_balance`,
    `get_bilateral_data` and `get_world_share` and `names_codes(...)` on
    `get_bilateral_flows`, `get_mirror_flows`, `get_commodity_series` and
    `get_top_partners`, every reporter parameter with `Reporters` by `reporterCode` and
    `reporterDesc` and every partner parameter with `partnerAreas` by `PartnerCode` and
    `PartnerDesc`, and the four slice tasks' docstrings name the numeric code alone — the
    family check fails without it on all 11 tasks.
    `src/xippios/comtrade/params.py` (sdk-comtrade) — `_resolve_iso3` and the alpha-3 branch
    of `_resolve_area` → the refusal of `check` with a hint table keyed by the alpha-3 codes
    of `Reporters` and `partnerAreas`, each naming its code, so `"CHE"` is refused naming
    `757 (Switzerland)` — the decision of https://github.com/xippios/sdk-core/issues/375, a
    breaking change that makes its release a minor.
    `tests/test_tasks.py` (sdk-comtrade) — `test_bilateral_flows_resolve_iso3_codes_before_the_call`,
    `test_iso3_codes_resolve_to_the_codes_upstream_data_uses` and
    `test_mirror_flows_resolve_iso3_codes_and_ask_monthly_data_for_months` → the refusal that
    names the code, and every other test that passes an alpha-3 code to a slice task, the
    end-to-end tests of the tools and the route among them, passes `"757"`, `"842"` and the
    other numeric codes — each fails once `_resolve_iso3` goes, since an alpha-3 code is
    refused.
    `tests/test_live.py` (sdk-comtrade) — `test_get_bilateral_flows_live` and
    `test_get_mirror_flows_live` pass `"757"` and `"842"` in place of `"CHE"` and `"USA"` —
    both fail in the nightly run once `_resolve_iso3` goes.
    `README.md` (sdk-comtrade) — the slice examples pass the numeric codes and the slice
    tasks' paragraphs name UN Comtrade's codes alone — they name the alpha-3 codes that the
    tasks refuse.
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — `names_codes(reporters=COUNTRIES,
    partners=COUNTRIES)` on `get_trade`, `get_trade_hs` and `download_trade` and
    `names_codes(reporters=COUNTRIES)` on `get_sold_production` and `get_total_production`,
    `COUNTRIES` declared from `cxt_free_iso` by `code` and `label` — the family check fails
    without it on all 5 tasks, and a country inside `get_data`'s `filters` stays unnamed
    until its row decides (https://github.com/xippios/sdk-eurostat/issues/52).
    `src/xippios/faostat/tasks.py` (sdk-faostat) — `names_codes(area=..., separator=",")` on
    `get_series` and `area` and `area_cs` of `get_data` in `UNNAMED_CODES` with their reasons,
    since under `area_cs` an M49 code can be an FAO code of another country, until its row
    decides (https://github.com/xippios/sdk-faostat/issues/34) — the family check fails
    without it on both tasks.
