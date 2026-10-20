import pytest

from xippios.core.client import ClientConfig, RateLimit, RetryPolicy, Timeouts


def test_timeouts_to_httpx() -> None:
    t = Timeouts().to_httpx()
    assert (t.connect, t.read, t.write, t.pool) == (10.0, 60.0, 10.0, 10.0)


def test_user_agent_format() -> None:
    config = ClientConfig(source="usda-nass", version="0.3.1", base_url="https://x.test")
    assert config.user_agent == "xippios-usda-nass/0.3.1 (+https://github.com/xippios)"


def test_retry_delay_doubles_and_caps_without_jitter() -> None:
    policy = RetryPolicy(max_attempts=5, backoff_base=1.0, backoff_max=5.0, jitter=False)
    assert [policy.delay(a) for a in range(1, 6)] == [1.0, 2.0, 4.0, 5.0, None]


def test_retry_delay_with_jitter_stays_in_band() -> None:
    policy = RetryPolicy(backoff_base=2.0, jitter=True)
    for _ in range(50):
        delay = policy.delay(1)
        assert delay is not None
        assert 1.0 <= delay <= 2.0


def test_retry_after_is_honoured_up_to_backoff_max() -> None:
    policy = RetryPolicy(backoff_base=0.1, backoff_max=10.0, jitter=False)
    assert policy.delay(1, retry_after=3.0) == 3.0
    assert policy.delay(1, retry_after=0.0) == 0.1
    assert policy.delay(1, retry_after=11.0) is None


def test_single_attempt_never_retries() -> None:
    assert RetryPolicy(max_attempts=1).delay(1) is None


def test_validation() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="per_minute"):
        RateLimit(per_minute=0)
    with pytest.raises(ValueError, match="burst"):
        RateLimit(per_minute=10, burst=0)


def test_rate_limit_defaults() -> None:
    limit = RateLimit(per_minute=120)
    assert limit.capacity == 120
    assert limit.per_second == 2.0
    assert RateLimit(per_minute=120, burst=5).capacity == 5
