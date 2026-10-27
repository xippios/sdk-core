"""Compare wall-clock readings in tests with a slack for a clock that steps back.

The WSL2 hosts the family's tests run on step their clock back about two seconds every
half minute, so a reading taken after a call can come out earlier than one the call
took: ``before <= result.meta.retrieved_at <= after`` fails now and then for a correct
``retrieved_at``.
"""

from datetime import datetime, timedelta

__all__ = ["CLOCK_SLACK", "assert_time_between"]

CLOCK_SLACK = timedelta(seconds=5)
"""The slack on a comparison of two wall-clock readings.

Five seconds covers the two-second step and stays far below what a wrong time is off
by: a recording's time, a packaged list's fetch date or a release time is hours or days
away. A test that compares two readings of its own uses it directly, e.g.
``second.meta.retrieved_at >= first.meta.retrieved_at - CLOCK_SLACK``.
"""


def assert_time_between(
    value: datetime, before: datetime, after: datetime, *, slack: timedelta = CLOCK_SLACK
) -> None:
    """Fail the test unless ``before - slack <= value <= after + slack``.

    ``before`` and ``after`` are readings taken around the call that produced
    ``value``, e.g.::

        before = datetime.now(UTC)
        result = tasks.list_regions()
        after = datetime.now(UTC)
        assert_time_between(result.meta.retrieved_at, before, after)

    Args:
        value: The time under test, e.g. ``result.meta.retrieved_at``.
        before: A reading taken before the call.
        after: A reading taken after the call.
        slack: How far the clock may have stepped; ``CLOCK_SLACK`` by default.

    Raises:
        AssertionError: ``value`` lies outside the bracket; the message names all three
            times.
    """
    if not before - slack <= value <= after + slack:
        raise AssertionError(
            f"{value.isoformat()} is not between {before.isoformat()} and "
            f"{after.isoformat()} (slack {slack.total_seconds():g} s)"
        )
