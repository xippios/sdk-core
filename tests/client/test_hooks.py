"""ClientConfig.before_request and ClientConfig.observe: where they run, and how often.

The placement is ADR-0015's: the pre-request hook once per call, after the cache lookup
and before the rate limiter; the observer on every response from the wire, before
``classify`` and the retry decision.
"""

import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    Client,
    ClientConfig,
    HeaderKeyAuth,
    MemoryCache,
    RateLimit,
    RetryPolicy,
)
from xippios.core.errors import NotFoundError, RateLimitError, TransportError, XippiosError

BASE = "https://api.example.test"


class Events:
    """Records hook calls, sleeps and sends in order, as plain strings."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def sleep(self, seconds: float) -> None:
        self.seen.append(f"sleep {seconds:.0f}")


def make(**changes: object) -> ClientConfig:
    arguments: dict[str, object] = {
        "source": "example",
        "version": "1",
        "base_url": BASE,
        "retry": RetryPolicy(max_attempts=3, backoff_base=0.1, jitter=False),
    }
    arguments.update(changes)
    return ClientConfig(**arguments)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_before_request_runs_once_per_call_not_per_retry(
    respx_mock: respx.MockRouter,
) -> None:
    events = Events()
    built: list[httpx.Request] = []

    def before(request: httpx.Request) -> None:
        built.append(request)
        events.seen.append(f"before {request.method} {request.url.path}")

    def answer(request: httpx.Request) -> httpx.Response:
        events.seen.append("sent")
        return httpx.Response(503) if len(events.seen) < 3 else httpx.Response(200, json={})

    respx_mock.post(f"{BASE}/v1/x").mock(side_effect=answer)
    config = make(before_request=before, retry=RetryPolicy(retry_non_idempotent=True))
    client = AsyncClient(
        config, auth=HeaderKeyAuth("X-Api-Key", "EXAMPLE_API_KEY"), sleep=events.sleep
    )
    await client.request(
        "POST", "/v1/x", params={"a": 1}, json={"b": 2}, headers={"X-Request": "one"}
    )
    assert events.seen[0] == "before POST /v1/x"
    assert events.seen.count("before POST /v1/x") == 1
    assert events.seen.count("sent") == 2
    (request,) = built
    assert request.url.params["a"] == "1"
    assert request.content == b'{"b":2}'
    assert request.headers["x-request"] == "one"
    assert "x-api-key" not in request.headers  # auth is applied later, when it is sent


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_before_request_runs_before_the_rate_limiter(respx_mock: respx.MockRouter) -> None:
    events = Events()

    def answer(request: httpx.Request) -> httpx.Response:
        events.seen.append("sent")
        return httpx.Response(200, json={})

    respx_mock.get(f"{BASE}/v1/x").mock(side_effect=answer)
    config = make(
        before_request=lambda request: events.seen.append("before"),
        rate_limit=RateLimit(per_minute=60, burst=1),
    )
    client = AsyncClient(config, sleep=events.sleep)
    await client.get("/v1/x")
    await client.get("/v1/x")
    assert events.seen == ["before", "sent", "before", "sleep 1", "sent"]


@pytest.mark.anyio
async def test_an_async_before_request_is_awaited(respx_mock: respx.MockRouter) -> None:
    events = Events()

    async def before(request: httpx.Request) -> None:
        await events.sleep(2.0)
        events.seen.append("before")

    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(make(before_request=before))
    await client.get("/v1/x")
    assert events.seen == ["sleep 2", "before"]
    assert route.call_count == 1


@pytest.mark.anyio
async def test_an_error_from_before_request_sends_nothing(respx_mock: respx.MockRouter) -> None:
    async def refuse(request: httpx.Request) -> None:
        raise RateLimitError("nothing was sent", retry_after=600.0, source="example")

    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(make(before_request=refuse))
    with pytest.raises(RateLimitError, match="nothing was sent") as info:
        await client.get("/v1/x")
    assert info.value.retry_after == 600.0
    assert not route.called


@pytest.mark.anyio
async def test_a_cache_hit_reaches_neither_hook(respx_mock: respx.MockRouter) -> None:
    events = Events()
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={"n": 1})
    config = make(
        cache=MemoryCache(),
        before_request=lambda request: events.seen.append("before"),
        observe=lambda response: events.seen.append(f"observe {response.status_code}"),
    )
    client = AsyncClient(config)
    await client.get("/v1/x")
    hit = await client.get("/v1/x")
    raw = await client.request("GET", "/v1/x", raise_on_error=False)
    assert hit.extensions["xippios_cache"] == "hit"
    assert raw.extensions["xippios_cache"] == "hit"
    assert route.call_count == 1
    assert events.seen == ["before", "observe 200"]


@pytest.mark.anyio
async def test_observe_sees_every_attempt_before_classify(respx_mock: respx.MockRouter) -> None:
    events = Events()

    def classify(response: httpx.Response) -> XippiosError | None:
        events.seen.append(f"classify {response.status_code}")
        return None

    respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(404)]
    )
    config = make(
        observe=lambda response: events.seen.append(f"observe {response.status_code}"),
        classify=classify,
    )
    client = AsyncClient(config, sleep=events.sleep)
    with pytest.raises(NotFoundError):
        await client.get("/v1/x")
    assert events.seen == [
        "observe 503",
        "classify 503",
        "sleep 0",
        "observe 502",
        "classify 502",
        "sleep 0",
        "observe 404",
        "classify 404",
    ]


@pytest.mark.anyio
async def test_observe_sees_raw_responses_too(respx_mock: respx.MockRouter) -> None:
    # The recorder asks for raw responses; ADR-0010 wants the quota observed on them too.
    seen: list[int] = []
    respx_mock.get(f"{BASE}/v1/x").respond(500, json={})
    client = AsyncClient(
        make(
            observe=lambda response: seen.append(response.status_code),
            retry=RetryPolicy(max_attempts=1),
        )
    )
    response = await client.request("GET", "/v1/x", raise_on_error=False)
    assert response.status_code == 500
    assert seen == [500]


@pytest.mark.anyio
async def test_an_error_from_observe_propagates(respx_mock: respx.MockRouter) -> None:
    def broken(response: httpx.Response) -> None:
        raise LookupError("observer bug")

    route = respx_mock.get(f"{BASE}/v1/x").respond(503)
    client = AsyncClient(make(observe=broken))
    with pytest.raises(LookupError, match="observer bug"):
        await client.get("/v1/x")
    assert route.call_count == 1  # raised before the retry decision


@pytest.mark.anyio
async def test_observe_is_not_called_without_a_response(respx_mock: respx.MockRouter) -> None:
    seen: list[int] = []
    respx_mock.get(f"{BASE}/v1/x").mock(side_effect=httpx.ConnectError("nope"))
    config = make(
        observe=lambda response: seen.append(response.status_code),
        retry=RetryPolicy(max_attempts=1),
    )
    with pytest.raises(TransportError):
        await AsyncClient(config).get("/v1/x")
    assert seen == []


def test_the_sync_facade_runs_both_hooks(respx_mock: respx.MockRouter) -> None:
    events = Events()
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    config = make(
        before_request=lambda request: events.seen.append("before"),
        observe=lambda response: events.seen.append("observe"),
    )
    with Client(config) as client:
        client.get_json("/v1/x")
    assert events.seen == ["before", "observe"]
