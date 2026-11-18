"""ToolSet: what a package's ``build(**options)`` returns, and the servers built from it.

``build_server`` builds a server from one tool set and a host one server from several
with ``register_tasks`` (https://github.com/xippios/sdk-core/issues/245; ADR-0026,
decision 8). The tasks are a fictitious source's.
"""

import argparse
import dataclasses
from typing import Annotated, Any

import pytest
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from xippios.core import Result, ResultMeta, TenantLock, bind_tasks, sync
from xippios.core.mcp import (
    ResultCap,
    ToolSet,
    build_server,
    is_loopback_only,
    is_write_server,
    main,
    register_tasks,
)
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


def apply_split_years(namespace: argparse.Namespace, server: MCPServer) -> MCPServer:
    CEILING["years"] = namespace.split_years
    return server


AREAS_CAP = ResultCap(max_rows=400)
BUILD_ALONE = "build_server takes name alone beside a tool set, which carries the rest"
REGISTER_ALONE = "register_tasks takes a tool set alone, which carries what it registers"


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
    assert not is_write_server(server)
    assert not is_loopback_only(server)


def test_build_server_names_a_server_from_a_tool_set_as_told() -> None:
    server = build_server(example_tools(), name="xippios-example-write")
    assert server.name == "xippios-example-write"


def test_a_tool_set_that_writes_or_is_held_builds_a_server_held_to_loopback() -> None:
    writes = build_server(ToolSet("example", [delete_series], read_only=False))
    assert (is_write_server(writes), is_loopback_only(writes)) == (True, True)
    held = build_server(ToolSet("example", [get_series], loopback_only=True))
    assert (is_write_server(held), is_loopback_only(held)) == (False, True)


def test_a_server_from_a_tool_set_is_checked_as_build_server_checks_it() -> None:
    with pytest.raises(ValueError, match="example_get_series: no parameter confirm"):
        build_server(ToolSet("example", [get_series], read_only=False))
    with pytest.raises(ValueError, match="caps names no task among the tasks: list_rows"):
        build_server(ToolSet("example", [get_series], caps={"list_rows": AREAS_CAP}))


@pytest.mark.parametrize(
    "given",
    [
        {"version": "2.0.0"},
        {"instructions": "Other text."},
        {"cap": ResultCap(max_rows=5)},
        {"caps": {"list_areas": AREAS_CAP}},
        {"read_only": False},
        {"loopback_only": True},
    ],
)
def test_build_server_takes_name_alone_beside_a_tool_set(given: dict[str, Any]) -> None:
    (keyword,) = given
    with pytest.raises(TypeError) as refused:
        build_server(example_tools(), **given)
    assert str(refused.value) == f"{BUILD_ALONE}; drop {keyword}"


def test_build_server_takes_no_tasks_beside_a_tool_set() -> None:
    with pytest.raises(TypeError) as refused:
        build_server(example_tools(), [list_areas], version="2.0.0")  # type: ignore[call-overload]
    assert str(refused.value) == f"{BUILD_ALONE}; drop tasks, version"


def test_build_server_with_a_slug_still_needs_its_tasks() -> None:
    with pytest.raises(TypeError, match="tasks"):
        build_server("example")  # type: ignore[call-overload]


@pytest.mark.anyio
async def test_a_host_builds_one_server_from_two_tool_sets_each_with_its_own_caps() -> None:
    other = ToolSet("other", [list_regions], version="0.3.0")  # the default cap
    server = MCPServer("xippios-group")
    names = register_tasks(server, example_tools()) + register_tasks(server, other)
    assert names == ["example_get_series", "example_list_areas", "other_list_regions"]
    assert {t.name for t in await server.list_tools()} == set(names)
    areas = await mcp_call(server, "example_list_areas", {})
    assert (len(areas["data"]), "note" in areas) == (310, False)
    regions = await mcp_call(server, "other_list_regions", {})
    assert (len(regions["data"]), regions["note"][:20]) == (200, "showing 200 of 310 r")


def test_one_held_tool_set_holds_the_host_built_server() -> None:
    server = MCPServer("xippios-group")
    register_tasks(server, example_tools())
    assert not is_loopback_only(server)
    register_tasks(server, ToolSet("mail", [list_regions], loopback_only=True))
    assert (is_write_server(server), is_loopback_only(server)) == (False, True)


def test_a_write_tool_set_makes_the_host_built_server_a_write_server() -> None:
    server = MCPServer("xippios-group-write")
    register_tasks(server, ToolSet("example", [delete_series], read_only=False))
    assert (is_write_server(server), is_loopback_only(server)) == (True, True)


@pytest.mark.parametrize(
    "given",
    [
        {"cap": ResultCap(max_rows=5)},
        {"caps": {"list_areas": AREAS_CAP}},
        {"read_only": False},
        {"loopback_only": True},
    ],
)
def test_register_tasks_takes_a_tool_set_alone(given: dict[str, Any]) -> None:
    (keyword,) = given
    server = MCPServer("xippios-group")
    middleware = list(server.middleware)
    with pytest.raises(TypeError) as refused:
        register_tasks(server, example_tools(), **given)
    assert str(refused.value) == f"{REGISTER_ALONE}; drop {keyword}"
    assert server.middleware == middleware, "nothing installed"
    assert not is_write_server(server)
    assert not is_loopback_only(server)


def test_register_tasks_takes_no_tasks_beside_a_tool_set() -> None:
    with pytest.raises(TypeError) as refused:
        register_tasks(MCPServer("x"), example_tools(), [list_areas])  # type: ignore[call-overload]
    assert str(refused.value) == f"{REGISTER_ALONE}; drop tasks"


def test_register_tasks_with_a_slug_still_needs_its_tasks() -> None:
    with pytest.raises(TypeError, match="tasks"):
        register_tasks(MCPServer("x"), "example")  # type: ignore[call-overload]


@pytest.mark.anyio
async def test_a_server_from_a_tool_set_keeps_the_annotated_constraints() -> None:
    # The blocking finding of step 4: a tool that lost its Annotated metadata.
    hosted = MCPServer("xippios-group")
    register_tasks(hosted, example_tools())
    for server in (build_server(example_tools()), hosted):
        tool = {t.name: t for t in await server.list_tools()}["example_get_series"]
        year = tool.input_schema["properties"]["year"]
        assert (year["minimum"], year["description"]) == (2000, "A year from 2000.")
        text = await mcp_call_text(server, "example_get_series", {"series_id": "C", "year": 1999})
        assert text == (
            "error: InvalidRequestError: year: Input should be greater than or equal to 2000"
        )


@pytest.mark.anyio
async def test_a_tool_set_of_tasks_a_lock_binds_keeps_their_constraints() -> None:
    lock = TenantLock("org", "demo", noun="organisation")
    server = build_server(ToolSet("example", bind_tasks([get_rows], lock)))
    tool = {t.name: t for t in await server.list_tools()}["example_get_rows"]
    assert "org" not in tool.input_schema["properties"]
    assert tool.input_schema["properties"]["limit"]["maximum"] == 100
    assert await mcp_call(server, "example_get_rows", {"limit": 5}) == {"org": "demo", "limit": 5}
    text = await mcp_call_text(server, "example_get_rows", {"limit": 101})
    assert text == "error: InvalidRequestError: limit: Input should be less than or equal to 100"


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


def test_a_host_applies_the_hooks_with_their_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(CEILING, "years", 20)
    tools = example_tools()
    server = build_server(tools)
    assert tools.apply_options is not None
    assert tools.apply_options(tools.option_defaults(), server) is server
    assert CEILING["years"] == 5, "what the entry point run without --split-years holds"


def test_the_entry_point_runs_the_server_with_the_tool_sets_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The source's run() of the module docstring: main with the tool set's hooks.
    monkeypatch.setitem(CEILING, "years", 20)
    tools = example_tools()
    server = build_server(tools)
    runs: list[str] = []

    def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
        runs.append(transport)

    monkeypatch.setattr(server, "run", fake_run)
    main(
        server,
        ["--split-years", "7"],
        add_options=tools.add_options,
        apply_options=tools.apply_options,
    )
    assert (runs, CEILING["years"]) == (["stdio"], 7)
