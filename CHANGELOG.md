# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: only a breaking change bumps the
minor, conventions §12).

## [0.4.0] - 2026-11-18

### Added

- The fifteen records that carried three amendments or a reversal are restated, each as the
  decision stands, in ADR-0028 to ADR-0042, which supersede ADR-0003, ADR-0004, ADR-0005,
  ADR-0008, ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0018,
  ADR-0019, ADR-0022 and ADR-0024. The old records keep their numbers as history. The
  conventions, now version 1.28, the README, the review checklist, the definition of done and
  core's docstrings cite the standing record, as `ADR-NNNN, decision N`, and a standing
  record's dated point as `ADR-NNNN, amendment YYYY-MM-DD, point x`.
  (ADR-0028, ADR-0029, ADR-0030, ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035, ADR-0036,
  ADR-0037, ADR-0038, ADR-0039, ADR-0040, ADR-0041, ADR-0042,
  https://github.com/xippios/sdk-core/issues/196, https://github.com/xippios/sdk-core/issues/272)
- Core defines the types of the package contract by which a host serves a source:
  `EnvVar(name_or_pattern, *, secret, required)` from `xippios.core`, a variable the package
  needs, and `ToolSet` from `xippios.core.mcp`, what its `build(**options)` returns: its tasks
  as its lock binds them, caps, instructions, version, `main`'s two hooks, `read_only` and
  `loopback_only`. `build_server(tool_set)` builds a source's server from its tool set,
  `register_tasks(server, tool_set)` registers one on a server a host builds from several,
  and `tool_set.option_defaults()` gives the options its hooks take without a command line,
  or raises `ValueError` for one that has no default. `serve_tenants(server, build, ...)`
  builds a multi-tenant source's bound server from the tool set its `build(lock)` returns,
  named as `server` is.
  (ADR-0023, ADR-0026, §7, §8, https://github.com/xippios/sdk-core/issues/245)
  - Hand-apply: `src/xippios/<package>/_client.py` — declare the variables it reads as
    `EnvVar` entries, in the list sdk-template 0.4.0 renders beside `SOURCE`
    (https://github.com/xippios/sdk-template/issues/81) — the file is the source's own, and a
    host reads the list.
    `src/xippios/<package>/mcp.py` — `server = build_server(SOURCE, [getattr(tasks, name) for
    name in tasks.__all__], version=..., instructions=..., caps=...)` → `build()` returning
    `ToolSet(SOURCE, tool_functions(tasks), caps=getattr(tasks, "MCP_CAPS", None),
    instructions=..., version=..., add_options=..., apply_options=...)`, `server =
    build_server(build())`, and `main` given the tool set's hooks in place of
    `getattr(tasks, "mcp_add_options", None)` — sdk-template 0.4.0 renders it
    (https://github.com/xippios/sdk-template/issues/159), so a host serves what the entry
    point serves.
    `src/xippios/cashctrl/mcp.py` (sdk-cashctrl) — after the serve command's entry, `build`
    (lines 27 to 35) → `def build(lock: TenantLock | None = None) -> ToolSet:` returning
    `ToolSet(SOURCE, bind_tasks(tool_functions(tasks), lock), caps=getattr(tasks,
    "MCP_CAPS", None), instructions=tenant_instructions(INSTRUCTIONS, lock),
    version=__version__)`, the import of `MCPServer` (line 9) deleted and `ToolSet` and
    `tool_functions` imported beside `build_server` (line 10), `server = build()` (line 38) →
    `server = build_server(build())`, and the entry point as that entry writes it,
    `serve_tenants(server, build, TENANTS, noun="organisation", check=check_org)` —
    `serve_tenants` builds the bound server from the tool set.
    `src/xippios/cashctrl/mcp_write.py` (sdk-cashctrl) — after the serve command's entry,
    `build` (lines 27 to 37) → returning `ToolSet(SOURCE, bind_tasks(tool_functions(tasks_write),
    lock), caps=getattr(tasks_write, "MCP_CAPS", None),
    instructions=tenant_instructions(INSTRUCTIONS, lock), version=__version__,
    read_only=False)`, the imports as in `mcp.py` (lines 10 and 11), `server = build()` (line
    40) → `server = build_server(build(), name="xippios-cashctrl-write")`, and the entry
    point `serve_tenants(server, build, TENANTS, noun="organisation", check=check_org)` —
    the bound write server takes its name from `server`, as it does
    today.
    `src/xippios/google/mail/mcp.py` (sdk-google-mail) — after the serve command's entry,
    `build` (lines 35 to 43) → `def build(lock: TenantLock | None = None) -> ToolSet:`
    returning `ToolSet(SOURCE, bind_tasks(tool_functions(tasks), lock), caps=getattr(tasks,
    "MCP_CAPS", None), instructions=tenant_instructions(INSTRUCTIONS, lock,
    bound=BOUND_INSTRUCTIONS), version=__version__, loopback_only=True)`, the imports as in
    sdk-cashctrl's `mcp.py` (lines 11 and 12), `server = build()` (line 46) → `server =
    build_server(build())`, and the entry point `serve_tenants(server, build, TENANTS,
    check=check_account)` — the read server is held to loopback by core
    (ADR-0025, D-a), bound or not.
    `src/xippios/google/mail/mcp_write.py` (sdk-google-mail) — after the serve command's
    entry, `build` (lines 39 to 48) → returning `ToolSet(SOURCE,
    bind_tasks(tool_functions(tasks_write), lock), caps=getattr(tasks_write, "MCP_CAPS",
    None), instructions=tenant_instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS),
    version=__version__, read_only=False)`, the imports as in `mcp.py` (lines 15 and 16),
    `server = build()` (line 51) → `server = build_server(build())`, and the entry point
    `serve_tenants(server, build, TENANTS, check=check_account)` — as
    above.
    `src/xippios/mcp/packages.py` (xippios-mcp) — `<path>.mcp.server` and `<path>.tasks`
    (`mcp_write` and `tasks_write` for `:write`), `tasks.__all__` and `MCP_CAPS`, lines 135
    to 159, and `Package.server`, `functions`, `tools` and `caps`, lines 69 to 72 → the
    `ToolSet` of `<path>.mcp.build()` (`mcp_write.build()`), its tools the `__name__` of
    each of `tool_set.tasks` — the contract carries what the host read by name.
    `src/xippios/mcp/servers.py` (xippios-mcp) — `_package_built`, lines 99 to 113, the
    package's own server and its `is_write_server` check → `build_server(tool_set)` per
    endpoint, its kind `tool_set.read_only`, and `_host_built`, lines 127 to 150,
    `register_tasks(server, slug, [package.functions[name] for name in kept], caps=caps or
    None, read_only=not package.ref.write)` → `register_tasks(server,
    dataclasses.replace(tool_set, tasks=kept, caps=cut))`, which carries `loopback_only`
    too, then `tool_set.apply_options(tool_set.option_defaults(), server)` for a tool set
    with hooks — a server the host builds lacked the package's hooks, version, instructions
    and hold (ADR-0026, amendment 2026-10-30, part (a)).
    `src/xippios/mcp/app.py` (xippios-mcp) — `_check_mounted_once`, line 98 and lines 142
    on, goes — every endpoint's server is built from its tool set, so no server object
    serves two endpoints.
- `nearest(value, codes, *, n=3)`, exported from `xippios.core` beside `closest`, names
  up to `n` known integer codes nearest to `value` by number with their names, nearest
  first and the lower of two equally near, for `UnknownCode`'s `closest`. `codes` is keyed
  by the integer or by its text, and each pair keeps its code as `codes` keys it: the
  strategy that sdk-usda-esr and sdk-usda-gats each carried.
  (ADR-0022, ADR-0023, §5, https://github.com/xippios/sdk-core/issues/107)
  - Hand-apply: `src/xippios/usda/esr/params.py` (sdk-usda-esr) — `_closest` (lines 76
    to 93): its first pass, `sorted(codes, key=lambda code: (abs(code - value), code))[:2]`
    (line 87), → `[code for code, _ in nearest(value, codes, n=2)]`, imported from
    `xippios.core` (line 24), and the local name `nearest` of line 87 renamed, since it
    would shadow the import. Its digit pass stays, ESR's own, so `999` still names
    `1001` and `902`, and `1040` still `104`, and the tests of `tests/test_params.py` pass
    unchanged — core takes the second copy (ADR-0023, decision 4).
    `src/xippios/usda/gats/params.py` (sdk-usda-gats) — `_nearest` (lines 409 to 412) and
    its call (line 449) → `nearest(customs_district_id, codes)`, imported from
    `xippios.core` beside `closest` (line 38): the same three ids, keyed by their text,
    in the same order, so `test_an_unknown_customs_district_names_the_nearest_ids` passes
    unchanged — as above.
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
    holds, else `super().token_refused(response)`, which quotes nothing of the answer. Its
    `credential_help` returns the account text of `_credential` (lines 130 and 131). Deleted
    are `_credential` (lines 120 to 133), `EXPIRY_MARGIN` (lines 96 and 97, and line 412 of
    `__all__`), `reset`, `_current`, `_keep`, `_sign`, `async_auth_flow` and `sync_auth_flow`,
    and the imports `os`, `threading`, `AsyncGenerator`, `Generator`, `SecretStr`,
    `ConfigError`, `UpstreamError` and `error_from_response`, while `BearerToken` and
    `RenewingBearerAuth` are imported from `xippios.core`. The module docstring names core's
    `RENEWAL_MARGIN` for `EXPIRY_MARGIN` (line 14) and core's `token_refused` for
    `error_from_response` (lines 22 and 23), and the class docstring drops "Two requests that
    start together before the first login has answered may each log in" (lines 185 and 186).
    Its importers hold as written: `api/auth_login.py` (`LOGIN_PATH`), and
    `tests/test_api.py`, `tests/test_tasks.py`, `tests/test_refresh_reference.py`
    (`auth.reset()`) and `tests/test_live.py` (`auth.async_auth_flow`) — core's base carries
    the flow, single-flight, and it takes this flow's way of reading the token answer alone on
    the async client only. FAOSTAT refuses a bearer with a 401 or a 403 (ADR-0025, amendment
    2026-11-18, point c).
    `tests/test_client.py` (sdk-faostat) — the import of `EXPIRY_MARGIN` (line 52) goes, and
    `test_the_token_lapses_expires_in_less_the_margin_after_the_login` reads `timed.margin`
    (line 190). The other tests of `LoginAuth` hold as written, the sync flow's refusal
    included, since core's message says "async client only" — the margin is core's.
    `CLAUDE.md` (sdk-faostat) — "and two requests that start together before the first login
    answers may each log in" (lines 214 and 215) goes, "(queue row 252)" (lines 16 and 212)
    names core's `RenewingBearerAuth`, and "core's `error_from_response`" (line 218) is core's
    `token_refused`, which quotes nothing of the answer — the base exchanges once for both.
    `src/xippios/google/mail/_auth.py` (sdk-google-mail) — `RefreshTokenAuth(EnvKeyAuth)`
    (line 154) becomes a `RenewingBearerAuth` that keeps what is Google's. Its signature
    stays, and its `__init__` sets `self.env_var` and calls `super().__init__` with `source`,
    `clock` and `credentials=None if key is None else {env_var: key}`. Its `token_form` reads
    `self.credential` for the client id, the secret and the refresh token that `self.key()`
    read (line 268). Its `token_request` builds the POST to `TOKEN_URL` without the
    `User-Agent` copy. Its `keep` (lines 278 to 339) splits in two: `read_token` keeps the
    granted scopes and `refresh_token_expires_in` under `_state` and returns
    `BearerToken(answer.access_token, answer.expires_in)`, and `token_refused` returns the
    `invalid_grant` `AuthError` and the `invalid_client` `ConfigError`, else
    `super().token_refused(response)`, which quotes nothing of the answer where
    `error_from_response` quoted it. Its `credential_help` returns `_credential`'s text for
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
    whose `token_form()` and `refresh_auth(DEMO, key=...)` keep their meaning — core takes the
    flow that reads the token answer alone and runs on the async client only, so no other
    answer, a download's included, is buffered and no sync flow is left. The refresh token is
    read at each refresh, not cached, and a variable counts as unset when it is empty, as
    `EnvKeyAuth` reads one, and goes out as it stands, unstripped.
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
- A multi-tenant source's bound server, its serve command and its write server's check come
  from core again, out of sdk-cashctrl's and sdk-google-mail's copies: `TenantLock`,
  `bind_tasks` and `tenant_instructions` from `xippios.core`, `serve_tenants` from
  `xippios.core.mcp`, and `assert_write_tools` and `keep_reserved_tenants` from
  `xippios.core.testing`. No tool of a server that `bind_tasks(tasks, TenantLock(TENANTS,
  "acme"))` binds takes `org`, the registry's `param`, so a call that names it is refused,
  and `serve_tenants(server, build, TENANTS, check=...)` is an entry point's `--org`, which
  checks the tenant at startup. `await assert_write_tools(...)` checks a
  write server against its write tasks, `confirm: bool = False` last, and
  `keep_reserved_tenants(TENANTS)` in `tests/conftest.py` leaves the tests the reserved
  tenant alone.
  (ADR-0014, ADR-0024, ADR-0025, §7, §8, https://github.com/xippios/sdk-core/issues/166)
  - Hand-apply: `src/xippios/cashctrl/_org_lock.py` (sdk-cashctrl) — deleted — core's
    `TenantLock`, `bind_tasks` and `tenant_instructions` are this copy: `OrgLock("org",
    name)` is `TenantLock(TENANTS, name, noun="organisation")`, whose sentence reads as
    `lock_sentence`'s did, and `instructions(base, lock)` is `tenant_instructions(base,
    lock)`, the same text.
    `src/xippios/cashctrl/_cli.py` (sdk-cashctrl) — deleted, its subdomain check (line 55)
    moved to `_client.py` — core's `serve_tenants` is this copy, `--org` with `ORG_HELP`'s
    text and `TENANTS.require` before the build.
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `check_org(org)`, which calls
    `TENANTS.field(org, "SUBDOMAIN")`, added after `TENANTS` (line 105) and to `__all__`
    (line 49) — `serve_tenants` runs the source's own startup check, so a missing or
    malformed subdomain still stops a bound server at startup, with the same message.
    `src/xippios/cashctrl/mcp.py` (sdk-cashctrl) — the imports of `serve` from `_cli` and of
    `OrgLock`, `bind_tasks` and `instructions` from `_org_lock` (lines 13 and 15) → `from
    xippios.core import TenantLock, bind_tasks, tenant_instructions`, with `serve_tenants`
    beside `build_server` (line 10) and `TENANTS` and `check_org` beside `SOURCE` (line 14),
    then `OrgLock` (line 27) → `TenantLock`, `instructions(INSTRUCTIONS, lock)` (line 33) →
    `tenant_instructions(INSTRUCTIONS, lock)` with no `bound=`, `serve(server, build)` and
    its comment (lines 43 to 46) → `serve_tenants(server, build, TENANTS,
    noun="organisation", check=check_org)`, and the docstring's `_cli`, `_org_lock` (line 6)
    → core's `serve_tenants` — the server, its options and its instructions are what they
    were, `INSTRUCTIONS` and then the lock's sentence when bound.
    `src/xippios/cashctrl/mcp_write.py` (sdk-cashctrl) — as in `mcp.py`: the imports (lines
    11 and 14 to 16), `OrgLock` (line 27), `instructions` (line 34), `serve` (line 45) and
    the docstring's `_cli` (line 5) — as there.
    `tests/conftest.py` (sdk-cashctrl) — `DEMO_PAIR` and `_strip_productive_organisations`
    with its call (lines 16 and 21 to 33) → `keep_reserved_tenants(TENANTS)` from
    `xippios.core.testing`, then `os.environ.pop("CASHCTRL_API_KEY", None)`, and the
    fixtures as they stand — core strips by the registry's scheme, sdk-google-mail's
    behaviour, so it removes `CASHCTRL_ORGS` and every organisation's pair but demo's and
    keeps a variable the scheme names for no organisation, where the copy removed every
    `CASHCTRL_*` variable but the demo pair, and the second line keeps the scaffold's key,
    which nothing reads, out of the tests as before.
    `tests/test_tasks_write.py` (sdk-cashctrl) — the copy of `assert_write_tools`,
    `_confirm_problem`, `_tool_names` and `_serves` with its comment (lines 161 to 254)
    deleted, `assert_write_tools` imported from `xippios.core.testing` (line 48), the
    helper's own tests from `create_thing` to
    `test_assert_write_tools_names_tools_with_the_underscored_source` (lines 281 to 423)
    deleted, and the imports they leave unused deleted too, `APIRouter` (line 42),
    `MCPServer` (line 43), `router_from_tasks` (line 45), `build_server` (line 46) and
    `is_write_server` and `register_tasks` (line 47), with
    `test_the_write_server_serves_write_tasks_only` (line 257) as it stands — core's
    `tests/testing/test_adapters.py` holds the helper's tests.
    `tests/test_org_lock.py` (sdk-cashctrl) — the tests of the lock and the command deleted
    (lines 90, 98, 119, 138, 158, 165, 175, 190, 211, 232, 246, 256, 270, 280, 349, 361 and
    404), with `TOOL`, `REQUEST_LOGGERS`, `EchoServers` and `locked` (lines 33, 35, 42 to 68
    and 83 to 84) and the imports they leave unused, the imports of `serve` and of
    `_org_lock` (lines 27 and 29) → `from xippios.core import TenantLock, bind_tasks`,
    `LOCK` (line 39) → `TenantLock(TENANTS, DEMO, noun="organisation")`, `TENANTS` imported
    from `_client`, `bind(task, LOCK)`
    (lines 107 and 150) → `bind_tasks([task], LOCK)[0]`, the organisation list's test (line
    197) on `mcp.build()` and `mcp.build(LOCK)` for `EchoServers`, and
    `test_a_missing_or_malformed_subdomain_fails_at_startup` (line 330) through `mcp.run()`
    with `sys.argv` set as the entry points' test of an undeclared organisation (line 288)
    sets it — core's `tests/test_tenant_lock.py` and `tests/mcp/test_cli.py` hold the tests
    of the lock and the command, and what stays tests the package's own wiring, its tasks
    bound, `--org` with `check_org` on both entry points, its instructions and its write
    server on loopback.
    `CLAUDE.md` (sdk-cashctrl) — Organisations' `_org_lock.py` (lines 31 to 36) and the
    `--org` bullet's `_cli.py`, `_org_lock.py` and `bind_tasks` (lines 55 to 58) → core's
    `TenantLock`, `bind_tasks` and `serve_tenants`, the Demo only paragraph's strip (line
    83) → core's `keep_reserved_tenants`, which removes `CASHCTRL_ORGS` and every
    organisation's pair but demo's, with the scaffold's `CASHCTRL_API_KEY` beside it, the
    Layout's `_org_lock.py` and `_cli.py` lines (136 to 137) dropped, and
    `assert_write_tools` (lines 171 and 211) → core's — the kit is core's again.
    `src/xippios/google/mail/_account_lock.py` (sdk-google-mail) — deleted — core's
    `TenantLock`, `bind_tasks` and `tenant_instructions` are this copy:
    `AccountLock("account", name)` is `TenantLock(TENANTS, name)`, its noun the
    parameter's, and `instructions(base, lock, bound=...)` is `tenant_instructions(base,
    lock, bound=...)`, the form core takes where the two copies differ.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — deleted, its refresh token check
    (lines 96 to 102) moved to `_client.py`, and `REMOTE_REFUSAL` goes with it, so the read
    server's refusal of `--http` on a remote `--host` is core's `main`'s,
    `xippios-google-mail is a read server held to loopback and carries no authentication`,
    followed by the loopback hosts and `--allow-remote`, and comes after the account check,
    where the copy refused the host first with its own text — core's `serve_tenants` is this
    copy, `--account` with `ACCOUNT_HELP`'s text and `TENANTS.require` before the build, and
    `main` judges loopback on the server `apply_options` returns.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — `check_account(account)`, which
    raises `_cli.py`'s `ConfigError` (lines 96 to 102) when `TENANTS.var(account,
    "REFRESH_TOKEN")` is unset or blank, with `CONSENT_COMMAND` imported from `_auth` (line
    48), added after `TENANTS` and to `__all__` (line 58) — `serve_tenants` runs the
    source's own startup check, so an unset refresh token still stops a bound server at
    startup, its message naming the variable and the consent command and no source.
    `src/xippios/google/mail/mcp.py` (sdk-google-mail) — the imports of `AccountLock`,
    `bind_tasks` and `instructions` from `_account_lock` and of `serve` from `_cli` (lines
    15 to 16) → `from xippios.core import TenantLock, bind_tasks, tenant_instructions`, with
    `serve_tenants` beside `build_server` (line 12) and `TENANTS` and `check_account` beside
    `SOURCE` (line 17), then `AccountLock` (line 35) → `TenantLock`,
    `instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS)` (line 41) →
    `tenant_instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS)`, `serve(server,
    build)` and its comment (lines 51 to 54) → `serve_tenants(server, build, TENANTS,
    check=check_account)`, and the docstring's `_cli`, `_account_lock`
    (line 6) → core's `serve_tenants` — the server, its options and its instructions are
    what they were.
    `src/xippios/google/mail/mcp_write.py` (sdk-google-mail) — as in `mcp.py`: the imports
    (lines 16 and 19 to 21), `AccountLock` (line 39), `instructions` (line 45), `serve` and
    its comment (lines 56 to 58) and the docstring's `_cli`, `_account_lock` and the read
    server's own loopback check (lines 9 to 11) — as there.
    `tests/conftest.py` (sdk-google-mail) — `DEMO_TOKEN`, `_ACCOUNT_TOKEN` and
    `_strip_productive_accounts` with its call (lines 26 to 43), `import re` (line 6) and
    the comment's first two lines (lines 1 to 2) → `keep_reserved_tenants(TENANTS)` from
    `xippios.core.testing`, with the fixtures and the write audit as they stand — core's
    strip is this copy's, so it removes `GOOGLE_ACCOUNTS` and every account's refresh token
    but demo's and keeps the client pair.
    `tests/test_tasks_write.py` (sdk-google-mail) — the copy of `assert_write_tools`,
    `_confirm_problem`, `_tool_names` and `_serves` with its comment (lines 165 to 261)
    deleted, `assert_write_tools` imported from `xippios.core.testing` (line 43), the
    helper's own tests from `create_thing` to
    `test_assert_write_tools_names_tools_with_the_underscored_source` (lines 307 to 447)
    deleted, `_tool_names(read_server)` in
    `test_the_read_server_is_no_write_server_and_keeps_its_tools` (line 286) → `{tool.name
    for tool in await read_server.list_tools()}`, and the imports left unused deleted,
    `APIRouter` (line 37), `MCPServer` (line 38), `router_from_tasks` (line 40),
    `build_server` (line 41) and `register_tasks` (line 42), with
    `test_the_write_server_serves_the_write_tasks_only` (line 264) as it stands — core's
    `tests/testing/test_adapters.py` holds the helper's tests.
    `tests/test_account_lock.py` (sdk-google-mail) — the tests of the lock and the command
    deleted (lines 98, 108, 129, 148, 168, 175, 185, 195, 216, 236, 252, 262, 295, 305, 350,
    362, 369 and 490), with `TOOL`, `REQUEST_LOGGERS`, `EchoServers` and `locked` (lines 41,
    43, 50 to 76 and 91 to 92) and the imports they leave unused,
    `test_the_loopback_rule_comes_before_the_account` (line 436) deleted too, since core's
    `main` judges loopback on the server `apply_options` returns, after the account, the
    imports of `_account_lock` and `_cli` (lines 29 to 36) → `from xippios.core import
    TenantLock, bind_tasks`, `REMOTE_REFUSAL not in err` (line 465) dropped, `LOCK` (line
    47) → `TenantLock(TENANTS, DEMO)`, `TENANTS` imported from `_client`, `bind(task, LOCK)`
    (lines 117 and 160) →
    `bind_tasks([task], LOCK)[0]`, `test_the_account_list_shows_the_bound_account_only`
    (line 202) on `mcp.build()` and `mcp.build(LOCK)` for `EchoServers`, and
    `test_a_listed_account_without_its_refresh_token_fails_at_startup` (line 276) through
    `mcp.run()` with `sys.argv` set as the entry points' test of an undeclared account (line
    313) sets it — core's `tests/test_tenant_lock.py` and `tests/mcp/test_cli.py` hold the
    tests of the lock and the command, and what stays tests the package's own wiring, as in
    sdk-cashctrl.
    `CLAUDE.md` (sdk-google-mail) — the Layout's `_account_lock.py` and `_cli.py` lines (35
    to 39) dropped, `conftest.py`'s strip (line 87) → core's `keep_reserved_tenants`,
    `test_tasks_write.py`'s `assert_write_tools, copied from sdk-cashctrl` (lines 111 to
    112) → core's, and `(_account_lock, through _cli.serve)` (line 346) → core's
    `TenantLock` through `serve_tenants` — the kit is core's again.
- `decode_csv` reads an open text stream beside a path and a response, such as a gzip or
  ZIP member that the source opens with the stdlib: row by row, a leading byte order mark
  stripped, and left open for the caller that opened it. Its errors name the stream's file
  name without the directories, `stream` for one without a name, and a binary stream is
  refused with `TypeError`, naming `io.TextIOWrapper`.
  (ADR-0019, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/89)
  - Hand-apply: `src/xippios/eurostat/parse/sdmx_csv.py` (sdk-eurostat) — `_gzip_records`
    (lines 102 to 105) yields from `decode_csv(text, source=SOURCE)` where it built its own
    `csv.DictReader(text)`, inside the same `_reading` and `_text(path, packed=True)`,
    which stay for `_header` and the gzip errors. The module docstring's sentence that
    the gzip file is read with the stdlib's `csv.DictReader` "since `decode_csv` takes a
    path or a response, not an open stream" (lines 23 to 30) says that both files' rows
    are read through `decode_csv`, a gzip file's as a stream — core reads the stream, and
    `tests/test_parse.py`'s `test_parse_sdmx_csv_refuses_text_that_is_not_utf8` (line
    300) and `test_parse_sdmx_csv_refuses_csv_the_csv_module_cannot_read` (line 317) pass
    unchanged, since core names a `gzip.open` stream by its file's name.
    `src/xippios/faostat/parse/bulk_csv.py` (sdk-faostat) — `parse_bulk_csv` (lines 124
    to 150) reads the table's rows through `decode_csv(io.TextIOWrapper(raw,
    encoding="utf-8-sig", newline=""), source=SOURCE)`, and its header for the check of a
    column named twice apart, from a first `archive.open(member)`, as sdk-eurostat's
    `_header` reads its own, since `decode_csv` gives rows as mappings, in which a column
    named twice is one key. `_reading` keeps its ZIP branch, and the module docstring's
    "`decode_csv` takes a path or a response, not an open stream" (lines 26 to 34) goes —
    core reads the stream. The errors of the rows' reading then name the member alone,
    not `<member> in <zip>`: `tests/test_parse.py`'s
    `test_parse_bulk_csv_refuses_text_that_is_not_utf8` (line 278) expects
    `f"faostat: {table_name(RL)} is not UTF-8 text: invalid start byte"`, and
    `test_parse_bulk_csv_refuses_csv_the_csv_module_cannot_read` (line 290)
    `f"faostat: {table_name(RL)} is not CSV the csv module reads: ..."`.
- `AsyncClient.post_json` and `delete_json` send a write through `request`, with
  `classify`, the hooks and the retry rule for a write, and decode its JSON answer as
  `get_json` decodes a read's, `None` for an answer with no body, a 204 say. A write
  wrapper no longer calls `request` and decodes the answer itself. `get_json` still
  refuses an empty body.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/178)
  - Hand-apply: `src/xippios/google/mail/api/drafts_create.py` (sdk-google-mail) —
    `client.request("POST", "drafts", json=...)` and `decode_json(response, ...)` (lines 48
    and 49) → `await client.post_json("drafts", json=...)`, parsed as before, and the import
    of `decode_json` (line 20) goes — core's write call replaces the request and the decode,
    its `ValidationError` naming the path the wrapper passes.
    `src/xippios/google/mail/api/messages_send.py` (sdk-google-mail) — lines 46 and 47 →
    `client.post_json("messages/send", json=body)`, and the import of `decode_json` (line
    19) goes — the same.
    `src/xippios/google/mail/api/messages_modify.py` (sdk-google-mail) — lines 51 and 52 →
    `client.post_json(f"messages/{quote(id, safe='')}/modify", json=body)`, and the import
    of `decode_json` (line 16) goes — the same.
    `src/xippios/google/mail/api/messages_trash.py` (sdk-google-mail) — lines 35 and 36 →
    `client.post_json(f"messages/{quote(id, safe='')}/trash")`, and the import of
    `decode_json` (line 13) goes — the same.
    `src/xippios/google/mail/api/drafts_delete.py` (sdk-google-mail) —
    `client.request("DELETE", ...)` (line 32) → `client.delete_json(...)`, and the
    docstring's "a success's body, empty, is not read" (line 24) → `delete_json` returns
    `None` for it — core reads the 204 that `delete_draft/ok.json` records as `None`.
    `src/xippios/cashctrl/api/_form.py` (sdk-cashctrl) — `post_form`'s `request` and its
    own decode (lines 242 to 252) → `return await client_for(org).post_json(path,
    data=fields, headers={"Content-Type": FORM_CONTENT_TYPE})`, and `BODY_LIMIT` and
    `ValidationError` leave the import (line 39) — the same, its `ValidationError` now
    carrying the decoder's reason after "is not JSON".
    `src/xippios/faostat/api/auth_login.py` (sdk-faostat) — `client.request("POST",
    LOGIN_PATH, data=..., auth=None)` and `decode_json(response, source=SOURCE,
    path=LOGIN_PATH)` (lines 47 to 50) → `client.post_json(LOGIN_PATH, data=...,
    auth=None)`, and the import of `decode_json` (line 21) goes — the same.
- `record` and `record_sync` read at most `max_read_bytes` of a response body, 32 MiB by
  default (`xippios.core.testing.record.MAX_READ_BYTES`): past it the reading stops and the
  recording raises, naming the method, the path and the bound, and writes nothing.
  `None` reads the body whole. (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/62)
- `xippios.core.errors.request_description(response)`, exported from `xippios.core`,
  gives the method and path that core's error messages name, `GET /v1/series`, so a
  source's `classify` words the errors it maps with it instead of a copy of its own.
  (ADR-0005, §5, https://github.com/xippios/sdk-core/issues/62)
  - Hand-apply: `src/xippios/eurostat/_client.py` (sdk-eurostat) — `_where` (lines 102 to
    104) and its five uses → `request_description` — core's description.
    `src/xippios/x/_client.py` (sdk-x) — `_where` (lines 96 to 98) and its use at line
    146 → `request_description` — core's description.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — the inline `where` of line
    247 → `request_description(response)` — core's description.
    `src/xippios/google/mail/_auth.py` (sdk-google-mail) — the inline `where` of line 297
    → `request_description(response)` — core's description.
    `src/xippios/faostat/_client.py` (sdk-faostat) — the inline
    `{request.method} {request.url.path}` of lines 166, 376 and 383 →
    `request_description(response)` — core's description.
    `src/xippios/usda/esmis/_client.py` (sdk-usda-esmis) — the inline
    `{request.method} {path}` of line 124 → `request_description(response)`, line 115
    keeping its raw path, which shows the encoded slash — core's description.
- `Scrub` takes `response_secrets`, a function of the response that returns values that
  must never be written, such as the tokens of a login or a refresh answer, which the
  credential rule does not name (`AccessToken` is one word). Each value is scrubbed and
  verified as the named ones are, so such an exchange records through `record_sync`.
  (ADR-0024, §10, https://github.com/xippios/sdk-core/issues/164)
  - Hand-apply: `scripts/record_fixture.py` (sdk-google-mail) —
    `Scrub(secrets=[*secret_values(), *answer_tokens(response)])` at lines 1058 to 1061
    and 1089 to 1091 → `Scrub(secrets=secret_values(), response_secrets=answer_tokens)`,
    `rewrite` keeping its list for the encoded forms — core reads and verifies the
    answer's tokens.
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
- `Tenants` and `list_task` are back in core, exported from `xippios.core` out of the module
  `xippios.core.tenants`: a multi-tenant source's tenants declared in the environment, one
  client each, which closes the client that a changed variable replaces, and the tool that
  names them. `Tenants(source, var_prefix=..., param=...)` takes the variables' prefix
  apart from the source slug, so its errors name the source, and `list_task(...,
  source=...)` names the `meta.source` of a registry that several sources share, the
  registry's slug by default.
  (ADR-0014, ADR-0024, ADR-0025, https://github.com/xippios/sdk-core/issues/166)
  - Hand-apply: `src/xippios/cashctrl/_tenants.py` (sdk-cashctrl) — deleted — core's module
    is this copy, the close of a replaced client included, and its default prefix is the
    slug's, `CASHCTRL`.
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `from xippios.cashctrl._tenants
    import Tenants` (line 45) → `from xippios.core import Tenants`, and the docstring's
    sentence on `_tenants.py` (lines 9 to 11) names core's `Tenants`, the declaration
    (line 97) as it stands but for `param="org"`, which core's `Tenants` requires — core's
    registry reads the same variables.
    `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — `from xippios.cashctrl._tenants import
    list_task` (line 79) → `from xippios.core import list_task`, and the docstring's
    `_tenants.list_task` (line 9) → core's `list_task`, the call (line 2273) as it stands
    — as above.
    `src/xippios/cashctrl/_org_lock.py` (sdk-cashctrl) — the import of `_LISTS_TENANTS`
    from `_tenants` (line 36) → `_LISTS_TENANTS = "__xippios_lists_tenants__"` in the
    module — core's `list_task` sets that mark, so the bound server still lists the bound
    organisation alone until core's lock wrapper replaces the file.
    `tests/test_tenants.py` (sdk-cashctrl) — deleted, with its import of the copy (line 30)
    — core's `tests/test_tenants.py` holds its tests, the close of row 24 b among them.
    `tests/test_registry.py` (sdk-cashctrl) — the docstring's lines 3 to 6, which name
    `_tenants.py` and `tests/test_tenants.py` → core's `Tenants`, tested in core — as above.
    `tests/test_tasks.py` (sdk-cashctrl) — the docstring of `TENANT_LIST` (line 51) → core's
    `list_task` — as above.
    `CLAUDE.md` (sdk-cashctrl) — Organisations, `_tenants.py` and `_tenants.list_task` (lines
    28, 31 to 34 and 52) → core's `Tenants` and `list_task`, and the Layout's `_tenants.py`
    and `test_tenants.py` lines (135, 173) dropped — the registry is core's again.
    `src/xippios/google/mail/_tenants.py` (sdk-google-mail) — deleted — core's module is
    this copy, `list_task`'s `source=` included, where the two copies differ.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — `from
    xippios.google.mail._tenants import Tenants` (line 55) → `from xippios.core import
    Tenants`, the declaration's first argument, `"google"` (line 105) → `SOURCE,
    var_prefix="GOOGLE"` with `param="account"`, which core's `Tenants` requires, and the
    docstring's lines 10 to 11 and 22 to 23 → core's
    `Tenants`, whose errors name `google-mail` — the variables keep the shared prefix, and
    an unknown account's `InvalidRequestError` and the registry's `ConfigError` name the
    source, `google` before, in an HTTP problem's `source` too (ADR-0025, amendment
    2026-11-18, (b), https://github.com/xippios/sdk-core/issues/279).
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — `from
    xippios.google.mail._tenants import list_task` (line 34) → `from xippios.core import
    list_task`, `source=SOURCE` dropped from the call (line 112), and the docstring's
    `_tenants.list_task` (line 8) → core's `list_task` — the registry names the source now.
    `src/xippios/google/mail/_account_lock.py` (sdk-google-mail) — the import of
    `_LISTS_TENANTS` from `_tenants` (line 41) → `_LISTS_TENANTS =
    "__xippios_lists_tenants__"` in the module — as in sdk-cashctrl's `_org_lock.py`.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — the import of `_is_set` from
    `_tenants` (line 42) → `os.environ.get(variable, "").strip()` in its one use (line 97)
    — core keeps `_is_set` private, until core's serve command replaces the file.
    `tests/test_tasks.py` (sdk-google-mail) — the docstring of `TENANT_LIST` (line 49) →
    core's `list_task`, and `test_list_accounts_lists_the_declared_names_only` (line 95)
    asserts `TENANTS.source == SOURCE` and `TENANTS.var("work", "REFRESH_TOKEN") ==
    "GOOGLE_WORK_REFRESH_TOKEN"` — the registry names the source, its variables the prefix.
    `CLAUDE.md` (sdk-google-mail) — the Layout's `_tenants.py` line (34) dropped — the
    registry is core's.
- `Gateway(source, data_path=...)` maps FAS's empty `text/plain` 404 on the source's data
  paths to `xippios.core.data_gov.NoDataForYear`, a `NotFoundError` with the request's
  `path` whose text says that the year it names holds no data. It replaces the
  `NoDataForYear` and the `classify` branch that sdk-usda-psd and sdk-usda-esr each carried.
  (ADR-0009, ADR-0023, §7, https://github.com/xippios/sdk-core/issues/106)
  - Hand-apply: `src/xippios/usda/psd/_client.py` (sdk-usda-psd) — `Gateway(SOURCE,
    data_path=DATA_PATH)`, the empty-404 branch of `classify` keeps its plain
    `NotFoundError` and loses the `NoDataForYear` return (lines 89 to 94), and the
    docstrings name `xippios.core.data_gov.NoDataForYear` (lines 15 and 76) — core maps it.
    `src/xippios/usda/psd/errors.py` (sdk-usda-psd) — deleted, `NoDataForYear` being all
    it holds — core's class replaces it.
    `src/xippios/usda/psd/tasks.py` (sdk-usda-psd) — `from xippios.core.data_gov import
    NoDataForYear` (line 55), `_absent` passes `source=exc.source` (line 152), and the
    docstring names core's class (line 391) — core's class takes its source as a keyword.
    `tests/test_client.py` (sdk-usda-psd) — the import of line 39 from
    `xippios.core.data_gov` — the module it named goes.
    `tests/test_tasks.py` (sdk-usda-psd) — the import of line 18, the same — the same.
    `tests/test_slices.py` (sdk-usda-psd) — the import of line 40, the same — the same.
    `CLAUDE.md` (sdk-usda-psd) — the Layout drops `errors.py` (line 41) and the fixtures'
    facts name core's `NoDataForYear` (line 206) — the same.
    `src/xippios/usda/esr/_client.py` (sdk-usda-esr) — `Gateway(SOURCE,
    data_path=DATA_PATH)`, the empty-404 branch of `classify` keeps its plain
    `NotFoundError` and loses the `NoDataForYear` return (lines 100 to 105), and the
    docstrings name core's class (lines 15 and 79) — core maps it.
    `src/xippios/usda/esr/errors.py` (sdk-usda-esr) — deleted, `NoDataForYear` being all
    it holds — core's class replaces it.
    `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — `from xippios.core.data_gov import
    NoDataForYear` (line 97) and `_absent` passes `source=exc.source` (line 237) — core's
    class takes its source as a keyword.
    `src/xippios/usda/esr/api/get_country_data.py` (sdk-usda-esr) — the docstring names
    core's class (line 15) — the module it named goes.
    `src/xippios/usda/esr/api/get_all_countries_data.py` (sdk-usda-esr) — the docstring
    names core's class (line 18) — the same.
    `src/xippios/usda/esr/params.py` (sdk-usda-esr) — the docstring names core's class
    (line 50) — the same.
    `tests/test_client.py` (sdk-usda-esr) — the import of line 48 from
    `xippios.core.data_gov` — the same.
    `tests/test_tasks.py` (sdk-usda-esr) — the import of line 26, the same — the same.
    `tests/test_slices.py` (sdk-usda-esr) — the import of line 44, the same — the same.
    `CLAUDE.md` (sdk-usda-esr) — the fixtures' facts name core's `NoDataForYear` (line
    81) and the Layout drops `errors.py` (line 126) — the same.
- `register_data_name(name)` of `xippios.core.redaction` declares a parameter whose name
  holds the whole word `token` data, a paging cursor such as X's `next_token`, so that
  `meta.request`, a recorded fixture and replay keep its value. Every other name with a
  whole-word `token` stays a credential, and `token`, `access_token`, `refresh_token`,
  `id_token` and a name with another credential word are refused with `ValueError`.
  (ADR-0019, §4, §10, https://github.com/xippios/sdk-core/issues/184)
  - Hand-apply: `src/xippios/x/_client.py` (sdk-x) — `register_data_name("next_token")`
    and `register_data_name("pagination_token")` at import — X's cursors are data.
    `src/xippios/x/tasks.py` (sdk-x) — the module docstring (lines 28 and 29) and the
    `Args:` of the five paged tasks (lines 273, 327, 386, 432 and 475) say that
    `meta.request` keeps the token as sent, no longer `REDACTED` — the same.
    `tests/test_tasks.py` (sdk-x) — the token as sent, for `REDACTED`, in the docstring
    of line 203 and the asserts of lines 218, 223, 266 and 323, and the comparisons of
    lines 265 and 322 with the `next_token=REDACTED` that the page-2 fixtures recorded
    leave `next_token` out until a PR records them again — the same.
    `tests/test_api.py` (sdk-x) — the token as sent, for `REDACTED`, at lines 283, 357, 384
    and 528, and the comparisons of lines 282 and 356 with the page-2 fixtures leave
    `next_token` out — the same.
    `tests/test_probe_accounts.py` (sdk-x) — the cursors as sent, for `REDACTED`, at line
    232 — the same.
    `CLAUDE.md` (sdk-x) — the fixtures' paragraph (lines 335 to 340) and the task layer's
    `meta` (line 383) say that the cursors are data, and that the two page-2 fixtures
    keep `next_token=REDACTED` until recorded again — the same.
- `FixtureResponse.sample` marks a download's replay fixture whose body is the sample its
  parser tests read, with the whole file's `original_bytes` and `sha256`, so the download
  replays that file and `truncated` keeps meaning the recorder's cut. `FixtureResponse`,
  `write_fixture` and `load_fixture` refuse a fixture with both marks, with either and without
  those two fields, or with them on a whole body. (ADR-0020, §10,
  https://github.com/xippios/sdk-core/issues/125)
  - Hand-apply: `scripts/cut_sample.py` (sdk-usda-wasde) — the replay fixture's `truncated` →
    `sample`, and the download fixtures written again — a sample is no first part of
    upstream's answer.
- `xippios.core.testing` exports `write_fixture(fixture, path)`, which writes a `Fixture` laid
  out as `record` writes it, and `fixture_text(fixture)`, which gives that text, so a recorder
  step that rewrites a fixture writes it as core does. `write_fixture` took a response before
  and was no export: `write_fixture(fixture_from_response(response), path)` does what it did.
  (ADR-0024, §10, https://github.com/xippios/sdk-core/issues/125)
  - Hand-apply: `scripts/record_fixture.py` (sdk-cashctrl, sdk-google-mail, sdk-x) — `to_json`
    and `_CUT_MARKS` → `fixture_text`, the file's write → `write_fixture` — core's writer.
    `scripts/cut_sample.py` (sdk-usda-wasde) — the JSON dump and its write →
    `write_fixture` — core's writer.
- `record`, `record_sync` and `fixture_from_response` take `array_key=`, with which
  `max_bytes=` cuts the array of a top-level key of a JSON object, `{"data": [...]}`, the rest
  of the object kept as upstream wrote it, and `keep="last"`, which keeps an array's last whole
  elements, for a list ordered oldest first. A JSON object without `array_key` is still
  refused. (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/127)
- `Answer` is generic over its payload: `get_answer(path, parse=T, endpoint=...)` parses
  the payload into `T` and returns an `Answer[T]`, and a wrapper returns
  `Answer(value, answer.retrieved_at)` for a value it derives from the payload. It
  replaces the pairs of a value and its `retrieved_at` that sources kept of their own.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/123)
  - Hand-apply: `src/xippios/comtrade/api/reference.py` (sdk-comtrade) — `ReferenceFile[T]`
    goes, `reference_rows` returns `Answer[list[dict[str, Any]]]` from
    `get_answer(..., parse=_ReferenceFile, endpoint=...)`, and `reference` returns
    `Answer[list[M]]`, reading `.payload` and `.retrieved_at` where it unpacked
    `rows, retrieved_at = await reference_rows(name)` — core's typed answer replaces the
    pair (ADR-0023, decision 4).
    `src/xippios/comtrade/api/__init__.py` (sdk-comtrade) — the import and `__all__` drop
    `ReferenceFile` — the class goes.
    `src/xippios/comtrade/tasks.py` (sdk-comtrade) — `list_commodities_async` reads
    `fetched.payload` for `fetched.rows` — `Answer` names the rows `payload`.
    `scripts/refresh_reference.py` (sdk-comtrade) — `_rows` reads `answer.payload` for
    `answer.rows`, and `_table` reads `.payload` and `.retrieved_at` where it unpacked
    `rows, fetched = sync(api.reference_rows)(file)` — `Answer` is not a tuple and names
    the rows `payload`.
    `tests/test_tasks.py` (sdk-comtrade) — `.payload` for `.rows` — `Answer` names the
    rows `payload`.
    `tests/test_live.py` (sdk-comtrade) — `.payload` for `.rows`, four times — `Answer`
    names the rows `payload`.
    `src/xippios/usda/nass/api/get_param_values.py` (sdk-usda-nass) — `ParamValues` goes,
    and `get_param_values` returns `Answer[list[str]]` — core's typed answer replaces the
    pair (ADR-0023, decision 4).
    `src/xippios/usda/nass/api/__init__.py` (sdk-usda-nass) — the import and `__all__`
    drop `ParamValues` — the class goes.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — `.payload` and `.retrieved_at`
    where it unpacked `values, retrieved_at = await api.get_param_values(param)` —
    `Answer` is not a tuple.
    `scripts/refresh_reference.py` (sdk-usda-nass) — `.payload` and `.retrieved_at` where
    it unpacked `values, retrieved_at = fetch(param)` — `Answer` is not a tuple.
    `tests/test_tasks.py` (sdk-usda-nass) — `.payload` and `.retrieved_at` where it
    unpacked `values, retrieved_at = await api.get_param_values("sector_desc")` —
    `Answer` is not a tuple.
- `build_server(..., loopback_only=True)` holds a read server to loopback as a write
  server is held: `main` serves it over `--http` on a loopback `--host` only unless
  `--allow-remote` is passed. `is_loopback_only(server)` answers for both kinds and
  `LOOPBACK_HOSTS` lists the hosts, both exported from `xippios.core.mcp`, and
  `register_tasks` takes `loopback_only` too. The usage line and the prefix of `main`'s
  errors name the entry point that runs instead of `server.name`, and the refusal and the
  help of `--allow-remote` name the server's kind.
  (ADR-0025, ADR-0026, §8, https://github.com/xippios/sdk-core/issues/167)
  - Hand-apply: `src/xippios/google/mail/mcp.py` (sdk-google-mail) — `build_server(...,
    loopback_only=True)` for the read server — core holds it to loopback now.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — the loopback check in
    `apply_options` and the copy of `_LOOPBACK_HOSTS` deleted — core's `main` refuses the
    host itself.
    `tests/test_account_lock.py` (sdk-google-mail) — the `xippios-google-mail: error:`
    assertions name the entry point, with `sys.argv` set as the `entry_point` fixture of
    core's `tests/mcp/test_cli.py` sets it, and the remote refusal of the read server
    asserts core's message — `main`'s errors name the entry point that runs, `pytest` in
    a test run, and the source's own check is gone.
    `tests/test_org_lock.py` (sdk-cashctrl) — the `xippios-cashctrl: error:` assertions
    name the entry point, with `sys.argv` set as in sdk-google-mail — as there.
    `src/xippios/mcp/app.py` (xippios-mcp) — the copy of `_LOOPBACK_HOSTS` →
    `LOOPBACK_HOSTS`, and `is_write_server` → `is_loopback_only` in the loopback check — an
    endpoint with `auth: none` holds a loopback-only read server as it holds a write server.
    `tests/test_app.py` (xippios-mcp) — `test_the_loopback_hosts_are_cores`, which reads
    `core_cli._LOOPBACK_HOSTS`, deleted with the copy, and the loopback cases parametrized
    on `LOOPBACK_HOSTS` — core exports the list.
- `xippios.core.mcp` exports `register_tasks`, `is_write_server` and
  `quiet_request_logging`, and `tool_functions(tasks)`, the functions of `tasks.__all__`
  that become tools, with `BULK_TASKS` read from the module it is given. `tool_functions`
  refuses an entry of `__all__` whose function carries another `__name__`, since a tool's
  name, an `MCP_CAPS` key and a `BULK_TASKS` entry read that name. A source's `mcp.py`
  passes `tool_functions(tasks)` to `build_server`, and a host imports nothing from
  `xippios.core.mcp.server` or `xippios.core._tasks`.
  (ADR-0023, ADR-0026, §8, https://github.com/xippios/sdk-core/issues/170)
  - Hand-apply: `src/xippios/mcp/packages.py` (xippios-mcp) — `is_bulk_task` from
    `xippios.core._tasks` → the names of `tool_functions(tasks)` — the private helper
    leaves the host's imports.
    `src/xippios/mcp/servers.py`, `src/xippios/mcp/app.py` and `src/xippios/mcp/cli.py`
    (xippios-mcp) — the imports from `xippios.core.mcp.server` → `xippios.core.mcp` — core
    exports what the host imports.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — `is_write_server` from
    `xippios.core.mcp.server` → `xippios.core.mcp` — as above.

### Changed

- Conventions §12 has a source's adoption of a core minor take a minor, since it moves the
  core bound, and a release's section say internal labels in plain words, and §15, the
  definition of done and the review checklist say what binds the host xippios-mcp, its
  adoption PR without `copier update` included. §7 keeps every credential variable unread by
  whoever works in a repository, a `_TOKEN` among them, §10 has a live run take
  `--tb=short --assert=plain`, and the header has a convention that seems wrong followed
  and said in the pull request. The two review documents say what a pull request's count of
  live calls covers and why, and the checklist raises the conventions version once per core
  release.
  (ADR-0005, ADR-0009, ADR-0018, ADR-0026, §7, §10, §12, §15,
  https://github.com/xippios/sdk-core/issues/185,
  https://github.com/xippios/sdk-core/issues/172,
  https://github.com/xippios/sdk-core/issues/211,
  https://github.com/xippios/sdk-core/issues/219,
  https://github.com/xippios/sdk-core/issues/208,
  https://github.com/xippios/sdk-core/issues/270)
- The secret scan of `.pre-commit-config.yaml` skips the line on which the fixture recorder
  writes a cut or sampled body's sha256, so a fixture that holds one needs no audited entry
  in `.secrets.baseline`. Every other line is still scanned, a body stored base64 included,
  which keeps its audited entry. Its comment says that `.copier-answers.yml` can name a
  key's variable, which a keyless source's does not.
  (ADR-0019, https://github.com/xippios/sdk-template/issues/42,
  https://github.com/xippios/sdk-core/issues/210)
- Conventions §8 gives a tool whose result is one upstream document or table that an agent
  reads whole, a report, a statement, a table's page or a matrix, a cap of its own with the
  rows and bytes it needs and a note that says how to read a part of it, as a reference
  tool has. (ADR-0016, §8, https://github.com/xippios/sdk-core/issues/91)
- Conventions §5 names the third point at which `InvalidRequestError` is raised, from a
  successful answer the task cannot serve as asked, and what a refusal of a code names in
  its place, the closest codes or its parent and the codes listed under its name. A
  refusal that lists the codes an upstream answer holds lists at most 20 of each list, then
  how many more, and §5 says where the packaged-list check applies: a code whose answer was
  never recorded, a list upstream refuses itself, a filter key with an operator, another
  coding system, a code upstream's live answer lacks, and the case upstream compares.
  (ADR-0007, ADR-0022, §5, https://github.com/xippios/sdk-core/issues/69,
  https://github.com/xippios/sdk-core/issues/110)
- Conventions §10 names the five kinds of body a test may serve where it was not recorded,
  each saying where it comes from, and `mount_fixture`'s docstring how far `url=` moves a
  recording. A sample of a file over the cap that cannot be cut by bytes is written by a
  script from one download, its row saying what it keeps, and a pull request deletes the
  fixture it leaves replayed by nothing. §10 names the fixture directory of a wrapper
  recorded only through tasks, of two wrappers of one name and of an auth flow's exchange.
  (ADR-0003, ADR-0018, ADR-0020, §10, https://github.com/xippios/sdk-core/issues/64,
  https://github.com/xippios/sdk-core/issues/100,
  https://github.com/xippios/sdk-core/issues/118,
  https://github.com/xippios/sdk-core/issues/147)
- Conventions §8: an error that a tool can return and that names another task, the one to
  call instead or the list task that names the known values, names that task's MCP tool
  too, as sdk-usda-nass's does: `list_param_values('state_alpha') lists the known values
  (over MCP, the tool usda_nass_list_param_values).` A task of `BULK_TASKS`, which has no
  tool, is named alone.
  (ADR-0022, §8, https://github.com/xippios/sdk-core/issues/111)
  - Hand-apply: `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — the messages that
    name `list_order_categories` (line 279), `create_person` (line 289), `update_order`
    (line 2263) and `list_accounts` (line 2358) → each names the task's tool beside it,
    `cashctrl_<task>`, and the tests that pin a message follow it — §8.
    `src/xippios/comtrade/errors.py` (sdk-comtrade) — `QueryTooLarge`'s advice naming
    `get_counts` (line 53) → its tool beside it — as above.
    `src/xippios/comtrade/params.py` (sdk-comtrade) — the reasons naming `list_codes`
    (line 232) and the list task of `{task}` (line 305), and the refusals naming
    `get_commodity_series` (lines 1008 and 1017), `get_data` (line 1048) and
    `get_bilateral_data` (line 1140) → each tool beside its task — as above.
    `src/xippios/eurostat/tasks.py` (sdk-eurostat) — the refusals naming `get_data`
    (lines 558, 617, 671 and 747), `get_cross_section` (line 622), `list_codes` (lines
    1007, 1018, 1116 and 1278), `list_products` (line 1114), `list_cn8` and `list_hs`
    (line 1272) and the task of `{task}` (line 1119) → each tool beside its task — as
    above.
    `src/xippios/faostat/_client.py` (sdk-faostat) — the refusal naming `list_domains`
    (line 384) → its tool beside it — as above.
    `src/xippios/faostat/tasks.py` (sdk-faostat) — the refusal naming `get_data` (line
    510) → its tool beside it — as above.
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — the refusal naming
    `list_messages` (line 235) → its tool beside it — as above.
    `src/xippios/usda/esmis/tasks.py` (sdk-usda-esmis) — the refusals naming
    `search_publications` (lines 497 and 708) and `list_releases` (line 628) → each tool
    beside its task — as above.
    `src/xippios/usda/gats/errors.py` (sdk-usda-gats) — `HS6_REASON`, naming
    `list_hs6_commodities` (line 46) → its tool beside it — as above.
    `src/xippios/usda/gats/params.py` (sdk-usda-gats) — the messages naming
    `list_countries` (lines 235, 251 and 389), `list_customs_districts` (lines 438 and
    452) and `list_hs6_commodities` (line 561) → each tool beside its task — as above.
    `src/xippios/usda/psd/params.py` (sdk-usda-psd) — the messages naming
    `get_world_data` (lines 63 and 270), `list_commodity_attributes` (lines 196 and 210),
    and `list_regions` with `list_countries` (lines 254, 269 to 271 and 285) → each tool
    beside its task — as above.
    `src/xippios/usda/wasde/tasks.py` (sdk-usda-wasde) — the reasons naming `list_tables`
    (line 621), `list_commodities` (line 666) and `list_regions` (line 707), and the
    refusal naming `get_table` (line 781) → each tool beside its task — as above.
- `UnknownCode` names a closest code whose name is its own text once, `Did you mean VA?`
  where it wrote `VA (VA)`, and its tail reads `If upstream added it since, the packaged
  list is out of date.`, where it named the maintainers' `/refresh-reference-data`, which
  an agent cannot run. `closest` takes `cutoff=`, 0.6 by default as before, and 0.5
  lets a code of two characters with one of them wrong match, `VS` naming `VA`.
  (ADR-0022, §5, https://github.com/xippios/sdk-core/issues/111)
  - Hand-apply: `tests/test_tasks.py` (sdk-comtrade) — `REFUSED_756` (lines 275 to 276)
    and `REFUSED_C16` (lines 740 to 741) end with the old tail, so the tests that compare
    a message with them fail: lines 294, 755, 783, 1687, 1860, 2516, 2750, 3292 and 3323
    → the new tail in both constants — core's tail changed.
    `tests/test_tasks.py` (sdk-eurostat) —
    `test_get_total_production_refuses_a_product_its_list_lacks` (lines 1872 to 1873) →
    the new tail — as above.
    `tests/test_params.py` (sdk-usda-esr) —
    `test_the_recorded_unknown_commodity_is_refused_naming_the_nearest` (lines 197 to
    198) → the new tail — as above.
    `tests/test_params.py` (sdk-usda-gats) —
    `test_the_recorded_unknown_partner_is_refused_without_a_close_code` (line 184) and
    `test_an_unknown_customs_district_names_the_nearest_ids` (line 432), which assert
    `/refresh-reference-data` in the message, and
    `test_the_membership_check_names_the_parameter_it_was_given_as` (lines 560 to 561) →
    the new tail — as above.
    `tests/test_params.py` (sdk-usda-psd) — `test_unknown_commodity_code_names_the_closest`
    (lines 133 to 134) and
    `test_an_unknown_code_without_a_close_match_still_reads_as_sentences` (lines 274 to
    275) → the new tail — as above.
    `src/xippios/usda/nass/params.py` (sdk-usda-nass) — `_check_value`'s own
    `Did you mean` hint (lines 122 to 124) → `hint` passed only when `close` is empty, the
    `list_param_values` sentence kept — `UnknownCode` names each bare value once, the same
    text.
- `record` and `record_sync` send once through the client they are given, whatever its
  `RetryPolicy` says, and never answer from the cache, so a 429 or a 5xx is recorded as it
  came and spends no second request. A source with a quota or a bill no longer builds a
  client on `RetryPolicy(max_attempts=1)` to record through `record`.
  (ADR-0015, §10, https://github.com/xippios/sdk-core/issues/148)
- Conventions §4 sets a file task's `meta.endpoint` to the file's name as upstream names
  it, `wasde1026.xml` rather than the file kind `wasde.xls`, and a list packaged from a
  released file names that file the same way. A download of an operation's answer keeps
  the operation's name, a file whose name carries the dataset's name is named by the part
  that every dataset's file shares, sdk-faostat's `All_Data_(Normalized).csv`, and a file
  read from the publisher's own origin or mirror keeps its name, the mirror's URL in
  `meta.request`.
  (ADR-0020, §4, §6, https://github.com/xippios/sdk-core/issues/135,
  https://github.com/xippios/sdk-core/issues/244,
  https://github.com/xippios/sdk-core/issues/280,
  https://github.com/xippios/sdk-core/issues/276)
- Conventions §4 reads the period-series rules for an upstream with no release calendar,
  a task that fetches one period, a split mode of a free-form query and the note on a
  series tool's ceiling, which counts the upstream calls one tool call spends. A
  paginated task over a list unbounded by nature or a metered upstream may return one
  upstream page per call, its cursor on its data, and collect nothing.
  (ADR-0012, ADR-0022, §4, https://github.com/xippios/sdk-core/issues/136,
  https://github.com/xippios/sdk-core/issues/238,
  https://github.com/xippios/sdk-core/issues/177)
  - Hand-apply: `src/xippios/usda/esr/tasks.py` (sdk-usda-esr) — the docstrings of
    `get_exports`, `get_latest_week` and `get_top_destinations` say that an empty list
    may be a market year not yet released — they answer one market year without reading
    the release list, and ESR answers an unreleased year with `[]`.
    `src/xippios/usda/nass/tasks.py` (sdk-usda-nass) — the docstring of each task that
    fetches one year says that an empty answer may be a year not yet released — Quick
    Stats names no release.
- Conventions §4 settles four cases of a release's time and `vintage`. The naive flag also
  marks a time whose printed zone upstream's own calendar and files contradict, kept with
  its offset dropped, and a release identifier that is a day or a month stays in `vintage`
  with `published_at` empty. A frozen feed whose answers carry their own releases keeps
  each answer's release in `vintage`, and a parameter that takes back a vintage keeps what
  is strictly later, keeps the whole answer's meta and refuses a value with a zone.
  (ADR-0022, §4, https://github.com/xippios/sdk-core/issues/53,
  https://github.com/xippios/sdk-core/issues/108,
  https://github.com/xippios/sdk-core/issues/119,
  https://github.com/xippios/sdk-core/issues/158)
- A tool's error answer sets `isError` on its result beside the family's text,
  `error: <ErrorClass>: <message>`: the answer to a `XippiosError` that the task raises, to
  arguments that the tool's schema refuses and to an argument that it does not declare, so
  a client tells it from data without reading the text. `mcp_call_text` returns the text
  of an answer so flagged and still fails an unknown tool or a task that crashed.
  (ADR-0026, §8, https://github.com/xippios/sdk-core/issues/168)
- A route answers an argument that a typed parameter refuses, a value outside an enum, a
  missing one or a body that is no JSON object, as problem details before the task runs:
  status 422, title `InvalidRequestError`, detail `<argument>: <message>` as the MCP
  adapter words it, with the count when there are several, and no input value, where
  FastAPI's own 422 answered a `detail` list that echoed the input.
  (ADR-0007, §9, https://github.com/xippios/sdk-core/issues/66)
  - Hand-apply: `tests/test_tasks.py` (sdk-eurostat) —
    `test_get_data_route_refuses_an_argument_its_schema_refuses` (line 443) asserts
    `detail[0]["loc"]` → `answer.json()["detail"] == message`, the text of
    `SCHEMA_REFUSALS` that the tool's test asserts, with the title `InvalidRequestError`,
    and its docstring says that core answers it — the route answers problem details.
    `tests/test_tasks.py` (sdk-cashctrl) — `test_list_accounts_is_a_post_route` (line 541)
    asserts FastAPI's `literal_error` → `rejected.json()["title"] == "InvalidRequestError"`
    and a detail that starts with `dir: ` — as above.
- Conventions §2 lets a task compose another task of its own `tasks.py`, awaiting its
  `_async` function, so the request, its refusals and the meta live once, and §4 has the
  composing task build its meta through the `ResultMeta` constructor, never `model_copy`.
  A parser of a bulk file kind may return `Iterator[Model]`, a generator that reads the
  file as the records are taken, where every other parser returns `list[Model]`.
  (ADR-0001, ADR-0020, §2, §4, https://github.com/xippios/sdk-core/issues/70,
  https://github.com/xippios/sdk-core/issues/90)
- Conventions §2 and §6 pace each host a source sends to with one limiter: a second base
  URL on the same host goes through the source's one client, a publisher's own origin or
  mirror takes its canonical host's pace with `meta.endpoint` naming the URL sent, or a
  file's name for a file, and a dependent sends nothing to its dependency's host. `classify` maps the shapes upstream
  documents and, where it documents none, the shapes the source recorded, each backed by
  a fixture that a test passes to it, which the review checklist's item 3 checks.
  (ADR-0008, ADR-0010, §2, §4, §6, https://github.com/xippios/sdk-core/issues/61,
  https://github.com/xippios/sdk-core/issues/113,
  https://github.com/xippios/sdk-core/issues/239,
  https://github.com/xippios/sdk-core/issues/276)
- Conventions §3 gives what upstream does but never documents one home, the hand-written
  `docs/upstream/OBSERVED.md`, each note naming its probe or the files it was written
  from, and the review checklist's item 2 counts a parameter traceable there as traced.
  `FETCHED.md` lists the pages a snapshot leaves out under `Not fetched` with their
  reason, a page behind a login with its status and redirect host, and a sample under
  `docs/upstream/samples/` is documentation with its row, never a test fixture.
  (ADR-0003, §3, https://github.com/xippios/sdk-core/issues/55,
  https://github.com/xippios/sdk-core/issues/103)
- The recorder drops the response headers that only identify a request, such as
  `x-amz-cf-id`, `x-request-id` and `x-transaction-id`
  (`xippios.core.testing.fixtures.REQUEST_ID_HEADERS`), so a new recording brings no audited
  entry of the secret scan for them. `ETag` and `x-amz-version-id` stay.
  (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/161)
- The response cache stores an answer only once `get_answer` has decoded it and, with
  `parse=`, parsed it, so a 200 whose body fails is requested again on the next call
  instead of answering from the cache until its entry expires. `get`, `get_json`,
  `request` and `record` still read the cache and store nothing.
  (ADR-0015, §6, https://github.com/xippios/sdk-core/issues/122)
- `cap_result` cuts the rows of a result whose `data` is a model that holds one list, and
  no other field a list, once it passes the byte bound: the rows are cut as a list
  result's are, with the usual note, and the model's other fields stay whole, where the
  model was a note and a preview until now. Within the byte bound such a model returns
  whole, and a model with no list or with two, or whose other fields alone pass the
  bound, is still the preview.
  (ADR-0016, §8, https://github.com/xippios/sdk-core/issues/131)
  - Hand-apply: `tests/test_tasks.py` (sdk-cashctrl, sdk-x) — a test that expects a note
    and a preview from a model over its cap (`get_report_data`, `count_posts`) → its rows
    cut, its other fields whole and the cut note — the cut of a model's rows.
    `CLAUDE.md` (sdk-cashctrl, sdk-x) — the lines that say such a result is cut whole into
    a note and a preview → its rows are cut and its other fields kept — the same cut.

### Fixed

- `parse_decimal` gives `None` for the texts `NaN`, `Infinity` and `sNaN` and every other
  result that is no finite number, where it gave `Decimal('NaN')`, `Decimal('Infinity')`
  and `Decimal('sNaN')`, as its docstring promised for anything that is not a number.
  Every finite text reads as before.
  (ADR-0008, https://github.com/xippios/sdk-core/issues/128)
  - Hand-apply: `src/xippios/usda/wasde/parse/wasde_xml.py` (sdk-usda-wasde) — `_value`
    (lines 198 to 201), whose `is_finite()` guard (line 201) → `return parse_decimal(text)`,
    `tests/test_parse.py`'s `NaN` and `Infinity` cases (lines 377 to 378) passing
    unchanged — core gives `None` for them.
- `render_enums` keeps a camelCase hump in a default class name, after a lower-case letter
  or a digit, `attributeId` giving `AttributeId` where it gave `Attributeid` and
  `partner2Code` `Partner2Code`, and a key without a hump keeps its name, `state_alpha`
  and `STATE_ALPHA` `StateAlpha`. The default gives every class name that sdk-comtrade,
  sdk-usda-esr, sdk-usda-gats, sdk-usda-nass and sdk-usda-psd commit, but sdk-usda-nass's
  `ProgressStage` and `ConditionCategory`, which stay in its `class_names`, so no class a
  source commits changes its name and a re-render under conventions §15 item 6 writes the
  same module.
  (ADR-0008, https://github.com/xippios/sdk-core/issues/95)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-usda-esr, sdk-usda-gats,
    sdk-usda-psd) — the line `class_names[id_field] = id_field[:1].upper() +
    id_field[1:]` (esr line 125, gats line 148, psd line 142), the `class_names` dict
    (lines 113, 139 and 130) and its argument to `render_enums` (lines 126, 149 and 143)
    → dropped: the default gives `UnitId`, `UnitOfMeasureId`, and `UnitId` and
    `AttributeId` — the default gives the line's name for an id field in camelCase with no
    upper-case run and no separator, as each of these is. For another id field the line
    stays: it keeps `countryISO` as `CountryISO` and `unit_id` as `Unit_id`, where the
    default gives `CountryIso` and `UnitId`.
    `scripts/refresh_reference.py` (sdk-cashctrl, sdk-faostat, sdk-google-mail, sdk-x) —
    the same line (line 110 in sdk-cashctrl, sdk-google-mail and sdk-x, 181 in
    sdk-faostat), its dict (98, 169) and its argument (111, 182) → dropped, since none of
    the four renders a list yet, as long as each id list it takes up later has such an id
    field — as above.
    `scripts/refresh_reference.py` (sdk-comtrade) — `class_names=class_names` in the
    `render_enums` call (line 483) → dropped, the dict of line 478 kept for the order of
    line 479: the default gives the ten names it sets, each key in camelCase with no
    upper-case run — as above.
- A sync task whose coroutine raises `SystemExit` or `KeyboardInterrupt`, or awaits a task
  that does, hands it to its caller, and the background loop serves the next call, where
  the loop's thread ended and that call and every later one waited for ever. So a script
  may exit from inside a sync task with its status. `sync` of a callable without a
  `__name__`, a `functools.partial` say, raises a `TypeError` that names
  `functools.update_wrapper`, where it raised an `AttributeError`.
  (ADR-0002, https://github.com/xippios/sdk-core/issues/77)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-usda-esmis) — the docstring of
    `Refused` (lines 58 to 63) drops its reason, that a `SystemExit` raised in the
    coroutine stops the loop's thread and leaves the caller waiting for ever. `Refused`
    may stay as the walk's refusal that `main` turns into its exit — core hands a
    `SystemExit` back to the caller.
- The docstrings of `fixture_path`, `replay_fixture`, `ReplayFixture` and the fixture
  module name the fixture directory after the wrapper function, or the task for an
  exchange recorded through a task, as conventions §10 has it since 1.22. The parameter
  keeps its name, `endpoint`. (ADR-0003, §10, https://github.com/xippios/sdk-core/issues/97)
- Both adapters keep the metadata of an `Annotated` task parameter: a `Field` constraint,
  a description or a validator reaches the tool's input schema and argument check and the
  route's parameters, where it was dropped and enforced by nobody. A tool answers a value
  that the constraint refuses as any refused argument, and a route as 422.
  (ADR-0007, ADR-0014, §8, §9, https://github.com/xippios/sdk-core/issues/68)
- A cache miss through `get_answer` carries the time its entry was stored, one reading of
  the clock for both, taken when the answer arrived and before the decode and the parse,
  so a later hit and the miss that stored it report one `retrieved_at` and a test
  asserts them equal.
  (ADR-0015, §4, https://github.com/xippios/sdk-core/issues/79)
- `register_tasks` and `router_from_tasks` skip a bulk task behind a wrapper whose own
  `__module__` names another module, a tenant lock's, when its `__wrapped__` leads to the
  task. A wrapper that keeps neither wraps `tool_functions(tasks)`, which leaves the bulk
  tasks out first.
  (ADR-0019, https://github.com/xippios/sdk-core/issues/170,
  https://github.com/xippios/sdk-core/issues/155)
- `quiet_request_logging` sets the `httpx2` and `httpcore2` loggers to `WARNING` with
  `httpx` and `httpcore`, so the `mcp` SDK's own HTTP client logs no request URL either.
  The testing plugin gives all four levels back after every test.
  (ADR-0005, ADR-0013, §10, https://github.com/xippios/sdk-core/issues/176)
- A cut that shows no row, since the first row alone passes the byte bound, says so in its
  note, `the first row alone exceeds the byte cap` or `the row at offset <start> alone
  exceeds the byte cap`, and names no resume offset. Until now it ended `resume with
  start=<start>`, the start the call had just used, so a tool that followed the note asked
  for the same row again.
  (ADR-0016, §8, https://github.com/xippios/sdk-core/issues/175)

### Security

- The client's `auth` goes to the base URL's origin only, so a file link on another host
  gets no key unless the call passes an `httpx.Auth` of its own, and a signed link in
  `meta.request` reads its signature (`sig`, `X-Amz-Signature`) `REDACTED`. A request sent
  with `auth=None` or to another origin spends no quota: the `QuotaPolicy` neither holds it
  back nor reads its answer, the limiter still paces it, and the api.data.gov gateway's
  `classify` reads the base URL's answers alone. Every request carries the extensions
  `xippios_auth` and `xippios_origin`, which say where its credentials go.
  (ADR-0015, ADR-0019, ADR-0009, §4, §6, §7, https://github.com/xippios/sdk-core/issues/163)
  - Hand-apply: `src/xippios/comtrade/_client.py` (sdk-comtrade) — the comment above `auth`
    (lines 206 to 213) says that the keyless reference files and public operations take
    the pace alone, no longer `policy` — a spent key quota holds no keyless call back.
    `src/xippios/comtrade/api/get_comtrade_releases.py` (sdk-comtrade) — the module
    docstring (lines 12 to 14) drops "and its `policy`: once upstream has said the key's
    quota is spent, this call is held back too" — the same.
    `src/xippios/comtrade/api/get_world_share.py` (sdk-comtrade) — the module docstring
    (lines 14 to 16), the same sentence — the same.
    `CLAUDE.md` (sdk-comtrade) — the reference files' "and a spent quota holds it back
    too" (line 70) and the public operations' "and `policy`, so a spent key quota holds
    them back too" (lines 77 and 78) go — the same.

### Breaking

- A multi-tenant source declares the parameter that names a tenant once, on its registry,
  `Tenants(..., param="org")`, required, and a server bound to one tenant no longer serves a
  task unbound: `bind_tasks` refuses, with `ValueError` naming the task and the parameter, a
  task that lacks it, where it returned the task as it was, unless it is the tenant list or
  its module names it in `NO_TENANT_TASKS`, beside `BULK_TASKS`, as touching no tenant. The
  family check gains `test_family_tasks_take_one_tenant`, which holds every task of a source
  with a `Tenants` registry, with no opt-in, to the registry's `param` once, required with
  no default, a `str`, the same two excepted, and `serve_tenants` takes its option from the
  registry and `TenantLock(TENANTS, "acme")` takes the registry, where both took a `param`
  of their own. Conventions §7 states the line for core and for a source's own tasks: one
  tenant per task, required, names only from the tenant list, nothing shared between
  tenants.
  (ADR-0036, §7, §8, https://github.com/xippios/sdk-core/issues/298,
  https://github.com/xippios/sdk-core/issues/299)
  - Hand-apply: `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `param="org",` after
    `list_var="CASHCTRL_ORGS",` in the declaration `TENANTS = Tenants(...)` (line 97) —
    core's `Tenants` requires the parameter that names a tenant, and the family check holds
    each of the 46 tasks to it, which takes `org` once, required, a `str`.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — `param="account",` after
    `list_var="GOOGLE_ACCOUNTS",` in the declaration `TENANTS = Tenants(...)` (line 104) —
    as above, for the 11 tasks, which take `account`.
- `download` refuses a `dest` that is a directory, or whose directory does not exist, with
  `InvalidRequestError` in the client's source's name, where it raised `ValueError`, with
  the same two texts and still before anything is sent, `before_request` included. Code
  that caught `ValueError` for it catches `InvalidRequestError`. Its documents and
  `Downloaded`'s state the mode of the file it writes, `0600`, as `tempfile.mkstemp`
  creates it, also over a file of another mode.
  (ADR-0019, ADR-0007, §5, §6, https://github.com/xippios/sdk-core/issues/152)
  - Hand-apply: `src/xippios/eurostat/tasks.py` (sdk-eurostat) — `_target` (lines 1508 to
    1522) goes, and `download_dataset_async` (line 1651) and `download_trade_async` (line
    1767) pass `Path(dest)` — core refuses a bad `dest` with eurostat's two texts before
    any request, as `tests/test_tasks.py` asserts at lines 1482, 1485, 2650 and 2653,
    which pass unchanged.
    `src/xippios/eurostat/api/sdmx.py` (sdk-eurostat) — `data_query`'s `Raises:` names
    `InvalidRequestError` for a bad `dest` where it names `ValueError` (line 195) — core's
    refusal is the taxonomy's.
    `src/xippios/cashctrl/api/_download.py` (sdk-cashctrl) — the docstrings of `check_dest`
    and `download` drop "where core's `download` raises `ValueError`" (lines 96 to 98 and
    128 to 130). `check_dest` stays, since `download` streams into a temporary file of its
    own, which core's check never sees, and a report's tree is read before it — core no
    longer raises `ValueError`.
- A tool refuses an argument that it does not declare before it runs, whatever its value,
  and names the ones it declares, where the argument was dropped and the tool ran with its
  default:
  `error: InvalidRequestError: yaer: Not an argument of this tool; it takes series_id, year`.
  So a call that still names a tenant on a server that a lock binds is refused, where it
  ran for the bound tenant.
  (ADR-0014, §8, https://github.com/xippios/sdk-core/issues/84)
  - Hand-apply: `tests/test_org_lock.py` (sdk-cashctrl) —
    `test_a_call_that_still_passes_org_is_answered_for_the_bound_org` (line 175) → the
    call is refused with
    `error: InvalidRequestError: org: Not an argument of this tool; it takes note`
    and the tool does not run, and
    `test_the_bound_read_server_reaches_the_bound_organisation_only` (line 216) → calls
    `cashctrl_list_currencies` with `{}`, its `{"org": "xa"}` refused — core refuses an
    argument that no tool of a bound server declares.
    `CLAUDE.md` (sdk-cashctrl) — the sentence that a call that still passes `org` is not
    refused, observed under core 0.3.0 → core's argument check refuses it, naming the
    tool's arguments — as above.
    `tests/test_account_lock.py` (sdk-google-mail) —
    `test_a_call_that_still_passes_account_is_answered_for_the_bound_account` (line 185)
    → refused with
    `error: InvalidRequestError: account: Not an argument of this tool; it takes note`,
    and `test_the_bound_read_server_answers_for_the_bound_account_only` (line 221) →
    calls `google_mail_get_profile` with `{}`, its `{"account": "xa"}` refused — as above.

## [0.3.2] - 2026-11-17

No behavior changes: the code is that of 0.3.0 but for a docstring. The repository's own
`.github/` names nothing that stands around it, its organization's checks start on no label
as sdk-template renders them for a source, and the family check's docstring tells a source's
two CI steps as sdk-template 0.3.3 renders them. A source takes nothing by hand: its bound
`~=0.3.0` takes 0.3.2.

### Changed

- `.github/workflows/organization.yml` runs on the opening, a push, a reopening and an edit
  of a pull request, no longer on `labeled`, and neither of its jobs has a condition of its
  own, as sdk-template renders the file for a source: GitHub reports a head's checks from
  its newest run, and a label set at the opening started a run that skipped both jobs.
  `.github/CODEOWNERS` no longer owns `/rules/**`, a path that the same render drops and
  that holds no file here. (https://github.com/xippios/sdk-template/issues/152,
  https://github.com/xippios/sdk-core/issues/231)
- `.github/CODEOWNERS` is the repository's own file: its header says so, and it names the
  paths that sdk-template renders for a source, without the lines under `src/` and of
  `workspace.toml`, `composer.json` and `package.json`, which matched no file here. The
  comment of `.github/workflows/publish.yml` names the maintainer who approves the `pypi` run
  by role and says that nobody pushes the tag by hand, and no step of the workflow changes.
  (https://github.com/xippios/sdk-core/issues/224, https://github.com/xippios/sdk-core/issues/215)

### Fixed

- The docstring of `xippios.core.testing.family` describes the two CI steps of a source as
  sdk-template 0.3.3 renders them: every pull request but Dependabot's brings an entry, a
  fragment under `changelog/` or a change of `CHANGELOG.md`, and no branch name exempts a
  release or an adoption. A fixture that a pull request only moves is neither added nor
  changed under the cap, as ADR-0019's amendment of 2026-11-13 reads it.
  (ADR-0019, §12, https://github.com/xippios/sdk-core/issues/209)

## [0.3.1] - 2026-11-13

Documents only: the code is that of 0.3.0. With conventions 1.26 and 1.27 the documents say
what a change must satisfy wherever a repository is worked and leave out how a change lands,
the 27 decision records have an index, a change's entry is a fragment under `changelog/`,
and `README.md` lists the documents. The release also carries the documentation that waited
since 0.3.0: conventions 1.22 to 1.25 and the records of Google Mail, the host and X
(ADR-0025 to ADR-0027).

### Added

- `.github/CODEOWNERS` names the paths whose change needs the maintainer's review: of the
  repository's own files, `.github/`, `.claude/`, `CLAUDE.md` and `pyproject.toml`.
  (https://github.com/xippios/sdk-core/pull/190, https://github.com/xippios/sdk-core/pull/198)
- The 27 decision records have an index, `docs/adr.md` for people and `docs/adr.json` for
  machines, which `scripts/adr_index.py` writes from the records' headers. With `--check` it
  writes nothing and exits 1 when either file is stale, a record's first line does not read
  `# ADR-NNNN: <title>` or two records take one number. Each header reads
  `Status: <status> · Date: <date>`, then its other fields, and `docs/reports/` holds the dated
  reports a record cites.
  (https://github.com/xippios/sdk-core/issues/193)
- Every change brings its changelog entry as a fragment, a file of its own under `changelog/`
  holding its bullet, which the release assembles into its section of `CHANGELOG.md`.
  `changelog/README.md` gives a fragment's name, its bullet and its Hand-apply note, for a
  change that a source's adoption follows by hand.
  (https://github.com/xippios/sdk-core/issues/197)

### Changed

- The records carry what conventions 1.26 changed. ADR-0018's amendment of 2026-11-13 names
  each rule it changes and gains (p): the clause that bound a source starting on a git pin of
  core 0.3.0 left the header, since every such source bounds `xippios-core~=0.3.0` from PyPI.
  ADR-0019 gains an amendment for §10's reading that a fixture a pull request only moves is
  neither added nor changed, and ADR-0027 gives its probe's count of requests and no longer
  what they cost. (ADR-0018, ADR-0019, ADR-0027, §10,
  https://github.com/xippios/sdk-core/issues/221)
- Conventions 1.27: §13 names `xippios/.github` as the organization's repository whose
  reusable workflows are called at `@main`, where it named the retired gates' repository.
  §12 has a dependent that bundles its adoption with feature work say so in its release's
  section of `CHANGELOG.md`, where it said a briefing. (ADR-0018, ADR-0021, §12, §13,
  https://github.com/xippios/sdk-core/issues/207)
- A pull request runs the organization's checks from `xippios/.github`:
  `.github/workflows/organization.yml` calls the conventions review as the job
  `conventions` and the ADR-index check as the job `adr-index`, and `gates.yml`, which
  called the two workflows of the retired gates, is deleted. `mypy --strict` reads
  `scripts/` beside `src` and `tests`. (§11, §13,
  https://github.com/xippios/sdk-core/issues/191,
  https://github.com/xippios/sdk-core/issues/206)
- The repository works alone: `README.md` lists its documents under `## Documents`, each by
  its URL on GitHub, and `CLAUDE.md` gives the package, its layout, its commands and its
  code rules and links that list.
  `.claude/settings.json` allows the checks and local git and no push, pull request or
  merge, and the pull request template copies the definition of done, the fragment under
  `changelog/` among it, as a reminder that the description need not tick.
  (ADR-0018, https://github.com/xippios/sdk-core/issues/191,
  https://github.com/xippios/sdk-core/issues/202,
  https://github.com/xippios/sdk-core/issues/216)
- Conventions 1.26: the documents say what a change must satisfy wherever a repository is
  worked and no longer how it lands, so §13, §15, the definition of done and the review
  checklist drop the merge classes, the auto-merge of an adoption or release PR, the
  branch names and the rule that a PR's description is the checklist. A change's entry is
  a fragment under `changelog/`, which a release PR assembles and deletes as one of the
  files §12 lets it change, and a repository without the folder keeps a line under
  `## [Unreleased]`. §2 names an existing source's rename PR without ambiguity, §10 lets a
  fixture over the cap move with its directory, and the hand-over and the roadmap lose
  their stale sentences. (ADR-0018, §2, §10, §12, §15,
  https://github.com/xippios/sdk-core/issues/203)

### Documentation

- **ADR-0003, amendment 2026-10-28**: fidelity in names is owed to what a consumer sees,
  `meta.endpoint`, the first line of a wrapper's docstring, the snapshot and the
  packaged parameter names; a layer-1 wrapper's module and function carry the upstream
  operation name in snake case, and its fixtures live in a directory named after it; the
  task layer and the MCP tool names are unchanged. **ADR-0018** gets a dated note under
  amendment (e): the gates repository has been `xippios/sdk-gates` since its rename on
  2026-10-27.
- **Conventions 1.22**: §2 names a wrapper module and its function after the upstream
  operation in snake case, from the operation's id in the snapshot (an OpenAPI
  `operationId`, a WADL method id) or else from the path (an `operationId` that restates
  the path, or an opaque one, counting as absent), without a controller prefix every
  operation of the API shares (the FAS APIs' `ESRData_`, `PSDData_`, `GATSData_`), a run
  of capitals one word, a file suffix that tells operations on one path apart kept as
  the last word (the default `.json` dropped) and upstream's spelling kept; the verbatim
  id stays in the wrapper's docstring and in its `endpoint=`, so `meta.endpoint` does
  not change; where operation ids repeat, one module per service holds them; a second
  function on the same endpoint is named after the wrapper with a suffix that says what
  differs, and a helper that calls no endpoint keeps a plain name; an existing source
  renames in one PR of its own right after its core 0.3.0 adoption, never inside it, or,
  already past that adoption, in the first PR of its next version. §10 keeps a wrapper's
  fixtures under `tests/fixtures/<wrapper>/<case>.json`, the case name in lowercase
  snake case with an upstream code written as upstream writes it, and a fixture recorded
  through a task rather than a wrapper lives under the task's name. §15 item 3 makes
  code core removed for its one consumer part of that consumer's adoption, copied from
  the commit core's handover names and listed file by file in the PR description with
  the ADR that moved it; item 8 excepts 1.22's name rule; §15 names `xippios/sdk-gates`
  as the home of the merge classes.
- The definition of done's Adoption PR block and its copy in
  `.github/PULL_REQUEST_TEMPLATE.md`: a line for code copied in from core, the current
  conventions version applied with 1.22's name rule excepted, and `xippios/sdk-gates` as
  the home of the merge classes.
- The review checklist's item 16: a new wrapper's module, function and fixture directory
  follow the name rule, and the verbatim id stays in the first line of its docstring and
  in `endpoint=`.
- **ADR-0025**: Google Mail, sdk-google-mail's decisions. Its read server is held to
  loopback unless `--allow-remote`, checked in its own `apply_options` until core 0.4.0
  carries the `loopback_only` option (row 282, the host its second consumer by the
  session's recommendation, row 296); `RefreshTokenAuth`, an `EnvKeyAuth` whose key is
  the refresh token and whose `auth_flow` renews the access token in memory, is the
  second consumer of a renewing-bearer base for core 0.4.0; a grant's scopes are
  upstream's to enforce, and `classify` maps the refusal to a re-consent `AuthError`;
  the multi-tenant kit (`Tenants`, `list_task`, the binding lock wrapper,
  `assert_write_tools`, the demo-only conftest strip, the serve command) is copied from
  sdk-cashctrl and returns to core in 0.4.0; `get_message` returns a decoded view, a
  projection by MIME role, the faithful tree on the wrapper.
- **ADR-0026**: the host xippios-mcp, a public package that is no source. 0.1.0 runs on
  today's packages, each package's server mounted by path; a group never mixes read and
  write tools, and the tool lists are checked at startup; per-endpoint auth is none or a
  bearer, the bearer the default, with allowed hosts and `transport_security` for a
  reverse proxy; the host applies the loopback rules itself to an endpoint with `auth:
  none` and is `loopback_only`'s second consumer (row 282), the session's recommendation
  (row 296); `isError` is read once core sets it; the `-read` and `-write` names; the
  template's package contract is its 0.2.0 interface; the sources are extras with `>=`
  bounds, an exception to ADR-0021 for the host alone; claude.ai needs an OAuth
  authorization server in front, Pomerium Core the runbook's choice. `CLAUDE.md` lists
  both ADRs.
- **ADR-0014, ADR-0018, ADR-0021, ADR-0022, ADR-0023 and ADR-0024, amended 2026-10-29**:
  ADR-0024's decision 6 is reversed for the kit that returns to core, as its status line
  now says, with a dated line each under ADR-0014 and ADR-0023; ADR-0014's second line
  makes the host the deployment that protects a write server beyond loopback. ADR-0021
  gains the dependency order (a dependent's adoption release follows a dependency's new
  minor right after, a breaking minor only, since a patch reaches the dependent inside
  its bound), the route for a dependency's new surface and a pointer to the host's
  exception; ADR-0022 a reading of 2026-10-29, a load time is never a vintage for a
  source whose only time is a load time; ADR-0018 (g) the version rule, (h) the refresh
  rule and (i) §15's three routes.
- **Conventions 1.23**: the version line applies the conventions to the host
  `xippios-mcp` where ADR-0026 binds it. §1 names `xippios-<source>-mcp-read` and
  `-write` for a source with a write server, lists `google-mail` (the shared namespace
  `google`, Drive later as `google-drive`) with the dated sentence that `mail` is
  Johannes's name for the product upstream calls Gmail, and names
  `GOOGLE_<NAME>_REFRESH_TOKEN`; §3 makes a MIME message's decoded view a projection by
  role; §4 says a load time is never a vintage, for a source whose only time is the time
  upstream loaded the data; §8 names the servers `-read` and `-write` where a write
  server exists, keeps `server.name` the slug, has a host group never mix read and write
  tools, and has an error answer set `isError` from a source's adoption of the core
  release that carries the code (core 0.4.0 as planned, row 283); §12 states the version
  rule (pre-1.0 only a breaking change bumps the minor), the refresh rule (a PR only
  when a record changed or `fetched` goes from a bare date to the full time, otherwise a
  coordination log line the release PR cites) and the dependency order; §13 gains the
  topic `email`; §15 gains three routes, a core release without a template tag, a
  dependency's minor whose new surface the dependent uses and a source frozen on a
  template tag, item 2 not applicable on the first and the third.
- The definition of done's `copier update` line and its last Process line, and their
  copies in `.github/PULL_REQUEST_TEMPLATE.md`: `copier update` not applicable on §15's
  routes (1) and (3); the reference refresh a PR of its own only when a record changed
  or `fetched` went from a bare date to the full time.
- The review checklist's items 12 (§15's item 2 does not apply on §15's routes (1) and
  (3)) and 13 (the refresh rule), and its leak rule, which names `_REFRESH_TOKEN` and
  `_SECRET` beside `_API_KEY`, as `CLAUDE.md`'s now does.
- `docs/handover.md`, "Adopting core 0.3.0", sdk-cashctrl: two dated brackets, its
  template frozen on v0.2.2 (§15's route (3)) and its copy of `client_for`, which closes
  the replaced client.
- **ADR-0027**: X as a metered, content-bearing source, sdk-x's decisions. The first
  release reads with the app's Bearer Token in `X_API_KEY` through `BearerAuth`, and
  posting, user-context auth and owned reads wait for their own ADR; spend is bounded
  outside the code, by the console's spending limit, a dollar budget line in every
  briefing that spends X credit and one billable live call a night, and the 15-minute
  per-endpoint windows are `classify`'s, with no `QuotaPolicy`; fixtures are recorded
  only from @XDevelopers, @USDA and @FAO, the recorder rewriting X Content by key before
  the write and admitting the `most_recent_post_id` expansion only; tasks return one
  upstream page per call with explicit token paging, at most 0.50 USD for posts or 1.00
  USD for users (1.50 USD with `lookup_users`' optional `most_recent_post`), under
  per-tool byte caps that hold a whole page; curated account lists are never packaged.
  Nothing in `xippios.core` changes. `CLAUDE.md` lists it.
- **ADR-0010, ADR-0025 and ADR-0026, amended 2026-10-30**: ADR-0010 leaves per-endpoint
  windows shorter than an hour to `classify` under a fast self-imposed pace, never
  rationed ahead and with no `QuotaPolicy` (row 304); ADR-0025's D-c records the scope
  refusal Gmail sends, HTTP 403 `insufficientPermissions` with an `insufficient_scope`
  challenge, not the 401 `authError` fold, and that permanent deletion and the settings
  writes would each be a third scope set (row 333); ADR-0026 gains host-built servers for
  groups and tool lists, the Forge recipe out of the public repository, the entry point
  `xippios-mcp`, the `-read` and `-write` rule as the operator's, and D114's free host
  minors with the package contract at its first minor after core 0.4.0 and template
  v0.4.0 (row 306).
- **Conventions 1.24**: §1 lists `x` among the sources (ADR-0027); §6 leaves
  per-endpoint windows shorter than an hour to `classify`, with no `QuotaPolicy` until
  row 318 (ADR-0010, amendment 2026-10-30); §13 gains the topic `social-media`
  (ADR-0027).
- **ADR-0016, amended 2026-10-30**: decision 4's byte bound above the default gains a
  second case beside a reference list an agent needs whole, a tool whose result is one
  upstream page that must return whole, to which the row bound never applies, which a cut at the default
  would turn into a preview: a cursor-paged page losing the `next_token` the caller
  needs for the next page, or a bounded lookup (sdk-x's post tools at 128,000 bytes and
  `lookup_users` at 160,000, row 338 item 3); the row bound is unchanged, and where the
  upstream bills per result the tool's docstring states the price. **ADR-0027** names
  that amendment beside ADR-0016's decision 4 in its decision 4 and §8's clause in its
  Consequences, and its Rejected bullet cites ADR-0012's collect-every-page decision by
  its content. The README's cap paragraph names the whole-page case beside the
  reference tool.
- **Conventions 1.25**: §8 gives a tool whose result is one upstream page that must
  return whole a byte bound of its own, beside the reference tool's (ADR-0016,
  amendment 2026-10-30).

## [0.3.0] - 2026-10-27

The family review of 2026-10-25 in one minor: its core items C1 to C11 and C13 to C15
(C12 shipped in 0.2.1), each named below with what it did; the code of ADR-0019 (bulk
downloads and non-JSON payloads) and ADR-0022 (packaged answers and release times),
whose rules 0.2.1 shipped as documentation; and ADR-0024, under which sdk-cashctrl
stands alone: tenants, the tenant lock, `assert_write_tools` and the recorder's host
placeholder, encoded matching, JSON verify and `rewrite` leave core for it. What had no
consumer is deleted and the export lists keep what consumers import (ADR-0023); what
sdk-usda-psd, sdk-usda-esr and sdk-usda-gats carried as copies, the api.data.gov gateway
and the packaged lists with their refusals, is core's now. Conventions 1.16 to 1.21 come
with it (0.2.1 shipped 1.15). While core is 0.x a minor keeps no compatibility with the
one before it (conventions §12): a source moves to `xippios-core~=0.3.0` and adopts this
release in one adoption PR before its next release, through conventions §15 with
`/adopt-release` (ADR-0018), and the rules of ADR-0019 and ADR-0022 bind it from that
adoption (conventions, header of 1.21). "Hand-apply for sources" below lists, per
source, what that PR changes by hand; the section "Adopting core 0.3.0" of
[`docs/handover.md`](https://github.com/xippios/sdk-core/blob/main/docs/handover.md), in
the repository and not in the sdist, walks the same items through §15.

The test suite counts 6,830 lines, from 8,072 at 0.2.1 and 7,546 at 0.2.0, by
`git ls-files 'tests/**/*.py' 'tests/*.py' | xargs cat | wc -l`, against the family
review's target of about 4,500 to 5,000. It stays above the target: the deletions with
no consumer took 834 lines and the move to sdk-cashctrl 1,271, while the tests of the
new code added 863 net, 29 for the gateway module after the slimmed quota policy's tests
went, 494 for the downloads, the recorder's truncation and the redaction rule, 310 for
the packaged answers, and 30 for the renderer, the argument check, the payload-free
parse failures, the cache clearing and the live run's quota summary, after 214 lines of
renderer tests went.

### Removed

- **`xippios.core.config` and the `pydantic-settings` dependency** (the family review's
  C1, a settings module with no consumer; ADR-0002, amendment 2026-10-27; ADR-0023,
  decision 5): `SourceSettings` goes; `resolve_api_key`, whose one caller was
  `EnvKeyAuth`, is folded into `xippios.core.client.auth` as a private helper with the
  same behaviour for that caller and the same `ConfigError` message. `pydantic` stays,
  `SecretStr` with it. Conventions 1.16 §7: the environment is read through the
  `EnvKeyAuth` helpers.
- **The sync `Client`** (the family review's C2, a sync client with no consumer;
  ADR-0002 and ADR-0015, amendments 2026-10-27): every source derives its sync task
  functions with `xippios.core.sync`, which stays. `xippios.core.client` no longer
  re-exports `UseClientDefault`, and core no longer imports it from httpx's private
  `httpx._client`: `auth=` keeps its three states on `AsyncClient.request`, `get` and
  `get_json` and on `record` and `record_sync` (the client's credentials by default,
  `None` for none, an `httpx.Auth` to replace them), its default now a sentinel of
  core's own.
- **`AsyncClient.derive`, the `limiter=` argument and the `limiter` property, and
  `retry=` and `timeouts=` on `record` and `record_sync`** (the family review's C3,
  overrides no source calls; ADR-0015, amendment 2026-10-27; asked for by sdk-comtrade):
  the rate limiter is built from `config.rate_limit` alone, and the testing plugin,
  which patches `TokenBucket.acquire`, needs neither. A recording goes through the
  client it is given; one that must not retry a 5xx records through a client whose
  config says `RetryPolicy(max_attempts=1)`. `auth=` per call stays: sdk-comtrade
  records its keyless reference files with it.
- **`paginate_pages` and `paginate_cursor`** (the family review's C4, page paging folded
  into offset paging and cursor paging deleted; no consumer): `paginate_offset` keeps
  its signature, and its docstring shows how a page-numbered endpoint maps the offset to
  its page, `page = first_page + offset // page_size`. sdk-cashctrl, its one consumer,
  is unaffected.
- **26 names leave the export lists** (the family review's C5, the public surface cut to
  what consumers import; ADR-0023, decision 5: an `__init__.py` exports only what
  consumers import), each still importable from the module that defines it:
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot` and `load_csv` from `xippios.core`;
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot`, `WIRE_HEADERS`, `Params`,
  `TokenBucket`, `send_with_retries` and `strip_wire_headers` from
  `xippios.core.client`; `LIVE_ENV`, `PLACEHOLDER_KEY`, `FixtureRequest`,
  `live_enabled`, `mount_fixture`, `replay`, `write_fixture`, `scrub_headers`,
  `scrub_params` and `scrub_url` from `xippios.core.testing`; `is_write_server`,
  `quiet_request_logging` and `register_tasks` from `xippios.core.mcp`;
  `PROBLEM_MEDIA_TYPE`, `STATUS_BY_ERROR`, `install_error_handlers` and
  `problem_response` from `xippios.core.http`. With the six deleted names above, the
  five lists go from 113 entries (98 names) to 81 (69 names); with the names added below
  and the three that move out, 88 (74) at 0.3.0. No source imports a removed name from a
  package.
- **`QuotaPolicy`'s `reset_header`, with the reset header's three formats** (the family
  review's C6, a slimmer `QuotaPolicy`; ADR-0015, amendment 2026-10-27; no source sets
  it, and api.data.gov sends no reset header): delay-seconds, epoch seconds and an
  HTTP-date are no longer read. A spent quota is back after a 429's `Retry-After`, the
  seconds `spent` names, or `window`, each cut to `window`.
- **`QuotaPolicy.mark_spent`** (the family review's C6; no caller): `spent=` stays, for
  an upstream that answers a spent limit with something other than a 429.
- **The per-config cap and the hook check of `QuotaPolicy.install`** (the family
  review's C6): `install` no longer binds the pause to each config's `retry.backoff_max`
  through a hook of its own, nor refuses with `ValueError` a config that has a
  `before_request` or `observe` hook of its own; `pause_cap=None` and the 30 s of a
  `before_request` called directly go with them (Changed, breaking, below).
- **The recorder's substring credential pattern** (the family review's C10, one
  redaction rule; ADR-0005 and ADR-0019, amendments 2026-10-27; found in the Eurostat
  design round, ADR-0019's context: its SDMX series `key` would have been redacted):
  `scrub_params`, `scrub_url` and every recording no longer redact a query parameter
  whose name merely contains `key`, `pass`, `auth`, `sig`, `cred`, `token` or `secret`
  (`keyword`, `passport`, `author`, `design`); they read the whole-word rule of
  `xippios.core.redaction` (Changed, breaking, below).
- **`is_credential_key` and `redact_credentials` leave `xippios.core.models`** (the
  family review's C10; ADR-0023, decision 5; no consumer): the rule's functions live in
  `xippios.core.redaction`, as `is_credential_name` and `redact_credentials`.
  `xippios.core.models.REDACTED` stays.
- **`render_str_enums` and `render_int_enums`, with the renderers' ruff layout** (the
  family review's C7, a renderer that leaves the layout to ruff; ADR-0008, amendment
  2026-10-27; ADR-0023, decision 5; found by sdk-comtrade and by sdk-template):
  `render_enums` (Added, below) replaces both. The quote choice, the parenthesised and
  split long values, `__all__` sorted as RUF022 sorts it, the wrapped docstrings and the
  refusal of a member name too long for a line go: the refresh script's `ruff format`
  and `ruff check --fix` do that work. Every source re-renders `enums.py` at its
  adoption through the template's script.
- **The testing plugin's patches of httpx's transports** (the family review's C11, the
  network guard on the connection pools only; ADR-0013, amendment 2026-10-27):
  `httpx.HTTPTransport.handle_request` and
  `httpx.AsyncHTTPTransport.handle_async_request` are no longer patched (Changed,
  below).
- **`Tenants` and `list_task` move to sdk-cashctrl** (the family review's C8, the
  multi-tenant pieces with one consumer out of core; ADR-0024, superseding ADR-0014's
  decisions 1 to 4, 6 and 11; Johannes's decision of 2026-10-25 that sdk-cashctrl stands
  alone; found by sdk-cashctrl): `xippios.core.tenants` is deleted and `Tenants` leaves
  `xippios.core`'s export list. The last commit that holds the code is
  `cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff` on `main`, named in `docs/handover.md`'s
  "Adopting core 0.3.0" section:
  `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/tenants.py`,
  tested in `tests/test_tenants.py`. `ResultMeta.tenant` stays.
- **`TenantLock` moves to sdk-cashctrl** (the family review's C8; ADR-0024, superseding
  ADR-0014's decision 7; found by sdk-cashctrl): `build_server` and `register_tasks`
  lose `tenant_lock=`, and the lock's middleware, the refusal of a tenant parameter with
  a default on a locked server, the instructions sentence and the narrowing of a
  `list_task` tool go with it. At that commit: `src/xippios/core/mcp/server.py`
  (`TenantLock`, `_lock_middleware`, `_check_lock`, `_defaulted`, `_declares`,
  `_refusal`, `_lock_sentence`, `_only_the_locked_tenant`, the `narrow` argument of
  `_as_tool`), tested in `tests/mcp/test_lock.py`. `TenantLock` leaves
  `xippios.core.mcp`'s export list. The `confirm` check, `is_write_server`, `main`'s
  loopback rule and option hooks, and `mcp_call` and `mcp_call_text` stay.
- **`assert_write_tools` moves to sdk-cashctrl** (the family review's C8; ADR-0024; the
  write checks found by sdk-cashctrl): with `_tool_names` and `_serves`, at that commit
  in `src/xippios/core/testing/adapters.py`, tested in `tests/testing/test_adapters.py`;
  it leaves `xippios.core.testing`'s export list, and the family check's write-server
  test, which called it, goes (Changed, below).
- **`Scrub(host=...)`, `Scrub(rewrite=...)`, the percent-encoded matching of secrets and
  the JSON-decoded verify move to sdk-cashctrl** (the family review's C9, the recorder's
  extras with one consumer out of core; ADR-0024; ADR-0023, decision 3 (b): a recorder's
  pre-write hooks are the source's; found by sdk-cashctrl): `host` with its checks and
  the placeholder it wrote into the URL, the headers and the bodies, `rewrite`,
  `_plain_or_encoded`, the host forms, `_json_strings` and `_strings`. At that commit:
  `src/xippios/core/testing/scrub.py`, tested in `tests/testing/test_scrub.py`,
  `tests/testing/test_fixtures.py` and `tests/testing/test_record_replay.py`. With the
  three names above, the five export lists hold 41 names in `xippios.core`, 18 in
  `xippios.core.client`, 7 in `xippios.core.mcp`, 3 in `xippios.core.http` and 19 in
  `xippios.core.testing`: 88 entries, 74 names.

### Changed (breaking)

- **`pause_cap` is the one bound of a quota pause** (the family review's C6; ADR-0010,
  decision 4, and ADR-0015, amended 2026-10-27): 30.0 by default, the default
  `backoff_max`, whether `before_request` runs as the hook or is called directly; a
  config's `retry.backoff_max` bounds the retries alone.
- **`QuotaPolicy.install(config)` sets the policy's own hooks** (the family review's
  C6): `dataclasses.replace(config, before_request=policy.before_request,
  observe=policy.observe)`, reading nothing else from the config. Hooks the config had
  are replaced; a source that needs hooks of its own as well composes them itself.
  Installing again changes nothing. Since the hook is `before_request` itself, a
  subclass's override is called through it; the testing plugin still turns off the pause
  step alone.
- **`key` is a credential only where a `QueryKeyAuth` sends it** (the family review's
  C10; ADR-0019, decision 6, amended 2026-10-27; found in the Eurostat design round,
  ADR-0019's context). The one rule of `xippios.core.redaction` names credentials by
  whole words between `_`, `-` or the ends: `api_key` (`apikey`, `api-key`), `token`,
  `secret`, `password`, `passwd`, `pwd`, `auth`, `authorization`, `sig`, `signature`,
  `credential`, `credentials`, and no bare `key`; `sig` and `pwd` are new, for
  pre-signed file links (an Azure SAS carries `sig=`). `QueryKeyAuth(param, ...)`
  registers `param` when it is built, a credential from then on in the whole process, in
  any letter case. USDA NASS's `QueryKeyAuth("key", ...)` keeps its `key` redacted;
  Eurostat, keyless, keeps its SDMX `key` as data; a `sort_key` is data everywhere. A
  process that imports both redacts `key` for both.
- **One rule for the envelope, the recorder and replay** (the family review's C10;
  ADR-0005, amended 2026-10-27): `ResultMeta.request`, the recorder's scrub,
  `sent_urls`, `sent_query`, `recorded_query` and `mount_fixture` read
  `xippios.core.redaction`; `scrub_params`, `scrub_url` and `scrub_headers` move there
  (the header list unchanged) and stay importable from `xippios.core.testing.scrub`;
  `models.REDACTED`, `testing.REDACTED` and `redaction.REDACTED` are one object.
  `recorded_query` reads the recorded URL through `scrub_url` again, and `match_params`
  naming a credential is refused by name ("names a credential, which a fixture holds as
  REDACTED") before its value is looked at.
- **`ResultMeta` refuses a field it does not define** (ADR-0012, amendment 2026-10-27;
  found by sdk-cashctrl): `extra="forbid"`, so a misspelt `totl=3` raises pydantic's
  `ValidationError` ("Extra inputs are not permitted") instead of losing the count
  without a word. The model is otherwise as it was, not frozen.
- **`meta.request` omits a parameter left `None`** (ADR-0022, rule 3; found by
  sdk-usda-psd): `ResultMeta` drops a top-level `None` at construction, before the
  credential rule, so a task passes its parameters as they are and a credential left
  `None` is not recorded as sent; a `None` inside a nested mapping is kept as given.
- **Parse failures print no payload** (conventions §5: errors never leak tracebacks;
  found by sdk-cashctrl in a live test's traceback): `parse`, `UpstreamModel.project`,
  `load_table`, `PackagedList.load`, `decode_json`, `decode_text` and `decode_csv` build
  their `ValidationError` and raise it `from None` through a private helper whose frame
  holds the error alone. The text folds in the cause's location, error type and message
  (`example get_thing: 1 validation error(s); first at 1.value (float_parsing): Input
  should be a valid number, ...`), json's message and position, the decoder's reason or
  the csv module's message, never an input value; the payload stays on `raw`, and the
  error's `repr` is its message. So neither pydantic's chained error, whose text quoted
  every failing value, nor the raising frame's arguments reach a printed traceback:
  under pytest's default `--tb=auto` the function that holds the payload is a middle
  entry, printed short. `project`, `load_table` and `PackagedList.load` raised
  pydantic's own `ValidationError` before and raise the taxonomy's now. The template's
  `--tb=short` on the live run stays as a second guard.
- **Core's recording verify is plain** (the family review's C9; Johannes's decision of
  2026-10-27; ADR-0024, decision 3; ADR-0005, amended 2026-10-27): `Scrub(secrets=...)`
  replaces each value as given, the longest first, in the letter case given, and before
  anything is kept or written the verify searches the URL, every header value and both
  text bodies for each value as given. A hit refuses the exchange with "the scrubbed
  fixture still holds a secret value in the <location>; it is refused before anything is
  written", the location `request URL` (it read `url`), `request header '<name>'`,
  `response header '<name>'`, `request body` or `response body`, never the value. A
  value percent-encoded or behind a JSON escape is no longer found by core, and header
  names are scrubbed but no longer searched.
- **The binary-body refusal is neutral** (ADR-0024, decision 5; found by sdk-cashctrl):
  "a binary body cannot be scrubbed; the recording is refused unless
  Scrub(allow_binary=True) stores it base64, flagged", which no longer tells every
  caller to pass the flag.
- **Arguments a tool's schema refuses are answered in conventions §8's form** (ADR-0014,
  amendment 2026-10-27; found by sdk-usda-esr): `register_tasks`, and `build_server`
  through it, installs one middleware per server that validates a call's arguments with
  the argument model the `mcp` SDK builds for the tool and answers a refusal before the
  tool runs as `error: InvalidRequestError: <argument>: <message>`, the first error with
  the count when there are several. The SDK answered an MCP error, `Error executing tool
  ...` with pydantic's text, its URL and the input value. The SDK runs
  `server.middleware` outermost-first, so a source's own middleware appended later runs
  inside the check, and one placed ahead of it in the list runs first; task errors keep
  their path. A family invariant (ADR-0023, decision 3 (a)).
- **A capped list says where to resume** (ADR-0016, amendment 2026-10-27; found by
  sdk-cashctrl): `cap_result` ends the note of a cut list whose `meta.request` records
  an integer `start`, an offset-paged task's, with `; resume with start=<start +
  shown>`; every other note is unchanged.

### Added

- **`BODY_LIMIT`, `error_from_response` and `parse_retry_after` exported from
  `xippios.core`** (the family review's C5; ADR-0023, decision 5: a name keeps or gains
  its export when a consumer imports it): sdk-cashctrl imports the first two from
  `xippios.core.errors`, and sdk-usda-psd, then sdk-usda-esr and sdk-usda-gats, the
  third. The module path keeps working.
- **`xippios.core.data_gov`, the api.data.gov gateway module** (the family review's C14,
  one module for the gateway three sources copied; ADR-0009, amendment 2026-10-27;
  ADR-0023; found by sdk-usda-psd and by sdk-usda-gats). `Gateway(source)` gives `auth`,
  a `HeaderKeyAuth` on `X-Api-Key` from `DATA_GOV_API_KEY` with the source's slug for
  its `ConfigError`; `classify(response)`, the gateway's `API_KEY_*` answer to a 401 or
  403 as `AuthError`, its 429 as `RateLimitError` and its `NOT_FOUND` 404 as
  `NotFoundError`, in the source's name with the gateway's URL written `<host>`, and
  `None` for every other answer; and `install(config)`, the hooks of `Gateway.policy`,
  one `QuotaPolicy` per process on `x-ratelimit-limit` and `x-ratelimit-remaining` with
  a one-hour window, which every source in the process shares. The policy's refusal
  before sending speaks for `api.data.gov` and names the variable. `API_KEY_ENV`,
  `KEY_HEADER`, `WINDOW`, `LIMIT_HEADER` and `REMAINING_HEADER` come with it. Consumers:
  sdk-usda-psd, sdk-usda-esr and sdk-usda-gats, which carry the same code as copies
  today, and the template's api.data.gov gateway answer of v0.3.0. Imported from its
  module; `xippios.core` does not re-export it.
- **`AsyncClient.download(url, dest, *, auth=)` and `Downloaded`** (the family review's
  C15, bulk downloads and non-JSON payloads; ADR-0019, decision 1; found by
  sdk-usda-nass): a GET through the client's pool, streamed to a temporary file beside
  `dest` and renamed when complete, removed on any failure, never cached and never held
  in memory. `before_request`, the limiter, `observe` and `classify` (both see a
  success's status and headers only; its body goes to the file unread) and the retry
  rule of ADR-0011 apply as for `get()`, a retry restarting the file; an error answer is
  read up to `BODY_LIMIT` bytes and raised through the taxonomy; a 1xx or 3xx raises
  `UpstreamError`, since redirects are not followed; a `dest` that is a directory, or
  whose directory does not exist, is refused with `ValueError` before anything is sent.
  `Downloaded` carries `path`, `bytes`, `content_type`, `filename` (from
  `Content-Disposition`), `etag`, `last_modified` (the header's text) and
  `retrieved_at`; exported from `xippios.core` and `xippios.core.client`. Consumers,
  named by ADR-0019: sdk-usda-esmis, sdk-usda-wasde, sdk-usda-nass's bulk datasets,
  sdk-eurostat and sdk-faostat.
- **`decode_text` and `decode_csv`** (the family review's C15; ADR-0019, decision 2,
  amended 2026-10-27; found by sdk-usda-nass), exported from `xippios.core.client`
  beside `decode_json`: the text in the `Content-Type` charset, UTF-8 by default, a byte
  order mark stripped; and `decode_csv(data, *, delimiter=",", source=None)`,
  `csv.DictReader` rows from a downloaded file (a `Path` or `str`) or a response,
  headers as upstream prints them, a generator that reads a file row by row and closes
  it when it ends.
- **`ClientConfig.cache_max_bytes`** (the family review's C15; ADR-0019, decision 3;
  found by sdk-usda-nass): 8 MiB by default; a larger body is returned and not stored; a
  value below 1 is refused.
- **`BULK_TASKS`** (the family review's C15; ADR-0019, decision 4; found by
  sdk-usda-nass): `register_tasks` and `router_from_tasks` skip a task whose defining
  module names it in `BULK_TASKS`, so the rendered adapters may pass `tasks.__all__`
  whole, and the family check's "`tasks.__all__` minus `BULK_TASKS`" holds for them; a
  cap in `caps` for a bulk task is refused as naming no task, and the refusal now says
  that a task in `BULK_TASKS` is no tool.
- **The recorder's `max_bytes=`** on `record`, `record_sync` and `fixture_from_response`
  (the family review's C15; ADR-0019, decision 5, amended 2026-10-27; found by
  sdk-usda-gats, and the family's finding that a cut-off JSON object, a JSON-stat cube,
  does not decode on replay): a JSON array is cut at an element boundary of its original
  text, its numbers and spacing as upstream wrote them; a text is cut at a UTF-8
  character boundary, never inside a secret value; a JSON object, a body declared JSON
  that does not parse, an array whose first element alone does not fit, a cut that keeps
  nothing, XML, ZIP, XLSX, gzip, XLS and a body that is not UTF-8 text are refused with
  the reason. `max_bytes` bounds the body, not the fixture file, which escapes the body
  as a JSON string. A cut response is marked `truncated` with `original_bytes`, `sha256`
  (of the whole body, before the scrub) and, for an array, `original_count`, new
  optional fields of `FixtureResponse`; a fixture without a cut is written without them,
  so every existing fixture loads and re-records unchanged. Replay serves the body as
  recorded.
- **`xippios.core.redaction`** (the family review's C10; ADR-0019, decision 6; ADR-0023,
  decision 3 (b), credential redaction; found in the Eurostat design round): the one
  `REDACTED`, `is_credential_name`, `register_credential_name`, `redact_credentials` and
  the three `scrub_*` functions, at the bottom of the package. Imported from its module;
  not re-exported.
- **`ResultMeta.published_at_naive`** (ADR-0022, rule 2; found by sdk-usda-gats): a
  naive `published_at`, a release time upstream printed without a zone (FAS:
  `2026-10-06T08:00:00`), is kept as given with the flag set; without the flag it is
  refused as before, and the flag with an aware `published_at` or with none is refused
  too. The HTTP envelope and the MCP text carry it. A family invariant (ADR-0023,
  decision 3 (a)); sdk-usda-esr and sdk-usda-gats fill it at adoption.
- **`PackagedList`** (the family review's C13, one packaged-list class for the sources'
  copies; ADR-0022, rule 1 and amendment 2026-10-27; found by sdk-usda-psd, by
  sdk-usda-esr in the template's scaffold, and by sdk-usda-gats), in
  `xippios.core.reference` and exported from `xippios.core`: one frozen model,
  `PackagedList(param, endpoint, fetched, records)` with an optional free-text `note`,
  for a list fetched from one upstream operation, upstream's records under upstream's
  field names, a list of values being records of one field named by the upstream
  parameter; any other key of a file is refused. `PackagedList.load(package, name)`
  reads `reference/<name>.json` through `load_json` (`name` with or without `.json`);
  `.meta(source, *, request, vintage, published_at, published_at_naive)` builds rule 1's
  `ResultMeta` (`endpoint` the list's operation, `retrieved_at` its `fetched`, `vintage`
  only what the caller passes, `total` `None`); `.parse(model, *, source)` validates the
  records through `parse`; `.write(path)` writes the file (`{"param", "endpoint",
  "fetched", "records"}` and `note` when it is set, indented, non-ASCII text kept,
  `fetched` to the second as `...Z`) for the refresh scripts. Consumers: sdk-usda-psd,
  sdk-usda-esr and sdk-usda-gats, which carry copies, sdk-usda-nass and sdk-comtrade,
  whose value files and tables it reads after their adoption, and the template's refresh
  script.
- **`matches` and `closest`** (the family review's C13; found by sdk-usda-psd and
  sdk-usda-gats), in `xippios.core.reference` and exported from `xippios.core`:
  `matches(search, *fields)`, the `search` filter of the `list_*` tasks (`None` matches
  everything; otherwise a case-folded substring test of each field that is not `None`,
  as text, never joined), and `closest(value, codes, *, n=3)`, sdk-usda-psd's two
  `difflib` passes, by code and then by name, at most `n` `(code, name)` pairs.
  Consumers: sdk-usda-psd, sdk-usda-esr, sdk-usda-gats and sdk-comtrade (`matches`);
  sdk-usda-psd and sdk-usda-gats, the latter behind its three-letter pass (`closest`;
  sdk-usda-esr's is integer-nearest and stays its own).
- **`UnknownCode`** (ADR-0022, amendment 2026-10-27; found by sdk-usda-gats), an
  `InvalidRequestError` in `xippios.core.errors`, exported from `xippios.core`:
  `UnknownCode(param, value, *, list_name, fetched, closest=(), hint=None, reason=None,
  source=None)` refuses a code a packaged list lacks with the copies' common message:
  the value, the parameter, the list and the day it was fetched, "Did you mean A (name),
  B (name)?" from `closest` unless `hint` is given, the `reason`, and that a code
  upstream added since needs a refresh (`/refresh-reference-data`). Attributes `param`,
  `value`, `list_name`, `fetched`, `closest`. No strategy protocol: a source passes the
  closest codes it found. Consumers: sdk-usda-psd, sdk-usda-esr and sdk-usda-gats.
- **`AsyncClient.get_answer(path, *, params, headers, auth)` and `Answer`** (ADR-0015,
  decision 5, amended 2026-10-27; found by sdk-usda-gats): the payload as `get_json`
  decodes it and `retrieved_at`, a cache hit's stored time from
  `xippios_cache_stored_at` as an aware UTC datetime, else the time the answer arrived.
  `Answer(payload, retrieved_at)` is a frozen dataclass, exported from `xippios.core`
  and `xippios.core.client`; `get_json` stays. Consumers: sdk-usda-gats's five cached
  wrappers and sdk-comtrade's cached `list_commodities`.
- **`UpstreamModel.dump_upstream()`** (ADR-0003; found by sdk-template): a record as
  `model_dump(mode="json")` under upstream's field names, the `serialization_alias`,
  else a string `validation_alias`, else the first choice of an `AliasChoices`, else the
  field name; a nested `UpstreamModel`, alone or in a list, likewise; a computed field,
  which is the package's, left out. Consumers: the refresh scripts of sdk-usda-psd,
  sdk-usda-esr, sdk-usda-gats and the template (`upstream_record`), and sdk-comtrade's
  tables (`_columns`).
- **`render_enums(lists, *, fetched, class_names=None, member_names=None,
  generator=...)`** (the family review's C7; ADR-0008, amendment 2026-10-27; found by
  sdk-template and, for the class docstrings, by sdk-usda-gats), in
  `xippios.core.reference`: one module of `StrEnum` and `IntEnum` classes, the kind
  inferred per list, a list of strings or of `(id, name)` pairs as `id_name_pairs`
  builds them; `fetched` one date for the module or one per list; each class docstring
  one line, "Values of ``<key>`` (fetched <date>).", which an MCP tool's input schema
  shows the agent. The output is plain ASCII: values as `ascii()` writes them, one
  member per line, `__all__` in the order of the lists, `# noqa: E501` on a line over
  100 columns, `# noqa: E741` on a member named `I`, `O` or `l`. Refused with
  `ValueError`: an empty list or one that mixes kinds (the message names what it found,
  by type); a key, class name, date or generator text that is not printable ASCII; a
  class name over 84 characters, named `IntEnum` or `StrEnum`, or shared by two lists; a
  repeated id; a member name with nothing to derive it from, or one that collides or an
  enum cannot take; and a key of `fetched`, `class_names` or `member_names` that `lists`
  does not hold. Consumers: every source, through the template's refresh script
  (ADR-0023, decision 1).
- **Every `MemoryCache` cleared around each offline test** (ADR-0013, amendment
  2026-10-27; found by sdk-usda-gats; sdk-comtrade carries the same fixture): a
  `MemoryCache` adds itself to a module-level weak set when it is built, and the
  plugin's autouse fixture clears every registered cache before and after each test not
  marked `live`, next to the quota reset. A `CacheBackend` of the source's own is not
  cleared; the `MemoryCache`s one holds are.
- **The quota a live run left** (ADR-0013, amendment 2026-10-27; found by sdk-usda-esr):
  after each `live` test that ran the plugin keeps every quota policy's source and
  `snapshot().describe()`, and the terminal summary prints one line per policy with a
  reading, `quota after the live run: <source>: <describe()>`: times, counts and the
  source, never a key, a host or a query.

### Changed

- **The api.data.gov 429's wait comes from the quota snapshot** (the family review's
  C14, the gateway module; found by sdk-usda-psd): the gateway's `classify` counts to
  `Gateway.policy.snapshot()`'s `resumes_at` on the policy's clock, since `observe` ran
  before it, instead of restating "`Retry-After`, else the window" as the three copies
  did; no `QuotaPolicy.wait_for` is added. Its message names the gateway's allowance,
  that every package using the key shares it, and the quota as the snapshot reports it,
  or the wait in seconds where no snapshot shows it spent, and no longer says what was
  retried: the retry loop's bound decides that.
- **`ResultCap` is defined in `xippios.core.models` and exported from `xippios.core`**
  (the family review's C5; the per-tool cap of ADR-0016; found by sdk-usda-psd): a
  source's `tasks.py` declares its `MCP_CAPS` without the `mcp` extra and without the
  `ImportError` guard around the import. `xippios.core.mcp` keeps re-exporting it, and
  `cap_result` stays there.
- **A packaged answer's `retrieved_at` is the list's fetch time, read from `fetched`**
  (ADR-0022, rule 1 and amendment 2026-10-27; found by sdk-usda-psd):
  `PackagedList.fetched` is a timezone-aware UTC time, and a file whose `fetched` is a
  bare date, every packaged file so far, reads as 00:00 UTC of that day, the start of
  the day the refresh scripts truncated the time to; a source's next refresh writes the
  full time. The sources answered with the time of the call and put the fetch date into
  `vintage`, which now holds an upstream release identifier only.
- **The network guard sits on httpcore's connection pools only** (the family review's
  C11; ADR-0013, amendment 2026-10-27): `httpcore.ConnectionPool.handle_request` and
  `httpcore.AsyncConnectionPool.handle_async_request`, which every default httpx
  transport sends through, proxies included. The refusal, its message and its edges are
  unchanged: respx answers a mocked request, a route that passes through meets the
  refusal, and a transport a test passes itself bypasses it. The plugin's docstrings
  name the decision of ADR-0013 they implement instead of restating it, and the
  `rate_limited` marker's text names the quota pause it keeps as well.
- **The family check has ten tests** (the family review's C8; Johannes's decision of
  2026-10-27; ADR-0024): `test_family_write_server_serves_the_write_tasks` is gone, and
  a source's write server is its own to test. The write tasks of `tasks_write` stay in
  `test_family_tasks_return_results`, `test_family_tasks_carry_agent_docstrings` and the
  README status table.
- **`.claude/settings.json`** (ADR-0018, amendment (e); found by sdk-template, which
  copies the file verbatim): `gh pr merge --auto` is allowed and `gh pr merge` is no
  longer denied, as in the workspace root's settings. A deny shadows every allow, so the
  session's one merge action, enabling auto-merge (ADR-0018, amendment (e)), was refused
  here.
- **`gates.yml` calls the gates repository under its new name `xippios/sdk-gates`**
  (ADR-0018, amendment (e): the merge classes it calls for; the repository was renamed
  from `.github` on 2026-10-27).

### Documentation

- **ADR-0002, amendment 2026-10-27**: `pydantic-settings` and `xippios.core.config` are
  gone, keys are read by the `EnvKeyAuth` helpers, and the sync facade is
  `xippios.core.sync`.
- **ADR-0015, amended 2026-10-27**: the sync `Client`, `UseClientDefault` and `derive`
  leave decisions 2 and 4 and the consequences; `QuotaSnapshot` is importable from
  `xippios.core.client.quota`. **ADR-0004** and **ADR-0009** get a line each for the
  deleted `config` module and `resolve_api_key`, and **ADR-0012** one for the
  paginators, of which `paginate_offset` remains.
- **Conventions 1.16**: §7 reads the environment through the `EnvKeyAuth` helpers.
- **ADR-0009, ADR-0010 and ADR-0015, amended 2026-10-27**: the gateway module as the
  code side of one key per issuer; the quota pause bounded by `pause_cap`; the removals
  of the family review's C6, `install`'s contract and the 429's wait read from the
  snapshot. **ADR-0016** gets a dated line: a subclass's override of `before_request` is
  called through the hook `install` sets.
- **Conventions 1.17**: §6 bounds the quota pause by the policy's `pause_cap` and says
  that `install` replaces the config's hooks; §7 names `xippios.core.data_gov` for the
  sources behind api.data.gov.
- **ADR-0019, amendment 2026-10-27**: decision 1's `auth=` default is the client's own
  credentials, and what differs from `get()` (the hooks see a success's headers only, a
  1xx or 3xx raises, `dest` refused before sending); decision 2's `decode_csv(data,
  ...)`; decision 5's one `max_bytes=` for texts and arrays, the cut at element
  boundaries, the JSON-object refusal and the XML reason ("a cut-off XML document is not
  well-formed"); decision 6's mechanism and the words `sig` and `pwd`. **ADR-0005** (the
  list without a bare `key`, no second pattern for fixtures), **ADR-0013** (the guard
  covers `download`; replay of a cut body) and **ADR-0004** (`redaction` and `_tasks` at
  the bottom, `client/download.py`) get a dated line each.
- **Conventions 1.18**: §4 states the one rule, every word of it, and when `key` is a
  credential; §6 that a download's hooks see a success's headers only, that a 1xx or 3xx
  raises, and `decode_csv`'s signature; §10 the scrub's rule, the JSON-object refusal,
  the XML reason, the cut at element boundaries, `original_count`, and that `max_bytes`
  bounds the body, not the file.
- **ADR-0022, amendment 2026-10-27**: the five decisions on the code (the `fetched` time
  and its bare-date reading; one `PackagedList` with value lists as one-field records
  and a URL path as `endpoint`; the helpers; `get_answer`; frozen series), the flag's
  refusals, the order of the `None` rule and the credential rule, and three more from
  the review of the code: the period series, found by sdk-usda-gats (the ceiling is the
  most periods one call fetches; an unreleased period is skipped where upstream's empty
  answer can be told from data, else the range is refused), its refusal as
  `NotFoundError` naming the latest released period, and the packaged file's optional
  `note` with every other key refused. **ADR-0015** (decision 5's `get_answer`),
  **ADR-0012** (`ResultMeta` refuses unknown fields) and **ADR-0004** (`reference` above
  `models`) get a dated line each.
- **Conventions 1.19**: §3 the packaged-list file, `reference/<name>.json` with its
  optional `note`; §4 the refusal of unknown fields, `get_answer` for a hit's
  `retrieved_at`, the flag's refusals, `PackagedList`'s methods and the bare-date
  reading, `matches`, the frozen series and the period series (both found by
  sdk-usda-gats); §5 `UnknownCode`, in the taxonomy tree under `InvalidRequestError`; §6
  `get_answer`. The preamble lists these among the rules that bind a source from its
  0.3.0 adoption.
- **ADR-0008, amended 2026-10-27**: `render_enums` replaces the two renderers, the plain
  output and the refresh script's ruff step replace the amendment of 2026-10-24's
  layout. **ADR-0013** (the guard on the pools, the cache clearing, the live summary),
  **ADR-0014** (the argument middleware), **ADR-0016** (the resume hint) and
  **ADR-0018** (amendment (f), the workflow hardening) get a dated line each.
- **Conventions 1.20**: §3 `render_enums` and the module committed as formatted; §8 what
  an enum's class docstring holds (found by sdk-usda-gats), the resume hint and refused
  arguments as `InvalidRequestError` text; §10 the guard on the pools, the cache
  clearing and the live summary; §13 the workflow hardening (the family's own finding):
  actions pinned by SHA, no persisted credentials but the `tag` job's, least
  permissions, no `secrets: inherit`, the gates called at `@main`; §15 item 6 re-renders
  through the template's script. The header binds the renderer rule from the 0.3.0
  adoption.
- `publish.yml`'s `tag` job says in a comment that its checkout keeps its credentials,
  since it pushes the tag with the token (conventions §13; ADR-0018, amendment (f)).
- The definition of done's adoption line and its copy in
  `.github/PULL_REQUEST_TEMPLATE.md`: generated enum files are committed as formatted,
  after the refresh script's `ruff format && ruff check --fix`, as conventions §15 item
  6 says (ADR-0008, amendment 2026-10-27).
- **ADR-0024**: sdk-cashctrl stands alone; tenants, the tenant lock,
  `assert_write_tools` and the recorder's host placeholder, encoded matching, JSON
  verify and `rewrite` leave core, while `ResultMeta.tenant` (a family invariant,
  ADR-0023, decision 3 (a)), the `confirm` check and the loopback rule (conventions §8,
  C8) and the plain verify (secret scrubbing, decision 3 (b)) stay. **ADR-0014** is
  superseded in part (decisions 1 to 4, 6, 7 and 11, and two consequences: the
  template's `multi_tenant` question and `tests/mcp/test_lock.py` as the middleware
  API's guard; 5, 8, 9 and 10 stand); **ADR-0005** (the verify's scope), **ADR-0013**
  (the placeholder host, the verify's forms and the family check's write-server test),
  **ADR-0017** (`rewrite`), **ADR-0019** (the text cut spares secrets only) and
  **ADR-0023** (which of "the write checks" left) get a dated line each. The template's
  `multi_tenant` question ADR-0014 announced (asked for by sdk-cashctrl) is not built.
- **Conventions 1.21**: §1 names a multi-tenant source's key variables as its own
  scheme; §3 makes the rewrite by key the source's recorder step; §7 has a multi-tenant
  source carry its tenant registry and keep `ResultMeta.tenant`; §8 loses the tenant
  list and the lock and keeps the write server's rules; §10 loses the placeholder host
  and the JSON-aware verify, keeps the plain verify and `allow_binary`, and the family
  check no longer names the write server.

### Hand-apply for sources

What a source's adoption of 0.3.0 changes by hand because of the changes above, per
source: every source first, then each by name. Of the names this release deletes, the
sources import the two renderers, in their refresh scripts; sdk-cashctrl imports the
names that move to it. The tests of the api.data.gov sources read a deleted attribute
and texts that change, and every source's tests meet the narrower credential rule.
`docs/handover.md`, "Adopting core 0.3.0", walks the same items through conventions §15.

#### Every source

- `tests/` — a test that expected a name without a credential word redacted (a
  whole-word `key` its own `QueryKeyAuth` does not send, `sort_key`, or a substring
  match such as `keyword` or `author`), in `meta.request`, `sent_urls`, `sent_query` or
  a newly recorded fixture, now sees the value → assert the value; a fixture recorded
  with the substring rule keeps `REDACTED` for such a name, so a `sent_query(route) ==
  recorded_query(fixture)` comparison differs on it until the fixture is re-recorded; a
  test that matched the text "was recorded as REDACTED" for a credential named in
  `match_params` → "names a credential"; a parameter whose name has the whole word `sig`
  or `pwd` now reads `REDACTED` — one redaction rule (C10).
- `tests/` — a `ResultMeta(...)` given a field it does not define now raises: name the
  field right — ADR-0012, amendment 2026-10-27.
- `tests/` — a test that asserted the SDK's answer to an argument the schema refuses
  (`Error executing tool ...`, `is_error`, `mcp_call_text` failing) → the text `error:
  InvalidRequestError: <argument>: <message>` through `mcp_call_text`; `mcp_call` still
  raises `AssertionError` on it — ADR-0014, amendment 2026-10-27.
- `tests/` — a test that matched `parse`'s text "first at <loc>: <msg>" → "first at
  <loc> (<type>): <msg>"; one that read pydantic's error from `__cause__` finds `None`;
  one that expected pydantic's `ValidationError` from `load_table`, `project` or
  `PackagedList.load` expects `xippios.core.errors.ValidationError` — parse failures
  print no payload.
- `scripts/refresh_reference.py` (every source with a generated `enums.py`; the template
  renders it in v0.3.0) — `render_str_enums(...)` and `render_int_enums(...)` → one
  `render_enums(lists, fetched=..., ...)` call, value lists and id lists in one mapping,
  `fetched` one date or one per list, then `ruff format` and `ruff check --fix` on
  `enums.py`, which is re-rendered and committed as formatted — the renderer (C7),
  ADR-0008, amendment 2026-10-27.
- `src/xippios/<pkg>/tasks.py` of a source with a bulk task — `BULK_TASKS =
  frozenset({...})` beside `MCP_CAPS`; `mcp.py` and `http.py` may pass `tasks.__all__`
  whole. Template v0.3.0 renders the `BULK_TASKS = frozenset()` scaffold — bulk
  downloads (C15), ADR-0019, decision 4.
- A source that caches an answer over 8 MiB (none known) — raise
  `ClientConfig(cache_max_bytes=...)` and say why in `CLAUDE.md` — ADR-0019, decision 3.
- The source's own workflows (a `siblings.yml`, a `live.yml` of its own) — checked
  against conventions §13's hardening — ADR-0018, amendment (f).

#### sdk-usda-nass

- `src/xippios/usda/nass/tasks.py` — the `ImportError`-guarded `from xippios.core.mcp
  import ResultCap` → an unguarded `from xippios.core import ResultCap`, and the comment
  that names the `mcp` extra goes — `ResultCap` lives in `xippios.core.models`.
- `src/xippios/usda/nass/tasks.py` and its `reference/*.json` value files — converted,
  without network, to packaged-list files (`{"param", "endpoint", "fetched", "records"}`
  and an optional `note`, a value list as records of one field named by the parameter,
  `fetched` kept as the date it is), `endpoint` the upstream operation,
  `get_param_values`, where nass wrote "reference"; any other key is refused, so nass
  writes its `derived_from` into `note` as text, and its two lists derived from
  `api_GET` records, `condition_categories` and `progress_stages`, keep `param:
  "unit_desc"` and `endpoint: "api_GET"` in files of their own names, which
  `PackagedList.load(package, name)` takes. The list tasks read the files with
  `PackagedList.load` and still return strings — ADR-0022, rule 1 and amendment (2) and
  (8).
- `src/xippios/usda/nass/` — nothing for the credential rule: its `QueryKeyAuth("key",
  ...)` registers `key`, so `meta.request`, `sent_urls`, `sent_query`, `recorded_query`
  and every recording keep `key=REDACTED` — C10.

#### sdk-comtrade

- `src/xippios/comtrade/tasks.py` — `_packaged_meta` and `_matches` →
  `packaged.meta(SOURCE, request=...)` and `matches`; `meta.vintage` becomes `None` and
  `meta.retrieved_at` the list's `fetched`, so the list tasks' docstrings that say
  "``meta.vintage`` is the day the package fetched the list, ``meta.retrieved_at`` when
  this task answered" and the tests that assert it change — ADR-0022, rule 1.
- `src/xippios/comtrade/tasks.py`, its `reference/*.json` value files and its CSV tables
  with `reference/tables.json` — converted, without network, to packaged-list files as
  for sdk-usda-nass, `endpoint` the upstream operation,
  `files/v1/app/reference/<file>.json`, where comtrade wrote a file path; comtrade
  writes its `note` and its `exceptions` into `note` as text, and its `origin` becomes
  `endpoint`. The list tasks read the files with `PackagedList.load` and still return
  strings — ADR-0022, rule 1 and amendment (2) and (8).
- `src/xippios/comtrade/tasks.py` — the cached `list_commodities` reads its answer with
  `client.get_answer(...)` for `retrieved_at` instead of `get()` and `decode_json()` —
  ADR-0015, decision 5, amended 2026-10-27.
- `scripts/refresh_reference.py` — `_columns` and `_write_table` →
  `PackagedList(param=..., endpoint=..., fetched=..., records=...).write(path)`, the
  records under upstream's names by `record.dump_upstream()`, `fetched` =
  `datetime.now(UTC)` to the second; `render_enums` takes the fetch day as text
  (`f"{fetched:%Y-%m-%d}"`) — `dump_upstream`, `PackagedList.write`.
- `scripts/refresh_reference.py` and `.claude/commands/refresh-reference-data.md` — the
  per-class rewrite of each docstring with its list's date → `fetched={name: date,
  ...}`; its notes leave the class docstrings, which reach the agent, for the packaged
  list's `note` (`PackagedList(note=...)`); the command's ruff step and its note on the
  renderer's layout go, since the script runs ruff — C7, conventions §8.
- `tests/` — the snapshot count of packaged lists (38) → structure checks (each record
  carries the list's fields; `endpoint` and `fetched` set) — a list's size changes with
  every refresh, and the next one rewrites every file with the full `fetched` time.
- `tests/conftest.py` (`empty_reference_cache`) — deleted: the plugin clears every
  `MemoryCache` around each offline test — ADR-0013, amendment 2026-10-27.
- Its planned `QuotaPolicy(limit_header=None, remaining_header=None, window=86400,
  spent=...)` — nothing: `spent=` stays — C6.

#### sdk-usda-psd

- `src/xippios/usda/psd/tasks.py` — the `ImportError`-guarded `ResultCap` import → `from
  xippios.core import ResultCap`, as for sdk-usda-nass.
- `src/xippios/usda/psd/_client.py` — the gateway block (`API_KEY_ENV`, `policy =
  QuotaPolicy(...)`, `_URL`, `_gateway_error`, `_over_rate_limit`, the `API_KEY_*`, 429
  and `NOT_FOUND` branches of `classify`, `auth = HeaderKeyAuth(...)`) → `gateway =
  Gateway(SOURCE)` from `xippios.core.data_gov`: `classify` returns
  `gateway.classify(response)` when that is not `None` and keeps its own branches after
  it (psd's empty 404), `config = gateway.install(ClientConfig(...))`, `client =
  AsyncClient(config, auth=gateway.auth)`; where the package keeps the names
  `API_KEY_ENV`, `policy` and `auth`, they become `xippios.core.data_gov.API_KEY_ENV`,
  `Gateway.policy` and `gateway.auth`; the `parse_retry_after` import goes when nothing
  else uses it, and may otherwise come from `xippios.core`; the module docstring's
  "waiting within `RetryPolicy.backoff_max`" reads "waiting within the policy's
  `pause_cap`" — the gateway module replaces the copies (C14, ADR-0023), and the pause
  has one cap (C6).
- `tests/test_client.py` — the wiring test drops `policy.reset_header`, which is gone,
  and may assert `config.before_request == Gateway.policy.before_request` next to
  `config.observe == Gateway.policy.observe`; the assertion on "Nothing was retried"
  goes, since the message no longer speaks of retries; a `retry_after` read through the
  client is the snapshot's wait from now, so `== 3151.0` or `== 3600` becomes a bracket
  with `CLOCK_SLACK`, while `classify` called on its own still gives the exact wait; the
  policy's refusal before sending carries `source == "api.data.gov"`, not the slug, and
  starts "api.data.gov quota of the key in DATA_GOV_API_KEY spent" — C6, C14.
- `CLAUDE.md`, the rate-limit row — "within `RetryPolicy.backoff_max` (30 s by default)"
  → "within the policy's `pause_cap` (30 s by default)", and the gateway's key, answers
  and quota named as `xippios.core.data_gov`'s — ADR-0010, decision 4, amended
  2026-10-27.
- `src/xippios/usda/psd/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)` from `xippios.core`; `_codes` reads
  `packaged.records` as before and keeps `packaged.fetched` (a datetime now, not ISO
  text); `_closest` → `closest(value, codes)` — C13, ADR-0023, decision 4.
- `src/xippios/usda/psd/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, with
  `reason=` and `source=SOURCE` at each raise (or a subclass that fills them in); the
  message reads "... in the packaged commodities list (fetched 2026-10-23). ..." and
  ends "If upstream added it since, the packaged list needs a refresh
  (/refresh-reference-data).", so a test that matched "in PSD's commodities list
  (packaged, fetched ...)" or "If PSD added the code since" matches the new text —
  ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/psd/tasks.py` — `_packaged`, `_packaged_meta` and `_matches` →
  `packaged.parse(Model, source=SOURCE)`, `packaged.meta(SOURCE, request=...)` and
  `matches`; `meta.vintage` becomes `None` and `meta.retrieved_at` the list's `fetched`,
  so the list tasks' docstrings that say "``meta.vintage`` is the day the package
  fetched the list, ``meta.retrieved_at`` when this task answered" and the tests that
  assert it change — ADR-0022, rule 1.
- `src/xippios/usda/psd/tasks.py` — nothing for its `None` filters: `meta.request`
  leaves them out by itself; a test that asserted `{"search": None}` sees `{}` —
  ADR-0022, rule 3.
- `src/xippios/usda/psd/tasks.py`, `get_time_series` — nothing; its docstring already
  states its ceiling and that a market year answering PSD's empty 404 is skipped —
  ADR-0022, amendment (6), conventions §4.
- `scripts/refresh_reference.py` — `upstream_record(record)` → `record.dump_upstream()`;
  `write(...)` → `PackagedList(param=..., endpoint=..., fetched=...,
  records=...).write(path)`, `fetched` = `datetime.now(UTC)` to the second;
  `render_enums` takes the fetch day as text (`f"{fetched:%Y-%m-%d}"`); the refusal of a
  value list and an id list together and `--render-only`'s refusal of lists fetched on
  different days go — `dump_upstream`, `PackagedList.write`, C7.
- `tests/` — the snapshot count of packaged lists (42) → structure checks, as for
  sdk-comtrade.

#### sdk-cashctrl

sdk-cashctrl receives what leaves core, copied from the last commit that holds it,
`cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff` on `main`:
`git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:<path>` (ADR-0024). No other source
imports a moved name.

- `src/xippios/cashctrl/_client.py` (the `Tenants` import, `TENANTS = Tenants(...)`,
  `client_for`) — `Tenants` → a module of its own copied from
  `src/xippios/core/tenants.py`; `client_for` keeps its shape. The copy keeps the
  replaced client dropped without closing until cashctrl decides otherwise — C8.
- `src/xippios/cashctrl/tasks.py` (the module docstring's
  `xippios.core.tenants.list_task`, `from xippios.core.tenants import list_task`,
  `list_organisations = list_task(...)`) → the copy's `list_task` — C8.
- `src/xippios/cashctrl/_cli.py`, `src/xippios/cashctrl/mcp.py`,
  `src/xippios/cashctrl/mcp_write.py` — `from xippios.core.mcp import TenantLock` and
  `build_server(..., tenant_lock=...)` → a lock of its own that is a wrapper binding
  `org` on its tools, no middleware, as the family review's C8 has it; ADR-0014's
  decision 7 no longer binds it. From `src/xippios/core/mcp/server.py` the wrapper keeps
  `TenantLock`'s validation of the parameter and the tenant, `_only_the_locked_tenant`
  for the organisation list, and the instructions sentence (`_lock_sentence`) reworded
  for a bound `org`; the middleware's functions (`_lock_middleware`, `_declares`,
  `_refusal`, `_check_lock`, `_defaulted`) have no part in it — C8.
- `tests/test_adapters.py`, which the update from template v0.2.0 deletes
  (`test_the_write_server_serves_write_tasks_only`) — the write-server test moves to a
  test file of cashctrl's own, such as `tests/test_tasks_write.py`, and calls the copy
  of `assert_write_tools`, from `src/xippios/core/testing/adapters.py`, with a check
  that `confirm` is the last parameter, instead of `from xippios.core.testing import
  assert_write_tools`. The family check no longer tests the write server; this test does
  — C8.
- `tests/test_org_lock.py` — follows the wrapper: a call names no other organisation
  than the one the server binds, so the refusal texts it asserts ("this server is locked
  to org=...; the call named another tenant", "...; the call did not name the tenant")
  and the instructions sentence it asserts change with the wrapper;
  `tests/test_registry.py` — against the package's own registry — C8.
- `scripts/record_fixture.py` — `scrub(key)`'s `Scrub(host=REPLAY_HOST, secrets=[...],
  rewrite=scrub_text, allow_binary=False)` → `Scrub(secrets=[...])`, and a step of the
  recorder's own on the `Fixture` that `fixture_from_response` returns, before its one
  write: the host placeholder, the percent-encoded matching and the JSON-decoded verify,
  copied from `src/xippios/core/testing/scrub.py`, and `scrub_text` over the URL, the
  header values and the bodies, so `scrub_request_url` folds into it;
  `redacted_a_secret`, which scrubs again with `Scrub(host=..., rewrite=...)`, compares
  through the same step; `main`'s prefix before core's binary-body refusal meets the new
  text — C9, ADR-0024, decision 4.
- `tests/test_record_fixture.py` — `test_a_key_the_scrub_cannot_reach_is_never_written`
  asserts that core's JSON verify refuses a key behind a JSON escape ("secret value"):
  core no longer decodes, so the recorder's own verify answers it, in its own words;
  `test_a_binary_body_is_refused` matches "binary body cannot be scrubbed" right after
  the recorder's reason → "a binary body cannot be scrubbed; the recording is refused
  unless Scrub(allow_binary=True) stores it base64, flagged";
  `test_nothing_unscrubbed_touches_disk` holds once the recorder replaces the host
  itself — C9.
- `CLAUDE.md` ("Organisations", "How to record a fixture") — the registry,
  `list_organisations` and the `--org` lock as the package's own; the recorder's
  `Scrub(secrets=[key, its basic-auth token])` with its own host, JSON and
  percent-encoded checks; core's verify searches plain values only — ADR-0024.
- `src/xippios/cashctrl/_client.py`, `src/xippios/cashctrl/api/_form.py`,
  `tests/test_errors.py` — `from xippios.core.errors import BODY_LIMIT,
  error_from_response` may become `from xippios.core import ...` — the names are
  exported now; the module path keeps working (C5).
- `src/xippios/cashctrl/_cli.py` — its module docstring names
  `xippios.core.mcp.quiet_request_logging`, which is importable from
  `xippios.core.mcp.server` only → name that path — docstring only, nothing breaks (C5).
- Where it imports `xippios.core.models.REDACTED` and `xippios.core.testing.REDACTED` —
  nothing: both keep working, one object — C10.
- A test that asserted a capped note of an offset-paged list task in full — the note
  ends `; resume with start=<n>` — ADR-0016, amendment 2026-10-27.
- Every task's `ResultMeta(tenant=org)` — nothing: `ResultMeta.tenant` stays — ADR-0024,
  decision 2.

#### sdk-usda-esr

- `src/xippios/usda/esr/tasks.py` — the `ResultCap` import, as for sdk-usda-nass.
- `src/xippios/usda/esr/_client.py` — the gateway block → `gateway = Gateway(SOURCE)`,
  as for sdk-usda-psd, `classify` keeping esr's 400 after `gateway.classify`;
  `parse_retry_after` and the module docstring as there — C14, C6.
- `tests/test_client.py` and `CLAUDE.md`'s rate-limit row — as for sdk-usda-psd — C6,
  C14.
- `src/xippios/usda/esr/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)`, `_codes` as for sdk-usda-psd; esr keeps its
  integer-nearest `_closest` — C13, ADR-0023, decision 4.
- `src/xippios/usda/esr/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, as for
  sdk-usda-psd — ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/esr/tasks.py` — `_packaged`, `_packaged_meta` and `_matches`, as for
  sdk-usda-psd — ADR-0022, rule 1.
- `src/xippios/usda/esr/tasks.py` — `published_at` from its naive release times with
  `published_at_naive=published_at is not None`, since the flag without a time is
  refused; `vintage` keeps the release text as upstream prints it — ADR-0022, rule 2.
- `scripts/refresh_reference.py` — `upstream_record(record)` → `record.dump_upstream()`;
  `render_enums` takes the fetch day as text; the refusal of a value list and an id list
  together and `--render-only`'s refusal of lists fetched on different days go —
  `dump_upstream`, C7.

#### sdk-usda-gats

- `src/xippios/usda/gats/tasks.py` — the `ResultCap` import, as for sdk-usda-nass.
- `src/xippios/usda/gats/_client.py` — the gateway block → `gateway = Gateway(SOURCE)`,
  as for sdk-usda-psd; `parse_retry_after` and the module docstring as there — C14, C6.
- `tests/test_client.py` and `CLAUDE.md`'s rate-limit row — as for sdk-usda-psd — C6,
  C14; the autouse cache-clearing fixture of `tests/test_client.py` — deleted: the
  plugin clears every `MemoryCache` around each offline test — ADR-0013, amendment
  2026-10-27.
- `tests/test_tasks.py`, the 429 test of `get_census_export_series` —
  `info.value.retry_after == 3151.0` is read through the client, so it becomes the
  snapshot's wait, a fraction under 3151: bracket it with `CLOCK_SLACK` — C14.
- `src/xippios/usda/gats/params.py` — the `PackagedList` class and `packaged_values` →
  `PackagedList.load(PACKAGE, name)`, `_codes` as for sdk-usda-psd; gats keeps its
  three-letter pass in front of `closest` and its `_nearest` and `_sharing_digits` —
  C13, ADR-0023, decision 4.
- `src/xippios/usda/gats/errors.py` — `UnknownCode` → `xippios.core.UnknownCode`, as for
  sdk-usda-psd; gats passes its example codes as `hint=` only when `closest` is empty,
  since a `hint` wins over `closest` — ADR-0022, amendment 2026-10-27.
- `src/xippios/usda/gats/tasks.py` — `_packaged`, `_packaged_meta` and `_matches`, as
  for sdk-usda-psd — ADR-0022, rule 1.
- `src/xippios/usda/gats/api/` — the five wrappers that return `(records, stored_at)` →
  `client.get_answer(path)`, its `retrieved_at` the task's `meta.retrieved_at` on a hit
  and a miss alike; `_client.stored_at` goes — ADR-0015, decision 5, amended 2026-10-27.
- `src/xippios/usda/gats/tasks.py` — `published_at` with `published_at_naive`, as for
  sdk-usda-esr — ADR-0022, rule 2.
- `src/xippios/usda/gats/tasks.py`, `get_census_export_series`,
  `get_census_import_series` and `get_census_reexport_series` — nothing: they already
  refuse a range with an unreleased month with `NotFoundError` naming the released
  months, and their docstrings say so — ADR-0022, amendment (6) and (7).
- `scripts/refresh_reference.py` — as for sdk-usda-esr — `dump_upstream`, C7.

## [0.2.1] - 2026-10-27

This patch release carries the release train, the family conformance check every source
runs, and the shared test helpers brought forward from 0.3.0; `gates.yml` ships switched
off. ADR-0019 to ADR-0023 and conventions 1.14 and 1.15 come as documentation; the code
of ADR-0019 and ADR-0022 ships in 0.3.0. As a patch, it keeps 0.2.0's compatibility
(conventions §12). A source adopts it in one adoption PR with `/adopt-release`, moving
its bound to `xippios-core~=0.2.1` (ADR-0018, amendment (c)); "Hand-apply for sources"
below lists what that PR changes by hand.

### Added

- **The release train** (conventions §12; ADR-0018, amendment (b); Johannes's decision
  of 2026-10-26): `publish.yml` keeps its name and runs on every push to `main` and on
  dispatch. Its `release-check` looks at a push that changed `pyproject.toml` or
  `CHANGELOG.md` (a new source's first release PR changes only the CHANGELOG, since the
  scaffold already says 0.1.0) and lets it through when the version in `pyproject.toml`
  has no tag and `CHANGELOG.md` has its `## [X.Y.Z] - ` heading; a changed
  `pyproject.toml` without that heading leaves a notice, anything else ends quietly.
  Then CI, the annotated tag `vX.Y.Z` on the merge commit with the CHANGELOG section as
  its message, the build checked against that tag, and the `pypi` environment that
  Johannes approves. A session never pushes a tag; sdk-usda-psd's v0.2.0 tag on the
  wrong commit, caught by the old workflow, was the case. `publish.yml` has no
  `concurrency` group, whose one pending run would lose a release run queued behind a
  run waiting at `pypi`. The workflow's header and `docs/handover.md` give the recovery
  path ("Re-run failed jobs" once the tag exists; a build that fails for good after the
  tag needs a patch release) and the race of two pushes to `main` close together (the
  second run's tag push fails red, or tags a later commit when the first run's `ci`
  failed; re-run the failed jobs of the run whose commit is the release, and if the
  other run already tagged a later commit, Johannes rejects its `pypi` deployment and
  the release is re-done as a patch; a release is not merged while another release run
  is waiting).
- **The family conformance check** (conventions §10; ADR-0013, amendment 2026-10-26;
  Johannes's decision of 2026-10-26), `xippios.core.testing.family`: what every source
  shares, tested once, collected with one line,
  `from xippios.core.testing.family import *  # noqa: F403`, in a template-rendered
  `tests/test_family.py`. Empty namespace levels, `py.typed`, `__version__`; `mcp.py`
  and `http.py` serve exactly `tasks.__all__` minus `BULK_TASKS`, the write server
  exactly `tasks_write.__all__`; every task synchronous (no `async_fn` required,
  conventions §6), returning `Result[T]`, with an agent docstring; the README status
  table, in the format of sdk-template's `README.md.jinja`, lists exactly the read and
  the write tasks; `.copier-answers.yml` names a template tag; `pyproject.toml` bounds
  `xippios-core` and its extras with `~=X.Y.Z`. The package under test is the ini option
  `xippios_package`, which the plugin registers, or the one `tasks.py` under
  `src/xippios/`. It replaces the three copies a review across the family counted in
  every source on 2026-10-25, `tests/test_layout.py`, `tests/test_adapters.py` and the
  structural part of `tests/test_tasks.py` (sdk-usda-psd, sdk-usda-nass, sdk-usda-esr,
  sdk-usda-gats, sdk-comtrade, sdk-cashctrl). Two family checks are CI steps instead,
  documented for the template in `docs/handover.md`: a CHANGELOG entry on every PR but a
  release, an adoption or Dependabot's, and the 256 KiB cap on the fixture files a PR
  adds or changes, a moved one included (ADR-0019), a warning in template v0.2.1 and an
  error from v0.3.0.
- **Shared test helpers** (ADR-0023 decision 2, each carried by two sources or more;
  brought forward from 0.3.0 by Johannes's decision of 2026-10-26):
  - the plugin's `anyio_backend`, asyncio, which the conftest of all six sources and of
    the template defined;
  - `sent_query(route)`, the scrubbed query of the last request a route received (asked
    for by sdk-usda-nass; sdk-usda-nass's `sent_query`, sdk-comtrade's `_sent`,
    sdk-cashctrl inline);
  - `recorded_query(fixture)`, the scrubbed query a fixture was recorded with
    (sdk-comtrade's `recorded_params` and `_recorded`, sdk-cashctrl's `recorded_query`);
  - `response_from_fixture(fixture)`, a recorded answer as an `httpx.Response` with its
    request, for calling `classify` (`recorded()` in sdk-usda-psd, sdk-usda-esr,
    sdk-usda-gats and sdk-cashctrl);
  - `url=` on `mount_fixture`, `replay` and the plugin's `replay_fixture`, serving a
    recorded answer at another URL (`_mount_recorded_404` in sdk-usda-psd and
    sdk-usda-esr, found by sdk-usda-esr);
  - `CLOCK_SLACK` and `assert_time_between(value, before, after)`, bracketing a time read
    around a call with five seconds of slack for the WSL2 host's clock, which steps back
    about two seconds (sdk-usda-gats's `CLOCK_SLACK`; the same bracket without slack in
    sdk-usda-psd and sdk-usda-esr).
  A query parameter sent or recorded more than once fails the two query helpers rather
  than losing a value.
- **`.github/workflows/gates.yml`** (Johannes's decision of 2026-10-26, as a fallback;
  ADR-0018, amendment (e): the merge classes its check posts): calls the `merge-class`
  and `family-review` workflows of `xippios/.github` as jobs, each only when the
  repository variable `GATES_CALLER` is `1`, which Johannes sets per repository if the
  ruleset editor offers no "Require workflows" rule. It ships off.

### Changed

- **`ci.yml` has no push trigger** (the release train, above): CI runs once per push to
  `main`, through `publish.yml`, for a release; the strict up-to-date policy tests every
  tree before it merges.
- **Every action in the three workflows is pinned by commit SHA**, its version in a
  comment, as in the `xippios/.github` repository.
- **The sdist's include and exclude patterns are anchored at the root** (found by
  sdk-template): unanchored, `README.md` and `LICENSE` match a file of that name at any
  depth. The sdist's file list is unchanged.
- **The `testing` extra declares `packaging>=22`**, which the family check reads the
  core bound with and which pytest already required; 22.0 is the first release whose
  versions and specifiers are PEP 440 only.

### Documentation

- **ADR-0019, bulk downloads and non-JSON payloads**: a streaming `download` that never
  touches the cache, `decode_text` and `decode_csv`, a byte bound on the cache, bulk
  tasks named in `BULK_TASKS` and skipped by the adapters, the fixture files a PR adds
  or changes under 256 KiB (a fixture over the cap recorded before the rule stays until
  re-recorded; small real samples for XML, ZIP, gzip, XLS and XLSX, never
  byte-truncated, byte truncation for text bodies only; JSON arrays truncated by
  elements and marked), and a `key` parameter that is data when the key is not sent in
  the query. The code ships in 0.3.0.
- **ADR-0020, file-distributed sources**: layer 1 is fetch plus `parse/`, one parser per
  file kind; fidelity applies to files; CSV/TSV, XML, gzip and zip are read with the
  standard library, XLS/XLSX or a hardened XML library through the source's own
  dependency; a PDF yields narrative text only, never numbers; the download's recorded
  exchange is replayed for the download call and the sample file is what the parser
  tests read, its provenance one row in `tests/fixtures/files/README.md`.
- **ADR-0021, dependencies between source packages**: a source may consume another
  source's task layer, bound to one minor, sharing one core minor, the dependency
  tagged first.
- **ADR-0022, packaged answers and release times**: `meta` of a packaged list carries
  the upstream's fetch time, operation and release identifier; `published_at_naive`
  admits a release time printed without a zone; `None` filters are left out of
  `meta.request`. The code ships in 0.3.0.
- **ADR-0023, core scope**: code enters `xippios-core` with two consumers, or one
  consumer for a stated reason from a closed list; a helper is copied to a second
  source at most; a public name with no consumer for two minors is removed.
- **ADR-0003, amendment 2026-10-26**: a source whose API is one part of a shared
  upstream document snapshots its part and records the full document's byte size and
  sha256; a `project` override that drops a personal identifier inside a kept list field
  (`bankAccounts[].iban`) is still parsing only; an adoption PR, which fetches nothing,
  leaves `FETCHED.md` to the next `/refresh-upstream` and ports only the capture
  script's changes.
- **ADR-0018, amendment 2026-10-26**: (a) decision 3 covers sdk-template's release PRs,
  which auto-merge after the reviewer's `ready` like core's and a source's; (b) the
  release train replaces the human tag: the release PR's merge runs `publish.yml`, which
  tags `vX.Y.Z` on the merge commit, and the approval of the `pypi` environment run is
  the human gate; sdk-template tags from its CHANGELOG's top heading with its own
  `release.yml`; until a repository's workflow tags itself, Johannes pushes its tag;
  (c) the core bound may read `~=X.Y.Z` when patch Z shipped what the source adopts,
  still one minor; (d) an adoption PR may delete the fixtures, mounts and tests the
  adoption itself makes dead, and nothing else rides along.
- **`docs/roadmap.md`**: core 0.2.1 and template v0.2.1 as the first step, core 0.3.0
  opening with a PR that deletes what has no consumer, and the order of the next
  sources; faostat's API is keyed by a login bearer token (probed 2026-10-26), and
  wasde's tables come from the release's XLS or XML, decided with Johannes when its work
  starts.
- **Conventions 1.14**: the rules of ADR-0019 and ADR-0022 bind a source from its 0.3.0
  adoption, or, when it starts on a git pin of core 0.3.0, each rule from its first PR
  on a pin that carries the rule's code; `usda-wasde` among the source names (§1;
  ADR-0020, ADR-0021); files and bulk tasks (§2, §3, §6, §8, §9, §10; ADR-0019,
  ADR-0020); a snapshot of one part of a shared upstream document and personal
  identifiers inside a kept list field (§3; ADR-0003 amendment); packaged answers, naive
  release times and the spared `key` (§4; ADR-0019, ADR-0022); source dependencies (§11,
  §12, §15; ADR-0021); the release train and the patch case of the core bound (§12;
  ADR-0018 amendment); copies of a helper (§15; ADR-0023); dead fixtures an adoption PR
  may delete (§15; ADR-0018 amendment); an adoption PR leaves `FETCHED.md` to the next
  `/refresh-upstream` (§15; ADR-0003 amendment).
- **Definition of done**: the fixture cap on the files a PR adds or changes and the
  `truncated` marker, file samples, a core PR's consumer statement in its ADR or
  description, the adoption line per ADR-0023 and the patch case of the bound, the
  live-call count, the `Decisions taken` block with what backs each line (as in the
  review checklist) and the release subset.
- **`docs/review-checklist.md`**: the checklist a reviewer applies to any `sdk-*` PR:
  `main`'s documents for every PR and the branch's own for a PR that changes them, a
  release PR's own tag allowed, a decision backed by a convention, an ADR, a
  coordination rule, a dated decision of Johannes's or a row, and a conventions change
  carrying an ADR or an amendment.
- **`.github/PULL_REQUEST_TEMPLATE.md`** mirrors the definition of done, its Adoption PR
  block included, with the Assumptions, Open questions and Decisions taken headings.
- **Conventions 1.15**: §10 states the one live workflow, `.github/workflows/live.yml`,
  in the shape the template renders, which a source whose secrets differ keeps: one job,
  `contents: read`, nightly and on `workflow_dispatch`, the key reaching only its pytest
  step, sources that share a key staggering their start (ADR-0009 amendment; found by
  sdk-template); §10 names the family conformance check, `xippios.core.testing.family`,
  which the rendered `tests/test_family.py` collects and every source's CI runs
  (ADR-0013 amendment); §15 and the definition of done's Adoption PR intro: the session
  enables auto-merge on an adoption PR only when its merge class is `auto`, and a
  `human` adoption waits for Johannes (ADR-0018, amendment (e); the merge classes of the
  `.github` repository's README), and the definition of done's Process line allows the
  session's one merge action, auto-merge on an adoption or `chore/release-*` PR, only
  when its merge class is `auto` (ADR-0018, amendment (e)).
  `.github/PULL_REQUEST_TEMPLATE.md` mirrors both.
- **ADR-0009, amendment 2026-10-26**: the live workflow's shape is the rule for every
  source, since the nightly live tests spend a shared key too.
- **ADR-0013, amendment 2026-10-26**: the plugin's guarantees extend to the family
  invariants the template-rendered `tests/test_family.py` collects.
- **ADR-0018, amendment (e)**: decision 3's auto-merge of adoption and release PRs after
  the reviewer's `ready` applies only to a PR whose merge class is `auto`; a `human`
  adoption or release (a source-owned workflow, a changed template answer, a protected
  path, a build or install route) waits for Johannes (his merge-class decision of
  2026-10-26).
- **`docs/roadmap.md`**: a pinned new source swaps to `~=0.3.0` in its single v0.3.0
  adoption PR, since a release PR changes only the §12 subset; eurostat's design round
  is the first decision put to Johannes when its work starts; faostat's paging and
  limits are verified with the credential first, once Johannes provides the FAO account
  on approving its package; the release check fires on a change of the version or of
  `CHANGELOG.md`, so a first release tags itself; the snapshot and design-round PRs of
  esmis and eurostat start on template v0.2.1 and core 0.2.1 without a pin, the scaffold
  carries `core_git_ref` only when core's `main` has merged the api.data.gov gateway
  module and the bulk downloads of ADR-0019, else a re-pin PR precedes the first tasks
  PR, and a re-pin to a SHA with ADR-0022's code precedes the reference-data PR;
  eurostat proves a keyless render of template v0.2.1 with `new-source.sh --local-only`,
  and the login-keyed case (faostat) is not a template variant (ADR-0023, ADR-0008).
- **`CLAUDE.md` and `docs/handover.md`** describe the release train: a session never
  tags, the release PR's merge tags, Johannes approves `pypi`. `docs/handover.md` gains
  "Core 0.2.1", with the release's recovery path, and "Adopting core 0.2.1", per source,
  with the template's two CI steps.

### Hand-apply for sources

What a source's adoption of 0.2.1 changes by hand: files the template does not update,
and the values `copier update` takes from the answers; `docs/handover.md`, "Adopting core
0.2.1", names them per source.

- `pyproject.toml` — `xippios-core~=0.2.1` and its extras likewise, from
  `core_version=0.2.1` — `tests/test_family.py` imports what 0.2.0 lacks (ADR-0018,
  amendment (c)).
- `tests/test_tasks.py` — delete `test_package_has_a_version` and
  `test_task_is_a_sync_facade_with_an_agent_docstring` — the family check makes them.
- `tests/test_client.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_errors.py` (sdk-cashctrl) — `recorded()` → `response_from_fixture` — a
  shared test helper (ADR-0023).
- `tests/test_slices.py` (sdk-usda-psd, sdk-usda-esr) — `_mount_recorded_404` →
  `replay_fixture(..., url=...)` — a shared test helper, found by sdk-usda-esr.
- `tests/test_tasks.py` (sdk-usda-nass `sent_query`, sdk-comtrade `_sent`, sdk-cashctrl
  inline) — the query of the last request → `sent_query` — a shared test helper, asked
  for by sdk-usda-nass.
- `tests/conftest.py` and `tests/test_tasks.py` (sdk-comtrade `recorded_params` and
  `_recorded`), `tests/test_tasks.py` (sdk-cashctrl `recorded_query`) — the recorded
  query → `recorded_query` — a shared test helper (ADR-0023).
- `tests/test_lists.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_tasks.py` (sdk-usda-gats) — the `retrieved_at` bracket →
  `assert_time_between`, `CLOCK_SLACK` from core — a shared test helper (ADR-0023).
- `tests/test_adapters.py` (sdk-comtrade, sdk-cashctrl) — the tests of their own move to
  `tests/test_tasks.py` or `tests/test_tasks_write.py` before the update deletes the
  file — the family check makes the rest.

## [0.2.0] - 2026-10-25

What the first four sources, sdk-usda-nass, sdk-comtrade, sdk-usda-psd and sdk-cashctrl,
had to build around core 0.1.0, moved into core: ADR-0009 to ADR-0018, amendments to
ADR-0003, ADR-0005, ADR-0007, ADR-0008, ADR-0010, ADR-0013 and ADR-0015, a follow-up
pointer in ADR-0011, and conventions 1.5 to 1.13 (0.1.0 shipped 1.4). While core is 0.x
a minor keeps no compatibility with the one before it: a source depends on
`xippios-core~=0.2.0` and adopts this release in one adoption PR before its next release
(conventions §12 and §15, ADR-0018). The section "Adopting core 0.2.0" of
[`docs/handover.md`](https://github.com/xippios/sdk-core/blob/main/docs/handover.md), in
the repository and not in the sdist, lists per source what that PR deletes and what
replaces it.

### Breaking changes

- **Writes are not retried after a 5xx** (ADR-0011): a 5xx and a transport failure are
  retried for GET, HEAD and OPTIONS only; a POST, PUT, PATCH or DELETE answered with a
  5xx is raised as `UpstreamError` after one attempt, so a write upstream applied before
  answering 502 is not sent twice (sdk-cashctrl). A 429 is still retried for every
  method. `RetryPolicy(retry_non_idempotent=True)` retries writes again, for an upstream
  that makes a repeated write safe or a source that only reads through POST.
- **Error messages name no host** (ADR-0005 amendment): `error_from_response` writes
  `404 from GET /v1/series: ...`, and `error_from_exception` writes `<host>` where a
  transport failure's text quotes the host. A multi-tenant source's host names the
  tenant; sdk-cashctrl had to mask it in its own `classify`.
- **Binary bodies are refused when recording** (ADR-0013): a body that is not UTF-8 text
  raises `ValueError` ("binary body cannot be scrubbed") and nothing is written, unless
  `Scrub(allow_binary=True)` stores it base64, flagged `body_base64: true` and
  unscrubbed, as 0.1.0 stored every such body (sdk-cashctrl).
- **`EnvKeyAuth.apply(self, request)`**: `apply` reads the key through `self.key()`
  instead of taking it as an argument, which pytest's long tracebacks printed
  (sdk-usda-nass); core's auth classes keep the key in no argument and no local
  variable. A subclass outside core that implements `apply(request, key)` drops the
  parameter; none is known.
- **The pytest plugin keeps the default run offline on its own** (ADR-0013, decision 4
  added by ADR-0015). In every test not marked `live`: a request through httpx's default
  transports or httpcore's pools raises `RuntimeError` naming method and path, from
  `pytest_configure` on, fixtures and collection included (`respx` answers and a
  transport a test passes itself are unaffected; a `respx` pass-through is refused); a
  rate limiter neither waits nor takes a token; every `QuotaPolicy` snapshot is
  forgotten before and after the test, and no policy waits or refuses; every
  `EnvKeyAuth` sends `PLACEHOLDER_KEY`, pinned on the class, and the variables named in
  the ini option `xippios_placeholder_key_envs` hold it. The `httpx` and `httpcore`
  logger levels come back after every test. A test that must reach the network is
  marked `network`; one that asserts a limiter wait, a quota pause or a quota refusal
  is marked `rate_limited`; a module that tests key resolution overrides
  `placeholder_api_key` with a fixture that pins nothing. A source deletes its own
  placeholder fixture, which could not reach one auth object per tenant (sdk-comtrade,
  sdk-cashctrl), and its replays stop waiting behind its limiter (sdk-comtrade,
  sdk-usda-psd).
- **`confirm: bool = False` is enforced at registration** (ADR-0014):
  `register_tasks(..., read_only=False)`, and so `build_server`, refuses with
  `ValueError`, before registering anything, a task without a parameter `confirm`
  annotated `bool` (`Annotated[bool, ...]` counts, `bool | None` does not) defaulting
  to `False`; before, only `assert_write_tools` caught it, in a test (sdk-cashctrl).
- **Write servers listen on loopback only** (ADR-0014): `main` serves a write server
  over `--http` on `127.0.0.1`, `localhost` or `::1` and otherwise exits with status 2,
  unless `--allow-remote` is passed: a write server carries no authentication, so
  beyond loopback a gateway in front of it has to. Read-only servers and stdio are
  unaffected.
- **`mcp_call` runs the server's middleware** (ADR-0014): it calls the tool through an
  in-process `mcp.Client` instead of `MCPServer.call_tool`, so a tenant lock applies
  (sdk-cashctrl). An MCP error, arguments the tool's schema refuses or an unknown tool
  now fail the test with `AssertionError` instead of raising the SDK's `ToolError`, and
  the server must be one `mcp.Client` connects to (an `MCPServer` or a low-level
  `Server`).
- **`classify` shapes retries** (ADR-0015): before a 429 or 5xx is retried, the client
  asks `classify`, also with `raise_on_error=False`. A `RateLimitError` sets the wait
  from its `retry_after`, so a wait beyond `RetryPolicy.backoff_max` is raised after
  one attempt; an `UpstreamError` for a 5xx, or `None`, keeps the status rule; any other
  error, an `AuthError` say, ends the retries. api.data.gov's 429 without `Retry-After`
  was sent three more times into the spent quota (sdk-usda-psd). `send_with_retries`
  takes `classify=`.
- **Result caps count UTF-8 bytes and promise no filter** (ADR-0016): `cap_result`
  measures `max_bytes` in UTF-8 bytes of the compact JSON text, as the convention said,
  not in characters, so non-ASCII text keeps fewer rows; the preview cuts no character.
  The default note ends "narrow the query to see the rest" ("showing {shown} of {total}
  rows (cap: {max_rows} rows or {max_bytes} bytes); ...", for a non-list result "result
  is {n} bytes, over the cap of {max_bytes}; ..."), where it suggested "more filters or
  a shorter date range" that a reference list does not have (sdk-comtrade). A test that
  asserts the old text changes; none is known.
- **Generated enum modules are ASCII-only and pass ruff as rendered** (ADR-0008
  amendment): `render_str_enums` writes each value as `ascii()` does
  (`"C\xf4te d\u2019Ivoire"`, unchanged at runtime), lays out a long member as ruff
  formats it, sorts `__all__` in ruff's order (RUF022), one name per line, and wraps its
  docstrings at 100 columns. It refuses with `ValueError` what made a file ruff rejects:
  caller text it cannot write as printable ASCII, a `generator`, `fetched` text, key or
  class name (a class name must also be an identifier, no keyword, at most 84
  characters), the error naming the argument and position, never the text; a member name
  over 92 columns, the error naming the key and quoting the value; and a key over 75
  characters, the error quoting the key. A value with nothing to derive a member name
  from (a Greek, Cyrillic or CJK label) is named once through the new `member_names=`. A
  source re-renders its enum file once and commits the one-time diff (sdk-usda-nass's
  first line only); the formatting step after a refresh goes (sdk-comtrade).
- **`Tenants` splits the caller's mistake from the operator's** (ADR-0014): new in this
  release, so it breaks only a source that moves its own tenant registry onto it. An
  undeclared tenant is `InvalidRequestError` (MCP text, HTTP 422), "unknown tenant ...";
  a missing or malformed variable of a declared one is `ConfigError` naming the
  variable, never the value (sdk-cashctrl, on its git pin already).
- **Personal identifiers stay out of task projections** (ADR-0017, conventions §3), a
  rule for sources: documented personal identifiers (CashCtrl's `ssn` and `iban`, and
  what a source judges equivalent) are left out of the projections tasks return unless
  a task fetches them deliberately and says so, and a write task does not echo one in
  `meta.request`; read models stay faithful; fixtures never carry the values, which a
  recording names in `Scrub(secrets=...)` or rewrites with `Scrub(rewrite=...)`.
  Nothing in core changes.

### Added

- **Request hooks and a quota policy** (ADR-0015, sdk-usda-psd).
  `ClientConfig.before_request` runs once per call, after the cache lookup and before
  the rate limiter, with no credentials on the request yet; sync or async, it may wait,
  or raise a taxonomy error and nothing is sent. `ClientConfig.observe` sees every
  response from the wire, retried attempts and raw responses included, a cache hit
  never, before `classify`. `QuotaPolicy` and `QuotaSnapshot` (in `xippios.core` and
  `xippios.core.client`) implement ADR-0010's quota rules on them:
  `QuotaPolicy(...).install(config)` sets both, and the policy keeps a thread-safe
  snapshot from the quota headers (`limit_header`, `remaining_header`, `reset_header`,
  each `None` to turn it off); a 429, or `remaining` at 0, marks the quota spent until
  `Retry-After`, the reset header or `window` from now, upstream's wait cut to `window`
  (`window=86400` for a daily quota); `spent=` reads any other answer to a spent limit,
  such as sdk-comtrade's 403 "replenished in HH:MM:SS", and `mark_spent()` marks it from
  code. A request into a spent quota waits within `pause_cap` (else
  `retry.backoff_max`), logged once, or raises `RateLimitError` with `retry_after`,
  saying nothing was sent and when the quota is back. `install` refuses a config with a
  hook of its own, and a subclass's `before_request` override is not called through the
  hook it sets; `snapshot()`, `reset()`, and `QuotaSnapshot.describe()`, numbers and
  times only. Replaces sdk-usda-psd's `QuotaAwareClient`, `Quota`, `observe_quota` and
  `quota_pause`, which sdk-usda-esr and sdk-usda-gats would otherwise copy.
- **Keyless calls on a keyed client** (ADR-0015, sdk-comtrade): `auth=` per call on
  `request`, `get` and `get_json` of `AsyncClient` and `Client`, and on `record` and
  `record_sync`, default `httpx.USE_CLIENT_DEFAULT` (its type, `UseClientDefault`, is
  re-exported from `xippios.core.client`). `None` sends the call, retries included,
  without the client's credentials and shares the cache; an `httpx.Auth` replaces them
  for that call and bypasses the cache. sdk-comtrade needed a second client to keep its
  key off public files on its data API's host.
- **Cache provenance and a cache filter** (ADR-0015, sdk-usda-psd): a cache hit carries
  `extensions["xippios_cache_stored_at"]`, the entry's time in epoch seconds, from which
  a task sets `retrieved_at` (conventions §4); `xippios.core.client.decode_json` is
  `get_json`'s decoding for a wrapper that calls `get` to read it.
  `ClientConfig.cache_filter` decides which GETs the cache takes, so one endpoint can be
  cached without a second client. `WIRE_HEADERS` and `strip_wire_headers` name the
  headers dropped from cache entries and fixtures (`content-length`,
  `content-encoding`, `transfer-encoding`, `connection`).
- **A shared pace** (sdk-usda-psd): `limiter=` for `AsyncClient` and `Client` takes a
  `TokenBucket` instead of building one from `config.rate_limit`, and
  `AsyncClient.limiter` returns the bucket in use, so two clients can share one pace.
- **Form bodies and retried writes** (ADR-0011, sdk-cashctrl): `data=` on
  `AsyncClient.request`, `Client.request`, `record` and `record_sync` sends a
  form-encoded body (passing `json=` too raises `ValueError`); `RetryPolicy`'s
  `retry_non_idempotent` (default `False`) retries a 5xx and a transport failure for
  POST, PUT, PATCH and DELETE too.
- **`AsyncClient.derive(retry=..., timeouts=...)`** (sdk-comtrade): a client with only
  those replaced, sharing auth, transport, sleep, rate limiter and cache. Closing it
  closes its own pools and leaves the borrowed transport open for its parent, as
  `record` needs after a recording with `retry=` or `timeouts=`; a transport a caller
  passed to a client is still closed with that client. `record` and `record_sync` take
  `headers=`, `scrub=`, `retry=` and `timeouts=`, overrides going through `derive`.
- **Upstream totals** (ADR-0012, sdk-cashctrl): `ResultMeta.total`, upstream's count of
  the records matching the request, `None` when it reports none. A paginated task sets
  it from upstream's count whether it returns one page or all, never from
  `len(data)`; a negative count is refused; `cap_result` and HTTP responses keep it.
- **Multi-tenant sources** (ADR-0014, sdk-cashctrl). `ResultMeta.tenant`, the tenant by
  name, never a value (`"tenant": null` for a single-tenant source).
  `xippios.core.Tenants(source, *, list_var, fields, reserved=(), validate=None,
  hints=None)` reads the tenants from the environment, names listed in `list_var` and
  values in `<SOURCE>_<NAME>_<FIELD>`, which `var(name, field)` names, a reserved tenant
  (`demo`) present when its variables are set; `names()`, `require(name)`,
  `field(name, field)` through `validate`, with `hints` text for a refused value,
  `client_for(name, build)`, one client per tenant rebuilt when a value changes,
  `reset()`. `xippios.core.tenants.list_task` is the task behind a
  `<source>_list_<tenants>` tool, names only. `TenantLock(param, value)`, as
  `tenant_lock=` for `build_server` and `register_tasks`, refuses without running the
  tool a call that names another tenant or leaves the tenant out, and names the tenant
  in the instructions; the list tool lists that tenant alone, and a locked server
  refuses a task whose tenant parameter has a default. `main(..., add_options=,
  apply_options=)` and `build_parser(prog, *, add_options=)` put a source's options on
  core's parser, parsed once, a `XippiosError` from `apply_options` exiting with status
  2; `is_write_server(server)` serves the loopback rule. Generalises sdk-cashctrl's
  organisation registry and `--org` lock.
- **Per-tool result caps** (ADR-0016, sdk-comtrade, sdk-usda-psd): `caps=` on
  `register_tasks` and `build_server` maps a task function's `__name__`
  (`list_partners`, not the tool name) to a `ResultCap` replacing `cap` for that tool;
  an unknown name is refused before anything is registered. A source keeps it as
  `MCP_CAPS` in `tasks.py`, passed by its `mcp.py` as
  `caps=getattr(tasks, "MCP_CAPS", None)`. `ResultCap(note=...)` replaces the text after
  the counts. The default, 200 rows or 65,536 bytes, cut `comtrade_list_reporters` (255
  rows, 69,011 bytes) and `comtrade_list_partners` (310 rows, 83,270 bytes) at 200
  rows, and `usda_psd_list_countries` (251 rows) before the United States.
- **Integer-id enums** (ADR-0008 amendment, sdk-usda-psd):
  `xippios.core.reference.render_int_enums` renders one `IntEnum` per list of
  `(id, name)` pairs, values the ids in upstream order, so a member equals the id in
  upstream's data; member names come from the names, `_<id>` appended to a name several
  ids share (`TOTAL_DISAPPEARANCE_126`); layout, `member_names=` and refusals as in
  `render_str_enums`, and an id listed twice is refused. `id_name_pairs(records, *,
  id_field, name_field)` builds the pairs, refusing a bad record by field and position,
  never by content. Replaces sdk-usda-psd's `render_id_enums`.
- **Scrubbed recording** (ADR-0013, sdk-cashctrl): `xippios.core.testing.Scrub(host=,
  secrets=, rewrite=, allow_binary=)`, as `scrub=` on `write_fixture`, `record` and
  `fixture_from_response` (now exported from `xippios.core.testing`), removes in memory,
  before the one write, what credential scrubbing does not: the request's host, replaced
  by a placeholder in every form (letter case, IDNA, percent-encoded), named values made
  `REDACTED`, and a text hook for bodies and response headers, for signed URLs. The
  scrubbed exchange is then verified, a JSON body also decoded; a host or value left
  raises `ValueError` saying where, never what, and nothing is written. A placeholder
  that would write what it hides is refused; one that contains the original host
  (`demo.example.test` for `example.test`) is allowed. `Scrub`'s `repr` leaves `secrets`
  out. `FixtureRequest.body`, `body_base64` and `content_type` keep the scrubbed request
  body for a write test to assert; fixtures from 0.1.0 still load. Ports the recorder
  sdk-cashctrl kept locally.
- **Replay by query parameter** (ADR-0013, sdk-comtrade): `match_params=` on
  `mount_fixture`, `replay` and the plugin's `replay_fixture` names recorded query
  parameters a request must carry too, so a count call (`countOnly=true`) and the data
  call on one path are told apart; a name not recorded, or recorded as `REDACTED`, is
  refused. Absence cannot be matched: the more specific fixture is mounted first.
  `ReplayFixture` types the fixture.
- **`xippios.core.testing.sent_urls(route)`** (sdk-usda-nass): the URLs a `respx` route
  received, through `scrub_url`, for a test to compare instead of keeping a request,
  key included, in its frame, which a failing assertion or `pytest -l` prints.
- **Offline-test names** (ADR-0013): `xippios.core.testing.PLACEHOLDER_KEY`
  (`"placeholder-for-fixture-replay"`), the ini option `xippios_placeholder_key_envs`
  and the markers `network` and `rate_limited`, described under Breaking changes.
- **Write-server checks** (sdk-cashctrl): `xippios.core.testing.assert_write_tools(
  write_server, write_tasks, *, source, read_server=None, router=None)` fails a test,
  naming the tool, unless the server is a write server whose tools are exactly the write
  tasks, each with `confirm: bool = False`, and no write tool is on the read server or
  the router. `mcp_call_text(server, name, arguments)` returns a tool's text through
  the same in-process client as `mcp_call`, for asserting an `error:` text.
- **ADR-0009 and ADR-0010** (sdk-usda-psd, sdk-comtrade): one key variable per issuer
  when one key serves several sources (`DATA_GOV_API_KEY`), and the rate-limit policy:
  a fast pace within a documented limit or a stated self-imposed one, longer-window
  quotas spent rather than rationed, the answer to a spent limit interpreted in
  `classify`, no request fired into a spent quota, pauses stated.
- **ADR-0018, core versioning and source adoption**: a source depends on one core minor
  (`xippios-core~=X.Y.0`) and adopts each new minor in one adoption PR against
  conventions §15, the definition of done's "Adoption PR" block. Adoption
  (`chore/template-update*`) and `chore/release-*` PRs are auto-merged after the
  reviewer's `ready`.

### Changed

- **Conventions 1.5 to 1.13**: 1.5 the key variable per issuer and the rate-limit
  policy (§1, §5, §6, §7; ADR-0009, ADR-0010); 1.6 error messages without the host and
  the retry rule (§5, §6; ADR-0011); 1.7 `ResultMeta.total` (§4; ADR-0012); 1.8 form
  bodies, the recorder's rules and the plugin's guarantees (§6, §10; ADR-0013); 1.9
  tenants, the `confirm` check, the loopback rule, the tenant lock and the option hooks
  (§1, §4, §7, §8, §10; ADR-0014); 1.10 the hooks, `QuotaPolicy`, `classify` in retries,
  `auth=` per call and a cache hit's `retrieved_at` (§4, §6, §10; ADR-0015); 1.11 the
  UTF-8 byte cap, per-tool caps in `MCP_CAPS` and a note that promises no filter (§8;
  ADR-0016); 1.12 `IntEnum` for integer ids and ASCII-only, ruff-clean enum modules
  (§3; ADR-0008 amendment); 1.13 `Fetched` as a UTC time with `Z`, HTML for tables a
  pipe table cannot hold, vendor snapshots (§3; ADR-0003 amendment), personal
  identifiers out of task projections (§3, §4; ADR-0017), `InvalidRequestError` also
  for upstream's own refusal mapped in `classify` (§5; ADR-0007 amendment, its
  docstring and the README with it), the one-minor core bound and the 0.x rule (§11,
  §12) and the adoption checklist (§15; ADR-0018). The definition of done gains the
  "Adoption PR" block, and its fixture grep covers the identifiers' values.
- **The edges of the plugin's quota guarantee are documented** (ADR-0013 and ADR-0015,
  amended by ADR-0016): consecutive live tests share every policy's snapshot; a quota
  spent while a fixture of wider scope is set up is forgotten before the body of the
  next test not marked `live`; a `QuotaPolicy` subclass's `before_request` override is
  neither called through `install`'s hook nor neutralised.
- **The `testing` extra declares `httpcore>=1.0`**, which the plugin patches and which
  only httpx's own dependency provided before.
- **CI runs `uv run pre-commit run --all-files`** after the tests, so the definition of
  done's "Enforced by CI" block holds.

### Fixed

- **A gzip answer replayed from the cache** raised `httpx.DecodingError`: the decoded
  body was stored with `content-encoding`. Entries are stored without wire headers, and
  those a persistent backend kept from 0.1.0 are stripped when replayed (sdk-usda-psd).
- **`parse_retry_after`** let `ValueError` or `OverflowError` out of the retry loop for
  non-ASCII digits (`"²"`) or an HTTP-date with a huge zone offset, and returned an
  infinite `retry_after` for a value too long for a finite float. It reads ASCII digits
  only and returns `None` for what it cannot read.
- **The live gate** skipped every test under a directory named `live`, marked or not;
  it follows the marker now.
- **Taxonomy errors survive `copy.copy`, `copy.deepcopy` and `pickle`**: errors with
  keyword-only arguments raised `TypeError`; `XippiosError.__reduce__` restores every
  attribute (sdk-cashctrl).
- **`RateLimit.per_minute`'s docstring**: the pace is the one a source sets within
  upstream's limit, or a self-imposed one (ADR-0010), not upstream's limit.

### Security

- **The MCP servers no longer log request URLs** (ADR-0005). Constructing an `MCPServer`
  configures root logging at `INFO`, and httpx logs every request URL at `INFO`, so
  every `xippios-<source>-mcp` wrote upstream URLs into its MCP client's logs:
  sdk-usda-nass's key, sent as `key=`, and sdk-cashctrl's tenant host.
  `xippios.core.mcp.quiet_request_logging()` sets the `httpx` and `httpcore` loggers to
  `WARNING`; `build_server` calls it after constructing the server, and `main` again
  right before running it, after `apply_options`. A consumer who wants the log raises
  the level and runs the server without `main`.
- **`.gitignore`** also ignores `.env.*` and `.envrc.*` (sdk-comtrade).
- **The secret scan no longer skips paths containing "swagger"**: detect-secrets'
  `is_swagger_file` filter, which exempted a verbatim upstream Swagger snapshot, is
  dropped (sdk-usda-psd); `.secrets.baseline` and the detect-secrets hook exclude
  `.copier-answers.yml` with sdk-template's pattern, so the template copies both files
  verbatim again (sdk-comtrade).

## [0.1.0] - 2026-10-22

First release, cut after the first source package (sdk-usda-nass) had exercised it.

### Added

- `xippios.core.errors`: the family error taxonomy (`XippiosError` and seven
  subclasses), `error_from_response`, `raise_for_status`, `parse_retry_after`.
- `xippios.core.models`: `UpstreamModel`, `ResultMeta`, `Result[T]`, `parse`.
- `xippios.core.config`: `SourceSettings` base and `resolve_api_key`.
- `xippios.core.sync`: derive a sync function from an async one on a shared
  background event loop.
- `xippios.core.client`: `AsyncClient` and `Client` with `ClientConfig`, `Timeouts`,
  `RetryPolicy`, `RateLimit`, `MemoryCache` and the `CacheBackend` protocol.
- `xippios.core.client.auth`: `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth`,
  `BasicKeyAuth` and the `EnvKeyAuth` base, resolving the key from the environment on
  the first request. Re-exported from `xippios.core`.
- `ResultMeta` redacts credential-like keys in `request` at construction (ADR-0005).
- `resolve_api_key` is typed to return `SecretStr` when the key is required.
- `xippios.core.pagination`: `paginate_offset`, `paginate_pages`, `paginate_cursor`,
  `collect`.
- `xippios.core.reference`: `load_csv`, `load_json`, `load_table`.
- `xippios.core.mcp` (extra `mcp`): `build_server`, `register_tasks`, `cap_result`,
  `error_to_text`, `main`.
- `xippios.core.http` (extra `http`): `router_from_tasks`, `problem_response`,
  `install_error_handlers`.
- `xippios.core.testing` (extra `testing`): pytest plugin with the `live` gate,
  fixture format, `record`, `replay`, scrubbing helpers.
- CI on Python 3.12, 3.13 and 3.14; trusted publishing on `v*` tags.
- `UpstreamModel` serialises `Decimal` fields as JSON numbers in both adapters
  (ADR-0008); `UpstreamModel.project` builds projections; `parse_decimal` reads
  published figures with separators or suppression codes.
- `ClientConfig.classify`: a source's error mapping, called on every response before
  the default status mapping.
- `xippios.core.reference.render_str_enums` and `enum_member_name`: generated
  `StrEnum` source for packaged value lists.
- `xippios.core.testing.assert_projection` and `mcp_call`.
- `InvalidRequestError` in the taxonomy (ADR-0007): a request refused before it is
  sent; HTTP 422, MCP text. Re-exported from `xippios.core`.
- `xippios.core.http.is_scalar`.

### Changed

- `router_from_tasks`: a task with any non-scalar parameter becomes a `POST` route whose
  JSON body is an object keyed by parameter name; scalar-only tasks stay `GET`.
