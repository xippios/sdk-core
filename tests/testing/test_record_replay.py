import json
from pathlib import Path

import httpx
import pytest
import respx

from xippios.core.client import AsyncClient, Client, ClientConfig, RetryPolicy, Timeouts
from xippios.core.errors import NotFoundError
from xippios.core.testing import REDACTED, Scrub, load_fixture, record, record_sync, replay

BASE = "https://api.example.test"


class Sleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


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


@pytest.mark.anyio
async def test_record_form_data_records_body_and_content_type(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # sdk-cashctrl: CashCtrl's writes are form-encoded; a write fixture asserts its payload.
    respx_mock.post(f"{BASE}/v1/create.json").respond(200, json={"success": True, "insertId": 7})
    fixture = await record(
        AsyncClient(config),
        "/v1/create.json",
        tmp_path / "create.json",
        method="POST",
        data={"a": 1, "b": 2},
    )
    assert fixture.request.method == "POST"
    assert fixture.request.body == "a=1&b=2"
    assert fixture.request.content_type == "application/x-www-form-urlencoded"
    assert load_fixture(tmp_path / "create.json").request == fixture.request


@pytest.mark.anyio
async def test_record_json_records_the_json_text(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.post(f"{BASE}/v1/query").respond(200, json={"rows": []})
    fixture = await record(
        AsyncClient(config),
        "/v1/query",
        tmp_path / "query.json",
        method="POST",
        json={"filter": {"year": 2024}},
        headers={"X-Request": "one"},
    )
    assert fixture.request.body == '{"filter":{"year":2024}}'
    assert json.loads(fixture.request.body) == {"filter": {"year": 2024}}
    assert fixture.request.content_type == "application/json"


@pytest.mark.anyio
async def test_record_refuses_json_and_data_together(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").respond(200, json={})
    with pytest.raises(ValueError, match="not both"):
        await record(
            AsyncClient(config), "/v1/x", tmp_path / "x.json", method="POST", json={}, data={}
        )
    assert not route.called
    assert not (tmp_path / "x.json").exists()


@pytest.mark.anyio
async def test_record_uses_the_given_retry_and_timeouts(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # sdk-comtrade: a recording could not override the client's retry policy or timeouts.
    route = respx_mock.get(f"{BASE}/v1/slow").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"n": 1})]
    )
    sleeper = Sleeper()
    client = AsyncClient(config, sleep=sleeper)  # max_attempts=1
    fixture = await record(
        client,
        "/v1/slow",
        tmp_path / "slow.json",
        retry=RetryPolicy(max_attempts=2, jitter=False),
        timeouts=Timeouts(read=300.0),
    )
    assert fixture.response.status == 200
    assert route.call_count == 2
    assert sleeper.calls == [0.5]  # the client's sleep, the override's backoff
    assert route.calls.last.request.extensions["timeout"]["read"] == 300.0

    route.side_effect = [httpx.Response(503)]
    fixture = await record(client, "/v1/slow", tmp_path / "slow.json")
    assert fixture.response.status == 503  # the client itself is unchanged
    assert route.call_count == 3
    assert route.calls.last.request.extensions["timeout"]["read"] == 60.0


@pytest.mark.anyio
async def test_record_a_tenant_and_replay_on_the_placeholder_host(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    tenant = ClientConfig(
        source="example",
        version="1",
        base_url="https://acme.example.test/api/v1",
        retry=RetryPolicy(max_attempts=1),
    )
    respx_mock.get("https://acme.example.test/api/v1/account/list.json").respond(
        200, json={"data": [{"id": 1, "link": "https://acme.example.test/a/1"}]}
    )
    fixture_file = tmp_path / "account_list" / "one.json"
    await record(
        AsyncClient(tenant),
        "/account/list.json",
        fixture_file,
        scrub=Scrub(host="demo.example.test", secrets=["acme"]),
    )
    assert "acme" not in fixture_file.read_text().lower()

    respx_mock.routes.clear()
    route = replay(respx_mock, fixture_file)
    demo = ClientConfig(source="example", version="1", base_url="https://demo.example.test/api/v1")
    rows = await AsyncClient(demo).get_json("/account/list.json")
    assert rows == {"data": [{"id": 1, "link": "https://demo.example.test/a/1"}]}
    assert route.call_count == 1


def test_record_sync_takes_the_new_keywords(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.post(f"{BASE}/v1/x").respond(200, json={"org": "s3cr3t"})
    client = Client(config)
    fixture = record_sync(
        client.async_client,
        "/v1/x",
        tmp_path / "x.json",
        method="POST",
        data={"org": "s3cr3t"},
        scrub=Scrub(secrets=["s3cr3t"]),
        timeouts=Timeouts(read=5.0),
    )
    assert fixture.request.body == f"org={REDACTED}"
    assert fixture.response.body == f'{{"org":"{REDACTED}"}}'
