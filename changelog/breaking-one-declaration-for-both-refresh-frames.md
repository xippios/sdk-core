- A source's reference refresh script declares its lists in one `Lists(package, lists,
  packaged, client, quota_header=None, before=None, after=None)`, a frozen dataclass of
  `xippios.core.refresh` beside `Snapshot`, and `run(declaration, argv=None)` is the one
  signature of both frames, so the two overloads of `run`, its six keywords and its two
  `TypeError`s leave. `Enumeration.values` and `.key` and a fetch that answers plain values
  leave, and the enum renderer, `render_enums` with `id_name_pairs` and `enum_member_name`,
  leaves `xippios.core.reference` for the reference frame that alone calls it. The provenance
  table of `reference/README.md` has the one header that sdk-template renders,
  `| File | Origin | Fetched |`, and no row counts its records, while `before`, whose one
  source is sdk-usda-nass, and `after`, which no source's code calls yet, stay.
  (ADR-0062, §3, https://github.com/xippios/sdk-core/issues/482)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-comtrade, sdk-eurostat, sdk-faostat,
    sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd,
    sdk-usda-wasde) — the port to core's frame that the template renders declares the lists
    in one `LISTS = Lists(package=..., lists=(...), packaged=PACKAGED_LISTS, client=client)`,
    with `quota_header` where upstream reports its quota, and ends with
    `raise SystemExit(run(LISTS))`, and a list of values is fetched as records of one field
    named by the list, `[{name: value} for value in values]`, as sdk-usda-nass's
    `fetch_param` builds them (`:306`), where sdk-faostat (`:353`), sdk-usda-gats (`:253`)
    and sdk-usda-psd (`:157`) hand the frame's values today — `run` takes one declaration
    and a fetch answers records or a finished `PackagedList`.
    `scripts/refresh_reference.py` (sdk-comtrade, sdk-eurostat, sdk-faostat, sdk-usda-esr,
    sdk-usda-gats, sdk-usda-nass, sdk-usda-psd) — the import of `render_enums`,
    `id_name_pairs` or `enum_member_name` from `xippios.core.reference` (sdk-comtrade `:71`,
    sdk-eurostat `:93`, sdk-faostat `:75`, sdk-usda-esr `:69`, sdk-usda-gats `:62`,
    sdk-usda-nass `:57`, sdk-usda-psd `:51`) fails, so each enum becomes its list's
    `Enumeration()`, or `Enumeration(ids=..., names=...)` for an id list, and
    sdk-usda-nass's `class_names` and `member_names` (`:213`, `:332-337`) become each
    list's `Enumeration(class_name=..., member_names=...)` — the renderer leaves the
    run-time module for the frame.
    `src/xippios/usda/<name>/reference/README.md` (sdk-usda-esr `:21`, sdk-usda-gats `:30`,
    sdk-usda-psd `:24`) — the header `| File | Origin | Fetched (UTC) | Records |` becomes
    the template's `| File | Origin | Fetched |` over `| --- | --- | --- |`, and each row
    loses its count of records — the frame knows one header and stops a run, and a render
    alone, before a request under another.
    `tests/test_scripts.py` (sdk-comtrade) — `test_refresh_reference_render_only_changes_nothing`
    (`:38`) calls `script.main` (`:49`), which `run(LISTS, argv)` replaces — the script's own
    entry leaves with its renderer.
    `tests/test_refresh_reference.py` (sdk-eurostat, sdk-faostat, sdk-usda-esr,
    sdk-usda-gats, sdk-usda-nass) — the tests that read the script's own render or table,
    sdk-eurostat's `test_render_only_reproduces_the_committed_enums` (`:293`) and
    `readme_rows` (`:372`), sdk-faostat's `test_refresh_writes_the_tables_the_provenance_and_the_enums`
    (`:148`), `test_with_provenance_replaces_the_rows_alone` (`:187`),
    `test_render_only_writes_the_committed_enums` (`:223`) and
    `test_render_names_no_class_of_its_own` (`:333`), and `test_render_writes_enums_py_as_committed`
    of sdk-usda-esr (`:211`), sdk-usda-gats (`:257`) and sdk-usda-nass (`:315`), test the
    frame's run of `LISTS` with `--render-only` or leave — the frame renders and core tests
    its renderer.
    `tests/test_params.py` (sdk-usda-esr) —
    `test_the_refresh_script_names_each_lists_upstream_operation` (`:91`) reads
    `script.LISTS`, `script.TABLES` and `script.ID_LISTS` (`:98-101`) as dicts, which become
    the `Listed` of `LISTS.lists`, each with its `endpoint` — one `Listed` per list of any
    shape.
