import asyncio
import gzip

import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    CachedResponse,
    Client,
    ClientConfig,
    MemoryCache,
    RateLimit,
    RetryPolicy,
    cache_key,
)
from xippios.core.client._core import _from_cache
from xippios.core.errors import (
    AuthError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
    ValidationError,
    XippiosError,
)

BASE = "https://api.example.test"


class Sleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.fixture
def sleeper() -> Sleeper:
    return Sleeper()


@pytest.fixture
def config() -> ClientConfig:
    return ClientConfig(
        source="example",
        version="1.2.3",
        base_url=BASE,
        retry=RetryPolicy(max_attempts=3, backoff_base=0.1, backoff_max=5.0, jitter=False),
        headers={"X-Family": "xippios"},
    )


@pytest.mark.anyio
async def test_headers_url_and_params(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={"ok": True})
    async with AsyncClient(config) as client:
        assert await client.get_json("/v1/x", params={"a": 1}) == {"ok": True}
    request = route.calls.last.request
    assert request.headers["user-agent"] == "xippios-example/1.2.3 (+https://github.com/xippios)"
    assert request.headers["x-family"] == "xippios"
    assert str(request.url) == f"{BASE}/v1/x?a=1"


@pytest.mark.anyio
async def test_auth_is_applied(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=httpx.BasicAuth("user", "pw"))
    await client.get("/v1/x")
    assert route.calls.last.request.headers["authorization"].startswith("Basic ")


@pytest.mark.anyio
async def test_retries_5xx_then_succeeds(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"n": 1})]
    )
    client = AsyncClient(config, sleep=sleeper)
    assert await client.get_json("/v1/x") == {"n": 1}
    assert route.call_count == 2
    assert sleeper.calls == [0.1]


@pytest.mark.anyio
async def test_gives_up_after_max_attempts(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(500, text="down")
    client = AsyncClient(config, sleep=sleeper)
    with pytest.raises(UpstreamError) as info:
        await client.get("/v1/x")
    assert info.value.status == 500
    assert info.value.body == "down"
    assert route.call_count == 3
    assert sleeper.calls == [0.1, 0.2]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "cls"), [(400, UpstreamError), (401, AuthError), (404, NotFoundError)]
)
async def test_other_4xx_never_retried(
    respx_mock: respx.MockRouter,
    config: ClientConfig,
    sleeper: Sleeper,
    status: int,
    cls: type[Exception],
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(status)
    client = AsyncClient(config, sleep=sleeper)
    with pytest.raises(cls):
        await client.get("/v1/x")
    assert route.call_count == 1
    assert sleeper.calls == []


@pytest.mark.anyio
async def test_429_honours_retry_after(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(429, headers={"Retry-After": "2"})
    client = AsyncClient(config, sleep=sleeper)
    with pytest.raises(RateLimitError) as info:
        await client.get("/v1/x")
    assert info.value.retry_after == 2.0
    assert route.call_count == 3
    assert sleeper.calls == [2.0, 2.0]


@pytest.mark.anyio
async def test_429_with_long_retry_after_is_raised_immediately(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(429, headers={"Retry-After": "600"})
    client = AsyncClient(config, sleep=sleeper)
    with pytest.raises(RateLimitError) as info:
        await client.get("/v1/x")
    assert info.value.retry_after == 600.0
    assert route.call_count == 1
    assert sleeper.calls == []


@pytest.mark.anyio
async def test_transport_error_retried_for_get_only(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    get = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.ConnectError("nope"), httpx.Response(200, json={})]
    )
    post = respx_mock.post(f"{BASE}/v1/x").mock(side_effect=httpx.ConnectError("nope"))
    client = AsyncClient(config, sleep=sleeper)
    await client.get("/v1/x")
    assert get.call_count == 2
    with pytest.raises(TransportError, match="ConnectError"):
        await client.request("POST", "/v1/x", json={"a": 1})
    assert post.call_count == 1


@pytest.mark.anyio
async def test_rate_limiter_waits_between_calls(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    limited = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        rate_limit=RateLimit(per_minute=60, burst=1),
    )
    client = AsyncClient(limited, sleep=sleeper)
    await client.get("/v1/x")
    await client.get("/v1/x")
    assert len(sleeper.calls) == 1
    assert 0.9 <= sleeper.calls[0] <= 1.0


@pytest.mark.anyio
async def test_get_responses_are_cached(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={"n": 1})
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=MemoryCache())
    client = AsyncClient(config)
    first = await client.get("/v1/x", params={"a": 1})
    second = await client.get("/v1/x", params={"a": 1})
    assert route.call_count == 1
    assert second.json() == {"n": 1}
    assert second.extensions.get("xippios_cache") == "hit"
    assert "xippios_cache" not in first.extensions
    await client.get("/v1/x", params={"a": 2})
    assert route.call_count == 2


@pytest.mark.anyio
async def test_gzip_answer_replays_from_the_cache(respx_mock: respx.MockRouter) -> None:
    # Found by sdk-usda-psd PR 3: the cache kept the decoded body with content-encoding,
    # so the replay tried to gunzip plain JSON and raised httpx.DecodingError.
    body = gzip.compress(b'{"a": 1}')
    route = respx_mock.get(f"{BASE}/v1/x").respond(
        200,
        content=body,
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    cache = MemoryCache()
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=cache)
    client = AsyncClient(config)
    first = await client.get("/v1/x")
    assert first.json() == {"a": 1}
    second = await client.get("/v1/x")
    assert route.call_count == 1
    assert second.extensions["xippios_cache"] == "hit"
    assert second.json() == first.json()
    stored = cache.get(cache_key("GET", httpx.URL(f"{BASE}/v1/x")))
    assert stored is not None
    names = {name.lower() for name, _ in stored.headers}
    assert "content-type" in names
    assert not names & {"content-encoding", "content-length"}


def test_from_cache_strips_wire_headers_of_an_old_entry() -> None:
    # A persistent backend may still hold entries stored by 0.1.0, wire headers and all.
    entry = CachedResponse(
        status=200,
        headers=(
            ("content-type", "application/json"),
            ("Content-Encoding", "gzip"),
            ("content-length", "99"),
            ("transfer-encoding", "chunked"),
            ("connection", "keep-alive"),
        ),
        content=b'{"a": 1}',
        stored_at=0.0,
    )
    response = _from_cache(entry, httpx.Request("GET", f"{BASE}/v1/x"))
    assert response.json() == {"a": 1}
    assert response.headers.get("content-type") == "application/json"
    for name in ("content-encoding", "transfer-encoding", "connection"):
        assert name not in response.headers
    assert response.headers.get("content-length") == "8"  # httpx's own, for the decoded body
    assert response.extensions["xippios_cache"] == "hit"


@pytest.mark.anyio
async def test_cache_filter_limits_caching_to_chosen_requests(
    respx_mock: respx.MockRouter,
) -> None:
    reference = respx_mock.get(f"{BASE}/v1/reference").respond(200, json={"codes": [1]})
    data = respx_mock.get(f"{BASE}/v1/data").respond(200, json={"rows": []})
    respx_mock.post(f"{BASE}/v1/reference").respond(200, json={})
    seen: list[httpx.Request] = []

    def only_reference(request: httpx.Request) -> bool:
        seen.append(request)
        return request.url.path == "/v1/reference"

    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        cache=MemoryCache(),
        cache_filter=only_reference,
    )
    client = AsyncClient(config)
    for _ in range(2):
        await client.get("/v1/reference", params={"lang": "en"})
        await client.get("/v1/data", params={"year": 2024})
    assert reference.call_count == 1
    assert data.call_count == 2
    hit = await client.get("/v1/reference", params={"lang": "en"})
    assert hit.extensions["xippios_cache"] == "hit"
    assert seen[0].url.params["lang"] == "en"
    assert seen[1].url.params["year"] == "2024"
    await client.request("POST", "/v1/reference", json={})  # never cached, filter not asked
    assert all(request.method == "GET" for request in seen)


@pytest.mark.anyio
async def test_non_200_and_non_get_are_not_cached(respx_mock: respx.MockRouter) -> None:
    get = respx_mock.get(f"{BASE}/v1/x").respond(404)
    post = respx_mock.post(f"{BASE}/v1/x").respond(200, json={})
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=MemoryCache())
    client = AsyncClient(config)
    for _ in range(2):
        with pytest.raises(NotFoundError):
            await client.get("/v1/x")
        await client.request("POST", "/v1/x", json={})
    assert get.call_count == 2
    assert post.call_count == 2


@pytest.mark.anyio
async def test_get_json_rejects_non_json(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, text="<html>oops</html>")
    client = AsyncClient(config)
    with pytest.raises(ValidationError) as info:
        await client.get_json("/v1/x")
    assert info.value.raw == "<html>oops</html>"


def test_one_pool_per_event_loop(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config)

    async def use() -> httpx.AsyncClient:
        await client.get("/v1/x")
        return client._pool()

    first = asyncio.run(use())  # held alive, so the second pool cannot reuse its address
    second = asyncio.run(use())
    assert first is not second


def test_sync_client_facade(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={"sync": True})
    with Client(config) as client:
        assert client.config is config
        assert client.get_json("/v1/x") == {"sync": True}
        assert client.get("/v1/x").status_code == 200
        assert client.request("GET", "/v1/x").status_code == 200
    assert route.call_count == 3


def test_sync_client_raises_taxonomy_errors(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(403)
    with pytest.raises(AuthError), Client(config) as client:
        client.get("/v1/x")


def _classify(response: httpx.Response) -> XippiosError | None:
    body = (
        response.json()
        if response.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    if response.status_code == 200 and body.get("error") == "no rows":
        return NotFoundError("upstream says no rows", source="example")
    if response.status_code == 413:
        return InvalidRequestError("too big", source="example")
    return None


@pytest.mark.anyio
async def test_classify_sees_every_response_first(respx_mock: respx.MockRouter) -> None:
    config = ClientConfig(
        source="example", version="1", base_url=BASE,
        retry=RetryPolicy(max_attempts=1), classify=_classify,
    )  # fmt: skip
    client = AsyncClient(config)
    respx_mock.get(f"{BASE}/v1/empty").respond(200, json={"error": "no rows"})
    respx_mock.get(f"{BASE}/v1/big").respond(413, json={"error": "exceeds limit"})
    respx_mock.get(f"{BASE}/v1/other").respond(404)
    respx_mock.get(f"{BASE}/v1/ok").respond(200, json={"rows": 1})
    with pytest.raises(NotFoundError, match="no rows"):
        await client.get("/v1/empty")
    with pytest.raises(InvalidRequestError, match="too big"):
        await client.get("/v1/big")
    with pytest.raises(NotFoundError, match="404"):
        await client.get("/v1/other")
    assert (await client.get_json("/v1/ok")) == {"rows": 1}
    raw = await client.request("GET", "/v1/empty", raise_on_error=False)
    assert raw.status_code == 200
