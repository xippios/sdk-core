- A tool's description is the text of its task's docstring before `Args:`, where it was the
  whole docstring, and the MCP adapter carries each argument's text under `Args:` into the
  tool's input schema, unless the parameter's `Annotated` metadata declares a description of its
  own. A fourth collected test of the family check fails a description of 1,000 characters or
  more, read and write tools alike, so what one argument needs goes to its line under `Args:`.
  (ADR-0063, §8, https://github.com/xippios/sdk-core/issues/485)
  - Hand-apply: `src/xippios/<package>/tasks.py` (sdk-cashctrl, sdk-comtrade, sdk-eurostat,
    sdk-faostat, sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd,
    sdk-usda-wasde) — the docstring of each read task whose text before `Args:` holds 1,000
    characters or more is trimmed under the bound, what one argument needs moved to its line
    under `Args:`, 68 tools on the sources' `main` on 2026-11-24: sdk-cashctrl's 6,
    sdk-comtrade's 10, sdk-eurostat's 11, sdk-faostat's 2, sdk-usda-esmis's 3, sdk-usda-esr's 6,
    sdk-usda-gats's 15, sdk-usda-nass's 4, sdk-usda-psd's 4 and sdk-usda-wasde's 7 —
    `test_family_tool_descriptions_stay_under_the_bound` names each tool over it (ADR-0063,
    decision 9).
    `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — the docstrings of its 10 write tasks
    over the bound are trimmed likewise — the test holds the write server's tools as well
    (ADR-0063, decision 9).
    `tests/test_tasks.py` (sdk-eurostat, sdk-usda-nass) — sdk-eurostat's
    `test_get_data_tool_schema_lists_the_enumerations` compares the property `lang` with its
    description, and sdk-usda-nass's
    `test_a_one_year_task_says_an_empty_answer_may_be_a_year_not_yet_published` reads
    `UNPUBLISHED_YEAR` in the description of the property `year`, where its 13 tasks write it
    under `Args:` — the property carries its argument's text, and the tool's description stops
    at `Args:` (ADR-0063, decision 9).
    `tests/test_tasks_write.py` (sdk-cashctrl) —
    `test_the_write_tool_schemas_show_snake_case_inside_lists` compares the property `confirm`
    with its description — the property carries its argument's text (ADR-0063, decision 9).
    `tests/test_slices.py` (sdk-usda-esr) — `test_slice_tool_names_and_the_field_schema` compares
    the property `field` with its description — the property carries its argument's text
    (ADR-0063, decision 9).
