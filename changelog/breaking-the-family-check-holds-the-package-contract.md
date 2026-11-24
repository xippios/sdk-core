- The family check holds the package contract, the entry points and the re-export of the tasks,
  which every source tested for itself: `mcp.build()` returns a `ToolSet` of `_client.SOURCE`,
  `mcp.server` lists the tools of `build_server(mcp.build())`, `mcp.ENV_VARS` is
  `_client.ENV_VARS` and a write server's `mcp_write.build()` returns a tool set that writes,
  `[project.scripts]` names the entry points of §8, each at its module's `run`, and the package
  re-exports every task of `tasks.__all__` and `tasks_write.__all__`. A source no longer tests
  these, nor what core's adapters and entry answer for every source, and its live suite keeps
  no probe of upstream's base URL beside the smoke test of each task.
  (ADR-0063, §8, §10, https://github.com/xippios/sdk-core/issues/477)
  - Hand-apply: `tests/test_live.py` (sdk-cashctrl, sdk-comtrade, sdk-eurostat, sdk-faostat,
    sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd, sdk-usda-wasde,
    sdk-x) — `test_upstream_answers` leaves, sdk-cashctrl's keyed one too, with each import that
    only it uses and the sentence of the module's docstring that names or counts it — every
    task's smoke test reaches upstream (ADR-0063, decision 8).
    `tests/test_tasks.py` (sdk-cashctrl, sdk-comtrade, sdk-eurostat, sdk-usda-esmis,
    sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd, sdk-usda-wasde) — these leave:
    sdk-cashctrl's `test_an_unknown_account_is_an_error_text_for_the_tool` and the assertions of
    a refused argument in `test_list_accounts_as_a_tool`, `test_list_accounts_is_a_post_route`,
    `test_list_custom_fields_as_a_route` and `test_list_cost_centers_is_a_post_route`,
    sdk-comtrade's `test_a_host_serves_what_the_entry_point_serves`,
    `test_a_tool_refuses_an_argument_it_does_not_declare`,
    `test_an_error_answer_is_flagged_beside_its_text`,
    `test_a_route_answers_an_argument_its_schema_refuses_as_problem_details` and their helper
    `_answer`, sdk-eurostat's `test_get_data_route_refuses_an_argument_its_schema_refuses`,
    sdk-usda-esmis's and sdk-usda-wasde's `test_the_package_re_exports_the_tasks`, sdk-usda-esr's
    and sdk-usda-psd's `test_the_adapters_refuse_a_bad_argument_before_the_task_runs`,
    sdk-usda-gats's and sdk-usda-nass's
    `test_a_tool_error_answer_is_flagged_and_an_undeclared_argument_refused` and
    `test_a_route_answers_a_refused_argument_as_problem_details`, sdk-usda-wasde's
    `test_an_error_answer_sets_is_error`, `test_an_answer_with_data_is_no_error`,
    `test_a_tool_refuses_an_argument_it_does_not_declare`,
    `test_a_route_refuses_an_argument_its_schema_refuses_as_problem_details` and their helper
    `tool_result`, the tests of the entry's usage and of the help of `--allow-remote`
    (sdk-comtrade's and sdk-usda-nass's
    `test_the_entry_point_names_itself_in_its_usage_and_errors`, sdk-usda-esr's
    `test_the_entry_point_names_itself`, sdk-usda-gats's
    `test_the_entry_point_names_itself_in_its_usage_help_and_errors` and sdk-usda-wasde's
    `test_allow_remote_changes_nothing_on_this_read_server`), and the assertions of
    `mcp.build()`'s source, `mcp.server` and `ENV_VARS` and of the re-export in
    sdk-comtrade's `test_the_package_contract_names_the_key_and_builds_the_served_tools`,
    sdk-usda-esmis's and sdk-usda-wasde's `test_the_package_reads_no_variable` and
    `test_build_is_the_tool_set_the_server_serves`, sdk-usda-esr's
    `test_the_package_exports_the_tasks`, sdk-usda-esr's and sdk-usda-psd's
    `test_build_returns_the_tool_set_the_entry_point_serves` and sdk-usda-gats's and
    sdk-usda-nass's `test_the_package_contract_for_a_host`, whose other assertions stay — each
    holds what the family check or core's own tests hold for every source (ADR-0063,
    decision 8).
    `tests/test_contract.py` (sdk-cashctrl, sdk-faostat, sdk-google-mail, sdk-x) — these leave:
    sdk-faostat's, sdk-google-mail's and sdk-x's
    `test_a_tool_refuses_an_argument_it_does_not_declare`, sdk-faostat's and sdk-x's
    `test_a_tool_flags_its_error_answer`,
    `test_a_route_answers_an_argument_its_schema_refuses_as_problem_details` and
    `test_the_entry_point_help_says_allow_remote_changes_nothing_here`, sdk-x's
    `test_a_tool_answer_with_data_is_not_flagged` and its helper `call`, sdk-google-mail's
    `test_a_bound_server_refuses_a_call_that_still_names_the_account`,
    `test_an_error_answer_is_flagged` and
    `test_a_route_answers_a_refused_argument_as_problem_details`, and the assertions that
    `mcp.ENV_VARS` and `mcp_write.ENV_VARS` are `_client.ENV_VARS` in sdk-cashctrl's
    `test_env_vars_name_the_organisations_and_their_pair_secret`, sdk-faostat's
    `test_env_vars_name_the_account_both_secret_and_required`, sdk-google-mail's
    `test_env_vars_name_the_account_list_the_refresh_tokens_and_the_client_pair` and sdk-x's
    `test_env_vars_name_the_bearer_token_secret_and_required`, and those of `mcp.build()`'s
    source, its `read_only` and `mcp.server` in sdk-faostat's, sdk-google-mail's and sdk-x's
    `test_build_is_the_tool_set_the_entry_point_serves`, whose other assertions stay — each holds
    what the family check or core's own tests hold for every source (ADR-0063, decision 8).
    `tests/test_entry_points.py` (sdk-cashctrl) —
    `test_the_servers_are_read_and_write_with_no_alias` leaves — the family check holds the two
    entry points and no third (ADR-0063, decision 8).
    `tests/test_tasks_write.py` (sdk-cashctrl, sdk-google-mail) — sdk-cashctrl's
    `test_write_tools_are_the_write_tasks_with_their_parameters` and sdk-google-mail's
    `test_write_tools_take_their_task_s_parameters_and_say_they_write` leave — the tools of the
    write server are `assert_write_tools`'s to hold, and their parameters and annotations core's
    adapter gives every source (ADR-0042, decision 1, ADR-0063, decision 8).
    `tests/test_lists.py` (sdk-usda-esr, sdk-usda-gats, sdk-usda-psd) —
    `test_every_list_task_is_exported` leaves — the family check holds the re-export of every
    task (ADR-0063, decision 8).
    `tests/test_slices.py` (sdk-usda-esr, sdk-usda-psd) — sdk-usda-psd's
    `test_every_slice_is_exported_as_a_tool` and the assertions of the re-export in
    sdk-usda-esr's `test_every_slice_is_exported` leave — the family check holds the re-export
    and the tools of every task (ADR-0063, decision 8).
    `tests/test_org_lock.py` and `tests/test_errors.py` (sdk-cashctrl), `tests/test_account_lock.py`
    (sdk-google-mail) — the assertions of core's answer to a refused argument in
    `test_the_bound_read_server_reaches_the_bound_organisation_only`,
    `test_a_rejection_is_an_invalid_request_for_both_adapters` and
    `test_the_bound_read_server_answers_for_the_bound_account_only` leave, and the assertions of
    the source's own refusal stay — core's adapters answer the same for every source
    (ADR-0063, decision 8).
