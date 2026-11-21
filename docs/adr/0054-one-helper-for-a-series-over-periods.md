# ADR-0054: One helper for a series over periods

Status: Accepted · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/373

## Context

ADR-0041, decisions 6 and 7, and conventions §4 state the rules of a task that assembles a
period series from one upstream call per period: it states its ceiling, the most periods one
call fetches, lower for the MCP tool where it is smaller, skips a period whose empty answer can
be told from data, refuses the whole range where it cannot with `NotFoundError` naming the
latest released period, and sets `vintage` to the newest release among the periods. Core gives
the rules no code, and five sources write the loop
(https://github.com/xippios/sdk-core/issues/315):

- sdk-usda-esr's `get_weekly_series` and sdk-usda-psd's `get_time_series` fetch market years,
  at most 10 and 100, and skip a year that answers core's `NoDataForYear`.
- sdk-usda-gats's Census series fetch months, at most 60 in Python and over HTTP and 24 on the
  MCP server, and sdk-usda-nass's `get_data(split_by_year=True)` fetches years, at most 20 and
  5 there. Each carries its process-wide ceiling with its command-line option, `--series-months`
  and `--split-years`, through `main`'s option hooks (ADR-0026, amendment 2026-11-18, point d),
  in 91 lines that are the same but for their names and numbers.
- sdk-comtrade's `get_commodity_series` sends a caller's list of periods 12 a call, at most 120,
  its ceiling checked among every other problem of the call in `validate_slice`.

Three of them send a request between the check of the range and the loop: sdk-usda-esr and
sdk-usda-gats read a release list, and sdk-usda-nass counts every year before it fetches one.
The vintage is derived three ways: from the rows, from the rows after a filter, and from a
release list apart from the answers. When a later request fails, all five return nothing, and
two docstrings say so, but none says which periods were fetched before it.

This record stands beside ADR-0041, decisions 6 and 7, and changes none of their rules: those
decisions keep the rules of a period series, and this record gives the ceiling, the loop and a
later failure their code. A change to a rule is ADR-0041's, a change to the helper this
record's. Decisions 1 to 4 are the answer of https://github.com/xippios/sdk-core/issues/373,
and decisions 5 to 7 are those of the pull request that built the helper.

## Decision

1. **The ceiling and the loop are two pieces of a new module.** `xippios.core.series` holds
   `Ceiling` and `fetch_periods`, both exported from `xippios.core`, a module of its own by
   ADR-0029, decision 1. They stay apart, so a task sends its release list or its counts
   between the check and the first request of the loop, and a range over the ceiling is still
   refused before any request.
2. **The ceiling is lowered on the MCP server through the option hooks of today.**
   `Ceiling(most, *, unit, mcp=None, option=None)` holds `most` in Python and over HTTP, and a
   source whose MCP server fetches fewer declares `mcp`, the ceiling the server starts with,
   and `option`, the option that sets another from 1 to `most`. Its `add_options` and
   `apply_options` are `main`'s two hooks, which the source's tool set carries, so a host that
   applies a tool set's hooks with `option_defaults()` serves `mcp` as the entry point does.
   The ceiling in force is the process's, as the two copies hold it: `apply_options` sets it
   for every call in the process. Core's `main` gains no option, and each source keeps its
   option's name and its numbers, since months and years take no one number.
3. **A later failure raises the same error, naming the periods fetched, and returns nothing.**
   `fetch_periods(periods, fetch, *, skip=())` sends one request per period, in the order
   given, each awaited before the next, passes over a period whose fetch raises one of `skip`,
   and returns the periods with their answers. When the fetch of a period after the first
   raises, the helper raises that error again, the same instance, so its class, its attributes,
   its cause and its traceback stay, with a message that also names the periods fetched before
   it, and returns nothing. The adapters pass the message alone, so an error that carried the
   answers would serve a Python caller and no other, and a partial answer would reverse the two
   sources' rule that a range is refused whole.
4. **The vintage stays the task's.** The helper returns what the task needs to derive the
   vintage, the periods with their answers, and derives nothing, since the three derivations
   share no input. This departs from the wording of
   https://github.com/xippios/sdk-core/issues/315, which gave the helper the newest vintage.
5. **The check names the range, the ceiling and its unit, and below `most` the option.**
   `check(count, *, asked=None, advice=None)` raises `InvalidRequestError` for more periods
   than the ceiling in force, `2024-08 to 2026-08 is 25 months; one call fetches at most 24
   months`, and below `most` adds `the ceiling set for this process`, with the MCP server's
   default and the option that raises it where one is declared, as both copies word it.
   `advice` closes the refusal, `Ask for fewer months.` by default, since a source's advice
   names its own parameters. `set(value)` refuses a value outside 1 to `most` with
   `InvalidRequestError` naming the option, the class that `main` turns into its exit status
   2, and the option's help is core's range and default followed by the source's `help`. The
   refusals carry the ceiling's `source`, as every error of the taxonomy does.
6. **The fetched periods are named by the first, the last and their count.** A period is named
   by its `str`, and the sentence added to the message reads `The series stopped at 2023 after
   2 periods fetched, 2021 to 2022, and returns nothing.`, so a series of 60 months names two
   of them, not sixty. A period passed over counts as fetched, since upstream answered it.
   The message of a `XippiosError` and the argument that holds it are extended in place, the
   two that `str`, both adapters and `repr` read. A failure in the first period passes as
   raised, since nothing was fetched before it.
7. **An error that is no `XippiosError` gets a note.** Its arguments are its own class's, so
   the helper leaves them and adds the same sentence as a note (PEP 678), which a traceback
   prints. A cancellation passes untouched, since the helper catches no `BaseException` that is
   no `Exception`.

## Consequences

- sdk-usda-psd's `get_time_series` and sdk-usda-esr's `get_weekly_series` call `check` and
  `fetch_periods` with `skip=(NoDataForYear,)`, and their tasks keep the vintage from the rows.
  sdk-usda-gats's and sdk-usda-nass's ceilings, their setters and their option hooks reduce to
  one `Ceiling` each, their refusals take core's wording and their options keep their names.
  sdk-comtrade keeps its ceiling in `validate_slice`, which joins every problem of a call in one
  refusal, and may take `fetch_periods` over its chunks of 12 for the failure's message. Each
  takes its part in its patch, by https://github.com/xippios/sdk-usda-esr/issues/29,
  https://github.com/xippios/sdk-usda-psd/issues/32,
  https://github.com/xippios/sdk-usda-gats/issues/33,
  https://github.com/xippios/sdk-usda-nass/issues/56 and
  https://github.com/xippios/sdk-comtrade/issues/36.
- A caller whose series failed partway knows where to start again, and the requests spent before
  the failure stay spent: nothing is returned.
- The order of a range, a start after its end, stays each source's refusal in its own
  parameters' names: the decision gives core the ceiling's check alone.
