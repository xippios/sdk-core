- `sent_bodies(route)` gives the bodies a route received, oldest first, a JSON body
  decoded and a form as a mapping of its fields, credentials `REDACTED` by the rule of
  `sent_urls`, `None` for a request without one, so a test asserts a write's body
  without keeping a request from `route.calls` in its frame.
  (ADR-0013, §10, https://github.com/xippios/sdk-core/issues/183)
  - Hand-apply: `tests/test_tasks_write.py` (sdk-cashctrl) — `sent_body` (lines 100 to
    102), a list of pairs read from `route.calls` → `sent_bodies(route)[-1]`, compared
    with `dict(recorded_body(...))` or a `dict` of the preview's payload, the fields'
    order then unchecked — no request in the test's frame.
    `tests/test_tasks_write.py` (sdk-google-mail) — `sent_body` (lines 98 to 100) →
    `sent_bodies(route)[-1]`, and line 854's empty body → `sent_bodies(route)[-1] is
    None` — no request in the test's frame.
    `tests/test_record_fixture.py` (sdk-google-mail) — the JSON read from `sent.calls` at
    line 712 → `sent_bodies(sent)[-1]["raw"]` — no request in the test's frame.
    `tests/test_consent.py` (sdk-google-mail) — the form read from `token.calls` at line
    160 → `sent_bodies(token)[-1]` — no request in the test's frame.
