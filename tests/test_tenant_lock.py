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
import sys
import threading
import types
import typing
from collections.abc import Callable
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
from xippios.core.mcp import ToolSet, build_server
from xippios.core.testing import mcp_call, mcp_call_text

SOURCE = "fictive-src"
TOOL = "fictive_src_echo_org"
LIST = "fictive_src_list_tenants"
DEMO = "demo"
SENTENCE = (
    "This server is bound to org demo; every tool acts on that organisation and takes no org."
)
TENANTS = Tenants(
    SOURCE, list_var="FICTIVE_SRC_TENANTS", param="org", fields=("SUBDOMAIN",), reserved=(DEMO,)
)
ACCOUNTS = Tenants(
    "fictive-mail", list_var="FICTIVE_MAIL_ACCOUNTS", param="account", fields=("REFRESH_TOKEN",)
)
LOCK = TenantLock(TENANTS, DEMO, noun="organisation")
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

        return build_server(ToolSet(SOURCE, bind_tasks([echo_org, list_tenants], lock)))


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


def test_a_lock_is_a_frozen_registry_tenant_and_noun() -> None:
    assert (LOCK.tenants, LOCK.value, LOCK.noun) == (TENANTS, DEMO, "organisation")
    assert TenantLock(tenants=TENANTS, value=DEMO, noun="organisation") == LOCK
    assert TenantLock(ACCOUNTS, DEMO).noun is None, "the parameter stands for the noun"
    with pytest.raises(dataclasses.FrozenInstanceError):
        LOCK.value = "other"  # type: ignore[misc]


def test_a_lock_binds_the_parameter_its_registry_declares_and_no_other() -> None:
    """https://github.com/xippios/sdk-core/issues/299: one declaration, ``Tenants(param=)``."""
    assert (LOCK.param, TenantLock(ACCOUNTS, DEMO).param) == ("org", "account")
    with pytest.raises(TypeError, match=r"^a lock takes the source's Tenants registry"):
        TenantLock("org", DEMO)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "noun", "message"),
    [
        ("", None, "value must name the tenant"),
        ("acme", "", "noun must be a word"),
        ("acme", " ", "noun must be a word"),
    ],
)
def test_a_lock_needs_a_tenant_and_a_noun(value: str, noun: str | None, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TenantLock(TENANTS, value, noun=noun)


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


def test_an_unbound_server_takes_its_tasks_as_they_are() -> None:
    def ping() -> dict[str, bool]:
        """Answer without an organisation."""
        return {"pong": True}

    assert bind_tasks([ping, find_things], None) == [ping, find_things]
    assert bind_tasks(iter([ping]), None) == [ping], "any iterable, a list back"


def test_a_task_without_the_parameter_is_refused_naming_it_and_the_parameter() -> None:
    """https://github.com/xippios/sdk-core/issues/299: a bound server would serve it unbound."""

    def ping() -> dict[str, bool]:
        """Answer without an organisation."""
        return {"pong": True}

    def count_all(limit: int = 10) -> int:
        """Count every organisation's things.

        Args:
            limit: At most this many, e.g. ``5``.
        """
        return limit

    with pytest.raises(ValueError, match=r"^ping takes no org, the tenant's parameter") as one:
        bind_tasks([find_things, ping], LOCK)
    assert str(one.value) == (
        "ping takes no org, the tenant's parameter that the lock binds; a bound server serves "
        "the tenant list and the tasks that take org, and no other (conventions §7)"
    )
    listed: list[Callable[..., object]] = [ping, find_things, count_all]
    with pytest.raises(ValueError, match=r"^ping, count_all take no org, the tenant's parameter"):
        bind_tasks(iter(listed), LOCK)


EXAMPLE_TASKS = '''
from xippios.core import sync


async def list_currencies_async() -> dict[str, list[str]]:
    """List the currencies every organisation may book in."""
    return {"currencies": ["CHF", "EUR"]}


list_currencies = sync(list_currencies_async)
NO_TENANT_TASKS = frozenset({"list_currencies"})
'''


@pytest.fixture
def example_tasks(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """An invented tasks module that still names a task in ``NO_TENANT_TASKS``."""
    module = types.ModuleType("xippios.example.tasks")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(EXAMPLE_TASKS, module.__dict__)  # its functions' __module__ is the module
    return module


def test_a_declaration_beside_the_tasks_serves_no_task_unbound(
    example_tasks: types.ModuleType,
) -> None:
    """A bound server serves the tenant's tasks and the tenant list, and no other task.

    ``NO_TENANT_TASKS`` left core in 0.5.0, since no source declared it, so a task that
    takes no tenant is refused whatever its module declares (ADR-0036, amendment
    2026-11-24).
    """
    with pytest.raises(ValueError, match=r"^list_currencies takes no org, the tenant's"):
        bind_tasks([example_tasks.list_currencies, list_tenants], LOCK)
    (bound,) = bind_tasks([list_tenants], LOCK)
    assert bound is not list_tenants, "the tenant list lists the bound tenant alone"


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
    server = build_server(ToolSet(SOURCE, bind_tasks([list_rows], LOCK)))
    (tool,) = await server.list_tools()
    limit = tool.input_schema["properties"]["limit"]
    assert (limit["minimum"], limit["maximum"], limit["description"]) == (
        1,
        100,
        "Rows per page, 1 to 100.",
    )
    refused = await mcp_call_text(server, "fictive_src_list_rows", {"limit": 500})
    assert refused == (
        "error: InvalidRequestError: limit: Input should be less than or equal to 100. "
        "Nothing was sent."
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
    assert text == (
        "error: InvalidRequestError: org: Not an argument of this tool; it takes note. "
        "Nothing was sent."
    )
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
    server = Echo().server(TenantLock(TENANTS, "gone"))
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

    server = build_server(ToolSet(SOURCE, bind_tasks([create_thing], LOCK), read_only=False))
    (tool,) = await server.list_tools()
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False, "a write tool"
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
    assert tenant_instructions(None, TenantLock(ACCOUNTS, "work")) == (
        "This server is bound to account work; every tool acts on that account and takes no "
        "account."
    )


@pytest.mark.anyio
async def test_a_client_reads_the_bound_server_s_instructions() -> None:
    text = "Fictive via xippios. Every tool takes org."
    bound = "Fictive via xippios."
    server = build_server(
        ToolSet(
            SOURCE,
            bind_tasks([list_tenants], LOCK),
            instructions=tenant_instructions(text, LOCK, bound=bound),
        )
    )
    async with Client(server) as client:
        assert client.instructions == f"{bound} {SENTENCE}"
