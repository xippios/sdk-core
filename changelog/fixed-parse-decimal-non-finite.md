- `parse_decimal` gives `None` for the texts `NaN`, `Infinity` and `sNaN` and every other
  result that is no finite number, where it gave `Decimal('NaN')`, `Decimal('Infinity')`
  and `Decimal('sNaN')`, as its docstring promised for anything that is not a number;
  every finite text reads as before.
  (ADR-0008, https://github.com/xippios/sdk-core/issues/128)
  - Hand-apply: `src/xippios/usda/wasde/parse/wasde_xml.py` (sdk-usda-wasde) — `_value`
    (lines 198 to 201), whose `is_finite()` guard (line 201) → `return parse_decimal(text)`,
    `tests/test_parse.py`'s `NaN` and `Infinity` cases (lines 377 to 378) passing
    unchanged — core gives `None` for them.
