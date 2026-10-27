"""TenantLock: a locked server refuses tool calls for another tenant before the tool runs.

Every call goes through ``mcp.Client`` connected in-process (``mcp_call``,
``mcp_call_text``), which runs the server's middleware chain, as sdk-cashctrl's
``--org`` tests established (tests/test_org_lock.py there).
"""

import dataclasses
import os
from collections.abc import Callable
from typing import Any

import pytest
from mcp.client import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent

from xippios.core import Tenants
from xippios.core.mcp import TenantLock, build_server
from xippios.core.mcp.server import is_write_server, register_tasks
from xippios.core.tenants import list_task
from xippios.core.testing import mcp_call, mcp_call_text

pytestmark = pytest.mark.anyio

TOOL = "example_echo_org"
REFUSAL = (
    "error: InvalidRequestError: this server is locked to org=acme; the call named another tenant"
)
LIST_VAR = "FICTIVE_LOCK_TENANTS"


def echo_task(calls: list[str]) -> Callable[..., Any]:
    async def echo_org(org: str) -> dict[str, str]:
        """Return the tenant the tool was called for.

        Args:
            org: A declared tenant, e.g. ``acme``.
        """
        calls.append(org)
        return {"org": org}

    return echo_org


def locked_server(calls: list[str], instructions: str | None = None) -> MCPServer:
    return build_server(
        "example",
        [echo_task(calls)],
        instructions=instructions,
        tenant_lock=TenantLock("org", "acme"),
    )


def test_a_lock_is_a_frozen_pair() -> None:
    lock = TenantLock("org", "acme")
    assert (lock.param, lock.value) == ("org", "acme")
    assert lock == TenantLock(param="org", value="acme")
    with pytest.raises(dataclasses.FrozenInstanceError):
        lock.value = "other"  # type: ignore[misc]


@pytest.mark.parametrize(("param", "value"), [("", "acme"), ("an org", "acme"), ("org", "")])
def test_a_lock_needs_a_parameter_name_and_a_tenant(param: str, value: str) -> None:
    with pytest.raises(ValueError, match=r"param must be|value must name"):
        TenantLock(param, value)


async def test_the_locked_tenant_passes() -> None:
    calls: list[str] = []
    assert await mcp_call(locked_server(calls), TOOL, {"org": "acme"}) == {"org": "acme"}
    assert calls == ["acme"]


@pytest.mark.parametrize("other", ["other", "ACME", "", None])
async def test_another_tenant_is_refused_without_running_the_tool(other: str | None) -> None:
    calls: list[str] = []
    text = await mcp_call_text(locked_server(calls), TOOL, {"org": other})
    assert text == REFUSAL  # text, as every family error, so mcp_call_text saw no is_error
    assert calls == []


MISSING = (
    "error: InvalidRequestError: this server is locked to org=acme; "
    "the call did not name the tenant"
)


async def test_a_call_that_leaves_out_the_declared_parameter_is_refused() -> None:
    calls: list[str] = []
    server = locked_server(calls)
    assert await mcp_call_text(server, TOOL, {}) == MISSING
    async with Client(server) as client:
        result = await client.call_tool(TOOL)  # no arguments at all
    content = result.content[0]
    assert isinstance(content, TextContent)
    assert content.text == MISSING
    assert not result.is_error
    assert calls == []


async def test_a_failing_schema_lookup_refuses_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    server = locked_server(calls)
    list_tools = server.list_tools
    failures = [RuntimeError("tool listing failed")]

    async def failing_once() -> list[Any]:
        # The lock's lookup comes first and fails; the client's own tools/list after
        # the call, which validates the result, gets the real listing.
        if failures:
            raise failures.pop()
        return await list_tools()

    monkeypatch.setattr(server, "list_tools", failing_once)
    assert await mcp_call_text(server, TOOL, {}) == MISSING  # text, not an MCP error
    assert failures == []  # the lookup ran and failed
    assert calls == []
    assert await mcp_call(server, TOOL, {"org": "acme"}) == {"org": "acme"}  # no lookup
    assert calls == ["acme"]


async def ping() -> dict[str, bool]:
    """Answer without a tenant."""
    return {"pong": True}


async def test_a_tool_that_does_not_take_the_parameter_is_untouched() -> None:
    calls: list[str] = []
    server = build_server(
        "example", [echo_task(calls), ping], tenant_lock=TenantLock("org", "acme")
    )
    assert await mcp_call(server, "example_ping", {}) == {"pong": True}
    assert await mcp_call_text(server, "example_ping", {"org": "other"}) == REFUSAL


def defaulted_task() -> Callable[..., Any]:
    async def echo_default(org: str = "acme") -> dict[str, str]:
        """Return the tenant, which has a default.

        Args:
            org: A declared tenant, e.g. ``acme``.
        """
        return {"org": org}

    return echo_default


def test_a_locked_server_refuses_a_tenant_parameter_with_a_default() -> None:
    lock = TenantLock("org", "acme")
    rule = (
        r"^example_echo_default: org has a default; a tool that takes the tenant parameter "
        r"must receive it on a locked server \(org=acme\), and a default is refused"
    )
    with pytest.raises(ValueError, match=rule):
        build_server("example", [echo_task([]), defaulted_task()], tenant_lock=lock)
    server = locked_server([])
    before = len(server.middleware)
    with pytest.raises(ValueError, match=rule):
        register_tasks(server, "example", [defaulted_task()])
    with pytest.raises(ValueError, match=rule):
        register_tasks(server, "example", [defaulted_task()], tenant_lock=lock)
    assert len(server.middleware) == before


async def test_a_lock_is_refused_on_a_server_with_a_defaulted_tenant_parameter() -> None:
    server = build_server("example", [defaulted_task()])  # unlocked: the default is fine
    assert await mcp_call(server, "example_echo_default", {}) == {"org": "acme"}
    before = len(server.middleware)
    with pytest.raises(ValueError, match=r"^example_echo_default: org has a default"):
        register_tasks(server, "example", [], tenant_lock=TenantLock("org", "beta"))
    assert len(server.middleware) == before  # nothing installed
    assert await mcp_call(server, "example_echo_default", {}) == {"org": "acme"}


async def test_listing_tools_is_unaffected() -> None:
    async with Client(locked_server([])) as client:
        tools = await client.list_tools()
    assert [tool.name for tool in tools.tools] == [TOOL]


async def test_a_locked_server_names_the_tenant_in_its_instructions() -> None:
    sentence = (
        "This server is locked to org acme; every tool call that takes org must pass org=acme."
    )
    server = locked_server([], instructions="Example via xippios.")
    assert server.instructions == f"Example via xippios. {sentence}"
    async with Client(server) as client:
        assert client.instructions == f"Example via xippios. {sentence}"
    assert locked_server([]).instructions == sentence


async def test_an_unlocked_server_keeps_its_instructions() -> None:
    calls: list[str] = []
    server = build_server("example", [echo_task(calls)], instructions="Example via xippios.")
    assert server.instructions == "Example via xippios."
    assert await mcp_call(server, TOOL, {"org": "other"}) == {"org": "other"}
    assert calls == ["other"]


async def test_register_tasks_installs_the_lock_once_per_server() -> None:
    calls: list[str] = []
    server = build_server("example", [], instructions="Kept.")
    before = len(server.middleware)
    lock = TenantLock("org", "acme")
    register_tasks(server, "example", [echo_task(calls)], tenant_lock=lock)
    register_tasks(server, "example", [], tenant_lock=TenantLock("org", "acme"))
    assert len(server.middleware) == before + 1
    assert server.instructions == "Kept."  # only build_server adds the sentence
    with pytest.raises(ValueError, match="locked to org=acme already"):
        register_tasks(server, "example", [], tenant_lock=TenantLock("org", "other"))
    assert len(server.middleware) == before + 1
    assert await mcp_call_text(server, TOOL, {"org": "other"}) == REFUSAL
    assert calls == []


@pytest.fixture
def tenants(monkeypatch: pytest.MonkeyPatch) -> Tenants:
    for name in [name for name in os.environ if name.startswith("FICTIVE_LOCK_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(LIST_VAR, "acme,beta")
    monkeypatch.setenv("FICTIVE_LOCK_DEMO_SUBDOMAIN", "demo")
    return Tenants("fictive-lock", list_var=LIST_VAR, fields=["SUBDOMAIN"], reserved=["demo"])


async def test_the_tenant_list_names_only_the_locked_tenant(tenants: Tenants) -> None:
    listing = list_task(tenants, name="list_organisations")
    tool = "fictive_lock_list_organisations"
    unlocked = build_server("fictive-lock", [listing])
    assert (await mcp_call(unlocked, tool, {}))["data"] == ["acme", "beta", "demo"]
    locked = build_server("fictive-lock", [listing], tenant_lock=TenantLock("org", "beta"))
    payload = await mcp_call(locked, tool, {})
    assert payload["data"] == ["beta"]
    assert payload["meta"]["endpoint"] == "list_organisations"
    assert listing().data == ["acme", "beta", "demo"]  # the task itself is unchanged


async def test_a_tenant_list_registered_before_the_lock_is_narrowed_too(
    tenants: Tenants,
) -> None:
    server = build_server("fictive-lock", [list_task(tenants, name="list_organisations")])
    register_tasks(server, "fictive-lock", [], tenant_lock=TenantLock("org", "demo"))
    payload = await mcp_call(server, "fictive_lock_list_organisations", {})
    assert payload["data"] == ["demo"]


async def test_a_lock_on_an_undeclared_tenant_lists_nothing(tenants: Tenants) -> None:
    server = build_server(
        "fictive-lock",
        [list_task(tenants, name="list_organisations")],
        tenant_lock=TenantLock("org", "gone"),
    )
    assert (await mcp_call(server, "fictive_lock_list_organisations", {}))["data"] == []


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name}


def test_registering_with_read_only_false_makes_a_write_server() -> None:
    assert is_write_server(build_server("example", [create_thing], read_only=False))
    assert is_write_server(build_server("example", [], read_only=False))
    assert not is_write_server(build_server("example", [create_thing]))
    server = build_server("example", [])
    register_tasks(server, "example", [create_thing], read_only=False)
    assert is_write_server(server)
