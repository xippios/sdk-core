# ADR-0068: Which document holds what, the handover's one part and the surface in two counts

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/484

## Context

Core keeps five documents that bind a source or that a source's work reads: the conventions, the
README, the review checklist, the definition of done and the handover. By core 0.4.1 they had
grown into each other. The conventions held 1,459 lines and 1,695 by the steps of 0.5.0 before
this record, among them sentences that only describe what core's code does, which the README
describes too; the history of rules, as the release from which each binds a source and the
route of a source frozen on a template tag; and the cases of twelve sources, 167 mentions of a
source or a publisher on 120 lines. The items of an adoption stood in five places: §15 of the
conventions, the definition of done's Adoption PR block, the review checklist's item 12, core's
pull request template and each part of the handover. The handover held a part for each release
since the first, each with lists of every source.

The answer on https://github.com/xippios/sdk-core/issues/484 settled which document holds what:
its part 2 has the conventions keep each rule that a source is held to as one sentence with its
record, one case per sub-rule and no history, the README say how core's names are called, and
the tests that pin sentences follow each trim; its part 3 gives the handover one part for 0.5.0.
Part 4 of the answer on https://github.com/xippios/sdk-core/issues/485 changed that part 3: the
handover's part names no source, and each source's list goes to its own adoption issue. Part 7
of the same answer has the statement of core's surface count the run-time part and the
workbench apart, without a split of the package. ADR-0065 names the invented source and what
binds.

Every source of the family records template `v0.4.0` in its `.copier-answers.yml`, so no
source stands on a frozen template tag or before a release from which a rule binds.

## Decision

1. **The conventions hold what binds a source.** Each rule that a source is held to, one that a
   check of core fails or a review blocks on, stands in `docs/conventions.md` once, in the
   section of its subject under the fifteen section numbers, as one sentence that can be quoted
   alone and cites its record. A sentence that says how a name of core is called or what core's
   code does is the README's; where one sentence does both, the conventions keep it and point to
   the README for the call. A sentence that a test of core pins stays where the test reads it,
   since the organization's check quotes it.
2. **One case per sub-rule, the invented source's.** A rule keeps at most one case for each of
   its parts, and the case is the invented source `example`'s (ADR-0065, decision 4). A rule
   that cannot be stated without a real upstream cites its record, where the case stands. §1 of
   the conventions reserves the slug `example` and lists no source of the family: the list
   stands where the sources are loaded, the host's extras and the organization's page.
3. **No history in what binds.** The history of a rule, the sentence that names the release
   from which a rule binds a source, and a route of §15 on which no source stands leave the
   conventions, the review checklist and the definition of done; the records and the changelog
   keep them (ADR-0065, decision 5). A rule binds a source from its adoption of the release
   whose conventions hold it (conventions §15, item 8). Route (3) of §15, a source frozen on a
   template tag, leaves by this decision, and ADR-0039 is amended.
4. **The adoption's items stand once.** Conventions §15 holds the items that an adoption PR is
   judged against, its routes and its reading for the host, the two lists of the handover's
   section for the release among them (https://github.com/xippios/sdk-core/issues/334,
   https://github.com/xippios/sdk-core/issues/349). The definition of done's Adoption PR block
   and the review checklist's item 12 point to §15 and copy none of its items, and core's pull
   request template links the definition of done in place of copying it.
5. **The handover holds one part that names no source.** `docs/handover.md` holds one part, for
   the coming release, and it names no source: the changes that a source's callers see, the
   conventions' changed rules by section, and what every source does. Each source's own list
   stands on its adoption issue, and the part of an earlier release leaves the file when the
   next part enters, since the records and the changelog tell history.
6. **A release states core's surface in two counts.** The statement of core's surface before
   and after a release counts the run-time part and the workbench apart, the workbench being
   `xippios.core.testing` and `xippios.core.refresh` with the modules under `testing/` and
   `refresh/`, each in names and in lines, as `scripts/count_surface.py` counts them. The
   package stays one.
7. **The pins follow the text.** A test of core that pins a sentence of a document follows a
   trim of that sentence in the same pull request, and a pin leaves only with the sentence it
   pins.

## Consequences

- The conventions name no source but `example`, outside the citation of a record, and a reader
  finds a real upstream's case in the record that a rule cites. They lose 145 lines of 1,695, and
  the README holds what they gave up of the client's hooks and its download.
- An adoption's review reads one list, §15's, and the definition of done and the review
  checklist no longer lag it.
- A source's adoption reads one part of the handover and its own adoption issue, and core's
  handover changes when a release does, not when a source does.
- ADR-0027, the record of one source's metered and content-bearing upstream, leaves core for that
  source's first record,
  https://github.com/xippios/sdk-x/blob/main/docs/adr/0001-x-metered-content-source.md, by part 4
  of the answer on https://github.com/xippios/sdk-core/issues/484, so a rule that it held cites
  that record (decision 2), while the superseded ADR-0010, ADR-0012 and ADR-0016 stay as written.
- ADR-0039 is amended: decision 2's third route leaves, and the definition of done's Adoption PR
  block points to §15 in place of mirroring it.
- A rule that a test pins keeps its sentence form, so a trim moves few pins, and the tests that
  read a source's name in a case follow the case to `example`.
