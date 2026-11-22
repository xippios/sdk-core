- `xippios.core.refresh` holds the frame of a source's `scripts/refresh_reference.py`: the
  script declares one `Listed` per packaged list with its fetch, its `Enumeration` and its
  origin and calls `run(lists, package=..., packaged=PACKAGED_LISTS, client=...)`, the one
  `run` of both frames, which still takes a `Snapshot` as it did. The frame refuses lists
  other than those the package declares it ships before a request, fetches every list before
  it writes one, each request sent once and counted, and then writes the packaged files, the
  provenance rows of `reference/README.md` in place under the header each README has and
  `enums.py` in the declared order as one, each made and formatted first. `--only` and
  `--render-only` are the frame's, and a hook before the first request and one after the
  last write carry what a script writes beside its lists.
  (ADR-0051, §3, https://github.com/xippios/sdk-core/issues/321,
  https://github.com/xippios/sdk-core/issues/370)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-comtrade) — ported to fifteen `Listed`,
    the ten value lists first in the order of their class names, its fetches building each
    list as it does now with `_reconcile`, `SUPPLEMENTS`, `EVIDENCE`, the spec lists read
    from the snapshot and the models' check, the origins its README keeps by hand declared,
    `packaged=[*PACKAGED_LISTS, *PACKAGED_TABLES]` and its client passed to `run` — the frame
    writes its files, its rows and its `enums.py` byte for byte as the script does today.
    `scripts/refresh_reference.py` (sdk-eurostat) — ported to nineteen `Listed` whose fetches
    build the TOC with `TocParser` and each codelist at the wrapper's `retrieved_at`,
    `lists.json` and the samples written in `after`, `--samples` and `--only` by a codelist's
    id read before the call, and `packaged=PACKAGED_LISTS` — as above, and its empty
    `enums.py` stays as committed.
    `scripts/refresh_reference.py` (sdk-faostat) — ported to fifteen `Listed` of
    `getCodeList`, `param` the dimension and the origin its path, `packaged=PACKAGED_LISTS`,
    and its count of logins kept around the call — as above, its empty `enums.py` as
    committed.
    `scripts/refresh_reference.py` (sdk-usda-esmis) — ported to two `Listed` whose fetches
    build the agencies and the walk of the publications as now, stamped at their first
    request, their origins made from the list and its note, its client passed to `run` and
    `packaged=[*PACKAGED_LISTS, *PACKAGED_TABLES]` — as above, and it gains `--only`,
    `--render-only` and the count of its requests.
    `src/xippios/usda/esmis/params.py` (sdk-usda-esmis) — `PACKAGED_TABLES = ("agency",
    "publication")` beside its empty `PACKAGED_LISTS` of value lists — the frame refuses
    lists the package does not declare, and esmis declares its two tables nowhere today.
    `scripts/refresh_reference.py` (sdk-usda-esr) — ported to four `Listed`, `unitsOfMeasure`
    with `Enumeration(ids="unitId", names="unitNames")`, the origin made from the list,
    `packaged=PACKAGED_LISTS` in place of its own check and
    `quota_header="x-ratelimit-remaining"` — as above.
    `scripts/refresh_reference.py` (sdk-usda-gats) — ported to five `Listed`, each endpoint its
    `OPERATIONS` entry, `unitsOfMeasure` with `Enumeration(ids="unitOfMeasureId",
    names="unitOfMeasureName")` and `packaged=PACKAGED_LISTS` — as above.
    `scripts/refresh_reference.py` (sdk-usda-nass) — ported to eleven `Listed`, `fetch_param`
    building each parameter list at the wrapper's `retrieved_at` and `fetch_derived` each
    derived list, `CLASS_NAMES`, `_SPELLED_OUT` and the dollar rule as `Enumeration` fields,
    `columns.csv` parsed in `before` and written in `after` on a full run, its read timeout
    set around the call, and `packaged=[*PACKAGED_PARAMS, *DERIVED_LISTS]` — as above.
    `scripts/refresh_reference.py` (sdk-usda-psd) — ported to five `Listed`, the two id lists
    with their `Enumeration(ids=..., names=...)`, the origin made from the list and
    `packaged=PACKAGED_LISTS` in place of its own check — as above, and it gains `--only` and
    the count of its requests.
    `scripts/refresh_reference.py` (sdk-usda-wasde) — ported to four `Listed` whose fetches
    build the lists from one download through xippios-usda-esmis, whose client it passes to
    `run`, the origins made from each list's note, the manifest written in `after`, `--keep`
    and `--from` read before the call, and `packaged=PACKAGED_LISTS` in place of its own
    check — as above, and it gains `--only`, `--render-only` and the count of its requests.
    `tests/test_scripts.py` (sdk-comtrade) — `test_refresh_reference_help_prints_usage_and_stops`
    and `test_refresh_reference_render_only_changes_nothing` load the copy's parser and run,
    and break with it gone: the first reads the frame's usage, the second runs `--render-only`
    through `run` — core's tests hold the frame's command line and render.
    `tests/test_refresh_reference.py` (sdk-eurostat, sdk-faostat, sdk-usda-esr,
    sdk-usda-gats, sdk-usda-nass) — the tests that call the copy's `main`, `refresh`,
    `render`, `module`, `metered`, `with_provenance` or `selected` break with it gone and are
    dropped: the run, `--only`, `--render-only`, the meter, the render and the provenance
    rows. The tests of a source's own fetches and hooks stay, sdk-eurostat's of `read_toc`,
    `toc_list` and the codelists, sdk-faostat's of its login count and sdk-usda-nass's of
    `columns_from_snapshot` and its read timeout — core's `tests/refresh/test_reference.py`
    holds the frame's parts.
    `tests/test_params.py` (sdk-usda-esr) —
    `test_the_refresh_script_names_each_lists_upstream_operation` reads the copy's `LISTS`,
    `TABLES` and `ID_LISTS` and breaks with them gone: it reads the port's `Listed`
    endpoints in their place — the operation each list names stays held.
