- `xippios.core.refresh` holds the frame of a source's `scripts/refresh_reference.py`: the
  script declares one `Listed` per packaged list with its fetch, its `Enumeration` and its
  origin and calls `run(lists, package=..., client=...)`, the one `run` of both frames, which
  still takes a `Snapshot` as it did. The frame fetches every list before it writes one, each
  request sent once and counted, then writes the packaged files, the provenance rows of
  `reference/README.md` in place under the header each README has and `enums.py` in the
  declared order, left alone where no list declares an enum. `--only` and `--render-only` are
  the frame's, and a hook before the first request and one after the last write carry what a
  script writes beside its lists.
  (ADR-0051, §3, https://github.com/xippios/sdk-core/issues/321,
  https://github.com/xippios/sdk-core/issues/370)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-comtrade) — ported to fifteen `Listed`,
    the ten value lists first in the order of their class names, its fetches building each
    list as it does now with `_reconcile`, `SUPPLEMENTS`, `EVIDENCE`, the spec lists read
    from the snapshot and the models' check, the origins its README keeps by hand declared
    and its client passed to `run`, and `tests/test_scripts.py` dropping its tests of the
    frame's parts, which break with the copy gone — the frame writes its files, its rows and
    its `enums.py` byte for byte as the script does today.
    `scripts/refresh_reference.py` (sdk-eurostat) — ported to nineteen `Listed` whose fetches
    build the TOC with `TocParser` and each codelist at the wrapper's `retrieved_at`,
    `lists.json` and the samples written in `after`, and `--samples` and `--only` by a
    codelist's id read before the call, its `tests/test_refresh_reference.py` keeping the
    tests of these and dropping those of the frame's parts — as above, and its empty
    `enums.py` stays as committed.
    `scripts/refresh_reference.py` (sdk-faostat) — ported to fifteen `Listed` of
    `getCodeList`, `param` the dimension and the origin its path, its count of logins kept
    around the call, its `tests/test_refresh_reference.py` keeping the login count's tests
    and dropping those of the frame's parts — as above, its empty `enums.py` as committed.
    `scripts/refresh_reference.py` (sdk-usda-esmis) — ported to two `Listed` whose fetches
    build the agencies and the walk of the publications as now, stamped at their first
    request, their origins made from the list and its note and its client passed to `run` —
    as above, and it gains `--only`, `--render-only` and the count of its requests.
    `scripts/refresh_reference.py` (sdk-usda-esr) — ported to four `Listed`, `unitsOfMeasure`
    with `Enumeration(ids="unitId", names="unitNames")`, the origin made from the list and
    `quota_header="x-ratelimit-remaining"`, its `tests/test_refresh_reference.py` dropping
    its tests of the frame's parts — as above.
    `scripts/refresh_reference.py` (sdk-usda-gats) — ported to five `Listed`, each endpoint its
    `OPERATIONS` entry and `unitsOfMeasure` with `Enumeration(ids="unitOfMeasureId",
    names="unitOfMeasureName")`, its `tests/test_refresh_reference.py` dropping its tests of
    the frame's parts — as above.
    `scripts/refresh_reference.py` (sdk-usda-nass) — ported to eleven `Listed`, `fetch_param`
    building each parameter list at the wrapper's `retrieved_at` and `fetch_derived` each
    derived list, `CLASS_NAMES`, `_SPELLED_OUT` and the dollar rule as `Enumeration` fields,
    `columns.csv` parsed in `before` and written in `after` on a full run and its read timeout
    set around the call, its `tests/test_refresh_reference.py` keeping the tests of these and
    dropping those of the frame's parts — as above.
    `scripts/refresh_reference.py` (sdk-usda-psd) — ported to five `Listed`, the two id lists
    with their `Enumeration(ids=..., names=...)` and the origin made from the list — as
    above, and it gains `--only` and the count of its requests.
    `scripts/refresh_reference.py` (sdk-usda-wasde) — ported to four `Listed` whose fetches
    build the lists from one download through xippios-usda-esmis, whose client it passes to
    `run`, the origins made from each list's note, the manifest written in `after`, and
    `--keep` and `--from` read before the call — as above, and it gains `--only`,
    `--render-only` and the count of its requests.
