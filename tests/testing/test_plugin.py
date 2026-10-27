import logging
from pathlib import Path

import httpcore
import pytest

from xippios.core.client import QuotaPolicy
from xippios.core.client.auth import EnvKeyAuth
from xippios.core.client.ratelimit import TokenBucket
from xippios.core.testing.plugin import LIVE_ENV, live_enabled

# The pytester runs below install the plugin's patches themselves, in process. The outer
# test lifts its own (the markers here, the placeholder pin by the override below), or
# a marker in an inner run would prove nothing.
pytestmark = [pytest.mark.network, pytest.mark.rate_limited]


@pytest.fixture
def placeholder_api_key() -> None:
    """The outer test pins no key; an inner run pins it itself."""


POOL_SEND = httpcore.ConnectionPool.handle_request
POOL_SEND_ASYNC = httpcore.AsyncConnectionPool.handle_async_request
ACQUIRE = TokenBucket.acquire
PAUSE = QuotaPolicy._pause
KEY = EnvKeyAuth.key
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


def test_live_tests_are_skipped_unless_the_gate_is_open(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)
    pytester.makepyfile(TEST_FILE)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=1, skipped=1)
    monkeypatch.setenv(LIVE_ENV, "1")
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=2)


def test_the_gate_follows_the_marker_not_a_name(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(LIVE_ENV, raising=False)
    pytester.mkpydir("live")
    (pytester.path / "live" / "test_named_live.py").write_text(
        "import pytest\n\n"
        "class TestLive:\n"
        "    def test_offline(self):\n"
        "        assert True\n\n"
        "@pytest.mark.live\n"
        "def test_marked():\n"
        "    assert True\n"
    )
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=1, skipped=1)


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


OFFLINE_TESTS = """
import socket

import httpx
import pytest

from xippios.core.client import AsyncClient, ClientConfig

URL = "https://tenant.example.test/v1/series?key=SECRET"
TENANT = ClientConfig(source="example", version="1", base_url="https://tenant.example.test")


def closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


CLOSED = f"http://127.0.0.1:{closed_port()}/v1/closed"


def outcome(url):
    try:
        httpx.get(url, timeout=2.0)
    except RuntimeError as exc:
        return str(exc)
    except httpx.TransportError as exc:
        return type(exc).__name__
    return "answered"


AT_COLLECTION = outcome("https://tenant.example.test/v1/at-collection")


@pytest.fixture(scope="module")
def module_download():
    return outcome("https://tenant.example.test/v1/module")


@pytest.fixture(scope="session")
def session_download():
    return outcome("https://tenant.example.test/v1/session")


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


def test_requests_at_collection_and_in_wider_fixtures_are_refused(
    module_download, session_download
):
    refused = "network access in an offline test: GET /v1/"
    assert AT_COLLECTION.startswith(refused + "at-collection; ")
    assert module_download.startswith(refused + "module; ")
    assert session_download.startswith(refused + "session; ")


def test_a_mocked_request_is_answered(respx_mock):
    respx_mock.get("https://tenant.example.test/v1/series").respond(200, json={"ok": True})
    assert httpx.get(URL).json() == {"ok": True}


@pytest.mark.anyio
async def test_a_mocked_async_request_is_answered(respx_mock):
    respx_mock.post("https://tenant.example.test/v1/series").respond(201)
    async with httpx.AsyncClient() as client:
        assert (await client.post(URL, json={})).status_code == 201


@pytest.mark.anyio
async def test_an_unmocked_download_is_refused(tmp_path):
    # ADR-0019: download goes through the client's pool, which the guard covers.
    refused = "^network access in an offline test: GET /v1/files/qs.csv; "
    with pytest.raises(RuntimeError, match=refused):
        await AsyncClient(TENANT).download("/v1/files/qs.csv?key=SECRET", tmp_path / "qs.csv")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_a_mocked_download_writes_the_file(respx_mock, tmp_path):
    respx_mock.get("https://tenant.example.test/v1/files/qs.csv").respond(200, text="a\\n1\\n")
    got = await AsyncClient(TENANT).download("/v1/files/qs.csv", tmp_path / "qs.csv")
    assert (got.bytes, (tmp_path / "qs.csv").read_text()) == (4, "a\\n1\\n")


def test_a_transport_of_the_test_is_untouched():
    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    with httpx.Client(transport=transport) as client:
        assert client.get(URL).status_code == 204


def test_a_pass_through_route_is_refused(respx_mock):
    route = respx_mock.get(CLOSED).pass_through()
    assert outcome(CLOSED).startswith("network access in an offline test: GET /v1/closed; ")
    assert route.called


@pytest.mark.anyio
async def test_an_async_pass_through_route_is_refused(respx_mock):
    respx_mock.get(CLOSED).pass_through()
    async with httpx.AsyncClient() as client:
        with pytest.raises(RuntimeError, match="^network access in an offline test: GET "):
            await client.get(CLOSED, timeout=2.0)


@pytest.mark.network
def test_a_pass_through_route_reaches_the_network_when_marked(respx_mock):
    route = respx_mock.get(CLOSED).pass_through()
    assert outcome(CLOSED) == "ConnectError"
    assert route.called


@pytest.mark.network
def test_a_network_test_reaches_the_real_transport():
    assert outcome(CLOSED) == "ConnectError"


@pytest.mark.network
@pytest.mark.anyio
async def test_an_async_network_test_reaches_the_real_transport():
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError):
            await client.get(CLOSED, timeout=2.0)


@pytest.mark.live
def test_a_live_test_reaches_the_real_transport():
    assert outcome(CLOSED) == "ConnectError"


def test_the_refusal_is_back_after_marked_tests():
    assert outcome(CLOSED).startswith("network access in an offline test: GET /v1/closed; ")
"""


def test_offline_tests_cannot_reach_the_network(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Row 7 (sdk-cashctrl): nothing enforced "no network in the default test run".
    monkeypatch.setenv(LIVE_ENV, "1")
    pytester.makepyfile(OFFLINE_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=15)
    # The inner session gave back the two pool methods it patched: the outer session's guard.
    assert httpcore.ConnectionPool.handle_request is POOL_SEND
    assert httpcore.AsyncConnectionPool.handle_async_request is POOL_SEND_ASYNC


LIMITER_TESTS = """
import pytest

from xippios.core.client import AsyncClient, ClientConfig, RateLimit
from xippios.core.client.ratelimit import TokenBucket

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


@pytest.mark.anyio
async def test_the_bypass_takes_no_token():
    bucket = TokenBucket(RateLimit(per_minute=60, burst=1), clock=lambda: 0.0)
    for _ in range(3):
        assert (await bucket.acquire()) == 0.0
    assert bucket._tokens == 1.0  # untouched: the burst is still there
    assert bucket.reserve() == 0.0
    assert bucket.reserve() > 0.0


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
    pytester.makepyfile(LIMITER_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=4)
    assert TokenBucket.acquire is ACQUIRE


QUOTA_TESTS = """
import httpx
import pytest

from xippios.core import AsyncClient, ClientConfig, QuotaPolicy, RateLimitError, RetryPolicy

PAUSE = QuotaPolicy._pause
SLEPT = []


async def sleep(seconds):
    SLEPT.append(seconds)


POLICY = QuotaPolicy(window=3600.0, sleep=sleep)
CLIENT = AsyncClient(
    POLICY.install(
        ClientConfig(
            source="example",
            version="1",
            base_url="https://h.test",
            retry=RetryPolicy(max_attempts=1),
        )
    )
)


@pytest.mark.anyio
async def test_a_replayed_429_spends_the_quota(respx_mock):
    respx_mock.get("https://h.test/p").respond(429, headers={"Retry-After": "3151"})
    with pytest.raises(RateLimitError):
        await CLIENT.get("/p")
    assert POLICY.snapshot().remaining == 0


@pytest.mark.anyio
async def test_the_next_test_is_neither_refused_nor_paused(respx_mock):
    assert POLICY.snapshot() is None
    route = respx_mock.get("https://h.test/p").respond(200, json={"a": 1})
    assert (await CLIENT.get_json("/p")) == {"a": 1}
    assert route.call_count == 1
    assert SLEPT == []


@pytest.mark.anyio
async def test_a_quota_spent_in_the_test_neither_refuses_nor_pauses(respx_mock):
    route = respx_mock.get("https://h.test/p").mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "20"}), httpx.Response(200)]
    )
    with pytest.raises(RateLimitError):
        await CLIENT.get("/p")
    assert POLICY.snapshot().remaining == 0  # observed all the same
    await CLIENT.get("/p")
    assert route.call_count == 2
    assert SLEPT == []
    assert QuotaPolicy._pause is not PAUSE


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_rate_limited_test_keeps_the_pause(respx_mock):
    assert POLICY.snapshot() is None
    route = respx_mock.get("https://h.test/p").respond(429, headers={"Retry-After": "3151"})
    with pytest.raises(RateLimitError):
        await CLIENT.get("/p")
    with pytest.raises(RateLimitError, match="nothing was sent"):
        await CLIENT.get("/p")
    assert route.call_count == 1
    assert QuotaPolicy._pause is PAUSE


@pytest.mark.live
def test_a_live_test_keeps_the_policy():
    assert QuotaPolicy._pause is PAUSE
    assert POLICY.snapshot() is None  # the rate_limited test's spent quota was reset after it
"""


def test_a_replayed_429_leaves_no_quota_spent_for_later_tests(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A source's module-level QuotaPolicy would refuse every test after a replayed 429.
    monkeypatch.setenv(LIVE_ENV, "1")
    pytester.makepyfile(QUOTA_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=5)
    assert QuotaPolicy._pause is PAUSE


CACHE_TESTS = """
import pytest

from xippios.core.client import MemoryCache
from xippios.core.client.cache import CachedResponse

CACHE = MemoryCache()  # module-level, as a source keeps its client's
ENTRY = CachedResponse(status=200, headers=(), content=b"{}", stored_at=0.0)


def test_an_offline_test_stores_an_entry():
    CACHE.set("k", ENTRY)
    assert len(CACHE) == 1


def test_the_next_test_starts_without_it():
    assert len(CACHE) == 0


@pytest.mark.live
def test_a_live_test_keeps_what_it_stores():
    CACHE.set("k", ENTRY)


@pytest.mark.live
def test_so_the_next_live_test_finds_it():
    assert len(CACHE) == 1


def test_an_offline_test_after_them_starts_without_it():
    assert len(CACHE) == 0
"""


def test_every_memory_cache_is_empty_around_an_offline_test(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Row 39 b (sdk-usda-gats, sdk-comtrade): each source cleared its caches by hand.
    monkeypatch.setenv(LIVE_ENV, "1")
    pytester.makepyfile(CACHE_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    result.assert_outcomes(passed=5)


SUMMARY_TESTS = """
import httpx
import pytest

from xippios.core import QuotaPolicy

POLICY = QuotaPolicy(source="example")
QUIET = QuotaPolicy(source="unused")  # no reading: no line


@pytest.mark.live
def test_a_live_call_reads_the_quota():
    POLICY.observe(
        httpx.Response(
            200,
            headers={"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "998"},
            request=httpx.Request("GET", "https://tenant.example.test/v1?key=SECRET"),
        )
    )


def test_an_offline_test_after_it_resets_the_snapshot():
    assert POLICY.snapshot() is None
"""


@pytest.mark.parametrize(("gate", "lines"), [("1", 1), ("0", 0)])
def test_a_live_run_ends_with_the_quota_left(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, gate: str, lines: int
) -> None:
    # Row 44 b (sdk-usda-esr): a release PR reports the quota a live run left.
    monkeypatch.setenv(LIVE_ENV, gate)
    pytester.makepyfile(SUMMARY_TESTS)
    result = pytester.runpytest("-p", "xippios.core.testing.plugin", "--strict-markers")
    printed = [line for line in result.outlines if line.startswith("quota after the live run")]
    assert len(printed) == lines
    if lines:
        assert printed[0].startswith(
            "quota after the live run: example: 998 of 1000 requests left as of "
        )
        assert "tenant" not in result.stdout.str()
        assert "SECRET" not in result.stdout.str()


PLACEHOLDER_TESTS = """
import os

import httpx
import pytest

from xippios.core.client import HeaderKeyAuth, QueryKeyAuth
from xippios.core.client.auth import EnvKeyAuth
from xippios.core.testing.plugin import PLACEHOLDER_KEY

KEY = EnvKeyAuth.key
SHELL = dict(os.environ)  # at collection, before any fixture: what direnv loaded
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
        httpx.get("https://h.test/h", auth=auth)
    assert header.call_count == 2
    query = respx_mock.get("https://h.test/q", params={"key": PLACEHOLDER_KEY}).respond(200)
    httpx.get("https://h.test/q", auth=QueryKeyAuth("key", "EXAMPLE_API_KEY"))
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

from xippios.core.client.auth import EnvKeyAuth
from xippios.core.testing.plugin import PLACEHOLDER_KEY

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


PLUGIN_CONFTEST = """
import pytest

pytest_plugins = ["xippios.core.testing.plugin"]
"""

ANYIO_TESTS = """
import asyncio

import pytest


@pytest.mark.anyio
async def test_runs_on_asyncio(anyio_backend):
    assert anyio_backend == "asyncio"
    assert asyncio.get_running_loop()
"""


def test_anyio_tests_run_on_asyncio_without_a_fixture_of_the_source(
    pytester: pytest.Pytester,
) -> None:
    # Every source's conftest.py carried this fixture (C12); the plugin has it now. Enabled
    # through pytest_plugins, as a source does, it is registered after anyio's own, which
    # is parametrised by installed backend and would give the test id a suffix.
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.makepyfile(ANYIO_TESTS)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*::test_runs_on_asyncio PASSED*"])


def test_a_conftest_anyio_backend_overrides_the_plugin(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(
        PLUGIN_CONFTEST
        + "\n\n@pytest.fixture(params=['asyncio'], ids=['own'])\n"
        + "def anyio_backend(request):\n"
        + "    return request.param\n"
    )
    pytester.makepyfile(ANYIO_TESTS)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["*::test_runs_on_asyncio[[]own[]] PASSED*"])
