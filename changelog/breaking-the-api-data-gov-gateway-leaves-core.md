- `xippios.core.data_gov` leaves core for the shared package `sdk-usda-fas` of the sources
  behind api.data.gov, import `xippios.usda.fas`, with `Gateway`, `NoDataForYear`, `API_KEY_ENV`
  and the module's other names and tests, and the refusal of a spent quota before sending says
  "quota" with the policy's `source` for every policy. `fetch_periods` takes a source's own
  error for a period without data in its `skip`.
  (ADR-0065, ADR-0032, §7, https://github.com/xippios/sdk-core/issues/485)
  - Hand-apply: `src/xippios/usda/psd/_client.py` (sdk-usda-psd) — line 31 imports `API_KEY_ENV`
    and `Gateway` from `xippios.usda.fas`, by the names that its first release exports, and the
    module docstring (lines 7 to 16) names that module in place of `xippios.core.data_gov` —
    every test that imports `_client.py` fails at the import until the port stands.
    `src/xippios/usda/esr/_client.py` (sdk-usda-esr) — line 33 likewise, and the module
    docstring (lines 6 to 18) — every test that imports `_client.py` fails at the import until
    the port stands.
    `src/xippios/usda/gats/_client.py` (sdk-usda-gats) — line 47 likewise, and the module
    docstring (lines 6 to 15) — every test that imports `_client.py` fails at the import until
    the port stands.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — line 52 imports `NoDataForYear` from
    `xippios.usda.fas` — every test that imports `tasks.py` fails at the import until it does.
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — line 94 likewise — every test that imports
    `tasks.py` fails at the import until it does.
    `pyproject.toml` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — declares `xippios-usda-fas`
    with one minor through the template's answer `source_dependencies`, since the template
    renders the file, and `known-third-party` (line 82) names `xippios.usda.fas` beside
    `xippios.core` where the render does not — every import of the shared package fails
    without the dependency, and ruff sorts it as the source's own without the second.
    `tests/test_client.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — the import of
    `xippios.core.data_gov` (lines 31, 32 and 32) and the seven tests that the shared package
    holds under the same names leave, `test_the_client_is_wired_for_the_gateway`,
    `test_invalid_key_is_an_auth_error_naming_the_code_and_the_variable`,
    `test_every_documented_key_code_is_an_auth_error`,
    `test_a_403_without_a_gateway_code_falls_through_to_core`,
    `test_the_gateway_not_found_is_a_not_found_error`, `test_other_statuses_fall_through_to_core`
    and `test_core_retries_a_429_only_within_its_backoff`, and a test that stays reads the
    refusal before sending as core words it, `quota spent (`, in place of `api.data.gov quota of
    the key in DATA_GOV_API_KEY spent` (sdk-usda-psd lines 298 and 299, sdk-usda-esr 418 and
    419, sdk-usda-gats 297 to 300) — the import fails the whole file, and core's subject of the
    quota left with the gateway.
    `tests/test_tasks.py` (sdk-usda-psd, sdk-usda-esr) — imports `NoDataForYear` from
    `xippios.usda.fas` (lines 15 and 16) — the file fails at the import until it does.
    `tests/test_slices.py` (sdk-usda-psd, sdk-usda-esr) — imports `NoDataForYear` from
    `xippios.usda.fas` (lines 30 and 31) — the file fails at the import until it does.
    `tests/test_live.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — imports `Gateway` from
    `xippios.usda.fas` (lines 25, 26 and 40) — the live suite fails at the import, and no
    offline test does.
    `CLAUDE.md` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — the rows Credentials and Rate
    limit (lines 16 and 17), the layout's entry of `_client.py` (sdk-usda-psd 30 to 32,
    sdk-usda-gats 31 to 33), the paragraph on the gateway (sdk-usda-esr 23 to 29) and the facts
    of the empty 404 (sdk-usda-psd 218 and 219, sdk-usda-esr 64) name `xippios.usda.fas` in place
    of `xippios.core.data_gov`, and one line names the dependency and what the source takes from
    it, as ADR-0021, decision 6, asks — no test breaks, and the review holds it.
    `README.md` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — one line names `xippios-usda-fas`
    and what the source takes from it, as ADR-0021, decision 6, asks — no test breaks, and the
    review holds it.
