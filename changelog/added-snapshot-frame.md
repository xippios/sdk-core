- `xippios.core.refresh` holds the frame of a source's `scripts/refresh_upstream.py`: the
  script declares a `Snapshot` with its pages, its attribution and its hooks and calls
  `run(snapshot)`, and the fetch, the attribution check, `FETCHED.md`, the write and
  `--check` are core's, in the standard library alone. Hooks carry what some sources do
  beyond the template's skeleton: `Credentials` for keyed samples with `--keyless`, a file
  kept as recorded, one page split into several files, a second origin after a 403, a wait
  on a 429, a section of the source's own and a note made from the answer. `FETCHED.md`
  takes one form in every source, each ETag in a code span on a row with the allowlist
  mark and the table `Not fetched` under its heading even when it has no row.
  (ADR-0046, §3, https://github.com/xippios/sdk-core/issues/320,
  https://github.com/xippios/sdk-core/issues/340,
  https://github.com/xippios/sdk-core/issues/415,
  https://github.com/xippios/sdk-core/issues/425)
  - Hand-apply: `scripts/refresh_upstream.py` — ported to a `Snapshot` declaration run by
    `xippios.core.refresh.run`, its `# /// script` block dropped, its frame code deleted
    and its own code kept as hooks: sdk-comtrade
    `linked` for the bundle and its products, `reduce` for the Help Center articles and
    `sections` for "Products found", sdk-eurostat `quota_wait`, `keep_recorded` with
    `canonical` for its WADL, `pause=5.0` and `reduce`, sdk-faostat `credentials` with its
    samples `keyed`, `reduce` for the terms, `note` for its checks and notes and `canonical`
    for `processing_time`, sdk-google-mail `reduce` and `note`, sdk-usda-esmis `linked` for
    the newest release and `reduce` for the calendar excerpt, its followed redirect to
    another host recorded by its status, sdk-usda-esr, sdk-usda-gats and sdk-usda-psd
    `note` and `linked` for the FAS portal kit and `reduce` for their part of the shared
    document, sdk-usda-nass `reduce`, sdk-usda-wasde `origin` for USDA's CDN origin,
    `linked` and `reduce`, and sdk-x `canonical` for its scope lists and `reduce` — the
    frame's rules reach a source through core and no longer through twelve copies, and the
    source's page files stay byte for byte as its hooks make them.
    `scripts/refresh_upstream.py` (sdk-cashctrl) — ported with `split` for its one page,
    its word check inside it, and four things of its script given up: `--from-file`, its
    run from a saved copy of the page that spends no request, since the frame takes no
    option of a source's own, its own User-Agent, which names its repository, for the
    family's, its request for the page gzipped, since the frame asks for each page as it
    is, at the cost of a larger transfer and no byte of its files, and the removal of an
    entry's file at the top of `docs/upstream/` once the table of contents drops the entry,
    which the frame makes in the subdirectories it writes to alone, so the port puts its
    entries under one or removes such a file by hand, `--check` naming no leftover — the
    frame carries none of the four while one source alone needs it (ADR-0023, decision 2,
    ADR-0046, decision 2).
    `docs/upstream/FETCHED.md` — rewritten once by the first run of the ported script, in
    the frame's form, every row with an ETag gaining the code span and the mark and the
    403 rows moving to `Not fetched` — the frame writes it alone (ADR-0028, decision 4).
    `tests/test_refresh_upstream.py` — its tests of what the frame now does, the render of
    `FETCHED.md` with its sentences, the row of `OBSERVED.md` and the table `Not fetched`,
    the write with the removal of a file no longer produced, and `--check` with its
    comparison of the committed `FETCHED.md`, deleted with the copy, since core's
    `tests/refresh/test_upstream.py` holds each, and its tests of the source's own hooks and
    of what its `Snapshot` declares kept, calling the hooks or reading the declaration, as
    `docs/handover.md` names each test per source — the tests call `render_fetched`, and
    all but sdk-eurostat's `write_snapshot` and `Response`, which the port deletes from the
    script, and §15, items 3 and 4, delete a copy with its tests.
