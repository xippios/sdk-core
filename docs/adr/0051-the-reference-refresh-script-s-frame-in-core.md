# ADR-0051: The reference refresh script's frame in core

Status: Accepted · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/370

## Context

A source that packages reference data keeps `scripts/refresh_reference.py`, which fetches its
lists, writes each `reference/<name>.json` with `PackagedList.write` and renders `enums.py`
with `render_enums` (conventions §3; ADR-0031, decision 6; ADR-0041, decisions 4 and 5).
sdk-template renders the script once, 262 lines at v0.4.0, and an update never overwrites a
file a source fills, so the nine sources that package lists carry nine copies, 3,442 lines
from 175 to 835 each, that kept between 2 and 9 of the template's 14 blocks as they stand.
The copies grew three shapes of the template's dicts, four of them build their lists by hand,
five count their requests through the client's meter, and four rewrite the provenance table
of `reference/README.md` by code while five keep it by hand. ADR-0023, decision 1, sends a
helper the template renders into every repository to core.
https://github.com/xippios/sdk-core/issues/309 took the frame into sdk-core 0.4.1
(https://github.com/xippios/sdk-core/issues/321), ADR-0046 gave both script frames one
subpackage, `xippios.core.refresh`, and the maintainer's answer on
https://github.com/xippios/sdk-core/issues/370, given on 2026-11-21, decided the design question.

## Decision

1. **The home and the one entry.** The frame is `xippios.core.refresh.reference`, a module
   beside the snapshot's `upstream` in the subpackage of ADR-0046, decision 1: it imports
   `client`, `models` and `reference` below it and `upstream` beside it, and nothing in core
   imports it. The subpackage's `__init__` exports `Listed` and `Enumeration` beside the
   snapshot's names, and one `run` for both frames, as ADR-0046's consequences have it:
   given a `Snapshot`, `run(snapshot, argv=None)` is the snapshot frame's run unchanged, and
   given the lists, `run(lists, argv=None, *, package, client, quota_header=None,
   before=None, after=None)` is this one's. A source's two scripts then import their
   declarations and `run` from one surface, which ADR-0029, decision 4, and ADR-0046,
   decision 1, make the `__all__` of an `__init__`, and neither frame's entry takes a
   second name.
2. **The shape: one `Listed` per list.** A source's script declares each list with its name,
   the file `reference/<name>.json` and the name `--only` takes; its fetch through the
   source's `api/` wrappers, async or not; the upstream operation and parameter its file
   records; its `Enumeration`, if any; and its origin. A fetch answers values, which become
   records of one field named by the list's `param`; records, a model's by `dump_upstream`
   and a mapping as it is; or a finished `PackagedList`, written as built, whose `param` and
   `endpoint` must be those its `Listed` declares where it declares them. One declaration
   replaces the three tuple shapes of the copies, and the four copies that build their lists
   by hand fit without a subclass. `package` is the source's import path, as
   `PackagedList.load` takes it: the frame writes into its directory as imported, and
   refuses one outside the directory the script runs in, an installed copy. `packaged` names
   the lists the package declares it ships, its `params.PACKAGED_LISTS` in the template's
   shape, and the lists declared to `run` must be exactly those, or the run stops before a
   request and names the lists declared on one side alone, as the template's script and the
   copies of sdk-usda-esr and sdk-usda-wasde stop. The frame takes the names from the source
   and reads no `params` of its own, since the sources declare them four ways: a tuple of
   every name in six, a mapping of the value lists beside one of the tables in sdk-comtrade,
   the parameters beside the derived lists in sdk-usda-nass, and in sdk-usda-esmis an empty
   tuple of value lists while it ships two tables. Each hands the names it ships, both parts
   where it keeps two.
3. **When a list was fetched.** The fetch carries the moment. Values and records are stamped
   when their fetch returned, as four copies stamp them (sdk-faostat, sdk-usda-esr,
   sdk-usda-gats, sdk-usda-psd), and a finished list keeps its own `fetched`: the wrapper's
   `retrieved_at` (sdk-comtrade, sdk-eurostat, sdk-usda-nass's parameter lists), the time of
   its first request (sdk-usda-esmis) or the time its file was complete (sdk-usda-wasde). So
   no source's `fetched` changes its meaning.
4. **What holds byte for byte.** The packaged files are `PackagedList.write`'s, as they are
   in every copy. `enums.py` is one `render_enums` call in the order the lists are declared,
   each `Enumeration` naming the field its values are read from, or the fields of its ids and
   names for an `IntEnum`, its key, its class name and its members named by hand, a mapping
   or a function of the values; where no list declares an enum, `enums.py` is left alone,
   hand-written or empty. The provenance table is found under the header the README has,
   `| File | Origin | Fetched |` or the FAS sources' `| File | Origin | Fetched (UTC) |
   Records |`, and each list's row is rewritten where it stands from its file: its Origin a
   declared text, a function of the written list or by default its endpoint in a code span,
   its `fetched` in UTC to the second, and the count of its records under the header that
   has them. A row of a file no list declares is kept, the template's `(none yet)` is
   dropped, and a list without a row gets one after the others. So the decided proof holds
   as https://github.com/xippios/sdk-core/issues/321 words it: the step's offline proof ran
   each of the nine sources' short scripts on the frame with `--render-only`, against its
   packaged files, and every `enums.py` and `reference/README.md` came out as committed.
5. **The run.** The command line takes `--only LIST [LIST ...]` or `--render-only`, one
   choice. Every list is fetched before the first file is written, through `client` with one
   attempt per request for the run, so a 5xx or a 429 spends no second call of upstream's
   quota, and the run prints the requests it sent and the quota left in `quota_header`, a
   failed run's too, a request that ended in a transport error counted as sent, so the count
   is never below what the run spent (sdk-usda-esr's rule). Every file the run writes is made
   before the first write: the packaged files by `PackagedList.write` in a temporary
   directory outside the repository, the rows, and `enums.py` formatted by `ruff format` and
   `ruff check --fix` from standard input under the configuration the repository gives its
   path. The files are then written as one: a write that fails halfway, a full disk or a
   file the run may not write, or an interrupt, puts back each file the run replaced and
   removes each it made, and the error is raised. So a fetch, a render, ruff or a write that
   fails leaves the tree as it was, and the run is run again. `--only`
   fetches the lists it names and keeps every other list's file, which must be packaged
   already, and `--render-only` writes the rows and `enums.py` from the packaged files,
   without a request or a key; both check what they need before the first request.
6. **Two hooks for what lies beside the lists.** `before` is called once the command line and
   the declarations are checked and before the first request, for what can stop a run before
   it spends one; `after` is called after the last write with the lists the run fetched, by
   name, for what a script writes beside them: sdk-eurostat's index and test samples,
   sdk-usda-nass's `columns.csv`, sdk-usda-wasde's manifest. `--render-only` calls neither.
   So "nothing is written until everything is fetched" stays the frame's promise, and the
   tests hold it. `after` runs once the frame's files stand written whole, so a hook that
   raises leaves them written, consistent with one another, the run says so before the
   hook's error ends it, and what the hook wrote is as the hook left it: a hook makes what it
   writes before it writes, as the frame does.
7. **What stays the source's.** The frame takes no option of a source's own and counts what
   its client's `observe` hook sees. A script that keeps an option, sdk-eurostat's `--samples`
   and its `--only` by a codelist's id, sdk-usda-wasde's `--keep` and `--from`, reads it
   before the call and passes the rest as `argv`; sdk-faostat's count of its logins, which
   run inside its client's auth flow, and sdk-usda-nass's longer read timeout stay around the
   call; one source needs each, and a second would bring it into the frame (ADR-0023,
   decision 2).

## Consequences

- The consumers are the nine sources that package lists, sdk-comtrade, sdk-eurostat,
  sdk-faostat, sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd and
  sdk-usda-wasde, each of which ports its script in its patch, and sdk-template, which renders
  the short script on this frame in its 0.4.1, released after core 0.4.1 and before the sources'
  patches, by the maintainer's decision on the order of the releases. sdk-cashctrl,
  sdk-google-mail and sdk-x package no list.
- A port moves the origins that five READMEs keep by hand into its declarations, and from
  then on the frame writes those rows on every run. sdk-comtrade and sdk-usda-psd gain
  `--only`, and sdk-usda-esmis and sdk-usda-wasde `--only`, `--render-only` and the meter's
  count of their requests; sdk-comtrade, sdk-usda-esmis,
  sdk-usda-psd and sdk-usda-wasde send each request once where their client retried, and
  print what they sent. sdk-eurostat and sdk-faostat no longer render their empty `enums.py`,
  which stays as committed.
- The offline proof shows the render and the rows. What only a full run of a ported script
  can show, in its source's patch, is the fetch: that each list's `fetched` keeps its moment,
  that the records are those the copy wrote, and the count the run prints; the trial before
  the release runs each port's tests offline on core's `main`.

Conventions §3, the README and the docstrings of `xippios.core.refresh` state its decisions.
