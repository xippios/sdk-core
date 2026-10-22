import base64

import httpx
import pytest
import respx
from pydantic import SecretStr

from xippios.core.client import (
    AsyncClient,
    BasicKeyAuth,
    BearerAuth,
    Client,
    ClientConfig,
    EnvKeyAuth,
    HeaderKeyAuth,
    QueryKeyAuth,
)
from xippios.core.errors import ConfigError

BASE = "https://api.example.test"
ENV = "EXAMPLE_TEST_API_KEY"
KEY = "not-a-real-key"


@pytest.fixture
def config() -> ClientConfig:
    return ClientConfig(source="example", version="1", base_url=BASE)


@pytest.fixture
def key_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV, KEY)


@pytest.mark.anyio
@pytest.mark.usefixtures("key_in_env")
async def test_query_key(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=QueryKeyAuth("key", ENV, source="example"))
    await client.get("/v1/x", params={"year": 2024})
    assert route.calls.last.request.url.params.multi_items() == [("year", "2024"), ("key", KEY)]


@pytest.mark.anyio
@pytest.mark.usefixtures("key_in_env")
async def test_header_key(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=HeaderKeyAuth("Ocp-Apim-Subscription-Key", ENV))
    await client.get("/v1/x")
    assert route.calls.last.request.headers["ocp-apim-subscription-key"] == KEY


@pytest.mark.anyio
@pytest.mark.usefixtures("key_in_env")
async def test_bearer(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=BearerAuth(ENV))
    await client.get("/v1/x")
    assert route.calls.last.request.headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.anyio
@pytest.mark.usefixtures("key_in_env")
async def test_basic_key_as_user_name(respx_mock: respx.MockRouter, config: ClientConfig) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=BasicKeyAuth(ENV))
    await client.get("/v1/x")
    expected = base64.b64encode(f"{KEY}:".encode()).decode()
    assert route.calls.last.request.headers["authorization"] == f"Basic {expected}"


def test_key_is_lazy_and_missing_key_is_a_config_error(
    respx_mock: respx.MockRouter, config: ClientConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV, raising=False)
    respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    auth = QueryKeyAuth("key", ENV, source="example")  # constructing never touches the environment
    client = Client(config, auth=auth)
    with pytest.raises(ConfigError, match=ENV):
        client.get("/v1/x")
    monkeypatch.setenv(ENV, KEY)
    assert client.get("/v1/x").status_code == 200


def test_explicit_key_wins_and_is_resolved_once(
    respx_mock: respx.MockRouter, config: ClientConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV, "from-environment")
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    auth = BearerAuth(ENV, key=SecretStr("explicit"))
    client = Client(config, auth=auth)
    client.get("/v1/x")
    monkeypatch.setenv(ENV, "changed-later")
    client.get("/v1/x")
    assert all(call.request.headers["authorization"] == "Bearer explicit" for call in route.calls)


def test_base_class_requires_apply() -> None:
    auth = EnvKeyAuth(ENV, key="k")
    request = httpx.Request("GET", f"{BASE}/v1/x")
    with pytest.raises(NotImplementedError):
        next(auth.auth_flow(request))
