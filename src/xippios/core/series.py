"""A series over periods: the ceiling of one call and its requests in order (ADR-0054).

A task that assembles a period series from one upstream call per period (conventions §4)
declares its ceiling once, a ``Ceiling``, checks the range against it before the first
request, and sends the requests with ``fetch_periods``, which returns each period with its
answer for the task to assemble, its vintage included::

    from xippios.core import Ceiling, fetch_periods
    from xippios.core.data_gov import NoDataForYear

    SERIES = Ceiling(10, unit="market years", source="usda-esr")


    async def get_weekly_series_async(...) -> Result[list[CommodityData]]:
        SERIES.check(end_year - start_year + 1, asked=f"{start_year} to {end_year}")
        ...  # a release list, or a count, may come between the two
        fetched = await fetch_periods(
            range(start_year, end_year + 1),
            lambda year: api.get_country_data(commodity_code, country_code, year),
            skip=(NoDataForYear,),
        )
        records = [record for _, answer in fetched for record in answer]

The two stay apart, since a task may send a request between them, and a range over the
ceiling is still refused before any request.
"""

import argparse
from collections.abc import Awaitable, Callable, Iterable

from xippios.core.errors import InvalidRequestError, XippiosError

__all__ = ["Ceiling", "fetch_periods"]


def _whole(value: object) -> bool:
    """``value`` is an ``int`` and no ``bool``: ``True`` is not ``1`` here."""
    return isinstance(value, int) and not isinstance(value, bool)


class Ceiling:
    """The most periods one call of a period series fetches, with its check (ADR-0054).

    ``most`` holds in Python and over HTTP, and no ceiling goes above it. A source whose MCP
    server fetches fewer declares ``mcp``, the ceiling the server starts with, and
    ``option``, the command-line option that sets another from 1 to ``most``.
    ``add_options`` and ``apply_options`` are ``main``'s two hooks for that option, which the
    source's tool set carries, so a host that applies a tool set's hooks with
    ``option_defaults()`` serves ``mcp`` as the entry point does. The ceiling in force,
    ``value``, is the process's, as a module of the source holds the ceiling:
    ``apply_options`` sets it for every call in the process, from Python and over HTTP too,
    one MCP server per process::

        SERIES = Ceiling(
            60,
            unit="months",
            mcp=24,
            option="--series-months",
            help="one request per month, so 60 months take about a minute of calls",
            source="usda-gats",
        )
        mcp_add_options = SERIES.add_options  # the tool set's hooks
        mcp_apply_options = SERIES.apply_options

    Args:
        most: The most periods one call fetches in Python and over HTTP, a whole number
            from 1, e.g. ``60``.
        unit: What the periods are, in the plural, as the refusals name them, e.g.
            ``"months"``, ``"market years"``.
        mcp: The ceiling the MCP server starts with, from 1 to ``most``, e.g. ``24``; given
            with ``option``. ``None``, the default, where the server fetches ``most`` too.
        option: The long option that sets the MCP server's ceiling, e.g.
            ``"--series-months"``, whose value argparse keeps under its name with ``_`` for
            ``-``, ``series_months``; given with ``mcp``.
        help: What the option's help says after its range and default, e.g. ``"one request
            per month, so 60 months take about a minute of calls"``; ``None`` for nothing.
        source: Source slug, which the refusals carry, e.g. ``"usda-gats"``.

    Attributes:
        most: As given.
        unit: As given.
        mcp: As given.
        option: As given.
        help: As given.
        source: As given.

    Raises:
        ValueError: ``most`` is no whole number from 1, one of ``mcp`` and ``option`` comes
            without the other, ``mcp`` lies outside 1 to ``most``, ``option`` is no long
            option, or ``help`` comes without ``option``: a fault of the source's code.
    """

    __slots__ = ("_dest", "_value", "help", "mcp", "most", "option", "source", "unit")

    def __init__(
        self,
        most: int,
        *,
        unit: str,
        mcp: int | None = None,
        option: str | None = None,
        help: str | None = None,
        source: str | None = None,
    ) -> None:
        if not _whole(most) or most < 1:
            raise ValueError(f"most must be a whole number of {unit} from 1, got {most!r}")
        if (mcp is None) != (option is None):
            raise ValueError(
                "mcp and option come together: the MCP server's ceiling and the option that "
                f"sets another, e.g. mcp=24, option='--series-months'; got mcp={mcp!r}, "
                f"option={option!r}"
            )
        if mcp is not None and (not _whole(mcp) or not 1 <= mcp <= most):
            raise ValueError(f"mcp must be a whole number from 1 to most, {most}, got {mcp!r}")
        if option is not None and (not option.startswith("--") or len(option) < 3):
            raise ValueError(
                f"option must be a long option, e.g. '--series-months', got {option!r}"
            )
        if help is not None and option is None:
            raise ValueError("help is the option's: it comes with mcp and option")
        self.most = most
        self.unit = unit
        self.mcp = mcp
        self.option = option
        self.help = help
        self.source = source
        self._dest = None if option is None else option[2:].replace("-", "_")
        self._value = most

    @property
    def value(self) -> int:
        """The ceiling in force in this process: ``most`` until ``set`` sets another."""
        return self._value

    def set(self, value: int) -> None:
        """Set the ceiling in force for every call in this process, from 1 to ``most``.

        ``apply_options`` calls it with the option's value, and a test that sets it sets
        ``most`` again after it.

        Args:
            value: A whole number from 1 to ``most``, e.g. ``24``.

        Raises:
            InvalidRequestError: ``value`` is no whole number from 1 to ``most`` (``True`` is
                not ``1``), naming the option where one is declared: ``the series ceiling,
                --series-months on the MCP server, must be a whole number of months from 1
                to 60, got 61.`` The ceiling stays as it was.
        """
        if not _whole(value) or not 1 <= value <= self.most:
            named = "" if self.option is None else f", {self.option} on the MCP server,"
            raise InvalidRequestError(
                f"the series ceiling{named} must be a whole number of {self.unit} from 1 to "
                f"{self.most}, got {value!r}.",
                source=self.source,
            )
        self._value = value

    def check(self, count: int, *, asked: str | None = None, advice: str | None = None) -> None:
        """Refuse a range of more periods than the ceiling in force, before the first request.

        A task calls it before any request of the call, which makes the refusal's
        ``Nothing was sent.`` true: a task that checks a range only after a request of the
        call, as sdk-usda-nass's split of ``year__GE`` alone after its count of the range,
        words that refusal itself and says what was sent (ADR-0054, amendment 2026-11-22).

        The refusal is the caller's ``InvalidRequestError``: the range as the task names it,
        or else the count asked, then the ceiling in force with its unit, and, below
        ``most``, that it is the ceiling set for this process, with the MCP server's default
        and the option that raises it where one is declared. It then says that nothing was
        sent, as a refusal of the call as given does (conventions §5), and ends with its
        advice::

            2024-08 to 2026-08 is 25 months; one call fetches at most 24 months, the ceiling
            set for this process (the MCP server starts with 24 by default; --series-months
            raises it, up to 60). Nothing was sent. Ask for fewer months.

        Args:
            count: The periods the call would fetch, e.g. ``len(months)``.
            asked: The range as the task names it, which the refusal opens with, e.g.
                ``"2024-08 to 2026-08"``; ``None`` names the count alone, ``25 months
                asked``.
            advice: The sentence that closes the refusal, after ``Nothing was sent.``, e.g.
                ``"Give a shorter range, e.g. year__GE=2021 with year__LE=2025."``, written
                with ``value`` where it names a bound; ``Ask for fewer <unit>.`` by default.

        Raises:
            InvalidRequestError: ``count`` is over ``value``; nothing was sent, since the
                task calls ``check`` before any request of the call.
        """
        ceiling = self._value
        if count <= ceiling:
            return
        opening = (
            f"{count} {self.unit} asked" if asked is None else f"{asked} is {count} {self.unit}"
        )
        bound = f"one call fetches at most {ceiling} {self.unit}"
        if ceiling < self.most:
            bound += ", the ceiling set for this process"
            if self.option is not None:
                bound += (
                    f" (the MCP server starts with {self.mcp} by default; {self.option} "
                    f"raises it, up to {self.most})"
                )
        closing = advice or f"Ask for fewer {self.unit}."
        raise InvalidRequestError(
            f"{opening}; {bound}. Nothing was sent. {closing}", source=self.source
        )

    def add_options(self, parser: argparse.ArgumentParser) -> None:
        """Add ``option`` to the MCP server's command line, a hook of ``main``.

        The option takes a whole number, ``mcp`` when not given, checked when it is applied,
        and its help reads ``most <unit> one tool call fetches, 1 to <most> (default <mcp>)``
        and then ``help``. A ceiling without an option adds nothing.

        Args:
            parser: Core's parser (``xippios.core.mcp.build_parser``), which then accepts
                e.g. ``--series-months 36``.
        """
        if self.option is None:
            return
        text = f"most {self.unit} one tool call fetches, 1 to {self.most} (default {self.mcp})"
        if self.help is not None:
            text += f"; {self.help}"
        parser.add_argument(
            self.option,
            type=int,
            default=self.mcp,
            dest=self._dest,
            metavar=self.unit.upper().replace(" ", "_"),
            help=text.replace("%", "%%"),  # argparse formats its help with %
        )

    def apply_options[S](self, namespace: argparse.Namespace, server: S) -> S:
        """Set the ceiling in force from ``option``, a hook of ``main``; return ``server``.

        A ceiling without an option changes nothing.

        Args:
            namespace: The parsed command line, e.g. ``argparse.Namespace(series_months=24)``,
                or a tool set's ``option_defaults()``.
            server: The server to run, returned as it is.

        Raises:
            InvalidRequestError: The option's value is outside 1 to ``most`` (``set``), which
                ``main`` turns into its error: the message on stderr, exit status 2, nothing
                served.
        """
        if self._dest is not None:
            self.set(getattr(namespace, self._dest))
        return server


def _named(periods: list[object]) -> str:
    """The periods answered by their count, the first and the last: never sixty of them.

    Answered, not fetched: a pass of counts on the loop counted them, and a period passed
    over held no data, yet upstream answered each (ADR-0054, amendment 2026-11-22).
    """
    if len(periods) == 1:
        return f"1 period answered, {periods[0]}"
    return f"{len(periods)} periods answered, {periods[0]} to {periods[-1]}"


def _stopped(error: Exception, period: object, answered: list[object]) -> None:
    """Name in ``error`` the periods answered before ``period``, whose fetch raised it.

    A ``XippiosError``'s message, and the argument that holds it, are extended in place,
    the two that ``str``, ``repr`` and both adapters read; any other error keeps its
    arguments, its class's own, and gets the sentence as a note (PEP 678). A message whose
    last character, past its trailing white space, is ``.``, ``?`` or ``!`` ended its
    sentence; any other takes a full stop first, a closing quote or bracket included, since
    it closes a value whose own punctuation is the value's. An empty message is the sentence.
    """
    sentence = f"The series stopped at {period} after {_named(answered)}, and returns nothing."
    if not isinstance(error, XippiosError):
        error.add_note(sentence)
        return
    message = error.message.rstrip()
    if message and message[-1] not in ".?!":
        message += "."  # the error's own sentence ends before the next one starts
    longer = f"{message} {sentence}".lstrip()
    error.args = tuple(longer if arg == error.message else arg for arg in error.args)
    error.message = longer


async def fetch_periods[P, T](
    periods: Iterable[P],
    fetch: Callable[[P], Awaitable[T]],
    *,
    skip: tuple[type[XippiosError], ...] = (),
) -> list[tuple[P, T]]:
    """Fetch each period in order, one request after another, and return them with their answers.

    The requests of a period series (conventions §4; ADR-0054): ``fetch(period)`` for each
    period in the order given, each awaited before the next, so the client's rate limiter
    and quota policy pace them and nothing runs at once. A period whose fetch raises one of
    ``skip``, upstream's answer for a period without data that can be told from data, is
    passed over. The task checks the range with its ``Ceiling`` before, and assembles the
    answers after, its vintage included: the helper derives nothing from them.

    When a fetch raises anything else, the helper returns nothing and raises that error
    again, the same instance, its class, its attributes, its cause and its traceback kept.
    After the first period its message also names the periods answered before it, those
    passed over included, by their count, the first and the last, each as its ``str``
    gives it. Answered holds for a pass that fetches and for one that counts, as a task may
    run the loop over its counts before its data::

        503 from GET /api/esr/exports/commodityCode/104/allCountries/marketYear/2023:
        Service Unavailable. The series stopped at 2023 after 2 periods answered, 2021 to
        2022, and returns nothing.

    An error that is no ``XippiosError`` keeps its arguments and gets that sentence as a
    note, which a traceback prints; a cancellation, no ``Exception``, passes untouched. A
    failure in the first period passes as raised, since nothing was answered before it.

    Args:
        periods: The periods, oldest first as a series runs, each named by its ``str`` in a
            failure's message, e.g. ``range(2021, 2026)`` or ``["202607", "202608"]``; none
            sends no request.
        fetch: The request of one period, e.g. ``lambda year: api.get_country_data(104,
            1220, year)``.
        skip: The errors that say a period holds no data, e.g. ``(NoDataForYear,)``; empty,
            the default, passes over no period.

    Returns:
        Each period that was not passed over with its answer, in the order given, e.g.
        ``[(2021, [...]), (2023, [...])]``; empty for no period, or when every period was
        passed over.
    """
    answered: list[object] = []
    fetched: list[tuple[P, T]] = []
    for period in periods:
        try:
            answer = await fetch(period)
        except skip:
            answered.append(period)
            continue
        except Exception as error:
            if answered:
                _stopped(error, period, answered)
            raise
        answered.append(period)
        fetched.append((period, answer))
    return fetched
