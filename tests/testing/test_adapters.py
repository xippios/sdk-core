from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, Any

import pytest

from xippios.core import NotFoundError, Result, ResultMeta, UpstreamModel, parse_decimal, sync
from xippios.core.http import router_from_tasks
from xippios.core.mcp import TenantLock, build_server, register_tasks
from xippios.core.testing import assert_projection, assert_write_tools, mcp_call, mcp_call_text


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
    server = build_server("example", [get_thing])
    text = await mcp_call_text(server, "example_get_thing", {"name": "missing"})
    assert text == "error: NotFoundError: no such thing"
    assert (await mcp_call_text(server, "example_get_thing", {"name": "a"})).startswith('{"data"')


@pytest.mark.anyio
async def test_mcp_call_goes_through_the_middleware() -> None:
    server = build_server("example", [get_thing], tenant_lock=TenantLock("name", "a"))
    assert (await mcp_call(server, "example_get_thing", {"name": "a"}))["data"][0]["name"] == "a"
    refusal = "error: InvalidRequestError: this server is locked to name=a"
    assert (await mcp_call_text(server, "example_get_thing", {"name": "b"})).startswith(refusal)
    with pytest.raises(AssertionError, match=refusal):
        await mcp_call(server, "example_get_thing", {"name": "b"})


@pytest.mark.anyio
async def test_mcp_call_fails_when_the_server_reports_an_error() -> None:
    server = build_server("example", [get_thing])
    with pytest.raises(AssertionError, match="name"):
        await mcp_call_text(server, "example_get_thing", {})  # the schema requires name
    with pytest.raises(AssertionError):
        await mcp_call(server, "example_no_such_tool", {})


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name, "written": str(confirm)}


def delete_thing(thing_id: int, confirm: Annotated[bool, "write"] = False) -> dict[str, int]:
    """Delete a thing; without confirm, return a preview.

    Args:
        thing_id: The thing's id, e.g. ``4``.
        confirm: ``True`` deletes, ``False`` previews.
    """
    return {"id": thing_id}


def list_things() -> list[str]:
    """List the things."""
    return ["a"]


WRITE: list[Callable[..., Any]] = [create_thing, delete_thing]
READ: list[Callable[..., Any]] = [list_things]


def test_assert_write_tools_accepts_a_separate_write_server() -> None:
    assert_write_tools(
        build_server("example", WRITE, read_only=False),
        WRITE,
        source="example",
        read_server=build_server("example", READ),
        router=router_from_tasks("example", READ),
    )


@pytest.mark.anyio
async def test_assert_write_tools_works_in_an_async_test() -> None:
    assert_write_tools(build_server("example", WRITE, read_only=False), WRITE, source="example")


def test_assert_write_tools_wants_a_server_registered_as_a_write_server() -> None:
    read_only = build_server("example", [])
    register_tasks(read_only, "example", WRITE)  # the write tasks, registered read-only
    with pytest.raises(
        AssertionError,
        match=(
            r"^the write server was not registered with read_only=False; "
            r"the loopback rule depends on it$"
        ),
    ):
        assert_write_tools(read_only, WRITE, source="example")


def test_assert_write_tools_wants_exactly_the_write_tasks() -> None:
    # build_server refuses a write task without confirm (conventions §8); a read-only
    # registration on the write server is how a stray tool would get there.
    write = build_server("example", WRITE, read_only=False)
    register_tasks(write, "example", [list_things])
    with pytest.raises(AssertionError, match=r"not write tasks: \['example_list_things'\]"):
        assert_write_tools(write, WRITE, source="example")
    write = build_server("example", [create_thing], read_only=False)
    with pytest.raises(AssertionError, match=r"missing .*: \['example_delete_thing'\]"):
        assert_write_tools(write, WRITE, source="example")


def no_confirm(name: str) -> None:
    """No confirm at all."""


def confirm_true(confirm: bool = True) -> None:
    """Writes unless told not to."""


def confirm_required(confirm: bool) -> None:
    """Must be told."""


def confirm_unannotated(confirm=False):  # type: ignore[no-untyped-def]
    """Not annotated."""


def confirm_optional(confirm: bool | None = False) -> None:
    """Optional."""


def confirm_zero(confirm: int = 0) -> None:
    """An int."""


@pytest.mark.parametrize(
    ("task", "problem"),
    [
        (no_confirm, "no parameter confirm"),
        (confirm_true, "confirm defaults to True, not False"),
        (confirm_required, "confirm has no default"),
        (confirm_unannotated, "confirm is not annotated"),
        (confirm_optional, r"confirm is annotated bool \| None, not bool"),
        (confirm_zero, "confirm is annotated <class 'int'>, not bool"),
    ],
)
def test_assert_write_tools_wants_confirm_false(task: Callable[..., Any], problem: str) -> None:
    write = build_server("example", [create_thing], read_only=False)
    register_tasks(write, "example", [task])  # build_server(read_only=False) refuses it
    with pytest.raises(AssertionError, match=f"^example_{task.__name__}: {problem}; "):
        assert_write_tools(write, [create_thing, task], source="example")


def test_assert_write_tools_keeps_write_tools_off_the_read_adapters() -> None:
    write = build_server("example", WRITE, read_only=False)
    read = build_server("example", [list_things, delete_thing])
    with pytest.raises(AssertionError, match=r"on the read server: \['example_delete_thing'\]"):
        assert_write_tools(write, WRITE, source="example", read_server=read)
    router = router_from_tasks("example", [list_things, create_thing])
    with pytest.raises(
        AssertionError,
        match=r"^example_create_thing: a write task has an HTTP route, GET /example/create_thing",
    ):
        assert_write_tools(write, WRITE, source="example", router=router)
    router = router_from_tasks("example", [delete_thing], prefix="/v1")
    with pytest.raises(AssertionError, match=r"^example_delete_thing: .* GET /v1/delete_thing"):
        assert_write_tools(write, WRITE, source="example", router=router)


def test_assert_write_tools_names_tools_with_the_underscored_source() -> None:
    write = build_server("usda-nass", WRITE, read_only=False)
    assert_write_tools(
        write, WRITE, source="usda-nass", router=router_from_tasks("usda-nass", READ)
    )
    router = router_from_tasks("usda-nass", WRITE)
    with pytest.raises(AssertionError, match=r"^usda_nass_create_thing: "):
        assert_write_tools(write, WRITE, source="usda-nass", router=router)
