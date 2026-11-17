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
