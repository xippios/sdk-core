- `nearest(value, codes, *, n=3)`, exported from `xippios.core` beside `closest`, names
  up to `n` known integer codes nearest to `value` by number with their names, nearest
  first and the lower of two equally near, for `UnknownCode`'s `closest`. `codes` is keyed
  by the integer or by its text, and each pair keeps its code as `codes` keys it: the
  strategy that sdk-usda-esr and sdk-usda-gats each carried.
  (ADR-0022, ADR-0023, §5, https://github.com/xippios/sdk-core/issues/107)
  - Hand-apply: `src/xippios/usda/esr/params.py` (sdk-usda-esr) — `_closest` (lines 76
    to 93): its first pass, `sorted(codes, key=lambda code: (abs(code - value), code))[:2]`
    (line 87), → `[code for code, _ in nearest(value, codes, n=2)]`, imported from
    `xippios.core` (line 24), and the local name `nearest` of line 87 renamed, since it
    would shadow the import. Its digit pass stays, ESR's own, so `999` still names
    `1001` and `902`, and `1040` still `104`, and the tests of `tests/test_params.py` pass
    unchanged — core takes the second copy (ADR-0023, decision 4).
    `src/xippios/usda/gats/params.py` (sdk-usda-gats) — `_nearest` (lines 409 to 412) and
    its call (line 449) → `nearest(customs_district_id, codes)`, imported from
    `xippios.core` beside `closest` (line 38): the same three ids, keyed by their text,
    in the same order, so `test_an_unknown_customs_district_names_the_nearest_ids` passes
    unchanged — as above.
