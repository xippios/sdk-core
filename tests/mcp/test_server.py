import json

import pytest
from mcp.types import CallToolResult, TextContent

from xippios.core import sync
from xippios.core.errors import NotFoundError
from xippios.core.mcp import ResultCap, build_server, register_tasks, tool_name
from xippios.core.models import Result, ResultMeta, UpstreamModel


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
    assert tool_name("usda-nass", get_series) == "usda_nass_get_series"
    assert tool_name("example", example_list_things) == "example_list_things"


@pytest.mark.anyio
async def test_tools_keep_signature_and_docstring() -> None:
    server = build_server("example", [get_series, example_list_things, plain], version="1.0")
    tools = {t.name: t for t in await server.list_tools()}
    assert set(tools) == {"example_get_series", "example_list_things", "example_plain"}
    series = tools["example_get_series"]
    assert series.description is not None
    assert series.description.startswith("Fetch one series.")
    assert "series_id: Upstream identifier" in series.description
    props = series.input_schema["properties"]
    assert props["series_id"]["type"] == "string"
    assert props["year"] == {"type": "integer", "default": 2024, "title": "Year"}
    assert series.input_schema["required"] == ["series_id"]
    assert series.annotations is not None
    assert series.annotations.read_only_hint is True
    assert series.annotations.destructive_hint is False


@pytest.mark.anyio
async def test_call_returns_capped_json_text() -> None:
    server = build_server("example", [get_series], cap=ResultCap(max_rows=3))
    result = await server.call_tool("example_get_series", {"series_id": "CORN", "year": 2010})
    assert isinstance(result, CallToolResult)
    assert not result.is_error
    content = result.content[0]
    assert isinstance(content, TextContent)
    payload = json.loads(content.text)
    assert [row["id"] for row in payload["data"]] == ["CORN"] * 3
    assert payload["note"].startswith("showing 3 of 10 rows")
    assert payload["meta"]["source"] == "example"


@pytest.mark.anyio
async def test_taxonomy_errors_become_text_not_errors() -> None:
    server = build_server("example", [get_series])
    result = await server.call_tool("example_get_series", {"series_id": "missing"})
    assert isinstance(result, CallToolResult)
    assert not result.is_error
    content = result.content[0]
    assert isinstance(content, TextContent)
    assert content.text == "error: NotFoundError: no series missing"


@pytest.mark.anyio
async def test_async_and_plain_functions_work() -> None:
    server = build_server("example", [example_list_things, plain])
    listed = await server.call_tool("example_list_things", {})
    assert isinstance(listed, CallToolResult)
    assert isinstance(listed.content[0], TextContent)
    assert json.loads(listed.content[0].text) == {"data": ["a", "b"]}
    doubled = await server.call_tool("example_plain", {"x": 21})
    assert isinstance(doubled, CallToolResult)
    assert isinstance(doubled.content[0], TextContent)
    assert json.loads(doubled.content[0].text) == {"x": 42}


@pytest.mark.anyio
async def test_register_tasks_on_existing_server_and_write_flag() -> None:
    server = build_server("example", [], name="custom", instructions="Call list first.")
    assert server.name == "custom"
    names = register_tasks(server, "example", [plain], read_only=False)
    assert names == ["example_plain"]
    tool = (await server.list_tools())[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is True
