- `Answer` is generic over its payload: `get_answer(path, parse=T, endpoint=...)` parses
  the payload into `T` and returns an `Answer[T]`, and a wrapper returns
  `Answer(value, answer.retrieved_at)` for a value it derives from the payload. It
  replaces the pairs of a value and its `retrieved_at` that sources kept of their own.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/123)
  - Hand-apply: `src/xippios/comtrade/api/reference.py` (sdk-comtrade) — `ReferenceFile[T]`
    goes, `reference_rows` returns the `Answer[list[dict[str, Any]]]` it builds from
    `get_answer(..., parse=_ReferenceFile, endpoint=...)`, `reference` returns an
    `Answer[list[M]]`, `api/__init__.py` drops the name, and `tasks.py`,
    `scripts/refresh_reference.py`, `tests/test_tasks.py` and `tests/test_live.py` read
    `.payload` for `.rows` — core's typed answer replaces the pair (ADR-0023, decision 4).
    `src/xippios/usda/nass/api/get_param_values.py` (sdk-usda-nass) — `ParamValues` goes,
    `get_param_values` returns `Answer[list[str]]`, `api/__init__.py` drops the name, and
    `tasks.py` and `tests/test_tasks.py` read `.payload` and `.retrieved_at` where they
    unpacked the pair — core's typed answer replaces the pair (ADR-0023, decision 4).
