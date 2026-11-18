- `RenewingBearerAuth`, in `xippios.core.client.auth` and exported with `BearerToken`, is the
  base of an upstream that exchanges a login or a refresh token for a short-lived bearer. The
  source writes `token_request` and `read_token`, and the base keeps the bearer until `margin`
  (60 s) before its expiry, exchanges once more on a 401 (`renew_on`), runs the first exchange
  single-flight and streams a download through it. The testing plugin pins the placeholder on
  every credential that a token request reads through `credential`, and a variable unset or
  empty is still its `ConfigError`.
  (ADR-0025, ADR-0013, §7, §10, https://github.com/xippios/sdk-core/issues/156)
  - Hand-apply: `src/xippios/faostat/_client.py` (sdk-faostat) — `LoginAuth` (lines 173 to
    333) becomes a `RenewingBearerAuth` that keeps what is FAOSTAT's. It sets
    `renew_on = REFUSED`, and its `__init__(*, source, base_url, clock)` keeps `login_url` and
    calls `super().__init__(source=source, clock=clock)`. Its `token_request` is `_login`
    (lines 237 to 250), reading `self.credential(USERNAME_ENV)` and
    `self.credential(PASSWORD_ENV)`, without the `User-Agent` copy, which the base makes. Its
    `read_token` parses `Auth` with `_keep`'s `ValidationError` (lines 280 to 289) and returns
    `BearerToken(result.access_token, result.expires_in)`. Its `token_refused` returns
    `_login_refused(response, source=self.source, hint=...)` where `_credentials_refused`
    holds, else `super().token_refused(response)`. Its `credential_help` returns the account
    text of `_credential` (lines 130 and 131). Deleted are `_credential` (lines 120 to 133),
    `EXPIRY_MARGIN` (lines 96 and 97, and line 412 of `__all__`), `reset`, `_current`, `_keep`,
    `_sign`, `async_auth_flow` and `sync_auth_flow`, and the imports `os`, `threading`,
    `AsyncGenerator`, `Generator`, `SecretStr`, `ConfigError`, `UpstreamError` and
    `error_from_response`, while `BearerToken` and `RenewingBearerAuth` are imported from
    `xippios.core`. The module docstring names core's `RENEWAL_MARGIN` for `EXPIRY_MARGIN`
    (line 14), and the class docstring drops "Two requests that start together before the
    first login has answered may each log in" (lines 185 and 186). Its importers hold as
    written: `api/auth_login.py` (`LOGIN_PATH`), and `tests/test_api.py`, `tests/test_tasks.py`,
    `tests/test_refresh_reference.py` (`auth.reset()`) and `tests/test_live.py`
    (`auth.async_auth_flow`) — core's base carries the flow, single-flight, and it takes this
    flow's way of reading the token answer alone on the async client only. FAOSTAT refuses a
    bearer with a 401 or a 403 (ADR-0025, amendment 2026-11-18, point c).
    `tests/test_client.py` (sdk-faostat) — the import of `EXPIRY_MARGIN` (line 52) goes, and
    `test_the_token_lapses_expires_in_less_the_margin_after_the_login` reads `timed.margin`
    (line 190). The other tests of `LoginAuth` hold as written, the sync flow's refusal
    included, since core's message says "async client only" — the margin is core's.
    `CLAUDE.md` (sdk-faostat) — "and two requests that start together before the first login
    answers may each log in" (lines 214 and 215) goes, and "(queue row 252)" (lines 16 and
    212) names core's `RenewingBearerAuth` — the base exchanges once for both.
    `src/xippios/google/mail/_auth.py` (sdk-google-mail) — `RefreshTokenAuth(EnvKeyAuth)`
    (line 154) becomes a `RenewingBearerAuth` that keeps what is Google's. Its signature
    stays, and its `__init__` sets `self.env_var` and calls `super().__init__(source=source,
    credentials=None if key is None else {env_var: key}, clock=clock)`. Its `token_form` reads
    `self.credential` for the client id, the secret and the refresh token that `self.key()`
    read (line 268). Its `token_request` builds the POST to `TOKEN_URL` without the
    `User-Agent` copy. Its `keep` (lines 278 to 339) splits in two: `read_token` keeps the
    granted scopes and `refresh_token_expires_in` under `_state` and returns
    `BearerToken(answer.access_token, answer.expires_in)`, and `token_refused` returns the
    `invalid_grant` `AuthError` and the `invalid_client` `ConfigError`, else
    `super().token_refused(response)`. Its `credential_help` returns `_credential`'s text for
    the two client variables and "export it or pass the key explicitly" for the refresh
    token's. Deleted are the comment naming row 252 (lines 1 to 3), `_credential` (lines 110
    to 124), `EXPIRY_MARGIN` (lines 76 and 77, and line 59 of `__all__`),
    `requires_response_body` (line 202), `_access_token` and `_lapses_at`, `reset`,
    `_current`, `apply` and `auth_flow`, and the imports `os`, `Generator`, `EnvKeyAuth`,
    `UpstreamError` and `error_from_response`, while `BearerToken`, `RenewingBearerAuth` and
    `XippiosError` are imported from `xippios.core`. The docstrings name the base for
    `EnvKeyAuth.key` and `auth_flow` (lines 8 to 10) and for the plugin's pin (lines 28 and
    29), and they drop "may each refresh" (lines 166 and 167) and the buffering of every
    answer (lines 173 to 175). Its importers hold as written: `_client.py`, `_tenants.py`,
    `_cli.py` and `_consent.py`, `tests/test_consent.py`, and `scripts/record_fixture.py`,
    whose `token_form()` and `refresh_auth(DEMO, key=...)` keep their meaning — core takes
    the flow that reads the token answer alone and runs on the async client only, so no
    other answer, a download's included, is buffered and no sync flow is left. The refresh
    token is read at each refresh, not cached, and a variable counts as unset when it is
    empty, as `EnvKeyAuth` reads one, and goes out as it stands, unstripped.
    `tests/test_tasks.py` (sdk-google-mail) — `granted()` calls `auth.read_token(...)` for
    `auth.keep(...)` (line 202) — `read_token` keeps the scopes.
    `tests/test_auth.py` (sdk-google-mail) — the import of `EXPIRY_MARGIN` (line 28) goes,
    `test_a_token_is_renewed_within_the_margin_of_its_expiry` takes the auth from
    `demo_client(clock)` and reads `auth.margin` (lines 110 and 112), and the docstring's
    `EnvKeyAuth.key` (line 5) is `RenewingBearerAuth.credential` — the margin and the pin are
    core's.
    `tests/conftest.py` (sdk-google-mail) — the comment's "as the refresh token, pinned on
    EnvKeyAuth" (line 22) names every credential of the refresh, pinned on
    `RenewingBearerAuth.credential` — the same.
    `CLAUDE.md` (sdk-google-mail) — `RefreshTokenAuth` (lines 16 and 33) is named a subclass
    of core's `RenewingBearerAuth`, without "queue row 252" — the row closes with core 0.4.0.
