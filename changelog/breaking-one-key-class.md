- One key class, `KeyAuth(env_var, location=..., name=...)`, sends a key where upstream takes
  it, `location` one of `"query"`, `"header"`, `"bearer"` and `"basic"` and `name` the
  parameter or header, and takes the place of `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth`
  and `BasicKeyAuth`, which leave `xippios.core` and `xippios.core.client`. A query key
  registers its name for the redaction as `QueryKeyAuth` did, and the basic user name goes
  with an empty password, since `BasicKeyAuth(password=)` leaves with its class.
  (ADR-0059, §7, https://github.com/xippios/sdk-core/issues/473)
  - Hand-apply: `src/xippios/usda/nass/_client.py` (sdk-usda-nass) — at `:19` and `:97`,
    `QueryKeyAuth("key", API_KEY_ENV, source=SOURCE)` becomes `KeyAuth(API_KEY_ENV,
    location="query", name="key", source=SOURCE)` with its import — the four key classes are
    one, and until it stands every test fails at the import of `_client.py`.
    `src/xippios/comtrade/_client.py` (sdk-comtrade) — at `:26` and `:224`,
    `HeaderKeyAuth("Ocp-Apim-Subscription-Key", API_KEY_ENV, source=SOURCE)` becomes
    `KeyAuth(API_KEY_ENV, location="header", name="Ocp-Apim-Subscription-Key",
    source=SOURCE)` with its import — until it stands every test fails at the import of
    `_client.py`.
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
    `scripts/record_fixture.py` (sdk-cashctrl) — at `:184` and `:1112`,
    `BasicKeyAuth(key_var, key=..., source=SOURCE)` becomes `KeyAuth(key_var,
    location="basic", key=..., source=SOURCE)` — `tests/test_record_fixture.py` fails at the
    script's import, and mypy over `scripts/` at the name.
    `tests/test_client.py` (sdk-usda-gats `:132`, sdk-usda-esr `:115`) — `auth.header ==
    "X-Api-Key"` becomes `(auth.location, auth.name) == ("header", "X-Api-Key")` — the
    gateway's auth is a `KeyAuth`, whose `name` holds the header, and the test fails at
    `header`.
