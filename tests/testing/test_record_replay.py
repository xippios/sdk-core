from pathlib import Path

import pytest
import respx

from xippios.core.client import AsyncClient, Client, ClientConfig, RetryPolicy
from xippios.core.errors import NotFoundError
from xippios.core.testing import load_fixture, record, record_sync, replay

BASE = "https://api.example.test"


@pytest.fixture
def config() -> ClientConfig:
    return ClientConfig(
        source="example", version="1", base_url=BASE, retry=RetryPolicy(max_attempts=1)
    )


@pytest.mark.anyio
async def test_record_then_replay(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    upstream = respx_mock.get(f"{BASE}/v1/x").respond(
        200, json={"rows": [1, 2]}, headers={"X-Vintage": "2024-10"}
    )
    client = AsyncClient(config)
    fixture_file = tmp_path / "x" / "two_rows.json"
    await record(client, "/v1/x", fixture_file, params={"key": "SECRET", "year": 2024})
    assert upstream.call_count == 1
    assert "SECRET" not in fixture_file.read_text()

    respx_mock.reset()
    respx_mock.routes.clear()
    route = replay(respx_mock, fixture_file)
    response = await client.get("/v1/x", params={"key": "OTHER", "year": 2024})
    assert route.call_count == 1
    assert response.json() == {"rows": [1, 2]}
    assert response.headers["x-vintage"] == "2024-10"


@pytest.mark.anyio
async def test_record_keeps_error_responses(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.get(f"{BASE}/v1/missing").respond(404, json={"error": "no such thing"})
    client = AsyncClient(config)
    fixture_file = tmp_path / "missing.json"
    fixture = await record(client, "/v1/missing", fixture_file)
    assert fixture.response.status == 404
    assert load_fixture(fixture_file).response.status == 404

    respx_mock.routes.clear()
    replay(respx_mock, fixture_file)
    with pytest.raises(NotFoundError, match="no such thing"):
        await client.get("/v1/missing")


def test_record_sync(respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"n": 1})
    client = Client(config)
    fixture = record_sync(client.async_client, "/v1/x", tmp_path / "x.json")
    assert fixture.response.status == 200
    assert (tmp_path / "x.json").exists()
