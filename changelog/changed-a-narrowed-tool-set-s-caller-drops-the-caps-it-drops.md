- A host that narrows a tool set with `dataclasses.replace` drops the cap of each task it drops
  in the same call, `caps=` beside `tasks=`, as ADR-0063, decision 4, and `ToolSet`'s docstring
  now say: the copy is checked as a new tool set, whose check refuses a key of `caps` that names
  no task with a `ValueError` naming the key. The code does not change, and the check that
  catches a misspelled key of a source's `MCP_CAPS` stands.
  (ADR-0063, https://github.com/xippios/sdk-core/issues/565)
