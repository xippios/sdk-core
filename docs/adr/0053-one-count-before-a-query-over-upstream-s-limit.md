# ADR-0053: One count before a query over upstream's limit

Status: Accepted · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/372 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/405

## Context

Two sources ask upstream for the count of a query's records before they fetch it, and both carry
the same error under the same name, `QueryTooLarge`, an `InvalidRequestError`
(https://github.com/xippios/sdk-core/issues/317):

- sdk-comtrade's `get_data` counts with `countOnly`, answers a count of 0 with an empty list and
  no second request, and refuses a count over 100,000 before the data request, since upstream
  would cut the answer at that limit without saying so (`src/xippios/comtrade/tasks.py`). Its
  slices count nothing, since their arguments bound their rows, and a bound over the limit is
  refused before any request, the error's `bound=True` (`_bounded`). Its class takes `count`,
  `limit` and `bound` and words its advice itself (`src/xippios/comtrade/errors.py`).
- sdk-usda-nass's `get_data` counts with `get_counts` the same way, against 50,000, and sets
  `meta.total` from the count. Over the limit, a query with `split_by_year` is split by year
  instead, every year counted before the first fetch, and a year alone over the limit is refused
  by its year. Its `classify` maps upstream's HTTP 413 to the error without a count. Its class
  takes `count`, which may be `None`, `limit` and `year` (`src/xippios/usda/nass/errors.py`,
  `_client.py` and `tasks.py`).

The row names two more sources that do not fit it as written. sdk-eurostat cannot count before it
asks: upstream estimates the size itself and refuses a query over its limit, printing the
estimate. sdk-faostat can count with `no_records=true`, whose answer is a float, but its upstream
has no limit, so a limit would be the package's own.

Decisions 1 to 3 are the answer of https://github.com/xippios/sdk-core/issues/372, decisions 4
to 6 are those of the pull request that built the helper, and decision 7, the amendment of
2026-11-22, is the answer of https://github.com/xippios/sdk-core/issues/405, which the
maintainer gave in the sdk-core panel that day.

## Decision

1. **One `QueryTooLarge`, whose message core words.** `QueryTooLarge(count, *, limit, narrow,
   bound=False, source=None)`, exported from `xippios.core`, is an `InvalidRequestError`, so the
   HTTP adapter answers it with 422 and the MCP adapter prints `error: QueryTooLarge: ...`, the
   name both copies print. `count` is the records the query would return as upstream counted
   them, with `bound` the most it could return as read from its arguments, and `None` where
   upstream refused the query as too large without a count; `limit` is the most records upstream
   serves per call, and `narrow` the text of what narrows the query. Core words the message from
   them in three forms, `narrow` last:
   - `query would return 5,006,385 records; upstream serves at most 100,000 per call.`
   - `query could return up to 100,008 records, a size read from its arguments with nothing
     counted or sent; upstream serves at most 100,000 per call.`
   - `upstream refused the query as too large; it serves at most 50,000 records per call.`

   A bound without a count raises `ValueError`, since a bound is a number. sdk-comtrade deletes
   its class, and sdk-usda-nass keeps a subclass of core's for its `year`, which its tests read.
2. **A runner that makes both requests.** `fetch_counted(count, fetch, *, limit, empty, narrow,
   source=None)`, exported from `xippios.core`, awaits `count()` and, over `limit`, raises
   `QueryTooLarge` with the count, the limit and `narrow` before it calls `fetch`; within it, a
   count equal to the limit included, it awaits `fetch()`. An error that `count` or `fetch`
   raises passes as raised, and a `limit` below 1 raises `ValueError` before the count. Since the
   runner sends both requests, the three cases of the row's proof are core's own tests.
3. **An empty count answers the task's empty answer.** A count of 0 returns `empty`, which the
   task passes, without calling `fetch`: no matching data is an answer and not an error, as both
   copies answer it.
4. **The runner returns the data with the count.** `fetch_counted` returns `(data, count)`, and
   `(empty, 0)` for a count of 0, so the task sets `meta.total` from the count it already paid
   for: the count is upstream's count of the records matching the request, which `meta.total`
   holds (ADR-0034; conventions §4). sdk-usda-nass sets it today, and sdk-comtrade may. The
   pair is typed `tuple[T | E, int]`, `empty` apart from what `fetch` returns, since the runner
   returns `empty` itself: with one type for both, mypy infers `list[Never]` from `empty=[]` and
   refuses a `fetch` of `list[Record]`, and apart it gives `list[Record]`.
5. **It lives in `xippios.core.pagination`.** The runner drives upstream's requests for one
   bounded answer, as `paginate_offset` with `max_items` and `collect` do, and `pagination`
   stands above `errors`, so it imports `QueryTooLarge` downward (ADR-0029, decisions 1 and 2).
   A module of its own would satisfy ADR-0029 as well, for one function; in `pagination` a
   caller finds the runner beside the other helpers of a fetch, and the tree gains no module.
6. **A count that is no whole number is the source's fault.** `count()` gives an `int` of 0 or
   more. A float, a whole one such as `1234.0` included, a `bool` or any other type raises
   `TypeError`, and a negative count `ValueError`, each naming the value, before `fetch` is
   called. The source reads upstream's count into an `int` where it parses upstream's answer: a
   pydantic `int` field reads `1234.0` as `1234` and refuses `1234.5`, which core's `parse`
   raises as `ValidationError`. No taxonomy error is raised, since no change of the request
   mends it (conventions §5).
7. **The error that a source's `classify` maps names its request.** By the maintainer's answer
   to https://github.com/xippios/sdk-core/issues/405, given in the sdk-core panel on 2026-11-22,
   `QueryTooLarge` takes one optional argument, `request=None`, beside `source`, the text that
   `request_description(response)` gives, which a source's `classify` passes when it maps
   upstream's refusal to the error, and keeps it as an attribute. The four fields of decision 1
   stand. Given, the message names it where its forms say "the query" or
   "query": `upstream refused GET /api/api_GET/ as too large; it serves at most 50,000 records
   per call.`, and `GET /v1/data would return 13,344,840 records; ...` for upstream's refusal
   that prints its count. Conventions §5 ask every error that a source's `classify` maps to name
   its request by `request_description`, and the package's own refusal before its data request
   to name none (ADR-0030, decision 4; ADR-0043), so the rule stands as written and gains no
   sentence. The runner refuses before the data request and passes none, a bound read from the
   arguments passes none, and the error refuses a bound with a request by `ValueError`, as it
   refuses a bound without a count. Without `request` every form reads as decision 1 gives it.

## Consequences

- sdk-comtrade deletes its `QueryTooLarge` and keeps `RECORD_LIMIT` and `MAX_PERIODS` in
  `errors.py`. `get_data` calls the runner, and `_bounded` raises core's error with
  `bound=True`. Its advice moves into `narrow`, and the clause that upstream cuts the rest
  without saying so leaves the message, which its docstring keeps.
- sdk-usda-nass keeps its subclass for `year`, which passes `request` on, and raises it at its
  four sites: its `classify` for upstream's 413, with a count of `None` and
  `request=request_description(response)`; its split, per year, by its own check, since the
  split counts every year before its first fetch and so takes no runner; and around the runner
  of `get_data`, whose refusal it catches to split the years or to raise its own error for one
  year. Since its fetch can raise the 413 too, the catch passes an error with a count of `None`
  as raised, and splits on a counted refusal alone. The message for a year alone starts with
  core's form, and the year goes into `narrow`.
- sdk-eurostat takes the error alone, from its `classify`, with the count and the limit read
  from upstream's own refusal and `request=request_description(response)`, and never the
  runner, since upstream offers no count request.
  Its row, https://github.com/xippios/sdk-eurostat/issues/53, proposes an estimate from the
  arguments before the request, which is the error's `bound=True`. sdk-faostat can take the
  runner only against a limit of its own, its count read into an `int`
  (https://github.com/xippios/sdk-faostat/issues/35). Each decides in its own patch, and this
  record builds nothing for either.
- The two consumers of ADR-0023 are sdk-comtrade and sdk-usda-nass, which delete their copies of
  the gate in their patches.
