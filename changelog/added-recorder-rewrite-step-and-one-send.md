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
    returns no value of its own, since its verify by pattern refuses what survives, the
    subdomain in any case among them. It keeps `TenantScrub` with its verify by
    pattern, `check`, the reminder after a write, the guards, whose reads go to the demo
    organisation's own client, and its refusal of another 2xx and of a binary body at a file
    path — the one-attempt client and the refusal of a 1xx or 3xx are core's.
    `tests/test_record_fixture.py` (sdk-cashctrl) — `test_the_recording_client_never_retries`
    goes with `recording_client`, and `test_a_5xx_is_recorded_after_one_request` sends through
    the demo organisation's own client — the recorder builds no client of its own.
    `scripts/cut_sample.py` (sdk-usda-wasde) — `fetch` sends with
    `send_once(AsyncClient(config), chosen.url)` in place of the client built for one attempt
    and `client.request(..., raise_on_error=False)`, and keeps its refusal of every status but
    200, its samples, its sha256 test and `write_download_fixture` — the one send is core's.
