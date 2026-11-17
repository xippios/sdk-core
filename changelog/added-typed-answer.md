- `Answer` is generic over its payload: `get_answer(path, parse=T, endpoint=...)` parses
  the payload into `T` and returns an `Answer[T]`, and a wrapper returns
  `Answer(value, answer.retrieved_at)` for a value it derives from the payload. It
  replaces the pairs of a value and its `retrieved_at` that sources kept of their own.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/123)
  - Hand-apply: `src/xippios/comtrade/api/reference.py` (sdk-comtrade) — `ReferenceFile[T]`
    goes, `reference_rows` returns `Answer[list[dict[str, Any]]]` from
    `get_answer(..., parse=_ReferenceFile, endpoint=...)`, and `reference` returns
    `Answer[list[M]]` — core's typed answer replaces the pair (ADR-0023, decision 4).
    `src/xippios/comtrade/api/__init__.py` (sdk-comtrade) — `__all__` drops
    `ReferenceFile` — the class goes.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `.payload` for `.rows` — `Answer`
    names the rows `payload`.
    `scripts/refresh_reference.py` (sdk-comtrade) — `.payload` for `.rows` — `Answer`
    names the rows `payload`.
    `tests/test_live.py` (sdk-comtrade) — `.payload` for `.rows` — `Answer` names the
    rows `payload`.
    `tests/test_tasks.py` (sdk-comtrade, sdk-usda-nass) — `.payload` for `.rows`, and
    `.payload` and `.retrieved_at` where a test unpacked `ParamValues` — `Answer` is
    not a tuple and names its value `payload`.
    `src/xippios/usda/nass/api/get_param_values.py` (sdk-usda-nass) — `ParamValues`
    goes, and `get_param_values` returns `Answer[list[str]]` — core's typed answer
    replaces the pair (ADR-0023, decision 4).
    `src/xippios/usda/nass/api/__init__.py` (sdk-usda-nass) — `__all__` drops
    `ParamValues` — the class goes.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — `.payload` and `.retrieved_at`
    where it unpacked the pair — `Answer` is not a tuple.
