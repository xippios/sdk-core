- One key class, `KeyAuth(env_var, location=..., name=...)`, sends a key where upstream takes
  it, `location` one of `"query"`, `"header"`, `"bearer"` and `"basic"`, `name` the parameter
  or header, and takes the place of `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth` and
  `BasicKeyAuth`, which leave `xippios.core` and `xippios.core.client`. `ClientConfig` takes
  one `read_timeout`, 60 s by default, in place of `Timeouts`, which leaves, the other
  timeouts 10 s each. What no source calls leaves the client: `decode_text`, the response
  branch and `delimiter=` of `decode_csv`, which reads a comma-separated file or text stream,
  `decode_json` from the two lists, `BasicKeyAuth(password=)`, `RenewingBearerAuth(margin=)`
  with its attribute, the bearer renewed 60 s before it lapses, the client's `async with`,
  whose place `aclose()` takes, and the second strip of a cached answer's wire headers.
  (ADR-0059, §6, §7, https://github.com/xippios/sdk-core/issues/473,
  https://github.com/xippios/sdk-core/issues/475)
  - Hand-apply: `src/xippios/usda/nass/_client.py` (sdk-usda-nass) — at `:19` and `:97`,
    `QueryKeyAuth("key", API_KEY_ENV, source=SOURCE)` becomes `KeyAuth(API_KEY_ENV,
    location="query", name="key", source=SOURCE)` with its import — the four key classes are
    one, and until it stands every test fails at the import of `_client.py`.
    `src/xippios/comtrade/_client.py` (sdk-comtrade) — at `:26` and `:224`,
    `HeaderKeyAuth("Ocp-Apim-Subscription-Key", API_KEY_ENV, source=SOURCE)` becomes
    `KeyAuth(API_KEY_ENV, location="header", name="Ocp-Apim-Subscription-Key",
    source=SOURCE)`, and at `:32`, `:57`, `:204` and `:233` `TIMEOUTS = Timeouts(read=180.0)`
    with `timeouts=TIMEOUTS` becomes `read_timeout=180.0` on its `ClientConfig`, the constant
    a float or gone from `__all__`, as `CLAUDE.md` names it — `Timeouts` leaves, and until it
    stands every test fails at the import of `_client.py`.
    `tests/test_tasks.py` (sdk-comtrade) — at `:61` and `:1138-1139`,
    `test_read_timeout_is_three_minutes_the_rest_family_defaults` asserts
    `config.read_timeout == 180.0` in place of `TIMEOUTS`' four fields — the other three are
    core's and no field of the config, and the test fails at the import of `TIMEOUTS` or at
    `config.timeouts`.
    `src/xippios/x/_client.py` (sdk-x) — at `:9` and `:192`, `BearerAuth(API_KEY_ENV,
    source=SOURCE)` becomes `KeyAuth(API_KEY_ENV, location="bearer", source=SOURCE)` with
    its import — until it stands every test fails at the import of `_client.py`.
    `scripts/record_fixture.py` (sdk-x) — at `:127`, `:680` and `:685`, the two
    `BearerAuth(API_KEY_ENV, ...)` become `KeyAuth(API_KEY_ENV, location="bearer", ...)`,
    `key=WRONG_KEY` kept — `tests/test_record_fixture.py` fails at the script's import, and
    mypy over `scripts/` at the name.
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — at `:36` and `:384`,
    `BasicKeyAuth(TENANTS.var(org, "API_KEY"), source=SOURCE)` becomes
    `KeyAuth(TENANTS.var(org, "API_KEY"), location="basic", source=SOURCE)` with its import
    — until it stands every test fails at the import of `_client.py`.
    `scripts/record_fixture.py` (sdk-cashctrl) — at `:184` and `:1112`, `BasicKeyAuth(key_var,
    key=..., source=SOURCE)` becomes `KeyAuth(key_var, location="basic", key=...,
    source=SOURCE)` — mypy over `scripts/` fails at the name, and so does a recording.
    `tests/test_client.py` (sdk-usda-gats `:132`, sdk-usda-esr `:115`) — `auth.header ==
    "X-Api-Key"` becomes `(auth.location, auth.name) == ("header", "X-Api-Key")` — the
    gateway's auth is a `KeyAuth`, whose `name` holds the header, and the test fails at
    `header`.
    `scripts/refresh_reference.py` (sdk-usda-nass) — at `:267`,
    `timeouts=replace(configured.timeouts, read=READ_TIMEOUT)` becomes
    `read_timeout=READ_TIMEOUT` — the config has no `timeouts`, and
    `tests/test_refresh_reference.py` fails at `:271-282`, whose asserts then read
    `configured.read_timeout == 60.0`, `config.read_timeout` inside the block and the
    request's `timeout` extension `{"connect": 10.0, "read": 300.0, "write": 10.0, "pool":
    10.0}`.
    `src/xippios/google/mail/_consent.py` (sdk-google-mail) — at `:254`, the code exchange's
    `timeout=config.timeouts.to_httpx()` becomes `timeout=httpx.Timeout(10.0,
    read=config.read_timeout)` — the exchange is sent outside core's client and keeps the
    family's timeouts, and mypy fails at `timeouts`, as the consent does at its exchange.
    `tests/test_live.py` (sdk-eurostat `:226`) — `test_list_datasets_upstream_toc_still_reads`
    takes `httpx.Timeout(10.0, read=config.read_timeout)` in place of
    `config.timeouts.to_httpx()` — mypy fails at `timeouts`, and the live test at its call.
    `tests/test_live.py` (sdk-comtrade `:50`, sdk-eurostat `:71`, sdk-faostat `:74`,
    sdk-usda-esmis `:49`, sdk-usda-esr `:59`, sdk-usda-gats `:62`, sdk-usda-nass `:27`,
    sdk-usda-psd `:46`, sdk-usda-wasde `:152`, sdk-x `:53`) — `test_upstream_answers` reads
    `config.timeouts.to_httpx()`, which becomes `httpx.Timeout(10.0,
    read=config.read_timeout)` for as long as the probe stands — mypy fails at `timeouts`.
