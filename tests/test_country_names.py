"""The name of each country code in an answer's meta (ADR-0056, sdk-core#316).

The row's proof first: an answer for the code ``CN`` of a list where it is Comoros carries
"Comoros" in ``meta``. Then each form a country argument takes in the six sources that take one:
a code alone, several in a list or in one text, an integer, a code left out and a default; the
answer of a task called through the MCP adapter, the HTTP router and a server bound to a tenant,
in either order of wrapping; and the edges: a code the list lacks, an answer that is no
``Result``, and a declaration the decorator refuses. The lists are this module's own.
"""

import inspect
import typing
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xippios.core import (
    Downloaded,
    InvalidRequestError,
    PackagedCodes,
    PackagedList,
    Result,
    ResultCap,
    ResultMeta,
    TenantLock,
    Tenants,
    UnknownCode,
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
"""Integer codes, which a task takes as a text of several separated by commas."""

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


@names_codes(reporter_code=REPORTERS, partner_code=PARTNERS, partner2_code=PARTNERS, separator=",")
def get_flows(
    reporter_code: str | None = None,
    partner_code: str | None = None,
    partner2_code: str | None = None,
) -> Result[int]:
    """Get the flows of reporters with partners, codes separated by commas."""
    return answer(reporter_code=reporter_code, partner_code=partner_code)


def test_several_codes_in_one_text_are_split_on_the_declared_separator() -> None:
    result = get_flows("757,842", partner_code="0")
    assert result.meta.names == {
        "reporter_code": {"757": "Switzerland", "842": "USA"},
        "partner_code": {"0": "World"},
    }
    assert get_flows("757").meta.names == {"reporter_code": {"757": "Switzerland"}}


@names_codes(country_code=PADDED)
def get_exports(country_code: int | None = None) -> Result[int]:
    """Get the exports to a country."""
    return answer(country_code=country_code)


def test_an_integer_code_stands_under_its_text_and_its_name_without_the_padding() -> None:
    assert get_exports(5700).meta.names == {"country_code": {"5700": "CHINA"}}
    assert get_exports(1220).model_dump(mode="json")["meta"]["names"] == {
        "country_code": {"1220": "CANADA"}
    }


@names_codes(area=AREAS, separator=",")
def get_area(area: str | int | Sequence[str | int]) -> Result[int]:
    """Get the data of areas, given as codes, integers or both."""
    return answer(area=area)


def test_an_integer_for_text_codes_is_read_as_its_text_and_digits_for_integers_as_theirs() -> None:
    assert get_area(4).meta.names == {"area": {"4": "Algeria"}}
    expected = {"area": {"4": "Algeria", "231": "United States of America"}}
    assert get_area([4, "231"]).meta.names == expected
    assert get_area("4,231").meta.names == expected
    assert get_area(["4,231"]).meta.names == expected, "a text in a list is split too"
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
    with pytest.raises(InvalidRequestError) as typed:
        get_unchecked(reporter_code="CHE")
    assert not isinstance(typed.value, UnknownCode)
    assert str(typed.value).startswith(
        "'CHE' is not an integer code: reporter_code takes the integer codes of the packaged "
        "reporters list (fetched 2026-10-23)"
    )
    # A value of the other type withholds the answer by the same reason (ADR-0056, decision 3).
    assert str(typed.value).endswith("so the answer is withheld.")


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
        names={"area": {"4": "Algeria"}, "reporters": {"XX": "stale"}},
    )
    return Result[int](data=0, meta=meta)


def test_names_the_task_set_are_kept_beside_the_decorators_own() -> None:
    result = sync(get_composed_async)(["US"], "4")
    assert result.meta.names == {"area": {"4": "Algeria"}, "reporters": {"US": "United States"}}


@names_codes(reporter_code=REPORTERS, separator=",")
@names_codes(country_code=COUNTRIES)
def get_both(reporter_code: str, country_code: str) -> Result[int]:
    """Get the data of reporters, separated by commas, for one country."""
    return answer(reporter_code=reporter_code, country_code=country_code)


def test_two_decorators_stack_one_per_separator() -> None:
    assert get_both("757,842", "CN").meta.names == {
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
            lambda: names_codes(country_code=COUNTRIES, separator=""),
            ValueError,
            "separator is a text of one character or more, or None",
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
)
LOCK = TenantLock(TENANTS, "demo", noun="organisation")


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
