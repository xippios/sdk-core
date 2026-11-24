- `record` and `send_once` of `xippios.core.testing` are the sync functions under their plain
  names, and `record_sync`, `send_once_sync`, `record_task`, `record_task_sync`, `array_key=`
  and `mount_fixture` leave with the client's collector. A caller on an event loop awaits
  `record.async_fn` or `send_once.async_fn`, a task of several requests is recorded by its
  source's own capture, `max_bytes=` cuts a JSON array alone and `replay` loads and mounts a
  fixture. `Scrub` replaces and verifies each secret percent-encoded and behind a JSON escape
  too, so a recording names a value once and none of its encoded forms.
  (ADR-0066, §10, https://github.com/xippios/sdk-core/issues/483)
  - Hand-apply: `scripts/record_fixture.py` (sdk-cashctrl) — `TenantScrub` takes no secrets,
    its patterns of them plain or percent-encoded at `:915-917` and the two places that read
    them leave while its host and subdomain patterns stay, and the sends that the note of
    `delete_json` ports await `send_once.async_fn` — core's `Scrub` replaces and verifies a
    secret's encoded forms itself, and the sync `send_once` refuses core's own loop, on which
    `exchange_async` runs through `sync`.
    `scripts/record_fixture.py` (sdk-google-mail) — its own capture of a task stays,
    `recording_client` with its `keep`, `task_exchanges_async` and the loop of `record_task`
    that numbers, builds and writes the fixtures, where its port to core 0.4.1 called
    `record_task_sync`, and `forms_of` with `_secret_pattern` (`:694-701`) leave, so
    `rewrite` replaces the secrets no more — `record_task` and the collector go back to it,
    and `Scrub` takes the encoded forms.
    `tests/test_record_fixture.py` (sdk-cashctrl, sdk-google-mail) — sdk-cashctrl's
    `test_secrets_are_redacted_plain_and_percent_encoded` (`:2292`) keeps its assertions
    with the step given no secrets, which core's scrub now meets alone, and its
    `test_a_percent_encoded_key_is_redacted_and_goes_to_review` (`:2259`) asserts the key
    `REDACTED` in the body and the `X-Echo` header by core's scrub and drops its exit status
    1 and its review line, since the step finds no key left to replace. sdk-google-mail's
    `test_forms_of_a_secret_cover_the_encodings` (`:127`) leaves with `forms_of`, and its
    `test_core_alone_leaves_the_encoded_refresh_token_which_the_check_refuses` (`:99`)
    asserts that core alone redacts the refresh token's `%2F` form, `check` finding no leak —
    each fails as it stands once core's scrub takes the encoded forms and the patterns leave.
    `scripts/record_fixture.py` (sdk-x) — its port to core's frame records through
    `record(client, path, fixture, ...)`, the sync function, and imports no `record_sync` —
    `record_sync` leaves, so the script fails at the import, and its tests with it.
    `scripts/cut_sample.py` (sdk-usda-wasde) — the download's one request in the async
    `fetch` awaits `send_once.async_fn`, as the note of `delete_json` has it — `fetch` runs
    on core's loop through `sync`, where the sync `send_once` raises `RuntimeError`.
    `CLAUDE.md` (sdk-faostat) — a recording names the user name and the password once each in
    `Scrub(secrets=[...])`, without their `quote` and `quote_plus` forms (`:252-254`) —
    `Scrub` replaces and verifies those forms itself.
