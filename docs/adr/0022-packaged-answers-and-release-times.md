# ADR-0022: Packaged answers and release times in `ResultMeta`

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview; the family review of 2026-10-25; the gats ruling of 2026-10-26) · Amended
2026-11-18 by https://github.com/xippios/sdk-core/issues/240

## Context

§4 defines `ResultMeta` for a fetched answer. Three sources answer `list_*` tasks from
packaged reference data, each its own way: `vintage` holds the list's fetch date (nass,
comtrade, psd) where it holds a release month in psd's data tasks; `endpoint` is
"reference" (nass), a file path (comtrade) or the operationId (psd); `retrieved_at` is
the answer time although nothing was fetched (the family review of 2026-10-25; queue
row 28 a).

FAS release times are naive (`2026-10-06T08:00:00`, no zone). `ResultMeta` refuses a
naive `published_at`, so nass, esr and gats leave it empty and gats puts the text into
`vintage` (ruling of 2026-10-26; queue row 39 d). ESMIS and WASDE print release times
the same way.

## Decision

1. **A packaged answer.** `retrieved_at` is the time the packaged list was fetched from
   upstream (the file's `fetched` value, as a cache hit uses the entry's stored time,
   ADR-0015). `endpoint` names the upstream operation the list came from (operationId
   or path), never "reference" or a file path. `vintage` holds an upstream release
   identifier only, and is `None` when the upstream has none: a fetch date is not a
   vintage. `total` is `None` unless upstream reports a count (ADR-0012). The
   `PackagedList` helper (review C13) builds this meta so no source writes it by hand.
2. **Naive release times.** `ResultMeta` gains `published_at_naive: bool = False`. A
   naive `published_at` is accepted only with the flag set and is stored as given, no
   zone attached; a naive value without the flag is refused as today. The flag means:
   upstream printed this time without a zone; it is upstream's text, not comparable
   across sources; a consumer that knows the publisher's zone assigns it outside the
   family (ADR-0003). `vintage` keeps the release identifier as upstream names it; where
   that identifier is the timestamp text, `vintage` holds the text and `published_at`
   its parsed value with the flag.
3. **`None` filters in `meta.request`** (row 28 b): a parameter the caller left `None`
   is omitted; `request` records what was sent.

## Consequences

- Core 0.3.0: the flag on `ResultMeta`; `PackagedList`. The HTTP envelope and the MCP
  text carry the flag.
- Adoption (§15, core 0.3.0): nass, comtrade, psd, esr and gats set `endpoint` and
  `vintage` by rule 1; esr and gats fill `published_at` from their release dates with
  the flag; gats drops the `(records, stored_at)` tuple once row 39 a lands; nass leaves
  `published_at` empty (`load_time` is a load time, not a release time). psd omits
  `None` filters (rule 3).
- Conventions §4: the two paragraphs and the field; the version bumps with the ADR.

## Amendment 2026-10-27

Johannes decided five points of the code on 2026-10-27, in the interview before core
0.3.0's PR 3, which carries this ADR's code.

1. **`fetched` is a time.** `PackagedList.fetched` is a timezone-aware UTC datetime,
   rule 1's `retrieved_at`. From template v0.3.0 on, the refresh scripts write
   `datetime.now(UTC)` to the second; a file whose `fetched` is a bare date, every file
   written before, reads as 00:00 UTC of that day, the start of the day the old scripts
   truncated the time to, and the source's next reference refresh writes the full time.
   A time without a zone is refused.
2. **One model.** `PackagedList(param, endpoint, fetched, records)`, frozen, with
   `PackagedList.load(package, name)` on `load_json`, `.meta(source, *, request,
   vintage, published_at, published_at_naive)` building rule 1's meta, `.parse(model, *,
   source)` validating the records, and `.write(path)` writing the file (`{"param",
   "endpoint", "fetched", "records"}`, indented, non-ASCII text kept, `fetched` to the
   second) for the refresh scripts. A list of values is records of one field named by
   the upstream parameter, and a table records of its columns: usda-nass's value files
   and sdk-comtrade's value files and CSV tables become such files in their adoptions,
   without network, their list tasks still returning strings. `endpoint` names the
   upstream operation, an operationId or a URL path; comtrade's
   `files/v1/app/reference/<file>.json` is a URL path and qualifies.
3. **The helpers.** `matches(search, *fields)` is the `search` filter of the list
   tasks, `closest(value, codes, *, n=3)` the two `difflib` passes of sdk-usda-psd (by
   code, then by name), and `UnknownCode(param, value, *, list_name, fetched, closest,
   hint, reason, source)`, an `InvalidRequestError`, the refusal of a code the packaged
   list lacks, with the copies' common message. A source with a strategy of its own for
   the closest codes (sdk-usda-gats's ISO codes, sdk-usda-esr's nearest integers) keeps
   it and passes its result, one consumer each (ADR-0023, decision 4).
4. **A cached answer's time.** `AsyncClient.get_answer(path, *, params, headers, auth)`
   returns `Answer(payload, retrieved_at)`: on a cache hit the time the entry was stored,
   else the time the answer arrived (ADR-0015, decision 5). sdk-usda-gats drops its
   `(records, stored_at)` tuples for it (queue row 39 a); `get_json` stays.
5. **Frozen series.** A series upstream no longer updates is marked in the README status
   table, by a status that names the last release, and in its task's docstring;
   `vintage` holds the last release's identifier. `ResultMeta` gains no field (queue row
   39 h).

With them, two rules of the code. Rule 2: the flag with an aware `published_at`, or with
none, is refused, since the flag says upstream printed a time without a zone. Rule 3:
`ResultMeta` drops a top-level `None` from `request` at construction, before the
credential rule, so a credential left `None` is not recorded as sent; a `None` inside a
nested mapping is kept as given.

In the review of that PR, on 2026-10-27, Johannes decided three more points:

6. **Period series** (queue row 39 i). A task that assembles a series from one upstream
   call per period states its ceiling, the most periods one call fetches (the MCP
   tool's, where it is smaller), and sets `vintage` to the newest release among the
   periods. Its docstring says what an unreleased period inside the range answers: the
   period is skipped where upstream's empty answer can be told from data (sdk-usda-psd's
   empty 404), and the whole range is refused, naming the latest released period, where
   it cannot (sdk-usda-gats's `[]` for an unreleased month looks like a month without
   trade). An empty answer that cannot be told from no data is never passed off as data.
7. **The refusal is `NotFoundError`**, naming the latest released period, as
   sdk-usda-gats refuses today; `InvalidRequestError` stays for a malformed request
   (ADR-0007).
8. **A packaged file holds the four keys and an optional `note`, nothing else.**
   `PackagedList` refuses any other key and gains `note: str | None = None`, free-text
   provenance that `.write` writes when it is set and core reads nothing from.
   sdk-usda-nass writes its `derived_from` into `note`, and its two lists derived from
   `unit_desc` keep `param: "unit_desc"` in files of their own names, which
   `load(package, name)` takes; sdk-comtrade writes its `note` and its `exceptions` into
   `note` as text, and its `origin` becomes `endpoint`.

Conventions 1.19 states the eight points in §3 to §6, and its preamble lists them among
the rules that bind a source from its 0.3.0 adoption.

## Reading 2026-10-29

A load time is never a vintage. Rule 1 says that a fetch date is not a vintage, and the
consequences have sdk-usda-nass leave `published_at` empty because its `load_time` is a
load time, not a release time. The sdk-usda-nass 0.3.0 debrief of 2026-10-29 proposed
`meta.vintage` from the newest `load_time` once core said how conventions §4 and this
ADR read for a source without a release calendar (queue row 264). They read: a source
whose only time is the time upstream loaded the data, as sdk-usda-nass's `load_time` is,
leaves `vintage` and `published_at` empty, since a load time is neither a release
identifier nor a release time, and a newest `load_time` computed across datasets is a
maximum the package computes, which queue row 199 (2) calls a guess. Johannes decided it
on 2026-10-29 (D110 (3)); sdk-usda-nass 0.3.0's PR 4, which waited on the question, is
dropped. Conventions §4 states it from 1.23 on.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **A printed zone that upstream contradicts** (decision 2; step 15;
https://github.com/xippios/sdk-core/issues/53, found by sdk-usda-esmis). Decision 2 flags
a time upstream printed without a zone. ESMIS prints one, `+0000` on `release_datetime`,
while the same site publishes its release calendar in Eastern time with the releases at
noon and writes the release files at 16:01 UTC, 12:01 Eastern (the WASDE of 2026-10-09),
so the printed zone does not say when the release happened. The flag also marks a time
whose printed zone upstream's own calendar and files contradict: the task keeps the
printed wall-clock time with its offset dropped, never converted, and sets the flag, and
the wrapper's model keeps the time as printed. Rule 2 refuses the flag with an aware
value, so the task drops the offset itself. The time is upstream's text, not comparable
across sources, as decision 2 says of a time printed without a zone. Johannes decided it
for sdk-usda-esmis on 2026-10-27, at its boundary interview, and sdk-usda-wasde reads the
time through it (ADR-0021).

(b) **A frozen feed whose answers carry their releases** (amendment 2026-10-27, point 5;
step 15; https://github.com/xippios/sdk-core/issues/108, found by sdk-usda-gats). Point 5
puts a frozen series' last release in `vintage`. sdk-usda-gats's UN Trade data, a feed
whose last release was 2021-01-18, answers one reporter and statistical year, and the
feed's release list gives each reporter-year a release time of its own
(`2020-06-03T05:50:46` for Iceland's 2019 exports). Where each answer of a frozen feed
carries its own release, `vintage` keeps that answer's release, and the feed's last
release goes to the README status value and the docstring only. The feed's list of
release dates keeps `vintage` empty, since it is no single release. Johannes confirmed
this option for sdk-usda-gats on 2026-10-28 (G5, at its PR 1 boundary) and left the
wording to the next batch of the documents.

(c) **A parameter that takes back a vintage** (decision 2; step 15;
https://github.com/xippios/sdk-core/issues/119, found by sdk-usda-esr, with
sdk-usda-psd). sdk-usda-esr's `get_release_dates(since=...)` takes the `meta.vintage`
text of an earlier call, ESR's naive release time, to return only the commodities
released since, and sdk-usda-psd's `get_release_dates` and `get_latest_release` take a
release month in the form its `meta.vintage` takes. Such a parameter takes the text as
`vintage` wrote it and keeps what is strictly later, an equal release being no newer.
`meta.vintage` and `meta.published_at` stay those of the whole upstream answer, not of
the filtered subset, so an empty answer still carries the marker to store for the next
call. Against a naive release time, a value with a zone is refused with
`InvalidRequestError`, never converted, since comparing the two would invent a zone
(ADR-0003), and so is a text the parameter cannot read (ADR-0007). Johannes decided
sdk-usda-esr's parameter on 2026-10-28 (G5): the text as input and the meta of the whole
answer; the refusal of a zone was the package's own.

(d) **Decisions 6 and 7 read as the sources apply them** (decisions 6 and 7; step 15;
https://github.com/xippios/sdk-core/issues/136, found by sdk-usda-nass; decided by
Johannes on 2026-11-17, https://github.com/xippios/sdk-core/issues/238). Decision 6
tells an unreleased period from a period without data by upstream's empty answer, and
refuses the range where it cannot. Four cases met it without a reading:

1. **No release calendar.** Where upstream names no release, so the latest released
   period is unknown, a range ends at the current period, and a period that counts zero
   is skipped, the docstring saying that a zero may be a period not yet released.
   sdk-usda-nass's `get_data(split_by_year=True)` refuses a year past the current UTC
   year with `InvalidRequestError` and skips a year counting 0, which Quick Stats does
   not tell apart from a year without records (Johannes, 2026-10-28).
2. **One period.** A task that fetches one period refuses a period after the latest
   released one where it knows that period, with decision 7's `NotFoundError`, as
   sdk-usda-gats's month tasks refuse a month their release list lacks. Where it does
   not know it, its docstring says that an empty answer may be a period not yet
   released.
3. **A split mode.** A split mode of a free-form query task, which fetches its range
   one period per call, is a period series, with its ceiling: sdk-usda-nass's
   `split_by_year`, 20 years, 5 on the MCP server.
4. **The calls a tool call spends.** The cap note counts the upstream calls that one
   tool call spends: the note that states the ceiling of a tool that assembles a period
   series, the cap on the periods one call fetches, counts them at that ceiling, as each
   of the four sources with such a tool does: sdk-usda-nass's 5 years on the MCP server
   at most 11 keyed calls, a first count and two calls a year; sdk-usda-gats's 24 months
   on the MCP server 24 requests; sdk-usda-esr's ten market years ten requests and one
   for the release list; sdk-usda-psd's 100 market years about 67 requests, from 1960,
   where its data starts, to the current forecast years.

(e) **A date-only release identifier** (decision 2; step 15;
https://github.com/xippios/sdk-core/issues/158, found by sdk-faostat, with
sdk-usda-psd). A release identifier that is a day or a month, with no time, such as
FAOSTAT's `date_update` (`2025-12-31`) or PSD's release month (`2026-10`), is neither a
time nor a time printed without a zone. It stays in `vintage` as upstream prints it, and
`published_at` stays empty: decision 2's flag covers a time printed without a zone, not
a day, and 00:00 of the day or the first of the month would date the release before it
happened, a look-ahead in an as-of store. The plan of core 0.4.0 settled it as both
sources have it.

Conventions §4 states the five points from 1.28 on.
