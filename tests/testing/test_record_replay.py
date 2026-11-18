import gzip
import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from respx.models import AllMockedAssertionError

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    RetryPolicy,
)
from xippios.core.errors import NotFoundError, TransportError, error_from_response
from xippios.core.testing import (
    REDACTED,
    Fixture,
    ReplayFixture,
    Scrub,
    fixture_from_response,
    fixture_text,
    load_fixture,
    record,
    record_sync,
    recorded_query,
    response_from_fixture,
    sent_bodies,
    sent_query,
    sent_urls,
    write_fixture,
)
from xippios.core.testing.replay import mount_fixture, replay

BASE = "https://api.example.test"


def _write(response: httpx.Response, path: Path) -> None:
    """Write ``response`` as a fixture, scrubbed of credentials only."""
    write_fixture(fixture_from_response(response), path)


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
    await record(client, "/v1/x", fixture_file, params={"token": "SECRET", "year": 2024})
    assert upstream.call_count == 1
    assert "SECRET" not in fixture_file.read_text()

    respx_mock.reset()
    respx_mock.routes.clear()
    route = replay(respx_mock, fixture_file)
    response = await client.get("/v1/x", params={"token": "OTHER", "year": 2024})
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
    fixture = record_sync(AsyncClient(config), "/v1/x", tmp_path / "x.json")
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
async def test_record_scrubs_the_named_secrets(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.get(f"{BASE}/v1/account/list.json").respond(200, json={"org": "acme"})
    fixture_file = tmp_path / "account_list" / "one.json"
    fixture = await record(
        AsyncClient(config), "/v1/account/list.json", fixture_file, scrub=Scrub(secrets=["acme"])
    )
    assert fixture.response.body == f'{{"org":"{REDACTED}"}}'
    assert "acme" not in fixture_file.read_text()


@pytest.mark.anyio
async def test_record_without_the_client_s_auth(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # sdk-comtrade: a keyless reference file is recorded without sending the key.
    route = respx_mock.get(f"{BASE}/files/ref.json").respond(200, json={"codes": []})
    client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", "EXAMPLE_API_KEY"))
    await record(client, "/files/ref.json", tmp_path / "ref.json", auth=None)
    assert "x-api-key" not in route.calls.last.request.headers
    await record(client, "/files/ref.json", tmp_path / "ref.json")
    assert "x-api-key" in route.calls.last.request.headers


def _retrying(sleeps: list[float], **options: Any) -> AsyncClient:
    """A client whose policy retries a 429, a 5xx and a transport failure, as a source's does.

    Each wait the retries would take is appended to ``sleeps`` instead of slept.
    """

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    config = ClientConfig(source="example", version="1", base_url=BASE, **options)
    assert config.retry.max_attempts > 1, "the default policy retries"
    return AsyncClient(config, sleep=sleep)


@pytest.mark.parametrize("status", [429, 503])
def test_a_recording_sends_once_whatever_the_client_s_retry_policy(
    respx_mock: respx.MockRouter, tmp_path: Path, status: int
) -> None:
    # https://github.com/xippios/sdk-core/issues/148: a source with a quota or a bill built
    # a client of its own to record; the recorder now sends once through the source's.
    route = respx_mock.get(f"{BASE}/v1/x").respond(
        status, json={"error": "busy"}, headers={"Retry-After": "0"}
    )
    sleeps: list[float] = []
    fixture = record_sync(_retrying(sleeps), "/v1/x", tmp_path / "busy.json")
    assert route.call_count == 1
    assert sleeps == []
    assert fixture.response.status == status
    assert load_fixture(tmp_path / "busy.json").response.status == status


def test_a_transport_failure_while_recording_is_sent_once_and_writes_nothing(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(side_effect=httpx.ConnectError("refused"))
    sleeps: list[float] = []
    with pytest.raises(TransportError, match=r"^ConnectError: refused$"):
        record_sync(_retrying(sleeps), "/v1/x", tmp_path / "x.json")
    assert (route.call_count, sleeps) == (1, [])
    assert not (tmp_path / "x.json").exists()


@pytest.mark.anyio
async def test_a_recording_neither_reads_nor_stores_the_cache(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # A recording is one live exchange: an answer the cache holds is not one.
    route = respx_mock.get(f"{BASE}/v1/x")
    route.side_effect = [httpx.Response(200, json={"n": 1}), httpx.Response(200, json={"n": 2})]
    client = _retrying([], cache=MemoryCache())
    assert (await client.get_answer("/v1/x")).payload == {"n": 1}  # stored
    fixture = await record(client, "/v1/x", tmp_path / "x.json")
    assert route.call_count == 2
    assert json.loads(fixture.response.body) == {"n": 2}
    assert (await client.get_answer("/v1/x")).payload == {"n": 1}, "the entry stands"
    assert route.call_count == 2


@pytest.mark.anyio
async def test_a_recording_runs_before_request_once_and_observe_sees_its_answer(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # A quota policy hears of the request a recording spends, as of any other.
    respx_mock.get(f"{BASE}/v1/x").respond(503, headers={"X-Left": "9"}, text="busy")
    before: list[str] = []
    observed: list[tuple[int, str, bytes]] = []

    def observe(response: httpx.Response) -> None:
        observed.append((response.status_code, response.headers["x-left"], response.content))

    client = _retrying(
        [], before_request=lambda request: before.append(request.url.path), observe=observe
    )
    await record(client, "/v1/x", tmp_path / "x.json")
    assert before == ["/v1/x"]
    assert observed == [(503, "9", b"busy")]


@pytest.mark.anyio
async def test_a_body_past_max_read_bytes_raises_and_writes_nothing(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # https://github.com/xippios/sdk-core/issues/62: an unfiltered Eurostat dataset that
    # upstream may answer synchronously is 145 MB.
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, content=b"x" * 1001)
    fixture_file = tmp_path / "x" / "big.json"
    client = AsyncClient(config)
    with pytest.raises(
        ValueError,
        match=r"^GET /v1/x answered a body over 1000 bytes, the recording's max_read_bytes; ",
    ):
        await record(client, "/v1/x", fixture_file, params={"year": 2024}, max_read_bytes=1000)
    assert not fixture_file.exists()
    whole = await record(client, "/v1/x", fixture_file, max_read_bytes=1001)
    assert len(whole.response.body) == 1001
    assert len((await record(client, "/v1/x", fixture_file, max_read_bytes=None)).response.body)
    for bound in (0, -1):
        with pytest.raises(ValueError, match=r"^max_read_bytes must be at least 1$"):
            await record(client, "/v1/x", fixture_file, max_read_bytes=bound)
    assert route.call_count == 3, "a bound below 1 is refused before anything is sent"


@pytest.mark.anyio
async def test_max_read_bytes_counts_the_body_as_decoded(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # The bound is upstream's whole body as httpx decodes it, as original_bytes counts it.
    packed = gzip.compress(b"x" * 5000)
    assert len(packed) < 100
    respx_mock.get(f"{BASE}/v1/x").respond(
        200, content=packed, headers={"Content-Encoding": "gzip"}
    )
    client = AsyncClient(config)
    with pytest.raises(ValueError, match="answered a body over 4999 bytes"):
        await record(client, "/v1/x", tmp_path / "x.json", max_read_bytes=4999)
    fixture = await record(client, "/v1/x", tmp_path / "x.json", max_read_bytes=5000)
    assert fixture.response.body == "x" * 5000


class _Chunks(httpx.AsyncByteStream):
    """A body of ``count`` chunks of one MiB, counting the chunks a reader took."""

    def __init__(self, count: int) -> None:
        self.count = count
        self.taken = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self.count):
            self.taken += 1
            yield bytes(1024 * 1024)


@pytest.mark.anyio
async def test_the_recorder_stops_reading_at_32_mib_by_default(tmp_path: Path) -> None:
    # Four times the largest body a source records whole (sdk-usda-gats, 7.6 MB), and the
    # reading stops there: the rest of a 145 MB answer is never fetched.
    body = _Chunks(40)
    observed: list[int] = []

    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body, request=request)

    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        observe=lambda response: observed.append(response.status_code),
    )
    client = AsyncClient(config, transport=httpx.MockTransport(answer))
    with pytest.raises(ValueError, match=f"answered a body over {32 * 1024 * 1024} bytes"):
        await record(client, "/v1/x", tmp_path / "x.json")
    assert body.taken == 33
    assert observed == [200], "observe still hears of the request the recording spent"
    assert not (tmp_path / "x.json").exists()


TOKENS = ("tok-access-1", "tok-id-2", "tok-refresh-3")  # pragma: allowlist secret
"""A login answer's tokens, which name no credential: ``AccessToken`` is one word."""


def _tokens(response: httpx.Response) -> list[str]:
    """The tokens of a login answer, as sdk-faostat's Cognito login returns them."""
    result = response.json().get("AuthenticationResult", {})
    return [result[name] for name in ("AccessToken", "IdToken", "RefreshToken") if name in result]


def test_a_login_answer_records_through_record_sync_its_tokens_redacted(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    # https://github.com/xippios/sdk-core/issues/164: the tokens are known once the answer
    # is, so the source names where they are read, not their values.
    access, identity, refresh = TOKENS
    answer = {"AccessToken": access, "IdToken": identity, "RefreshToken": refresh}
    respx_mock.post(f"{BASE}/auth/login").respond(
        200,
        json={"AuthenticationResult": {**answer, "ExpiresIn": 3600}},
        headers={"X-Echo": access},
    )
    fixture_file = tmp_path / "auth_login" / "login.json"
    fixture = record_sync(
        AsyncClient(config),
        "/auth/login",
        fixture_file,
        method="POST",
        data={"user": "user-1", "pass": "pass-2"},
        scrub=Scrub(secrets=["user-1", "pass-2"], response_secrets=_tokens),
    )
    result = json.loads(fixture.response.body)["AuthenticationResult"]
    assert result == {
        "AccessToken": REDACTED,
        "IdToken": REDACTED,
        "RefreshToken": REDACTED,
        "ExpiresIn": 3600,
    }
    assert dict(fixture.response.headers)["x-echo"] == REDACTED
    assert fixture.request.body == f"user={REDACTED}&pass={REDACTED}"
    written = fixture_file.read_text(encoding="utf-8")
    assert not [value for value in (*TOKENS, "user-1", "pass-2") if value in written]


def test_response_secrets_refuses_one_string_and_an_empty_value(
    respx_mock: respx.MockRouter, config: ClientConfig, tmp_path: Path
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"token": "tok-1", "empty": ""})
    fixture_file = tmp_path / "x.json"
    one_string = Scrub(response_secrets=lambda response: response.json()["token"])
    with pytest.raises(TypeError, match=r"^response_secrets returns a sequence of values"):
        record_sync(AsyncClient(config), "/v1/x", fixture_file, scrub=one_string)
    empty = Scrub(response_secrets=lambda response: [response.json()["empty"]])
    with pytest.raises(ValueError, match=r"^response_secrets returned an empty value"):
        record_sync(AsyncClient(config), "/v1/x", fixture_file, scrub=empty)
    not_text = Scrub(response_secrets=lambda response: [7])  # type: ignore[list-item]
    with pytest.raises(TypeError, match=r"^response_secrets returns text values"):
        record_sync(AsyncClient(config), "/v1/x", fixture_file, scrub=not_text)
    assert not fixture_file.exists()


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


def test_match_params_refuses_a_credential_or_absent_name(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    request = httpx.Request("GET", f"{BASE}/v1/x?token=SECRET&year=2024")
    path = tmp_path / "x.json"
    _write(httpx.Response(200, json={}, request=request), path)
    with pytest.raises(ValueError, match=r"^match_params: 'token' names a credential") as info:
        replay(respx_mock, path, match_params=["year", "token"])
    assert "SECRET" not in str(info.value)
    with pytest.raises(ValueError, match=r"^match_params: 'month' is not a query parameter"):
        replay(respx_mock, path, match_params=["month"])
    with pytest.raises(TypeError, match="collection of names"):
        replay(respx_mock, path, match_params="year")
    assert len(respx_mock.routes) == 0  # a refusal mounts nothing
    replay(respx_mock, path, match_params=["year"])
    replay(respx_mock, path, match_params=[])
    assert len(respx_mock.routes) == 2


def test_match_params_on_a_key_that_is_data(respx_mock: respx.MockRouter) -> None:
    # Eurostat's SDMX series key, keyless (ADR-0019, decision 6); NASS's QueryKeyAuth("key")
    # makes it a credential, and a value recorded as REDACTED cannot be matched.
    series = _recorded(f"{BASE}/data/prc_hicp_manr?key=M.DE.CP00", [1])
    route = mount_fixture(respx_mock, series, match_params=["key"])
    assert httpx.get(f"{BASE}/data/prc_hicp_manr?key=M.DE.CP00").json() == [1]
    assert sent_urls(route) == [f"{BASE}/data/prc_hicp_manr?key=M.DE.CP00"]
    QueryKeyAuth("key", "EXAMPLE_API_KEY")
    with pytest.raises(ValueError, match=r"^match_params: 'key' names a credential"):
        mount_fixture(respx_mock, series, match_params=["key"])
    nass = _recorded(f"{BASE}/api/api_GET?key=SECRET&year=2024", [1])
    assert recorded_query(nass) == {"key": REDACTED, "year": "2024"}


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
    assert recorded.request.body == "name=Corn&n=2"
    assert sent_bodies(route) == [{"name": "Corn", "n": "2"}]
    assert route.calls.last.request.headers["content-type"] == recorded.request.content_type

    await client.request("POST", "/v1/create.json", data={"name": "Rice"})
    assert route.call_count == 2  # the body is not matched; the assertion is the test's
    assert sent_bodies(route)[-1] == {"name": "Rice"}


@pytest.mark.anyio
async def test_sent_urls_are_scrubbed_strings_in_order(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # sdk-usda-nass: a test that kept the request in its locals would print the key.
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    assert sent_urls(route) == []
    client = AsyncClient(config)
    await client.get("/v1/x", params={"token": "SECRET", "year": 2024})
    await client.get("/v1/x", params={"year": 2025})
    urls = sent_urls(route)
    assert urls == [f"{BASE}/v1/x?token={REDACTED}&year=2024", f"{BASE}/v1/x?year=2025"]
    assert all(isinstance(url, str) for url in urls)


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    """The plugin's ``replay_fixture`` reads from here: one recorded ``GET /v1/x?year=2024``."""
    request = httpx.Request("GET", f"{BASE}/v1/x", params={"year": 2024})
    _write(httpx.Response(200, json={"n": 1}, request=request), tmp_path / "x" / "y.json")
    return tmp_path


def test_replay_fixture_is_typed_as_replay_fixture(replay_fixture: ReplayFixture) -> None:
    route = replay_fixture("x", "y", match_params=["year"])
    assert httpx.get(f"{BASE}/v1/x", params={"year": 2024}).json() == {"n": 1}
    assert sent_urls(route) == [f"{BASE}/v1/x?year=2024"]


@pytest.mark.anyio
async def test_a_truncated_array_records_replays_and_decodes(
    respx_mock: respx.MockRouter, replay_fixture: ReplayFixture, fixtures_dir: Path
) -> None:
    # Row 43 (sdk-usda-gats): a list over the fixture cap keeps its first elements.
    respx_mock.get(f"{BASE}/v1/rows").respond(200, json=[{"n": n} for n in range(1000)])
    client = AsyncClient(ClientConfig(source="example", version="1", base_url=BASE))
    with pytest.raises(ValueError, match="max_bytes must be at least 1"):
        await record(client, "/v1/rows", fixtures_dir / "rows" / "cut.json", max_bytes=0)
    assert respx_mock.calls.call_count == 0  # refused before anything is sent
    recorded = await record(client, "/v1/rows", fixtures_dir / "rows" / "cut.json", max_bytes=60)
    written = load_fixture(fixtures_dir / "rows" / "cut.json").response
    assert written == recorded.response
    assert (written.truncated, written.original_count) == (True, 1000)
    assert (fixtures_dir / "rows" / "cut.json").read_text(encoding="utf-8") == fixture_text(
        recorded
    )

    respx_mock.routes.clear()
    replay_fixture("rows", "cut")
    assert await client.get_json("/v1/rows") == [{"n": n} for n in range(7)]


@pytest.mark.anyio
async def test_an_object_s_array_records_its_last_elements_and_replays(
    respx_mock: respx.MockRouter, replay_fixture: ReplayFixture, fixtures_dir: Path
) -> None:
    # Row 127 (sdk-usda-nass, sdk-usda-psd): {"data": [...]} ordered oldest first.
    answer = {"data": [{"year": year} for year in range(1960, 2024)], "count": 64}
    respx_mock.get(f"{BASE}/api/api_GET").respond(200, json=answer)
    client = AsyncClient(ClientConfig(source="example", version="1", base_url=BASE))
    path = fixtures_dir / "api_GET" / "latest.json"
    choices: list[dict[str, Any]] = [{"array_key": "data"}, {"keep": "last"}]
    for options in choices:
        with pytest.raises(ValueError, match=r"^array_key and keep='last' choose what max_bytes"):
            await record(client, "/api/api_GET", path, **options)
    assert respx_mock.calls.call_count == 0  # refused before anything is sent
    recorded = await record(
        client, "/api/api_GET", path, max_bytes=60, array_key="data", keep="last"
    )
    assert (recorded.response.truncated, recorded.response.original_count) == (True, 64)

    respx_mock.routes.clear()
    replay_fixture("api_GET", "latest")
    replayed = await client.get_json("/api/api_GET")
    assert replayed == {"data": [{"year": 2022}, {"year": 2023}], "count": 64}


@pytest.mark.anyio
async def test_a_download_replays_its_sample_body_and_the_mark_survives(
    respx_mock: respx.MockRouter,
    replay_fixture: ReplayFixture,
    fixtures_dir: Path,
    config: ClientConfig,
) -> None:
    # Row 125 (sdk-usda-wasde): the replay fixture carries the sample the parser tests
    # read, marked a sample, so `truncated` keeps meaning the recorder's cut.
    whole = b"<report>" + b"<page/>" * 1000 + b"</report>"
    sample = b"<report><page/></report>"
    request = httpx.Request("GET", f"{BASE}/files/wasde.xml")
    xml = {"Content-Type": "application/xml"}
    recorded = fixture_from_response(
        httpx.Response(200, content=whole, headers=xml, request=request)
    )
    marks = {"original_bytes": len(whole), "sha256": hashlib.sha256(whole).hexdigest()}
    body = recorded.response.model_copy(update={"body": sample.decode(), "sample": True, **marks})
    path = fixtures_dir / "download_report" / "sr12.json"
    write_fixture(recorded.model_copy(update={"response": body}), path)
    loaded = load_fixture(path).response
    assert (loaded.sample, loaded.truncated, loaded.original_bytes) == (True, False, len(whole))
    assert loaded.sha256 == marks["sha256"]

    replay_fixture("download_report", "sr12")
    got = await AsyncClient(config).download(f"{BASE}/files/wasde.xml", fixtures_dir / "sr12.xml")
    assert (fixtures_dir / "sr12.xml").read_bytes() == sample
    assert got.bytes == len(sample)


def test_sent_query_is_the_last_query_scrubbed(respx_mock: respx.MockRouter) -> None:
    # sdk-usda-nass (sent_query) and sdk-comtrade (_sent) each carried it; cashctrl reads
    # route.calls.last inline (row 36 a).
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    with pytest.raises(AssertionError, match="received no request"):
        sent_query(route)
    httpx.get(f"{BASE}/v1/x", params={"token": "SECRET", "year": 2024})
    httpx.get(f"{BASE}/v1/x", params={"year": 2025, "state": ""})
    assert sent_query(route) == {"year": "2025", "state": ""}
    assert [httpx.URL(url).params.get("token") for url in sent_urls(route)] == [REDACTED, None]


def test_sent_query_refuses_a_repeated_parameter(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    httpx.get(f"{BASE}/v1/x?period=2022&period=2023&flow=M")
    with pytest.raises(AssertionError, match=r"sent more than once: \['period'\]"):
        sent_query(route)


@pytest.mark.anyio
async def test_sent_bodies_decodes_json_and_forms_with_credentials_redacted(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # https://github.com/xippios/sdk-core/issues/183: sdk-google-mail decoded its writes'
    # JSON, sdk-cashctrl its writes' forms and sdk-faostat its logins' forms, each from
    # route.calls, where a failing assertion prints the request.
    route = respx_mock.post(f"{BASE}/v1/write").respond(200, json={})
    client = AsyncClient(config)
    assert sent_bodies(route) == []
    grant = {"access_token": "tok-1"}  # pragma: allowlist secret
    await client.request("POST", "/v1/write", json={"addLabelIds": ["L1"], "grant": grant, "n": 2})
    listed = [{"client_secret": "s-1"}, 3]  # pragma: allowlist secret
    await client.request("POST", "/v1/write", json=listed)
    await client.request(
        "POST",
        "/v1/write",
        data={"name": "Corn ü", "password": "p-1", "note": ""},  # pragma: allowlist secret
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
    )
    await client.request("POST", "/v1/write")
    assert sent_bodies(route) == [
        {"addLabelIds": ["L1"], "grant": {"access_token": REDACTED}, "n": 2},
        [{"client_secret": REDACTED}, 3],
        {"name": "Corn ü", "password": REDACTED, "note": ""},
        None,
    ]


def test_sent_bodies_refuses_a_body_it_does_not_decode(respx_mock: respx.MockRouter) -> None:
    cases: list[tuple[dict[str, Any], str]] = [
        (
            {"content": b"tok-1", "headers": {"Content-Type": "text/plain"}},
            r"^call 2 sent a text/plain body; sent_bodies decodes JSON and forms$",
        ),
        ({"content": b"tok-1"}, r"^call 2 sent a body without a content type; "),
        (
            {"content": b"{tok-1", "headers": {"Content-Type": "application/json"}},
            r"^call 2 sent a body declared application/json that is not JSON$",
        ),
        (
            {"data": {"id": [1, 2], "q": "tok-1"}},
            r"^call 2 sent form fields more than once: \['id'\]$",
        ),
    ]
    for options, refusal in cases:
        respx_mock.routes.clear()
        route = respx_mock.post(f"{BASE}/v1/write").respond(200, json={})
        httpx.post(f"{BASE}/v1/write", json={"n": 1})
        httpx.post(f"{BASE}/v1/write", **options)
        with pytest.raises(AssertionError, match=refusal) as refused:
            sent_bodies(route)
        assert "tok-1" not in str(refused.value)


def test_recorded_query_is_the_scrubbed_recorded_query(tmp_path: Path) -> None:
    # sdk-comtrade (recorded_params, _recorded) and sdk-cashctrl (recorded_query).
    request = httpx.Request("GET", f"{BASE}/v1/x?token=SECRET&year=2024&q=")
    path = tmp_path / "x.json"
    _write(httpx.Response(200, json={}, request=request), path)
    assert recorded_query(load_fixture(path)) == {"token": REDACTED, "year": "2024", "q": ""}


def test_a_recorded_answer_is_served_at_another_url(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    # sdk-usda-psd and sdk-usda-esr each carried _mount_recorded_404 (row 41 b): the empty
    # 404 recorded for 1900 stands in for a year without data inside a range.
    request = httpx.Request("GET", f"{BASE}/v1/year/1900")
    path = tmp_path / "data" / "unknown_year.json"
    _write(httpx.Response(404, content=b"", request=request), path)
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


def test_response_from_fixture_carries_the_recorded_request(tmp_path: Path) -> None:
    # sdk-usda-psd, sdk-usda-esr, sdk-usda-gats (test_client.py) and sdk-cashctrl
    # (test_errors.py) each carried recorded(): a recorded answer for classify.
    request = httpx.Request("GET", f"{BASE}/v1/x?token=SECRET")
    path = tmp_path / "x.json"
    _write(httpx.Response(404, json={"error": "none"}, request=request), path)
    response = response_from_fixture(load_fixture(path))
    assert (response.status_code, response.json()) == (404, {"error": "none"})
    assert (response.request.method, str(response.request.url)) == (
        "GET",
        f"{BASE}/v1/x?token={REDACTED}",
    )
    error = error_from_response(response, source="example")
    assert isinstance(error, NotFoundError)
    assert str(error).startswith("404 from GET /v1/x")
