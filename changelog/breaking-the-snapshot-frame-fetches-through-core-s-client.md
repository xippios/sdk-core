- The snapshot frame of `xippios.core.refresh` sends every request through core's
  `AsyncClient`, one that it builds from the slug and that names itself
  `xippios-<slug>/<version>` as the source's client does, or the source's own handed as
  `Snapshot(client=...)`, and it follows a redirect on the page's host itself. `Credentials`
  and `quota_wait` leave for the client's credentials with the snapshot's `variables` and for
  the client's retry policy, `Page.keep_recorded` for the source's `reduce`, `Page.origin` for
  two declared pages, and `--out` and `indent` leave, while `load_json` is now `read_json` and
  `split`, `pause` and `Page.keyed` stay. `FETCHED.md` rises to form 2, which a source's first
  refresh on this core writes whole.
  (ADR-0062, §3, https://github.com/xippios/sdk-core/issues/482)
  - Hand-apply: `scripts/refresh_upstream.py` (sdk-faostat) — the login (`:437-497`) and the
    keyed headers leave, the four samples stay `keyed=True`, and the snapshot takes `client=`
    the source's client, whose auth logs in, with
    `variables=("FAOSTAT_USERNAME", "FAOSTAT_PASSWORD")` — the client holds the credentials
    and sends them to its base URL's origin alone.
    `scripts/refresh_upstream.py` (sdk-eurostat) — the wait after a 429 (`:442`, `:511-529`)
    becomes `client=` a client of the website with
    `RetryPolicy(max_attempts=2, backoff_base=10.0, backoff_max=900.0, jitter=False)` and a
    `classify` that reads `X-Rate-Limit-Retry-After-Seconds` into a `RateLimitError`, and the
    WADL kept as recorded (`:1146-1163`) is kept by `reduce`, while `pause=5.0` stays —
    `quota_wait` and `Page.keep_recorded` leave the frame.
    `scripts/refresh_upstream.py` (sdk-usda-wasde) — each page that `www.usda.gov` refuses
    with 403 (`capture_usda`, `:1032-1061`) is declared twice, `Page(url, status=403, ...)`
    and its copy `Page(f"{ORIGIN}{path}", file)` — `Page.origin` leaves the frame, and a run
    stops once the edge answers otherwise.
    `scripts/refresh_upstream.py` (sdk-google-mail, sdk-usda-esr, sdk-usda-gats,
    sdk-usda-psd) — a JSON document cut to its part is read with `read_json` and written with
    `dump_json`, neither taking `indent` — the frame's reader takes a name of its own beside
    the root's `load_json`.
    `tests/test_refresh_upstream.py` (sdk-google-mail, sdk-x) —
    `test_no_page_is_kept_as_observed_md` (`:90`, `:88`) runs the script with `--out`, which
    the frame refuses, so the port runs it without and reads the declaration's `out` —
    `--out` leaves the command line.
    `docs/upstream/FETCHED.md` (every source) — the first refresh on this core rewrites it
    whole in form 2 and sends `xippios-<slug>/<version>`, a User-Agent that eleven sources
    send for the first time, in a networked run with the maintainer's consent and its count —
    the frame fetches through core's client.
