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
