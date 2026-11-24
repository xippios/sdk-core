import inspect
import typing
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Literal

import httpx
import pytest
import respx
from mcp.client import Client
from pydantic import Field

from xippios.core import (
    InvalidRequestError,
    NotFoundError,
    Result,
    ResultMeta,
    TenantLock,
    Tenants,
    UpstreamModel,
    bind_tasks,
    parse_decimal,
    sync,
)
from xippios.core.http import router_from_tasks
from xippios.core.mcp import ToolSet, build_server
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
    server = build_server(ToolSet("example", [get_thing]))
    payload = await mcp_call(server, "example_get_thing", {"name": "a"})
    assert payload["data"] == [{"name": "a", "value": 2.5}]
    assert payload["meta"]["source"] == "example"


@pytest.mark.anyio
async def test_mcp_call_fails_on_error_text() -> None:
    server = build_server(ToolSet("example", [get_thing]))
    with pytest.raises(AssertionError, match="error: NotFoundError: no such thing"):
        await mcp_call(server, "example_get_thing", {"name": "missing"})


@pytest.mark.anyio
async def test_mcp_call_text_returns_the_text_error_text_included() -> None:
    # https://github.com/xippios/sdk-core/issues/168: the error answer is flagged
    # is_error, and mcp_call_text still returns its text for the test to assert.
    server = build_server(ToolSet("example", [get_thing]))
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
    server = build_server(ToolSet("example", [get_thing, crash]))
    # The argument middleware answers in §8's form, flagged, so the middleware ran.
    refused = "error: InvalidRequestError: name: Field required. Nothing was sent."
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


# assert_write_tools: a write server against its write tasks (conventions §8) ---------
# The tests of the two copies, two sources'
# tests/test_tasks_write.py, which core removed in 0.3.0 and takes back in 0.4.0 with the
# check that confirm is the last parameter (ADR-0042, decision 1). Every write task holds
# its preview, which the check reads in every call (ADR-0050, decision 4).


class ThingPreview(UpstreamModel):
    """What a thing's write would send; nothing was written."""

    performed: Literal[False] = False
    reads: list[str]


def previewed(endpoint: str) -> Result[ThingPreview]:
    """The preview of a write that reads nothing first."""
    meta = ResultMeta(source="example", endpoint=endpoint)
    return Result[ThingPreview](data=ThingPreview(reads=[]), meta=meta)


def create_thing(name: str, confirm: bool = False) -> Result[ThingPreview]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return previewed("thing/create")


def delete_thing(
    thing_id: int, confirm: typing.Annotated[bool, "write"] = False
) -> Result[ThingPreview]:
    """Delete a thing; without confirm, return a preview.

    Args:
        thing_id: The thing's id, e.g. ``4``.
        confirm: ``True`` deletes, ``False`` previews.
    """
    return previewed("thing/delete")


def list_things() -> list[str]:
    """List the things."""
    return ["a"]


WRITE: list[Callable[..., Any]] = [create_thing, delete_thing]
READ: list[Callable[..., Any]] = [list_things]


@pytest.mark.anyio
async def test_assert_write_tools_accepts_a_separate_write_server() -> None:
    await assert_write_tools(
        ToolSet("example", WRITE, read_only=False),
        WRITE,
        read_server=build_server(ToolSet("example", READ)),
        router=router_from_tasks("example", READ),
    )
    await assert_write_tools(ToolSet("example", WRITE, read_only=False), iter(WRITE))


@pytest.mark.anyio
async def test_assert_write_tools_accepts_a_server_a_lock_binds() -> None:
    def rename_thing(org: str, name: str, confirm: bool = False) -> Result[ThingPreview]:
        """Rename a thing; without confirm, return a preview.

        Args:
            org: A declared organisation, e.g. ``demo``.
            name: The new name, e.g. ``"Corn"``.
            confirm: ``True`` writes, ``False`` previews.
        """
        return previewed("thing/rename")

    tenants = Tenants("example-src", list_var="EXAMPLE_SRC_TENANTS", param="org", fields=("KEY",))
    bound = bind_tasks([rename_thing], TenantLock(tenants, "demo"))
    await assert_write_tools(ToolSet("example", bound, read_only=False), bound)


@pytest.mark.anyio
async def test_assert_write_tools_wants_a_write_tool_set() -> None:
    # ADR-0063, decision 5: the loopback rule reads the tool set's read_only, where it
    # read is_write_server's registry.
    with pytest.raises(
        AssertionError,
        match=(
            r"^the write tool set is read-only: build it with read_only=False, which the "
            r"loopback rule reads"
        ),
    ):
        await assert_write_tools(ToolSet("example", WRITE), WRITE)
    server = build_server(ToolSet("example", WRITE, read_only=False))
    with pytest.raises(TypeError, match=r"^write_tools takes the write server's ToolSet, "):
        await assert_write_tools(server, WRITE)


@pytest.mark.anyio
async def test_assert_write_tools_wants_exactly_the_write_tasks() -> None:
    with pytest.raises(AssertionError, match=r"not write tasks: \['example_delete_thing'\]"):
        await assert_write_tools(ToolSet("example", WRITE, read_only=False), [create_thing])
    write = ToolSet("example", [create_thing], read_only=False)
    with pytest.raises(AssertionError, match=r"missing .*: \['example_delete_thing'\]"):
        await assert_write_tools(write, WRITE)


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


def confirm_first(confirm: bool = False, name: str = "") -> None:
    """Confirm before the other parameters."""


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
def test_a_write_task_without_confirm_false_never_reaches_the_check(
    task: Callable[..., Any], problem: str
) -> None:
    # The write tool set refuses it when it is built (ADR-0063, decision 3).
    with pytest.raises(ValueError, match=f"^example_{task.__name__}: {problem}; "):
        ToolSet("example", [create_thing, task], read_only=False)


@pytest.mark.anyio
async def test_assert_write_tools_wants_confirm_last() -> None:
    write = ToolSet("example", [create_thing, confirm_first], read_only=False)
    with pytest.raises(
        AssertionError, match=r"^example_confirm_first: confirm is not the last parameter; "
    ):
        await assert_write_tools(write, [create_thing, confirm_first])


@pytest.mark.anyio
async def test_assert_write_tools_keeps_write_tools_off_the_read_adapters() -> None:
    write = ToolSet("example", WRITE, read_only=False)
    read = build_server(ToolSet("example", [list_things, delete_thing]))
    with pytest.raises(AssertionError, match=r"on the read server: \['example_delete_thing'\]"):
        await assert_write_tools(write, WRITE, read_server=read)
    with_write = router_from_tasks("example", [list_things, create_thing])
    with pytest.raises(
        AssertionError,
        match=r"^example_create_thing: a write task has an HTTP route, GET /example/create_thing",
    ):
        await assert_write_tools(write, WRITE, router=with_write)
    prefixed = router_from_tasks("example", [delete_thing], prefix="/v1")
    with pytest.raises(AssertionError, match=r"^example_delete_thing: .* GET /v1/delete_thing"):
        await assert_write_tools(write, WRITE, router=prefixed)


@pytest.mark.anyio
async def test_assert_write_tools_names_tools_with_the_underscored_source() -> None:
    write = ToolSet("example-api", WRITE, read_only=False)
    await assert_write_tools(write, WRITE, router=router_from_tasks("example-api", READ))
    with_write = router_from_tasks("example-api", WRITE)
    with pytest.raises(AssertionError, match=r"^example_api_create_thing: "):
        await assert_write_tools(write, WRITE, router=with_write)


# What a write tool's preview shows (conventions §8; ADR-0050) ------------------------
# A write task's answer holds one member tagged performed: Literal[False], the preview,
# which declares reads, the operations it read. Every call holds the annotations, and
# the dry run calls each tool without confirm and compares reads with what the router saw.
# One source's previews read with GET, as rename_item's does, and another's read nothing
# but a reply's, as add_item's reads nothing.

ITEMS = "https://items.example.test"


class Item(UpstreamModel):
    id: int
    name: str


class ItemPreview(UpstreamModel):
    """What an item's write would send; nothing was written."""

    performed: Literal[False] = False
    endpoint: str
    payload: dict[str, str]
    reads: list[str]


class RecordPreview[T](UpstreamModel):
    """A preview generic in the record it shows, as a source's ``WritePreview[T]`` is."""

    performed: Literal[False] = False
    endpoint: str
    payload: dict[str, str]
    reads: list[str]
    before: T | None = None


class BarePreview(UpstreamModel):
    """A preview tagged as one that says nothing of what it read."""

    performed: Literal[False] = False
    endpoint: str


class ItemWritten(UpstreamModel):
    performed: Literal[True] = True
    id: int


type ItemOutcome = ItemPreview | ItemWritten
"""A ``type`` alias of the union, which the check reads through as it reads the union."""


def _meta(endpoint: str) -> ResultMeta:
    return ResultMeta(source="example", endpoint=endpoint)


def _shown(data: ItemPreview | ItemWritten) -> Result[ItemPreview | ItemWritten]:
    endpoint = data.endpoint if isinstance(data, ItemPreview) else "item/create.json"
    return Result[ItemPreview | ItemWritten](data=data, meta=_meta(endpoint))


async def add_item_async(name: str, confirm: bool = False) -> Result[ItemPreview | ItemWritten]:
    """Add an item; without confirm=true it shows the payload and reads nothing.

    Args:
        name: The item's name, e.g. ``"Corn"``.
        confirm: ``true`` adds it; ``false`` (the default) only previews it.
    """
    if not name.strip():
        raise InvalidRequestError("name is empty; nothing was sent", source="example")
    payload = {"name": name}
    if confirm is not True:
        return _shown(ItemPreview(endpoint="item/create.json", payload=payload, reads=[]))
    async with httpx.AsyncClient(base_url=ITEMS) as client:
        answer = await client.post("/item/create.json", data=payload)
    return _shown(ItemWritten(id=answer.json()["id"]))


async def rename_item_async(
    item_id: int, name: str, confirm: bool = False
) -> Result[RecordPreview[Item] | ItemWritten]:
    """Rename an item; without confirm=true it reads the item, one GET, and shows it.

    Args:
        item_id: The item's id, e.g. ``4``.
        name: The new name, e.g. ``"Wheat"``.
        confirm: ``true`` renames it; ``false`` (the default) only previews it.
    """
    endpoint = "item/update.json"
    payload = {"id": str(item_id), "name": name}
    async with httpx.AsyncClient(base_url=ITEMS) as client:
        stored = Item(**(await client.get("/item/read.json", params={"id": item_id})).json())
        if confirm is not True:
            preview = RecordPreview[Item](
                endpoint=endpoint, payload=payload, reads=["item/read.json"], before=stored
            )
            return Result[RecordPreview[Item] | ItemWritten](data=preview, meta=_meta(endpoint))
        await client.post(f"/{endpoint}", data=payload)
    return Result[RecordPreview[Item] | ItemWritten](
        data=ItemWritten(id=item_id), meta=_meta(endpoint)
    )


add_item = sync(add_item_async)
rename_item = sync(rename_item_async)
PREVIEWED: list[Callable[..., Any]] = [add_item, rename_item]


async def tag_items(tag: str, confirm: bool = False) -> Result[ItemOutcome]:
    """Tag the items a search finds; the preview reads them with a POST, as some upstreams do.

    Args:
        tag: The tag, e.g. ``"grain"``.
        confirm: ``true`` tags them; ``false`` (the default) only previews it.
    """
    async with httpx.AsyncClient(base_url=ITEMS) as client:
        await client.post("/item/search.json", json={"tag": tag})
    return _shown(ItemPreview(endpoint="item/tag.json", payload={}, reads=["item/search.json"]))


async def add_item_posting(name: str, confirm: bool = False) -> Result[ItemOutcome]:
    """A preview that writes.

    Args:
        name: The item's name.
        confirm: Ignored.
    """
    async with httpx.AsyncClient(base_url=ITEMS) as client:
        await client.post("/item/create.json", data={"name": name})
    return _shown(ItemPreview(endpoint="item/create.json", payload={"name": name}, reads=[]))


async def rename_item_quietly(item_id: int, confirm: bool = False) -> Result[ItemOutcome]:
    """A preview that read and says it did not.

    Args:
        item_id: The item's id.
        confirm: Ignored.
    """
    async with httpx.AsyncClient(base_url=ITEMS) as client:
        await client.get("/item/read.json", params={"id": item_id})
    return _shown(ItemPreview(endpoint="item/update.json", payload={}, reads=[]))


async def rename_item_claiming(item_id: int, confirm: bool = False) -> Result[ItemOutcome]:
    """A preview that says it read and sent nothing.

    Args:
        item_id: The item's id.
        confirm: Ignored.
    """
    return _shown(ItemPreview(endpoint="item/update.json", payload={}, reads=["item/read.json"]))


async def add_item_at_once(name: str, confirm: bool = False) -> Result[ItemOutcome]:
    """A task whose call without confirm answers as a confirmed one does.

    Args:
        name: The item's name.
        confirm: Ignored.
    """
    return _shown(ItemWritten(id=5))


async def add_item_unpreviewed(name: str, confirm: bool = False) -> Result[ItemWritten]:
    """A write task with no preview member."""
    return Result[ItemWritten](data=ItemWritten(id=5), meta=_meta("item/create.json"))


async def add_item_bare(name: str, confirm: bool = False) -> Result[BarePreview | ItemWritten]:
    """A preview without reads."""
    preview = BarePreview(endpoint="item/create.json")
    return Result[BarePreview | ItemWritten](data=preview, meta=_meta("item/create.json"))


async def add_item_twice(name: str, confirm: bool = False) -> Result[ItemPreview | BarePreview]:
    """Two members tagged as the preview."""
    preview = BarePreview(endpoint="item/create.json")
    return Result[ItemPreview | BarePreview](data=preview, meta=_meta("item/create.json"))


def add_item_unwrapped(name: str, confirm: bool = False) -> dict[str, str]:
    """A write task that returns its preview outside a ``Result``."""
    return {"name": name}


async def add_item_unannotated(name: str, confirm: bool = False):  # type: ignore[no-untyped-def]
    """A write task whose return is not annotated."""
    return _shown(ItemPreview(endpoint="item/create.json", payload={}, reads=[]))


async def add_item_long(name: str, confirm: bool = False) -> Result[ItemOutcome]:
    """A preview past the byte bound of the default cap, which the tool answers cut.

    Args:
        name: The item's name.
        confirm: Ignored.
    """
    payload = {"name": name, "notes": "x" * 70_000}
    return _shown(ItemPreview(endpoint="item/create.json", payload=payload, reads=[]))


class UnshownPreview(UpstreamModel):
    """A preview that declares reads and leaves it out of its JSON."""

    performed: Literal[False] = False
    reads: list[str] = Field(default_factory=list, exclude=True)


async def add_item_unshown(name: str, confirm: bool = False) -> Result[UnshownPreview]:
    """A preview whose answer over MCP carries no reads.

    Args:
        name: The item's name.
        confirm: Ignored.
    """
    return Result[UnshownPreview](data=UnshownPreview(), meta=_meta("item/create.json"))


@pytest.mark.anyio
async def test_the_check_holds_one_preview_that_declares_reads() -> None:
    # Both previews pass, the generic one through the sync facade's annotations too, and so
    # does a Result whose data is a type alias of the union.
    write = ToolSet("example", PREVIEWED, read_only=False)
    await assert_write_tools(write, PREVIEWED)
    tagging = ToolSet("example", [tag_items], read_only=False)
    await assert_write_tools(tagging, [tag_items])


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("task", "problem"),
    [
        pytest.param(
            add_item_unpreviewed,
            r"no member of its Result's data is tagged performed: Literal\[False\], the preview",
            id="no-preview-member",
        ),
        pytest.param(
            add_item_bare,
            r"the preview BarePreview declares no reads: list\[str\], the operations it read",
            id="no-reads",
        ),
        pytest.param(
            add_item_twice,
            r"2 members of its Result's data are tagged performed: Literal\[False\]: "
            r"ItemPreview, BarePreview; one is the preview",
            id="two-previews",
        ),
        pytest.param(
            add_item_unwrapped,
            r"returns dict\[str, str\], not a Result whose data holds the preview",
            id="no-result",
        ),
        pytest.param(
            add_item_unannotated,
            r"its return is not annotated; a write task returns a Result that holds its preview",
            id="not-annotated",
        ),
    ],
)
async def test_the_check_fails_a_write_task_without_its_preview(
    task: Callable[..., Any], problem: str
) -> None:
    # No switch: preview_reads, which no source passed, left in 0.5.0, so every call holds
    # the write tasks' previews (https://github.com/xippios/sdk-core/issues/475, part 7).
    write = ToolSet("example", [task], read_only=False)
    with pytest.raises(AssertionError, match=f"^example_{task.__name__}: {problem}$"):
        await assert_write_tools(write, [task])


def test_the_check_takes_no_switch_for_the_preview() -> None:
    assert "preview_reads" not in inspect.signature(assert_write_tools).parameters


@pytest.mark.anyio
async def test_a_dry_run_passes_a_preview_that_reads_and_one_that_does_not(
    respx_mock: respx.MockRouter,
) -> None:
    read = respx_mock.get(f"{ITEMS}/item/read.json").respond(200, json={"id": 4, "name": "Corn"})
    write = ToolSet("example", PREVIEWED, read_only=False)
    await assert_write_tools(
        write,
        PREVIEWED,
        dry_run={
            "add_item": {"name": "Corn"},
            "rename_item": [{"item_id": 4, "name": "Wheat"}, {"item_id": 4, "name": "Rye"}],
        },
        sent=respx_mock,
    )
    assert read.call_count == 2, "one read for each call of rename_item, none for add_item"


@pytest.mark.anyio
async def test_a_dry_run_fails_a_preview_that_writes(respx_mock: respx.MockRouter) -> None:
    created = respx_mock.post(f"{ITEMS}/item/create.json").respond(200, json={"id": 5})
    write = ToolSet("example", [add_item_posting], read_only=False)
    with pytest.raises(
        AssertionError,
        match=(
            r"^example_add_item_posting: the preview sent a request that is no read, "
            r"POST /item/create\.json; a preview sends no write$"
        ),
    ):
        await assert_write_tools(
            write,
            [add_item_posting],
            dry_run={"add_item_posting": {"name": "Corn"}},
            sent=respx_mock,
        )
    assert created.called


@pytest.mark.anyio
async def test_a_dry_run_fails_a_preview_that_read_and_says_it_did_not(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(f"{ITEMS}/item/read.json").respond(200, json={"id": 4, "name": "Corn"})
    write = ToolSet("example", [rename_item_quietly], read_only=False)
    with pytest.raises(
        AssertionError,
        match=(
            r"^example_rename_item_quietly: the preview sent GET /item/read\.json "
            r"and its reads is empty$"
        ),
    ):
        await assert_write_tools(
            write,
            [rename_item_quietly],
            dry_run={"rename_item_quietly": {"item_id": 4}},
            sent=respx_mock,
        )


@pytest.mark.anyio
async def test_a_dry_run_fails_a_preview_that_says_it_read_and_sent_nothing(
    respx_mock: respx.MockRouter,
) -> None:
    write = ToolSet("example", [rename_item_claiming], read_only=False)
    with pytest.raises(
        AssertionError,
        match=(
            r"^example_rename_item_claiming: the preview's reads names "
            r"\['item/read\.json'\] and it sent no request$"
        ),
    ):
        await assert_write_tools(
            write,
            [rename_item_claiming],
            dry_run={"rename_item_claiming": {"item_id": 4}},
            sent=respx_mock,
        )


@pytest.mark.anyio
async def test_a_dry_run_fails_a_write_task_without_a_preview_member() -> None:
    # The dry run reads reads, so it holds the preview's annotation first.
    write = ToolSet("example", [add_item_unpreviewed], read_only=False)
    with pytest.raises(AssertionError, match=r"^example_add_item_unpreviewed: no member "):
        await assert_write_tools(
            write,
            [add_item_unpreviewed],
            dry_run={"add_item_unpreviewed": {"name": "Corn"}},
            sent=respx.MockRouter(),
        )


@pytest.mark.anyio
async def test_a_dry_run_fails_an_answer_that_is_no_preview(
    respx_mock: respx.MockRouter,
) -> None:
    write = ToolSet("example", [add_item_at_once], read_only=False)
    with pytest.raises(
        AssertionError,
        match=r"^example_add_item_at_once: the dry run's answer is no preview, performed is True$",
    ):
        await assert_write_tools(
            write,
            [add_item_at_once],
            dry_run={"add_item_at_once": {"name": "Corn"}},
            sent=respx_mock,
        )


@pytest.mark.anyio
async def test_a_dry_run_fails_a_refused_call_with_its_answer(
    respx_mock: respx.MockRouter,
) -> None:
    write = ToolSet("example", [add_item], read_only=False)
    with pytest.raises(
        AssertionError,
        match=(
            r"^example_add_item: the dry run answered "
            r"error: InvalidRequestError: name is empty; nothing was sent$"
        ),
    ):
        await assert_write_tools(
            write,
            [add_item],
            dry_run={"add_item": {"name": " "}},
            sent=respx_mock,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("task", "problem"),
    [
        pytest.param(
            add_item_long,
            r"the result cap cut the dry run's answer: result is \d+ bytes, over the cap of "
            r"65536; narrow the query to see the rest",
            id="cut-by-the-cap",
        ),
        pytest.param(
            add_item_unshown,
            r"the preview carries no reads, the list of the operations it read",
            id="reads-not-in-the-answer",
        ),
    ],
)
async def test_a_dry_run_judges_the_answer_the_tool_gives(
    respx_mock: respx.MockRouter, task: Callable[..., Any], problem: str
) -> None:
    # The dry run reads the tool's text, as an agent does, not the task's model.
    write = ToolSet("example", [task], read_only=False)
    with pytest.raises(AssertionError, match=f"^example_{task.__name__}: {problem}$"):
        await assert_write_tools(
            write,
            [task],
            dry_run={task.__name__: {"name": "Corn"}},
            sent=respx_mock,
        )


@pytest.mark.anyio
async def test_a_source_declares_a_read_that_upstream_takes_by_post(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{ITEMS}/item/search.json").respond(200, json=[])
    write = ToolSet("example", [tag_items], read_only=False)
    arguments: dict[str, Any] = {"dry_run": {"tag_items": {"tag": "grain"}}, "sent": respx_mock}
    with pytest.raises(AssertionError, match=r"no read, POST /item/search\.json; "):
        await assert_write_tools(write, [tag_items], **arguments)

    def is_read(request: httpx.Request) -> bool:
        return request.method == "GET" or request.url.path == "/item/search.json"

    await assert_write_tools(write, [tag_items], is_read=is_read, **arguments)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("dry_run", "problem"),
    [
        pytest.param(
            {"add_item": {"name": "Corn"}},
            r"^dry_run gives no arguments for the write tasks \['rename_item'\]; "
            r"the dry run calls each write tool$",
            id="a-task-left-out",
        ),
        pytest.param(
            {"add_item": {"name": "Corn"}, "rename_item": [], "rename": {"item_id": 4}},
            r"^dry_run names no write task: \['rename'\]; a key is the task function's __name__$",
            id="a-key-of-no-task",
        ),
        pytest.param(
            {"add_item": {"name": "Corn"}, "rename_item": []},
            r"^example_rename_item: dry_run gives it no arguments$",
            id="an-empty-list",
        ),
        pytest.param(
            {"add_item": {"name": "Corn", "confirm": False}, "rename_item": {"item_id": 4}},
            r"^example_add_item: a dry run calls without confirm; drop it from dry_run$",
            id="confirm-given",
        ),
    ],
)
async def test_a_dry_run_wants_arguments_for_each_write_task_and_no_confirm(
    respx_mock: respx.MockRouter, dry_run: dict[str, Any], problem: str
) -> None:
    write = ToolSet("example", PREVIEWED, read_only=False)
    with pytest.raises(AssertionError, match=problem):
        await assert_write_tools(write, PREVIEWED, dry_run=dry_run, sent=respx_mock)
    assert not respx_mock.calls, "the arguments are checked before any tool is called"


@pytest.mark.anyio
async def test_the_dry_run_s_keywords_go_together() -> None:
    write = ToolSet("example", PREVIEWED, read_only=False)
    with pytest.raises(TypeError, match=r"^dry_run needs sent=, the respx router"):
        await assert_write_tools(write, PREVIEWED, dry_run={})
    with pytest.raises(TypeError, match=r"^sent= and is_read= serve the dry run; pass dry_run="):
        await assert_write_tools(write, PREVIEWED, sent=respx.MockRouter())
    with pytest.raises(TypeError, match=r"^sent= and is_read= serve the dry run; pass dry_run="):
        await assert_write_tools(write, PREVIEWED, is_read=bool)
