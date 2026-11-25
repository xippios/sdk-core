# ADR-0061: The one way of each feature

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/474

## Context

The twelve sources of the family serve the same features in different ways. Several values of a
filter are a list in one source and a comma-separated text in another; a read task's verb is one
of eight, and `list_` names a packaged list, a live list or one page; a row count is `n` in three
sources and a range is `start_year` and `end_year` in three and `since` and `until` in four;
"no data" is an empty list in one task and `NotFoundError` in its neighbour; two sources gather
every problem of a call into one refusal with code of their own; a tool call over MCP spends 24
requests in one source and 100 in another; a tool is paged in one source where its second run
sends a request and unpaged in another where it would send none. An agent that has learnt one
source cannot carry what it learnt to the next, and each adoption judges the same question again.

https://github.com/xippios/sdk-core/issues/474 decided that a second record, beside the boundary
of ADR-0060, holds the twelve ways, one decision each, and that the conventions state each in the
section of its subject, so that a rule can be quoted alone with its decision. Of the twelve, the
conventions held only the two meanings of `since` (ADR-0052). The family check takes the one way
that a test can hold whole, the verbs of decision 3; the others are the review's. The
maintainer's answer on https://github.com/xippios/sdk-usda-esr/issues/60, part 1, the interview of
sdk-usda-esr's adoption, read decision 5 for the family on the same day.

## Decision

1. **Several values of one filter are a list.** An argument that takes several values of one
   upstream filter takes a list, which the package joins as upstream wants them. A
   comma-separated text is no argument form.
2. **A filter of the package's own only where upstream has none.** A package filters after the
   fetch only where upstream offers no filter of its own. The filter is named after upstream's
   field that it reads, compares by equality or by prefix, and its docstring says that the
   package filters after the fetch. `search` on a `list_` task stays core's `matches` (ADR-0041).
3. **Six verbs, each with one meaning.** `list_` names a list of upstream's records of one kind;
   `get_` one record, or the answer of one data operation; `search_` and `count_` upstream's own
   search and count operations; `download_` a file written to a path; and a write takes `create_`,
   `update_`, `delete_` or upstream's own verb. A read task's name therefore starts with one of
   the five read verbs, `list_`, `get_`, `search_`, `count_` or `download_`, and the family
   check's `test_family_read_tasks_start_with_a_read_verb` fails every task of `tasks.__all__`,
   bulk or not, whose name starts with none. Six tasks of three sources fail it today:
   sdk-cashctrl's four `export_` tasks, which write a file to `dest`, sdk-usda-wasde's
   `read_report_text` and sdk-x's `lookup_users`.
4. **Five words for a package's own arguments.** An argument that upstream does not take is one
   of five words: `search` on a list task; `since` alone for a vintage taken back; `since` and
   `until` for the inclusive bounds of dates or periods (ADR-0052); `start_<period>` and
   `end_<period>` for a series that the package assembles; and `dest` for a download's path. A
   tenant comes first and `confirm` last. An argument that upstream takes keeps upstream's name
   (ADR-0028, decision 2).
5. **One order of arguments within a source.** Within a source one concept stands at one
   position in every task. The arguments that identify a record are positional, in the order of
   upstream's path, and every optional filter and every other argument of the package's own is
   keyword-only, as the invented source `example` takes `get_series(region_code, year, *,
   unit=None)` and sdk-usda-esr will take `get_exports(commodity_code, market_year, *,
   country_code=None)` (https://github.com/xippios/sdk-usda-esr/issues/60, part 1). A tenant keeps the place
   that decision 4 gives it, first and positional, since it names the upstream account that the
   path is under, and the arguments after it follow that order, as `example` takes
   `get_balance(tenant, account_id, *, as_of=None)` for its tenant `acme`. Over MCP and HTTP
   nothing changes, since a tool and a route take their arguments by name, and a Python caller by
   position rewrites its call. No test holds it, since it would fail positional signatures in the
   sources before each has its order.
6. **One answer for "no data" per kind of task.** A task that returns a list answers no data
   with the empty list, and a task that returns one record raises `NotFoundError`. A period that
   upstream has not released is `NotFoundError` where the package knows the latest release
   (ADR-0041, decision 6).
7. **One refusal names the first problem.** A refusal of the call as given names the first
   problem that it finds, in core's words, and a package gathers no list of every problem into
   one refusal. The collectors of sdk-cashctrl and sdk-comtrade leave at their adoptions.
8. **A stated bound of requests per call.** A task that spends more than one request states in
   its tool's description, the text of its docstring before `Args:` (ADR-0063, decision 9), the
   most requests that one call can spend, retries counted, and one tool call over MCP sends at
   most about two dozen requests before the client's retries, as a walk of 24 pages spends 96
   at the client's default of four attempts.
9. **A paged cap only where a continuation costs upstream nothing.** A tool takes
   `ResultCap(paged=True)` only where a second run of its task sends upstream no request, an
   answer of a packaged table or one that the response cache holds. This tightens ADR-0047,
   decision 2, whose second run that "costs little" becomes one that costs upstream nothing.
10. **A billed read and a write are sent once.** A request that upstream bills and a request that
    writes are sent once, and the error of a write that failed says that its outcome is unknown.
    This changes ADR-0011 for a write and a billed read. Core's client takes the write's half by
    the change that https://github.com/xippios/sdk-core/issues/480 decided, and a source with
    billed reads sets `RetryPolicy(max_attempts=1)` on its client.
11. **Core's response cache in a read-only source of public data.** A read-only source of public
    data gives its client core's response cache, and a client that takes none says why in one
    sentence of the source's `CLAUDE.md`: private data, or a billed page whose age matters.
12. **A value set written by hand is held by an offline test.** A value set that a package writes
    by hand from upstream's document, an enumeration or a table of allowed values, is held by an
    offline test that reads it against the document under `docs/upstream/`.

## Consequences

- Conventions §1 state decisions 3 and 4, §2 decisions 1, 2 and 5, §5 decisions 6 and 7, §6
  decisions 10 and 11, §8 decisions 8 and 9 and §10 decision 12 and the family check of
  decision 3, each in one sentence that cites its decision here.
- ADR-0047 and ADR-0011 each take one sentence that points here; their other decisions stand.
- The ways bind a source from its adoption of core 0.5.0, which takes what the source does not
  meet yet, named by source and file in the release's changelog. By the alignment of the twelve
  sources that this record answers: decision 1 changes sdk-comtrade's comma-separated texts;
  decision 2 sdk-usda-gats and sdk-eurostat; decision 3 the six tasks above; decision 5 a call
  by position of an optional filter or an argument of the package's own in every source, and a
  concept at two positions in sdk-usda-psd, sdk-usda-esr, sdk-comtrade, sdk-x, sdk-eurostat and
  sdk-usda-gats; decision 6 sdk-usda-nass, sdk-usda-esmis and sdk-usda-esr; decision 7
  sdk-cashctrl and sdk-comtrade; decision 8 sdk-usda-psd, sdk-usda-esmis, sdk-usda-nass and
  sdk-cashctrl; decision 9 each source whose paged tools send a request on a second run;
  decision 10 sdk-x, sdk-cashctrl and sdk-google-mail; decision 11 sdk-usda-esmis, sdk-usda-esr,
  sdk-usda-psd, sdk-comtrade and sdk-usda-nass; decision 12 sdk-cashctrl, sdk-x, sdk-google-mail
  and sdk-usda-esmis.
- A way that a test cannot hold, the order of decision 5 or the bound of decision 8, is judged
  in review against its decision.
