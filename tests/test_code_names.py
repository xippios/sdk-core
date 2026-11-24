"""The name of each code in an answer's meta (ADR-0067, https://github.com/xippios/sdk-core/issues/478).

The row's proof first: an answer for the code ``CN`` of a list where it is Comoros carries
"Comoros" in ``meta``. Then each form a code argument takes: a code alone, several in a list, an
integer, a code left out and a default; the answer of a task called through the MCP adapter, the
HTTP router and a server bound to a tenant, in either order of wrapping; and the edges: a code the
list lacks, an answer that is no ``Result``, and a declaration the decorator refuses. Then the
codes of an answer's records, which their model names by ``NamedBy``: a list's names in
``meta.names``, a code the list lacks in ``meta.notes``, a label on the record itself, and the
marks that are refused. The lists are this module's own.
"""

import inspect
import typing
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from xippios.core import (
    Downloaded,
    InvalidRequestError,
    NamedBy,
    PackagedCodes,
    PackagedList,
    Result,
    ResultCap,
    ResultMeta,
    TenantLock,
    Tenants,
    UnknownCode,
    UpstreamModel,
    bind_tasks,
    names_codes,
    sync,
)
from xippios.core._loop import as_async, run
from xippios.core.http import router_from_tasks
from xippios.core.mcp import ToolSet, build_server
from xippios.core.testing import mcp_call

FETCHED = "2026-10-23T09:00:00Z"


def declared(
    param: str, code: str, name: str | None, records: list[dict[str, Any]], **options: Any
) -> PackagedCodes:
    """A packaged list of ``records``, declared by its code and name fields."""
    packaged = PackagedList.model_validate(
        {"param": param, "endpoint": "lists", "fetched": FETCHED, "records": records}
    )
    return packaged.codes(code, name, source="example", **options)


COUNTRIES = declared(
    "countries",
    "countryCode",
    "countryName",
    [
        {"countryCode": "CN", "countryName": "Comoros"},
        {"countryCode": "CH", "countryName": "China"},
        {"countryCode": "GB", "countryName": "Gabon"},
        {"countryCode": "US", "countryName": "United States"},
    ],
)
"""Text codes, where ``CN`` is Comoros and China is ``CH``."""

REPORTERS = declared(
    "reporters",
    "code",
    "desc",
    [{"code": 757, "desc": "Switzerland"}, {"code": 842, "desc": "USA"}],
)
"""Integer codes, which a task takes as integers or as their digits."""

PARTNERS = declared(
    "partners",
    "code",
    "desc",
    [
        {"code": 0, "desc": "World"},
        {"code": 757, "desc": "Switzerland"},
        {"code": 842, "desc": "USA"},
    ],
)

AREAS = declared(
    "area",
    "code",
    "label",
    [{"code": "4", "label": "Algeria"}, {"code": "231", "label": "United States of America"}],
)
"""Text codes, which a task takes as integers too."""

PADDED = declared(
    "countries",
    "countryCode",
    "countryDescription",
    [
        {"countryCode": 5700, "countryDescription": "CHINA     "},
        {"countryCode": 1220, "countryDescription": "CANADA  "},
    ],
)
"""Integer codes whose names upstream pads."""

STATES = declared(
    "state_alpha",
    "state_alpha",
    None,
    [{"state_alpha": "VA"}, {"state_alpha": "IA"}],
    fold_case=True,
)
"""A list of values that upstream compares without case."""


def answer(**request: Any) -> Result[int]:
    return Result[int](data=0, meta=ResultMeta(source="example", endpoint="data", request=request))


async def get_data_async(country_code: str | None = None, year: int = 2024) -> Result[list[int]]:
    """Get a year of a country's data.

    Args:
        country_code: The country, e.g. ``"US"``; omit it for every country.
        year: The year, e.g. ``2024``.
    """
    meta = ResultMeta(
        source="example", endpoint="data", request={"country_code": country_code, "year": year}
    )
    return Result[list[int]](data=[year], meta=meta)


get_data = sync(names_codes(country_code=COUNTRIES)(get_data_async))


def test_an_answer_for_cn_of_a_list_where_it_is_comoros_names_comoros() -> None:
    """The proof of https://github.com/xippios/sdk-core/issues/316."""
    result = get_data("CN")
    assert result.meta.names == {"country_code": {"CN": "Comoros"}}
    assert result.model_dump(mode="json")["meta"]["names"] == {"country_code": {"CN": "Comoros"}}
    assert result.meta.request == {"country_code": "CN", "year": 2024}, "the code as sent"


def test_a_task_asked_for_every_country_names_nothing_and_dumps_as_before() -> None:
    result = get_data(year=2023)
    assert result.meta.names == {}
    assert "names" not in result.model_dump(mode="json")["meta"]
    undecorated = sync(get_data_async)(year=2023)
    assert result.model_dump(exclude={"meta": {"retrieved_at"}}) == undecorated.model_dump(
        exclude={"meta": {"retrieved_at"}}
    )


@names_codes(reporters=COUNTRIES, partners=COUNTRIES)
def get_trade(
    reporters: Sequence[str] | None = None, partners: Sequence[str] | set[str] | None = None
) -> Result[int]:
    """Get the trade between reporters and partners."""
    return answer(reporters=reporters, partners=partners)


def test_several_codes_in_a_list_a_tuple_or_a_set_are_each_named_once_in_order() -> None:
    result = get_trade(["CN", "CH", "CN"], ("US",))
    assert result.meta.names == {
        "reporters": {"CN": "Comoros", "CH": "China"},
        "partners": {"US": "United States"},
    }
    assert list(result.meta.names["reporters"]) == ["CN", "CH"], "in the order given"
    assert get_trade(partners={"GB"}).meta.names == {"partners": {"GB": "Gabon"}}
    assert get_trade([]).meta.names == {}, "no code, no entry"


@names_codes(reporter_code=REPORTERS, partner_code=PARTNERS, partner2_code=PARTNERS)
def get_flows(
    reporter_code: str | list[str] | None = None,
    partner_code: str | None = None,
    partner2_code: str | None = None,
) -> Result[int]:
    """Get the flows of reporters with partners."""
    return answer(reporter_code=reporter_code, partner_code=partner_code)


def test_a_text_is_one_code_and_several_codes_are_a_list() -> None:
    # Several values of one filter are a list (ADR-0061, decision 1), so the decorator splits
    # no text (ADR-0067, decision 3; https://github.com/xippios/sdk-core/issues/478).
    result = get_flows(["757", "842"], partner_code="0")
    assert result.meta.names == {
        "reporter_code": {"757": "Switzerland", "842": "USA"},
        "partner_code": {"0": "World"},
    }
    assert get_flows("757").meta.names == {"reporter_code": {"757": "Switzerland"}}
    with pytest.raises(InvalidRequestError, match=r"^'757,842' is not an integer code"):
        get_flows("757,842")


@names_codes(country_code=PADDED)
def get_exports(country_code: int | None = None) -> Result[int]:
    """Get the exports to a country."""
    return answer(country_code=country_code)


def test_an_integer_code_stands_under_its_text_and_its_name_without_the_padding() -> None:
    assert get_exports(5700).meta.names == {"country_code": {"5700": "CHINA"}}
    assert get_exports(1220).model_dump(mode="json")["meta"]["names"] == {
        "country_code": {"1220": "CANADA"}
    }


@names_codes(area=AREAS)
def get_area(area: str | int | Sequence[str | int]) -> Result[int]:
    """Get the data of areas, given as codes, integers or both."""
    return answer(area=area)


def test_an_integer_for_text_codes_is_read_as_its_text_and_digits_for_integers_as_theirs() -> None:
    assert get_area(4).meta.names == {"area": {"4": "Algeria"}}
    expected = {"area": {"4": "Algeria", "231": "United States of America"}}
    assert get_area([4, "231"]).meta.names == expected
    assert get_flows("842").meta.names["reporter_code"] == {"842": "USA"}, "digits for integers"


class Country(StrEnum):
    CN = "CN"
    US = "US"


@names_codes(country_code=COUNTRIES)
def get_default(country_code: str = "US", year: int = 2024) -> Result[int]:
    """Get the data of a country, the United States unless told otherwise."""
    return answer(country_code=country_code)


@names_codes(state=STATES)
def get_state(state: str) -> Result[int]:
    """Get the data of a state."""
    return answer(state=state)


def test_a_default_a_positional_an_enum_and_a_folded_code_are_named_as_given() -> None:
    assert get_default().meta.names == {"country_code": {"US": "United States"}}, "the default"
    assert get_default("GB", 2020).meta.names == {"country_code": {"GB": "Gabon"}}
    assert get_default(Country.CN).meta.names == {"country_code": {"CN": "Comoros"}}
    # A list of values names each code by itself, as upstream spells it.
    assert get_state("va").meta.names == {"state": {"va": "VA"}}


SENT: list[object] = []


@names_codes(country_code=COUNTRIES, reporter_code=REPORTERS)
def get_unchecked(country_code: str | None = None, reporter_code: str | None = None) -> Result[int]:
    """Get the data of a country, its code sent unchecked."""
    SENT.append(country_code or reporter_code)
    return answer(country_code=country_code, reporter_code=reporter_code)


def test_a_code_the_list_lacks_withholds_the_answer_with_the_lists_refusal() -> None:
    SENT.clear()
    with pytest.raises(UnknownCode) as refused:
        get_unchecked("CHN")
    assert SENT == ["CHN"], "the task ran: the refusal comes after the call"
    assert (refused.value.param, refused.value.value) == ("country_code", "CHN")
    assert str(refused.value).startswith(
        "'CHN' is not a country_code in the packaged countries list (fetched 2026-10-23)."
    )
    assert "names the country of each code it is for" in str(refused.value)
    assert "the answer is withheld" in str(refused.value)
    # Checked after the call: upstream was asked, so the check's switch leaves out that nothing
    # was sent (https://github.com/xippios/sdk-core/issues/481, part 1).
    assert "(fetched 2026-10-23). Did you mean " in str(refused.value)
    assert "Upstream was asked" in str(refused.value)
    assert "Nothing was sent" not in str(refused.value)
    with pytest.raises(InvalidRequestError) as typed:
        get_unchecked(reporter_code="CHE")
    assert not isinstance(typed.value, UnknownCode)
    assert str(typed.value).startswith(
        "'CHE' is not an integer code: reporter_code takes the integer codes of the packaged "
        "reporters list (fetched 2026-10-23)"
    )
    # A value of the other type withholds the answer by the same reason (ADR-0067, decision 4).
    assert str(typed.value).endswith("so the answer is withheld.")
    assert "Nothing was sent" not in str(typed.value)


@names_codes(country_code=COUNTRIES)
def get_checked(country_code: str) -> Result[int]:
    """Get the data of a country, its code checked first."""
    COUNTRIES.check(
        "country_code", country_code, hints={"all": "Omit country_code for every country."}
    )
    return answer(country_code=country_code)


def test_the_tasks_own_refusal_passes_as_it_raised_it() -> None:
    with pytest.raises(UnknownCode, match="Omit country_code for every country") as refused:
        get_checked("all")
    assert "withheld" not in str(refused.value)


@names_codes(country_code=COUNTRIES)
def get_bare(country_code: str | None = None) -> Any:
    """Return a bare list, against the family's rule."""
    return [1]


def test_an_answer_that_is_no_result_raises_type_error_naming_the_task() -> None:
    with pytest.raises(TypeError, match=r"^get_bare returned a list, not a Result: names_codes"):
        get_bare("CN")
    with pytest.raises(TypeError, match=r"^get_bare returned a list"):
        get_bare()  # asked for every country: still no Result


@names_codes(country_code=COUNTRIES)
def download_data(country_code: str, dest: Path) -> Result[Downloaded]:
    """Download the data of a country into a file."""
    got = Downloaded(
        path=dest,
        bytes=3,
        content_type="text/csv",
        filename=None,
        etag=None,
        last_modified=None,
        retrieved_at=datetime(2026, 10, 23, tzinfo=UTC),
    )
    return Result[Downloaded](
        data=got, meta=ResultMeta(source="example", endpoint="data.csv", request={"url": "u"})
    )


def test_a_downloads_answer_is_a_result_and_is_named() -> None:
    result = download_data("GB", Path("data.csv"))
    assert result.meta.names == {"country_code": {"GB": "Gabon"}}
    assert result.data.path == Path("data.csv")


SHARED = Result[int](
    data=1,
    meta=ResultMeta(
        source="example",
        endpoint="data",
        published_at=datetime(2026, 10, 6, 8),
        published_at_naive=True,
        vintage="2026-10",
        request={"country_code": "CN", "sig": "kept out"},  # a signed link's signature
        total=3,
        tenant="demo",
    ),
)


@names_codes(country_code=COUNTRIES)
def get_shared(country_code: str) -> Result[int]:
    """Return one answer for every call."""
    return SHARED


def test_the_answer_keeps_its_data_and_meta_and_the_tasks_own_object_is_not_changed() -> None:
    first, second = get_shared("CN"), get_shared("CH")
    assert first.meta.names == {"country_code": {"CN": "Comoros"}}
    assert second.meta.names == {"country_code": {"CH": "China"}}
    assert SHARED.meta.names == {}, "the task's object stays as it built it"
    assert first.meta.model_dump() == {**SHARED.meta.model_dump(), "names": first.meta.names}
    assert first.meta.request == {"country_code": "CN", "sig": "REDACTED"}
    assert type(first) is type(SHARED)
    assert first.data == 1


@names_codes(reporters=COUNTRIES)
async def get_composed_async(reporters: Sequence[str], area: str) -> Result[int]:
    """Compose an answer that names its area."""
    meta = ResultMeta(
        source="example",
        endpoint="data",
        names={"area": {"4": "Algeria"}, "reporters": {"CH": "China", "US": "stale"}},
    )
    return Result[int](data=0, meta=meta)


def test_names_the_task_set_are_kept_beside_the_decorators_own() -> None:
    # Those of a record under the parameter's name among them (ADR-0067, decision 2): the
    # decorator's name takes a code's place where both name it.
    result = sync(get_composed_async)(["US"], "4")
    assert result.meta.names == {
        "area": {"4": "Algeria"},
        "reporters": {"CH": "China", "US": "United States"},
    }


@names_codes(reporter_code=REPORTERS)
@names_codes(country_code=COUNTRIES)
def get_both(reporter_code: list[str], country_code: str) -> Result[int]:
    """Get the data of reporters for one country."""
    return answer(reporter_code=reporter_code, country_code=country_code)


def test_two_decorators_stack() -> None:
    assert get_both(["757", "842"], "CN").meta.names == {
        "country_code": {"CN": "Comoros"},
        "reporter_code": {"757": "Switzerland", "842": "USA"},
    }


def get_declared(country_code: str, year: int, *codes: str, **rest: str) -> Result[int]:
    """A task to declare."""
    return answer(country_code=country_code)


@pytest.mark.parametrize(
    ("declare", "error", "message"),
    [
        (lambda: names_codes(), TypeError, "names_codes names no parameter"),
        (
            lambda: names_codes(country_code="countries"),  # type: ignore[arg-type]
            TypeError,
            "names_codes takes a PackagedCodes per parameter, PackagedList.codes(...), and "
            "country_code is a str",
        ),
        (
            lambda: names_codes(country_code=COUNTRIES, separator=","),  # type: ignore[arg-type]
            TypeError,
            "names_codes takes a PackagedCodes per parameter, PackagedList.codes(...), and "
            "separator is a str",
        ),
        (
            lambda: names_codes(country_cod=COUNTRIES)(get_declared),
            TypeError,
            "names_codes names country_cod, which get_declared does not take: it takes "
            "country_code, year, codes and rest",
        ),
        (
            lambda: names_codes(rest=COUNTRIES)(get_declared),
            TypeError,
            "names_codes names rest, the **rest of get_declared, which holds no code by its name",
        ),
        (
            lambda: names_codes(country_code=COUNTRIES)(
                names_codes(country_code=AREAS)(get_declared)
            ),
            TypeError,
            "names_codes names country_code of get_declared twice",
        ),
    ],
)
def test_a_declaration_that_cannot_name_is_refused_when_the_module_is_imported(
    declare: Callable[[], object], error: type[Exception], message: str
) -> None:
    with pytest.raises(error) as refused:
        declare()
    assert str(refused.value) == message


def test_a_var_positional_parameter_names_each_code_it_holds() -> None:
    declared_codes = names_codes(codes=COUNTRIES)(get_declared)
    assert declared_codes("US", 2024, "CN", "GB").meta.names == {
        "codes": {"CN": "Comoros", "GB": "Gabon"}
    }


def test_the_decorated_task_keeps_its_name_module_docstring_signature_and_hints() -> None:
    decorated = names_codes(country_code=COUNTRIES)(get_data_async)
    assert inspect.iscoroutinefunction(decorated)
    for attribute in ("__name__", "__qualname__", "__module__", "__doc__"):
        assert getattr(decorated, attribute) == getattr(get_data_async, attribute)
    assert decorated.__wrapped__ is get_data_async  # type: ignore[attr-defined]
    assert inspect.signature(decorated) == inspect.signature(get_data_async)
    assert typing.get_type_hints(decorated) == typing.get_type_hints(get_data_async)
    assert sync(decorated).__name__ == "get_data", "sync drops the suffix as before"
    facade = names_codes(country_code=COUNTRIES)(sync(get_data_async))
    assert not inspect.iscoroutinefunction(facade)
    assert inspect.signature(facade) == inspect.signature(get_data_async)
    assert (facade.__name__, facade.__doc__) == ("get_data", get_data_async.__doc__)


ORDERS = {
    "the async function, then sync": lambda: sync(
        names_codes(country_code=COUNTRIES)(get_data_async)
    ),
    "sync, then the facade": lambda: names_codes(country_code=COUNTRIES)(sync(get_data_async)),
}


@pytest.fixture(params=sorted(ORDERS))
def task(request: pytest.FixtureRequest) -> Callable[..., Any]:
    """The task decorated in one order of wrapping or the other."""
    return ORDERS[request.param]()


@pytest.mark.anyio
async def test_the_adapters_await_a_twin_that_names_in_either_order(
    task: Callable[..., Any],
) -> None:
    assert task("CN").meta.names == {"country_code": {"CN": "Comoros"}}, "the direct call"
    twin = as_async(task)
    assert (await twin("CH")).meta.names == {"country_code": {"CH": "China"}}, "the adapters'"


@pytest.mark.anyio
async def test_an_mcp_tool_answers_with_the_names_and_keeps_its_schema(
    task: Callable[..., Any],
) -> None:
    server = build_server(ToolSet("example", [task]))
    named = await mcp_call(server, "example_get_data", {"country_code": "CN"})
    assert named["meta"]["names"] == {"country_code": {"CN": "Comoros"}}
    every = await mcp_call(server, "example_get_data", {"year": 2023})
    assert "names" not in every["meta"]
    (tool,) = await server.list_tools()
    (plain,) = await build_server(ToolSet("example", [sync(get_data_async)])).list_tools()
    assert (tool.name, tool.description, tool.input_schema) == (
        plain.name,
        plain.description,
        plain.input_schema,
    )


@pytest.mark.anyio
async def test_a_paged_tool_keeps_its_schema_and_its_offset_and_names_each_page(
    task: Callable[..., Any],
) -> None:
    # ADR-0047: the adapter adds offset to a paged tool and runs the task again for a page.
    caps = {"get_data": ResultCap(paged=True)}
    server = build_server(ToolSet("example", [task], caps=caps))
    (tool,) = await server.list_tools()
    (plain,) = await build_server(
        ToolSet("example", [sync(get_data_async)], caps=caps)
    ).list_tools()
    assert tool.input_schema == plain.input_schema
    assert "offset" in tool.input_schema["properties"]
    first = await mcp_call(server, "example_get_data", {"country_code": "CN"})
    again = await mcp_call(server, "example_get_data", {"country_code": "CN", "offset": 0})
    for page in (first, again):
        assert page["meta"]["names"] == {"country_code": {"CN": "Comoros"}}


def test_an_http_route_answers_with_the_names_and_keeps_its_method(
    task: Callable[..., Any],
) -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [task]))
    with TestClient(app) as http:
        named = http.get("/example/get_data", params={"country_code": "GB"})
        every = http.get("/example/get_data")
    assert named.status_code == 200
    assert named.json()["meta"]["names"] == {"country_code": {"GB": "Gabon"}}
    assert "names" not in every.json()["meta"]


TENANTS = Tenants(
    "example",
    list_var="EXAMPLE_NAMES_TENANTS",
    param="org",
    fields=("API_KEY",),
    reserved=("demo",),
    noun="organisation",
)
LOCK = TenantLock(TENANTS, "demo")


async def get_org_data_async(org: str, country_code: str) -> Result[int]:
    """Get the data of a country for an organisation.

    Args:
        org: The organisation, e.g. ``"demo"``.
        country_code: The country, e.g. ``"US"``.
    """
    meta = ResultMeta(
        source="example", endpoint="data", request={"country_code": country_code}, tenant=org
    )
    return Result[int](data=0, meta=meta)


BOUND = {
    "decorated, then bound": lambda: bind_tasks(
        [names_codes(country_code=COUNTRIES)(sync(get_org_data_async))], LOCK
    )[0],
    "bound, then decorated": lambda: names_codes(country_code=COUNTRIES)(
        bind_tasks([sync(get_org_data_async)], LOCK)[0]
    ),
}


@pytest.mark.parametrize("order", sorted(BOUND))
def test_a_tool_bound_to_a_tenant_names_in_either_order(order: str) -> None:
    bound = BOUND[order]()
    assert "org" not in inspect.signature(bound).parameters
    result = run(bound(country_code="CN"))
    assert result.meta.names == {"country_code": {"CN": "Comoros"}}
    assert result.meta.tenant == "demo"


# The codes of an answer's records: their model names them (ADR-0067, decisions 6 and 7;
# https://github.com/xippios/sdk-core/issues/478, parts 2 and 4). The invented source's record
# carries a region's code, which its packaged list names, and an item's code beside its label.

REGIONS = declared(
    "regions",
    "regionCode",
    "regionName",
    [
        {"regionCode": "R1", "regionName": "North"},
        {"regionCode": "R2", "regionName": "South  "},
        {"regionCode": "R3", "regionName": "East"},
    ],
)
UNITS = declared("units", "unitId", "unitName", [{"unitId": 8, "unitName": "(1000 MT)"}])


class Row(UpstreamModel):
    region_code: Annotated[str | None, NamedBy(REGIONS)] = Field(validation_alias="regionCode")
    unit_id: Annotated[int, NamedBy(UNITS)] = Field(validation_alias="unitId")
    item_code: Annotated[int, NamedBy("item")] = Field(validation_alias="itemCode")
    item: str


def row(region: str | None = "R1", unit: int = 8, item: int = 15) -> Row:
    return Row.model_validate(
        {"regionCode": region, "unitId": unit, "itemCode": item, "item": "Wheat"}
    )


def rows_answer(*records: Row, meta: ResultMeta | None = None) -> Result[list[Row]]:
    return Result[list[Row]](
        data=list(records), meta=meta or ResultMeta(source="example", endpoint="rows")
    )


def test_every_answer_that_holds_the_record_names_each_code_its_list_names() -> None:
    result = rows_answer(row("R1"), row("R2"), row("R1"), row(None))
    assert result.meta.names == {
        "region_code": {"R1": "North", "R2": "South"},
        "unit_id": {"8": "(1000 MT)"},
    }
    assert list(result.meta.names["region_code"]) == ["R1", "R2"], "each once, in order"
    assert result.meta.notes == []
    dumped = result.model_dump(mode="json")["meta"]
    assert dumped["names"] == result.meta.names
    assert "notes" not in dumped, "no note, no key"


def test_a_label_on_the_record_names_its_code_where_it_stands() -> None:
    # A value that upstream's record states stays on the record (ADR-0060, decision 8), so the
    # item's name is no entry of meta.names.
    result = rows_answer(row())
    assert "item_code" not in result.meta.names
    assert result.model_dump(mode="json")["data"][0]["item"] == "Wheat"


class Report(BaseModel):
    title: str
    rows: list[Row]
    by_region: dict[str, Row]
    first: Row | None = None


def test_a_record_is_named_in_a_model_a_mapping_and_a_tuple_at_any_depth() -> None:
    report = Report(title="t", rows=[row("R1")], by_region={"south": row("R2")}, first=row("R3"))
    assert Result[Report](data=report, meta=ResultMeta(source="example", endpoint="r")).meta.names[
        "region_code"
    ] == {"R1": "North", "R2": "South", "R3": "East"}
    pair = Result[tuple[Row, ...]](
        data=(row("R2"),), meta=ResultMeta(source="example", endpoint="r")
    )
    assert pair.meta.names["region_code"] == {"R2": "South"}
    plain = Result[dict[str, Any]](
        data={"region_code": "R1"}, meta=ResultMeta(source="example", endpoint="r")
    )
    assert plain.meta.names == {}, "a mapping of no record names nothing"


def test_a_code_the_list_lacks_is_left_out_and_said_in_one_note_per_field() -> None:
    # The answer is not withheld, since upstream returned the code (ADR-0067, decision 7).
    result = rows_answer(row("R1"), row("R9"), row("R8"), row("R9"), row("R1", unit=4))
    assert result.meta.names == {"region_code": {"R1": "North"}, "unit_id": {"8": "(1000 MT)"}}
    assert result.meta.notes == [
        "The packaged regions list (fetched 2026-10-23) holds no name for region_code R9 or R8 "
        "of this answer, so meta.names leaves them out.",
        "The packaged units list (fetched 2026-10-23) holds no name for unit_id 4 of this "
        "answer, so meta.names leaves it out.",
    ]
    assert len(result.data) == 5


def test_the_names_and_notes_of_the_task_s_meta_stay_and_its_object_is_not_changed() -> None:
    meta = ResultMeta(
        source="example",
        endpoint="rows",
        request={"region_code": "R2"},
        names={"region_code": {"R2": "South"}, "area": {"4": "Algeria"}},
        notes=["Two market years held no data."],
    )
    result = rows_answer(row("R1"), row("R9"), meta=meta)
    assert result.meta.names == {
        "region_code": {"R1": "North", "R2": "South"},
        "area": {"4": "Algeria"},
        "unit_id": {"8": "(1000 MT)"},
    }
    assert result.meta.notes[0] == "Two market years held no data."
    assert len(result.meta.notes) == 2
    assert meta.names == {"region_code": {"R2": "South"}, "area": {"4": "Algeria"}}
    assert len(meta.notes) == 1
    again = rows_answer(*result.data, meta=result.meta)
    assert again.meta == result.meta, "a composed answer says its note once"
    assert Result[list[Row]].model_validate(result.model_dump(mode="json")) == result


@names_codes(region_code=REGIONS)
def get_rows(region_code: list[str]) -> Result[list[Row]]:
    """Get the rows of regions."""
    return rows_answer(*(row(code) for code in region_code), row("R3"))


def test_a_request_and_its_records_name_their_codes_under_one_entry() -> None:
    result = get_rows(["R1", "R2"])
    assert result.meta.names["region_code"] == {"R1": "North", "R2": "South", "R3": "East"}


@pytest.mark.anyio
async def test_a_record_s_codes_are_named_over_mcp_and_http() -> None:
    server = build_server(ToolSet("example", [get_rows]))
    called = await mcp_call(server, "example_get_rows", {"region_code": ["R2"]})
    assert called["meta"]["names"]["region_code"] == {"R2": "South", "R3": "East"}
    app = FastAPI()
    app.include_router(router_from_tasks("example", [get_rows]))
    with TestClient(app) as http:
        answered = http.post("/example/get_rows", json={"region_code": ["R1"]})
    assert answered.json()["meta"]["names"]["region_code"] == {"R1": "North", "R3": "East"}


class Integer(UpstreamModel):
    code: Annotated[str, NamedBy(UNITS)]
    codes: Annotated[list[int] | None, NamedBy(UNITS)] = None


def test_digits_for_integer_codes_and_a_list_of_codes_are_named() -> None:
    result = Result[Integer](
        data=Integer(code="8", codes=[8, 8]), meta=ResultMeta(source="example", endpoint="i")
    )
    assert result.meta.names == {"code": {"8": "(1000 MT)"}, "codes": {"8": "(1000 MT)"}}


@pytest.mark.parametrize(
    ("by", "shown"),
    [("2nd", "'2nd'"), ("", "''"), (REGIONS.packaged, "a PackagedList"), (8, "an int")],
)
def test_named_by_takes_a_list_s_codes_or_a_field_s_name(by: Any, shown: str) -> None:
    with pytest.raises(TypeError) as refused:
        NamedBy(by)
    assert str(refused.value) == (
        "NamedBy takes the list that names the codes, PackagedList.codes(...), or the name of "
        f"the field beside the code that holds its name, and got {shown}"
    )


class Unnamed(UpstreamModel):
    item_code: Annotated[int, NamedBy("label")]
    twice: Annotated[str, NamedBy(REGIONS), NamedBy("item")]
    unit_code: Annotated[int, NamedBy("unit")]
    region: Annotated[Row, NamedBy(REGIONS)]
    self_code: Annotated[str, NamedBy("self_code")]
    item: str
    unit: int
    items: list[Annotated[str, NamedBy(REGIONS)]]
    either: Annotated[str, NamedBy(REGIONS)] | Annotated[int, NamedBy(UNITS)]
    again: Annotated[Annotated[str, NamedBy(REGIONS)] | None, NamedBy(REGIONS)]


def test_a_mark_that_cannot_name_is_refused_when_an_answer_holds_its_record() -> None:
    # A mark on a list's items or in a union of codes is no mark of the field: a Result would
    # read nothing of it, so it is refused (https://github.com/xippios/sdk-core/pull/537,
    # finding 1).
    record = Unnamed.model_construct(
        item_code=1,
        twice="R1",
        unit_code=2,
        region=row(),
        self_code="x",
        item="i",
        unit=3,
        items=["R1"],
        either="R1",
        again="R1",
    )
    with pytest.raises(TypeError) as refused:
        Result[Unnamed](data=record, meta=ResultMeta(source="example", endpoint="u"))
    assert str(refused.value) == (
        "Unnamed.item_code is named by label, which is no other field of the model; "
        "Unnamed.twice is marked by NamedBy twice; keep one; "
        "Unnamed.unit_code is named by unit, which holds int, not text; "
        "Unnamed.region holds Row, no code: NamedBy marks a field of text or integer codes, one "
        "or a list of them; "
        "Unnamed.self_code is named by self_code, which is no other field of the model; "
        "Unnamed.items carries NamedBy inside its type, where no answer reads it: mark the "
        "field, Annotated[str | None, NamedBy(...)] or Annotated[str, NamedBy(...)] | None; "
        "Unnamed.either carries NamedBy inside its type, where no answer reads it: mark the "
        "field, Annotated[str | None, NamedBy(...)] or Annotated[str, NamedBy(...)] | None; "
        "Unnamed.again is marked by NamedBy twice; keep one "
        "(conventions §4, ADR-0067, decision 6)"
    )


class Optionally(UpstreamModel):
    inner: Annotated[str | None, NamedBy(REGIONS)] = None
    outer: Annotated[str, NamedBy(REGIONS)] | None = None
    typed: Optional[Annotated[str, NamedBy(REGIONS)]] = None  # noqa: UP045
    item_code: Annotated[int, NamedBy("item")] | None = None
    item: str | None = None


def test_an_optional_code_reads_its_mark_inside_or_outside_none() -> None:
    # The plain spelling of an optional code is Annotated[...] | None (finding 1 of
    # https://github.com/xippios/sdk-core/pull/537): the mark reads in all three forms.
    record = Optionally(inner="R1", outer="R2", typed="R3", item_code=4, item="Wheat")
    result = Result[Optionally](data=record, meta=ResultMeta(source="example", endpoint="o"))
    assert result.meta.names == {
        "inner": {"R1": "North"},
        "outer": {"R2": "South"},
        "typed": {"R3": "East"},
    }
    empty = Result[Optionally](data=Optionally(), meta=ResultMeta(source="example", endpoint="o"))
    assert empty.meta.names == {}


OTHERS = declared(
    "others",
    "otherCode",
    "otherName",
    [{"otherCode": "O1", "otherName": "Other one"}, {"otherCode": "R2", "otherName": "Other two"}],
)


class First(UpstreamModel):
    code: Annotated[str, NamedBy(REGIONS)]


class Second(UpstreamModel):
    code: Annotated[str, NamedBy(OTHERS)]


class Both(BaseModel):
    first: list[First]
    second: list[Second]


def test_two_lists_of_one_field_name_note_each_its_own_gaps_and_no_code_named() -> None:
    # Two models of one answer mark a field of one name with two lists (finding 2 of
    # https://github.com/xippios/sdk-core/pull/537): a code that one list names is no gap, and
    # each list's gaps are noted under its own name.
    both = Both(
        first=[First(code="R1"), First(code="R9")],
        second=[Second(code="O1"), Second(code="R1"), Second(code="R9"), Second(code="R8")],
    )
    result = Result[Both](data=both, meta=ResultMeta(source="example", endpoint="b"))
    assert result.meta.names == {"code": {"R1": "North", "O1": "Other one"}}
    assert result.meta.notes == [
        "The packaged regions list (fetched 2026-10-23) holds no name for code R9 of this "
        "answer, so meta.names leaves it out.",
        "The packaged others list (fetched 2026-10-23) holds no name for code R9 or R8 of this "
        "answer, so meta.names leaves them out.",
    ]
