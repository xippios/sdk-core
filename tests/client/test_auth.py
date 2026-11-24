import base64
import inspect
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from xippios.core.client import AsyncClient, ClientConfig, KeyAuth
from xippios.core.client.auth import EnvKeyAuth
from xippios.core.errors import ConfigError
from xippios.core.models import ResultMeta
from xippios.core.redaction import REDACTED, is_credential_name, scrub_params

BASE = "https://api.example.test"
ENV = "EXAMPLE_TEST_API_KEY"
KEY = "not-a-real-key"
OTHER_ENV = "EXAMPLE_OTHER_API_KEY"
OTHER_KEY = "not-a-real-header-key"


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
        (KeyAuth(ENV, location="query", name="key", source="example"), None, KEY),
        (KeyAuth(ENV, location="header", name="X-Api-Key"), "x-api-key", KEY),
        (KeyAuth(ENV, location="bearer"), "authorization", f"Bearer {KEY}"),
        (KeyAuth(ENV, location="basic"), "authorization", BASIC),
    ],
    ids=["query", "header", "bearer", "basic"],
)
async def test_the_one_key_class_sends_the_key_where_it_travels(
    respx_mock: respx.MockRouter,
    config: ClientConfig,
    auth: KeyAuth,
    header: str | None,
    value: str,
) -> None:
    # One class for the four places a key travels (ADR-0059, decision 7).
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    await AsyncClient(config, auth=auth).get("/v1/x", params={"year": 2024})
    sent = route.calls.last.request
    if header is None:  # the query parameter
        assert sent.url.params.multi_items() == [("year", "2024"), ("key", value)]
    else:
        assert sent.headers[header] == value
        assert "key" not in sent.url.params
    assert isinstance(auth, EnvKeyAuth), "the plugin's placeholder pin covers it"


def test_the_key_class_keeps_where_the_key_travels() -> None:
    query = KeyAuth(ENV, location="query", name="key", source="example")
    assert (query.env_var, query.location, query.name, query.source) == (
        ENV,
        "query",
        "key",
        "example",
    )
    bearer = KeyAuth(ENV, location="bearer")
    assert (bearer.location, bearer.name, bearer.source) == ("bearer", None, None)


def test_a_query_key_makes_its_parameter_a_credential_and_a_header_none() -> None:
    KeyAuth(ENV, location="header", name="key", source="example")  # a header registers none
    assert not is_credential_name("key")
    KeyAuth(ENV, location="query", name="key", source="example")
    assert is_credential_name("key", source="example")
    assert not is_credential_name("key", source="sibling"), "another source's key stays data"


@pytest.mark.usefixtures("key_in_env")
def test_a_key_the_process_holds_leaves_no_envelope_whatever_its_slug() -> None:
    # The review of #518: a query key registered under one slug stayed as sent in an
    # envelope of another (https://github.com/xippios/sdk-core/issues/485, part 4).
    query = KeyAuth(ENV, location="query", name="key", source="example")
    header = KeyAuth(OTHER_ENV, location="header", name="X-Api-Key", key=OTHER_KEY)
    request = {
        "key": KEY,
        "series": "M.DE",
        "copy": OTHER_KEY,
        "link": f"{BASE}/v1/x?key={KEY}&year=2024",
        "nested": [{"value": KEY}],
    }
    meta = ResultMeta(source="example-v2", endpoint="get_series", request=request)
    assert meta.request == {
        "key": REDACTED,
        "series": "M.DE",
        "copy": REDACTED,
        "link": f"{BASE}/v1/x?key={REDACTED}&year=2024",
        "nested": [{"value": REDACTED}],
    }
    keyless = ResultMeta(source="sibling", endpoint="get_series", request={"key": "M.DE.CP00"})
    assert keyless.request == {"key": "M.DE.CP00"}, "another source's data stays as sent"
    assert scrub_params([("q", KEY), ("year", "2024")]) == [("q", REDACTED), ("year", "2024")]
    assert (query.key(), header.key()) == (KEY, OTHER_KEY), "the keys are still sent"


def test_a_query_key_without_its_source_is_refused() -> None:
    # Its name is a credential of the source it names, and of no other (ADR-0040, decision 6).
    with pytest.raises(ValueError, match=r'^location="query" takes source=, the source whose'):
        KeyAuth(ENV, location="query", name="key")
    assert not is_credential_name("key"), "a refused query key registers nothing"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"location": "cookie", "name": "key"},
            "^location is one of query, header, bearer or basic, not 'cookie'$",
        ),
        (
            {"location": "query"},
            '^location="query" takes name=, the query parameter that carries the key$',
        ),
        (
            {"location": "header", "name": ""},
            '^location="header" takes name=, the header that carries the key$',
        ),
        (
            {"location": "bearer", "name": "Authorization"},
            '^location="bearer" takes no name=: the key goes in the Authorization header$',
        ),
        (
            {"location": "basic", "name": "user"},
            '^location="basic" takes no name=: the key goes in the Authorization header$',
        ),
    ],
    ids=["unknown", "query-unnamed", "header-empty", "bearer-named", "basic-named"],
)
def test_a_location_without_its_name_or_with_one_it_takes_none_is_refused(
    arguments: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        KeyAuth(ENV, **arguments)
    assert not is_credential_name("key"), "a refused query key registers nothing"


def test_basic_sends_the_key_as_the_user_name_with_no_password_to_give() -> None:
    # The password was never given by a source: it leaves (https://github.com/xippios/sdk-core/issues/475).
    assert "password" not in inspect.signature(KeyAuth).parameters
    auth = KeyAuth(ENV, location="basic", key=KEY)
    sent = next(auth.auth_flow(httpx.Request("GET", f"{BASE}/v1/x")))
    assert sent.headers["authorization"] == BASIC


@pytest.mark.anyio
async def test_key_is_lazy_and_a_missing_or_empty_key_is_a_config_error(
    respx_mock: respx.MockRouter, config: ClientConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV, raising=False)
    route = respx_mock.get(f"{BASE}/v1/x").respond(200, json={})
    # constructing never touches the environment
    auth = KeyAuth(ENV, location="query", name="key", source="example")
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
    client = AsyncClient(config, auth=KeyAuth(ENV, location="bearer", key=SecretStr("explicit")))
    await client.get("/v1/x")
    monkeypatch.setenv(ENV, "changed-later")
    await client.get("/v1/x")
    assert all(call.request.headers["authorization"] == "Bearer explicit" for call in route.calls)


def test_apply_reads_the_key_itself() -> None:
    # sdk-usda-nass: apply(request, key) made the key an argument of a traceback frame,
    # which pytest's long tracebacks print.
    for cls in (EnvKeyAuth, KeyAuth):
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
