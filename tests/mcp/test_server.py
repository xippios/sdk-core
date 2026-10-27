import logging
import sys
import types
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

import httpx
import pytest
from pydantic import BaseModel, field_validator

from xippios.core import sync
from xippios.core.errors import InvalidRequestError, NotFoundError
from xippios.core.mcp import ResultCap, TenantLock, build_server, tool_name
from xippios.core.mcp.server import is_write_server, quiet_request_logging, register_tasks
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


async def latest_release_async() -> Result[list[str]]:
    """The newest release, at the time upstream printed it, without a zone."""
    printed = datetime(2026, 10, 6, 8, 0)
    meta = ResultMeta(
        source="example", endpoint="releases", published_at=printed, published_at_naive=True
    )
    return Result[list[str]](data=["202608"], meta=meta)


@pytest.mark.anyio
async def test_a_naive_release_time_reaches_the_agent_with_its_flag() -> None:
    # ADR-0022, rule 2: the MCP text carries the flag.
    server = build_server("example", [sync(latest_release_async)])
    meta = (await mcp_call(server, "example_latest_release", {}))["meta"]
    assert (meta["published_at"], meta["published_at_naive"]) == ("2026-10-06T08:00:00", True)


@pytest.mark.anyio
async def test_call_returns_capped_json_text() -> None:
    server = build_server("example", [get_series], cap=ResultCap(max_rows=3))
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
    server = build_server("example", [get_series, list_areas], caps=caps)
    areas = await mcp_call(server, "example_list_areas", {})
    assert len(areas["data"]) == 310
    assert "note" not in areas
    series = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2500})
    assert len(series["data"]) == 200  # the default cap
    assert series["note"] == (
        "showing 200 of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the rest"
    )


@pytest.mark.anyio
async def test_a_cap_of_its_own_replaces_the_server_cap_for_that_tool_only() -> None:
    server = build_server("example", [])
    caps = {"list_areas": ResultCap(max_rows=300, note="ask for one area by code instead")}
    names = register_tasks(
        server, "example", [get_series, list_areas], cap=ResultCap(max_rows=3), caps=caps
    )
    assert names == ["example_get_series", "example_list_areas"]
    areas = await mcp_call(server, "example_list_areas", {})
    assert len(areas["data"]) == 300
    assert areas["note"] == (
        "showing 300 of 310 rows (cap: 300 rows or 65536 bytes); ask for one area by code instead"
    )
    series = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2010})
    assert len(series["data"]) == 3
    assert series["note"].startswith("showing 3 of 10 rows (cap: 3 rows or 65536 bytes); ")


async def list_regions_async() -> Result[list[str]]:
    """List the 300 regions with their long names, about 90 KB of JSON."""
    regions = [f"R{i:03d} {'x' * 290}" for i in range(300)]
    return Result[list[str]](data=regions, meta=ResultMeta(source="example", endpoint="regions"))


list_regions = sync(list_regions_async)


@pytest.mark.anyio
async def test_a_tool_with_a_byte_bound_of_its_own_returns_what_the_default_would_cut() -> None:
    default = await mcp_call(build_server("example", [list_regions]), "example_list_regions", {})
    assert 0 < len(default["data"]) < 300  # the default 64 KB cuts it
    assert default["note"].startswith(f"showing {len(default['data'])} of 300 rows ")
    caps = {"list_regions": ResultCap(max_rows=400, max_bytes=200_000)}
    server = build_server("example", [list_regions], caps=caps)
    whole = await mcp_call(server, "example_list_regions", {})
    assert len(whole["data"]) == 300
    assert "note" not in whole


@pytest.mark.anyio
async def test_a_cap_for_a_name_that_is_no_task_is_refused() -> None:
    caps = {"example_list_areas": ResultCap(max_rows=400), "list_nothing": ResultCap()}
    rule = (
        "^caps names no task among the tasks: example_list_areas, list_nothing; a key is the "
        "task function's __name__, not the tool name with the source prefix, and a task in "
        "BULK_TASKS is no tool$"
    )
    with pytest.raises(ValueError, match=rule):
        build_server("example", [get_series, list_areas], caps=caps)
    server = build_server("example", [])
    middleware = list(server.middleware)  # the SDK's own
    with pytest.raises(ValueError, match=r"^caps names no task among the tasks: list_nothing;"):
        register_tasks(server, "example", iter([list_areas]), caps={"list_nothing": ResultCap()})
    with pytest.raises(ValueError, match=r"^caps names no task among the tasks: list_nothing;"):
        register_tasks(
            server,
            "example",
            [create_thing],
            caps={"list_nothing": ResultCap()},
            read_only=False,
            tenant_lock=TenantLock("org", "acme"),
        )
    assert await server.list_tools() == []  # checked before anything is registered
    assert not is_write_server(server)  # nor marked a write server
    assert server.middleware == middleware  # nor locked: another lock is still accepted
    register_tasks(server, "example", [plain], tenant_lock=TenantLock("org", "other"))
    assert len(server.middleware) == len(middleware) + 1


@pytest.mark.anyio
async def test_a_cap_of_its_own_falls_back_to_the_family_default_not_to_the_server_cap() -> None:
    caps = {"list_areas": ResultCap(max_rows=300)}  # max_bytes unset
    server = build_server(
        "example", [get_series, list_areas], cap=ResultCap(max_bytes=1000), caps=caps
    )
    areas = await mcp_call(server, "example_list_areas", {})
    assert len(areas["data"]) == 300  # over 2,000 bytes, more than the server cap allows
    assert areas["note"].startswith("showing 300 of 310 rows (cap: 300 rows or 65536 bytes); ")
    series = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2100})
    assert series["note"].endswith(
        "rows (cap: 200 rows or 1000 bytes); narrow the query to see the rest"
    )


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
    # ADR-0019, decision 4: the rendered mcp.py passes every name of tasks.__all__.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)
    server = build_server("example", [get_series, download_series])
    assert [tool.name for tool in await server.list_tools()] == ["example_get_series"]
    with pytest.raises(ValueError, match=r"download_series; .* a task in BULK_TASKS is no tool$"):
        build_server(
            "example", [get_series, download_series], caps={"download_series": ResultCap()}
        )
    monkeypatch.delitem(sys.modules, tasks.__name__)  # no module, no BULK_TASKS: a tool
    assert len(await build_server("example", [download_series]).list_tools()) == 1


@pytest.mark.anyio
async def test_taxonomy_errors_become_text_not_errors() -> None:
    server = build_server("example", [get_series])
    text = await mcp_call_text(server, "example_get_series", {"series_id": "missing"})
    assert text == "error: NotFoundError: no series missing"  # mcp_call_text: not is_error


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


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"field": "volume"}, "field: Input should be 'quantity' or 'value'"),
        ({"field": "value", "year": "soon"},
         "year: Input should be a valid integer, unable to parse string as an integer"),
        ({"year": "soon"}, "field: Field required (the first of 2 errors)"),
        ({"field": "value", "year": 1999}, "year: there is no data before 2000"),  # the task's
    ],
)  # fmt: skip
@pytest.mark.anyio
async def test_arguments_the_schema_refuses_are_answered_in_the_family_form(
    arguments: dict[str, Any], expected: str
) -> None:
    # Row 41 a (sdk-usda-esr): the SDK answered "Error executing tool ...", pydantic's text.
    server = build_server("example", [get_top])
    register_tasks(server, "example", [plain])  # the middleware is installed once
    names = [getattr(middleware, "__name__", "") for middleware in server.middleware]
    assert names.count("check_arguments") == 1
    text = await mcp_call_text(server, "example_get_top", arguments)  # not is_error
    assert text == f"error: InvalidRequestError: {expected}"
    assert not {"volume", "soon", "pydantic", "input_value"} & set(text.replace(",", " ").split())
    assert await mcp_call(server, "example_get_top", {"field": "value"}) == {"field": "value"}


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
    server = build_server("example", [search])
    with pytest.raises(AssertionError, match="Error executing tool example_search"):
        await mcp_call_text(server, "example_search", {"query": {"name": "corn"}})  # is_error


@pytest.mark.anyio
async def test_async_and_plain_functions_work() -> None:
    server = build_server("example", [example_list_things, plain])
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


@pytest.mark.anyio
async def test_register_tasks_on_existing_server_and_write_flag() -> None:
    server = build_server("example", [], name="custom", instructions="Call list first.")
    assert server.name == "custom"
    names = register_tasks(server, "example", [create_thing, delete_thing], read_only=False)
    assert names == ["example_create_thing", "example_delete_thing"]
    tool = (await server.list_tools())[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is True


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
@pytest.mark.anyio
async def test_a_write_server_refuses_a_task_without_confirm_false(
    task: Callable[..., Any], problem: str
) -> None:
    rule = r"every task of a write server takes confirm: bool = False .*\(conventions §8\)"
    with pytest.raises(ValueError, match=f"^example_{task.__name__}: {problem}; {rule}"):
        build_server("example", [create_thing, task], read_only=False)
    server = build_server("example", [])
    with pytest.raises(ValueError, match=f"^example_{task.__name__}: "):
        register_tasks(server, "example", iter([create_thing, task]), read_only=False)
    assert await server.list_tools() == []  # checked before anything is registered


@pytest.mark.anyio
async def test_a_read_only_server_ignores_the_confirm_rule() -> None:
    server = build_server("example", [no_confirm, confirm_true, confirm_zero, plain])
    assert len(await server.list_tools()) == 4
    names = register_tasks(server, "example", [confirm_required], read_only=True)
    assert names == ["example_confirm_required"]


REQUEST_LOGGERS = ("httpx", "httpcore")


def _unset_request_logger_levels() -> None:
    # Start from the library default, whatever an earlier build_server left behind.
    for name in REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)


def _request_with_key() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        assert client.get("https://example.test/x?key=FAKE-KEY-123").status_code == 200


def test_build_server_quiets_request_loggers() -> None:
    _unset_request_logger_levels()
    build_server("example", [])
    for name in REQUEST_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_request_urls_are_not_logged_after_build_server(caplog: pytest.LogCaptureFixture) -> None:
    _unset_request_logger_levels()
    build_server("example", [])
    with caplog.at_level(logging.INFO):
        _request_with_key()
    assert [r for r in caplog.records if r.name.split(".")[0] in REQUEST_LOGGERS] == []
    assert not any("FAKE-KEY-123" in r.getMessage() for r in caplog.records)


def test_consumer_can_raise_the_request_log_level_again(caplog: pytest.LogCaptureFixture) -> None:
    _unset_request_logger_levels()
    build_server("example", [])
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
    assert [lg.level for lg in loggers] == [logging.WARNING, logging.WARNING]
    assert [(lg.handlers, lg.propagate, lg.disabled) for lg in loggers] == before
    assert (logging.getLogger().level, logging.getLogger().handlers) == root_before
