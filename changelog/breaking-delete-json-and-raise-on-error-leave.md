- `AsyncClient.delete_json` and the switch `raise_on_error` of `request` leave, so the client
  raises every error answer through `classify` and the taxonomy. A DELETE goes through
  `request("DELETE", path)`, and a script or a live test that needs an error answer as it
  came takes `xippios.core.testing.send_once`, which sends once and returns any status.
  (ADR-0037, §6, https://github.com/xippios/sdk-core/issues/473)
  - Hand-apply: `src/xippios/google/mail/api/drafts_delete.py` (sdk-google-mail) — at
    `:33`, `await client.delete_json(...)` becomes `await client.request("DELETE", ...)`,
    and the docstring at `:24` says so — `delete_json` leaves, and until it stands every
    test of `delete_draft` fails at the call.
    `scripts/record_fixture.py` (sdk-cashctrl) — at `:493-499`, `:500` and `:552-553`,
    `client.request(..., raise_on_error=False)` becomes `await send_once.async_fn(client,
    path, method=..., ...)` of `xippios.core.testing`, and the docstring at `:116` says so —
    `tests/test_record_fixture.py` fails at the keyword, and mypy over `scripts/` too.
    `tests/test_live.py` (sdk-cashctrl) — at `:152` and `:960-961`,
    `client.request("GET", ..., raise_on_error=False)` becomes
    `await send_once.async_fn(client, ...)` — mypy fails at the keyword, and the live tests
    at their call.
    `scripts/record_fixture.py` (sdk-google-mail) — at `:967-974` and `:981-987`,
    `client.request(..., raise_on_error=False)` becomes `await send_once.async_fn(client,
    ...)`, the token exchange keeping `auth=None` — `tests/test_record_fixture.py` fails
    at the keyword, and mypy over `scripts/` too.
    `scripts/cut_sample.py` (sdk-usda-wasde) — at `:249`, `client.request("GET",
    chosen.url, raise_on_error=False)` becomes `await send_once.async_fn(client, chosen.url,
    max_read_bytes=None)` where a report may pass 32 MiB — mypy over `scripts/` fails at
    the keyword.
    `scripts/record_fixture.py` (sdk-x) — at `:624`, `client.request("GET", path,
    params=params, raise_on_error=False)` becomes `await send_once.async_fn(client, path,
    params=params)` — `tests/test_record_fixture.py` fails at the keyword, and mypy over
    `scripts/` too.
