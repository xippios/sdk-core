from decimal import Decimal

import pytest

from xippios.core import NotFoundError, Result, ResultMeta, UpstreamModel, parse_decimal, sync
from xippios.core.mcp import build_server
from xippios.core.testing import assert_projection, mcp_call


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
