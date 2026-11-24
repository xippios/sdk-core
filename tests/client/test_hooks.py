"""ClientConfig.before_request and ClientConfig.observe: where they run, and how often.

The placement is ADR-0037's: the pre-request hook once per call, after the cache lookup
and before the rate limiter; the observer on every response from the wire, before
``classify`` and the retry decision.
"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    KeyAuth,
    MemoryCache,
    QuotaPolicy,
    RateLimit,
    RetryPolicy,
)
from xippios.core.errors import NotFoundError, RateLimitError, XippiosError
from xippios.core.testing import send_once

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

    # A read, since a write is never retried; its body shows the request built is the call's.
    respx_mock.get(f"{BASE}/v1/x").mock(side_effect=answer)
    config = make(before_request=before)
    client = AsyncClient(
        config,
        auth=KeyAuth("EXAMPLE_API_KEY", location="header", name="X-Api-Key"),
        sleep=events.sleep,
    )
    await client.request(
        "GET", "/v1/x", params={"a": 1}, json={"b": 2}, headers={"X-Request": "one"}
    )
    assert events.seen[0] == "before GET /v1/x"
    assert events.seen.count("before GET /v1/x") == 1
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
    await client.get_answer("/v1/x")
    hit = await client.get("/v1/x")
    requested = await client.request("GET", "/v1/x")
    assert hit.extensions["xippios_cache"] == "hit"
    assert requested.extensions["xippios_cache"] == "hit"
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
async def test_a_classify_words_a_spent_quota_from_the_policy_s_public_snapshot(
    respx_mock: respx.MockRouter,
) -> None:
    # A package that holds one policy for the sources behind one key words its own refusal of a
    # 429 from snapshot() and the clock it gave the policy, and needs no private member of the
    # policy (ADR-0065, decision 2): observe has read the answer before classify runs.
    now = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)
    policy = QuotaPolicy(window=3600.0, source="example", clock=lambda: now)

    def classify(response: httpx.Response) -> XippiosError | None:
        if response.status_code != 429:
            return None
        snapshot = policy.snapshot()
        assert snapshot is not None
        assert snapshot.resumes_at is not None
        wait = (snapshot.resumes_at - now).total_seconds()
        return RateLimitError(
            f"the example quota is spent until {snapshot.resumes_at:%H:%M} UTC, in {wait:.0f} s",
            retry_after=wait,
            source="example",
        )

    respx_mock.get(f"{BASE}/v1/x").respond(429, headers={"Retry-After": "120"})
    config = policy.install(make(classify=classify, retry=RetryPolicy(max_attempts=1)))
    with pytest.raises(RateLimitError) as info:
        await AsyncClient(config).get("/v1/x")
    assert info.value.message == "the example quota is spent until 08:02 UTC, in 120 s"
    assert info.value.retry_after == 120.0


@pytest.mark.anyio
async def test_observe_sees_a_recording_s_answer_too(respx_mock: respx.MockRouter) -> None:
    # The recorder takes an answer whatever its status; ADR-0033 wants the quota observed
    # on it too. The client's public calls return no such answer (#473, part 2).
    seen: list[int] = []
    respx_mock.get(f"{BASE}/v1/x").respond(500, json={})
    client = AsyncClient(
        make(
            observe=lambda response: seen.append(response.status_code),
            retry=RetryPolicy(max_attempts=1),
        )
    )
    response = await send_once(client, "/v1/x")
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
