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
  - Hand-apply: `src/xippios/<package>/tasks.py` (every source) — `MCP_INSTRUCTIONS` holds
    the text that `mcp.py` held as `INSTRUCTIONS`, and a multi-tenant source's
    `MCP_BOUND_INSTRUCTIONS` the text it held as `BOUND_INSTRUCTIONS` — the rendered `mcp.py`
    builds its tool set with `ToolSet.from_tasks`, which reads both from the tasks module
    (ADR-0063, decision 7).
    `src/xippios/<package>/tasks_write.py` (sdk-cashctrl, sdk-google-mail) —
    `MCP_INSTRUCTIONS` and `MCP_BOUND_INSTRUCTIONS` hold the texts of `mcp_write.py` — the
    rendered `mcp_write.py` reads them from the write tasks module (ADR-0063, decision 7).
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — `MCP_LOOPBACK_ONLY = True` — the
    read server's hold to loopback is a declaration of the tasks module, and the rendered
    `mcp.py` passes no `loopback_only` (ADR-0063, decision 7).
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `TENANTS = Tenants(...,
    noun="organisation")` — the noun is the registry's, and neither the entry nor a lock
    takes one (ADR-0063, decision 7).
    `src/xippios/usda/gats/tasks.py` (sdk-usda-gats) and `src/xippios/usda/nass/tasks.py`
    (sdk-usda-nass) — `mcp_apply_options(namespace: argparse.Namespace) -> None` without
    `server`, its return and the import of `MCPServer` — `main` and a host call the hook with
    the parsed options alone (ADR-0063, decision 7).
    `tests/test_org_lock.py` (sdk-cashctrl) — `LOCK = TenantLock(TENANTS, DEMO)`, and
    `test_both_entry_points_bind_to_the_org` reads `MCP_INSTRUCTIONS` and
    `MCP_BOUND_INSTRUCTIONS` from `tasks` and `tasks_write` in place of `module.INSTRUCTIONS`
    and `module.BOUND_INSTRUCTIONS` — a lock given `noun` fails with a `TypeError`, and the
    server modules hold no text (ADR-0063, decision 7).
    `tests/test_entry_points.py` (sdk-cashctrl) — `test_the_server_names_stay` expects
    `mcp_write.server.name == "xippios-cashctrl"` — the write server takes its slug's name
    (ADR-0063, decision 7).
    `tests/test_account_lock.py` (sdk-google-mail) — `test_both_entry_points_bind_to_the_account`
    reads `MCP_BOUND_INSTRUCTIONS` from `tasks` and `tasks_write` in place of
    `module.BOUND_INSTRUCTIONS` — the server modules hold no text (ADR-0063, decision 7).
    `tests/test_contract.py` (sdk-google-mail, sdk-faostat, sdk-x) —
    `test_build_is_the_tool_set_the_entry_point_serves` compares `tools.instructions` with
    the tasks module's `MCP_INSTRUCTIONS` — `mcp.INSTRUCTIONS` leaves (ADR-0063, decision 7).
    `tests/test_tasks.py` (sdk-usda-esr, sdk-usda-psd) —
    `test_build_returns_the_tool_set_the_entry_point_serves` compares `tools.instructions`
    with `tasks.MCP_INSTRUCTIONS` — `mcp.INSTRUCTIONS` leaves (ADR-0063, decision 7).
    `tests/test_tasks.py` (sdk-usda-gats, sdk-usda-nass) —
    `test_the_package_contract_for_a_host` reads `tasks.MCP_INSTRUCTIONS`,
    `test_a_host_applies_the_options_as_the_entry_point_does` calls
    `tools.apply_options(tools.option_defaults())`, the tests of the hook call
    `tasks.mcp_apply_options(namespace)` and compare no server
    (`test_the_mcp_server_refuses_a_series_beyond_its_ceiling_before_any_request` and
    `test_the_python_api_spans_60_months` of sdk-usda-gats,
    `test_the_hooks_apply_the_option_through_cores_parser` and
    `test_the_mcp_server_refuses_a_split_beyond_its_ceiling_before_any_call` of
    sdk-usda-nass), and `test_the_entry_point_applies_series_months_or_exits_with_status_2`
    and `test_the_entry_point_applies_split_years_or_exits_with_status_2` patch
    `MCPServer.run` on the class and call `main(build, argv=[...])` — `main` builds the
    server that it runs, so a patch of the module's `server` no longer stops it and those
    tests would serve over stdio (ADR-0063, decision 7).
    `tests/test_tasks.py` (sdk-comtrade, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass,
    sdk-usda-wasde) and `tests/test_contract.py` (sdk-faostat, sdk-x) — no assertion that
    the help of `--allow-remote` says `changes nothing: this read server is not held to
    loopback` — the help is one sentence for every server, a test of core's own answer that
    ADR-0063, decision 8, takes out of a source's tests (ADR-0063, decision 7).
