from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from xippios.core import sync
from xippios.core.errors import InvalidRequestError, NotFoundError, RateLimitError
from xippios.core.http import PROBLEM_MEDIA_TYPE, is_scalar, router_from_tasks
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


def test_defaults_and_plain_functions() -> None:
    client = make_client()
    assert (
        client.get("/example/get_series", params={"series_id": "X"}).json()["data"][0]["value"]
        == 2024.0
    )
    assert client.get("/example/list_things").json() == ["a", "b"]


def test_missing_required_parameter_is_422() -> None:
    assert make_client().get("/example/get_series").status_code == 422


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
