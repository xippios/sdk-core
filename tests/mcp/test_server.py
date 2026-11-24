import dataclasses
import functools
import logging
import sys
import types
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

import httpx
import httpx2
import pytest
from mcp.client import Client
from mcp.types import CallToolResult, TextContent
from pydantic import AfterValidator, BaseModel, Field, field_validator

from xippios.core import ResultCap, sync
from xippios.core.errors import InvalidRequestError, NotFoundError
from xippios.core.mcp import (
    ToolSet,
    build_server,
    quiet_request_logging,
    register_tasks,
    tool_functions,
    tool_name,
)
from xippios.core.models import Result, ResultMeta, UpstreamModel
from xippios.core.testing import mcp_call, mcp_call_text


class Series(UpstreamModel):
    id: str
    value: float


async def get_series_async(series_id: str, year: int = 2024) -> Result[list[Series]]:
    """Fetch one series.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
        year: Marketing year, e.g. ``2024``.
    """
    if series_id == "missing":
        raise NotFoundError(f"no series {series_id}")
    rows = [Series(id=series_id, value=float(i)) for i in range(year - 2000)]
    return Result[list[Series]](data=rows, meta=ResultMeta(source="example", endpoint="series"))


get_series = sync(get_series_async)


async def example_list_things() -> list[str]:
    """List the things."""
    return ["a", "b"]


def plain(x: int) -> dict[str, int]:
    """Double it.

    Args:
        x: A number.
    """
    return {"x": x * 2}


def test_tool_name_prefix_is_never_doubled() -> None:
    assert tool_name("example-api", get_series) == "example_api_get_series"
    assert tool_name("example", example_list_things) == "example_list_things"


def test_tool_name_takes_a_tasks_name_as_text() -> None:
    # https://github.com/xippios/sdk-core/issues/476, part 6: a refusal below tasks.py
    # names a tool without the function at hand.
    assert tool_name("example", "get_series") == tool_name("example", get_series)
    assert tool_name("example-api", "get_series") == "example_api_get_series"
    assert tool_name("example", "example_list_things") == "example_list_things"


@pytest.mark.anyio
async def test_tools_keep_signature_and_docstring() -> None:
    # ADR-0063, decision 9: the description is the docstring's text before Args:, and each
    # argument's text from Args: describes it in the input schema.
    server = build_server(
        ToolSet("example", [get_series, example_list_things, plain], version="1.0")
    )
    tools = {t.name: t for t in await server.list_tools()}
    assert set(tools) == {"example_get_series", "example_list_things", "example_plain"}
    series = tools["example_get_series"]
    assert series.description == "Fetch one series."
    props = series.input_schema["properties"]
    assert props["series_id"] == {
        "type": "string",
        "title": "Series Id",
        "description": 'Upstream identifier, e.g. ``"CORN_YIELD"``.',
    }
    assert props["year"] == {
        "type": "integer",
        "default": 2024,
        "title": "Year",
        "description": "Marketing year, e.g. ``2024``.",
    }
    assert series.input_schema["required"] == ["series_id"]
    assert series.annotations is not None
    assert series.annotations.read_only_hint is True
    assert series.annotations.destructive_hint is False
    assert tools["example_list_things"].description == "List the things."
    assert tools["example_plain"].input_schema["properties"]["x"]["description"] == "A number."


class Kind(StrEnum):
    """The kinds of report that upstream serves, from its list of reports."""

    ANNUAL = "annual"
    MONTHLY = "monthly"


async def get_report_async(
    region: str, year: int = 2024, *, kind: Kind = Kind.ANNUAL, limit: int = 10
) -> Result[list[str]]:
    """Fetch one region's report for a year.

    A report is upstream's table for one region, its rows in upstream's order.

    Args:
        region: A region's code from ``list_regions``, e.g. ``"north"``; a code
            upstream does not list is refused before any request.
        year (int): Four-digit year,
            e.g. ``2024``.

            A year upstream has not published answers no rows.
        kind: Which report, ``annual`` or ``monthly``.
        unknown: A name that no parameter carries, which no schema shows.

    Returns:
        The report's rows, which no description carries.

    Raises:
        NotFoundError: Upstream has no such region.
    """
    return Result[list[str]](data=[region], meta=ResultMeta(source="example", endpoint="report"))


get_report = sync(get_report_async)


@pytest.mark.anyio
async def test_the_description_is_the_docstring_before_args() -> None:
    # ADR-0063, decision 9: what follows Args:, Returns: and Raises: among it, leaves the
    # description, and a docstring without Args: is the description whole.
    server = build_server(ToolSet("example", [get_report, example_list_things]))
    tools = {t.name: t for t in await server.list_tools()}
    assert tools["example_get_report"].description == (
        "Fetch one region's report for a year.\n\n"
        "A report is upstream's table for one region, its rows in upstream's order."
    )
    assert tools["example_list_things"].description == "List the things."


@pytest.mark.anyio
async def test_each_argument_s_text_reaches_the_input_schema() -> None:
    # ADR-0063, decision 9: an argument's lines as the docstring wraps them, its type in
    # parentheses dropped; an argument that Args: does not name has no description, and an
    # entry that names no argument reaches nothing.
    server = build_server(ToolSet("example", [get_report]))
    tool = {t.name: t for t in await server.list_tools()}["example_get_report"]
    props = tool.input_schema["properties"]
    assert props["region"]["description"] == (
        'A region\'s code from ``list_regions``, e.g. ``"north"``; a code\n'
        "upstream does not list is refused before any request."
    )
    assert props["year"]["description"] == (
        "Four-digit year,\ne.g. ``2024``.\n\nA year upstream has not published answers no rows."
    )
    assert props["kind"]["description"] == "Which report, ``annual`` or ``monthly``."
    assert "description" not in props["limit"]
    assert set(props) == {"region", "year", "kind", "limit"}
    assert "unknown" not in str(tool.input_schema)
    # The enum's class docstring still reaches the schema through the type (conventions §8).
    kind = tool.input_schema["$defs"]["Kind"]
    assert (
        kind["description"] == "The kinds of report that upstream serves, from its list of reports."
    )
    assert props["kind"]["$ref"] == "#/$defs/Kind"
    served = await mcp_call(server, "example_get_report", {"region": "north", "kind": "monthly"})
    assert served["data"] == ["north"]


async def latest_release_async() -> Result[list[str]]:
    """The newest release, at the time upstream printed it, without a zone."""
    printed = datetime(2026, 10, 6, 8, 0)
    meta = ResultMeta(
        source="example", endpoint="releases", published_at=printed, published_at_naive=True
    )
    return Result[list[str]](data=["202608"], meta=meta)


@pytest.mark.anyio
async def test_a_naive_release_time_reaches_the_agent_with_its_flag() -> None:
    # ADR-0041, decision 2: the MCP text carries the flag.
    server = build_server(ToolSet("example", [sync(latest_release_async)]))
    meta = (await mcp_call(server, "example_latest_release", {}))["meta"]
    assert (meta["published_at"], meta["published_at_naive"]) == ("2026-10-06T08:00:00", True)


@pytest.mark.anyio
async def test_call_returns_capped_json_text() -> None:
    server = build_server(
        ToolSet("example", [get_series], caps={"get_series": ResultCap(max_rows=3)})
    )
    payload = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2010})
    assert [row["id"] for row in payload["data"]] == ["CORN"] * 3
    assert payload["note"].startswith("showing 3 of 10 rows")
    assert payload["meta"]["source"] == "example"


async def list_areas_async() -> Result[list[str]]:
    """List the 310 areas, a reference list an agent needs whole."""
    areas = [f"A{i:03d}" for i in range(310)]
    return Result[list[str]](data=areas, meta=ResultMeta(source="example", endpoint="areas"))


list_areas = sync(list_areas_async)


@pytest.mark.anyio
async def test_a_tool_with_a_cap_of_its_own_returns_the_whole_list() -> None:
    caps = {"list_areas": ResultCap(max_rows=400)}  # the sync facade's __name__
    server = build_server(ToolSet("example", [get_series, list_areas], caps=caps))
    areas = await mcp_call(server, "example_list_areas", {})
    assert len(areas["data"]) == 310
    assert "note" not in areas
    series = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2500})
    assert len(series["data"]) == 200  # the default cap
    assert series["note"] == (
        "showing 200 of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the rest"
    )


@pytest.mark.anyio
async def test_a_tool_without_a_cap_of_its_own_takes_the_family_default() -> None:
    # ADR-0063, decision 1: the default cap of the slug forms left with them.
    server = build_server(ToolSet("example", []))
    caps = {"list_areas": ResultCap(max_rows=300, note="ask for one area by code instead")}
    names = register_tasks(server, ToolSet("example", [get_series, list_areas], caps=caps))
    assert names == ["example_get_series", "example_list_areas"]
    areas = await mcp_call(server, "example_list_areas", {})
    assert len(areas["data"]) == 300
    assert areas["note"] == (
        "showing 300 of 310 rows (cap: 300 rows or 65536 bytes); ask for one area by code instead"
    ), "a field the tool's own cap leaves unset takes the family default"
    series = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2300})
    assert len(series["data"]) == 200
    assert series["note"] == (
        "showing 200 of 300 rows (cap: 200 rows or 65536 bytes); narrow the query to see the rest"
    )


async def list_regions_async() -> Result[list[str]]:
    """List the 300 regions with their long names, about 90 KB of JSON."""
    regions = [f"R{i:03d} {'x' * 290}" for i in range(300)]
    return Result[list[str]](data=regions, meta=ResultMeta(source="example", endpoint="regions"))


list_regions = sync(list_regions_async)


@pytest.mark.anyio
async def test_a_tool_with_a_byte_bound_of_its_own_returns_what_the_default_would_cut() -> None:
    default = await mcp_call(
        build_server(ToolSet("example", [list_regions])), "example_list_regions", {}
    )
    assert 0 < len(default["data"]) < 300  # the default 64 KB cuts it
    assert default["note"].startswith(f"showing {len(default['data'])} of 300 rows ")
    caps = {"list_regions": ResultCap(max_rows=400, max_bytes=200_000)}
    server = build_server(ToolSet("example", [list_regions], caps=caps))
    whole = await mcp_call(server, "example_list_regions", {})
    assert len(whole["data"]) == 300
    assert "note" not in whole


async def download_series_async(series_id: str) -> Result[list[Series]]:
    """Download every year of one series.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
    """
    raise NotImplementedError


download_series_async.__module__ = "example_bulk_tasks"
download_series = sync(download_series_async)  # keeps the module, as in a tasks.py


@pytest.mark.anyio
async def test_a_task_in_bulk_tasks_is_no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR-0040, decision 4: the rendered mcp.py passes every name of tasks.__all__.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)
    tools = ToolSet("example", [get_series, download_series])
    assert tools.tasks == (get_series,), "a tool set holds tools alone (ADR-0063, decision 3)"
    server = build_server(tools)
    assert [tool.name for tool in await server.list_tools()] == ["example_get_series"]
    with pytest.raises(ValueError, match=r"download_series; .* a task in BULK_TASKS is no tool$"):
        ToolSet("example", [get_series, download_series], caps={"download_series": ResultCap()})
    monkeypatch.delitem(sys.modules, tasks.__name__)  # no module, no BULK_TASKS: a tool
    assert len(await build_server(ToolSet("example", [download_series])).list_tools()) == 1


def locked(fn: Callable[..., Any]) -> Callable[..., Any]:
    """A tenant lock's wrapper, defined in a module of its own: its ``__module__`` is the lock's."""

    @functools.wraps(fn)
    def bound(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    bound.__module__ = "example_lock"
    return bound


@pytest.mark.anyio
async def test_a_bulk_task_behind_a_wrapper_of_another_module_is_no_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # https://github.com/xippios/sdk-core/issues/155: the wrapper's __module__ names no
    # tasks module, and its __wrapped__ leads to the task that its module names in BULK_TASKS.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)
    server = build_server(ToolSet("example", [locked(get_series), locked(download_series)]))
    assert [tool.name for tool in await server.list_tools()] == ["example_get_series"]


def test_the_bulk_check_ends_on_a_wrapper_that_wraps_itself() -> None:
    from xippios.core._tasks import is_bulk_task

    looped = locked(plain)
    looped.__wrapped__ = looped  # type: ignore[attr-defined]
    assert is_bulk_task(looped) is False


def tasks_module(name: str, **functions: Callable[..., Any]) -> types.ModuleType:
    """A tasks module named ``name`` whose ``__all__`` lists ``functions`` by their keys."""
    module = types.ModuleType(name)
    for key, fn in functions.items():
        setattr(module, key, fn)
    module.__all__ = list(functions)  # type: ignore[attr-defined]
    return module


def test_tool_functions_are_the_tasks_of_all_minus_bulk_tasks() -> None:
    tasks = tasks_module(
        "example_tasks", get_series=get_series, download_series=download_series, plain=plain
    )
    assert tool_functions(tasks) == [get_series, download_series, plain]
    # BULK_TASKS is read from the module given, whatever module a function names
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    assert tool_functions(tasks) == [get_series, plain]


@pytest.mark.anyio
async def test_a_server_built_from_tool_functions_serves_them() -> None:
    tasks = tasks_module("example_tasks", get_series=get_series, download_series=download_series)
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    server = build_server(ToolSet("example", tool_functions(tasks)))
    assert [tool.name for tool in await server.list_tools()] == ["example_get_series"]


def test_tool_functions_refuse_an_entry_that_names_another_function() -> None:
    tasks = tasks_module("example_tasks", get_series=get_series, list_series=plain)
    tasks.__all__.append("list_nothing")
    rule = (
        r"^example_tasks\.__all__: list_series is the function plain, list_nothing is not in "
        r"the module; a task's name is its entry in __all__, which tool names, MCP_CAPS and "
        r"BULK_TASKS read as the function's __name__$"
    )
    with pytest.raises(ValueError, match=rule):
        tool_functions(tasks)
    tasks.BULK_TASKS = frozenset({"list_series"})  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match=r"list_series is the function plain"):
        tool_functions(tasks)  # a bulk task's entry too
    with pytest.raises(ValueError, match=r"^example_none has no __all__, the names of its tasks$"):
        tool_functions(types.ModuleType("example_none"))


@pytest.mark.anyio
async def test_a_server_keeps_no_hold_of_its_own() -> None:
    # ADR-0063, decisions 5 and 7: main reads the hold from the tool set it builds the server
    # from, read_only and loopback_only, and a host from each tool set it registers.
    from xippios.core.mcp import server as module

    held = build_server(ToolSet("example", [get_series], loopback_only=True))
    tool = (await held.list_tools())[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert not hasattr(module, "_hold")
    assert {f.name for f in dataclasses.fields(module._ServerRecord)} == {
        "arguments",
        "added",
        "checking",
    }


@pytest.mark.anyio
async def test_taxonomy_errors_become_text_not_errors() -> None:
    server = build_server(ToolSet("example", [get_series]))
    text = await mcp_call_text(server, "example_get_series", {"series_id": "missing"})
    assert text == "error: NotFoundError: no series missing"


async def call_tool(server: Any, name: str, arguments: dict[str, Any]) -> CallToolResult:
    async with Client(server) as client:
        return await client.call_tool(name, arguments)


def text_of(result: CallToolResult) -> str:
    assert len(result.content) == 1, result.content
    content = result.content[0]
    assert isinstance(content, TextContent), content
    return content.text


@pytest.mark.anyio
async def test_an_error_answer_sets_is_error_beside_its_text() -> None:
    # https://github.com/xippios/sdk-core/issues/168; ADR-0026, decision 6: a client tells
    # an error answer from data by the flag, and the text stays conventions §8's.
    server = build_server(ToolSet("example", [get_series, get_top]))
    raised = await call_tool(server, "example_get_series", {"series_id": "missing"})
    assert (raised.is_error, text_of(raised)) == (True, "error: NotFoundError: no series missing")
    refused = await call_tool(server, "example_get_top", {"field": "volume"})
    assert refused.is_error is True
    assert text_of(refused) == (
        "error: InvalidRequestError: field: Input should be 'quantity' or 'value'. "
        "Nothing was sent."
    )
    undeclared = await call_tool(server, "example_get_top", {"field": "value", "top": 3})
    assert undeclared.is_error is True
    served = await call_tool(server, "example_get_series", {"series_id": "CORN", "year": 2001})
    assert served.is_error is False
    assert text_of(served).startswith('{"data"')


class Measure(StrEnum):
    """Values of ``field`` (fetched 2026-10-27)."""

    QUANTITY = "quantity"
    VALUE = "value"


def get_top(field: Measure, year: int = 2024) -> dict[str, str]:
    """Rank by one field.

    Args:
        field: What to rank by, e.g. ``"value"``.
        year: Marketing year from 2000, e.g. ``2024``.
    """
    if year < 2000:
        raise InvalidRequestError("year: there is no data before 2000")
    return {"field": field.value}


NOTHING_SENT = "Nothing was sent."
"""The sentence that closes the adapter's refusal of an argument (ADR-0063, decision 6)."""


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"field": "volume"}, f"field: Input should be 'quantity' or 'value'. {NOTHING_SENT}"),
        ({"field": "value", "year": "soon"},
         "year: Input should be a valid integer, unable to parse string as an integer. "
         f"{NOTHING_SENT}"),
        ({"year": "soon"}, f"field: Field required (the first of 2 errors). {NOTHING_SENT}"),
        ({"field": "value", "year": 1999}, "year: there is no data before 2000"),  # the task's
    ],
)  # fmt: skip
@pytest.mark.anyio
async def test_arguments_the_schema_refuses_are_answered_in_the_family_form(
    arguments: dict[str, Any], expected: str
) -> None:
    # The SDK answered "Error executing tool ...", pydantic's text.
    server = build_server(ToolSet("example", [get_top]))
    register_tasks(server, ToolSet("example", [plain]))  # the middleware is installed once
    names = [getattr(middleware, "__name__", "") for middleware in server.middleware]
    assert names.count("check_arguments") == 1
    text = await mcp_call_text(server, "example_get_top", arguments)
    assert text == f"error: InvalidRequestError: {expected}"
    assert not {"volume", "soon", "pydantic", "input_value"} & set(text.replace(",", " ").split())
    assert await mcp_call(server, "example_get_top", {"field": "value"}) == {"field": "value"}


def count_series_factory(ran: list[str]) -> Callable[..., dict[str, Any]]:
    def count_series(series_id: str, year: int = 2024) -> dict[str, Any]:
        """Count the rows of one series.

        Args:
            series_id: Upstream identifier, e.g. ``"CORN"``.
            year: Marketing year, e.g. ``2024``.
        """
        ran.append(series_id)
        return {"series_id": series_id, "year": year}

    return count_series


TAKES = "Not an argument of this tool; it takes series_id, year"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"series_id": "CORN", "yaer": 2024}, f"yaer: {TAKES}"),
        ({"series_id": "CORN", "org": None}, f"org: {TAKES}"),  # a null is an argument too
        ({"series_id": "CORN", "org": "demo", "yaer": 2024},
         f"org: {TAKES} (the first of 2 errors)"),  # in the call's order
        ({"yaer": 2024}, f"yaer: {TAKES} (the first of 2 errors)"),  # series_id missing too
        ({"year": "soon", "yaer": 2024, "series_id": "CORN"},
         f"yaer: {TAKES} (the first of 2 errors)"),  # ahead of what the schema refuses
    ],
)  # fmt: skip
@pytest.mark.anyio
async def test_an_argument_the_tool_does_not_declare_is_refused_before_it_runs(
    arguments: dict[str, Any], expected: str
) -> None:
    # https://github.com/xippios/sdk-core/issues/84: the SDK's argument model dropped it,
    # and the tool ran with its default.
    ran: list[str] = []
    server = build_server(ToolSet("example", [count_series_factory(ran)]))
    text = await mcp_call_text(server, "example_count_series", arguments)
    assert text == f"error: InvalidRequestError: {expected}. {NOTHING_SENT}"
    assert not {"2024", "demo", "None", "soon"} & set(text.replace(",", " ").split())
    assert ran == [], "the tool does not run"
    served = await mcp_call(server, "example_count_series", {"series_id": "CORN"})
    assert served == {"series_id": "CORN", "year": 2024}


@pytest.mark.anyio
async def test_a_tool_without_arguments_refuses_every_argument() -> None:
    server = build_server(ToolSet("example", [example_list_things]))
    text = await mcp_call_text(server, "example_list_things", {"search": "a"})
    assert text == (
        "error: InvalidRequestError: search: Not an argument of this tool; it takes no "
        f"arguments. {NOTHING_SENT}"
    )
    assert await mcp_call(server, "example_list_things", {}) == {"data": ["a", "b"]}


def shout(value: str) -> str:
    return value.upper()


async def get_ranked_async(
    top: Annotated[int, Field(ge=1, description="How many, from 1.")] = 10,
    name: Annotated[str, AfterValidator(shout)] = "corn",
) -> dict[str, Any]:
    """Rank one series.

    Args:
        top: How many to rank, from 1, e.g. ``10``.
        name: Which series, e.g. ``"corn"``.
    """
    return {"top": top, "name": name}


get_ranked = sync(get_ranked_async)


@pytest.mark.anyio
async def test_an_annotated_parameter_keeps_its_metadata_in_the_tool() -> None:
    # https://github.com/xippios/sdk-core/issues/68: get_type_hints dropped the metadata,
    # so the schema lacked the bound and the validator never ran.
    server = build_server(ToolSet("example", [get_ranked]))
    tool = {t.name: t for t in await server.list_tools()}["example_get_ranked"]
    top = tool.input_schema["properties"]["top"]
    assert (top["minimum"], top["description"]) == (1, "How many, from 1.")
    # The description a parameter declares wins over its text under Args:, and a parameter
    # whose metadata declares none takes that text beside its validator (ADR-0063, decision 9).
    name = tool.input_schema["properties"]["name"]
    assert name["description"] == 'Which series, e.g. ``"corn"``.'
    text = await mcp_call_text(server, "example_get_ranked", {"top": 0})
    assert text == (
        "error: InvalidRequestError: top: Input should be greater than or equal to 1. "
        f"{NOTHING_SENT}"
    )
    served = await mcp_call(server, "example_get_ranked", {"name": "wheat"})
    assert served == {"top": 10, "name": "WHEAT"}, "the validator ran"


async def get_coded_async(
    code: Annotated[str, Field(description="A code of upstream's list.")] | None = None,
    year: Annotated[int, Field(ge=2000)] | None = None,
) -> dict[str, Any]:
    """Fetch the rows of one code.

    Args:
        code: The docstring's text for code, which the parameter's own replaces.
        year: A year from 2000, e.g. ``2024``.
    """
    return {"code": code, "year": year}


get_coded = sync(get_coded_async)


@pytest.mark.anyio
async def test_a_description_a_parameter_declares_inside_a_union_wins() -> None:
    # https://github.com/xippios/sdk-core/pull/533, finding 1: the parameter's own description
    # keeps its place in the union's member, and the docstring's text is not set beside it; a
    # union whose member declares none takes the argument's text (ADR-0063, decision 9).
    server = build_server(ToolSet("example", [get_coded]))
    tool = {t.name: t for t in await server.list_tools()}["example_get_coded"]
    code = tool.input_schema["properties"]["code"]
    assert "description" not in code
    assert {"type": "string", "description": "A code of upstream's list."} in code["anyOf"]
    assert "The docstring's text for code" not in str(tool.input_schema)
    year = tool.input_schema["properties"]["year"]
    assert year["description"] == "A year from 2000, e.g. ``2024``."


class Query(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _crash(cls, value: str) -> str:
        raise RuntimeError("a validator that crashes")


def search(query: Query) -> dict[str, str]:
    """Search by a query.

    Args:
        query: What to look for, e.g. ``{"name": "corn"}``.
    """
    return {"name": query.name}


@pytest.mark.anyio
async def test_a_validator_that_crashes_falls_through_to_the_sdks_answer() -> None:
    # Only a refusal is answered as InvalidRequestError; a crash stays the SDK's to answer.
    server = build_server(ToolSet("example", [search]))
    with pytest.raises(AssertionError, match="Error executing tool example_search"):
        await mcp_call_text(server, "example_search", {"query": {"name": "corn"}})  # is_error


@pytest.mark.anyio
async def test_async_and_plain_functions_work() -> None:
    server = build_server(ToolSet("example", [example_list_things, plain]))
    assert await mcp_call(server, "example_list_things", {}) == {"data": ["a", "b"]}
    assert await mcp_call(server, "example_plain", {"x": 21}) == {"x": 42}


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name, "written": str(confirm)}


def delete_thing(thing_id: int, confirm: "Annotated[bool, 'write']" = False) -> None:
    """Delete a thing; the annotation is a string, resolved to bool."""


@pytest.mark.anyio
async def test_a_write_tool_set_registered_on_a_server_marks_its_tools_destructive() -> None:
    server = build_server(ToolSet("example", [], instructions="Call list first."), name="custom")
    assert (server.name, server.instructions) == ("custom", "Call list first.")
    names = register_tasks(
        server, ToolSet("example", [create_thing, delete_thing], read_only=False)
    )
    assert names == ["example_create_thing", "example_delete_thing"]
    tool = (await server.list_tools())[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is True


# httpx2 and httpcore2 are the mcp SDK's own HTTP client (https://github.com/xippios/sdk-core/issues/176)
REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")


def _unset_request_logger_levels() -> None:
    # Start from the library default, whatever an earlier build_server left behind.
    for name in REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)


def _request_with_key() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        assert client.get("https://example.test/x?key=FAKE-KEY-123").status_code == 200


def _httpx2_request_with_key() -> None:
    transport = httpx2.MockTransport(lambda request: httpx2.Response(200, json={}))
    with httpx2.Client(transport=transport) as client:
        assert client.get("https://example.test/y?key=FAKE-KEY-456").status_code == 200


def test_build_server_quiets_request_loggers() -> None:
    _unset_request_logger_levels()
    build_server(ToolSet("example", []))
    for name in REQUEST_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_request_urls_are_not_logged_after_build_server(caplog: pytest.LogCaptureFixture) -> None:
    _unset_request_logger_levels()
    build_server(ToolSet("example", []))
    with caplog.at_level(logging.INFO):
        _request_with_key()
        _httpx2_request_with_key()
    assert [r for r in caplog.records if r.name.split(".")[0] in REQUEST_LOGGERS] == []
    assert not any("FAKE-KEY" in r.getMessage() for r in caplog.records)


def test_httpx2_logs_request_urls_unless_quieted(caplog: pytest.LogCaptureFixture) -> None:
    # The reason it is quieted: httpx2 logs each request's full URL at INFO, as httpx does.
    _unset_request_logger_levels()
    with caplog.at_level(logging.INFO):
        _httpx2_request_with_key()
    assert [r.name for r in caplog.records] == ["httpx2"]
    assert "example.test/y?key=FAKE-KEY-456" in caplog.records[0].getMessage()


def test_consumer_can_raise_the_request_log_level_again(caplog: pytest.LogCaptureFixture) -> None:
    _unset_request_logger_levels()
    build_server(ToolSet("example", []))
    logging.getLogger("httpx").setLevel(logging.INFO)
    with caplog.at_level(logging.INFO):
        _request_with_key()
    assert [r.name for r in caplog.records] == ["httpx"]
    assert "example.test/x?key=FAKE-KEY-123" in caplog.records[0].getMessage()


def test_quiet_request_logging_is_idempotent() -> None:
    _unset_request_logger_levels()
    loggers = [logging.getLogger(name) for name in REQUEST_LOGGERS]
    before = [(lg.handlers[:], lg.propagate, lg.disabled) for lg in loggers]
    root_before = (logging.getLogger().level, logging.getLogger().handlers[:])
    quiet_request_logging()
    quiet_request_logging()
    assert [lg.level for lg in loggers] == [logging.WARNING] * len(REQUEST_LOGGERS)
    assert [(lg.handlers, lg.propagate, lg.disabled) for lg in loggers] == before
    assert (logging.getLogger().level, logging.getLogger().handlers) == root_before


# The rest of a cut answer: a paged cap gives the tool the adapter's own offset
# (https://github.com/xippios/sdk-core/issues/314, decided in sdk-core#362).


def list_weeks_factory(runs: list[dict[str, Any]]) -> Callable[..., Result[list[int]]]:
    def list_weeks(year: int = 2024) -> Result[list[int]]:
        """List the 500 weeks of a series, oldest first.

        Args:
            year: Marketing year, e.g. ``2024``.
        """
        runs.append({"year": year})
        meta = ResultMeta(source="example", endpoint="weeks", request={"year": year})
        return Result[list[int]](data=list(range(500)), meta=meta)

    return list_weeks


def paged() -> dict[str, ResultCap]:
    return {"list_weeks": ResultCap(paged=True)}


@pytest.mark.anyio
async def test_a_paged_tool_answers_200_of_500_and_the_call_its_note_names_the_next_200() -> None:
    runs: list[dict[str, Any]] = []
    server = build_server(ToolSet("example", [list_weeks_factory(runs)], caps=paged()))
    first = await mcp_call(server, "example_list_weeks", {"year": 2024})
    assert first["data"] == list(range(200))
    assert first["note"] == (
        "showing 200 of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the "
        "rest; continue with offset=200"
    )
    second = await mcp_call(server, "example_list_weeks", {"year": 2024, "offset": 200})
    assert second["data"] == list(range(200, 400))
    assert second["note"].endswith("; continue with offset=400")
    assert second["meta"]["request"] == {"year": 2024}, "offset is the adapter's, not the task's"
    assert runs == [{"year": 2024}, {"year": 2024}], "the task runs again, without offset"


@pytest.mark.anyio
async def test_a_paged_tool_that_keeps_the_last_rows_walks_to_older_ones() -> None:
    caps = {"list_weeks": ResultCap(paged=True, keep="last")}
    server = build_server(ToolSet("example", [list_weeks_factory([])], caps=caps))
    newest = await mcp_call(server, "example_list_weeks", {})
    assert newest["data"] == list(range(300, 500))
    assert newest["note"].endswith("; continue with offset=200")
    older = await mcp_call(server, "example_list_weeks", {"offset": 200})
    assert older["data"] == list(range(100, 300))


@pytest.mark.anyio
async def test_a_paged_tool_declares_offset_and_an_unpaged_one_does_not() -> None:
    server = build_server(ToolSet("example", [list_weeks_factory([]), get_series], caps=paged()))
    tools = {tool.name: tool for tool in await server.list_tools()}
    weeks = tools["example_list_weeks"].input_schema
    assert list(weeks["properties"]) == ["year", "offset"]
    assert weeks["properties"]["offset"] == {
        "default": 0,
        "description": "Rows of the answer already shown, to skip: the note of a cut answer "
        "names the next offset. 0, the default, starts at the first row.",
        "minimum": 0,
        "title": "Offset",
        "type": "integer",
    }
    assert "required" not in weeks
    series = tools["example_get_series"].input_schema
    assert list(series["properties"]) == ["series_id", "year"]
    text = await mcp_call_text(server, "example_get_series", {"series_id": "CORN", "offset": 200})
    assert text == (f"error: InvalidRequestError: offset: {TAKES}. {NOTHING_SENT}"), (
        "the unpaged tool refuses offset as any argument it does not declare"
    )


@pytest.mark.anyio
async def test_a_cap_that_keeps_the_last_rows_describes_offset_from_the_last_row() -> None:
    caps = {"list_weeks": ResultCap(paged=True, keep="last")}
    server = build_server(ToolSet("example", [list_weeks_factory([])], caps=caps))
    (tool,) = await server.list_tools()
    assert tool.input_schema["properties"]["offset"]["description"] == (
        "Rows of the answer already shown, counted from its last row: the note of a cut "
        "answer names the next offset, which reaches older rows. 0, the default, starts at "
        "the last row."
    )


@pytest.mark.anyio
async def test_a_negative_offset_is_refused_before_the_task_runs() -> None:
    runs: list[dict[str, Any]] = []
    server = build_server(ToolSet("example", [list_weeks_factory(runs)], caps=paged()))
    text = await mcp_call_text(server, "example_list_weeks", {"offset": -1})
    assert text == (
        "error: InvalidRequestError: offset: Input should be greater than or equal to 0. "
        f"{NOTHING_SENT}"
    )
    assert runs == []


async def get_summary_async() -> Result[dict[str, int]]:
    """Summarise the series in one record."""
    meta = ResultMeta(source="example", endpoint="summary")
    return Result[dict[str, int]](data={"weeks": 500}, meta=meta)


get_summary = sync(get_summary_async)


@pytest.mark.anyio
async def test_a_paged_tool_whose_answer_holds_no_rows_refuses_an_offset() -> None:
    server = build_server(
        ToolSet("example", [get_summary], caps={"get_summary": ResultCap(paged=True)})
    )
    assert (await mcp_call(server, "example_get_summary", {}))["data"] == {"weeks": 500}
    text = await mcp_call_text(server, "example_get_summary", {"offset": 5})
    assert text == (
        "error: InvalidRequestError: offset: this answer holds no list of rows to continue; "
        "call the tool without offset"
    )


def list_pages(offset: int = 0) -> Result[list[int]]:
    """List rows from an upstream offset of the task's own.

    Args:
        offset: Upstream's offset, e.g. ``100``.
    """
    return Result[list[int]](data=[offset], meta=ResultMeta(source="example", endpoint="pages"))


@pytest.mark.anyio
async def test_an_unpaged_task_keeps_its_own_offset() -> None:
    # A paged cap would shadow it, which the tool set refuses (tests/mcp/test_toolset.py).
    unpaged = build_server(ToolSet("example", [list_pages]))
    assert (await mcp_call(unpaged, "example_list_pages", {"offset": 7}))["data"] == [7]


def create_rows_factory(writes: list[int]) -> Callable[..., Result[list[int]]]:
    def create_rows(count: int, confirm: bool = False) -> Result[list[int]]:
        """Create rows, or preview them unless confirm is true.

        Args:
            count: How many rows, e.g. ``300``.
            confirm: ``True`` creates them, ``False`` previews them.
        """
        if confirm:
            writes.append(count)
        meta = ResultMeta(source="example", endpoint="rows", request={"count": count})
        return Result[list[int]](data=list(range(count)), meta=meta)

    return create_rows


@pytest.mark.anyio
async def test_a_write_task_may_keep_the_last_rows_which_runs_it_once() -> None:
    writes: list[int] = []
    caps = {"create_rows": ResultCap(keep="last")}
    server = build_server(
        ToolSet("example", [create_rows_factory(writes)], caps=caps, read_only=False)
    )
    (tool,) = await server.list_tools()
    assert list(tool.input_schema["properties"]) == ["count", "confirm"], "no offset"
    payload = await mcp_call(server, "example_create_rows", {"count": 300, "confirm": True})
    assert payload["data"] == list(range(100, 300))
    assert payload["note"] == (
        "showing rows 101 to 300 of 300 (cap: 200 rows or 65536 bytes); narrow the query to "
        "see the rest"
    ), "the note names no call that runs the task again"
    assert writes == [300]
