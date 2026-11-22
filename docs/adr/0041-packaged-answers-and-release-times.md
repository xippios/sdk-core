# ADR-0041: Packaged answers and release times in `ResultMeta`

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0022 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/440

## Context

`ResultMeta` was defined for a fetched answer, and three sources answered `list_*` tasks from
packaged reference data each its own way, with a fetch date in `vintage`, "reference" or a
file path in `endpoint` and the answer time in `retrieved_at`. FAS, ESMIS and WASDE print
release times without a zone, which `ResultMeta` refused. Johannes decided the record on
2026-10-26, and the eight points of its amendment of 2026-10-27, which decisions 4 to 10
state, on 2026-10-27. This record states ADR-0022 with its amendment of 2026-10-27, its reading of
2026-10-29 and its amendment of 2026-11-18 as they stand, and changes no decision; their
history stays in ADR-0022. Decisions 6 and 7 keep the numbers by which the conventions and
the sources cite them.

## Decision

1. **A packaged answer.** `retrieved_at` is the time the packaged list was fetched from
   upstream (the file's `fetched` value, as a cache hit uses the entry's stored time,
   ADR-0037). `endpoint` names the upstream operation the list came from (operationId or
   path), never "reference" or a file path. `vintage` holds an upstream release identifier
   only, and is `None` when the upstream has none: a fetch date is not a vintage. `total` is
   `None` unless upstream reports a count (ADR-0034). The `PackagedList` helper (decision 5)
   builds this meta so no source writes it by hand. A load time is never a vintage: a source
   whose only time is the time upstream loaded the data, as sdk-usda-nass's `load_time` is,
   leaves `vintage` and `published_at` empty, since a load time is neither a release
   identifier nor a release time, and a newest `load_time` computed across datasets is a
   maximum the package computes, a guess. Johannes decided it on 2026-10-29 (D110 (3)).
2. **Naive release times.** `ResultMeta` has `published_at_naive: bool = False`. A naive
   `published_at` is accepted only with the flag set and is stored as given, no zone
   attached; a naive value without the flag is refused, and so is the flag with an aware
   `published_at`, or with none. The flag means: upstream printed this time without a zone;
   it is upstream's text, not comparable across sources; a consumer that knows the
   publisher's zone assigns it outside the family (ADR-0028). `vintage` keeps the release
   identifier as upstream names it; where that identifier is the timestamp text, `vintage`
   holds the text and `published_at` its parsed value with the flag.
   - The flag also marks a time whose printed zone upstream's own calendar and files
     contradict, as ESMIS prints `+0000` on `release_datetime` while its releases happen at
     noon Eastern: the task keeps the printed wall-clock time with its offset dropped, never
     converted, and sets the flag, and the wrapper's model keeps the time as printed. The
     task drops the offset itself, since the flag with an aware value is refused. Johannes
     decided it for sdk-usda-esmis on 2026-10-27.
   - A parameter that takes back a vintage, such as sdk-usda-esr's
     `get_release_dates(since=...)`, takes the text as `vintage` wrote it and keeps what is
     strictly later, an equal release being no newer. `meta.vintage` and `meta.published_at`
     stay those of the whole upstream answer, not of the filtered subset, so an empty answer
     still carries the marker to store for the next call. Against a naive release time, a
     value with a zone is refused with `InvalidRequestError`, never converted, since
     comparing the two would invent a zone (ADR-0028), and so is a text the parameter cannot
     read (ADR-0007). Johannes decided sdk-usda-esr's parameter on 2026-10-28 (G5): the text
     as input and the meta of the whole answer.
   - A release identifier that is a day or a month, with no time, such as FAOSTAT's
     `date_update` or PSD's release month, is neither a time nor a time printed without a
     zone. It stays in `vintage` as upstream gives it, and `published_at` stays empty: the
     flag covers a time printed without a zone, not a day, and 00:00 of the day or the first
     of the month would date the release before it happened. The plan of core 0.4.0 settled
     it as both sources have it.
3. **`None` filters in `meta.request`**: a parameter the caller left `None` is omitted;
   `request` records what was sent. `ResultMeta` drops a top-level `None` from `request` at
   construction, before the credential rule, so a credential left `None` is not recorded as
   sent; a `None` inside a nested mapping is kept as given.
4. **`fetched` is a time.** `PackagedList.fetched` is a timezone-aware UTC datetime, decision
   1's `retrieved_at`. The refresh scripts write `datetime.now(UTC)` to the second; a file
   whose `fetched` is a bare date reads as 00:00 UTC of that day, and the source's next
   reference refresh writes the full time. A time without a zone is refused.
5. **One model, one file.** `PackagedList(param, endpoint, fetched, records, note=None)`,
   frozen, with `PackagedList.load(package, name)` on `load_json`, `.meta(source, *,
   request, vintage, published_at, published_at_naive)` building decision 1's meta,
   `.parse(model, *, source)` validating the records, and `.write(path)` writing the file
   (`{"param", "endpoint", "fetched", "records"}` and `note` when it is set, indented,
   non-ASCII text kept, `fetched` to the second) for the refresh scripts. A packaged file
   holds the four keys and an optional `note`, nothing else: `PackagedList` refuses any other
   key, and `note` is free-text provenance that core reads nothing from. A list of values is
   records of one field named by the upstream parameter, and a table records of its columns.
   sdk-usda-nass's two lists derived from `unit_desc` keep `param: "unit_desc"` in files of
   their own names, which `load(package, name)` takes. `endpoint` names the upstream operation, an operationId or a
   URL path; sdk-comtrade's `files/v1/app/reference/<file>.json` is a URL path and qualifies.
6. **Period series.** A task that assembles a series from one upstream call per period
   states its ceiling, the most periods one call fetches (the MCP tool's, where it is
   smaller), and sets `vintage` to the newest release among the periods. Its docstring says
   what an unreleased period inside the range answers: the period is skipped where upstream's
   empty answer can be told from data (sdk-usda-psd's empty 404), and the whole range is
   refused, naming the latest released period, where it cannot (sdk-usda-gats's `[]` for an
   unreleased month looks like a month without trade). An empty answer that cannot be told
   from no data is never passed off as data. The readings the sources apply
   (https://github.com/xippios/sdk-core/issues/238):
   1. **No release calendar.** Where upstream names no release, so the latest released
      period is unknown, a range ends at the current period, and a period that counts zero
      is skipped, the docstring saying that a zero may be a period not yet released, as
      sdk-usda-nass's `get_data(split_by_year=True)` refuses a year past the current UTC year
      with `InvalidRequestError` and skips a year counting 0 (Johannes, 2026-10-28).
   2. **One period.** A task that fetches one period refuses a period after the latest
      released one where it knows that period, with decision 7's `NotFoundError`, as
      sdk-usda-gats's month tasks refuse a month their release list lacks. Where it does not
      know it, its docstring says that an empty answer may be a period not yet released.
   3. **A split mode.** A split mode of a free-form query task, which fetches its range one
      period per call, is a period series, with its ceiling: sdk-usda-nass's
      `split_by_year`, 20 years, 5 on the MCP server.
   4. **The calls a tool call spends.** The cap note that states the ceiling of a tool that
      assembles a period series counts the upstream calls that one tool call spends at that
      ceiling, as each of the four sources with such a tool does: sdk-usda-nass's 5 years on
      the MCP server at most 11 keyed calls, a first count and two calls a year.
7. **The refusal is `NotFoundError`**, naming the latest released period;
   `InvalidRequestError` stays for a malformed request (ADR-0007).
8. **The helpers of the list tasks.** `matches(search, *fields)` is the `search` filter of the
   list tasks. `closest(value, codes, *, n=3, cutoff=0.6)` runs two `difflib` passes, by code
   and then by name, `cutoff` passed to both. `nearest(value, codes, *, n=3)`, exported from
   `xippios.core` beside `closest`, gives up to `n` known integer codes nearest to `value` by
   number with their names, nearest first and the lower of two equally near; `codes` is keyed
   by the integer or by its text, and each pair keeps its code as `codes` keys it. A source
   with a strategy of its own for the closest codes keeps it and passes its result.
   `UnknownCode(param, value, *, list_name, fetched, closest, hint, reason, source)`, an
   `InvalidRequestError`, refuses a code the packaged list lacks: it names a closest pair
   whose name is the code's own text once, `Did you mean VA?`, and every other pair with its
   name, `0410000 (Wheat)`, and its tail reads `If upstream added it since, the packaged list
   is out of date.` Where the check applies, as the sources apply it:
   - conventions §5 refuses a code the packaged list lacks where upstream answers an unknown
     code with an empty result, and `UnknownCode` also refuses a code whose answer from
     upstream was never recorded, its `reason` saying so; a value list that upstream refuses
     itself keeps that refusal, mapped in `classify`, or a check of the source's own that
     raises `InvalidRequestError`;
   - in free-form filters the value of a key that names a packaged parameter is checked, and
     a key with an operator (`<column>__<OPERATOR>`) is checked as a key only;
   - a code sent under a coding system the packaged list does not hold goes unchecked, and
     the task's docstring says so;
   - a code the packaged list holds and upstream's live answer lacks is no unknown code but
     one upstream dropped: `NotFoundError`, naming the code and the operation;
   - a value is compared with the list as upstream compares it, case ignored only where
     upstream ignores it, and it is sent, and recorded in `meta.request`, as the caller gave
     it, so a value upstream serves is never refused and the request records what was sent.
9. **A cached answer's time.** `AsyncClient.get_answer` returns `Answer(payload,
   retrieved_at)`: on a cache hit the time the entry was stored, else the time the answer
   arrived (ADR-0037, decision 5); `get_json` stays.
10. **Frozen series.** A series upstream no longer updates is marked in the README status
    table, by a status that names the last release, and in its task's docstring; `vintage`
    holds the last release's identifier, and `ResultMeta` gains no field. Where each answer
    of a frozen feed carries its own release, `vintage` keeps that answer's release, and the
    feed's last release goes to the README status value and the docstring only; the feed's
    list of release dates keeps `vintage` empty, since it is no single release. Johannes
    confirmed it for sdk-usda-gats on 2026-10-28 (G5).
11. **An error that names another task names its MCP tool too.** An error that a tool can
    return and that names another task, the one to call instead or the list task that names
    the known values, names that task's MCP tool too, since an agent calls a tool by the
    tool's name: `list_param_values('state_alpha') lists the known values (over MCP, the
    tool usda_nass_list_param_values).` A task of `BULK_TASKS` has no tool (ADR-0040,
    decision 4), and an error names it alone.

## Consequences

- The HTTP envelope and the MCP text carry `published_at_naive`.

The conventions' header, §3, §4, §5 and §8, the README and the docstrings of `ResultMeta`,
`xippios.core.reference` and `UnknownCode` state its decisions from 1.28 on.

## Amendment 2026-11-22

https://github.com/xippios/sdk-core/issues/440 amends decision 8 for a value that is no code, a
misfit that the trial of core 0.4.1 met in sdk-comtrade
(https://github.com/xippios/sdk-core/issues/430). `UnknownCode` takes one more keyword after
`source`, `outdated: bool = True`, named for the sentence it governs as `closest`, `hint` and
`reason` are named for theirs. Its tail, `If upstream added it since, the packaged list is out of
date.`, stands while `outdated` is true, the default, and a message with `outdated=False` ends
with its hint and its reason. The check of a packaged list passes `outdated=False` for a value of
its hint table alone (ADR-0045, decision 3, as amended on the same day): a value that is no code
of upstream's, such as sdk-comtrade's ISO alpha-3 `"CHE"` where upstream takes integers, which no
refresh of the list makes a code. Every other refusal keeps the tail, a source's own
`UnknownCode(hint=...)` and the check's refusal with `otherwise` among them, so a source on core
0.4.0 keeps its message. Decision 8 stands otherwise as written, and conventions §5 states the
hinted refusal in a sentence of its own.
