from decimal import Decimal

import pytest
from mcp.client import Client

from xippios.core import NotFoundError, Result, ResultMeta, UpstreamModel, parse_decimal, sync
from xippios.core.mcp import build_server
from xippios.core.testing import assert_projection, mcp_call, mcp_call_text


class Full(UpstreamModel):
    name: str
    value: str
    extra: int


class Slim(UpstreamModel):
    name: str
    value: Decimal | None


def test_assert_projection_accepts_a_faithful_projection() -> None:
    full = Full(name="x", value="1,000", extra=1)
    slim = Slim.project(full, value=parse_decimal(full.value))
    assert_projection(slim, full, value=Decimal("1000"))


def test_assert_projection_rejects_a_changed_field() -> None:
    full = Full(name="x", value="1", extra=1)
    with pytest.raises(AssertionError, match="name"):
        assert_projection(Slim(name="y", value=Decimal("1")), full, value=Decimal("1"))
    with pytest.raises(AssertionError, match="does not have"):
        assert_projection(Slim(name="x", value=None), full, value=None, nope=1)


async def get_thing_async(name: str) -> Result[list[Slim]]:
    """Get a thing.

    Args:
        name: Which one.
    """
    if name == "missing":
        raise NotFoundError("no such thing", source="example")
    return Result(
        data=[Slim(name=name, value=Decimal("2.5"))],
        meta=ResultMeta(source="example", endpoint="e"),
    )


get_thing = sync(get_thing_async)


@pytest.mark.anyio
async def test_mcp_call_returns_decoded_json_with_numbers() -> None:
    server = build_server("example", [get_thing])
    payload = await mcp_call(server, "example_get_thing", {"name": "a"})
    assert payload["data"] == [{"name": "a", "value": 2.5}]
    assert payload["meta"]["source"] == "example"


@pytest.mark.anyio
async def test_mcp_call_fails_on_error_text() -> None:
    server = build_server("example", [get_thing])
    with pytest.raises(AssertionError, match="error: NotFoundError: no such thing"):
        await mcp_call(server, "example_get_thing", {"name": "missing"})


@pytest.mark.anyio
async def test_mcp_call_text_returns_the_text_error_text_included() -> None:
    # https://github.com/xippios/sdk-core/issues/168: the error answer is flagged
    # is_error, and mcp_call_text still returns its text for the test to assert.
    server = build_server("example", [get_thing])
    async with Client(server) as client:
        flagged = await client.call_tool("example_get_thing", {"name": "missing"})
    assert flagged.is_error is True
    text = await mcp_call_text(server, "example_get_thing", {"name": "missing"})
    assert text == "error: NotFoundError: no such thing"
    assert (await mcp_call_text(server, "example_get_thing", {"name": "a"})).startswith('{"data"')


def crash(name: str) -> None:
    """Crash.

    Args:
        name: Anything.
    """
    raise RuntimeError("a task that crashes")


@pytest.mark.anyio
async def test_mcp_call_fails_when_the_server_reports_an_error() -> None:
    server = build_server("example", [get_thing, crash])
    # The argument middleware answers in §8's form, flagged, so the middleware ran.
    refused = "error: InvalidRequestError: name: Field required"
    assert await mcp_call_text(server, "example_get_thing", {}) == refused
    with pytest.raises(AssertionError, match=refused):
        await mcp_call(server, "example_get_thing", {})
    # An MCP error of another kind fails both: an unknown tool, a task that crashed.
    with pytest.raises(AssertionError, match="Unknown tool: example_no_such_tool"):
        await mcp_call_text(server, "example_no_such_tool", {})
    with pytest.raises(AssertionError, match="Error executing tool example_crash"):
        await mcp_call_text(server, "example_crash", {"name": "a"})
    with pytest.raises(AssertionError, match="Error executing tool example_crash"):
        await mcp_call(server, "example_crash", {"name": "a"})
