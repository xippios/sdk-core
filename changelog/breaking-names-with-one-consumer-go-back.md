- `naive_time` leaves `xippios.core` for its one consumer, sdk-usda-esr, and `load_table` with
  `load_csv` leave `xippios.core` and `xippios.core.reference` for theirs, sdk-usda-nass: a
  source hands `newer_than` its own reader of its vintage text, whose refusal of a reader that
  does not compare with the releases names no reader of core's, and reads a packaged CSV file
  itself. `assert_list_current` leaves the list of `xippios.core.testing`, since no source
  imports it, and stays in `xippios.core.testing.live`, which calls it.
  (ADR-0059, ADR-0052, https://github.com/xippios/sdk-core/issues/473)
  - Hand-apply: `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — its reader of `since` stays
    its own, `_since` with `_SINCE_EXAMPLE`, about 40 lines, handed to `newer_than` as `read=`,
    or, on a branch that took core's `naive_time`, that function with `_NAIVE_EXAMPLE` copied in
    from the commit that the handover names and bound to the source's slug — core ships no
    reader of a vintage text, so its `main`, which imports no `naive_time`, breaks no test, and
    on such a branch every test fails at the import of `tasks.py` until the copy stands.
    `src/xippios/usda/nass/params.py` (sdk-usda-nass) — `columns()` reads `columns.csv` itself,
    `load_table` and `load_csv` copied in from the commit that the handover names, about 10
    lines over `csv.DictReader` and `TypeAdapter(list[Column])`, in place of the import of
    `load_table` from `xippios.core` — core reads no CSV file, and until the copy stands every
    test that imports the package, `tests/test_tasks.py` and `tests/test_refresh_reference.py`
    among them, fails at the import of `params.py`.
