import httpx
import pytest

from xippios.core.testing import LIVE_ENV, live_enabled

# The pytester runs below install the plugin's patches themselves; the outer layer must
# not stack its own under them, or a marker in an inner run would prove nothing.
pytestmark = [pytest.mark.network]

SEND = httpx.HTTPTransport.handle_request
SEND_ASYNC = httpx.AsyncHTTPTransport.handle_async_request
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


def test_replay_fixture_helper(pytester: pytest.Pytester) -> None:
    fixtures = pytester.mkdir("tests") / "fixtures" / "ep"
    fixtures.mkdir(parents=True)
    (fixtures / "case.json").write_text(
        '{"recorded_at": "2026-10-20T00:00:00Z", "request": {"method": "GET",'
        ' "url": "https://h.test/p"}, "response": {"status": 200, "headers": [],'
        ' "body": "{\\"a\\": 1}", "body_base64": false}}'
    )
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
