"""ToolSet: what a package's ``build(**options)`` returns, and the servers built from it.

``build_server`` builds a server from one tool set and a host one server from several
with ``register_tasks``, both from a tool set alone, and a tool set is checked when it is
built (ADR-0063, decisions 1 and 3). The tasks are the invented source's.
"""

import argparse
import ast
import dataclasses
import inspect
import sys
import types
from collections.abc import Callable
from typing import Annotated, Any

import pytest
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from xippios.core import Result, ResultCap, ResultMeta, TenantLock, Tenants, bind_tasks, sync
from xippios.core.mcp import ToolSet, build_server, main, register_tasks, tool_name
from xippios.core.testing import mcp_call, mcp_call_text


async def get_series_async(
    series_id: str,
    year: Annotated[int, Field(ge=2000, description="A year from 2000.")] = 2024,
) -> Result[list[str]]:
    """Fetch one series, a row per year since 2000.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
        year: The last year, from 2000, e.g. ``2024``.
    """
    rows = [f"{series_id}-{y}" for y in range(2000, year)]
    return Result[list[str]](data=rows, meta=ResultMeta(source="example", endpoint="series"))


get_series = sync(get_series_async)


def list_areas() -> Result[list[str]]:
    """List the 310 areas, a reference list an agent needs whole."""
    areas = [f"A{i:03d}" for i in range(310)]
    return Result[list[str]](data=areas, meta=ResultMeta(source="example", endpoint="areas"))


def list_regions() -> Result[list[str]]:
    """List the 310 regions of another source."""
    regions = [f"R{i:03d}" for i in range(310)]
    return Result[list[str]](data=regions, meta=ResultMeta(source="other", endpoint="regions"))


def delete_series(series_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete one series; a preview unless confirm is true.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
        confirm: Delete for real, e.g. ``true``; a preview otherwise.
    """
    return {"deleted": series_id if confirm else None}


def get_rows(
    org: str,
    limit: Annotated[int, Field(ge=1, le=100, description="Rows per page, 1 to 100.")] = 10,
) -> dict[str, object]:
    """List rows of one organisation.

    Args:
        org: A declared organisation, e.g. ``demo``.
        limit: Rows per page, e.g. ``10``.
    """
    return {"org": org, "limit": limit}


CEILING = {"years": 20}
"""A fictitious source's process-wide setting, which its entry point's option sets."""


def add_split_years(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--split-years", type=int, default=5)


def apply_split_years(namespace: argparse.Namespace) -> None:
    CEILING["years"] = namespace.split_years


AREAS_CAP = ResultCap(max_rows=400)


def example_tools() -> ToolSet:
    return ToolSet(
        "example",
        [get_series, list_areas],
        caps={"list_areas": AREAS_CAP},
        instructions="Example via xippios. Call example_list_areas first.",
        version="1.2.0",
        add_options=add_split_years,
        apply_options=apply_split_years,
    )


def test_a_tool_set_holds_what_a_package_serves() -> None:
    tools = example_tools()
    assert tools.source == "example"
    assert tools.tasks == (get_series, list_areas)
    assert dict(tools.caps) == {"list_areas": AREAS_CAP}
    assert tools.instructions == "Example via xippios. Call example_list_areas first."
    assert tools.version == "1.2.0"
    assert (tools.add_options, tools.apply_options) == (add_split_years, apply_split_years)
    assert (tools.read_only, tools.loopback_only) == (True, False)


def test_a_tool_set_takes_build_servers_defaults() -> None:
    tools = ToolSet("example", [get_series])
    assert (dict(tools.caps), tools.instructions, tools.version) == ({}, None, "")
    assert (tools.add_options, tools.apply_options) == (None, None)
    assert (tools.read_only, tools.loopback_only) == (True, False)


@pytest.mark.anyio
async def test_a_tool_set_takes_caps_none_as_no_caps() -> None:
    # Finding 1 of https://github.com/xippios/sdk-core/pull/288: §8's
    # caps=getattr(tasks, "MCP_CAPS", None) for a source without MCP_CAPS.
    tools = ToolSet("example", [get_series, list_areas], caps=None)
    assert dict(tools.caps) == {}
    areas = await mcp_call(build_server(tools), "example_list_areas", {})
    assert (len(areas["data"]), areas["note"][:20]) == (200, "showing 200 of 310 r")


def test_a_tool_set_keeps_a_read_only_copy_of_its_caps() -> None:
    caps = {"list_areas": AREAS_CAP}
    tools = ToolSet("example", [get_series, list_areas], caps=caps)
    caps["get_series"] = ResultCap(max_rows=1)
    assert dict(tools.caps) == {"list_areas": AREAS_CAP}
    with pytest.raises(TypeError):
        tools.caps["get_series"] = ResultCap(max_rows=1)  # type: ignore[index]


def test_a_tool_set_is_frozen_and_replace_narrows_it() -> None:
    tools = example_tools()
    with pytest.raises(dataclasses.FrozenInstanceError):
        tools.version = "2.0.0"  # type: ignore[misc]
    narrowed = dataclasses.replace(tools, tasks=[get_series], caps={})
    assert narrowed.tasks == (get_series,)
    assert narrowed.instructions == tools.instructions
    with pytest.raises(TypeError, match="entry 1 of tasks is no function"):
        dataclasses.replace(tools, tasks=[None])  # type: ignore[list-item]


def test_a_tool_set_refuses_an_empty_source_and_a_task_that_is_no_function() -> None:
    with pytest.raises(ValueError, match="source"):
        ToolSet("", [get_series])
    with pytest.raises(TypeError, match="entry 2 of tasks is no function"):
        ToolSet("example", [get_series, "list_areas"])  # type: ignore[list-item]


@pytest.mark.anyio
async def test_build_server_builds_a_server_from_one_tool_set() -> None:
    server = build_server(example_tools())
    assert server.name == "xippios-example"
    assert server.version == "1.2.0"
    assert server.instructions == "Example via xippios. Call example_list_areas first."
    names = {t.name for t in await server.list_tools()}
    assert names == {"example_get_series", "example_list_areas"}
    areas = await mcp_call(server, "example_list_areas", {})
    assert (len(areas["data"]), "note" in areas) == (310, False), "the tool's own cap"
    series = await mcp_call(server, "example_get_series", {"series_id": "C", "year": 2300})
    assert (len(series["data"]), series["note"][:20]) == (200, "showing 200 of 300 r")


def test_build_server_names_a_server_from_a_tool_set_as_told() -> None:
    server = build_server(example_tools(), name="xippios-example-write")
    assert server.name == "xippios-example-write"


def held_to_loopback(tool_set: ToolSet, monkeypatch: pytest.MonkeyPatch) -> bool:
    """Whether ``main`` refuses the server of ``tool_set`` over ``--http`` beyond loopback.

    ``MCPServer.run`` is replaced, so nothing is served either way.
    """
    runs: list[str] = []

    def run(self: MCPServer, transport: str = "stdio", **options: Any) -> None:
        runs.append(transport)

    monkeypatch.setattr(MCPServer, "run", run)
    try:
        main(lambda: tool_set, argv=["--http", "--host", "0.0.0.0"])
    except SystemExit as stopped:
        return stopped.code == 2
    assert runs == ["streamable-http"]
    return False


def test_a_tool_set_that_writes_or_is_held_is_served_on_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ADR-0063, decision 5: the hold is read from the tool set's read_only and loopback_only.
    writes = ToolSet("example", [delete_series], read_only=False)
    assert held_to_loopback(writes, monkeypatch)
    held = ToolSet("example", [get_series], loopback_only=True)
    assert (held.read_only, held.loopback_only) == (True, True)
    assert held_to_loopback(held, monkeypatch)
    assert not held_to_loopback(example_tools(), monkeypatch)


def test_the_slug_forms_are_gone() -> None:
    # ADR-0063, decision 1: a tool set alone, which carries every argument but the name.
    with pytest.raises(TypeError):
        build_server("example", [get_series])  # type: ignore[arg-type, call-arg]
    with pytest.raises(TypeError):
        build_server(example_tools(), version="2.0.0")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        register_tasks(MCPServer("x"), "example", [get_series])  # type: ignore[arg-type, call-arg]
    with pytest.raises(TypeError):
        register_tasks(MCPServer("x"), example_tools(), cap=ResultCap(max_rows=5))  # type: ignore[call-arg]


@pytest.mark.anyio
async def test_a_host_builds_one_server_from_two_tool_sets_each_with_its_own_caps() -> None:
    other = ToolSet("other", [list_regions], version="0.3.0")  # the default cap
    server = MCPServer("example-host")
    names = register_tasks(server, example_tools()) + register_tasks(server, other)
    assert names == ["example_get_series", "example_list_areas", "other_list_regions"]
    assert {t.name for t in await server.list_tools()} == set(names)
    areas = await mcp_call(server, "example_list_areas", {})
    assert (len(areas["data"]), "note" in areas) == (310, False)
    regions = await mcp_call(server, "other_list_regions", {})
    assert (len(regions["data"]), regions["note"][:20]) == (200, "showing 200 of 310 r")


@pytest.mark.anyio
async def test_a_server_from_a_tool_set_keeps_the_annotated_constraints() -> None:
    # The blocking finding of step 4: a tool that lost its Annotated metadata.
    hosted = MCPServer("example-host")
    register_tasks(hosted, example_tools())
    for server in (build_server(example_tools()), hosted):
        tool = {t.name: t for t in await server.list_tools()}["example_get_series"]
        year = tool.input_schema["properties"]["year"]
        assert (year["minimum"], year["description"]) == (2000, "A year from 2000.")
        text = await mcp_call_text(server, "example_get_series", {"series_id": "C", "year": 1999})
        assert text == (
            "error: InvalidRequestError: year: Input should be greater than or equal to 2000. "
            "Nothing was sent."
        )


@pytest.mark.anyio
async def test_a_tool_set_of_tasks_a_lock_binds_keeps_their_constraints() -> None:
    tenants = Tenants(
        "example", list_var="EXAMPLE_ORGS", param="org", fields=("API_KEY",), noun="organisation"
    )
    lock = TenantLock(tenants, "demo")
    server = build_server(ToolSet("example", bind_tasks([get_rows], lock)))
    tool = {t.name: t for t in await server.list_tools()}["example_get_rows"]
    assert "org" not in tool.input_schema["properties"]
    assert tool.input_schema["properties"]["limit"]["maximum"] == 100
    assert await mcp_call(server, "example_get_rows", {"limit": 5}) == {"org": "demo", "limit": 5}
    text = await mcp_call_text(server, "example_get_rows", {"limit": 101})
    assert text == (
        "error: InvalidRequestError: limit: Input should be less than or equal to 100. "
        "Nothing was sent."
    )


# The checks of a declaration run when a tool set is built, so a source's own tests fail
# on it before any server is built (ADR-0063, decision 3).


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name, "written": str(confirm)}


def delete_thing(thing_id: int, confirm: "Annotated[bool, 'write']" = False) -> None:
    """Delete a thing; the annotation is a string, resolved to bool."""


def no_confirm(name: str) -> None:
    """No confirm at all."""


def confirm_wrong_type(confirm: bool | None = False) -> None:
    """Optional, not bool."""


def confirm_true(confirm: bool = True) -> None:
    """Writes unless told not to."""


def confirm_required(confirm: bool) -> None:
    """Must be told."""


def confirm_zero(confirm: int = 0) -> None:
    """An int."""


@pytest.mark.parametrize(
    ("task", "problem"),
    [
        (no_confirm, "no parameter confirm"),
        (confirm_wrong_type, r"confirm is annotated bool \| None, not bool"),
        (confirm_zero, "confirm is annotated <class 'int'>, not bool"),
        (confirm_true, "confirm defaults to True, not False"),
        (confirm_required, "confirm has no default"),
    ],
)
def test_a_write_tool_set_refuses_a_task_without_confirm_false(
    task: Callable[..., Any], problem: str
) -> None:
    rule = r"every task of a write server takes confirm: bool = False .*\(conventions §8\)"
    with pytest.raises(ValueError, match=f"^example_{task.__name__}: {problem}; {rule}$"):
        ToolSet("example", [create_thing, task], read_only=False)
    read = ToolSet("example", iter([create_thing, task]))
    with pytest.raises(ValueError, match=f"^example_{task.__name__}: {problem}; "):
        dataclasses.replace(read, read_only=False)  # a copy is checked as a new tool set


def test_a_write_tool_set_takes_confirm_false_however_it_is_annotated() -> None:
    tools = ToolSet("example", [create_thing, delete_thing], read_only=False)
    assert tools.tasks == (create_thing, delete_thing)


def test_a_read_tool_set_ignores_the_confirm_rule() -> None:
    tools = ToolSet("example", [no_confirm, confirm_true, confirm_zero, confirm_required])
    assert len(tools.tasks) == 4


def test_a_cap_for_a_name_that_is_no_task_is_refused() -> None:
    caps = {"example_list_areas": ResultCap(max_rows=400), "list_nothing": ResultCap()}
    rule = (
        "^caps names no task among the tasks: example_list_areas, list_nothing; a key is the "
        "task function's __name__, not the tool name with the source prefix, and a task in "
        "BULK_TASKS is no tool$"
    )
    with pytest.raises(ValueError, match=rule):
        ToolSet("example", [get_series, list_areas], caps=caps)
    with pytest.raises(ValueError, match=r"^caps names no task among the tasks: list_nothing;"):
        ToolSet("example", [create_thing], caps={"list_nothing": ResultCap()}, read_only=False)


def test_the_caller_of_a_narrowed_copy_drops_the_cap_of_each_task_it_drops() -> None:
    # A host's list of tools: dataclasses.replace checks the copy as a new tool set, so a copy
    # that keeps the cap of a task it drops is refused, naming the key, and the caller passes
    # caps= beside tasks= in the same replace (ADR-0063, decisions 3 and 4).
    tools = example_tools()
    with pytest.raises(ValueError, match=r"^caps names no task among the tasks: list_areas;"):
        dataclasses.replace(tools, tasks=[get_series])
    narrowed = dataclasses.replace(tools, tasks=[get_series], caps={})
    assert [tool_name(narrowed.source, fn) for fn in narrowed.tasks] == ["example_get_series"]
    assert dict(narrowed.caps) == {}


def download_series(series_id: str) -> Result[list[str]]:
    """Download every year of one series to a file.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
    """
    raise NotImplementedError


download_series.__module__ = "example_bulk_tasks"


@pytest.mark.anyio
async def test_a_tool_set_holds_tools_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR-0063, decisions 3 and 4: a host names a source's tools from tool_set.tasks, and
    # needs no is_bulk_task of core's.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)
    tools = ToolSet("example", [get_series, download_series, list_areas])
    names = [tool_name(tools.source, task) for task in tools.tasks]
    assert names == [tool.name for tool in await build_server(tools).list_tools()]
    assert tools.tasks == (get_series, list_areas)


def list_weeks(year: int = 2024) -> Result[list[int]]:
    """List the 500 weeks of a series, oldest first, from a packaged table.

    Args:
        year: Marketing year, e.g. ``2024``.
    """
    return Result[list[int]](data=list(range(500)), meta=ResultMeta(source="example", endpoint="w"))


def list_pages(offset: int = 0) -> Result[list[int]]:
    """List rows from an upstream offset of the task's own.

    Args:
        offset: Upstream's offset, e.g. ``100``.
    """
    return Result[list[int]](data=[offset], meta=ResultMeta(source="example", endpoint="pages"))


def list_entries(start: int = 0, limit: int = 100) -> Result[list[int]]:
    """List the entries from upstream's offset ``start``, one page of upstream's.

    Args:
        start: The offset of the first entry, e.g. ``100``.
        limit: Entries on the page, e.g. ``100``.
    """
    rows = list(range(start, start + limit))
    meta = ResultMeta(source="example", endpoint="entries", request={"start": start})
    return Result[list[int]](data=rows, meta=meta)


def create_rows(count: int, confirm: bool = False) -> Result[list[int]]:
    """Create rows, or preview them unless confirm is true.

    Args:
        count: How many rows, e.g. ``300``.
        confirm: ``True`` creates them, ``False`` previews them.
    """
    return Result[list[int]](
        data=list(range(count)), meta=ResultMeta(source="example", endpoint="r")
    )


def test_a_task_that_takes_offset_itself_is_refused_a_paged_cap() -> None:
    caps = {"list_pages": ResultCap(paged=True)}
    why = (
        r"^example_list_pages: the task takes a parameter offset, which a paged cap adds as "
        r"the adapter's own argument for the rest of a cut answer; rename the task's "
        r"parameter or leave the tool unpaged$"
    )
    with pytest.raises(ValueError, match=why):
        ToolSet("example", [list_weeks, list_pages], caps=caps)


def test_a_task_that_takes_start_is_refused_a_paged_cap() -> None:
    # https://github.com/xippios/sdk-core/issues/479, part 3: the task pages upstream itself,
    # its cut answer resumes with its own start, and a continuation would send a request.
    why = (
        r"^example_list_entries: the task takes a parameter start and pages upstream itself, "
        r"so its cut answer resumes with start and a continuation would send upstream a "
        r"request; leave the tool unpaged$"
    )
    with pytest.raises(ValueError, match=why):
        ToolSet("example", [list_weeks, list_entries], caps={"list_entries": ResultCap(paged=True)})
    kept = ToolSet("example", [list_entries], caps={"list_entries": ResultCap(keep="last")})
    assert kept.tasks == (list_entries,), "a cap without paged is no continuation"
    paged = ToolSet(
        "example", [list_weeks, list_entries], caps={"list_weeks": ResultCap(paged=True)}
    )
    assert len(paged.tasks) == 2, "the refusal names the task that takes start alone"


@pytest.mark.anyio
async def test_an_unpaged_task_that_takes_start_resumes_with_it() -> None:
    server = build_server(ToolSet("example", [list_entries]))
    payload = await mcp_call(server, "example_list_entries", {"start": 100, "limit": 300})
    assert payload["note"].endswith("; resume with start=300"), "ADR-0038, decision 3"


def test_a_write_task_is_refused_a_paged_cap_since_a_continuation_writes_again() -> None:
    # https://github.com/xippios/sdk-core/pull/388#pullrequestreview-6008310538, finding 1:
    # following "continue with offset=200" ran a confirmed write a second time.
    why = (
        r"^example_create_rows: a paged cap runs the task again for the next rows, so a write "
        r"task is never paged: following its note would repeat a confirmed write; leave the "
        r"tool unpaged$"
    )
    caps = {"create_rows": ResultCap(paged=True)}
    with pytest.raises(ValueError, match=why):
        ToolSet("example", [create_rows], caps=caps, read_only=False)
    read = ToolSet("example", [create_rows], caps=caps)
    with pytest.raises(ValueError, match=why):
        dataclasses.replace(read, read_only=False)


def test_option_defaults_are_core_options_and_the_sources_at_their_defaults() -> None:
    defaults = example_tools().option_defaults()
    assert vars(defaults) == {
        "http": False,
        "host": "127.0.0.1",
        "port": 8000,
        "allow_remote": False,
        "split_years": 5,
    }


def test_option_defaults_without_add_options_are_core_options_alone() -> None:
    defaults = ToolSet("example", [get_series]).option_defaults()
    core = {"http": False, "host": "127.0.0.1", "port": 8000, "allow_remote": False}
    assert vars(defaults) == core


def add_required_org(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--org", required=True)


def add_bad_default(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--years", type=int, default="five")


@pytest.mark.parametrize(
    ("add_options", "message"),
    [
        (add_required_org, "the following arguments are required: --org"),
        (add_bad_default, "argument --years: invalid int value: 'five'"),
    ],
    ids=["required", "bad-default"],
)
def test_option_defaults_refuse_an_option_without_a_default_and_exit_nothing(
    capsys: pytest.CaptureFixture[str],
    add_options: Any,
    message: str,
) -> None:
    # Finding 3 of https://github.com/xippios/sdk-core/pull/288: argparse's exit would end
    # a host that serves every other package too.
    tools = ToolSet("example", [get_series], add_options=add_options)
    with pytest.raises(ValueError, match="add_options needs a default") as refused:
        tools.option_defaults()
    assert str(refused.value) == (
        "example: add_options needs a default for each of its options, since a host "
        f"applies the hooks without a command line: {message}"
    )
    assert capsys.readouterr() == ("", ""), "no usage printed"


def test_a_host_applies_the_hooks_with_their_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(CEILING, "years", 20)
    tools = example_tools()
    server = build_server(tools)
    assert tools.apply_options is not None
    assert tools.apply_options(tools.option_defaults()) is None
    assert CEILING["years"] == 5, "what the entry point run without --split-years holds"
    assert server.name == "xippios-example", "the hooks take no server"


def test_the_entry_point_runs_the_server_with_the_tool_sets_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The source's run() of the module docstring: main(build) reads the tool set's hooks.
    monkeypatch.setitem(CEILING, "years", 20)
    runs: list[str] = []

    def run(self: MCPServer, transport: str = "stdio", **options: Any) -> None:
        runs.append(transport)

    monkeypatch.setattr(MCPServer, "run", run)
    main(example_tools, argv=["--split-years", "7"])
    assert (runs, CEILING["years"]) == (["stdio"], 7)


# Core builds the tool set from a tasks module (ADR-0063, decision 7) --------------------

INSTRUCTIONS = "Example via xippios. Every tool takes org."
BOUND_INSTRUCTIONS = "Example via xippios."


def download_areas() -> bytes:
    """Download the areas as a file, a bulk task."""
    return b""


def example_tasks(*tasks: Callable[..., Any], **declarations: Any) -> types.ModuleType:
    """The invented source's tasks module: ``tasks`` in ``__all__`` and its declarations."""
    module = types.ModuleType("xippios.example.tasks")
    module.__all__ = [fn.__name__ for fn in tasks]  # type: ignore[attr-defined]
    for fn in tasks:
        setattr(module, fn.__name__, fn)
    for name, value in declarations.items():
        setattr(module, name, value)
    return module


def test_core_builds_the_tool_set_from_the_tasks_module() -> None:
    tasks = example_tasks(
        get_series,
        list_areas,
        download_areas,
        BULK_TASKS=frozenset({"download_areas"}),
        MCP_CAPS={"list_areas": AREAS_CAP},
        MCP_INSTRUCTIONS="Example via xippios. Call example_list_areas first.",
        mcp_add_options=add_split_years,
        mcp_apply_options=apply_split_years,
    )
    tools = ToolSet.from_tasks("example", tasks, version="1.2.0")
    assert (tools.source, tools.tasks) == ("example", (get_series, list_areas))
    assert dict(tools.caps) == {"list_areas": AREAS_CAP}
    assert tools.instructions == "Example via xippios. Call example_list_areas first."
    assert tools.version == "1.2.0"
    assert (tools.add_options, tools.apply_options) == (add_split_years, apply_split_years)
    assert (tools.read_only, tools.loopback_only) == (True, False)


def test_a_tasks_module_without_declarations_gives_a_tool_set_s_defaults() -> None:
    tools = ToolSet.from_tasks("example", example_tasks(get_series))
    assert (tools.tasks, dict(tools.caps), tools.instructions, tools.version) == (
        (get_series,),
        {},
        None,
        "",
    )
    assert (tools.add_options, tools.apply_options) == (None, None)
    assert (tools.read_only, tools.loopback_only) == (True, False)


def test_a_read_tool_set_s_hold_to_loopback_is_a_declaration_of_its_tasks_module() -> None:
    # https://github.com/xippios/sdk-core/issues/476, part 4
    tools = ToolSet.from_tasks("example", example_tasks(get_series, MCP_LOOPBACK_ONLY=True))
    assert (tools.read_only, tools.loopback_only) == (True, True)


@pytest.mark.anyio
async def test_a_lock_binds_the_tasks_and_ends_the_bound_text_with_its_sentence() -> None:
    tenants = Tenants(
        "example", list_var="EXAMPLE_ORGS", param="org", fields=("API_KEY",), noun="organisation"
    )
    sentence = (
        "This server is bound to org acme; every tool acts on that organisation and takes no org."
    )
    tasks = example_tasks(
        get_rows, MCP_INSTRUCTIONS=INSTRUCTIONS, MCP_BOUND_INSTRUCTIONS=BOUND_INSTRUCTIONS
    )
    unbound = ToolSet.from_tasks("example", tasks)
    assert (unbound.tasks, unbound.instructions) == ((get_rows,), INSTRUCTIONS)
    bound = ToolSet.from_tasks("example", tasks, lock=TenantLock(tenants, "acme"))
    assert bound.instructions == f"{BOUND_INSTRUCTIONS} {sentence}"
    server = build_server(bound)
    tool = {t.name: t for t in await server.list_tools()}["example_get_rows"]
    assert "org" not in tool.input_schema["properties"]
    assert await mcp_call(server, "example_get_rows", {"limit": 5}) == {"org": "acme", "limit": 5}
    del tasks.MCP_BOUND_INSTRUCTIONS
    without = ToolSet.from_tasks("example", tasks, lock=TenantLock(tenants, "acme"))
    assert without.instructions == f"{INSTRUCTIONS} {sentence}", "the unbound text, then"


def test_a_write_module_builds_a_write_tool_set_checked_as_one() -> None:
    tools = ToolSet.from_tasks("example", example_tasks(delete_series), read_only=False)
    assert (tools.tasks, tools.read_only) == ((delete_series,), False)
    with pytest.raises(ValueError, match=r"^example_get_series: no parameter confirm"):
        ToolSet.from_tasks("example", example_tasks(get_series), read_only=False)


@pytest.mark.parametrize(
    ("declaration", "value", "message"),
    [
        ("MCP_CAPS", [("list_areas", AREAS_CAP)], "MCP_CAPS is a mapping"),
        ("MCP_INSTRUCTIONS", 3, "MCP_INSTRUCTIONS is text or None"),
        ("MCP_BOUND_INSTRUCTIONS", b"x", "MCP_BOUND_INSTRUCTIONS is text or None"),
        ("MCP_LOOPBACK_ONLY", "yes", "MCP_LOOPBACK_ONLY is True or False"),
        ("mcp_add_options", "--split-years", "mcp_add_options is a function or None"),
        ("mcp_apply_options", 1, "mcp_apply_options is a function or None"),
    ],
)
def test_a_declaration_of_another_type_is_refused_by_its_name(
    declaration: str, value: object, message: str
) -> None:
    tasks = example_tasks(get_series, list_areas, **{declaration: value})
    with pytest.raises(TypeError, match=rf"^xippios\.example\.tasks\.{message}, got "):
        ToolSet.from_tasks("example", tasks)


def test_the_tool_set_imports_no_mcp_sdk() -> None:
    # https://github.com/xippios/sdk-core/issues/485, part 1, the first trim: the hooks take
    # the parsed options alone, so the tool set names no server.
    from xippios.core.mcp import toolset

    tree = ast.parse(inspect.getsource(toolset))
    imported = [
        alias.name if isinstance(node, ast.Import) else node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else node.names[:1])
    ]
    assert [name for name in imported if name.split(".")[0] == "mcp"] == []
