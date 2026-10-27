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
    HeaderKeyAuth,
    QueryKeyAuth,
)
from xippios.core.client.auth import EnvKeyAuth
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


BASIC = "Basic " + base64.b64encode(f"{KEY}:".encode()).decode()


@pytest.mark.anyio
@pytest.mark.usefixtures("key_in_env")
@pytest.mark.parametrize(
    ("auth", "header", "value"),
    [
        (QueryKeyAuth("key", ENV, source="example"), None, KEY),
        (HeaderKeyAuth("Ocp-Apim-Subscription-Key", ENV), "ocp-apim-subscription-key", KEY),
        (BearerAuth(ENV), "authorization", f"Bearer {KEY}"),
        (BasicKeyAuth(ENV), "authorization", BASIC),
    ],
    ids=["query", "header", "bearer", "basic"],
)
async def test_each_shape_sends_the_key_from_the_environment(
    respx_mock: respx.MockRouter,
    config: ClientConfig,
    auth: EnvKeyAuth,
    header: str | None,
    value: str,
) -> None:
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    await AsyncClient(config, auth=auth).get("/v1/x", params={"year": 2024})
    sent = route.calls.last.request
    if header is None:  # the query shape
        assert sent.url.params.multi_items() == [("year", "2024"), ("key", value)]
    else:
        assert sent.headers[header] == value


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
