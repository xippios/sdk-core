import base64
import inspect

import httpx
import pytest
import respx
from pydantic import SecretStr

from xippios.core.client import (
    AsyncClient,
    BasicKeyAuth,
    BearerAuth,
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
def placeholder_api_key() -> None:
    """These tests check how a key is resolved: the plugin's placeholder pin stays off."""


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


@pytest.mark.anyio
async def test_key_is_lazy_and_a_missing_or_empty_key_is_a_config_error(
    respx_mock: respx.MockRouter, config: ClientConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV, raising=False)
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    auth = QueryKeyAuth("key", ENV, source="example")  # constructing never touches the environment
    client = AsyncClient(config, auth=auth)
    with pytest.raises(
        ConfigError, match=f"^{ENV} is not set; export it or pass the key explicitly$"
    ):
        await client.get("/v1/x")
    monkeypatch.setenv(ENV, "")
    with pytest.raises(ConfigError, match=ENV):
        await client.get("/v1/x")
    assert not route.called
    monkeypatch.setenv(ENV, KEY)
    assert (await client.get("/v1/x")).status_code == 200


@pytest.mark.anyio
async def test_explicit_key_wins_and_is_resolved_once(
    respx_mock: respx.MockRouter, config: ClientConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV, "from-environment")
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    client = AsyncClient(config, auth=BearerAuth(ENV, key=SecretStr("explicit")))
    await client.get("/v1/x")
    monkeypatch.setenv(ENV, "changed-later")
    await client.get("/v1/x")
    assert all(call.request.headers["authorization"] == "Bearer explicit" for call in route.calls)


def test_base_class_requires_apply() -> None:
    auth = EnvKeyAuth(ENV, key="k")
    request = httpx.Request("GET", f"{BASE}/v1/x")
    with pytest.raises(NotImplementedError):
        next(auth.auth_flow(request))


def test_apply_reads_the_key_itself() -> None:
    # sdk-usda-nass: apply(request, key) made the key an argument of a traceback frame,
    # which pytest's long tracebacks print.
    for cls in (EnvKeyAuth, QueryKeyAuth, HeaderKeyAuth, BearerAuth, BasicKeyAuth):
        assert list(inspect.signature(cls.apply).parameters) == ["self", "request"], cls

    class Custom(EnvKeyAuth):
        def apply(self, request: httpx.Request) -> None:
            request.headers["X-Custom"] = self.key()

    auth = Custom(ENV, key=KEY)
    assert next(auth.auth_flow(httpx.Request("GET", f"{BASE}/v1/x"))).headers["x-custom"] == KEY


def test_a_failing_apply_keeps_the_key_out_of_every_frame() -> None:
    auth = EnvKeyAuth(ENV, key=KEY)
    with pytest.raises(NotImplementedError) as info:
        next(auth.auth_flow(httpx.Request("GET", f"{BASE}/v1/x")))
    frames = [entry.locals for entry in info.traceback]
    assert [name for local in frames for name, value in local.items() if value == KEY] == []
