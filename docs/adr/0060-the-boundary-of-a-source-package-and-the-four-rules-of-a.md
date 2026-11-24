# ADR-0060: The boundary of a source package and the four rules of a record that a package shapes itself

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/474

## Context

ADR-0028 says that a package mirrors upstream and maps no source's concept onto another's, and
it says how a name, a snapshot and a fixture stay faithful. It does not say what a package
returns and what it leaves to those who build on the packages. The twelve sources read the gap
each its own way: sdk-usda-esr computes `meta.vintage` as the newest week of its rows,
sdk-usda-gats borrows six release times from another flow's list, sdk-usda-psd, sdk-usda-esr and
sdk-comtrade rank countries and partners, sdk-usda-nass sums the counts of a split into
`meta.total`, and sdk-usda-nass, sdk-comtrade, sdk-eurostat, sdk-usda-wasde and sdk-usda-psd
answer slices whose filters the caller cannot change.

The maintainer decided the boundary as six sentences, sentence by sentence, and
https://github.com/xippios/sdk-core/issues/474 decided where they stand. A new record beside
ADR-0028, since its decisions 2 to 8 do not change and the sources cite it often, so that
superseding it would cost each source its citations, while an amendment is one sentence and
cannot hold six. The organization's check blocks a release only on a sentence of the conventions
that can be quoted alone with its record, so each sentence takes a decision here to cite, and the
conventions take the six sentences word for word in §14 and each rule once, in the section of its
subject.

The maintainer's answer on https://github.com/xippios/sdk-usda-esr/issues/60, part 3, the interview of
sdk-usda-esr's adoption, read decision 1 for the family on the same day: a time that upstream
prints is read into the type that keeps all of it, and no text stands beside it. Decisions 7 to
9 state that reading.

## Decision

1. **Values.** A package returns each value of upstream's data as upstream states it, under
   upstream's own name, code and unit. It derives no value of the data and converts none. Where it
   reads a printed text as a number or a time and the reading can lose something, the text stands
   beside it. Upstream's own name is the name in its API document, spelled as the language allows.
2. **Releases.** A package reports a release identifier as upstream states it for the data
   answered, and may filter its own items by it. Where an answer holds several releases it reports
   the newest. It compares no values across releases and reconciles none.
3. **Labels and lists.** A label names a code in upstream's own words, from upstream's own list of
   the same source. A shared rule of the workspace names a domain concept only to find where such
   a label is owed. A package builds no list, name, grouping or rule of its own.
4. **What an answer holds.** A task is an upstream operation, a list that orients a caller, or a
   series over periods. It returns what its operation returns for the arguments given, and a caller
   can set what upstream documents. A package adds no task that fixes filters, sorts, ranks or cuts
   for the caller. The cut of an answer over MCP is the one choice made for the caller: its note
   says so, and it changes no value.
5. **Usability.** Usability inside the scope is: typed answers, errors that say what upstream
   refused and what to send, paging and a series over periods, lists that orient a caller, checks
   of what upstream returned, and the record of upstream's observed behavior.
6. **The family's own.** What is about the call and not about upstream's data is the family's own:
   the envelope, a write's preview and acknowledgement, a download's record, an error's wait, a
   tenant's name. What a package withholds by the identifier rule, it withholds on purpose.
7. **A record that a package shapes itself** follows four rules, as sdk-usda-wasde's record of a
   release's tables will: one value per record; a field under upstream's name holds upstream's
   text; a reading of that text stands beside it under the one suffix of a reading,
   `<stem>_number`; and a code and its label stand side by side, the label as `<stem>_label`
   beside the code `<stem>`. A text stands beside a reading only where no type keeps what upstream
   sends, so the family has no suffix for a time, `<stem>_number` is the one twin of a reading and
   `<stem>_label` stays the name of a code's label (https://github.com/xippios/sdk-usda-esr/issues/60, part 3). The one exception
   is ADR-0020's, decision 2, as amended on this date: where the file names no value that the
   record needs, as sdk-usda-wasde's XML names no commodity on some pages, the record reads it from
   the table's title or from the same release's XLS and says which.
8. **What the sentences take from the packages.**
   - A task that fixes filters over one upstream operation, a slice, leaves the source package, and
     what is built on the packages takes it. A lookup by a key that the caller names stays as an
     argument of its list task, and a task that picks the latest release leaves with the slices
     (decision 4).
   - A ranking leaves, with the groupings and the joins that serve it (decisions 1, 3 and 4).
   - `meta.vintage` is set only from a release identifier that upstream states for the data
     answered. A date computed from the rows and another flow's release list leave it empty, and
     the task's docstring says why. A task that reads a file has one reading of it, the catalog's
     release identifier (decision 2; ADR-0041, decisions 1 and 6, and ADR-0020, decision 5, as
     amended on this date).
   - A value that upstream's record does not state stands in the envelope, never on the record,
     and core gives it its place: the names of the codes in an answer's rows and one place for a
     task's note, as https://github.com/xippios/sdk-core/issues/478 decided (decisions 1 and 6).
   - A value that upstream prints as text and that can carry a mark reaches a caller twice: the
     text as printed, and beside it the parsed number, or nothing where the text holds none
     (decision 1).
   - A time that upstream prints is read into the type that keeps everything upstream sends,
     naive where upstream states no zone, and no text stands beside it: sdk-usda-esr's
     `releaseTimeStamp` reads as a time that keeps upstream's fraction of a second, and the
     private attribute that kept its text goes (decision 1; https://github.com/xippios/sdk-usda-esr/issues/60, part 3).
   - A caller can set what upstream documents as a parameter, and a package's default is upstream's
     own (decision 4).
   - `meta.total` is upstream's count and is summed no more than it is computed: a task that
     assembles its answer from several requests leaves it `None` unless upstream counts the whole
     request (decision 1; ADR-0034, decision 4, as amended on this date).
9. **The family check holds the form of a reading.** `test_family_readings_stand_beside_their_text`
   reads every model that a task's `Result[T]` reaches, read and write tasks alike, through its
   fields and computed fields, and fails a field `<stem>_number` whose stem is a field of the same
   model that holds no text, `str` or a subclass, optional or not. The stem is the name before the
   suffix where the model holds a field of that name. A name whose part before the suffix names no
   field of its model is upstream's own name and no reading, as sdk-cashctrl's `street_number` is,
   and the check passes it. A field `<stem>_label` is the label of a code, no reading, beside a code
   that may be an integer (ADR-0056), so the check does not read it, and sdk-cashctrl's
   `row_label` and `field_label` are upstream's own names as well (https://github.com/xippios/sdk-usda-esr/issues/60, part 3). The check therefore
   holds a reading's form and not that a reading which can lose something has one: that is the
   review's, by decision 1. One pair stands in the family today, sdk-usda-nass's `value` and its
   computed `value_number`, and no model of the twelve sources holds a suffixed field beside a stem
   that is no text, so a source whose upstream names such a pair reopens the stem rule here.

## Consequences

- Conventions §14 hold the six sentences of decisions 1 to 6 word for word. Each rule stands once
  in the section of its subject and cites this record: §2 the task of decision 4, §3 the values,
  the labels and the shaped record of decisions 1, 3 and 7, §4 the release identifier and the
  count of decisions 2 and 8, §8 the cut of decision 4, and §10 the check of decision 9. The
  review checklist's item on fidelity judges a change against this record.
- ADR-0028, ADR-0001, ADR-0020, ADR-0034 and ADR-0041 each take one sentence that points here;
  their other decisions stand. ADR-0041 then holds two amendments, its last.
- The sentences bind a source from its adoption of core 0.5.0, which takes what the source does not
  meet yet, named by source and file in the release's changelog: the slices of sdk-usda-nass,
  sdk-comtrade, sdk-eurostat, sdk-usda-psd and sdk-usda-wasde and the rankings of sdk-usda-psd,
  sdk-usda-esr and sdk-comtrade leave; sdk-usda-esr's computed vintage and sdk-usda-gats's six
  borrowed release times stay empty; sdk-usda-nass's split leaves `meta.total` empty; and
  sdk-faostat and sdk-eurostat keep the printed text beside the number that they parse.
- A slice that leaves is no loss to a caller: the task it fixed takes the same arguments, and what
  is built on the packages names its own slices.
