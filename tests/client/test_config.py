import dataclasses

import pytest

from xippios.core.client import ClientConfig, RateLimit, RetryPolicy


def test_one_read_timeout_of_sixty_seconds_by_default() -> None:
    # Timeouts became the one timeout that a source sets, the read timeout
    # (https://github.com/xippios/sdk-core/issues/475).
    config = ClientConfig(source="example", version="1", base_url="https://h.test")
    assert config.read_timeout == 60.0
    assert "timeouts" not in {field.name for field in dataclasses.fields(ClientConfig)}
    slow = ClientConfig(source="example", version="1", base_url="https://h.test", read_timeout=180)
    assert slow.read_timeout == 180
    with pytest.raises(ValueError, match=r"^read_timeout must be above 0 seconds$"):
        ClientConfig(source="example", version="1", base_url="https://h.test", read_timeout=0)


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


def test_the_policy_has_no_switch_for_a_write_or_a_transport_failure() -> None:
    # The method alone decides what is repeated (ADR-0011, amendment 2026-11-24).
    fields = {field.name for field in dataclasses.fields(RetryPolicy)}
    assert fields == {"max_attempts", "backoff_base", "backoff_max", "jitter"}
    with pytest.raises(TypeError):
        RetryPolicy(retry_non_idempotent=True)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        RetryPolicy(retry_transport_errors=False)  # type: ignore[call-arg]


def test_validation() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="per_minute"):
        RateLimit(per_minute=0)
    with pytest.raises(ValueError, match="burst"):
        RateLimit(per_minute=10, burst=0)
    with pytest.raises(ValueError, match="cache_max_bytes must be at least 1"):
        ClientConfig(source="s", version="1", base_url="https://h.test", cache_max_bytes=0)
    default = ClientConfig(source="s", version="1", base_url="https://h.test")
    assert default.cache_max_bytes == 8 * 1024 * 1024  # 8 MiB (ADR-0040, decision 3)


def test_rate_limit_defaults() -> None:
    limit = RateLimit(per_minute=120)
    assert limit.capacity == 120
    assert limit.per_second == 2.0
    assert RateLimit(per_minute=120, burst=5).capacity == 5
