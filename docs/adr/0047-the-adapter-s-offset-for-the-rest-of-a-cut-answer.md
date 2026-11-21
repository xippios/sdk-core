# ADR-0047: The adapter's offset for the rest of a cut answer

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/362

## Context

ADR-0038 caps every MCP tool result at 200 rows or 64 KB and says over the cap what the answer
left out, and a cut list says where to resume only where its task records an integer `start` in
`meta.request`, an offset-paged task's: two tasks of sdk-google-mail and four of sdk-cashctrl. Every
other cut list ends at its first page. sdk-usda-esr's every-country answer of 385 to 1,136 rows is
cut to 200, sdk-usda-nass's `get_data` near 60 records, sdk-comtrade's `get_world_trade` to 104 of
167 rows and sdk-usda-esmis's `list_publications` to 200 of 2,008 for one agency, and a caller over
MCP has no way to the rest (https://github.com/xippios/sdk-core/issues/314). A cut keeps the first
rows, so a series ordered oldest first loses its newest rows, the ones an agent usually wants:
sdk-eurostat asked to keep the last rows (https://github.com/xippios/sdk-core/issues/71), which
waited for a second consumer, and sdk-usda-esr's weekly series is that consumer.

A continuation for every list tool would change the arguments the tools declare and the notes of
their cut answers, which about 36 assertions in ten sources pin under `xippios-core~=0.4.0`. The
second run of a task costs upstream again unless a packaged table or the response cache answers
it, and the response cache answers it in sdk-faostat and sdk-eurostat alone, within 300 seconds.

## Decision

1. **A paged cap gives the tool the adapter's own `offset`.** `ResultCap(paged=True)` adds
   `offset: int = 0` to the tool, after the task's parameters, keyword-only and at least 0, with
   a description in the input schema: the rows of the answer already shown. The tool takes it off
   the call, runs the task again with the task's own arguments and cuts the task's rows from
   there. The adapter keeps no state between calls. `offset` reaches neither the task nor
   `meta.request`, and a negative one is refused by the argument check before the task runs, as
   `error: InvalidRequestError: offset: Input should be greater than or equal to 0`.
2. **A tool opts in, and nothing else changes.** `paged` defaults to `False`, which leaves a tool,
   the arguments it declares and every note of ADR-0038 as they are, byte for byte. A source opts
   a tool in where a second run of its task costs little, a packaged table or an answer the
   response cache holds, and leaves out a tool whose second run is dear, many upstream requests or
   a billed page. A task that records its own `start` keeps the note it has and is left unpaged.
   A task that takes a parameter `offset` itself is refused a paged cap at registration, with
   `ValueError` naming the tool and saying that the adapter's argument would shadow it, before
   anything is registered. A write task is never paged: a continuation runs the task again,
   so following the note of a paged write tool would repeat a confirmed write, and
   `register_tasks(read_only=False)` refuses a paged cap for every task of a write server
   with `ValueError` naming the tool and saying so, before anything is registered or marked.
   A write task may keep the last rows, `ResultCap(keep="last")` alone, since that runs it
   once and its note names no call that runs it again.
3. **The note of a paged tool names the next call.** Its first page reads as ADR-0038, decision 3,
   writes it and ends `; continue with offset=<offset + shown>`, `shown` counted after both
   bounds, so a page that the byte bound cuts short still names the right next offset. A later
   page names its rows, `showing rows <a> to <b> of <total>`, counted from 1 in the task's order,
   then the cap and its note and the continuation; the last page is that count alone. Where one
   row alone passes the byte bound, the page shows no row and its note says `the first row alone
   exceeds the byte cap`, or `row <n>` on a later page, then the cap's note and, where rows follow
   it, `; continue past it with offset=<offset + 1>`, for the adapter's argument only. A paged
   note never names `start`. An `offset` that leaves no row answers no row with `showing 0 of
   <total> rows; offset <offset> leaves no row to show`, since rows can change between two runs. A
   paged tool whose answer holds no list of rows refuses an `offset` above 0 as
   `InvalidRequestError`.
4. **The note marks a page, and `meta` stays the task's.** ADR-0038 marks a cut answer by the
   `note` beside `data` and `meta`, and a page is marked the same way: every page carries its
   note, the last one too, and an answer without one is whole. `meta` is the envelope the task
   built, its `request` what the task sent (conventions §4), so the adapter writes nothing into
   it.
5. **A cap may keep the last rows.** `ResultCap(keep="last")`, default `"first"`, keeps the last
   rows of a cut answer, the newest of a series ordered oldest first, in the task's order. Its
   note names its rows from the first page on. On a paged tool `offset` counts the rows already
   shown from the last row, so a continuation walks to older rows and keeps one meaning, the rows
   already shown. On an unpaged tool the answer is the newest rows and the note, with no
   continuation and no `start` resume. Any other value of `keep` is refused with `ValueError`.
6. **The family check knows the adapter's argument.** It holds a paged tool's input schema to its
   task's parameters and `offset`, and every other tool's to its task's parameters alone, as
   before.
7. **It stands beside ADR-0038.** ADR-0038's decisions hold for every cap: the bounds, a cap per
   tool with its note, the cut of a model's one list and the preview. This record adds two fields
   to the cap and the notes of a paged or a last-rows cap, and changes no text that ADR-0038
   writes for a cap that has neither.

Each part has two consumers (ADR-0023, decision 2). A paged tool, one whose second run costs
little: sdk-usda-esmis's `list_publications` on its packaged table, sdk-usda-nass's
`list_param_values`, nine of its lists packaged and the rest one keyed call, sdk-usda-esr's `get_exports` for every country,
one request, and the list tools of sdk-faostat and sdk-eurostat, whose answers the response
cache holds. The last rows: sdk-eurostat's `get_series`
(https://github.com/xippios/sdk-core/issues/71) and sdk-usda-esr's `get_exports` for every
country, paged, and its `get_weekly_series`, unpaged, since a second run of the series spends
one request per market year.

## Consequences

- A continuation runs the task again: it costs upstream again unless a packaged table or the
  response cache answers it, and where upstream changed between the two runs a row can repeat or
  be skipped. The source weighs that when it opts a tool in. On a multi-tenant source the second
  run spends the tenant's own quota, on a shared key the key's, and on a metered upstream it is
  billed again.
- A source takes the fields in its patch, an entry in its `MCP_CAPS` for each tool whose answer is
  cut, and shortens a cap's note that only worked around the cut.
- What a paged cap does not reach stays as ADR-0038 has it: a model with two lists, an answer
  that is no list and a page whose cursor must come back whole are previews or cuts as before, and
  sdk-x's billed pages stay unpaged.

Conventions §8, the README and the docstrings of `ResultCap`, `cap_result` and
`xippios.core.mcp.server` state its decisions from 1.29 on.
