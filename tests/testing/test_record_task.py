"""The recording of every exchange of a task, ``record_task`` (ADR-0057).

The tasks below make their calls through clients of their own module, bound by name as a
source binds its client: ``record_task`` is handed the task and none of them.
"""

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from xippios.core import sync
from xippios.core.client import AsyncClient, ClientConfig, MemoryCache, RetryPolicy
from xippios.core.errors import NotFoundError, UpstreamError, ValidationError
from xippios.core.testing import (
    REDACTED,
    Fixture,
    ReplayFixture,
    Scrub,
    fixture_path,
    load_fixture,
    record_task,
    record_task_sync,
)

BASE = "https://api.example.test"


async def no_sleep(_: float) -> None:
    return None


def _config(**changes: Any) -> ClientConfig:
    retry = RetryPolicy(max_attempts=3, jitter=False)
    return ClientConfig(source="example", version="1", base_url=BASE, retry=retry, **changes)


CLIENT = AsyncClient(_config(), sleep=no_sleep)
"""The source's client, whose policy retries."""
CACHED = AsyncClient(_config(cache=MemoryCache()), sleep=no_sleep)
"""A client that caches, as a source's may."""


async def three_series_async(series: str) -> dict[str, Any]:
    """Three calls on three paths: the series' entry, its metadata and its data."""
    listed = (await CLIENT.get_answer("/v1/series", params={"id": series})).payload
    meta = (await CLIENT.get_answer(f"/v1/series/{series}/meta")).payload
    data = (await CLIENT.get_answer(f"/v1/series/{series}/data", params={"year": "2025"})).payload
    return {"listed": listed, "meta": meta, "data": data}


three_series = sync(three_series_async)


async def four_calls_async(series: str) -> None:
    await three_series_async(series)
    await CLIENT.get_answer(f"/v1/series/{series}/notes")


async def calls_async(count: int) -> None:
    for number in range(count):
        await CLIENT.get_answer(f"/v1/calls/{number}")


PATHS = ["/v1/series", "/v1/series/corn/meta", "/v1/series/corn/data"]
ANSWERS: list[dict[str, Any]] = [{"ids": ["corn"]}, {"unit": "t"}, {"values": [1, 2]}]


def _serve(respx_mock: respx.MockRouter, **extra: Any) -> list[respx.Route]:
    """The three answers of ``three_series("corn")``, each with ``extra`` added."""
    return [
        respx_mock.get(f"{BASE}{path}").respond(200, json={**answer, **extra})
        for path, answer in zip(PATHS, ANSWERS, strict=True)
    ]


def _paths(fixtures: list[Fixture]) -> list[str]:
    return [httpx.URL(fixture.request.url).path for fixture in fixtures]


@pytest.fixture
def fixtures_dir(tmp_path: Path) -> Path:
    """The directory the recordings write and ``replay_fixture`` reads."""
    return tmp_path / "fixtures"


@pytest.mark.anyio
async def test_a_task_of_three_calls_on_three_paths_records_three_fixtures_that_replay(
    respx_mock: respx.MockRouter, fixtures_dir: Path, replay_fixture: ReplayFixture
) -> None:
    routes = _serve(respx_mock)
    recorded = await record_task(three_series_async, "corn", fixtures=fixtures_dir, case="ok")
    assert [route.call_count for route in routes] == [1, 1, 1]
    assert _paths(recorded) == PATHS, "in the order the task sent them"
    directory = fixtures_dir / "three_series"
    assert sorted(entry.name for entry in directory.iterdir()) == [
        "ok.json",
        "ok_2.json",
        "ok_3.json",
    ]
    cases = ["ok", "ok_2", "ok_3"]
    assert [load_fixture(fixture_path(fixtures_dir, "three_series", c)) for c in cases] == recorded
    respx_mock.clear()
    replays = [replay_fixture("three_series", case) for case in cases]
    assert await three_series_async("corn") == dict(
        zip(["listed", "meta", "data"], ANSWERS, strict=True)
    )
    assert [route.call_count for route in replays] == [1, 1, 1]


def test_record_task_sync_records_a_sync_facade_through_its_async_twin(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    _serve(respx_mock)
    recorded = record_task_sync(three_series, "corn", fixtures=fixtures_dir, case="ok")
    assert _paths(recorded) == PATHS
    assert (fixtures_dir / "three_series" / "ok_3.json").is_file()


@pytest.mark.anyio
async def test_the_scrub_the_rewrite_step_and_the_check_run_on_each_exchange(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    _serve(respx_mock, note="key-123", text="a post about corn")
    seen: list[tuple[str, bool]] = []

    def step(fixture: Fixture) -> tuple[Fixture, list[str]]:
        seen.append((httpx.URL(fixture.request.url).path, "key-123" in fixture.response.body))
        body = json.loads(fixture.response.body)
        replaced = [body["text"]]
        body["text"] = "[text rewritten]"
        response = fixture.response.model_copy(update={"body": json.dumps(body)})
        return fixture.model_copy(update={"response": response}), replaced

    await record_task(
        three_series_async,
        "corn",
        fixtures=fixtures_dir,
        case="ok",
        scrub=Scrub(secrets=["key-123"]),
        rewrite=step,
    )
    assert seen == [(path, False) for path in PATHS], "the step sees each scrubbed exchange"
    for case in ("ok", "ok_2", "ok_3"):
        written = fixture_path(fixtures_dir, "three_series", case).read_text(encoding="utf-8")
        assert REDACTED in written
        assert "[text rewritten]" in written
        assert "key-123" not in written
        assert "a post about corn" not in written


LEFT = "cornfield-7"
"""A value the step replaces in the body, which the third answer echoes in a header."""


@pytest.mark.anyio
async def test_a_refusal_in_the_third_of_four_exchanges_writes_nothing_and_names_it(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    routes = _serve(respx_mock, text=LEFT)
    routes[2].respond(200, json={"text": LEFT}, headers={"X-Echo": LEFT})
    notes = respx_mock.get(f"{BASE}/v1/series/corn/notes").respond(200, json={"text": LEFT})

    def step(fixture: Fixture) -> tuple[Fixture, list[str]]:
        body = json.loads(fixture.response.body)
        body["text"] = "[text rewritten]"
        response = fixture.response.model_copy(update={"body": json.dumps(body)})
        return fixture.model_copy(update={"response": response}), [LEFT]

    with pytest.raises(ValueError, match="exchange 3 of 4") as refused:
        await record_task(four_calls_async, "corn", fixtures=fixtures_dir, case="ok", rewrite=step)
    message = str(refused.value)
    assert "four_calls/ok_3.json" in message
    assert "response header 'x-echo'" in message
    assert "a write among them may have been applied" in message
    assert LEFT not in message
    assert not fixtures_dir.exists(), "no fixture of the task is written"
    assert [route.call_count for route in [*routes, notes]] == [1, 1, 1, 1]


@pytest.mark.anyio
async def test_a_task_that_raises_writes_nothing_and_the_collector_is_off_after(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    routes = _serve(respx_mock)
    routes[1].respond(404, json={"error": "no such series"})
    with pytest.raises(NotFoundError):
        await record_task(three_series_async, "corn", fixtures=fixtures_dir, case="ok")
    assert not fixtures_dir.exists()
    routes[0].side_effect = [httpx.Response(503, text="busy"), httpx.Response(200, json={})]
    routes[0].reset()
    await CLIENT.get("/v1/series")
    assert routes[0].call_count == 2, "retried again: the collector is off"


async def cached_and_busy_async() -> None:
    await CACHED.get_answer("/v1/regions")
    with contextlib.suppress(UpstreamError):  # the 503 is recorded before it is raised
        await CACHED.get("/v1/busy")


@pytest.mark.anyio
async def test_retries_are_off_and_the_cache_is_skipped_while_recording(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    regions = respx_mock.get(f"{BASE}/v1/regions")
    regions.side_effect = [httpx.Response(200, json={"n": 1}), httpx.Response(200, json={"n": 2})]
    busy = respx_mock.get(f"{BASE}/v1/busy").respond(503, text="busy")
    assert (await CACHED.get_answer("/v1/regions")).payload == {"n": 1}, "stored, off"
    recorded = await record_task(cached_and_busy_async, fixtures=fixtures_dir, case="busy")
    assert [json.loads(recorded[0].response.body), recorded[1].response.status] == [{"n": 2}, 503]
    assert busy.call_count == 1, "the 503 is recorded as it came, never retried"
    assert regions.call_count == 2, "the cache did not answer the recording"
    assert (await CACHED.get_answer("/v1/regions")).payload == {"n": 1}, "nor did it fill it"
    assert regions.call_count == 2


async def redirected_async() -> None:
    await CLIENT.get("/v1/series")
    await CLIENT.get("/v1/moved")
    await CLIENT.get("/v1/series/corn/meta")


@pytest.mark.anyio
async def test_a_3xx_among_the_exchanges_refuses_the_recording(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    _serve(respx_mock)
    respx_mock.get(f"{BASE}/v1/moved").respond(302, headers={"Location": f"{BASE}/v2/moved"})
    with pytest.raises(ValueError, match=r"exchange 2 of 3.*HTTP 302") as refused:
        await record_task(redirected_async, fixtures=fixtures_dir, case="ok")
    assert "redirected/ok_2.json" in str(refused.value)
    assert not fixtures_dir.exists()


async def decodes_a_redirect_async() -> None:
    await CLIENT.get_answer("/v1/series")
    await CLIENT.get_answer("/v1/moved")  # a 302 has no JSON body: the task raises


async def swallows_a_redirect_async() -> None:
    await CLIENT.get_answer("/v1/series")
    with contextlib.suppress(ValidationError):
        await CLIENT.get_answer("/v1/moved")
    await CLIENT.get_answer("/v1/series/corn/meta")


async def raises_after_a_redirect_async() -> None:
    await CLIENT.get("/v1/moved")
    await CLIENT.get_answer("/v1/series")
    await CLIENT.get_answer("/v1/series/corn/meta")  # answers 404: the task raises


@pytest.mark.anyio
async def test_a_3xx_the_task_decodes_refuses_with_the_frame_s_reason_and_the_task_s_error(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    # https://github.com/xippios/sdk-core/issues/364, part 2: refused on every path, whatever
    # the task makes of the answer.
    _serve(respx_mock)
    respx_mock.get(f"{BASE}/v1/moved").respond(302, headers={"Location": f"{BASE}/v2/moved"})
    with pytest.raises(ValueError, match=r"exchange 2 of 2.*HTTP 302") as refused:
        await record_task(decodes_a_redirect_async, fixtures=fixtures_dir, case="ok")
    assert "decodes_a_redirect/ok_2.json" in str(refused.value)
    assert isinstance(refused.value.__cause__, ValidationError), "the task's own error"
    assert not fixtures_dir.exists()


@pytest.mark.anyio
async def test_a_3xx_the_task_swallows_refuses_the_recording(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    _serve(respx_mock)
    respx_mock.get(f"{BASE}/v1/moved").respond(302, headers={"Location": f"{BASE}/v2/moved"})
    with pytest.raises(ValueError, match=r"exchange 2 of 3.*HTTP 302"):
        await record_task(swallows_a_redirect_async, fixtures=fixtures_dir, case="ok")
    assert not fixtures_dir.exists()


@pytest.mark.anyio
async def test_a_3xx_before_the_task_s_error_refuses_with_its_own_number(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    routes = _serve(respx_mock)
    routes[1].respond(404, json={"error": "no such series"})
    respx_mock.get(f"{BASE}/v1/moved").respond(302, headers={"Location": f"{BASE}/v2/moved"})
    with pytest.raises(ValueError, match=r"exchange 1 of 3.*HTTP 302") as refused:
        await record_task(raises_after_a_redirect_async, fixtures=fixtures_dir, case="ok")
    assert "raises_after_a_redirect/ok.json" in str(refused.value)
    assert isinstance(refused.value.__cause__, NotFoundError)
    assert not fixtures_dir.exists()


async def writes_into_a_redirect_async() -> None:
    await CLIENT.post_json("/v1/notes", json={"n": 1})


@pytest.mark.anyio
async def test_a_write_answered_with_a_3xx_says_once_that_it_may_have_been_applied(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    respx_mock.post(f"{BASE}/v1/notes").respond(303, headers={"Location": f"{BASE}/v1/notes/7"})
    with pytest.raises(ValueError, match="HTTP 303") as refused:
        await record_task(writes_into_a_redirect_async, fixtures=fixtures_dir, case="ok")
    assert str(refused.value).count("may have been applied") == 1, str(refused.value)


async def downloads_async(dest: str) -> None:
    await CLIENT.get_answer("/v1/series")
    await CLIENT.download("/files/qs.csv", dest)


async def swallows_async(dest: str) -> None:
    with contextlib.suppress(ValueError):
        await downloads_async(dest)


@pytest.mark.anyio
@pytest.mark.parametrize("task", [downloads_async, swallows_async])
async def test_a_download_inside_the_task_is_refused_before_it_is_sent(
    respx_mock: respx.MockRouter, fixtures_dir: Path, tmp_path: Path, task: Any
) -> None:
    _serve(respx_mock)
    download = respx_mock.get(f"{BASE}/files/qs.csv").respond(200, content=b"a,b\n")
    with pytest.raises(ValueError, match=r"exchange 2, GET /files/qs\.csv, is a download"):
        await record_task(task, str(tmp_path / "qs.csv"), fixtures=fixtures_dir, case="ok")
    assert download.call_count == 0
    assert not fixtures_dir.exists()
    assert not (tmp_path / "qs.csv").exists()


async def takes_fixtures_async(fixtures: str) -> None:
    raise AssertionError("the task ran")


async def takes_case_async(*, case: str) -> None:
    raise AssertionError("the task ran")


async def takes_scrub_async(scrub: str = "") -> None:
    raise AssertionError("the task ran")


async def takes_rewrite_async(series: str, rewrite: bool = False) -> None:
    raise AssertionError("the task ran")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("task", "clash"),
    [
        (takes_fixtures_async, "fixtures"),
        (takes_case_async, "case"),
        (takes_scrub_async, "scrub"),
        (takes_rewrite_async, "rewrite"),
    ],
)
async def test_a_task_that_takes_a_keyword_of_the_helper_is_refused_before_it_runs(
    fixtures_dir: Path, task: Any, clash: str
) -> None:
    with pytest.raises(TypeError, match=f"takes {clash}, which record_task takes"):
        await record_task(task, fixtures=fixtures_dir, case="ok")


async def takes_task_async(task: str) -> None:
    await CLIENT.get_answer(f"/v1/tasks/{task}")


@pytest.mark.anyio
async def test_a_task_s_keyword_named_task_reaches_the_task(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    respx_mock.get(f"{BASE}/v1/tasks/t-1").respond(200, json={})
    recorded = await record_task(takes_task_async, fixtures=fixtures_dir, case="ok", task="t-1")
    assert _paths(recorded) == ["/v1/tasks/t-1"]


@pytest.mark.anyio
async def test_a_recording_with_fewer_exchanges_refuses_while_later_numbers_stand(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    respx_mock.get(url__regex=rf"{BASE}/v1/calls/\d+").respond(200, json={})
    await record_task(calls_async, 3, fixtures=fixtures_dir, case="ok")
    directory = fixtures_dir / "calls"
    for other in ("ok_1.json", "okay_9.json", "ok_x.json"):  # no number of the case "ok"
        (directory / other).write_text("{}", encoding="utf-8")
    before = {entry.name: entry.read_text(encoding="utf-8") for entry in directory.iterdir()}
    with pytest.raises(ValueError, match=r"calls/ok_3\.json") as refused:
        await record_task(calls_async, 2, fixtures=fixtures_dir, case="ok")
    assert "ok_1.json" not in str(refused.value)
    assert "okay_9.json" not in str(refused.value)
    assert {e.name: e.read_text(encoding="utf-8") for e in directory.iterdir()} == before
    (directory / "ok_3.json").unlink()
    recorded = await record_task(calls_async, 2, fixtures=fixtures_dir, case="ok")
    assert _paths(recorded) == ["/v1/calls/0", "/v1/calls/1"]


async def sends_nothing_async() -> None:
    return None


@pytest.mark.anyio
async def test_a_task_that_sends_no_request_is_refused(fixtures_dir: Path) -> None:
    with pytest.raises(ValueError, match="sent no request"):
        await record_task(sends_nothing_async, fixtures=fixtures_dir, case="ok")
    assert not fixtures_dir.exists()


async def at_once_async(series: str) -> None:
    meta = CLIENT.get_answer(f"/v1/series/{series}/meta")
    data = CLIENT.get_answer(f"/v1/series/{series}/data")
    await asyncio.gather(meta, data)


@pytest.mark.anyio
async def test_two_recordings_at_once_do_not_mix_and_concurrent_requests_are_kept(
    respx_mock: respx.MockRouter, fixtures_dir: Path
) -> None:
    _serve(respx_mock)
    respx_mock.get(url__regex=rf"{BASE}/v1/calls/\d+").respond(200, json={})
    first, second, third = await asyncio.gather(
        record_task(three_series_async, "corn", fixtures=fixtures_dir, case="ok"),
        record_task(calls_async, 2, fixtures=fixtures_dir, case="ok"),
        record_task(at_once_async, "corn", fixtures=fixtures_dir, case="ok"),
    )
    assert _paths(first) == PATHS
    assert _paths(second) == ["/v1/calls/0", "/v1/calls/1"]
    assert sorted(_paths(third)) == sorted(PATHS[1:]), "in the order the answers arrived"


async def records_inside_async() -> None:
    await record_task(sends_nothing_async, fixtures=Path("unused"), case="ok")


@pytest.mark.anyio
async def test_a_recording_inside_a_recorded_task_is_refused(fixtures_dir: Path) -> None:
    with pytest.raises(RuntimeError, match="inside another"):
        await record_task(records_inside_async, fixtures=fixtures_dir, case="ok")
