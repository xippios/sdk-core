import functools
import sys
import types
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import AfterValidator, Field

from xippios.core import sync
from xippios.core.errors import InvalidRequestError, NotFoundError, RateLimitError
from xippios.core.http import is_scalar, router_from_tasks
from xippios.core.http.problems import PROBLEM_MEDIA_TYPE
from xippios.core.models import Result, ResultMeta, UpstreamModel


class Series(UpstreamModel):
    id: str
    value: float


async def get_series_async(series_id: str, year: int = 2024) -> Result[list[Series]]:
    """Fetch one series.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
        year: Marketing year.
    """
    if series_id == "missing":
        raise NotFoundError(f"no series {series_id}", source="example")
    if series_id == "slow":
        raise RateLimitError("slow down", retry_after=5)
    rows = [Series(id=series_id, value=float(year))]
    return Result[list[Series]](
        data=rows, meta=ResultMeta(source="example", endpoint="series", request={"year": year})
    )


get_series = sync(get_series_async)


def list_things() -> list[str]:
    """List the things."""
    return ["a", "b"]


async def download_series_async(series_id: str) -> Result[list[Series]]:
    """Download every year of one series."""
    raise NotImplementedError


download_series_async.__module__ = "example_bulk_tasks"
download_series = sync(download_series_async)


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [get_series, list_things]))
    return TestClient(app)


def test_routes_return_the_envelope() -> None:
    client = make_client()
    response = client.get("/example/get_series", params={"series_id": "CORN", "year": 2010})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == [{"id": "CORN", "value": 2010.0}]
    assert payload["meta"]["source"] == "example"
    assert payload["meta"]["request"] == {"year": 2010}
    assert payload["meta"]["retrieved_at"].endswith("Z")
    assert payload["meta"]["total"] is None


def test_a_task_in_bulk_tasks_gets_no_route(monkeypatch: pytest.MonkeyPatch) -> None:
    # ADR-0019, decision 4: the rendered http.py passes every name of tasks.__all__.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)
    router = router_from_tasks("example", [get_series, download_series])
    assert [route.path for route in router.routes] == ["/example/get_series"]  # type: ignore[attr-defined]


def test_a_bulk_task_behind_a_wrapper_of_another_module_gets_no_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # https://github.com/xippios/sdk-core/issues/155: __wrapped__ leads to the bulk task.
    tasks = types.ModuleType("example_bulk_tasks")
    tasks.BULK_TASKS = frozenset({"download_series"})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, tasks.__name__, tasks)

    @functools.wraps(download_series)
    def bound(*args: Any, **kwargs: Any) -> Any:
        return download_series(*args, **kwargs)

    bound.__module__ = "example_lock"
    router = router_from_tasks("example", [get_series, bound])
    assert [route.path for route in router.routes] == ["/example/get_series"]  # type: ignore[attr-defined]


def test_defaults_and_plain_functions() -> None:
    client = make_client()
    assert (
        client.get("/example/get_series", params={"series_id": "X"}).json()["data"][0]["value"]
        == 2024.0
    )
    assert client.get("/example/list_things").json() == ["a", "b"]


def refusal(detail: str) -> dict[str, Any]:
    """The problem details of an argument a route refuses before the task runs."""
    return {
        "type": "urn:xippios:error:InvalidRequestError",
        "title": "InvalidRequestError",
        "status": 422,
        "detail": detail,
        "source": "example",
    }


def test_missing_required_parameter_is_422() -> None:
    response = make_client().get("/example/get_series")
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json() == refusal("series_id: Field required")


def get_level(level: "Level", year: int = 2024) -> dict[str, Any]:
    """Get one level of a year.

    Args:
        level: Which level, e.g. ``"STATE"``.
        year: Marketing year, e.g. ``2024``.
    """
    return {"level": level.value, "year": year}


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({"level": "STAET"}, "level: Input should be 'STATE' or 'COUNTY'"),
        ({"level": "STATE", "year": "soon"},
         "year: Input should be a valid integer, unable to parse string as an integer"),
        ({"level": "STAET", "year": "soon"},
         "level: Input should be 'STATE' or 'COUNTY' (the first of 2 errors)"),
    ],
)  # fmt: skip
def test_an_argument_a_typed_parameter_refuses_is_answered_as_problem_details(
    params: dict[str, str], detail: str
) -> None:
    # https://github.com/xippios/sdk-core/issues/66: FastAPI's own 422 echoed the input.
    app = FastAPI()
    app.include_router(router_from_tasks("example", [get_level]))
    response = TestClient(app).get("/example/get_level", params=params)
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json() == refusal(detail)
    assert not {"STAET", "soon", "pydantic"} & set(response.text.replace('"', " ").split())
    assert "input" not in response.json()


@pytest.mark.parametrize(
    ("request_kwargs", "detail"),
    [
        ({"json": {}}, "filters: Field required"),
        ({"json": {"filters": {}, "limit": "many"}},
         "limit: Input should be a valid integer, unable to parse string as an integer"),
        ({"json": {"filters": {"year": [2012]}}},
         "filters.year.str: Input should be a valid string (the first of 2 errors)"),
        ({"json": ["filters"]},
         "body: Input should be a valid dictionary or object to extract fields from"),
        ({}, "body: Field required"),
        ({"content": b'{"filters": ', "headers": {"content-type": "application/json"}},
         "body: JSON decode error"),
    ],
)  # fmt: skip
def test_a_body_the_route_refuses_is_answered_as_problem_details(
    request_kwargs: dict[str, Any], detail: str
) -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [count]))
    response = TestClient(app).post("/example/count", **request_kwargs)
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json() == refusal(detail)
    assert not {"many", "2012", "[2012]"} & set(response.text.replace('"', " ").split())


def test_errors_are_problem_details() -> None:
    client = make_client()
    response = client.get("/example/get_series", params={"series_id": "missing"})
    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json() == {
        "type": "urn:xippios:error:NotFoundError",
        "title": "NotFoundError",
        "status": 404,
        "detail": "no series missing",
        "source": "example",
    }
    limited = client.get("/example/get_series", params={"series_id": "slow"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "5"


def test_openapi_metadata() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [get_series]))
    spec = app.openapi()
    operation = spec["paths"]["/example/get_series"]["get"]
    assert operation["tags"] == ["example"]
    assert operation["summary"] == "Fetch one series."
    assert "series_id: Upstream identifier" in operation["description"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert params["series_id"]["required"] is True
    assert params["series_id"]["in"] == "query"
    assert params["year"]["required"] is False
    assert operation["operationId"].startswith("example_get_series")


def test_custom_prefix_and_tags() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [list_things], prefix="/v1/ex", tags=["t"]))
    client = TestClient(app)
    assert client.get("/v1/ex/list_things").status_code == 200
    assert app.openapi()["paths"]["/v1/ex/list_things"]["get"]["tags"] == ["t"]


class Level(StrEnum):
    STATE = "STATE"
    COUNTY = "COUNTY"


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (str, True), (int, True), (float, True), (bool, True), (Decimal, True), (date, True),
        (Level, True), (int | None, True), (str | int, True), (Literal["a", "b"], True),
        (Annotated[str, "meta"], True), (Any, True),
        (Mapping[str, str | int], False), (dict[str, str], False), (list[str], False),
        (list[str] | None, False), (Series, False),
    ],
)  # fmt: skip
def test_is_scalar(annotation: object, expected: bool) -> None:
    assert is_scalar(annotation) is expected


async def count_async(filters: Mapping[str, str | int], limit: int = 10) -> Result[int]:
    """Count records matching filters.

    Args:
        filters: Column filters, e.g. ``{"commodity_desc": "CORN"}``.
        limit: Cap on the count.
    """
    if "bad" in filters:
        raise InvalidRequestError("unknown column 'bad'", source="example")
    return Result(
        data=min(len(filters), limit),
        meta=ResultMeta(source="example", endpoint="count", request=dict(filters)),
    )


count = sync(count_async)


def test_non_scalar_parameters_make_a_post_route_with_a_keyed_body() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [count, get_series]))
    client = TestClient(app)
    response = client.post(
        "/example/count", json={"filters": {"commodity_desc": "CORN", "year": 2012}, "limit": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"] == 1
    assert response.json()["meta"]["request"] == {"commodity_desc": "CORN", "year": 2012}
    assert client.get("/example/count").status_code == 405
    assert client.post("/example/count", json={}).status_code == 422
    assert client.get("/example/get_series", params={"series_id": "X"}).status_code == 200


def test_post_route_openapi_and_errors() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [count]))
    spec = app.openapi()
    operation = spec["paths"]["/example/count"]["post"]
    assert operation["summary"] == "Count records matching filters."
    schema_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    schema = spec["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]
    assert set(schema["properties"]) == {"filters", "limit"}
    assert schema["required"] == ["filters"]
    response = TestClient(app).post("/example/count", json={"filters": {"bad": 1}})
    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM_MEDIA_TYPE
    assert response.json()["title"] == "InvalidRequestError"


class Priced(UpstreamModel):
    name: str
    price: Decimal | None


async def priced_async(name: str) -> Result[list[Priced]]:
    """Priced things.

    Args:
        name: Which.
    """
    return Result(
        data=[Priced(name=name, price=Decimal("4.61"))],
        meta=ResultMeta(source="example", endpoint="p"),
    )


async def latest_release_async() -> Result[list[str]]:
    """The newest release, at the time upstream printed it, without a zone."""
    printed = datetime(2026, 10, 6, 8, 0)
    meta = ResultMeta(
        source="example", endpoint="releases", published_at=printed, published_at_naive=True
    )
    return Result[list[str]](data=["202608"], meta=meta)


def test_http_responses_carry_a_naive_release_time_with_its_flag() -> None:
    # ADR-0022, rule 2: the HTTP envelope carries the flag.
    app = FastAPI()
    app.include_router(router_from_tasks("example", [sync(latest_release_async)]))
    meta = TestClient(app).get("/example/latest_release").json()["meta"]
    assert (meta["published_at"], meta["published_at_naive"]) == ("2026-10-06T08:00:00", True)


def test_http_responses_carry_decimals_as_numbers() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [sync(priced_async)]))
    response = TestClient(app).get("/example/priced", params={"name": "corn"})
    assert response.status_code == 200
    assert response.json()["data"] == [{"name": "corn", "price": 4.61}]


async def list_series_async(limit: int | None = None) -> Result[list[Series]]:
    """List series, one page when ``limit`` is given.

    Args:
        limit: Page size, e.g. ``2``; omit for every series.
    """
    records = [{"id": f"S{i}", "value": i} for i in range(5)]
    answer: dict[str, Any] = {"total": 5, "data": records if limit is None else records[:limit]}
    rows = [Series.model_validate(record) for record in answer["data"]]
    request = {} if limit is None else {"limit": limit}
    meta = ResultMeta(source="example", endpoint="list", request=request, total=answer["total"])
    return Result(data=rows, meta=meta)


def test_http_responses_carry_the_upstream_total() -> None:
    app = FastAPI()
    app.include_router(router_from_tasks("example", [sync(list_series_async)]))
    client = TestClient(app)
    page = client.get("/example/list_series", params={"limit": 2})
    assert page.status_code == 200
    assert len(page.json()["data"]) == 2
    assert page.json()["meta"]["total"] == 5
    assert client.get("/example/list_series").json()["meta"]["total"] == 5
    total = app.openapi()["components"]["schemas"]["ResultMeta"]["properties"]["total"]
    assert total["anyOf"] == [{"type": "integer"}, {"type": "null"}]


def shout(value: str) -> str:
    return value.upper()


async def get_ranked_async(
    top: Annotated[int, Field(ge=1, description="How many, from 1.")] = 10,
    name: Annotated[str, AfterValidator(shout)] = "corn",
) -> dict[str, Any]:
    """Rank one series.

    Args:
        top: How many to rank, from 1, e.g. ``10``.
        name: Which series, e.g. ``"corn"``.
    """
    return {"top": top, "name": name}


async def count_ranked_async(
    filters: Mapping[str, str], top: Annotated[int, Field(ge=1)] = 10
) -> dict[str, Any]:
    """Count the ranked records that match filters.

    Args:
        filters: Column filters, e.g. ``{"commodity_desc": "CORN"}``.
        top: How many to rank, from 1, e.g. ``10``.
    """
    return {"filters": dict(filters), "top": top}


def test_an_annotated_parameter_keeps_its_metadata_in_the_route() -> None:
    # https://github.com/xippios/sdk-core/issues/68: get_type_hints dropped the metadata.
    app = FastAPI()
    app.include_router(
        router_from_tasks("example", [sync(get_ranked_async), sync(count_ranked_async)])
    )
    client = TestClient(app)
    operation = app.openapi()["paths"]["/example/get_ranked"]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert params["top"]["schema"]["minimum"] == 1
    refused = client.get("/example/get_ranked", params={"top": 0})
    assert refused.status_code == 422
    assert refused.json() == refusal("top: Input should be greater than or equal to 1")
    served = client.get("/example/get_ranked", params={"name": "wheat"})
    assert served.json() == {"top": 10, "name": "WHEAT"}, "the validator ran"
    body = client.post("/example/count_ranked", json={"filters": {"a": "b"}, "top": 0})
    assert body.json() == refusal("top: Input should be greater than or equal to 1")
    assert client.post("/example/count_ranked", json={"filters": {}}).json()["top"] == 10
