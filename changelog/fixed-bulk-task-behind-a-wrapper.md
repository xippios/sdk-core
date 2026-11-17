- `register_tasks` and `router_from_tasks` skip a bulk task behind a wrapper whose own
  `__module__` names another module, a tenant lock's, when its `__wrapped__` leads to the
  task. A wrapper that keeps neither wraps `tool_functions(tasks)`, which leaves the bulk
  tasks out first.
  (ADR-0019, https://github.com/xippios/sdk-core/issues/170,
  https://github.com/xippios/sdk-core/issues/155)
