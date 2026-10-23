import logging
from pathlib import Path

import httpx
import pytest

from xippios.core.client import EnvKeyAuth, TokenBucket
from xippios.core.testing import LIVE_ENV, PLACEHOLDER_KEY, live_enabled

# The pytester runs below install the plugin's patches themselves, in process. The outer
# test lifts its own (the markers here, the placeholder pin by the override below), or
# a marker in an inner run would prove nothing.
pytestmark = [pytest.mark.network, pytest.mark.rate_limited]


@pytest.fixture
def placeholder_api_key() -> None:
    """The outer test pins no key; an inner run pins it itself."""


SEND = httpx.HTTPTransport.handle_request
SEND_ASYNC = httpx.AsyncHTTPTransport.handle_async_request
ACQUIRE = TokenBucket.acquire
KEY = EnvKeyAuth.key
ANYIO_CONFTEST = """
import pytest

@pytest.fixture
def anyio_backend():
    return "asyncio"
"""

TEST_FILE = """
import pytest

@pytest.mark.live
def test_live():
    assert True

def test_offline():
    assert True
"""


def test_live_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)
    assert live_enabled() is False
    monkeypatch.setenv(LIVE_ENV, "1")
    assert live_enabled() is True
    monkeypatch.setenv(LIVE_ENV, "yes")
    assert live_enabled() is False


def test_live_tests_skipped_by_default(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)
    pytester.makepyfile(TEST_FILE)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=1, skipped=1)


def test_live_tests_run_when_gate_open(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_ENV, "1")
    pytester.makepyfile(TEST_FILE)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=2)


def write_ep_case(pytester: pytest.Pytester) -> None:
    """``tests/fixtures/ep/case.json``: ``GET https://h.test/p`` answered ``{"a": 1}``."""
    fixtures: Path = pytester.mkdir("tests") / "fixtures" / "ep"
    fixtures.mkdir(parents=True)
    (fixtures / "case.json").write_text(
        '{"recorded_at": "2026-10-20T00:00:00Z", "request": {"method": "GET",'
        ' "url": "https://h.test/p"}, "response": {"status": 200, "headers": [],'
        ' "body": "{\\"a\\": 1}", "body_base64": false}}'
    )


def test_replay_fixture_helper(pytester: pytest.Pytester) -> None:
    write_ep_case(pytester)
    pytester.makepyfile(
        """
        import httpx

        def test_uses_fixture(replay_fixture):
            route = replay_fixture("ep", "case")
            assert httpx.get("https://h.test/p?any=thing").json() == {"a": 1}
            assert route.called
        """
    )
    result = pytester.runpytest("-p", "xippios.core.testing.plugin")
    result.assert_outcomes(passed=1)


def test_replay_fixture_helper_matches_params(pytester: pytest.Pytester) -> None:
    fixtures = pytester.mkdir("tests") / "fixtures" / "get"
    fixtures.mkdir(parents=True)
    (fixtures / "count.json").write_text(
        '{"recorded_at": "2026-10-23T00:00:00Z", "request": {"method": "GET",'
        ' "url": "https://h.test/get?countOnly=true&r=1"}, "response": {"status": 200,'
        ' "headers": [], "body": "{\\"count\\": 3}", "body_base64": false}}'
    )
    pytester.makepyfile(
        """
        import httpx
        import pytest
        from respx.models import AllMockedAssertionError

        def test_matches_count_only(replay_fixture):
            route = replay_fixture("get", "count", match_params=["countOnly"])
            assert httpx.get("https://h.test/get?countOnly=true").json() == {"count": 3}
            with pytest.raises(AllMockedAssertionError):
                httpx.get("https://h.test/get?countOnly=false")
            assert route.call_count == 1

        def test_positional(replay_fixture):
            replay_fixture("get", "count", ["countOnly"])
            assert httpx.get("https://h.test/get?countOnly=true").json() == {"count": 3}
        """
    )
    result = pytester.runpytest("-p", "xippios.core.testing.plugin")
    result.assert_outcomes(passed=2)


OFFLINE_TESTS = """
import socket

import httpx
import pytest

SEND = httpx.HTTPTransport.handle_request
SEND_ASYNC = httpx.AsyncHTTPTransport.handle_async_request
URL = "https://tenant.example.test/v1/series?key=SECRET"


def test_an_unmocked_request_is_refused():
    with pytest.raises(RuntimeError) as info:
        httpx.get(URL)
    message = str(info.value)
    assert message.startswith("network access in an offline test: GET /v1/series; ")
    assert "tenant" not in message
    assert "SECRET" not in message


@pytest.mark.anyio
async def test_an_unmocked_async_request_is_refused():
    refused = "^network access in an offline test: POST /v1/series; "
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match=refused):
            await client.post(URL, json={})


def test_a_mocked_request_is_answered(respx_mock):
    respx_mock.get("https://tenant.example.test/v1/series").respond(200, json={"ok": True})
    assert httpx.get(URL).json() == {"ok": True}


@pytest.mark.anyio
async def test_a_mocked_async_request_is_answered(respx_mock):
    respx_mock.post("https://tenant.example.test/v1/series").respond(201)
    async with httpx.AsyncClient() as client:
        assert (await client.post(URL, json={})).status_code == 201


def test_a_transport_of_the_test_is_untouched():
    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    with httpx.Client(transport=transport) as client:
        assert client.get(URL).status_code == 204


def closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.network
def test_a_network_test_reaches_the_real_transport():
    assert httpx.HTTPTransport.handle_request is SEND
    assert httpx.AsyncHTTPTransport.handle_async_request is SEND_ASYNC
    with pytest.raises(httpx.ConnectError):
        httpx.get(f"http://127.0.0.1:{closed_port()}/v1/series", timeout=2.0)


@pytest.mark.live
def test_a_live_test_keeps_the_real_transports():
    assert httpx.HTTPTransport.handle_request is SEND
    assert httpx.AsyncHTTPTransport.handle_async_request is SEND_ASYNC
"""


def test_offline_tests_cannot_reach_the_network(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Row 7 (sdk-cashctrl): nothing enforced "no network in the default test run".
    monkeypatch.setenv(LIVE_ENV, "1")
    pytester.makeconftest(ANYIO_CONFTEST)
    pytester.makepyfile(OFFLINE_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=7)
    assert httpx.HTTPTransport.handle_request is SEND
    assert httpx.AsyncHTTPTransport.handle_async_request is SEND_ASYNC


LIMITER_TESTS = """
import time

import pytest

from xippios.core.client import AsyncClient, Client, ClientConfig, RateLimit, TokenBucket

ACQUIRE = TokenBucket.acquire
CONFIG = ClientConfig(
    source="example",
    version="1",
    base_url="https://h.test",
    rate_limit=RateLimit(per_minute=60, burst=1),
)


class Sleeper:
    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)


@pytest.mark.anyio
async def test_replayed_requests_do_not_wait(replay_fixture):
    route = replay_fixture("ep", "case")
    sleeper = Sleeper()
    client = AsyncClient(CONFIG, sleep=sleeper)
    for _ in range(2):
        assert (await client.get_json("/p")) == {"a": 1}
    assert route.call_count == 2
    assert sleeper.calls == []
    assert TokenBucket.acquire is not ACQUIRE


def test_the_sync_client_does_not_wait_either(replay_fixture):
    route = replay_fixture("ep", "case")
    started = time.monotonic()
    with Client(CONFIG) as client:
        client.get("/p")
        client.get("/p")
    assert route.call_count == 2
    assert time.monotonic() - started < 0.5


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_rate_limited_test_waits(replay_fixture):
    replay_fixture("ep", "case")
    sleeper = Sleeper()
    client = AsyncClient(CONFIG, sleep=sleeper)
    await client.get("/p")
    await client.get("/p")
    assert sleeper.calls == [pytest.approx(1.0, abs=0.1)]
    assert TokenBucket.acquire is ACQUIRE


@pytest.mark.live
def test_a_live_test_keeps_the_limiter():
    assert TokenBucket.acquire is ACQUIRE
"""


def test_offline_tests_never_wait_on_the_rate_limiter(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Rows 12 and 18 (sdk-comtrade, sdk-usda-psd): a burst=1 source waited 1 s per replay.
    monkeypatch.setenv(LIVE_ENV, "1")
    write_ep_case(pytester)
    pytester.makeconftest(ANYIO_CONFTEST)
    pytester.makepyfile(LIMITER_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=4)
    assert TokenBucket.acquire is ACQUIRE


PLACEHOLDER_TESTS = """
import os

import pytest

from xippios.core.client import Client, ClientConfig, EnvKeyAuth, HeaderKeyAuth, QueryKeyAuth
from xippios.core.testing import PLACEHOLDER_KEY

KEY = EnvKeyAuth.key
SHELL = dict(os.environ)  # at collection, before any fixture: what direnv loaded
CONFIG = ClientConfig(source="example", version="1", base_url="https://h.test")
TENANTS = {name: HeaderKeyAuth("X-Key", f"TENANT_{name.upper()}_KEY") for name in ("a", "b")}


@pytest.mark.live
def test_a_live_test_reads_the_shell_and_caches_the_key(placeholder_api_key):
    assert placeholder_api_key is None
    assert EnvKeyAuth.key is KEY
    assert os.environ["EXAMPLE_API_KEY"] == SHELL["EXAMPLE_API_KEY"] != PLACEHOLDER_KEY
    assert TENANTS["a"].key() == SHELL["TENANT_A_KEY"]  # now cached on the object


def test_the_named_variables_hold_the_placeholder(placeholder_api_key):
    assert placeholder_api_key == PLACEHOLDER_KEY
    assert os.environ["EXAMPLE_API_KEY"] == PLACEHOLDER_KEY
    assert os.environ["OTHER_TOKEN"] == PLACEHOLDER_KEY
    assert os.environ["TENANT_A_KEY"] == SHELL["TENANT_A_KEY"]  # not named in the ini option


def test_every_auth_object_sends_the_placeholder(respx_mock):
    header = respx_mock.get("https://h.test/h", headers={"X-Key": PLACEHOLDER_KEY}).respond(200)
    for auth in TENANTS.values():  # "a" holds the live key, "b" has no variable at all
        with Client(CONFIG, auth=auth) as client:
            client.get("/h")
    assert header.call_count == 2
    query = respx_mock.get("https://h.test/q", params={"key": PLACEHOLDER_KEY}).respond(200)
    with Client(CONFIG, auth=QueryKeyAuth("key", "EXAMPLE_API_KEY")) as client:
        client.get("/q")
    assert query.called


@pytest.mark.live
def test_a_later_live_test_gets_everything_back(placeholder_api_key):
    assert placeholder_api_key is None
    assert EnvKeyAuth.key is KEY
    assert os.environ["EXAMPLE_API_KEY"] == SHELL["EXAMPLE_API_KEY"]
    assert TENANTS["a"].key() == SHELL["TENANT_A_KEY"]
"""


@pytest.fixture
def shell_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """What direnv would have loaded: keys an offline test must never send."""
    monkeypatch.setenv(LIVE_ENV, "1")
    monkeypatch.setenv("EXAMPLE_API_KEY", "shell-key")
    monkeypatch.setenv("OTHER_TOKEN", "shell-token")
    monkeypatch.setenv("TENANT_A_KEY", "shell-tenant-a")
    monkeypatch.delenv("TENANT_B_KEY", raising=False)


@pytest.mark.usefixtures("shell_keys")
def test_offline_tests_send_the_placeholder_key(pytester: pytest.Pytester) -> None:
    # Row 12 (sdk-comtrade): every source carried this fixture by hand (sdk-template 0.1.5).
    pytester.makeini("[pytest]\nxippios_placeholder_key_envs = EXAMPLE_API_KEY OTHER_TOKEN\n")
    pytester.makeconftest('pytest_plugins = ["xippios.core.testing.plugin"]\n')
    pytester.makepyfile(PLACEHOLDER_TESTS)
    result = pytester.runpytest("--strict-markers", "--strict-config")
    result.assert_outcomes(passed=4)
    assert EnvKeyAuth.key is KEY


SOURCE_CONFTEST = """
import pytest

from xippios.core.client import QueryKeyAuth

pytest_plugins = ["xippios.core.testing.plugin"]

VARIABLE = "EXAMPLE_API_KEY"
auth = QueryKeyAuth("key", VARIABLE)
PLACEHOLDER_KEY = "placeholder-for-fixture-replay"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def placeholder_api_key(request, monkeypatch):
    if "live" in request.keywords:
        return None
    monkeypatch.setenv(VARIABLE, PLACEHOLDER_KEY)
    monkeypatch.setattr(auth, "key", lambda: PLACEHOLDER_KEY)
    return PLACEHOLDER_KEY


@pytest.fixture
def source_auth():
    return auth
"""

SOURCE_TESTS = """
import os

from xippios.core.client import EnvKeyAuth
from xippios.core.testing import PLACEHOLDER_KEY

KEY = EnvKeyAuth.key
SHELL = dict(os.environ)


def test_the_source_fixture_overrides_the_plugin(placeholder_api_key, source_auth):
    assert placeholder_api_key == PLACEHOLDER_KEY
    assert source_auth.key() == placeholder_api_key
    assert os.environ["EXAMPLE_API_KEY"] == placeholder_api_key
    assert os.environ["OTHER_TOKEN"] == SHELL["OTHER_TOKEN"]  # the plugin's fixture did not run
    assert EnvKeyAuth.key is KEY
"""


@pytest.mark.usefixtures("shell_keys")
def test_a_source_fixture_of_the_same_name_overrides_the_plugin(
    pytester: pytest.Pytester,
) -> None:
    # A source on core 0.2.0 may keep the fixture it carries from sdk-template 0.1.5.
    pytester.makeini("[pytest]\nxippios_placeholder_key_envs = OTHER_TOKEN\n")
    pytester.makeconftest(SOURCE_CONFTEST)
    pytester.makepyfile(SOURCE_TESTS)
    result = pytester.runpytest("--strict-markers", "--strict-config")
    result.assert_outcomes(passed=1)


def test_placeholder_key_is_exported() -> None:
    from xippios.core.testing import plugin

    assert PLACEHOLDER_KEY == plugin.PLACEHOLDER_KEY == "placeholder-for-fixture-replay"


LOGGER_TESTS = """
import logging

import pytest

from xippios.core.mcp import build_server

NAMES = ("httpx", "httpcore")
BEFORE = [logging.getLogger(name).level for name in NAMES]


def test_building_a_server_quiets_the_request_loggers():
    build_server("example", [])
    assert [logging.getLogger(name).level for name in NAMES] == [logging.WARNING] * 2


def test_the_next_test_gets_the_levels_back():
    assert [logging.getLogger(name).level for name in NAMES] == BEFORE


@pytest.mark.live
def test_a_live_test_quiets_them_too():
    build_server("example", [])


def test_and_the_next_test_gets_them_back_again():
    assert [logging.getLogger(name).level for name in NAMES] == BEFORE
"""


def test_request_logger_levels_are_restored_after_every_test(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Row 8 (sdk-cashctrl): core restored the levels in its own conftest only.
    monkeypatch.setenv(LIVE_ENV, "1")
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.NOTSET)
    pytester.makepyfile(LOGGER_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=4)
    assert [logging.getLogger(name).level for name in ("httpx", "httpcore")] == [0, 0]
