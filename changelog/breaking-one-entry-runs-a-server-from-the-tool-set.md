- One entry runs a source's MCP server: `main(build, *, tenants=None, check=None, argv=None)`
  takes the package's `build`, reads the option hooks from the tool set that it returns, builds
  the server that it runs and binds a tenant where `tenants` is given, and `serve_tenants`
  leaves. Core builds the tool set from the tasks module with `ToolSet.from_tasks`, which
  reads `MCP_CAPS`, `MCP_INSTRUCTIONS`, `MCP_BOUND_INSTRUCTIONS`, `mcp_add_options`,
  `mcp_apply_options` and `MCP_LOOPBACK_ONLY`, so a rendered `mcp.py` holds no line that a
  source edits. `apply_options` takes the parsed options alone and returns nothing, the noun
  of a tenant goes from `TenantLock` to `Tenants(noun=)`, both servers of a source are named
  `xippios-<source>`, and `build_parser(server=)`, the three wordings of the help of
  `--allow-remote` and the entry `ResultCap` of `xippios.core.mcp`, which no source imports
  from there, leave. (ADR-0063, ADR-0036, §4, §8,
  https://github.com/xippios/sdk-core/issues/476)
  - Hand-apply: `src/xippios/<package>/tasks.py` (every source) — `MCP_INSTRUCTIONS` holds the text
    that `mcp.py` held as `INSTRUCTIONS`, sdk-cashctrl's and
    sdk-google-mail's `MCP_BOUND_INSTRUCTIONS` the text it held as `BOUND_INSTRUCTIONS`,
    sdk-google-mail's `MCP_LOOPBACK_ONLY = True` the read server's hold to loopback, and
    sdk-usda-gats's and sdk-usda-nass's `mcp_apply_options(namespace: argparse.Namespace) -> None`
    takes no `server`, returns nothing and imports no `MCPServer` — the rendered `mcp.py` builds
    its tool set with `ToolSet.from_tasks`, which reads these declarations from the tasks module,
    and `main` and a host call the hook with the parsed options alone (ADR-0063, decision 7).
    `src/xippios/<package>/tasks_write.py` (sdk-cashctrl, sdk-google-mail) — `MCP_INSTRUCTIONS`
    and `MCP_BOUND_INSTRUCTIONS` hold the texts of `mcp_write.py` — the rendered `mcp_write.py`
    reads them from the write tasks module (ADR-0063, decision 7).
    `src/xippios/<package>/_client.py` (sdk-cashctrl, sdk-google-mail) — sdk-cashctrl's `TENANTS =
    Tenants(..., noun="organisation")`, and the docstrings of sdk-cashctrl's `check_org` and
    sdk-google-mail's `check_account` say that core's `main` calls the check
    after `TENANTS.require`, in place of `serve_tenants` — the noun is the registry's and neither
    the entry nor a lock takes one, `serve_tenants` left core, and the template's update
    skips `_client.py` (ADR-0063, decision 7).
    `README.md` (sdk-usda-gats) — a host applies the hooks
    as `tools.apply_options(tools.option_defaults())` — the hook takes no server (ADR-0063,
    decision 7).
    `CLAUDE.md` (sdk-cashctrl, sdk-google-mail) — the lines that name `serve_tenants`,
    sdk-cashctrl's 47 and sdk-google-mail's 69, 71 and 363, name core's `main`, which binds a
    server to one tenant given `tenants=TENANTS` — `serve_tenants` left core, and the template's
    update skips `CLAUDE.md`, so no update rewrites the lines and no test breaks for them
    (ADR-0063, decision 7).
    `tests/test_org_lock.py` (sdk-cashctrl) — `LOCK = TenantLock(TENANTS, DEMO)`,
    and `test_both_entry_points_bind_to_the_org` reads `MCP_INSTRUCTIONS`
    and `MCP_BOUND_INSTRUCTIONS` from `tasks` and `tasks_write` in place of `module.INSTRUCTIONS`
    and `module.BOUND_INSTRUCTIONS` — a lock given `noun` fails with a `TypeError`, and the server
    modules hold no text (ADR-0063, decision 7).
    `tests/test_entry_points.py` (sdk-cashctrl) — `test_the_server_names_stay`
    expects `mcp_write.server.name == "xippios-cashctrl"` — the write server takes its slug's name
    (ADR-0063, decision 7).
    `tests/test_account_lock.py` (sdk-google-mail) — `test_both_entry_points_bind_to_the_account`
    reads `MCP_BOUND_INSTRUCTIONS` from `tasks` and `tasks_write` in place
    of `module.BOUND_INSTRUCTIONS` — the server modules hold no text (ADR-0063, decision 7).
    `tests/test_contract.py` (sdk-google-mail, sdk-faostat, sdk-x)
    — `test_build_is_the_tool_set_the_entry_point_serves` compares `tools.instructions` with the
    tasks module's `MCP_INSTRUCTIONS`, and sdk-faostat's and
    sdk-x's `test_the_entry_point_help_says_allow_remote_changes_nothing_here` asserts no help
    of `--allow-remote` — `mcp.INSTRUCTIONS` leaves, and the help is one sentence for every server,
    a test of core's own answer that ADR-0063, decision 8, takes out of a source's tests (ADR-0063,
    decision 7).
    `tests/test_tasks.py` (sdk-comtrade, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd,
    sdk-usda-wasde) — sdk-usda-esr's and
    sdk-usda-psd's `test_build_returns_the_tool_set_the_entry_point_serves` and sdk-usda-gats's and
    sdk-usda-nass's `test_the_package_contract_for_a_host` compare `tools.instructions`
    with `tasks.MCP_INSTRUCTIONS`, sdk-usda-gats's and
    sdk-usda-nass's `test_a_host_applies_the_options_as_the_entry_point_does`
    calls `tools.apply_options(tools.option_defaults())`, their tests of the hook
    call `tasks.mcp_apply_options(namespace)` and compare no server
    (`test_the_mcp_server_refuses_a_series_beyond_its_ceiling_before_any_request`
    and `test_the_python_api_spans_60_months` of
    sdk-usda-gats, `test_the_hooks_apply_the_option_through_cores_parser`
    and `test_the_mcp_server_refuses_a_split_beyond_its_ceiling_before_any_call` of sdk-usda-nass),
    their `test_the_entry_point_applies_series_months_or_exits_with_status_2`
    and `test_the_entry_point_applies_split_years_or_exits_with_status_2` patch `MCPServer.run` on
    the class and call `main(build, argv=[...])`,
    and `test_the_entry_point_names_itself_in_its_usage_and_errors` of sdk-comtrade and
    sdk-usda-nass, `test_the_entry_point_names_itself` of
    sdk-usda-esr, `test_the_entry_point_names_itself_in_its_usage_help_and_errors` of sdk-usda-gats
    and `test_allow_remote_changes_nothing_on_this_read_server` of sdk-usda-wasde assert no help
    of `--allow-remote` — `mcp.INSTRUCTIONS` leaves, the hook takes no server, `main` builds the
    server that it runs, so a patch of the module's `server` no longer stops it and those tests
    would serve over stdio, and the help is one sentence for every server, a test of core's own
    answer that ADR-0063, decision 8, takes out of a source's tests (ADR-0063, decision 7).
