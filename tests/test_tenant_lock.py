"""The binding lock: a server bound to one tenant, whose tools take no tenant argument.

The tests of the two copies that return to core (ADR-0042, decision 1):
sdk-cashctrl's ``tests/test_org_lock.py`` and sdk-google-mail's
``tests/test_account_lock.py``, the parts that test the lock itself, on a fictitious source
whose variables no shell sets. A call goes through ``mcp_call_text``, an in-process client,
so the argument check runs as it does for a real client: on a bound server it refuses the
tenant's argument, which no tool declares (ADR-0036, decision 12).
"""

import asyncio
import dataclasses
import inspect
import json
import os
import threading
import typing
from typing import Annotated

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.client import Client
from mcp.server.mcpserver import MCPServer
from pydantic import AfterValidator, Field

from xippios.core import (
    Result,
    ResultMeta,
    TenantLock,
    Tenants,
    bind_tasks,
    list_task,
    sync,
    tenant_instructions,
)
from xippios.core.http import router_from_tasks
from xippios.core.mcp import build_server, is_write_server
from xippios.core.testing import mcp_call, mcp_call_text

SOURCE = "fictive-src"
TOOL = "fictive_src_echo_org"
LIST = "fictive_src_list_tenants"
DEMO = "demo"
SENTENCE = (
    "This server is bound to org demo; every tool acts on that organisation and takes no org."
)
LOCK = TenantLock("org", DEMO, noun="organisation")
TENANTS = Tenants(SOURCE, list_var="FICTIVE_SRC_TENANTS", fields=("SUBDOMAIN",), reserved=(DEMO,))
list_tenants = list_task(TENANTS, name="list_tenants")


@pytest.fixture(autouse=True)
def only_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with the reserved ``demo`` declared and no other tenant, by name."""
    for name in [name for name in os.environ if name.startswith("FICTIVE_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(TENANTS.var(DEMO, "SUBDOMAIN"), "placeholder")


class Echo:
    """Builds servers with one tool that records the organisation it was called for."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def server(self, lock: TenantLock | None = None) -> MCPServer:
        calls = self.calls

        async def echo_org(org: str, note: str = "") -> dict[str, str]:
            """Return the organisation the tool was called for.

            Args:
                org: A declared organisation, e.g. ``demo``.
                note: Any text, e.g. ``"hi"``.
            """
            calls.append(org)
            return {"org": org, "note": note}

        return build_server(SOURCE, bind_tasks([echo_org, list_tenants], lock))


def find_things(org: str, query: str | None = None, *, limit: int = 10) -> list[str]:
    """Find things.

    Args:
        org: A declared organisation,
            e.g. ``demo``.
        query: Full-text search, e.g. ``"Muster"``.
        limit: At most this many, e.g. ``5``.

    Returns:
        The things' names.
    """
    return [org, query or "", str(limit), str(threading.get_ident())]


# The lock ----------------------------------------------------------------------------


def test_a_lock_is_a_frozen_parameter_tenant_and_noun() -> None:
    assert (LOCK.param, LOCK.value, LOCK.noun) == ("org", DEMO, "organisation")
    assert TenantLock(param="org", value=DEMO, noun="organisation") == LOCK
    assert TenantLock("account", DEMO).noun is None, "the parameter stands for the noun"
    with pytest.raises(dataclasses.FrozenInstanceError):
        LOCK.value = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("param", "value", "noun", "message"),
    [
        ("", "acme", None, "param must be a parameter name"),
        ("an org", "acme", None, "param must be a parameter name"),
        ("org", "", None, "value must name the tenant"),
        ("org", "acme", "", "noun must be a word"),
        ("org", "acme", " ", "noun must be a word"),
    ],
)
def test_a_lock_needs_a_parameter_name_a_tenant_and_a_noun(
    param: str, value: str, noun: str | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        TenantLock(param, value, noun=noun)


# The wrapper -------------------------------------------------------------------------


def test_a_bound_task_keeps_its_name_and_drops_the_parameter() -> None:
    """Same ``__name__`` (tool names, ``MCP_CAPS`` keys), no ``org`` in signature or hints."""
    (bound,) = bind_tasks([find_things], LOCK)
    assert (bound.__name__, bound.__qualname__, bound.__module__) == (
        find_things.__name__,
        find_things.__qualname__,
        find_things.__module__,
    )
    parameters = inspect.signature(bound).parameters
    assert list(parameters) == ["query", "limit"]
    assert parameters["limit"].kind is inspect.Parameter.KEYWORD_ONLY
    assert typing.get_type_hints(bound) == {
        "query": str | None,
        "limit": int,
        "return": list[str],
    }


def test_the_docstring_loses_the_entry_and_its_continuation() -> None:
    (bound,) = bind_tasks([find_things], LOCK)
    assert inspect.getdoc(bound) == (
        "Find things.\n\nArgs:\n"
        '    query: Full-text search, e.g. ``"Muster"``.\n'
        "    limit: At most this many, e.g. ``5``.\n\n"
        "Returns:\n    The things' names."
    )


def test_an_args_block_the_entry_emptied_goes() -> None:
    def ping(org: str) -> str:
        """Answer for the organisation.

        Args:
            org: A declared organisation, e.g. ``demo``.
        """
        return org

    (bound,) = bind_tasks([ping], LOCK)
    assert inspect.getdoc(bound) == "Answer for the organisation."
    assert list(inspect.signature(bound).parameters) == []


def test_a_task_without_the_parameter_and_an_unbound_server_are_left_as_they_are() -> None:
    def ping() -> dict[str, bool]:
        """Answer without an organisation."""
        return {"pong": True}

    assert bind_tasks([ping], LOCK)[0] is ping
    assert bind_tasks([ping, find_things], None) == [ping, find_things]
    assert bind_tasks(iter([ping]), None) == [ping], "any iterable, a list back"


@pytest.mark.anyio
async def test_a_bound_sync_facade_awaits_its_async_twin_on_the_running_loop() -> None:
    loops: list[asyncio.AbstractEventLoop] = []

    async def count_async(org: str, n: int = 1) -> Result[list[str]]:
        """Count.

        Args:
            org: A declared organisation, e.g. ``demo``.
            n: How many, e.g. ``2``.
        """
        loops.append(asyncio.get_running_loop())
        return Result[list[str]](
            data=[org] * n, meta=ResultMeta(source=SOURCE, endpoint="count", tenant=org)
        )

    count = sync(count_async)
    (bound,) = bind_tasks([count], LOCK)
    assert bound.__name__ == "count"
    result = await bound(n=2)
    assert (result.data, result.meta.tenant) == ([DEMO, DEMO], DEMO)
    assert loops == [asyncio.get_running_loop()], "the twin, not the facade's own loop"


@pytest.mark.anyio
async def test_a_bound_plain_function_runs_in_a_worker_thread() -> None:
    (bound,) = bind_tasks([find_things], LOCK)
    org, query, limit, thread = await bound(query="x", limit=3)
    assert (org, query, limit) == (DEMO, "x", "3")
    assert int(thread) != threading.get_ident(), "as core's as_async runs it"


def list_rows(
    org: str,
    limit: Annotated[int, Field(ge=1, le=100, description="Rows per page, 1 to 100.")] = 10,
    name: Annotated[str, AfterValidator(str.upper)] = "all",
) -> dict[str, object]:
    """List rows.

    Args:
        org: A declared organisation, e.g. ``demo``.
        limit: Rows per page, e.g. ``10``.
        name: Which rows, e.g. ``"wheat"``.
    """
    return {"org": org, "limit": limit, "name": name}


def test_a_bound_task_keeps_the_annotated_metadata_of_its_other_parameters() -> None:
    (bound,) = bind_tasks([list_rows], LOCK)
    hints = typing.get_type_hints(list_rows, include_extras=True)
    assert typing.get_type_hints(bound, include_extras=True) == {
        "limit": hints["limit"],
        "name": hints["name"],
        "return": hints["return"],
    }


@pytest.mark.anyio
async def test_a_bound_tool_keeps_an_annotated_constraint_in_its_schema_and_its_check() -> None:
    """Conventions §8: the constraint holds in the schema and the check, bound or not."""
    server = build_server(SOURCE, bind_tasks([list_rows], LOCK))
    (tool,) = await server.list_tools()
    limit = tool.input_schema["properties"]["limit"]
    assert (limit["minimum"], limit["maximum"], limit["description"]) == (
        1,
        100,
        "Rows per page, 1 to 100.",
    )
    refused = await mcp_call_text(server, "fictive_src_list_rows", {"limit": 500})
    assert refused == (
        "error: InvalidRequestError: limit: Input should be less than or equal to 100"
    )
    served = await mcp_call(server, "fictive_src_list_rows", {"limit": 5, "name": "wheat"})
    assert served == {"org": DEMO, "limit": 5, "name": "WHEAT"}, "the validator ran"


def test_a_bound_route_keeps_an_annotated_constraint_in_its_schema_and_its_check() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks(SOURCE, bind_tasks([list_rows], LOCK)))
    client = TestClient(app)
    operation = app.openapi()["paths"]["/fictive-src/list_rows"]["get"]
    params = {param["name"]: param for param in operation["parameters"]}
    assert set(params) == {"limit", "name"}, "no org"
    assert (params["limit"]["schema"]["minimum"], params["limit"]["schema"]["maximum"]) == (1, 100)
    refused = client.get("/fictive-src/list_rows", params={"limit": 500})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "limit: Input should be less than or equal to 100"
    served = client.get("/fictive-src/list_rows", params={"limit": 5, "name": "wheat"})
    assert served.json() == {"org": DEMO, "limit": 5, "name": "WHEAT"}, "the validator ran"


# Calls on a bound server -------------------------------------------------------------


@pytest.mark.anyio
async def test_the_bound_tenant_is_passed() -> None:
    echo = Echo()
    text = await mcp_call_text(echo.server(LOCK), TOOL, {"note": "hi"})
    assert json.loads(text) == {"org": DEMO, "note": "hi"}
    assert echo.calls == [DEMO]


@pytest.mark.anyio
async def test_no_tool_of_a_bound_server_takes_the_parameter() -> None:
    async with Client(Echo().server(LOCK)) as client:
        tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == [TOOL, LIST]
    for tool in tools:
        assert "org" not in tool.input_schema.get("properties", {}), tool.name
        assert "org:" not in (tool.description or ""), tool.name


@pytest.mark.anyio
@pytest.mark.parametrize("named", [DEMO, "other", "", None])
async def test_a_call_that_still_names_the_tenant_is_refused(named: str | None) -> None:
    """Step 2's argument check: no tool of a bound server declares ``org``, so none takes it."""
    echo = Echo()
    text = await mcp_call_text(echo.server(LOCK), TOOL, {"org": named, "note": "x"})
    assert text == "error: InvalidRequestError: org: Not an argument of this tool; it takes note"
    assert echo.calls == [], "the tool does not run"


@pytest.mark.anyio
async def test_the_tenant_list_shows_the_bound_tenant_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TENANTS.list_var, "xa,xb")
    echo = Echo()
    unbound = await mcp_call(echo.server(), LIST, {})
    assert unbound["data"] == ["xa", "xb", DEMO]
    only = await mcp_call(echo.server(LOCK), LIST, {})
    assert only["data"] == [DEMO]
    assert (only["meta"]["tenant"], only["meta"]["endpoint"]) == (None, "list_tenants")
    assert list_tenants().data == ["xa", "xb", DEMO], "the task itself is unchanged"


@pytest.mark.anyio
async def test_a_lock_on_an_undeclared_tenant_lists_nothing() -> None:
    server = Echo().server(TenantLock("org", "gone"))
    assert (await mcp_call(server, LIST, {}))["data"] == []


@pytest.mark.anyio
async def test_a_bound_write_task_keeps_confirm_last_on_a_write_server() -> None:
    def create_thing(org: str, name: str, confirm: bool = False) -> dict[str, str]:
        """Create a thing; without confirm, return a preview.

        Args:
            org: A declared organisation, e.g. ``demo``.
            name: The thing's name, e.g. ``"Corn"``.
            confirm: ``True`` writes, ``False`` previews.
        """
        return {"org": org, "name": name, "written": str(confirm)}

    server = build_server(SOURCE, bind_tasks([create_thing], LOCK), read_only=False)
    assert is_write_server(server)
    (tool,) = await server.list_tools()
    assert list(tool.input_schema["properties"]) == ["name", "confirm"]
    payload = await mcp_call(server, "fictive_src_create_thing", {"name": "Corn"})
    assert payload == {"org": DEMO, "name": "Corn", "written": "False"}


# The instructions --------------------------------------------------------------------


def test_an_unbound_server_keeps_its_text() -> None:
    assert tenant_instructions("Every tool takes org.", None) == "Every tool takes org."
    assert tenant_instructions("Every tool takes org.", None, bound="B.") == (
        "Every tool takes org."
    )
    assert tenant_instructions(None, None) is None


def test_a_bound_server_s_text_ends_with_the_lock_s_sentence() -> None:
    unbound = "Every tool takes org."
    assert tenant_instructions(unbound, LOCK) == f"{unbound} {SENTENCE}", "sdk-cashctrl's call"
    assert tenant_instructions(unbound, LOCK, bound="Bound.") == f"Bound. {SENTENCE}"
    assert tenant_instructions(unbound, LOCK, bound="") == SENTENCE
    assert tenant_instructions(None, LOCK) == SENTENCE


def test_the_sentence_names_the_lock_s_noun_or_else_its_parameter() -> None:
    assert tenant_instructions(None, TenantLock("account", "work")) == (
        "This server is bound to account work; every tool acts on that account and takes no "
        "account."
    )


@pytest.mark.anyio
async def test_a_client_reads_the_bound_server_s_instructions() -> None:
    text = "Fictive via xippios. Every tool takes org."
    bound = "Fictive via xippios."
    server = build_server(
        SOURCE,
        bind_tasks([list_tenants], LOCK),
        instructions=tenant_instructions(text, LOCK, bound=bound),
    )
    async with Client(server) as client:
        assert client.instructions == f"{bound} {SENTENCE}"
