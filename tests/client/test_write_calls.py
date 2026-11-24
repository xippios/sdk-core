"""``post_json`` and ``delete_json``, the write counterparts of ``get_json`` (#178)."""

import json

import httpx
import pytest
import respx

from xippios.core.client import AsyncClient, ClientConfig, MemoryCache, RetryPolicy
from xippios.core.errors import (
    InvalidRequestError,
    RateLimitError,
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


def make_client(
    sleeper: Sleeper | None = None, *, auth: httpx.Auth | None = None, **changes: object
) -> AsyncClient:
    arguments: dict[str, object] = {
        "source": "example",
        "version": "1",
        "base_url": BASE,
        "retry": RetryPolicy(max_attempts=3, backoff_base=0.1, jitter=False),
    }
    arguments.update(changes)
    config = ClientConfig(**arguments)  # type: ignore[arg-type]
    return AsyncClient(config, auth=auth, sleep=sleeper or Sleeper())


@pytest.mark.anyio
async def test_post_json_sends_a_json_body_and_decodes_the_answer(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(f"{BASE}/v1/drafts").respond(200, json={"id": "r-1"})
    client = make_client()
    answer = await client.post_json(
        "/v1/drafts", json={"message": {"raw": "eA"}}, params={"alt": "json"}
    )
    assert answer == {"id": "r-1"}
    sent = route.calls.last.request
    assert sent.url.params["alt"] == "json"
    assert sent.headers["content-type"] == "application/json"
    assert json.loads(sent.content) == {"message": {"raw": "eA"}}


@pytest.mark.anyio
async def test_post_json_sends_a_form_with_its_headers(respx_mock: respx.MockRouter) -> None:
    # sdk-cashctrl: CashCtrl's writes take form fields, with the charset declared.
    route = respx_mock.post(f"{BASE}/v1/journal/create.json").respond(
        200, json={"success": True, "insertId": 51}
    )
    client = make_client()
    form = "application/x-www-form-urlencoded; charset=UTF-8"
    answer = await client.post_json(
        "/v1/journal/create.json", data={"title": "x y"}, headers={"Content-Type": form}
    )
    assert answer == {"success": True, "insertId": 51}
    assert route.calls.last.request.headers["content-type"] == form
    assert route.calls.last.request.content == b"title=x+y"


@pytest.mark.anyio
@pytest.mark.parametrize("status", [200, 202, 204])
async def test_a_bodiless_answer_returns_none(respx_mock: respx.MockRouter, status: int) -> None:
    # sdk-google-mail: drafts.delete answers no body.
    respx_mock.delete(f"{BASE}/v1/drafts/r-1").respond(status)
    respx_mock.post(f"{BASE}/v1/messages/m1/trash").respond(status)
    client = make_client()
    assert await client.delete_json("/v1/drafts/r-1") is None
    assert await client.post_json("/v1/messages/m1/trash") is None


@pytest.mark.anyio
async def test_delete_json_decodes_an_answer_with_a_body(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.delete(f"{BASE}/v1/items/7").respond(200, json={"deleted": 7})
    client = make_client()
    assert await client.delete_json("/v1/items/7", params={"force": "true"}) == {"deleted": 7}
    sent = route.calls.last.request
    assert sent.url.params["force"] == "true"
    assert sent.content == b""


@pytest.mark.anyio
async def test_a_body_that_is_not_json_raises_naming_the_path(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{BASE}/v1/drafts").respond(200, text="<html>oops</html>")
    respx_mock.delete(f"{BASE}/v1/drafts/r-1").respond(200, text=" ")
    client = make_client()
    with pytest.raises(ValidationError) as info:
        await client.post_json("/v1/drafts", json={})
    assert info.value.message == (
        "example: response from /v1/drafts is not JSON: Expecting value at line 1 column 1 (char 0)"
    )
    assert info.value.raw == "<html>oops</html>"
    with pytest.raises(ValidationError, match=r"^example: response from /v1/drafts/r-1 is not"):
        await client.delete_json("/v1/drafts/r-1")  # a blank body is a body


@pytest.mark.anyio
async def test_get_json_still_refuses_an_empty_body(respx_mock: respx.MockRouter) -> None:
    """``None`` for a bodiless answer is the write calls' alone: ``get_json`` is unchanged."""
    respx_mock.get(f"{BASE}/v1/x").respond(204)
    with pytest.raises(ValidationError, match=r"^example: response from /v1/x is not JSON: "):
        await make_client().get_json("/v1/x")


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "DELETE"])
async def test_a_write_call_goes_through_classify_and_the_write_retry_rule(
    respx_mock: respx.MockRouter, method: str
) -> None:
    route = respx_mock.route(method=method, url=f"{BASE}/v1/x").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(503, text="busy"),
        ]
    )
    sleeper = Sleeper()
    client = make_client(sleeper)
    with pytest.raises(RateLimitError):
        await write(client, method, "/v1/x")
    with pytest.raises(UpstreamError, match=r"its outcome is unknown\.$"):
        await write(client, method, "/v1/x")
    assert route.call_count == 2  # neither a 429 nor a 5xx to a write is repeated (ADR-0011)
    assert sleeper.calls == []

    def classify(response: httpx.Response) -> XippiosError | None:
        if response.json().get("success") is False:
            return InvalidRequestError("refused", source="example")
        return None

    respx_mock.route(method=method, url=f"{BASE}/v1/y").respond(200, json={"success": False})
    with pytest.raises(InvalidRequestError, match=r"^refused$"):
        await write(make_client(classify=classify), method, "/v1/y")


async def write(client: AsyncClient, method: str, path: str) -> object:
    """``post_json(path)`` or ``delete_json(path)``, by ``method``."""
    if method == "POST":
        return await client.post_json(path)
    return await client.delete_json(path)


@pytest.mark.anyio
async def test_a_write_call_takes_auth_and_never_touches_the_cache(
    respx_mock: respx.MockRouter,
) -> None:
    post = respx_mock.post(f"{BASE}/v1/x").respond(200, json={"ok": True})
    delete = respx_mock.delete(f"{BASE}/v1/x").respond(204)
    client = make_client(auth=httpx.BasicAuth("user", "pw"), cache=MemoryCache())
    for _ in range(2):
        await client.post_json("/v1/x", json={})
        await client.delete_json("/v1/x")
    assert (post.call_count, delete.call_count) == (2, 2)
    assert "authorization" in post.calls.last.request.headers
    await client.post_json("/v1/x", json={}, auth=None)
    await client.delete_json("/v1/x", auth=None)
    assert "authorization" not in post.calls.last.request.headers
    assert "authorization" not in delete.calls.last.request.headers


@pytest.mark.anyio
async def test_json_and_data_together_are_refused_before_sending(
    respx_mock: respx.MockRouter,
) -> None:
    route = respx_mock.post(f"{BASE}/v1/x").respond(200, json={})
    with pytest.raises(ValueError, match="json= or data=, not both"):
        await make_client().post_json("/v1/x", json={"a": 1}, data={"a": 1})
    assert not route.called
