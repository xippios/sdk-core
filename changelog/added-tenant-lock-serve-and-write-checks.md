- A multi-tenant source's bound server, its serve command and its write server's check come
  from core again, out of sdk-cashctrl's and sdk-google-mail's copies: `TenantLock`,
  `bind_tasks` and `tenant_instructions` from `xippios.core`, `serve_tenants` from
  `xippios.core.mcp`, and `assert_write_tools` and `keep_reserved_tenants` from
  `xippios.core.testing`. No tool of a server that `bind_tasks(tasks, TenantLock("org",
  "acme"))` binds takes `org`, so a call that names it is refused, and
  `serve_tenants(server, build, TENANTS, param="org", check=...)` is an entry point's
  `--org`, which checks the tenant at startup. `await assert_write_tools(...)` checks a
  write server against its write tasks, `confirm: bool = False` last, and
  `keep_reserved_tenants(TENANTS)` in `tests/conftest.py` leaves the tests the reserved
  tenant alone.
  (ADR-0014, ADR-0024, ADR-0025, §7, §8, https://github.com/xippios/sdk-core/issues/166)
  - Hand-apply: `src/xippios/cashctrl/_org_lock.py` (sdk-cashctrl) — deleted — core's
    `TenantLock`, `bind_tasks` and `tenant_instructions` are this copy: `OrgLock("org",
    name)` is `TenantLock("org", name, noun="organisation")`, whose sentence reads as
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
    its comment (lines 43 to 46) → `serve_tenants(server, build, TENANTS, param="org",
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
    `LOCK` (line 39) → `TenantLock("org", DEMO, noun="organisation")`, `bind(task, LOCK)`
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
    `AccountLock("account", name)` is `TenantLock("account", name)`, its noun the
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
    startup, its message naming the variable and the consent command and no source,
    whichever slug https://github.com/xippios/sdk-core/issues/279 gives the registry.
    `src/xippios/google/mail/mcp.py` (sdk-google-mail) — the imports of `AccountLock`,
    `bind_tasks` and `instructions` from `_account_lock` and of `serve` from `_cli` (lines
    15 to 16) → `from xippios.core import TenantLock, bind_tasks, tenant_instructions`, with
    `serve_tenants` beside `build_server` (line 12) and `TENANTS` and `check_account` beside
    `SOURCE` (line 17), then `AccountLock` (line 35) → `TenantLock`,
    `instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS)` (line 41) →
    `tenant_instructions(INSTRUCTIONS, lock, bound=BOUND_INSTRUCTIONS)`, `serve(server,
    build)` and its comment (lines 51 to 54) → `serve_tenants(server, build, TENANTS,
    param="account", check=check_account)`, and the docstring's `_cli`, `_account_lock`
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
    47) → `TenantLock("account", DEMO)`, `bind(task, LOCK)` (lines 117 and 160) →
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
