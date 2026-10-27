# ADR-0022: Packaged answers and release times in `ResultMeta`

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview; the family review of 2026-10-25; the gats ruling of 2026-10-26)

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
