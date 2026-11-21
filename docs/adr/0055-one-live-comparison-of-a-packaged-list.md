# ADR-0055: One live comparison of a packaged list

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/374

## Context

Conventions §3 ship a source's reference lists inside its package, and §5 has a task refuse a
code that its packaged list lacks (ADR-0045), so a code that upstream adds is refused until the
source refreshes the list. Six sources compare their lists with upstream's in their nightly live
tests, each with a copy of its own: sdk-usda-esr, sdk-usda-psd and sdk-usda-gats compare every
record of their 4, 5 and 5 lists and print the first records that differ; sdk-comtrade
compares 4 of its 15 lists, two of them by their codes alone; sdk-usda-esmis 1 of its 2, by its
acronyms in order; sdk-usda-wasde 3 of its 4, through its own `differences`, which names rows
and never values. sdk-faostat compares 1 of its 15 tables, for removed codes only, and
sdk-usda-nass, with 11 lists, and sdk-eurostat, with 19, compare none
(https://github.com/xippios/sdk-core/issues/319). sdk-eurostat's reference refresh of
2026-11-20 found 424 entries of its table of contents added, 349 removed and 2,433 changed since
2026-10-28, which no nightly run had shown (https://github.com/xippios/sdk-eurostat/issues/70).

Conventions §10 have a live test assert on shapes and counts, never on a raw payload, since the
log of a public repository is public (ADR-0032, decision 6). A failure that names the codes of a
list needs a clause of its own.

## Decision

1. **Core owns the test, and the source declares its lists.** `xippios.core.testing.live` holds
   the nightly test, `test_packaged_list_is_current`, which a source collects in
   `tests/test_live.py` with one line, `from xippios.core.testing.live import *  # noqa: F403`,
   beside two declarations. `LIVE_LISTS` maps each packaged list that the source compares, by
   the name of its file `reference/<name>.json`, to a pair of its `PackagedCodes`
   (`PackagedList.codes`, ADR-0045) and the function that fetches it now. `NO_LIVE_LIST` maps
   each packaged list that it does not compare to the reason. The test runs once per entry of
   `LIVE_LISTS`, `test_packaged_list_is_current[<name>]`, marked `live`, so an offline run
   sends nothing.
2. **The declaration stands in `tests/test_live.py`.** The collected test reads it from its own
   module, through the `pytest_generate_tests` that the same star import brings, and the family
   check loads that file by its path from the repository's root, as it reads `README.md` and
   `pyproject.toml` there. Under `--import-mode=importlib`, which the sources use, no test
   module stands on an import path for another to import. The package's `tasks.py`, where
   `BULK_TASKS` stands, would ship the fetch functions of the tests in the wheel and load every
   compared list, a large one too, whenever the package is imported.
3. **The family check compares the declaration with the files.**
   `test_family_every_packaged_list_is_declared_for_the_live_run` fails a source whose package
   holds a packaged list, a `reference/<name>.json` that holds `param`, `endpoint`, `fetched`
   and `records`, in neither declaration. It fails an entry that names no packaged list, so a
   stale declaration does not pass, a list in both, an entry of `NO_LIVE_LIST` without a reason,
   and an entry of `LIVE_LISTS` that is no pair of a `PackagedCodes` declared from that file and
   a function. A source with no packaged list and no declaration passes. The check fails at once
   from core 0.4.1 on, with no release that warns first, as every new family check of 0.4.1 does
   (https://github.com/xippios/sdk-core/issues/359, part 4).
4. **What a fetch returns.** The function takes no argument and returns the list upstream
   serves now, or an awaitable of it, which the test runs on core's loop as `sync` runs a task.
   The list is records, mappings under upstream's field names or `UpstreamModel` instances read
   through `dump_upstream`, compared by the declared code; or bare codes, text or integers,
   compared by code alone, for a list that upstream serves as codes or a fetch that reads no
   more of it.
5. **What fails the run.** A code that is gone from upstream's list, a code that is new in it
   and a code whose record changed each fail the run. The records are compared by the declared
   code, `PackagedCodes.code`, each as the JSON that the packaged file holds, in any order of the
   list and of a record's fields, and a code listed twice compares its records together.
6. **The failure names codes and never records.** `assert_list_current(codes, current, *,
   packaged=None)` is the assertion underneath, public for a source whose fetch is its own, a
   session's fixture say. It fails the test with the list's name and fetch date, the counts, and
   the codes gone, new and changed, the first 20 of each in the list's order and how many more,
   and with no frame and no local value of the test, whatever `--tb` or `--showlocals` a run
   takes. `packaged=` gives the packaged side read as the source reads its current side, for a
   list whose records name the release they came from, as sdk-usda-wasde's carry
   `report_month`. Conventions §10 gain the clause that a live comparison of a public reference
   list may name its codes in the log, never a record's other fields.

## Consequences

- The six copies go, each in its source's patch, and sdk-faostat, sdk-usda-nass and
  sdk-eurostat take the test. The changelog's Hand-apply note names, per source, what it deletes
  from `tests/test_live.py` and what it declares. A list that a source leaves out stands in
  `NO_LIVE_LIST` with its reason, and which list a source compares is its own choice, made in
  its patch: full coverage costs sdk-faostat 14 more keyed requests a night, sdk-usda-nass 9 and
  sdk-eurostat 15 more files.
- A list with no endpoint to compare with stands in `NO_LIVE_LIST`: sdk-usda-nass's two derived
  lists, four of sdk-comtrade's taken from the specification and sdk-usda-wasde's four read from
  a release file, three of which its own tests compare through `assert_list_current`.
- sdk-usda-esr, sdk-usda-psd and sdk-usda-gats no longer hold the order of a list in the nightly
  run, since another order compares equal, nor the endpoint a list task names, which an offline
  test of the task holds.
- The family check runs `tests/test_live.py` once more, offline, as pytest's collection does: a
  module that sends a request when it is imported fails both.
