import asyncio
import gzip
import time

import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    HeaderKeyAuth,
    MemoryCache,
    QueryKeyAuth,
    RateLimit,
    RetryPolicy,
    cache_key,
    decode_json,
)
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
from xippios.core.testing import REDACTED, sent_urls

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
    headers = route.calls.last.request.headers
    assert headers["user-agent"] == "xippios-example/1.2.3 (+https://github.com/xippios)"
    assert headers["x-family"] == "xippios"
    assert sent_urls(route) == [f"{BASE}/v1/x?a=1"]


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
    assert sleeper.calls == [0.1]  # the GET's retry; none for the POST


NON_IDEMPOTENT = ["POST", "PUT", "PATCH", "DELETE"]


@pytest.mark.anyio
@pytest.mark.parametrize("method", NON_IDEMPOTENT)
async def test_5xx_to_a_write_is_returned_after_one_attempt(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper, method: str
) -> None:
    # sdk-cashctrl: a booking answered 503 after it was applied must not be repeated.
    route = respx_mock.route(method=method, url=f"{BASE}/v1/x").respond(503, text="busy")
    client = AsyncClient(config, sleep=sleeper)
    response = await client.request(method, "/v1/x", json={"a": 1}, raise_on_error=False)
    assert response.status_code == 503
    assert route.call_count == 1
    with pytest.raises(UpstreamError):
        await client.request(method, "/v1/x", json={"a": 1})
    assert route.call_count == 2
    assert sleeper.calls == []


@pytest.mark.anyio
async def test_a_write_is_retried_when_the_policy_allows(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").mock(
        side_effect=[
            httpx.Response(503),
            httpx.ConnectError("nope"),
            httpx.Response(200, json={"id": 7}),
        ]
    )
    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        retry=RetryPolicy(backoff_base=0.1, jitter=False, retry_non_idempotent=True),
    )
    client = AsyncClient(config, sleep=sleeper)
    response = await client.request("POST", "/v1/x", json={"a": 1})
    assert response.json() == {"id": 7}
    assert route.call_count == 3  # a 5xx and a transport failure, each retried
    assert sleeper.calls == [0.1, 0.2]


@pytest.mark.anyio
async def test_429_to_a_write_is_retried(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200, json={"id": 7}),
        ]
    )
    client = AsyncClient(config, sleep=sleeper)
    response = await client.request("POST", "/v1/x", json={"a": 1})
    assert response.json() == {"id": 7}
    assert route.call_count == 2
    assert sleeper.calls == [1.0]


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_5xx_to_an_idempotent_method_is_still_retried(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper, method: str
) -> None:
    route = respx_mock.route(method=method, url=f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200)]
    )
    client = AsyncClient(config, sleep=sleeper)
    response = await client.request(method, "/v1/x")
    assert response.status_code == 200
    assert route.call_count == 2
    assert sleeper.calls == [0.1]


@pytest.mark.anyio
async def test_retry_transport_errors_off_wins_over_retry_non_idempotent(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").mock(side_effect=httpx.ConnectError("nope"))
    policy = RetryPolicy(retry_transport_errors=False, retry_non_idempotent=True)
    config = ClientConfig(source="example", version="1", base_url=BASE, retry=policy)
    client = AsyncClient(config, sleep=sleeper)
    with pytest.raises(TransportError):
        await client.request("POST", "/v1/x", json={"a": 1})
    assert route.call_count == 1
    assert sleeper.calls == []


@pytest.mark.anyio
async def test_a_body_is_sent_form_encoded_or_as_json(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # sdk-cashctrl: CashCtrl's writes take form fields, not JSON.
    route = respx_mock.post(f"{BASE}/v1/x").respond(200, json={"success": True})
    client = AsyncClient(config)
    await client.request("POST", "/v1/x", data={"a": 1, "b": "x y/é"})
    assert route.calls.last.request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert route.calls.last.request.content == b"a=1&b=x+y%2F%C3%A9"
    await client.request("POST", "/v1/x", json={"a": 1})
    assert route.calls.last.request.headers["content-type"] == "application/json"
    assert route.calls.last.request.content == b'{"a":1}'


@pytest.mark.anyio
async def test_json_and_data_together_are_refused_before_sending(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config)
    with pytest.raises(ValueError, match="json= or data=, not both"):
        await client.request("POST", "/v1/x", json={"a": 1}, data={"a": 1})
    assert not route.called


@pytest.mark.anyio
@pytest.mark.rate_limited
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
async def test_a_cache_hit_carries_the_time_its_entry_was_stored(
    respx_mock: respx.MockRouter,
) -> None:
    # sdk-usda-psd: a task stamped a hit with the current time as retrieved_at.
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"n": 1})
    cache = MemoryCache(ttl=None)
    client = AsyncClient(ClientConfig(source="example", version="1", base_url=BASE, cache=cache))
    before = time.time()
    first = await client.get("/v1/x")
    after = time.time()
    assert "xippios_cache_stored_at" not in first.extensions
    hit = await client.get("/v1/x")
    stored = cache.get(cache_key("GET", httpx.URL(f"{BASE}/v1/x")))
    assert stored is not None
    assert hit.extensions["xippios_cache"] == "hit"
    assert hit.extensions["xippios_cache_stored_at"] == stored.stored_at
    assert before <= stored.stored_at <= after
    assert decode_json(hit, source="example") == {"n": 1}  # get, then decode_json


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

    cache = MemoryCache()
    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        cache=cache,
        cache_filter=only_reference,
    )
    client = AsyncClient(config)
    for _ in range(2):
        await client.get("/v1/reference", params={"lang": "en"})
        await client.get("/v1/data", params={"year": 2024})
    assert reference.call_count == 1
    assert data.call_count == 2
    assert len(cache) == 1  # the filtered-out GET was never stored
    assert cache.get(cache_key("GET", httpx.URL(f"{BASE}/v1/data?year=2024"))) is None
    hit = await client.get("/v1/reference", params={"lang": "en"})
    assert hit.extensions["xippios_cache"] == "hit"
    assert seen[0].url.params["lang"] == "en"
    assert seen[1].url.params["year"] == "2024"
    await client.request("POST", "/v1/reference", json={})  # never cached, filter not asked
    assert all(request.method == "GET" for request in seen)
    assert len(cache) == 1


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


def test_decode_json_refuses_a_body_that_is_not_json() -> None:
    request = httpx.Request("GET", f"{BASE}/v1/x?key=SECRET")
    response = httpx.Response(200, text="<html>oops</html>", request=request)
    with pytest.raises(ValidationError) as info:
        decode_json(response, source="example")
    assert info.value.message == "example: response from /v1/x is not JSON"
    assert info.value.raw == "<html>oops</html>"
    assert info.value.source == "example"
    assert isinstance(info.value.__cause__, ValueError)
    with pytest.raises(ValidationError, match=r"^response from /v1/data is not JSON$"):
        decode_json(response, path="/v1/data")
    with pytest.raises(ValidationError, match=r"^response is not JSON$"):
        decode_json(httpx.Response(200, text="oops"))


def test_one_pool_per_event_loop(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config)

    async def use() -> httpx.AsyncClient:
        await client.get("/v1/x")
        return client._pool()

    first = asyncio.run(use())  # held alive, so the second pool cannot reuse its address
    second = asyncio.run(use())
    assert first is not second


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


# -- classify shapes retries (ADR-0015) ---------------------------------------------------


class CountingClassify:
    """A source's classify that maps by status and counts its calls per status."""

    def __init__(self, mapping: dict[int, XippiosError]) -> None:
        self.mapping = mapping
        self.calls: list[int] = []

    def __call__(self, response: httpx.Response) -> XippiosError | None:
        self.calls.append(response.status_code)
        return self.mapping.get(response.status_code)


def _classified(classify: CountingClassify, *, max_attempts: int = 4) -> ClientConfig:
    policy = RetryPolicy(max_attempts=max_attempts, backoff_base=0.1, jitter=False)
    return ClientConfig(
        source="example", version="1", base_url=BASE, retry=policy, classify=classify
    )


@pytest.mark.anyio
async def test_a_429_that_classify_gives_a_long_wait_is_raised_after_one_attempt(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    # sdk-usda-psd: api.data.gov's spent quota is a 429 without Retry-After; the core loop
    # fired three more requests into it before classify's one-hour wait was ever read.
    route = respx_mock.get(f"{BASE}/v1/x").respond(429, json={"error": "OVER_RATE_LIMIT"})
    spent = RateLimitError("quota spent", retry_after=3600.0, source="example")
    classify = CountingClassify({429: spent})
    client = AsyncClient(_classified(classify), sleep=sleeper)
    with pytest.raises(RateLimitError) as info:
        await client.get("/v1/x")
    assert info.value is spent
    assert info.value.retry_after == 3600.0
    assert route.call_count == 1
    assert sleeper.calls == []
    assert classify.calls == [429]


@pytest.mark.anyio
async def test_the_retry_after_from_classify_sets_the_wait(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"n": 1})]
    )
    classify = CountingClassify({429: RateLimitError("slow down", retry_after=2.0)})
    client = AsyncClient(_classified(classify), sleep=sleeper)
    assert await client.get_json("/v1/x") == {"n": 1}
    assert route.call_count == 2
    assert sleeper.calls == [2.0]


@pytest.mark.anyio
async def test_a_rate_limit_error_without_retry_after_keeps_the_header(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(429, headers={"Retry-After": "3"})
    classify = CountingClassify({429: RateLimitError("slow down")})
    client = AsyncClient(_classified(classify, max_attempts=3), sleep=sleeper)
    with pytest.raises(RateLimitError, match="slow down"):
        await client.get("/v1/x")
    assert route.call_count == 3
    assert sleeper.calls == [3.0, 3.0]


@pytest.mark.anyio
async def test_a_5xx_that_classify_maps_to_an_upstream_error_is_still_retried(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    # sdk-cashctrl maps every 5xx to UpstreamError, to scrub the host from its message.
    route = respx_mock.get(f"{BASE}/v1/x").respond(503, text="busy")
    busy = UpstreamError("busy", status=503, body="", source="example")
    classify = CountingClassify({503: busy})
    client = AsyncClient(_classified(classify, max_attempts=3), sleep=sleeper)
    with pytest.raises(UpstreamError, match="busy") as info:
        await client.get("/v1/x")
    assert info.value is busy
    assert route.call_count == 3
    assert sleeper.calls == [0.1, 0.2]
    assert classify.calls == [503, 503, 503]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (503, AuthError("key disabled", status=503)),
        (503, InvalidRequestError("query too large")),
        (502, NotFoundError("no such series")),
        (429, UpstreamError("not a rate limit", status=429, body="")),
    ],
)
async def test_another_error_from_classify_stops_the_retries(
    respx_mock: respx.MockRouter, sleeper: Sleeper, status: int, error: XippiosError
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(status)
    classify = CountingClassify({status: error})
    client = AsyncClient(_classified(classify), sleep=sleeper)
    with pytest.raises(type(error)) as info:
        await client.get("/v1/x")
    assert info.value is error
    assert route.call_count == 1
    assert sleeper.calls == []
    assert classify.calls == [status]


@pytest.mark.anyio
async def test_classify_returning_none_keeps_the_retry(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json={})]
    )
    classify = CountingClassify({})
    client = AsyncClient(_classified(classify), sleep=sleeper)
    await client.get("/v1/x")
    assert route.call_count == 3
    assert sleeper.calls == [0.1, 0.2]
    assert classify.calls == [503, 429, 200]  # once per attempt, the final one included


@pytest.mark.anyio
async def test_classify_is_called_at_most_once_per_attempt(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(503)
    classify = CountingClassify({})
    client = AsyncClient(_classified(classify, max_attempts=3), sleep=sleeper)
    with pytest.raises(UpstreamError):
        await client.get("/v1/x")
    assert route.call_count == 3
    assert classify.calls == [503, 503, 503]  # the last attempt's answer is not asked twice


@pytest.mark.anyio
async def test_a_raw_request_stops_retrying_and_returns_the_response(
    respx_mock: respx.MockRouter, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(429)
    classify = CountingClassify({429: RateLimitError("quota spent", retry_after=3600.0)})
    client = AsyncClient(_classified(classify), sleep=sleeper)
    response = await client.request("GET", "/v1/x", raise_on_error=False)
    assert response.status_code == 429
    assert route.call_count == 1
    assert sleeper.calls == []
    assert classify.calls == [429]


# -- auth per request (ADR-0015) ----------------------------------------------------------

KEY_ENV = "EXAMPLE_API_KEY"  # pragma: allowlist secret (a variable name)


@pytest.mark.anyio
async def test_auth_none_sends_a_keyed_client_s_request_without_the_key(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    # sdk-comtrade: the public reference files on the same host needed a second client.
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=QueryKeyAuth("key", KEY_ENV))
    await client.get("/v1/x", params={"a": 1})
    await client.get("/v1/x", params={"a": 1}, auth=None)
    await client.get_json("/v1/x", params={"a": 1}, auth=None)
    await client.request("GET", "/v1/x", params={"a": 1}, auth=None)
    await client.get("/v1/x", params={"a": 1})
    assert sent_urls(route) == [
        f"{BASE}/v1/x?a=1&key={REDACTED}",
        f"{BASE}/v1/x?a=1",
        f"{BASE}/v1/x?a=1",
        f"{BASE}/v1/x?a=1",
        f"{BASE}/v1/x?a=1&key={REDACTED}",
    ]


@pytest.mark.anyio
async def test_another_auth_replaces_the_client_s_for_one_request(
    respx_mock: respx.MockRouter, config: ClientConfig
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", KEY_ENV))
    await client.get("/v1/x", auth=httpx.BasicAuth("user", "pw"))
    other = route.calls.last.request.headers
    assert other["authorization"].startswith("Basic ")
    assert "x-api-key" not in other
    await client.get("/v1/x")
    default = route.calls.last.request.headers
    assert "x-api-key" in default
    assert "authorization" not in default


@pytest.mark.anyio
async def test_auth_none_holds_for_every_retry(
    respx_mock: respx.MockRouter, config: ClientConfig, sleeper: Sleeper
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={})]
    )
    client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", KEY_ENV), sleep=sleeper)
    await client.get("/v1/x", auth=None)
    assert route.call_count == 2
    assert not any("x-api-key" in call.request.headers for call in route.calls)


@pytest.mark.anyio
async def test_a_call_with_its_own_auth_bypasses_the_cache(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[
            httpx.Response(200, json={"who": "client"}),
            httpx.Response(200, json={"who": "other"}),
        ]
    )
    cache = MemoryCache()
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=cache)
    client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", KEY_ENV))
    assert await client.get_json("/v1/x") == {"who": "client"}
    other = await client.get_json("/v1/x", auth=httpx.BasicAuth("user", "pw"))
    assert other == {"who": "other"}  # reached the transport, not the keyed entry
    assert route.call_count == 2
    assert route.calls.last.request.headers["authorization"].startswith("Basic ")
    assert len(cache) == 1
    hit = await client.get("/v1/x")
    assert hit.extensions["xippios_cache"] == "hit"
    assert hit.json() == {"who": "client"}  # the other auth's answer was not stored


@pytest.mark.anyio
async def test_any_explicit_auth_form_bypasses_the_cache(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=MemoryCache())
    client = AsyncClient(config)
    await client.get("/v1/x")
    basic = ("user", "pw")  # httpx's tuple form, outside the annotation
    await client.get("/v1/x", auth=basic)  # type: ignore[arg-type]
    assert route.call_count == 2
    assert route.calls.last.request.headers["authorization"].startswith("Basic ")


@pytest.mark.anyio
async def test_auth_none_and_the_default_share_the_cache(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(f"{BASE}/v1/reference").respond(200, json={"codes": [1]})
    config = ClientConfig(source="example", version="1", base_url=BASE, cache=MemoryCache())
    client = AsyncClient(config, auth=QueryKeyAuth("key", KEY_ENV))
    await client.get("/v1/reference", auth=None)
    hit = await client.get("/v1/reference")
    assert hit.extensions["xippios_cache"] == "hit"
    assert sent_urls(route) == [f"{BASE}/v1/reference"]
