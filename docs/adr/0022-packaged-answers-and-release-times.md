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
