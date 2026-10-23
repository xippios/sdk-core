import pytest

from xippios.core.testing import LIVE_ENV, live_enabled

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
