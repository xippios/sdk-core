# ADR-0063: The server from a tool set

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/476 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/476

## Context

Core 0.4.0 gave the package contract a tool set, `ToolSet`, which a source's `build(**options)`
returns, and let `build_server` and `register_tasks` take one beside their older forms, a source
slug with its tasks and a keyword for each field (ADR-0026, amendment 2026-11-18, points c and d).
Every source builds its server from a tool set since its adoption of core 0.4.0, and the slug forms
lived on in tests, 128 calls of core's and seven of three sources', and in the host xippios-mcp,
which pins core 0.3, calls `register_tasks(server, slug, tasks, ...)` and imports the private
`xippios.core._tasks.is_bulk_task` and `is_write_server` from `xippios.core.mcp.server`. The checks
of a declaration ran when a server registered its tasks, so a source's own tests met a write task
without `confirm`, a cap for a name that is no task or a paged cap that its task does not fit only
once they built a server. `is_write_server` and `is_loopback_only` read two registries that
`register_tasks` filled, which said what a tool set's `read_only` and `loopback_only` already say.
A tool's description was the task's whole docstring: the 170 tools of the twelve sources carried
316,016 characters at their tags.

The maintainer's answer on https://github.com/xippios/sdk-core/issues/476 made the tool set the one
way to build and run a source's server, with one entry and a tool set that core builds from the
tasks module. His answer on https://github.com/xippios/sdk-core/issues/485 kept the MCP runtime in
core with three trims, left HTTP untouched, had the host import nothing private of core, and bound
a tool's description, which part 7 of that answer made exact on the same day. The answer on
https://github.com/xippios/sdk-core/issues/477 moved the contract tests into the family check, the
answer on https://github.com/xippios/sdk-core/issues/479, part 3, refused a paged cap for a task
that takes `start`, and the answer on https://github.com/xippios/sdk-core/issues/481, part 1, has
every refusal before a request say that nothing was sent.

This record states the server from a tool set whole. It replaces points a, c and d of ADR-0026's
amendment of 2026-11-18 and ADR-0038's decision 1, and restates what stands of them, and it
changes decisions 7, 8, 9 and 12 of ADR-0036 and decision 2 of ADR-0047. Decisions 1 to 6 are core
0.5.0's change of the builders; decision 7 is its change of the entry, and decisions 8 and 9 its
change of the family check.

## Decision

1. **A tool set alone builds a server.** `build_server(tool_set, *, name=None)` builds a package's
   server, named `xippios-<source>` unless `name` names it, with the tool set's version and
   instructions, and `register_tasks(server, tool_set)` registers one tool set on a server, so a
   host builds one server from the tool sets of several packages, each tool with its own package's
   caps. The forms that took a slug and its tasks, the default `cap` of every tool and the refusal
   of an argument beside a tool set leave. A tool's own cap is keyed by its task function's
   `__name__` (`list_partners`, a sync facade's with `_async` stripped), never the tool name with
   the source prefix; a tool without one takes the family default, 200 rows or 64 KB, and a field
   that its own cap leaves unset takes the family default too (ADR-0038, decisions 2 to 5).
2. **The package contract and its names.** `xippios.core.EnvVar(name_or_pattern, *, secret,
   required)` is a variable that a package needs, by name or by a pattern such as
   `EXAMPLE_<NAME>_API_KEY` for one per tenant, and names a variable without reading one. A
   source's `_client.py` declares its variables so, and its `mcp.py` defines `build(**options)`,
   which returns its `ToolSet`: `source`, its `tasks` as its lock binds them, `caps`, where `None`
   is no cap of a tool's own, `instructions`, `version`, the two hooks `add_options` and
   `apply_options`, `read_only` and `loopback_only`. Its module-level `server` is
   `build_server(build())`, and `build` takes no `transport_security`, which a host passes where it
   serves the server. `tool_functions(tasks)` gives the functions of `tasks.__all__` that become
   tools, `BULK_TASKS` read from the module that it is given, and refuses an entry whose function
   carries another `__name__`, so a task's name, its tool's name and its `MCP_CAPS` key are one
   name. `tool_functions` and `tool_name` are exported from `xippios.core`, since neither needs the
   `mcp` extra, and stay in the list of `xippios.core.mcp`, where the sources import them today;
   `tool_name` takes a task's name as text too, for a refusal below `tasks.py` that names a tool,
   as conventions §8 asks of an error that names another task.
3. **A tool set is checked when it is built.** The three checks of a declaration run in the making
   of a `ToolSet`, the second trim of https://github.com/xippios/sdk-core/issues/485, part 1, so a
   source's own tests fail on a declaration that no server could serve before any server is built:
   every key of `caps` names one of its tasks; every task of a tool set that
   writes takes `confirm: bool = False`; and a paged cap fits its task, refused for every task of a
   tool set that writes, since a continuation would repeat a confirmed write, for a task that takes
   `offset`, which the adapter's argument would shadow, and for a task that takes `start`, which
   pages upstream itself, so that its cut answer resumes with `start` and a continuation would send
   upstream a request (ADR-0061, decision 9). Each refusal is a `ValueError` that names the tool
   and says why. A tool set holds tools alone: a task that its module names in `BULK_TASKS` is left
   out, a wrapper whose `__wrapped__` leads to one included, so a cap keyed to it is refused as
   naming no task. `dataclasses.replace` gives a narrowed copy and checks it as a new tool set.
4. **What a host reads.** The host is a consumer that reads a source's tool set, and no public name
   enters for it:
   - a tool set holds tools alone, so the names of a source's tools are
     `tool_name(tool_set.source, fn)` for each `fn` of `tool_set.tasks`, and no caller needs
     `is_bulk_task`;
   - `ToolSet`, `build_server`, `register_tasks`, `LOOPBACK_HOSTS` and `quiet_request_logging`
     are taken by the pinned path `xippios.core.mcp`, never by `xippios.core.mcp.server` or
     `xippios.core.mcp.cli`, and `tool_name`, `tool_functions`, `ResultCap` and `ConfigError` from
     `xippios.core`;
   - a narrowed copy of a tool set, for a host's list of tools, is `dataclasses.replace`, which
     checks the copy as decision 3 checks a tool set, so the caller drops the cap of each task it
     drops, with `caps=` beside `tasks=` in the same `replace`, else the check of decision 3
     refuses the copy with a `ValueError` naming the key;
   - a tool set's hooks are applied without a server and without a command line, by
     `option_defaults()` and the hook of decision 7, so a host holds a package's options at the
     values its entry point holds without options; an option that an empty command line leaves
     without a value raises `ValueError` naming the source, where argparse would end the process;
   - `mcp_call` and `mcp_call_text` of `xippios.core.testing` stay the helpers of a host's tests.

   A host binds no tenant in 0.5.0: a tenant source's own entry does, and through a host its tools
   take the tenant as an argument.
5. **The write rule and the hold to loopback are the tool set's.** `is_write_server` and
   `is_loopback_only` leave with their two registries, since a tool set's `read_only` and
   `loopback_only` say the same (https://github.com/xippios/sdk-core/issues/485, part 1, the third
   trim). A tool set that writes marks its tools read-only false and destructive, and one that
   writes or is `loopback_only` holds the server it is registered on to loopback, which the entry
   serves over `--http` on a host of `LOOPBACK_HOSTS` only unless `--allow-remote` is passed,
   since it carries no authentication (ADR-0036, decision 9; ADR-0025, D-a). A host reads both
   fields from the tool set and applies the rule itself where it serves a server without the
   entry (ADR-0026, decision 5). `assert_write_tools` takes the write tool set,
   `assert_write_tools(mcp_write.build(), write_tasks, ...)`: it fails a tool set that does not
   write, builds the write server from it as `mcp_write.server` is built, and reads the source
   from it, so its `source` leaves.
6. **The MCP adapter's refusal says that nothing was sent.** An argument that a tool does not
   declare and arguments that its schema refuses are answered before the tool runs as
   `error: InvalidRequestError: <argument>: <message>. Nothing was sent.`, flagged `is_error`, as
   `yaer: Not an argument of this tool; it takes series_id, year. Nothing was sent.` The sentence
   is the MCP adapter's alone: the HTTP router answers as before
   (https://github.com/xippios/sdk-core/issues/485, part 2), and core's other refusals before a
   request take it in the change of each.
7. **One entry runs the server of the tool set.** `main(build, *, tenants=None, check=None,
   argv=None)` is the one entry function: it takes the package's `build`, reads the option hooks
   from the tool set that `build` returns, builds the server that it runs, and binds a tenant where
   `tenants` is given, its `--<param>` checked by `tenants.require` and then by `check` before the
   bound server is built. `serve_tenants`, `main`'s two hook parameters and the branch for a
   `build` that returns a server leave. Core builds the tool set from a tasks module, `tasks.py` or
   `tasks_write.py`, as `tool_functions` reads its `BULK_TASKS`: its tools, `MCP_CAPS`, the two
   option hooks `mcp_add_options` and `mcp_apply_options`, and `MCP_INSTRUCTIONS`, so a rendered
   `mcp.py` holds no line that a source edits and keeps its module-level `server`. `apply_options`
   takes the parsed options alone and returns nothing, since no hook uses the server, so `ToolSet`
   no longer imports the MCP SDK (the first trim). A read tool set's hold to loopback becomes a
   declaration of its `tasks.py`, which sdk-google-mail alone makes, the noun of a tenant goes to
   the `Tenants` registry, which sdk-cashctrl alone gives, and sdk-cashctrl's write server takes
   its slug's name, `xippios-cashctrl`, as sdk-google-mail's does. The three wordings of the help
   of `--allow-remote` and `build_parser(server=)` leave, and no file under `http/` changes.
8. **The family check holds the contract.** Three collected tests enter the family check: that
   `mcp.build()` returns a `ToolSet` of `_client.SOURCE`, that `mcp.server` lists the tools of
   `build_server(mcp.build())` and that `mcp.ENV_VARS` is `_client.ENV_VARS`, and of a write
   server that `mcp_write.build()` returns a tool set of the source that writes; that
   `[project.scripts]` names the entry points of conventions §8, each at its module's `run`; and
   that every name of `tasks.__all__` and `tasks_write.__all__` is the package's own attribute. A
   source does not test again what core's adapters answer for every source, by one sentence of
   conventions §10, and keeps the test of a refusal of its own; the live probe
   `test_upstream_answers` leaves with nothing in its place, since every task has a live smoke
   test (https://github.com/xippios/sdk-core/issues/477). The tools of a write server stay the
   source's to test with `assert_write_tools` (ADR-0042, decision 1).
9. **A tool's description and its bound.** A tool's description is the text of its task's
   docstring before `Args:`, under 1,000 characters, and the adapter carries each argument's text
   into the tool's input schema. A fourth collected test of the family check holds the bound, and
   conventions §8 state it in place of the sentence that makes the whole docstring the
   description. Each source trims at its adoption: 78 of the 170 tools pass the bound today
   (https://github.com/xippios/sdk-core/issues/485, part 7).

## Consequences

- The sources change at their adoption of core 0.5.0, named by file in the release's changelog:
  seven test calls of the slug form in three sources build a tool set, two in sdk-cashctrl, four
  in sdk-faostat and one in sdk-usda-psd; sdk-google-mail's tests of the two predicates read the
  tool set's fields; sdk-cashctrl and sdk-google-mail pass `assert_write_tools` their write tool
  set; and no source pages a tool whose task takes `start`, which are sdk-cashctrl's
  `list_journal_entries`, `list_persons`, `list_orders` and `list_history` and sdk-google-mail's
  `get_thread` today.
- The host moves to `register_tasks(server, tool_set)` and the tool set's fields, and imports
  nothing private of core, at its adoption of core 0.5.0, which brings it from core 0.3.
- The consumers of the names that decision 2 adds to the root, by ADR-0059, decisions 1 and 2:
  `tool_name` from `xippios.core`, and its text form, serve the refusals that name another
  task's tool, which sdk-usda-esmis and sdk-eurostat write by hand since their adoption of core
  0.4.0, the second saying why in its decision 4 (https://github.com/xippios/sdk-usda-esmis/pull/46,
  https://github.com/xippios/sdk-eurostat/pull/68, as https://github.com/xippios/sdk-core/issues/336
  asks), and the host, which names a source's tools with it (decision 4); `tool_functions` from
  `xippios.core` serves the host under the package contract (ADR-0059, decision 4) and every
  source's rendered `mcp.py`, which calls the same function today.
- The pieces with one consumer that stay, by ADR-0059, decision 2: `loopback_only`, which
  sdk-google-mail declares and the host reads; the noun of a tenant, sdk-cashctrl's; and
  `option_defaults()`, which the host reads under the package contract (ADR-0059, decision 4)
  and the tests of sdk-usda-nass and sdk-usda-gats call.
- ADR-0026, ADR-0038, ADR-0036 and ADR-0047 each take one sentence that points here, and their
  other decisions stand.
- Conventions §7 and §8, the README and the docstrings of `xippios.core.mcp`, `ToolSet`,
  `build_server`, `register_tasks`, `tool_name` and `assert_write_tools` state decisions 1 to 6,
  and the changes that build decisions 7 to 9 state theirs.

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/476: in decision 7 core reads
from a tasks module, with `ToolSet.from_tasks` and each where the module declares it, beside its
tools, `MCP_CAPS`, the two option hooks and `MCP_INSTRUCTIONS`, also `MCP_LOOPBACK_ONLY = True`,
the declaration of a read tool set's hold to loopback, which sdk-google-mail makes, and
`MCP_BOUND_INSTRUCTIONS`, the text of a server bound to one tenant that `tenant_instructions`
takes as `bound`, which sdk-cashctrl and sdk-google-mail give, while the other decisions and the
rest of decision 7 stand as written.
