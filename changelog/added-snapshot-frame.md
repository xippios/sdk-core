- `xippios.core.refresh` holds the frame of a source's `scripts/refresh_upstream.py`: the
  script declares a `Snapshot` with its pages, its attribution and its hooks and calls
  `run(snapshot)`, and the fetch, the attribution check, which reads an image's alternative
  text and passes a statement recorded with a link only as the text of that link,
  `FETCHED.md`, the write and `--check` are core's, in the standard library alone. Hooks
  carry what some sources do beyond the template's skeleton: `Credentials` for keyed samples
  with `--keyless`, a file kept as recorded, one page split into several files, a second
  origin after a 403, a wait on a 429, a section of the source's own and a note made from
  the answer. `FETCHED.md` takes one form in every source, each ETag in a code span on a row
  with the allowlist mark and the table `Not fetched` under its heading even when it has no
  row.
  (ADR-0046, §3, https://github.com/xippios/sdk-core/issues/320,
  https://github.com/xippios/sdk-core/issues/340,
  https://github.com/xippios/sdk-core/issues/415,
  https://github.com/xippios/sdk-core/issues/425,
  https://github.com/xippios/sdk-core/issues/437)
  - Hand-apply: `scripts/refresh_upstream.py` — ported to a `Snapshot` declaration run by
    `xippios.core.refresh.run`, its `# /// script` block dropped, its frame code deleted
    and its own code kept as hooks: sdk-comtrade
    `linked` for the bundle and its products, `reduce` for the Help Center articles, `note`
    for the note that each article's and product file's answer gives and `sections` for
    "Products found", sdk-eurostat `quota_wait`, `keep_recorded` with
    `canonical` for its WADL, `pause=5.0` and `reduce`, sdk-faostat `credentials` with its
    samples `keyed`, `reduce` for the terms, `note` for its checks and notes and `canonical`
    for `processing_time`, sdk-google-mail `reduce` alone, every note of its pages static,
    sdk-usda-esmis `linked` for
    the newest release and `reduce` for the calendar excerpt, its followed redirect to
    another host recorded by its status, sdk-usda-esr, sdk-usda-gats and sdk-usda-psd
    `note` and `linked` for the FAS portal kit, `reduce` for their part of the shared
    document and `sections` for how their parts of the two documents compare, which needs
    both rows, sdk-usda-nass `reduce` and a `vocabulary` of the phrases on its api page that
    state nothing new, sdk-usda-wasde `origin` for USDA's CDN origin,
    `linked` and `reduce`, and sdk-x `canonical` for its scope lists and `reduce`, its
    footer's page declared without a file and with `stable=False`, since the frame searches a
    page whole. sdk-google-mail, sdk-usda-wasde and sdk-x check each page's title in `reduce`
    from a table of their own, since core's `Page` holds no title, and sdk-faostat and
    sdk-usda-esmis keep their check of their YAML document's `info` in a hook, since the
    frame parses a JSON document alone. Each `info.license`, `info.termsOfService` and
    `info.contact` that a JSON document holds is recorded as a `Statement` from it, sdk-x's
    `info.contact` among them — the
    frame's rules reach a source through core and no longer through twelve copies, the
    source's page files stay byte for byte as its hooks make them, and the frame stops on
    such an `info` field that the attribution does not record
    (https://github.com/xippios/sdk-core/issues/435).
    `scripts/refresh_upstream.py` (sdk-cashctrl) — ported with `split` for its one page,
    its word check inside it, `note` for the files that keep a nested table as HTML and
    `sections` for its vendor examples, its attribution recording "Terms of Service" from
    its page with its link to https://cashctrl.com/en/about/terms, which the error handling's
    text links, and its footer's copyright notice from its page, which the frame reads in the
    logo's alternative text and checks on every run, its own check of the notice in `split`
    deleted, and six things of its script given up: `--from-file`, its
    run from a saved copy of the page that spends no request, since the frame takes no
    option of a source's own, its own User-Agent, which names its repository, for the
    family's, its request for the page gzipped, since the frame asks for each page as it
    is, at the cost of a larger transfer and no byte of its files, the removal of an
    entry's file at the top of `docs/upstream/` once the table of contents drops the entry,
    which the frame makes in the subdirectories it writes to alone, so the port puts its
    entries under one or removes such a file by hand, `--check` naming no leftover, the
    fragment of its entry in each split file's row of `FETCHED.md`, `index.html#/order`,
    since the frame's row of a file split from a page names the page's URL, the file's
    first line keeping the fragment, and its check that the notice stands in the footer's
    logo, since the frame checks the notice on the page and tells no part of a page apart —
    the frame carries none of the six while one source alone needs it, and stops on the link
    while the attribution does not record it
    (ADR-0023, decision 2, ADR-0046, decisions 2 and 7,
    https://github.com/xippios/sdk-cashctrl/issues/134).
    `docs/upstream/FETCHED.md` — rewritten once by the first run of the ported script, in
    the frame's form, every row with an ETag gaining the code span and the mark and the
    403 rows moving to `Not fetched`, a run that stops until the attribution records what it
    finds in an image's alternative text or a linked statement's words outside its link,
    which no offline run shows — the frame writes it alone (ADR-0028, decision 4,
    ADR-0046, decision 7).
    `tests/test_refresh_upstream.py` — its tests of what the frame now does, the render of
    `FETCHED.md` with its sentences, the row of `OBSERVED.md` and the table `Not fetched`,
    the write with the removal of a file no longer produced, and `--check` with its
    comparison of the committed `FETCHED.md`, deleted with the copy, since core's
    `tests/refresh/test_upstream.py` holds each, and its tests of the source's own hooks and
    of what its `Snapshot` declares kept, calling the hooks or reading the declaration, as
    `docs/handover.md` names each test per source — the tests call `render_fetched`, and
    all but sdk-eurostat's `write_snapshot` and `Response`, which the port deletes from the
    script, and §15, items 3 and 4, delete a copy with its tests.
