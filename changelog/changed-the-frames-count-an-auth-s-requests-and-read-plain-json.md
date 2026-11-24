- The two refresh frames count each request that the client hands to its transport, the token
  requests of a `RenewingBearerAuth` and its resend after a refused bearer among them, those of
  a call that an error ends and a refused login's included, and the snapshot frame prints its
  count on a failed run too, as the reference frame does. `send_once` and a download's refusal
  keep the earlier answers of an auth's flow in their `history` as statuses alone, and
  `xippios.core.refresh.parse_json` reads a JSON answer that a hook writes nothing of again,
  refusing a key twice and keeping compact JSON as served, with `read_json` reading through it.
  A check of one page against another runs in `Snapshot.sections`, which sees every row before
  anything is written.
  (ADR-0062, ADR-0059, ADR-0025, §3, https://github.com/xippios/sdk-core/issues/579,
  https://github.com/xippios/sdk-core/pull/580)
  - Hand-apply: `scripts/refresh_upstream.py` (sdk-faostat, sdk-x, sdk-eurostat, sdk-usda-esr,
    sdk-usda-gats, sdk-usda-psd) — sdk-faostat drops its own count of the frame's requests and
    keeps its count of logins, and its check of one page against another moves from a hook
    that sees one page into `sections`, which returns `()` and raises `changed`, while each of
    the six drops its own reader of JSON that refuses a duplicate key alone for `parse_json` —
    the frame counts the auth's requests, holds the reader and sees every row before it writes.
    `scripts/refresh_reference.py` (sdk-faostat) — drops its own count of the frame's requests
    and keeps its count of logins, which ADR-0062 decision 16 leaves to it — the frame counts
    the auth's requests in its line.
