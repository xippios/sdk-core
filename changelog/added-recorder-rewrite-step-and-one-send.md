- `record`, `record_sync` and `fixture_from_response` take `rewrite=`, a source's own step that
  returns the scrubbed `Fixture` rewritten with the values it replaced, and nothing is written
  while one of those values is left in the URL, a header value, a body or a string decoded from
  a JSON body. The order is the scrub, the step, the check and the one write, and `send_once`
  and `send_once_sync` send a recording's one request without the write, so no recorder builds
  a client for one attempt.
  (ADR-0048, §10, https://github.com/xippios/sdk-core/issues/322, https://github.com/xippios/sdk-core/issues/281)
  - Hand-apply: `scripts/record_fixture.py` (sdk-x) — deletes the client built with
    `RetryPolicy(max_attempts=1)`, `exchange`, `survivors`, `_strings`, `_masked` and its calls
    of `fixture_from_response` and `write_fixture`, and records with
    `record_sync(client, ..., rewrite=step)`, the step running `unknown_answered`, `rewrite` and
    the 256 KiB test and returning the values `rewrite` replaced, stripped. It keeps the command
    line, `refusal` with `ADMITTED` and `WRAPPERS`, the estimate, `--wrong-key` as `auth=`, the
    summary and the rewrite rules — core runs the step and checks its values.
    `tests/test_record_fixture.py` (sdk-x) — the two tests of `survivors` assert the refusal of
    `fixture_from_response(..., rewrite=step)`, which names the place, `response body`, where
    `survivors` named the key's path — the check and its message are core's.
    `scripts/record_fixture.py` (sdk-google-mail) — the single exchange sends with
    `send_once_sync` through the demo account's client, the token request with `auth=None` and
    `--garbage-bearer` as `auth=`, and every exchange, a task's too, builds its fixture with
    `fixture_from_response(response, scrub=..., rewrite=step)`, the step running `rewrite` and
    `check` and raising `ValueError` on a leak. It keeps `MessageScrub`, the text rules,
    `check`, the command line, the write safety rule and `recording_client` for `record_task`
    alone, until core records the exchanges of a task (https://github.com/xippios/sdk-core/issues/174)
    — the single exchange needs no client of its own.
    `scripts/record_fixture.py` (sdk-cashctrl) — deletes `recording_client`, sends with
    `send_once_sync(client_for(DEMO), ...)`, `--wrong-key` as `auth=`, and passes
    `TenantScrub(...).apply` as the step of `fixture_from_response(..., rewrite=...)`, which
    returns the pair of the rewritten fixture and no value of its own, `(rewritten, [])`, since
    its verify by pattern refuses what survives, the subdomain in any case among them. It
    keeps `TenantScrub` with its verify by pattern, `check`, the reminder after a write, the
    guards, whose reads of `order/read.json` and `order/bookentry/read.json` are sent once by
    `send_once` through the demo organisation's own client, which retries a 5xx, a read that
    core refuses as a 1xx or 3xx refusing the write, and its refusal of another 2xx and of a
    binary body at a file path — the one-attempt client and the refusal of a 1xx or 3xx are
    core's, and a step that returns the fixture alone raises `TypeError`.
    `tests/test_record_fixture.py` (sdk-cashctrl) — `test_the_recording_client_never_retries`
    goes with `recording_client`, `test_a_5xx_is_recorded_after_one_request` sends through
    the demo organisation's own client, `test_secrets_are_redacted_plain_and_percent_encoded`,
    `test_the_host_then_the_secrets_then_the_rewrite` and
    `test_the_verify_passes_a_clean_fixture` unpack the pair that `apply` returns, and the
    redirect of `test_a_file_path_writes_no_answer_but_an_error_or_a_refusal` asserts the
    refusal of `send_once`, which names the method, the path and the status, where the
    recorder's own check of a file path's answer named the file path — the recorder builds no
    client of its own, `send_once` refuses the 302 before that check reads it, and
    `test_an_order_write_naming_an_unmarked_or_unreadable_order_is_refused` holds one read of
    each order, which a guard that reads through the retrying client exceeds
    (https://github.com/xippios/sdk-cashctrl/issues/134).
    `scripts/cut_sample.py` (sdk-usda-wasde) — `fetch` sends with
    `send_once(AsyncClient(config), chosen.url)` in place of the client built for one attempt
    and `client.request(..., raise_on_error=False)`, and keeps its refusal of every status but
    200, its samples, its sha256 test and `write_download_fixture` — the one send is core's.
