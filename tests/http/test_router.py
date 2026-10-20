from fastapi import FastAPI
from fastapi.testclient import TestClient

from xippios.core import sync
from xippios.core.errors import NotFoundError, RateLimitError
from xippios.core.http import PROBLEM_MEDIA_TYPE, router_from_tasks
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
