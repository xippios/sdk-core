import json
from pathlib import Path

import httpx
import pytest
import respx
from respx.models import AllMockedAssertionError

from xippios.core.client import (
    AsyncClient,
    Client,
    ClientConfig,
    HeaderKeyAuth,
    RetryPolicy,
    Timeouts,
)
from xippios.core.errors import NotFoundError, error_from_response
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
    recorded_query,
    replay,
    response_from_fixture,
    sent_query,
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


class ClosingTransport(httpx.AsyncBaseTransport):
    """Answers every request and counts how often a pool closed it."""

    def __init__(self) -> None:
        self.closed = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"n": 1})

    async def aclose(self) -> None:
        self.closed += 1


@pytest.mark.anyio
async def test_record_closes_the_derived_client_and_leaves_the_transport_open(
    config: ClientConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[AsyncClient] = []
    aclose = AsyncClient.aclose

    async def counting_aclose(self: AsyncClient) -> None:
        closed.append(self)
        await aclose(self)

    monkeypatch.setattr(AsyncClient, "aclose", counting_aclose)
    transport = ClosingTransport()
    client = AsyncClient(config, transport=transport)
    await record(client, "/v1/x", tmp_path / "a.json", timeouts=Timeouts(read=300.0))
    assert len(closed) == 1  # the derived client, closed when record returned
    assert closed[0] is not client
    assert transport.closed == 0  # the client's transport, which derive only borrowed
    await record(client, "/v1/x", tmp_path / "b.json")
    assert len(closed) == 1  # the caller's own client stays open
    await client.aclose()
    assert transport.closed == 1


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


@pytest.mark.anyio
@pytest.mark.parametrize("override", [False, True], ids=["client", "derived"])
async def test_record_without_the_client_s_auth(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path, override: bool
) -> None:
    # sdk-comtrade: a keyless reference file is recorded without sending the key.
    route = respx_mock.get(f"{BASE}/files/ref.json").respond(200, json={"codes": []})
    client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", "EXAMPLE_API_KEY"))
    timeouts = Timeouts(read=300.0) if override else None
    await record(client, "/files/ref.json", tmp_path / "ref.json", auth=None, timeouts=timeouts)
    assert "x-api-key" not in route.calls.last.request.headers
    await record(client, "/files/ref.json", tmp_path / "ref.json", timeouts=timeouts)
    assert "x-api-key" in route.calls.last.request.headers


def test_record_sync_takes_auth(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/files/ref.json").respond(200, json={})
    client = Client(config, auth=HeaderKeyAuth("X-Api-Key", "EXAMPLE_API_KEY"))
    record_sync(client.async_client, "/files/ref.json", tmp_path / "ref.json", auth=None)
    assert "x-api-key" not in route.calls.last.request.headers


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


def test_match_params_refuses_a_partly_redacted_value(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    request = httpx.Request("GET", f"{BASE}/v1/x?org=acme-1&year=2024")
    path = tmp_path / "x.json"
    write_fixture(
        httpx.Response(200, json={}, request=request), path, scrub=Scrub(secrets=["acme"])
    )
    assert httpx.URL(load_fixture(path).request.url).params["org"] == f"{REDACTED}-1"
    with pytest.raises(
        ValueError, match=r"^match_params: 'org' was recorded as REDACTED, in"
    ) as info:
        replay(respx_mock, path, match_params=["org"])
    assert "acme" not in str(info.value)
    assert len(respx_mock.routes) == 0


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


def test_the_more_specific_fixture_is_mounted_first(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # match_params cannot say "countOnly absent"; mount order does it (documented).
    count = httpx.Request("GET", f"{BASE}/v1/get", params={"countOnly": "true", "r": 1})
    data = httpx.Request("GET", f"{BASE}/v1/get", params={"r": 1})
    write_fixture(httpx.Response(200, json={"count": 3}, request=count), tmp_path / "c.json")
    write_fixture(httpx.Response(200, json={"rows": []}, request=data), tmp_path / "d.json")
    replay(respx_mock, tmp_path / "c.json", match_params=["countOnly"])
    replay(respx_mock, tmp_path / "d.json")
    assert httpx.get(f"{BASE}/v1/get?countOnly=true&r=1").json() == {"count": 3}
    assert httpx.get(f"{BASE}/v1/get?r=1").json() == {"rows": []}


def test_sent_query_is_the_last_query_scrubbed(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # sdk-usda-nass (sent_query) and sdk-comtrade (_sent) each carried it; cashctrl reads
    # route.calls.last inline (row 36 a).
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    with pytest.raises(AssertionError, match="received no request"):
        sent_query(route)
    with Client(config) as client:
        client.get("/v1/x", params={"key": "SECRET", "year": 2024})
        client.get("/v1/x", params={"year": 2025, "state": ""})
    assert sent_query(route) == {"year": "2025", "state": ""}
    assert [httpx.URL(url).params.get("key") for url in sent_urls(route)] == [REDACTED, None]


def test_sent_query_refuses_a_repeated_parameter(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    httpx.get(f"{BASE}/v1/x?period=2022&period=2023&flow=M")
    with pytest.raises(AssertionError, match=r"sent more than once: \['period'\]"):
        sent_query(route)


def test_recorded_query_is_the_scrubbed_recorded_query(tmp_path: Path) -> None:
    # sdk-comtrade (recorded_params, _recorded) and sdk-cashctrl (recorded_query).
    request = httpx.Request("GET", f"{BASE}/v1/x?key=SECRET&year=2024&q=")
    path = tmp_path / "x.json"
    write_fixture(httpx.Response(200, json={}, request=request), path)
    assert recorded_query(load_fixture(path)) == {"key": REDACTED, "year": "2024", "q": ""}


def test_a_recorded_answer_is_served_at_another_url(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # sdk-usda-psd and sdk-usda-esr each carried _mount_recorded_404 (row 41 b): the empty
    # 404 recorded for 1900 stands in for a year without data inside a range.
    request = httpx.Request("GET", f"{BASE}/v1/year/1900")
    path = tmp_path / "data" / "unknown_year.json"
    write_fixture(httpx.Response(404, content=b"", request=request), path)
    route = replay(respx_mock, path, url=f"{BASE}/v1/year/2022")
    assert httpx.get(f"{BASE}/v1/year/2022").status_code == 404
    with pytest.raises(AllMockedAssertionError):
        httpx.get(f"{BASE}/v1/year/1900")
    assert sent_urls(route) == [f"{BASE}/v1/year/2022"]
    flows = replay(respx_mock, path, url=f"{BASE}/v1/year/2023?flow=M", match_params=["flow"])
    assert httpx.get(f"{BASE}/v1/year/2023?flow=M").status_code == 404
    with pytest.raises(AllMockedAssertionError):
        httpx.get(f"{BASE}/v1/year/2023?flow=X")
    assert flows.call_count == 1
    with pytest.raises(ValueError, match=r"'year' is not a query parameter of the URL given"):
        replay(respx_mock, path, url=f"{BASE}/v1/year/2024", match_params=["year"])


def test_the_plugin_serves_a_recorded_answer_at_another_url(
    replay_fixture: ReplayFixture,
) -> None:
    route = replay_fixture("x", "y", url=f"{BASE}/v2/x")
    with Client(ClientConfig(source="example", version="1", base_url=BASE)) as client:
        assert client.get_json("/v2/x") == {"n": 1}
    assert sent_urls(route) == [f"{BASE}/v2/x"]


def test_response_from_fixture_carries_the_recorded_request(tmp_path: Path) -> None:
    # sdk-usda-psd, sdk-usda-esr, sdk-usda-gats (test_client.py) and sdk-cashctrl
    # (test_errors.py) each carried recorded(): a recorded answer for classify.
    request = httpx.Request("GET", f"{BASE}/v1/x?key=SECRET")
    path = tmp_path / "x.json"
    write_fixture(httpx.Response(404, json={"error": "none"}, request=request), path)
    response = response_from_fixture(load_fixture(path))
    assert (response.status_code, response.json()) == (404, {"error": "none"})
    assert (response.request.method, str(response.request.url)) == (
        "GET",
        f"{BASE}/v1/x?key={REDACTED}",
    )
    error = error_from_response(response, source="example")
    assert isinstance(error, NotFoundError)
    assert str(error).startswith("404 from GET /v1/x")
