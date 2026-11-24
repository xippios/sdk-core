"""The filter of a parameter that takes back a vintage (ADR-0052, sdk-core#318).

Each source hands ``newer_than`` its own reader of its vintage text, since core ships none
(ADR-0059, decision 4; ADR-0052, amendment 2026-11-24). Two forms each have their test: a
release time printed without a zone, read by the invented source's reader below (a date alone
its midnight, a zone refused), and a release month read into ``(year, month)``, used as a
filter of records and as all or nothing on the newest release.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import pytest

from xippios.core import InvalidRequestError, ResultMeta, XippiosError, newer_than

SOURCE = "example"


def read_since(text: str) -> datetime:
    """The invented source's reader of its vintage text, a release time printed without a zone."""
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is not None:
        raise InvalidRequestError(
            f"since must be a release time without a zone, got {text!r}.", source=SOURCE
        )
    return parsed


@dataclass(frozen=True)
class Release:
    """One record of a release list, its release time as upstream prints it, without a zone."""

    code: str
    printed: str | None

    @property
    def time(self) -> datetime | None:
        return None if self.printed is None else datetime.fromisoformat(self.printed)


def released(release: Release) -> datetime | None:
    return release.time


NEWEST = "2026-10-22T08:30:42.67"
RELEASES = [
    Release("0101", "2026-10-15T08:30:00"),
    Release("0107", NEWEST),
    Release("0201", "2026-10-22T08:30:42.5"),
    Release("0301", "2026-10-08T08:30:00"),
]
"""A release list in upstream's order, the newest release not last."""


def codes(releases: list[Release]) -> list[str]:
    return [release.code for release in releases]


def test_a_stored_vintage_keeps_only_what_was_released_strictly_later() -> None:
    kept = newer_than("2026-10-15T08:30:00", RELEASES, released=released, read=read_since)
    assert codes(kept) == ["0107", "0201"], "strictly later, in upstream's order"


def test_an_equal_vintage_keeps_nothing_and_the_task_still_names_the_newest_release() -> None:
    """The helper filters; the task builds ``meta`` from the whole answer beside it."""
    kept = newer_than(NEWEST, RELEASES, released=released, read=read_since)
    newest = max(RELEASES, key=lambda release: release.time or datetime.min)
    meta = ResultMeta(
        source=SOURCE,
        endpoint="GetReleases",
        published_at=newest.time,
        published_at_naive=True,
        vintage=newest.printed,
        request={"since": NEWEST},
    )
    assert kept == [], "a release at exactly since is no newer"
    assert (meta.vintage, meta.published_at) == (NEWEST, datetime(2026, 10, 22, 8, 30, 42, 670000))
    assert meta.request == {"since": NEWEST}, "the text as the caller gave it"


def test_since_none_keeps_every_item_and_reads_nothing() -> None:
    def never(text: str) -> datetime:
        raise AssertionError(f"read {text!r}, though since is None")

    kept = newer_than(None, RELEASES, released=released, read=never)
    assert kept == RELEASES, "every item, unchanged, in upstream's order"
    assert kept is not RELEASES, "a list of its own"


def test_the_times_are_compared_not_their_texts() -> None:
    """``42.50`` sorts after ``42.5`` as text and is the same time, so it is no newer."""
    same = Release("0401", "2026-10-22T08:30:42.50")
    later = Release("0402", "2026-10-22T08:30:42.51")
    kept = newer_than("2026-10-22T08:30:42.5", [same, later], released=released, read=read_since)
    assert codes(kept) == ["0402"]


def test_a_date_alone_is_its_midnight_as_the_reader_reads_it() -> None:
    kept = newer_than("2026-10-22", RELEASES, released=released, read=read_since)
    assert codes(kept) == ["0107", "0201"], "released on that day after 00:00"


@pytest.mark.parametrize(
    "since",
    ["not a time", "2026-10-22T25:00:00", "2026-10-22T08:30:42Z"],
    ids=["words", "hour_25", "zulu"],
)
def test_the_reader_s_refusal_passes_with_its_source(since: str) -> None:
    with pytest.raises(InvalidRequestError) as info:
        newer_than(since, RELEASES, released=released, read=read_since)
    assert str(info.value) == f"since must be a release time without a zone, got {since!r}."
    assert info.value.source == SOURCE, "the source's slug, which an HTTP problem names"


def test_an_unreadable_since_is_refused_over_an_empty_answer_too() -> None:
    with pytest.raises(InvalidRequestError, match="since must be a release time"):
        newer_than("not a time", [], released=released, read=read_since)


def test_since_is_read_once_before_any_item() -> None:
    reads: list[str] = []
    seen: list[str] = []

    def read(text: str) -> datetime:
        assert seen == [], "since is read before the first item"
        reads.append(text)
        return read_since(text)

    def items() -> Iterator[Release]:
        for release in RELEASES:
            seen.append(release.code)
            yield release

    kept = newer_than("2026-10-15T08:30:00", items(), released=released, read=read)
    assert codes(kept) == ["0107", "0201"], "any iterable, consumed once"
    assert reads == ["2026-10-15T08:30:00"]


def test_an_item_without_a_release_time_is_kept() -> None:
    """It cannot be shown to be no newer, and dropping it would hide it from every later call."""
    unknown = Release("0501", None)
    answer = [*RELEASES, unknown]
    assert codes(newer_than(NEWEST, answer, released=released, read=read_since)) == ["0501"]
    assert newer_than(None, answer, released=released, read=read_since) == answer


@dataclass(frozen=True)
class MonthRecord:
    """A record of a release list: a country and the month of its last release."""

    country_code: str
    release_year: int
    release_month: int


def release_month(record: MonthRecord) -> tuple[int, int]:
    return record.release_year, record.release_month


RELEASE_MONTH = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


def read_month(since: str) -> tuple[int, int]:
    """A source's own reader of its vintage text, a release month ``YYYY-MM``."""
    if not RELEASE_MONTH.fullmatch(since):
        raise InvalidRequestError(
            f"since must be a release month 'YYYY-MM' such as '2026-09', got {since!r}.",
            source="example",
        )
    return int(since[:4]), int(since[5:])


MONTHS = [
    MonthRecord("US", 2026, 10),
    MonthRecord("BR", 2026, 9),
    MonthRecord("E4", 2026, 10),
    MonthRecord("PK", 2022, 9),
]


def test_a_source_hands_its_own_reader_of_a_month() -> None:
    kept = newer_than("2026-09", MONTHS, released=release_month, read=read_month)
    assert [record.country_code for record in kept] == ["US", "E4"], "2026-09 itself is not kept"
    assert newer_than("2026-10", MONTHS, released=release_month, read=read_month) == []


def test_the_newest_release_is_kept_whole_or_not_at_all() -> None:
    """A source's ``get_latest_release``: the records of the newest release, if newer."""
    newest = max(release_month(record) for record in MONTHS)
    latest = [record for record in MONTHS if release_month(record) == newest]
    assert newer_than("2026-09", latest, released=release_month, read=read_month) == latest
    assert newer_than("2026-10", latest, released=release_month, read=read_month) == []


def test_a_reader_whose_value_does_not_compare_with_the_release_is_the_sources_fault() -> None:
    """A month read against releases that are times: no argument the caller could change.

    mypy accepts the pair, so the helper names both values and their types, as a
    ``TypeError`` of the source's code, never an ``InvalidRequestError`` that would tell the
    caller to change the request (conventions §5).
    """
    with pytest.raises(TypeError) as info:
        newer_than("2026-09", RELEASES, released=released, read=read_month)
    message = str(info.value)
    assert message.startswith(
        "newer_than compares each release with read(since): released gave "
        "datetime.datetime(2026, 10, 15, 8, 30), a datetime, and read gave (2026, 9), a tuple, "
        "which do not compare ("
    )
    hint = "). Hand it a reader that reads since into the form released gives."
    assert message.endswith(hint), "core ships no reader of a vintage text to name (ADR-0059)"
    assert isinstance(info.value.__cause__, TypeError), "the comparison's own error, chained"
    assert not isinstance(info.value, XippiosError)


def test_an_aware_release_against_a_naive_reader_is_the_sources_fault() -> None:
    aware = Release("0601", "2026-10-22T08:30:00+00:00")
    with pytest.raises(TypeError, match="which do not compare") as info:
        newer_than("2026-10-15T08:30:00", [aware], released=released, read=read_since)
    assert "tzinfo=datetime.timezone.utc), a datetime, and read gave datetime.datetime(" in str(
        info.value
    ), "the two times as given, so the missing zone shows"


def test_the_sources_refusal_passes_as_the_reader_raised_it() -> None:
    with pytest.raises(InvalidRequestError) as info:
        newer_than("2026-13", MONTHS, released=release_month, read=read_month)
    assert str(info.value) == (
        "since must be a release month 'YYYY-MM' such as '2026-09', got '2026-13'."
    ), "the reader's own wording, its class unchanged"
    assert info.value.source == "example"
