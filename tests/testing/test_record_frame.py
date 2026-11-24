"""The recorder's frame: a source's rewrite step, the one send and final answers (ADR-0066)."""

import inspect
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from xippios.core.client import AsyncClient, ClientConfig, MemoryCache
from xippios.core.testing import (
    REDACTED,
    Fixture,
    Scrub,
    fixture_from_response,
    fixture_text,
    load_fixture,
    record,
    send_once,
)

BASE = "https://api.example.test"

PLACEHOLDERS = {
    "text": "[text rewritten]",
    "description": "[description rewritten]",
    "username": "[username rewritten]",
    "name": "[name rewritten]",
    "location": "[location rewritten]",
}
ACCOUNTS = frozenset({"acme", "example"})
"""The accounts whose names and handles a fixture keeps, as a source keeps its three."""


def _by_key(node: Any, replaced: list[str]) -> Any:
    """``node`` with a source's rule applied, each value it replaced appended to ``replaced``.

    Every ``text`` and ``description`` at any depth, and the ``username``, ``name`` and
    ``location`` of an object whose ``username`` is no account of ``ACCOUNTS``.
    """
    if isinstance(node, list):
        return [_by_key(item, replaced) for item in node]
    if not isinstance(node, dict):
        return node
    other = isinstance(node.get("username"), str) and node["username"].lower() not in ACCOUNTS
    result: dict[str, Any] = {}
    for key, value in node.items():
        mine = key in ("text", "description") or (other and key in ("username", "name", "location"))
        if mine and isinstance(value, str):
            replaced.append(value)
            result[key] = PLACEHOLDERS[key]
        else:
            result[key] = _by_key(value, replaced)
    return result


def rewrite_by_key(fixture: Fixture) -> tuple[Fixture, list[str]]:
    """A source's step in small: keys replaced in a JSON body, the values returned.

    The body is written compact, as upstream sends it; one with nothing to replace stays as sent.
    """
    replaced: list[str] = []
    body = _by_key(json.loads(fixture.response.body), replaced)
    if not replaced:
        return fixture, []
    text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    return fixture.model_copy(
        update={"response": fixture.response.model_copy(update={"body": text})}
    ), replaced


@pytest.fixture
def client() -> AsyncClient:
    """A source's client whose policy retries, as a source's does: a recording never retries."""
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    config = ClientConfig(source="example", version="1", base_url=BASE)
    assert config.retry.max_attempts > 1, "the default policy retries"
    return AsyncClient(config, sleep=sleep)


USERS = {
    "data": [{"id": "1", "username": "ACME", "name": "ACME", "description": "a bio of ours"}],
    "includes": {
        "posts": [{"id": "9", "text": "a post about corn", "lang": "en"}],
        "users": [{"id": "2", "username": "someone", "name": "Some One", "location": "a town"}],
    },
}
"""An answer of a source's shape, built here: this repository records from no upstream."""


@pytest.mark.anyio
async def test_record_scrubs_then_rewrites_then_checks_then_writes_once(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    answer = {**USERS, "note": "key-123"}
    route = respx_mock.get(f"{BASE}/2/users/by").respond(200, json=answer)
    fixture_file = tmp_path / "get_users_by_usernames" / "acme.json"
    seen: list[tuple[bool, bool]] = []

    def step(fixture: Fixture) -> tuple[Fixture, list[str]]:
        seen.append((fixture_file.exists(), "key-123" in fixture.response.body))
        return rewrite_by_key(fixture)

    fixture = await record.async_fn(
        client,
        "/2/users/by",
        fixture_file,
        params={"usernames": "ACME"},
        scrub=Scrub(secrets=["key-123"]),
        rewrite=step,
    )
    assert route.call_count == 1
    assert seen == [(False, False)], "the step sees the scrubbed fixture, before the write"
    body = json.loads(fixture.response.body)
    assert body["note"] == REDACTED
    assert body["data"][0] == {
        "id": "1",
        "username": "ACME",
        "name": "ACME",
        "description": "[description rewritten]",
    }
    assert body["includes"]["posts"][0]["text"] == "[text rewritten]"
    assert body["includes"]["users"][0]["location"] == "[location rewritten]"
    assert load_fixture(fixture_file) == fixture
    written = fixture_file.read_text(encoding="utf-8")
    assert written == fixture_text(fixture)
    for value in ("a bio of ours", "a post about corn", "someone", "Some One", "a town"):
        assert value not in written


@pytest.mark.anyio
async def test_sdk_x_s_rule_records_through_record_the_fixture_its_own_flow_writes(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    # https://github.com/xippios/sdk-core/issues/322, the first proof: the reduced recorder
    # writes what a source's flow writes today, fixture_from_response, its step, write_fixture.
    respx_mock.get(f"{BASE}/2/users/by").respond(
        200,
        content=json.dumps(USERS).encode(),
        headers={"Content-Type": "application/json", "x-rate-limit-remaining": "299"},
    )
    params = {"usernames": "ACME", "user.fields": "description,location"}
    fixture_file = tmp_path / "frame.json"
    framed = await record.async_fn(
        client, "/2/users/by", fixture_file, params=params, rewrite=rewrite_by_key
    )
    response = await send_once.async_fn(client, "/2/users/by", params=params)
    today, _ = rewrite_by_key(fixture_from_response(response))
    assert framed.model_copy(update={"recorded_at": today.recorded_at}) == today
    unchanged = {"data": [{"id": "1", "username": "EXAMPLE"}]}
    respx_mock.get(f"{BASE}/2/users/by").respond(200, json=unchanged)
    kept = await record.async_fn(
        client, "/2/users/by", tmp_path / "kept.json", rewrite=rewrite_by_key
    )
    assert json.loads(kept.response.body) == unchanged, "nothing to replace: kept as sent"


LEFT = "cornfield-7"
"""A value the step replaces in the response body, which each case leaves in one place."""


def _replace_text(fixture: Fixture) -> tuple[Fixture, list[str]]:
    """The response body's ``text`` replaced, and nothing else of the fixture."""
    body = json.loads(fixture.response.body)
    replaced = [body["text"]]
    body["text"] = "[text rewritten]"
    response = fixture.response.model_copy(update={"body": json.dumps(body)})
    return fixture.model_copy(update={"response": response}), replaced


@pytest.mark.parametrize(
    ("place", "request_options", "served"),
    [
        ("request URL", {"params": {"q": LEFT}}, {"json": {"text": LEFT}}),
        (
            "response header 'x-echo'",
            {},
            {"json": {"text": LEFT}, "headers": {"X-Echo": LEFT}},
        ),
        ("response body", {}, {"json": {"text": LEFT, "title": LEFT}}),
        ("request body", {"method": "POST", "json": {"text": LEFT}}, {"json": {"text": LEFT}}),
        (
            "response body, a decoded JSON string",
            {},
            {"content": b'{"text": "Z\\u00fcrich", "title": "Z\\u00fcrich"}'},
        ),
    ],
)
def test_a_replaced_value_left_in_a_place_refuses_the_write_and_names_the_place(
    respx_mock: respx.MockRouter,
    client: AsyncClient,
    tmp_path: Path,
    place: str,
    request_options: dict[str, Any],
    served: dict[str, Any],
) -> None:
    # https://github.com/xippios/sdk-core/issues/322, the second proof.
    respx_mock.route(url__startswith=f"{BASE}/v1/x").respond(200, **served)
    fixture_file = tmp_path / "x.json"
    with pytest.raises(ValueError, match=r"^the rewritten fixture still holds") as refused:
        record(client, "/v1/x", fixture_file, rewrite=_replace_text, **request_options)
    message = str(refused.value)
    assert message == (
        f"the rewritten fixture still holds a value the rewrite step replaced, in the {place}; "
        "nothing is written"
    )
    assert LEFT not in message
    assert "Zürich" not in message
    assert not fixture_file.exists()


def test_redacted_is_masked_before_the_check(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    # A value the step replaced that is a part of REDACTED is not found inside one.
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"text": "DACT", "key": "k-1"})
    fixture = record(
        client, "/v1/x", tmp_path / "x.json", scrub=Scrub(secrets=["k-1"]), rewrite=_replace_text
    )
    assert json.loads(fixture.response.body) == {"text": "[text rewritten]", "key": REDACTED}


def test_the_step_refuses_with_value_error_and_nothing_is_written(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={"text": LEFT})

    def refuse(fixture: Fixture) -> tuple[Fixture, list[str]]:
        raise ValueError("the answer names an account outside the three; nothing is written")

    with pytest.raises(ValueError, match=r"^the answer names an account outside the three"):
        record(client, "/v1/x", tmp_path / "x.json", rewrite=refuse)
    assert route.call_count == 1
    assert not (tmp_path / "x.json").exists()


def test_a_step_cannot_bring_a_secret_back(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"text": "k-1"})

    def restore(fixture: Fixture) -> tuple[Fixture, list[str]]:
        response = fixture.response.model_copy(update={"body": '{"text": "k-1"}'})
        return fixture.model_copy(update={"response": response}), []

    with pytest.raises(ValueError, match="still holds a secret value in the response body"):
        record(client, "/v1/x", tmp_path / "x.json", scrub=Scrub(secrets=["k-1"]), rewrite=restore)
    assert not (tmp_path / "x.json").exists()


def test_an_empty_value_the_step_returns_is_passed_over(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    # A source replaces a user's empty description too: nothing of it can survive.
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"text": "", "description": ""})
    fixture = record(client, "/v1/x", tmp_path / "x.json", rewrite=rewrite_by_key)
    assert json.loads(fixture.response.body) == {
        "text": "[text rewritten]",
        "description": "[description rewritten]",
    }


@pytest.mark.parametrize(
    ("returned", "message"),
    [
        ("fixture", r"^rewrite returns the fixture and the values it replaced"),
        ("not a fixture", r"^rewrite returns the fixture and the values it replaced"),
        ("one string", r"^rewrite returns the values it replaced as a sequence"),
        ("not text", r"^rewrite returns text values; one it returned is no string$"),
    ],
)
def test_a_step_that_returns_another_shape_is_refused(
    respx_mock: respx.MockRouter,
    client: AsyncClient,
    tmp_path: Path,
    returned: str,
    message: str,
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={"text": LEFT})
    shapes: dict[str, Any] = {
        "fixture": lambda fixture: fixture,
        "not a fixture": lambda fixture: ({}, []),
        "one string": lambda fixture: (fixture, LEFT),
        "not text": lambda fixture: (fixture, [7]),
    }
    with pytest.raises(TypeError, match=message) as refused:
        record(client, "/v1/x", tmp_path / "x.json", rewrite=shapes[returned])
    assert LEFT not in str(refused.value)
    assert not (tmp_path / "x.json").exists()


def test_a_rewrite_that_is_no_function_is_refused_before_anything_is_sent(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    not_callable: Any = "rewrite_by_key"
    with pytest.raises(TypeError, match=r"^rewrite is a function of the scrubbed Fixture"):
        record(client, "/v1/x", tmp_path / "x.json", rewrite=not_callable)
    assert not route.called
    request = httpx.Request("GET", f"{BASE}/v1/x")
    with pytest.raises(TypeError, match=r"^rewrite is a function of the scrubbed Fixture"):
        fixture_from_response(httpx.Response(200, json={}, request=request), rewrite=not_callable)


def test_fixture_from_response_runs_the_frame_on_one_exchange_without_the_write(
    tmp_path: Path,
) -> None:
    # The door of https://github.com/xippios/sdk-core/issues/174: every exchange of a task
    # is checked before any is written.
    request = httpx.Request("GET", f"{BASE}/2/users/by?usernames=ACME")
    response = httpx.Response(200, json=USERS, request=request)
    fixture = fixture_from_response(response, rewrite=rewrite_by_key)
    assert json.loads(fixture.response.body)["data"][0]["description"] == "[description rewritten]"
    assert list(tmp_path.iterdir()) == []
    left = httpx.Response(
        200, json={"text": LEFT}, headers={"x-echo": LEFT}, request=httpx.Request("GET", BASE)
    )
    with pytest.raises(ValueError, match=r"in the response header 'x-echo'; nothing is written$"):
        fixture_from_response(left, rewrite=_replace_text)


def test_the_plain_names_are_the_sync_functions_and_their_async_fn_is_awaited() -> None:
    # https://github.com/xippios/sdk-core/issues/483, part 1: one function under each plain
    # name, the sync one, as a task's sync form is; a caller on the loop awaits async_fn.
    for function, name in ((record, "record"), (send_once, "send_once")):
        assert not inspect.iscoroutinefunction(function), name
        assert inspect.iscoroutinefunction(function.async_fn), name
        assert function.__name__ == function.async_fn.__name__ == name
        assert list(inspect.signature(function).parameters)[:2] == ["client", "path"]


@pytest.mark.parametrize("status", [429, 503])
def test_send_once_sends_one_attempt_and_returns_the_answer_as_it_came(
    respx_mock: respx.MockRouter, client: AsyncClient, status: int
) -> None:
    # https://github.com/xippios/sdk-core/issues/281: no recorder builds a client for one
    # attempt any more, and a 429 or a 5xx spends no second request.
    route = respx_mock.get(f"{BASE}/v1/x").respond(
        status, text="busy", headers={"Retry-After": "0"}
    )
    response = send_once(client, "/v1/x", params={"year": 2024})
    assert route.call_count == 1
    assert (response.status_code, response.content) == (status, b"busy")
    assert response.request.url.params["year"] == "2024"


@pytest.mark.anyio
async def test_send_once_neither_reads_nor_stores_the_cache(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x")
    route.side_effect = [httpx.Response(200, json={"n": 1}), httpx.Response(200, json={"n": 2})]
    cached = AsyncClient(
        ClientConfig(source="example", version="1", base_url=BASE, cache=MemoryCache())
    )
    assert (await cached.get_answer("/v1/x")).payload == {"n": 1}
    response = await send_once.async_fn(cached, "/v1/x")
    assert response.json() == {"n": 2}
    assert (await cached.get_answer("/v1/x")).payload == {"n": 1}, "the entry stands"
    assert route.call_count == 2


@pytest.mark.anyio
async def test_send_once_runs_the_client_s_hooks_and_takes_the_recorder_s_options(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(f"{BASE}/v1/create.json").respond(200, json={"insertId": 7})
    before: list[str] = []
    observed: list[int] = []
    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        before_request=lambda request: before.append(request.url.path),
        observe=lambda response: observed.append(response.status_code),
    )
    hooked = AsyncClient(config)
    response = await send_once.async_fn(
        hooked, "/v1/create.json", method="post", data={"a": 1}, auth=None
    )
    assert (before, observed) == (["/v1/create.json"], [200])
    assert route.calls.last.request.content == b"a=1"
    assert response.json() == {"insertId": 7}
    with pytest.raises(ValueError, match="not both"):
        await send_once.async_fn(hooked, "/v1/create.json", method="POST", json={}, data={})
    for bound in (0, -1):
        with pytest.raises(ValueError, match=r"^max_read_bytes must be at least 1$"):
            await send_once.async_fn(hooked, "/v1/create.json", max_read_bytes=bound)
    assert route.call_count == 1, "a refused argument sends nothing"
    respx_mock.get(f"{BASE}/v1/big").respond(200, content=b"x" * 11)
    with pytest.raises(ValueError, match=r"^GET /v1/big answered a body over 10 bytes"):
        await send_once.async_fn(hooked, "/v1/big", max_read_bytes=10)


INTERIM = [101, 301, 302, 303, 304, 307, 308]
"""The statuses of an answer that is no final answer of its operation (ADR-0066, decision 4)."""


def _refusal(status: int, method: str = "GET") -> str:
    return rf"^{method} /v1/x answered HTTP {status}\b.*, no final answer of its operation"


def test_record_refuses_a_1xx_or_3xx_and_writes_nothing(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path
) -> None:
    # Each status is held once, on fixture_from_response below; each path refuses one here.
    elsewhere = "https://elsewhere.example.test/acme-tenant/x"
    route = respx_mock.get(f"{BASE}/v1/x").respond(302, headers={"Location": elsewhere})
    fixture_file = tmp_path / "x.json"
    with pytest.raises(ValueError, match=_refusal(302)) as refused:
        record(client, "/v1/x", fixture_file, rewrite=rewrite_by_key)
    assert "acme-tenant" not in str(refused.value), "a header's value is never named"
    assert "(ADR-0066)" in str(refused.value)
    assert route.call_count == 1
    assert not fixture_file.exists()


def test_send_once_refuses_a_1xx_or_3xx(respx_mock: respx.MockRouter) -> None:
    status = 304
    observed: list[int] = []
    config = ClientConfig(
        source="example",
        version="1",
        base_url=BASE,
        observe=lambda response: observed.append(response.status_code),
    )
    route = respx_mock.get(f"{BASE}/v1/x").respond(status)
    with pytest.raises(ValueError, match=_refusal(status)):
        send_once(AsyncClient(config), "/v1/x")
    assert route.call_count == 1
    assert observed == [status], "a quota policy still hears of the request spent"


@pytest.mark.parametrize("status", INTERIM)
def test_fixture_from_response_refuses_a_1xx_or_3xx_built_elsewhere(status: int) -> None:
    response = httpx.Response(status, request=httpx.Request("GET", f"{BASE}/v1/x"))
    with pytest.raises(ValueError, match=_refusal(status)):
        fixture_from_response(response)


def test_the_refusal_says_what_to_record_instead(
    respx_mock: respx.MockRouter, client: AsyncClient
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(302)
    with pytest.raises(ValueError, match="the URL that its Location header names"):
        send_once(client, "/v1/x")
    respx_mock.get(f"{BASE}/v1/x").respond(101)
    with pytest.raises(ValueError, match="an interim answer"):
        send_once(client, "/v1/x")
    respx_mock.post(f"{BASE}/v1/x").respond(303)
    with pytest.raises(ValueError, match=_refusal(303, "POST")) as refused:
        send_once(client, "/v1/x", method="POST", data={"a": 1})
    assert str(refused.value).endswith("the request was sent, so a write may have been applied")


@pytest.mark.parametrize("status", [200, 204, 404, 500])
def test_a_final_answer_is_recorded_whatever_its_status(
    respx_mock: respx.MockRouter, client: AsyncClient, tmp_path: Path, status: int
) -> None:
    respx_mock.get(f"{BASE}/v1/x").respond(status)
    fixture = record(client, "/v1/x", tmp_path / "x.json")
    assert load_fixture(tmp_path / "x.json").response.status == fixture.response.status == status
