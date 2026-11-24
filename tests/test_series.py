"""A series over periods: the ceiling of one call and its requests in order (ADR-0054, #315).

The row's proof first: a range over the ceiling is refused before a request, saying that
nothing was sent, a period without data is skipped, and a failure in the third of five periods
names the two answered. Then the MCP server's lower ceiling through the tool set's hooks, the
option that raises it, an empty range, a failure in the first period, every period skipped, a
pass that counts, and what a failure keeps of the error: its instance, class, attributes, cause
and traceback. The words "Nothing was sent" and "answered" are those of ADR-0054's amendment of
2026-11-22 (https://github.com/xippios/sdk-core/issues/438).
"""

import argparse
import pickle
from collections.abc import Awaitable, Callable

import pytest

from xippios.core import (
    Ceiling,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
    XippiosError,
    fetch_periods,
)
from xippios.core.data_gov import NoDataForYear
from xippios.core.mcp import ToolSet, build_parser, main

SOURCE = "example"


def market_years() -> Ceiling:
    """A ceiling of the task's own, the same in Python, over HTTP and over MCP."""
    return Ceiling(10, unit="market years", source=SOURCE)


def months() -> Ceiling:
    """A ceiling lowered on the MCP server, with its option, as sdk-usda-gats declares it."""
    return Ceiling(
        60,
        unit="months",
        mcp=24,
        option="--series-months",
        help="one request per month, so 60 months take about a minute of calls",
        source=SOURCE,
    )


class Upstream:
    """One answer per period, the periods it was asked for in order, and what each raises."""

    def __init__(self, raises: dict[int, BaseException] | None = None) -> None:
        self.asked: list[int] = []
        self.raises = raises or {}
        self.running = 0

    async def fetch(self, year: int) -> list[str]:
        assert self.running == 0, "one request at a time"
        self.running += 1
        try:
            self.asked.append(year)
            if year in self.raises:
                raise self.raises[year]
            return [f"{year}-a", f"{year}-b"]
        finally:
            self.running -= 1


def no_data(year: int) -> NoDataForYear:
    return NoDataForYear(f"/api/example/year/{year}", source=SOURCE)


def unavailable(year: int) -> UpstreamError:
    return UpstreamError(
        f"503 from GET /api/example/year/{year}: Service Unavailable",
        status=503,
        body="Service Unavailable",
        source=SOURCE,
    )


async def series(
    ceiling: Ceiling, fetch: Callable[[int], Awaitable[list[str]]], start: int, end: int
) -> list[tuple[int, list[str]]]:
    """A task's series: the range checked before the first request, then the requests."""
    ceiling.check(end - start + 1, asked=f"{start} to {end}")
    return await fetch_periods(range(start, end + 1), fetch, skip=(NoDataForYear,))


# The row's proof


@pytest.mark.anyio
async def test_a_range_over_the_ceiling_is_refused_before_a_request() -> None:
    upstream = Upstream()
    with pytest.raises(InvalidRequestError) as info:
        await series(market_years(), upstream.fetch, 2010, 2021)
    assert info.value.message == (
        "2010 to 2021 is 12 market years; one call fetches at most 10 market years. Nothing was "
        "sent. Ask for fewer market years."
    )
    assert info.value.source == SOURCE
    assert upstream.asked == [], "refused before any request"


@pytest.mark.anyio
async def test_a_range_at_the_ceiling_is_fetched_whole() -> None:
    upstream = Upstream()
    fetched = await series(market_years(), upstream.fetch, 2012, 2021)
    assert [year for year, _ in fetched] == list(range(2012, 2022))
    assert upstream.asked == list(range(2012, 2022))


@pytest.mark.anyio
async def test_a_period_without_data_is_skipped() -> None:
    upstream = Upstream({2022: no_data(2022)})
    fetched = await series(market_years(), upstream.fetch, 2021, 2023)
    assert fetched == [(2021, ["2021-a", "2021-b"]), (2023, ["2023-a", "2023-b"])]
    assert upstream.asked == [2021, 2022, 2023], "one request per period, in order"


@pytest.mark.anyio
async def test_a_failure_in_the_third_of_five_periods_names_the_two_answered() -> None:
    error = unavailable(2023)
    upstream = Upstream({2023: error})
    with pytest.raises(UpstreamError) as info:
        await series(market_years(), upstream.fetch, 2021, 2025)
    assert info.value is error, "the same error, raised again"
    assert info.value.message == (
        "503 from GET /api/example/year/2023: Service Unavailable. The series stopped at 2023 "
        "after 2 periods answered, 2021 to 2022, and returns nothing."
    )
    assert upstream.asked == [2021, 2022, 2023], "no request after the failure"


# The ceiling: the MCP server's lower one, the option that raises it, and the Python API's


def test_the_python_api_holds_most_and_its_refusal_names_no_mcp_server() -> None:
    ceiling = months()
    assert (ceiling.most, ceiling.mcp, ceiling.value) == (60, 24, 60)
    ceiling.check(60)
    with pytest.raises(InvalidRequestError) as info:
        ceiling.check(61, asked="2021-08 to 2026-08")
    assert info.value.message == (
        "2021-08 to 2026-08 is 61 months; one call fetches at most 60 months. Nothing was sent. "
        "Ask for fewer months."
    )


def test_the_mcp_servers_lower_ceiling_comes_through_the_tool_sets_hooks() -> None:
    """A host applies a tool set's hooks with ``option_defaults()``, as the entry point does
    without options: the ceiling in force is then the MCP server's, for the whole process."""
    ceiling = months()
    tools = ToolSet(
        SOURCE, [], add_options=ceiling.add_options, apply_options=ceiling.apply_options
    )
    assert tools.apply_options is not None
    assert tools.apply_options(tools.option_defaults()) is None
    assert ceiling.value == 24
    ceiling.check(24)
    with pytest.raises(InvalidRequestError) as info:
        ceiling.check(25, asked="2024-08 to 2026-08")
    assert info.value.message == (
        "2024-08 to 2026-08 is 25 months; one call fetches at most 24 months, the ceiling set "
        "for this process (the MCP server starts with 24 by default; --series-months raises "
        "it, up to 60). Nothing was sent. Ask for fewer months."
    )


def test_the_option_raises_the_ceiling_up_to_most(monkeypatch: pytest.MonkeyPatch) -> None:
    """The option keeps the source's name and its unit, and its help names the range, the
    default and the source's text. The help is compared as plain text, so the test pins its
    colors and its width."""
    monkeypatch.setenv("PYTHON_COLORS", "0")
    monkeypatch.setenv("COLUMNS", "100")
    ceiling = months()
    parser = build_parser("xippios-example-mcp", add_options=ceiling.add_options)
    assert parser.parse_args([]).series_months == 24
    namespace = parser.parse_args(["--series-months", "36"])
    ceiling.apply_options(namespace)
    assert ceiling.value == 36
    with pytest.raises(InvalidRequestError) as info:
        ceiling.check(37)
    assert info.value.message == (
        "37 months asked; one call fetches at most 36 months, the ceiling set for this process "
        "(the MCP server starts with 24 by default; --series-months raises it, up to 60). "
        "Nothing was sent. Ask for fewer months."
    )
    assert (
        "--series-months MONTHS most months one tool call fetches, 1 to 60 (default 24); one "
        "request per month, so 60 months take about a minute of calls"
    ) in " ".join(parser.format_help().split())


def test_an_option_past_most_stops_the_entry_point_with_status_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ceiling = months()
    tools = ToolSet(
        SOURCE, [], add_options=ceiling.add_options, apply_options=ceiling.apply_options
    )
    with pytest.raises(SystemExit) as info:
        main(lambda: tools, argv=["--series-months", "61"])
    assert info.value.code == 2
    assert (
        "the series ceiling, --series-months on the MCP server, must be a whole number of "
        "months from 1 to 60, got 61."
    ) in capsys.readouterr().err
    assert ceiling.value == 60, "the ceiling stays as it was"


@pytest.mark.parametrize("value", [1, 24, 60])
def test_set_takes_1_to_most(value: int) -> None:
    ceiling = months()
    ceiling.set(value)
    assert ceiling.value == value


@pytest.mark.parametrize("value", [0, 61, -24, True, "24", 24.0, None])
def test_set_refuses_anything_else_and_keeps_the_ceiling(value: object) -> None:
    ceiling = months()
    ceiling.set(36)
    with pytest.raises(InvalidRequestError) as info:
        ceiling.set(value)  # type: ignore[arg-type]
    assert info.value.message == (
        "the series ceiling, --series-months on the MCP server, must be a whole number of "
        f"months from 1 to 60, got {value!r}."
    )
    assert info.value.source == SOURCE
    assert ceiling.value == 36


def test_a_ceiling_without_an_option_adds_none_and_its_hooks_change_nothing() -> None:
    ceiling = market_years()
    parser = build_parser("xippios-example-mcp", add_options=ceiling.add_options)
    assert vars(parser.parse_args([])) == vars(build_parser("xippios-example-mcp").parse_args([]))
    ceiling.apply_options(parser.parse_args([]))
    assert ceiling.value == 10


def test_a_ceiling_set_without_an_option_says_so_and_names_no_server() -> None:
    ceiling = market_years()
    ceiling.set(5)
    with pytest.raises(InvalidRequestError) as info:
        ceiling.check(6, asked="2020 to 2025", advice="Narrow the range, e.g. 2021 to 2025.")
    assert info.value.message == (
        "2020 to 2025 is 6 market years; one call fetches at most 5 market years, the ceiling "
        "set for this process. Nothing was sent. Narrow the range, e.g. 2021 to 2025."
    ), "the sentence stands before the source's advice too"
    with pytest.raises(InvalidRequestError) as unset:
        ceiling.set(11)
    assert unset.value.message == (
        "the series ceiling must be a whole number of market years from 1 to 10, got 11."
    )


@pytest.mark.parametrize(
    ("arguments", "says"),
    [
        ({"most": 0}, "most"),
        ({"most": True}, "most"),
        ({"most": 60, "mcp": 24}, "mcp and option"),
        ({"most": 60, "option": "--series-months"}, "mcp and option"),
        ({"most": 60, "mcp": 0, "option": "--series-months"}, "mcp"),
        ({"most": 60, "mcp": 61, "option": "--series-months"}, "mcp"),
        ({"most": 60, "mcp": 24, "option": "series-months"}, "option"),
        ({"most": 60, "mcp": 24, "option": "-m"}, "option"),
        ({"most": 60, "help": "one request per month"}, "help"),
    ],
)
def test_a_declaration_that_cannot_hold_is_refused(arguments: dict[str, object], says: str) -> None:
    """A fault of the source's code, raised where the ceiling is declared."""
    with pytest.raises(ValueError, match=says):
        Ceiling(unit="months", **arguments)  # type: ignore[arg-type]


# The loop: an empty range, every period skipped, a failure in the first period


@pytest.mark.anyio
async def test_an_empty_range_sends_no_request_and_returns_nothing() -> None:
    upstream = Upstream()
    assert await fetch_periods([], upstream.fetch) == []
    assert upstream.asked == []


@pytest.mark.anyio
async def test_every_period_skipped_is_an_empty_list() -> None:
    upstream = Upstream({year: no_data(year) for year in (1900, 1901, 1902)})
    assert await fetch_periods([1900, 1901, 1902], upstream.fetch, skip=(NoDataForYear,)) == []
    assert upstream.asked == [1900, 1901, 1902]


@pytest.mark.anyio
async def test_a_failure_in_the_first_period_passes_as_raised() -> None:
    error = unavailable(2021)
    message = error.message
    upstream = Upstream({2021: error})
    with pytest.raises(UpstreamError) as info:
        await fetch_periods([2021, 2022], upstream.fetch, skip=(NoDataForYear,))
    assert info.value is error
    assert info.value.message == message, "nothing was answered before it"
    assert getattr(info.value, "__notes__", []) == []
    assert upstream.asked == [2021]


@pytest.mark.anyio
async def test_a_period_skipped_counts_as_answered() -> None:
    """Upstream answered it, with no data, so a caller starts again after it."""
    upstream = Upstream({2021: no_data(2021), 2022: no_data(2022), 2023: unavailable(2023)})
    with pytest.raises(UpstreamError) as info:
        await fetch_periods([2021, 2022, 2023], upstream.fetch, skip=(NoDataForYear,))
    assert info.value.message.endswith(
        "The series stopped at 2023 after 2 periods answered, 2021 to 2022, and returns nothing."
    )


@pytest.mark.anyio
async def test_one_period_answered_is_named_alone() -> None:
    upstream = Upstream({2022: unavailable(2022)})
    with pytest.raises(UpstreamError) as info:
        await fetch_periods([2021, 2022], upstream.fetch)
    assert info.value.message.endswith(
        "The series stopped at 2022 after 1 period answered, 2021, and returns nothing."
    )


@pytest.mark.anyio
async def test_a_pass_that_counts_names_the_periods_counted_as_answered() -> None:
    """sdk-usda-nass's split counts every year on the loop before it fetches one, so the
    periods before a failed count were counted and never fetched: the sentence holds for
    both passes (https://github.com/xippios/sdk-usda-nass/issues/86)."""
    error = unavailable(2021)
    counted: list[int] = []

    async def count(year: int) -> int:
        if year == 2021:
            raise error
        counted.append(year)
        return 12

    with pytest.raises(UpstreamError) as info:
        await fetch_periods([2020, 2021, 2022], count)
    assert info.value is error
    assert info.value.message == (
        "503 from GET /api/example/year/2021: Service Unavailable. The series stopped at 2021 "
        "after 1 period answered, 2020, and returns nothing."
    )
    assert counted == [2020]


@pytest.mark.anyio
async def test_only_the_classes_of_skip_are_passed_over() -> None:
    """The gateway's own 404, a ``NotFoundError`` that is no ``NoDataForYear``, is raised."""
    gone = NotFoundError("404 from GET /api/example/year/2022: NOT_FOUND", source=SOURCE)
    upstream = Upstream({2022: gone})
    with pytest.raises(NotFoundError) as info:
        await fetch_periods([2021, 2022, 2023], upstream.fetch, skip=(NoDataForYear,))
    assert info.value is gone
    assert info.value.message == (
        "404 from GET /api/example/year/2022: NOT_FOUND. The series stopped at 2022 after 1 "
        "period answered, 2021, and returns nothing."
    )
    assert upstream.asked == [2021, 2022]


@pytest.mark.anyio
async def test_a_long_series_names_the_first_the_last_and_the_count() -> None:
    periods = [f"{year}{month:02d}" for year in range(2021, 2026) for month in range(1, 13)]

    async def fetch(period: str) -> list[str]:
        if period == "202512":
            raise RateLimitError("429 from GET /api/example: spent", retry_after=60.0)
        return [period]

    with pytest.raises(RateLimitError) as info:
        await fetch_periods(periods, fetch)
    assert info.value.message == (
        "429 from GET /api/example: spent. The series stopped at 202512 after 59 periods "
        "answered, 202101 to 202511, and returns nothing."
    )
    assert "202306" not in info.value.message, "not sixty periods"
    assert info.value.retry_after == 60.0


# What a later failure keeps of the error


@pytest.mark.anyio
async def test_a_later_failure_keeps_the_class_the_attributes_the_cause_and_the_traceback() -> None:
    cause = ConnectionResetError("reset by peer")

    async def fetch(year: int) -> list[str]:
        if year == 2023:
            raise unavailable(2023) from cause
        return [str(year)]

    with pytest.raises(UpstreamError) as info:
        await fetch_periods([2021, 2022, 2023, 2024], fetch)
    error = info.value
    assert type(error) is UpstreamError
    assert (error.status, error.body, error.source) == (503, "Service Unavailable", SOURCE)
    assert error.__cause__ is cause
    assert any(entry.name == "fetch" for entry in info.traceback), "the raising frame stays"
    longer = error.message
    assert longer.endswith("after 2 periods answered, 2021 to 2022, and returns nothing.")
    assert (str(error), error.args) == (longer, (longer,)), "what both adapters and repr read"
    copy = pickle.loads(pickle.dumps(error))  # the taxonomy's __reduce__ keeps the message
    assert (type(copy), copy.message, copy.status) == (UpstreamError, longer, 503)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("message", "opening"),
    [
        ("The upstream refused the request.", "The upstream refused the request. "),
        ("The upstream refused the request.  ", "The upstream refused the request. "),
        ("404 from GET /x/2022: Did you mean 2021?", "404 from GET /x/2022: Did you mean 2021? "),
        ("429 from GET /x: Slow down!", "429 from GET /x: Slow down! "),
        ("429 from GET /x: Slow down!\n", "429 from GET /x: Slow down! "),
        # any other last character takes a full stop: a word, a closing quote or bracket
        ("503 from GET /x: Service Unavailable", "503 from GET /x: Service Unavailable. "),
        ("503 from GET /x: (retry later)", "503 from GET /x: (retry later). "),
        ("got 'weekEndingDate'", "got 'weekEndingDate'. "),
        ("got ['2021', '2022?']", "got ['2021', '2022?']. "),
        ('400 from GET /x: "Try again later."', '400 from GET /x: "Try again later.". '),
        ('429 from GET /x: {"error": "Later."}', '429 from GET /x: {"error": "Later."}. '),
        # nothing to end
        ("", ""),
        ("  ", ""),
    ],
)
async def test_a_message_that_ends_its_sentence_takes_the_next_one_after_a_space(
    message: str, opening: str
) -> None:
    """A message whose last character, past its trailing white space, is ``.``, ``?`` or
    ``!`` ended its sentence. Any other last character takes a full stop: a closing quote or
    bracket closes a value, a repr, a JSON body or upstream's quoted text, whose own
    punctuation is the value's, so the stop ends the sentence after it."""
    error = XippiosError(message, source=SOURCE)
    upstream = Upstream({2022: error})
    with pytest.raises(XippiosError) as info:
        await fetch_periods([2021, 2022], upstream.fetch)
    assert info.value.message == (
        f"{opening}The series stopped at 2022 after 1 period answered, 2021, and returns nothing."
    )
    assert info.value.args == (info.value.message,)


@pytest.mark.anyio
async def test_an_error_that_is_no_xippios_error_keeps_its_arguments_and_gets_a_note() -> None:
    error = KeyError("weekEndingDate")
    upstream = Upstream({2023: error})
    with pytest.raises(KeyError) as info:
        await fetch_periods([2021, 2022, 2023], upstream.fetch)
    assert info.value is error
    assert info.value.args == ("weekEndingDate",)
    assert info.value.__notes__ == [
        "The series stopped at 2023 after 2 periods answered, 2021 to 2022, and returns nothing."
    ]


class Stop(BaseException):
    """No ``Exception``: a cancellation, an interrupt."""


@pytest.mark.anyio
async def test_a_cancellation_passes_untouched() -> None:
    stop = Stop("cancelled")
    upstream = Upstream({2022: stop})
    with pytest.raises(Stop) as info:
        await fetch_periods([2021, 2022], upstream.fetch)
    assert info.value is stop
    assert info.value.args == ("cancelled",)
    assert getattr(info.value, "__notes__", []) == []


def test_the_hooks_fit_a_tool_set_and_take_no_server() -> None:
    """``apply_options`` takes the parsed options alone and returns nothing, so a tool set
    takes both hooks as they are (https://github.com/xippios/sdk-core/issues/485, part 1)."""
    ceiling = months()
    ceiling.apply_options(argparse.Namespace(series_months=12))
    assert ceiling.value == 12
    tools = ToolSet(SOURCE, [], apply_options=ceiling.apply_options)
    assert tools.apply_options is not None
    tools.apply_options(argparse.Namespace(series_months=13))
    assert ceiling.value == 13
