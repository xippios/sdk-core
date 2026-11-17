- `cap_result` cuts the rows of a result whose `data` is a model that holds one list, and
  no other field a list, once it passes the byte bound: the rows are cut as a list
  result's are, with the usual note, and the model's other fields stay whole, where the
  model was a note and a preview until now. Within the byte bound such a model returns
  whole, and a model with no list or with two, or whose other fields alone pass the
  bound, is still the preview.
  (ADR-0016, §8, https://github.com/xippios/sdk-core/issues/131)
  - Hand-apply: `tests/test_tasks.py` (sdk-cashctrl, sdk-x) — a test that expects a note
    and a preview from a model over its cap (`get_report_data`, `count_posts`) → its rows
    cut, its other fields whole and the cut note — the cut of a model's rows.
    `CLAUDE.md` (sdk-cashctrl, sdk-x) — the lines that say such a result is cut whole into
    a note and a preview → its rows are cut and its other fields kept — the same cut.
