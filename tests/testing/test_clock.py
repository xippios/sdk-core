from datetime import UTC, datetime, timedelta

import pytest

from xippios.core.testing import CLOCK_SLACK, assert_time_between

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_a_time_inside_the_bracket_or_the_slack_passes() -> None:
    # sdk-usda-gats carried CLOCK_SLACK; usda-psd and usda-esr bracket retrieved_at
    # without it, exposed to the WSL2 host's two-second step back.
    later = NOW + timedelta(seconds=1)
    assert_time_between(NOW, NOW, later)
    assert_time_between(NOW - timedelta(seconds=2), NOW, later)
    assert_time_between(later + CLOCK_SLACK, NOW, later)


def test_a_time_beyond_the_slack_fails_naming_the_three() -> None:
    with pytest.raises(AssertionError, match=r"^2026-10-26T11:59:54\+00:00 is not between"):
        assert_time_between(NOW - timedelta(seconds=6), NOW, NOW)
    with pytest.raises(AssertionError, match=r"\(slack 0 s\)$"):
        assert_time_between(NOW + timedelta(microseconds=1), NOW, NOW, slack=timedelta(0))


def test_the_slack_is_five_seconds() -> None:
    assert timedelta(seconds=5) == CLOCK_SLACK
