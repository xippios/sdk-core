- `Gateway(source, data_path=...)` maps FAS's empty `text/plain` 404 on the source's data
  paths to `xippios.core.data_gov.NoDataForYear`, a `NotFoundError` with the request's
  `path` whose text says that the year it names holds no data. It replaces the
  `NoDataForYear` and the `classify` branch that sdk-usda-psd and sdk-usda-esr each carried.
  (ADR-0009, ADR-0023, §7, https://github.com/xippios/sdk-core/issues/106)
  - Hand-apply: `src/xippios/usda/psd/_client.py` (sdk-usda-psd) — `Gateway(SOURCE,
    data_path=DATA_PATH)`, the empty-404 branch of `classify` keeps its plain
    `NotFoundError` and loses the `NoDataForYear` return (lines 89 to 94), and the
    docstrings name `xippios.core.data_gov.NoDataForYear` (lines 15 and 76) — core maps it.
    `src/xippios/usda/psd/errors.py` (sdk-usda-psd) — deleted, `NoDataForYear` being all
    it holds — core's class replaces it.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — `from xippios.core.data_gov import
    NoDataForYear` (line 55), `_absent` passes `source=exc.source` (line 152), and the
    docstring names core's class (line 391) — core's class takes its source as a keyword.
    `tests/test_client.py` (sdk-usda-psd) — the import of line 39 from
    `xippios.core.data_gov` — the module it named goes.
    `tests/test_tasks.py` (sdk-usda-psd) — the import of line 18, the same — the same.
    `tests/test_slices.py` (sdk-usda-psd) — the import of line 40, the same — the same.
    `CLAUDE.md` (sdk-usda-psd) — the Layout drops `errors.py` (line 41) and the fixtures'
    facts name core's `NoDataForYear` (line 206) — the same.
    `src/xippios/usda/esr/_client.py` (sdk-usda-esr) — `Gateway(SOURCE,
    data_path=DATA_PATH)`, the empty-404 branch of `classify` keeps its plain
    `NotFoundError` and loses the `NoDataForYear` return (lines 100 to 105), and the
    docstrings name core's class (lines 15 and 79) — core maps it.
    `src/xippios/usda/esr/errors.py` (sdk-usda-esr) — deleted, `NoDataForYear` being all
    it holds — core's class replaces it.
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — `from xippios.core.data_gov import
    NoDataForYear` (line 97) and `_absent` passes `source=exc.source` (line 237) — core's
    class takes its source as a keyword.
    `src/xippios/usda/esr/api/get_country_data.py` (sdk-usda-esr) — the docstring names
    core's class (line 15) — the module it named goes.
    `src/xippios/usda/esr/api/get_all_countries_data.py` (sdk-usda-esr) — the docstring
    names core's class (line 18) — the same.
    `src/xippios/usda/esr/params.py` (sdk-usda-esr) — the docstring names core's class
    (line 50) — the same.
    `tests/test_client.py` (sdk-usda-esr) — the import of line 48 from
    `xippios.core.data_gov` — the same.
    `tests/test_tasks.py` (sdk-usda-esr) — the import of line 26, the same — the same.
    `tests/test_slices.py` (sdk-usda-esr) — the import of line 44, the same — the same.
    `CLAUDE.md` (sdk-usda-esr) — the fixtures' facts name core's `NoDataForYear` (line
    81) and the Layout drops `errors.py` (line 126) — the same.
