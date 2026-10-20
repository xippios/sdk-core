import pytest

from xippios.core.client import RateLimit, TokenBucket


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_burst_then_queue() -> None:
    clock = Clock()
    bucket = TokenBucket(RateLimit(per_minute=60, burst=2), clock=clock)
    assert bucket.reserve() == 0.0
    assert bucket.reserve() == 0.0
    assert bucket.reserve() == pytest.approx(1.0)
    assert bucket.reserve() == pytest.approx(2.0)


def test_refill_over_time() -> None:
    clock = Clock()
    bucket = TokenBucket(RateLimit(per_minute=120, burst=1), clock=clock)
    assert bucket.reserve() == 0.0
    clock.now = 0.25
    assert bucket.reserve() == pytest.approx(0.25)
    clock.now = 10.0
    assert bucket.reserve() == 0.0


def test_capacity_is_not_exceeded_after_idle() -> None:
    clock = Clock()
    bucket = TokenBucket(RateLimit(per_minute=60, burst=3), clock=clock)
    clock.now = 1000.0
    for _ in range(3):
        assert bucket.reserve() == 0.0
    assert bucket.reserve() > 0.0


@pytest.mark.anyio
async def test_acquire_sleeps_for_the_wait() -> None:
    clock = Clock()
    bucket = TokenBucket(RateLimit(per_minute=60, burst=1), clock=clock)
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    assert await bucket.acquire(sleep) == 0.0
    assert await bucket.acquire(sleep) == pytest.approx(1.0)
    assert slept == [pytest.approx(1.0)]
