- A tool set alone builds a server, and it is checked when it is built: `build_server(tool_set,
  *, name=None)` and `register_tasks(server, tool_set)` take a `ToolSet` alone, the slug forms and
  the default `cap` leave, and the checks of a write task's `confirm`, of a cap's key and of a
  paged cap run when the tool set is made, which now also refuses a paged cap for a task that
  takes `start` and leaves the tasks of `BULK_TASKS` out. `is_write_server` and
  `is_loopback_only` leave, since the tool set's `read_only` and `loopback_only` say the same, and
  `assert_write_tools` takes the write tool set in place of the write server and `source=`.
  `tool_functions` and `tool_name` come from `xippios.core` too, `tool_name` takes a task's name
  as text, and the MCP adapter's refusal of an argument ends with "Nothing was sent."
  (ADR-0063, ADR-0026, ADR-0036, ADR-0038, ADR-0047, §7, §8,
  https://github.com/xippios/sdk-core/issues/476)
  - Hand-apply: `tests/test_tasks.py` (sdk-cashctrl) — the servers of
    `test_a_history_over_its_cap_names_the_filters_and_where_to_resume` and
    `test_a_report_over_its_cap_is_cut_by_its_rows_with_a_note_naming_the_period` built as
    `build_server(ToolSet(SOURCE, [task], caps=...))`, and the refusals that
    `test_list_accounts_as_a_tool` and `test_list_orders_as_a_tool` compare whole ending with
    `. Nothing was sent.` — a slug beside its tasks fails with a `TypeError`, and the adapter's
    refusal says that the tool did not run (ADR-0063, decisions 1 and 6).
    `tests/test_tasks_write.py` (sdk-cashctrl) — `test_the_write_server_serves_write_tasks_only`
    calls `assert_write_tools(mcp_write.build(), list(WRITE_TASKS.values()),
    read_server=read_server, router=router)` — the check reads the write tool set, and a server
    or `source=` fails it (ADR-0063, decision 5).
    `tests/test_org_lock.py` (sdk-cashctrl) — the refusal that
    `test_the_bound_read_server_reaches_the_bound_organisation_only` compares ends with
    `. Nothing was sent.` — the adapter's refusal says that the tool did not run (ADR-0063,
    decision 6).
    `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — no `ResultCap(paged=True)` in `MCP_CAPS` for
    `list_journal_entries`, `list_persons`, `list_orders` or `list_history`, whose tasks take
    `start` — the tool set refuses it when `mcp.py` builds it, and every test that imports the
    server fails (ADR-0063, decision 3).
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — no paged cap for `get_thread`, whose
    task takes `start` — the tool set refuses it when `mcp.py` builds it (ADR-0063, decision 3).
    `tests/test_contract.py` (sdk-google-mail) — `test_the_read_server_is_held_to_loopback_bound_or_not`
    reads `mcp.build().loopback_only` and `mcp_write.build().read_only` in place of
    `is_loopback_only`, and the refusals of `test_a_tool_refuses_an_argument_it_does_not_declare`
    and `test_a_bound_server_refuses_a_call_that_still_names_the_account` end with
    `. Nothing was sent.` — the import of `is_loopback_only` fails the module (ADR-0063,
    decisions 5 and 6).
    `tests/test_tasks_write.py` (sdk-google-mail) —
    `test_the_read_server_is_no_write_server_and_keeps_its_tools` reads the `read_only` of
    `mcp_write.build()` and `mcp.build()` in place of `is_write_server`, and
    `test_the_write_server_serves_the_write_tasks_only` calls
    `assert_write_tools(mcp_write.build(), list(WRITE_TASKS.values()), read_server=read_server,
    router=router)` — the import of `is_write_server` fails the module, and the check reads the
    write tool set (ADR-0063, decision 5).
    `tests/test_account_lock.py` (sdk-google-mail) — the refusal that
    `test_the_bound_read_server_answers_for_the_bound_account_only` compares ends with
    `. Nothing was sent.` — the adapter's refusal says that the tool did not run (ADR-0063,
    decision 6).
    `tests/test_tasks.py` (sdk-faostat) — the servers of `test_get_data_tool_cap_note_names_paging`,
    `test_get_series_tool_cap_note_names_since_and_until`,
    `test_list_task_tool_cap_note_names_search` and
    `test_list_bulk_datasets_tool_cap_note_names_search` built as
    `build_server(ToolSet(SOURCE, [task], caps=...))` — a slug beside its tasks fails with a
    `TypeError` (ADR-0063, decision 1).
    `tests/test_slices.py` (sdk-usda-psd) — the server of
    `test_a_cut_series_names_the_filters_that_narrow_it` built as
    `build_server(ToolSet("usda-psd", [tasks.get_time_series], caps=...))` — a slug beside its
    tasks fails with a `TypeError` (ADR-0063, decision 1).
    `tests/test_contract.py` (sdk-faostat, sdk-x) — the refusal that
    `test_a_tool_refuses_an_argument_it_does_not_declare` compares ends with
    `. Nothing was sent.` — a test of core's own answer, which ADR-0063, decision 8, takes out of
    a source's tests at this adoption (ADR-0063, decision 6).
    `tests/test_tasks.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-wasde, sdk-usda-gats,
    sdk-usda-nass, sdk-comtrade, sdk-eurostat, sdk-x) — the refusals that
    `test_the_adapters_refuse_a_bad_argument_before_the_task_runs`,
    `test_a_tool_refuses_an_argument_it_does_not_declare`,
    `test_a_tool_error_answer_is_flagged_and_an_undeclared_argument_refused`,
    `test_get_data_tool_refuses_an_argument_its_schema_refuses` and
    `test_an_argument_the_schema_refuses_is_an_error_answer` compare whole end with
    `. Nothing was sent.` — a test of core's own answer, which ADR-0063, decision 8, takes out of
    a source's tests at this adoption (ADR-0063, decision 6).
    `src/xippios/mcp/packages.py` (xippios-mcp) — a package's tools read from its tool set,
    `tool_name(tool_set.source, fn)` for each `fn` of `mcp.build().tasks`, in place of the import
    of `xippios.core._tasks.is_bulk_task` — a tool set holds tools alone, and the host reads no
    private name of core (ADR-0063, decision 4).
    `src/xippios/mcp/servers.py` (xippios-mcp) — `register_tasks(server, tool_set)` with
    `dataclasses.replace(tool_set, tasks=..., caps=...)` for an include or exclude list, the write
    rule from `tool_set.read_only`, and `register_tasks` and `quiet_request_logging` from
    `xippios.core.mcp` — the slug form and `is_write_server` left (ADR-0063, decisions 1, 4 and
    5).
    `src/xippios/mcp/app.py` and `src/xippios/mcp/cli.py` (xippios-mcp) — `quiet_request_logging`
    from `xippios.core.mcp` in place of `xippios.core.mcp.server` — a host takes core's names by
    their pinned path (ADR-0063, decision 4).
    `tests/test_servers.py` (xippios-mcp) — `test_a_group_with_an_exclude_list`,
    `test_the_write_server_alone_is_the_packages_own` and
    `test_the_write_server_with_an_exclude_list` read `Built.write` or the package's tool set in
    place of `is_write_server` — the import of `is_write_server` fails the module (ADR-0063,
    decision 5).
