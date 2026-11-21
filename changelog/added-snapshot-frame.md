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
  https://github.com/xippios/sdk-core/issues/340)
  - Hand-apply: `scripts/refresh_upstream.py` — ported to a `Snapshot` declaration run by
    `xippios.core.refresh.run`, its `# /// script` block dropped, its frame code deleted
    and its own code kept as hooks: sdk-cashctrl `split` with its word check, sdk-comtrade
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
    `docs/upstream/FETCHED.md` — rewritten once by the first run of the ported script, in
    the frame's form, every row with an ETag gaining the code span and the mark and the
    403 rows moving to `Not fetched` — the frame writes it alone (ADR-0028, decision 4).
