import logging
from collections.abc import Callable
from typing import Annotated, Any

import httpx
import pytest

from xippios.core import sync
from xippios.core.errors import NotFoundError
from xippios.core.mcp import (
    ResultCap,
    build_server,
    quiet_request_logging,
    register_tasks,
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
    payload = await mcp_call(server, "example_get_series", {"series_id": "CORN", "year": 2010})
    assert [row["id"] for row in payload["data"]] == ["CORN"] * 3
    assert payload["note"].startswith("showing 3 of 10 rows")
    assert payload["meta"]["source"] == "example"


@pytest.mark.anyio
async def test_taxonomy_errors_become_text_not_errors() -> None:
    server = build_server("example", [get_series])
    text = await mcp_call_text(server, "example_get_series", {"series_id": "missing"})
    assert text == "error: NotFoundError: no series missing"  # mcp_call_text: not is_error


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
