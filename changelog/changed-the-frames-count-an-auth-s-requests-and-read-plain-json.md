- The two refresh frames count each request the client sent for a call, the token requests of a
  `RenewingBearerAuth` and its resend after a refused bearer among them, from the answer's
  `history`, which `send_once` and a download's refusal now keep as statuses alone, and not a
  token request whose answer the auth refuses, which ends the run, and the snapshot frame
  prints its count on a failed run too, as the reference frame does.
  `xippios.core.refresh.parse_json` reads a JSON answer that a hook writes nothing of again,
  refusing a key twice and keeping compact JSON as served, and `read_json` reads through it. A
  check of one page against another runs in `Snapshot.sections`, which sees every row before
  anything is written.
  (ADR-0062, ADR-0059, ADR-0025, §3, https://github.com/xippios/sdk-core/issues/579)
  - Hand-apply: `scripts/refresh_upstream.py` — a source with a login drops its own count of
    the frame's requests and keeps its count of logins, a source drops its own reader of JSON
    that refuses a duplicate key alone for `parse_json`, and a check of one page against
    another moves from a hook that sees one page into `sections`, which returns `()` and
    raises `changed` — the frame counts the auth's requests, holds the reader and sees every
    row before it writes.
    `scripts/refresh_reference.py` — a source with a login drops its own count of the frame's
    requests and keeps its count of logins — the frame counts the auth's requests in its line.
