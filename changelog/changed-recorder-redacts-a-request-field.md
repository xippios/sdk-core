- A recorder writes `REDACTED` in place of the value of a field of a request that it must not
  keep and drops none of them, as conventions §10 now say, so that the census of built answers
  compares a replay with its recording key by key. Core's census compares what it compared,
  as strict for every source. (ADR-0048, §10, https://github.com/xippios/sdk-core/issues/439)
  - Hand-apply: `scripts/record_fixture.py` (sdk-google-mail) — `raw` in a write's request
    body written as `REDACTED`, where `MessageScrub` dropped the key, and `check` refusing a
    request's `raw` only where it holds another value — the census reads a key that the
    recording lacks as another body.
    `tests/test_record_fixture.py` (sdk-google-mail) — the assertions on a recorded write's
    request body read `"raw": "REDACTED"` where they read no `raw` — the recorder keeps the
    key.
    `tests/test_tasks_write.py` (sdk-google-mail) — the assertions on the recorded bodies of
    `send_message/ok.json` and `create_draft/ok.json` read `"raw": "REDACTED"` — the recorder
    keeps the key.
    `tests/fixtures/send_message/ok.json` (sdk-google-mail) — recorded again with the changed
    recorder, in a pull request before the adoption, a keyed write on the demo mailbox that
    needs the maintainer's go and a budget — the census names `test_send_message_sends_it` and
    `test_send_message_over_mcp` as answering another body until then.
    `tests/fixtures/create_draft/ok.json` (sdk-google-mail) — recorded again in the same pull
    request and the same run — the census names `test_create_draft_stores_the_message_as_a_draft`
    and `test_create_draft_over_mcp` as answering another body until then.
