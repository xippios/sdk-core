- Core defines the types of the package contract by which a host serves a source:
  `EnvVar(name_or_pattern, *, secret, required)` from `xippios.core`, a variable the package
  needs, and `ToolSet` from `xippios.core.mcp`, what its `build(**options)` returns: its tasks
  as its lock binds them, caps, instructions, version, `main`'s two hooks, `read_only` and
  `loopback_only`. `build_server(tool_set)` builds a source's server from its tool set,
  `register_tasks(server, tool_set)` registers one on a server a host builds from several,
  and `tool_set.option_defaults()` gives the options its hooks take without a command line.
  (ADR-0023, ADR-0026, §7, §8, https://github.com/xippios/sdk-core/issues/245)
  - Hand-apply: `src/xippios/<package>/_client.py` — declare the variables it reads as
    `EnvVar` entries, in the list sdk-template 0.4.0 renders beside `SOURCE`
    (https://github.com/xippios/sdk-template/issues/81) — the file is the source's own, and a
    host reads the list.
    `src/xippios/<package>/mcp.py` — `server = build_server(SOURCE, [getattr(tasks, name) for
    name in tasks.__all__], version=..., instructions=..., caps=...)` → `build()` returning
    `ToolSet(SOURCE, tool_functions(tasks), caps=..., instructions=..., version=...,
    add_options=..., apply_options=...)`, `server = build_server(build())`, and `main` given
    the tool set's hooks in place of `getattr(tasks, "mcp_add_options", None)` — sdk-template
    0.4.0 renders it (https://github.com/xippios/sdk-template/issues/159), so a host serves
    what the entry point serves.
    `src/xippios/cashctrl/mcp.py` (sdk-cashctrl) — `build(lock)` returning `build_server(...)`
    → returning `ToolSet(SOURCE, bind_tasks(tool_functions(tasks), lock), ...)`, `server =
    build_server(build())`, and the serve command given `lambda lock:
    build_server(build(lock))` — its render is changed by hand.
    `src/xippios/cashctrl/mcp_write.py` (sdk-cashctrl) — as `mcp.py`, the tool set
    `read_only=False` and the server `build_server(build(), name="xippios-cashctrl-write")`
    — as above.
    `src/xippios/google/mail/mcp.py` (sdk-google-mail) — as sdk-cashctrl's `mcp.py`, the
    tool set `loopback_only=True` (ADR-0025, D-a) — as above.
    `src/xippios/google/mail/mcp_write.py` (sdk-google-mail) — as sdk-cashctrl's
    `mcp_write.py` — as above.
    `src/xippios/mcp/packages.py` (xippios-mcp) — `<path>.mcp.server` and `<path>.tasks`
    (`mcp_write` and `tasks_write` for `:write`), `tasks.__all__` and `MCP_CAPS`, lines 135
    to 159, and `Package.server`, `functions`, `tools` and `caps`, lines 69 to 72 → the
    `ToolSet` of `<path>.mcp.build()` (`mcp_write.build()`), its tools the `__name__` of
    each of `tool_set.tasks` — the contract carries what the host read by name.
    `src/xippios/mcp/servers.py` (xippios-mcp) — `_package_built`, lines 99 to 113, the
    package's own server and its `is_write_server` check → `build_server(tool_set)` per
    endpoint, its kind `tool_set.read_only`, and `_host_built`, lines 127 to 150,
    `register_tasks(server, slug, [package.functions[name] for name in kept], caps=caps or
    None, read_only=not package.ref.write)` → `register_tasks(server,
    dataclasses.replace(tool_set, tasks=kept, caps=cut))`, which carries `loopback_only`
    too, then `tool_set.apply_options(tool_set.option_defaults(), server)` for a tool set
    with hooks — a server the host builds lacked the package's hooks, version, instructions
    and hold (ADR-0026, amendment 2026-10-30, part (a)).
    `src/xippios/mcp/app.py` (xippios-mcp) — `_check_mounted_once`, line 98 and lines 142
    on, goes — every endpoint's server is built from its tool set, so no server object
    serves two endpoints.
