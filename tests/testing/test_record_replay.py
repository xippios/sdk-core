import json
from pathlib import Path

import httpx
import pytest
import respx
from respx.models import AllMockedAssertionError

from xippios.core.client import AsyncClient, Client, ClientConfig, RetryPolicy, Timeouts
from xippios.core.errors import NotFoundError
from xippios.core.testing import (
    REDACTED,
    Fixture,
    ReplayFixture,
    Scrub,
    fixture_from_response,
    load_fixture,
    mount_fixture,
    record,
    record_sync,
    replay,
    sent_urls,
    write_fixture,
)

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


def _recorded(url: str, body: object, method: str = "GET") -> Fixture:
    """A synthetic fixture, built here: this repository records from no upstream."""
    request = httpx.Request(method, url)
    return fixture_from_response(httpx.Response(200, json=body, request=request))


@pytest.mark.anyio
async def test_match_params_matches_the_recorded_value_and_misses_another(
    respx_mock: respx.MockRouter,
) -> None:
    # sdk-comtrade: the count and the data call of data/v1/get share one path and differ
    # in countOnly=true.
    count = _recorded(f"{BASE}/data/v1/get?reporterCode=842&countOnly=true", {"count": 12})
    route = mount_fixture(respx_mock, count, match_params=["countOnly"])
    async with httpx.AsyncClient() as http:
        answer = await http.get(f"{BASE}/data/v1/get", params={"countOnly": "true", "x": "1"})
        assert answer.json() == {"count": 12}
        assert route.call_count == 1
        with pytest.raises(AllMockedAssertionError):
            await http.get(f"{BASE}/data/v1/get", params={"countOnly": "false"})
        with pytest.raises(AllMockedAssertionError):
            await http.get(f"{BASE}/data/v1/get")

        data = _recorded(f"{BASE}/data/v1/get?reporterCode=842", {"data": [1]})
        fallback = mount_fixture(respx_mock, data)  # mounted second, so asked second
        assert (await http.get(f"{BASE}/data/v1/get?countOnly=false")).json() == {"data": [1]}
        assert (await http.get(f"{BASE}/data/v1/get?countOnly=true")).json() == {"count": 12}
        assert (route.call_count, fallback.call_count) == (2, 1)


@pytest.mark.anyio
async def test_match_params_matches_every_recorded_value_of_a_name(
    respx_mock: respx.MockRouter,
) -> None:
    chunk = _recorded(f"{BASE}/v1/x?period=2022&period=2023&flow=M", {"rows": 2})
    route = mount_fixture(respx_mock, chunk, match_params=("period", "flow"))
    async with httpx.AsyncClient() as http:
        assert (await http.get(f"{BASE}/v1/x?flow=M&period=2022&period=2023")).status_code == 200
        with pytest.raises(AllMockedAssertionError):
            await http.get(f"{BASE}/v1/x?flow=M&period=2022")
        with pytest.raises(AllMockedAssertionError):
            await http.get(f"{BASE}/v1/x?flow=X&period=2022&period=2023")
    assert route.call_count == 1


def test_match_params_refuses_a_redacted_or_absent_name(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    request = httpx.Request("GET", f"{BASE}/v1/x?key=SECRET&year=2024")
    path = tmp_path / "x.json"
    write_fixture(httpx.Response(200, json={}, request=request), path)
    with pytest.raises(ValueError, match=r"^match_params: 'key' was recorded as REDACTED") as info:
        replay(respx_mock, path, match_params=["year", "key"])
    assert "SECRET" not in str(info.value)
    with pytest.raises(ValueError, match=r"^match_params: 'month' is not a query parameter"):
        replay(respx_mock, path, match_params=["month"])
    with pytest.raises(TypeError, match="collection of names"):
        replay(respx_mock, path, match_params="year")
    assert len(respx_mock.routes) == 0  # a refusal mounts nothing
    replay(respx_mock, path, match_params=["year"])
    replay(respx_mock, path, match_params=[])
    assert len(respx_mock.routes) == 2


@pytest.mark.anyio
async def test_replay_ignores_the_body_and_the_test_asserts_it(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.post(f"{BASE}/v1/create.json").respond(200, json={"success": True})
    client = AsyncClient(config)
    fixture_file = tmp_path / "create.json"
    recorded = await record(
        client, "/v1/create.json", fixture_file, method="POST", data={"name": "Corn", "n": 2}
    )

    respx_mock.routes.clear()
    route = replay(respx_mock, fixture_file)
    await client.request("POST", "/v1/create.json", data={"name": "Corn", "n": 2})
    assert route.calls.last.request.content.decode() == recorded.request.body == "name=Corn&n=2"
    assert route.calls.last.request.headers["content-type"] == recorded.request.content_type

    await client.request("POST", "/v1/create.json", data={"name": "Rice"})
    assert route.call_count == 2  # the body is not matched; the assertion is the test's
    assert route.calls.last.request.content.decode() != recorded.request.body


@pytest.mark.anyio
async def test_sent_urls_are_scrubbed_strings_in_order(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # sdk-usda-nass: a test that kept the request in its locals would print the key.
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    assert sent_urls(route) == []
    client = AsyncClient(config)
    await client.get("/v1/x", params={"key": "SECRET", "year": 2024})
    await client.get("/v1/x", params={"year": 2025})
    urls = sent_urls(route)
    assert urls == [f"{BASE}/v1/x?key={REDACTED}&year=2024", f"{BASE}/v1/x?year=2025"]
    assert all(isinstance(url, str) for url in urls)


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    """The plugin's ``replay_fixture`` reads from here: one recorded ``GET /v1/x?year=2024``."""
    request = httpx.Request("GET", f"{BASE}/v1/x", params={"year": 2024})
    write_fixture(httpx.Response(200, json={"n": 1}, request=request), tmp_path / "x" / "y.json")
    return tmp_path


def test_replay_fixture_is_typed_as_replay_fixture(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("x", "y", match_params=["year"])
    with Client(ClientConfig(source="example", version="1", base_url=BASE)) as client:
        assert client.get_json("/v1/x", params={"year": 2024}) == {"n": 1}
    assert sent_urls(route) == [f"{BASE}/v1/x?year=2024"]
