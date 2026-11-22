"""The collector inside the client, on while a task is recorded (ADR-0057).

While it is on, every ``AsyncClient`` of the running context hands it each answer it read
whole, in the order they arrived, sends each request once and neither reads nor fills the
cache. Off, the client behaves as it does without it.
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
import respx

from xippios.core.client import AsyncClient, ClientConfig, MemoryCache, RetryPolicy
from xippios.core.client._core import _collecting
from xippios.core.errors import TransportError, UpstreamError
from xippios.core.testing import send_once

BASE = "https://api.example.test"
OTHER = "https://files.example.test"


async def no_sleep(_: float) -> None:
    return None


def make_client(base_url: str = BASE, **changes: object) -> AsyncClient:
    """A source's client whose policy retries, as a source's does."""
    arguments: dict[str, object] = {
        "source": "example",
        "version": "1",
        "base_url": base_url,
        "retry": RetryPolicy(max_attempts=3, jitter=False),
    }
    arguments.update(changes)
    config = ClientConfig(**arguments)  # type: ignore[arg-type]
    return AsyncClient(config, sleep=no_sleep)


@pytest.mark.anyio
async def test_every_client_hands_each_answer_read_whole_in_the_order_it_arrived(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(f"{BASE}/v1/series").respond(200, json={"ids": ["a"]})
    respx_mock.get(f"{OTHER}/v2/meta").respond(200, json={"unit": "t"})
    respx_mock.post(f"{BASE}/v1/notes").respond(201, json={"id": 7})
    source, files = make_client(), make_client(OTHER)
    with _collecting() as collector:
        assert (await source.get_json("/v1/series")) == {"ids": ["a"]}
        assert (await files.get_answer("/v2/meta")).payload == {"unit": "t"}
        assert (await source.post_json("/v1/notes", json={"n": 1})) == {"id": 7}
    assert [(r.request.method, str(r.request.url)) for r in collector.answers] == [
        ("GET", f"{BASE}/v1/series"),
        ("GET", f"{OTHER}/v2/meta"),
        ("POST", f"{BASE}/v1/notes"),
    ]
    assert [r.json() for r in collector.answers] == [{"ids": ["a"]}, {"unit": "t"}, {"id": 7}]


@pytest.mark.anyio
async def test_a_request_is_sent_once_whatever_the_retry_policy_and_again_once_off(
    respx_mock: respx.MockRouter,
) -> None:
    client = make_client()
    route = respx_mock.get(f"{BASE}/v1/x")
    route.side_effect = [httpx.Response(503, text="busy"), httpx.Response(200, json={})]
    with _collecting() as collector:
        with pytest.raises(UpstreamError):
            await client.get("/v1/x")
        assert route.call_count == 1
        failing = respx_mock.get(f"{BASE}/v1/down").mock(side_effect=httpx.ConnectError)
        with pytest.raises(TransportError):
            await client.get("/v1/down")
        assert failing.call_count == 1, "a transport failure is not retried either"
    assert [r.status_code for r in collector.answers] == [503]
    route.side_effect = [httpx.Response(503, text="busy"), httpx.Response(200, json={})]
    route.reset()
    assert (await client.get("/v1/x")).status_code == 200
    assert route.call_count == 2, "off, the policy retries as configured"


@pytest.mark.anyio
async def test_the_cache_is_neither_read_nor_filled_while_collecting(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x")
    route.side_effect = [
        httpx.Response(200, json={"n": 1}),
        httpx.Response(200, json={"n": 2}),
        httpx.Response(200, json={"n": 3}),
    ]
    client = make_client(cache=MemoryCache())
    assert (await client.get_answer("/v1/x")).payload == {"n": 1}, "off: stored"
    with _collecting() as collector:
        assert (await client.get_answer("/v1/x")).payload == {"n": 2}, "not read"
        assert (await client.get_answer("/v1/x")).payload == {"n": 3}, "not read"
    assert route.call_count == 3
    assert len(collector.answers) == 2
    assert (await client.get_answer("/v1/x")).payload == {"n": 1}, "nor filled: it stands"
    assert route.call_count == 3


@pytest.mark.anyio
async def test_the_collector_is_off_again_after_a_block_that_raises(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = make_client()

    async def recorded() -> list[httpx.Response]:
        with _collecting() as collector:
            await client.get("/v1/x")
            raise LookupError(collector.answers)

    with pytest.raises(LookupError) as raised:
        await recorded()
    answers: list[httpx.Response] = raised.value.args[0]
    route.side_effect = [httpx.Response(503, text="busy"), httpx.Response(200, json={})]
    route.reset()
    assert (await client.get("/v1/x")).status_code == 200
    assert route.call_count == 2, "retried: the collector is off"
    assert len(answers) == 1, "nothing collected once off"


@pytest.mark.anyio
async def test_a_download_while_collecting_is_refused_before_it_is_sent(
    respx_mock: respx.MockRouter, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/files/qs.csv").respond(200, content=b"a,b\n")
    client = make_client()
    with _collecting() as collector:
        with pytest.raises(ValueError, match=r"GET /files/qs\.csv: a download") as refused:
            await client.download("/files/qs.csv", tmp_path / "qs.csv")
        assert "ADR-0057" in str(refused.value)
    assert route.call_count == 0
    assert collector.download == (1, "GET /files/qs.csv")
    assert list(tmp_path.iterdir()) == []
    downloaded = await client.download("/files/qs.csv", tmp_path / "qs.csv")
    assert downloaded.bytes == 4, "off, a download goes as before"


@pytest.mark.anyio
async def test_send_once_hands_its_answer_to_the_collector(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(404, json={"error": "none"})
    with _collecting() as collector:
        await send_once(make_client(), "/v1/x")
    assert [r.status_code for r in collector.answers] == [404]


@pytest.mark.anyio
async def test_a_token_request_inside_an_auth_flow_is_not_collected(
    respx_mock: respx.MockRouter,
) -> None:
    class Exchange(httpx.Auth):
        async def async_auth_flow(
            self, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            answer = yield httpx.Request("POST", f"{OTHER}/token")
            await answer.aread()
            request.headers["Authorization"] = f"Bearer {answer.json()['token']}"
            yield request

    token = respx_mock.post(f"{OTHER}/token").respond(200, json={"token": "t-1"})
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"n": 1})
    client = AsyncClient(
        ClientConfig(source="example", version="1", base_url=BASE), auth=Exchange()
    )
    with _collecting() as collector:
        await client.get("/v1/x")
    assert token.call_count == 1
    assert [str(r.request.url) for r in collector.answers] == [f"{BASE}/v1/x"]


@pytest.mark.anyio
async def test_the_collector_is_a_context_of_the_running_task(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.get(f"{BASE}/v1/a").respond(200, json={"a": 1})
    respx_mock.get(f"{BASE}/v1/b").respond(200, json={"b": 1})
    other = respx_mock.get(f"{BASE}/v1/other")
    other.side_effect = [httpx.Response(503, text="busy"), httpx.Response(200, json={})]
    client = make_client()
    started, ended = asyncio.Event(), asyncio.Event()
    leaked: list[asyncio.Task[httpx.Response]] = []

    async def outside() -> None:
        await started.wait()
        await client.get("/v1/other")

    async def later() -> httpx.Response:
        await ended.wait()
        return await client.get("/v1/a")

    async def recorded() -> list[httpx.Response]:
        with _collecting() as collector:
            started.set()
            # Requests the task starts at once are collected, in the order they arrived.
            await asyncio.gather(client.get("/v1/a"), client.get("/v1/b"))
            leaked.append(asyncio.create_task(later()))
        return collector.answers

    answers, _ = await asyncio.gather(recorded(), outside())
    assert sorted(str(r.request.url) for r in answers) == [f"{BASE}/v1/a", f"{BASE}/v1/b"]
    assert other.call_count == 2, "another task's request is retried: never collected"
    ended.set()
    await leaked[0]
    assert len(answers) == 2, "a task that outlives the recording hands nothing over"


def test_a_recording_inside_a_recording_is_refused() -> None:
    with _collecting(), pytest.raises(RuntimeError, match="inside another"), _collecting():
        pass
