- `Answer` is generic over its payload: `get_answer(path, parse=T, endpoint=...)` parses
  the payload into `T` and returns an `Answer[T]`, and a wrapper returns
  `Answer(value, answer.retrieved_at)` for a value it derives from the payload. It
  replaces the pairs of a value and its `retrieved_at` that sources kept of their own.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/123)
  - Hand-apply: `src/xippios/comtrade/api/reference.py` (sdk-comtrade) — `ReferenceFile[T]`
    goes, `reference_rows` returns `Answer[list[dict[str, Any]]]` from
    `get_answer(..., parse=_ReferenceFile, endpoint=...)`, and `reference` returns
    `Answer[list[M]]`, reading `.payload` and `.retrieved_at` where it unpacked
    `rows, retrieved_at = await reference_rows(name)` — core's typed answer replaces the
    pair (ADR-0023, decision 4).
    `src/xippios/comtrade/api/__init__.py` (sdk-comtrade) — the import and `__all__` drop
    `ReferenceFile` — the class goes.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `list_commodities_async` reads
    `fetched.payload` for `fetched.rows` — `Answer` names the rows `payload`.
    `scripts/refresh_reference.py` (sdk-comtrade) — `_rows` reads `answer.payload` for
    `answer.rows`, and `_table` reads `.payload` and `.retrieved_at` where it unpacked
    `rows, fetched = sync(api.reference_rows)(file)` — `Answer` is not a tuple and names
    the rows `payload`.
    `tests/test_tasks.py` (sdk-comtrade) — `.payload` for `.rows` — `Answer` names the
    rows `payload`.
    `tests/test_live.py` (sdk-comtrade) — `.payload` for `.rows`, four times — `Answer`
    names the rows `payload`.
    `src/xippios/usda/nass/api/get_param_values.py` (sdk-usda-nass) — `ParamValues` goes,
    and `get_param_values` returns `Answer[list[str]]` — core's typed answer replaces the
    pair (ADR-0023, decision 4).
    `src/xippios/usda/nass/api/__init__.py` (sdk-usda-nass) — the import and `__all__`
    drop `ParamValues` — the class goes.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — `.payload` and `.retrieved_at`
    where it unpacked `values, retrieved_at = await api.get_param_values(param)` —
    `Answer` is not a tuple.
    `scripts/refresh_reference.py` (sdk-usda-nass) — `.payload` and `.retrieved_at` where
    it unpacked `values, retrieved_at = fetch(param)` — `Answer` is not a tuple.
    `tests/test_tasks.py` (sdk-usda-nass) — `.payload` and `.retrieved_at` where it
    unpacked `values, retrieved_at = await api.get_param_values("sector_desc")` —
    `Answer` is not a tuple.
