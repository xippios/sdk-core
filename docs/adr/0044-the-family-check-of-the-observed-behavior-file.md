# ADR-0044: The family check of the observed-behavior file

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/359

## Context

Conventions §3 keep what a source observed of upstream, which no page of its documentation
states, in one file written by hand, `docs/upstream/OBSERVED.md`, which `FETCHED.md` lists in
a row of its own, and give each note its evidence (ADR-0028, decision 5). Six sources keep the
file on 2026-11-21: sdk-usda-esmis with 17 notes, sdk-usda-wasde with 21, sdk-usda-esr with 13,
sdk-cashctrl with 29, sdk-eurostat with 1 and sdk-faostat with 12. Four of them hold it by a
`tests/test_observed.py` of their own and sdk-faostat by two tests of its
`tests/test_refresh_upstream.py`, five copies that share their core: a `###` section is a
note, its last paragraph is its probe, `FETCHED.md` has the row, and every file a note cites
exists. They differ in the rest (https://github.com/xippios/sdk-core/issues/348). The release
check held sdk-usda-esr's release on the file (https://github.com/xippios/sdk-usda-esr/pull/47),
and the sources' patches on core 0.4.1 would write a sixth to a twelfth copy.

The copies cannot be taken as they stand. The rows of `FETCHED.md` are four, six and nine cells
wide. 72 notes open their last paragraph with `Probe:` and sdk-usda-wasde's 21 with
`Observed:`, the two kinds of evidence §3 names, a probe and the release files a layout was
written from. sdk-usda-esr's last note ends with a link reference definition.

## Decision

1. **Three rules, where a source keeps the file.** The family check holds three rules of
   `docs/upstream/OBSERVED.md`, one test each, and a source without the file passes all
   three, as a source without tenants passes the tenant check, since §3 asks for the file
   only where a source observed something:
   - `test_family_fetched_md_lists_observed_md_in_a_row_of_its_own`: `docs/upstream/FETCHED.md`
     holds a table row whose first cell is `OBSERVED.md`, whose last cell says that it is
     written by hand and whose cells between, if any, are `-`. The row is told by these
     three and never by its width, so the tables of four, six and nine cells pass alike,
     and the snapshot frame writes the row in the one form it chooses
     (https://github.com/xippios/sdk-core/issues/363).
   - `test_family_observed_notes_end_with_their_probe_and_date`: the file holds one note at
     least, and the last paragraph of every note opens with `Probe: ` or `Observed: ` and
     an ISO 8601 date right after the label, `Probe: 2026-11-20, ...`.
   - `test_family_observed_md_cites_files_that_exist`: every code span of the file whose
     text starts with `tests/`, `docs/`, `src/` or `scripts/`, holds no space and ends in
     an extension names a file that exists, from the repository's root. The rule reads the
     whole file, the lines above its first note included, as three of the copies do.
2. **What a note is.** A note is a `###` section: it runs from its heading to the next
   heading of level one to three outside a fenced code block, so a `##` heading groups
   notes and is none itself, and a `####` heading stays inside its note. Its paragraphs are
   its blocks between blank lines, each read with its lines joined. A link reference
   definition is dropped before the last paragraph is judged, since it renders as nothing.
   Two notes of one heading under two groups are two notes, each judged.
3. **The fourth rule stays the source's.** That no dated note of what upstream answered
   stands outside the file is the source's own test and the review's: the two heuristics
   that sdk-usda-esr and sdk-cashctrl hold it by match text that tells no probe in seven to
   eleven other sources. What a source holds beyond the three rules stays its own too: an
   operation of its snapshot in each probe, a recording's day among the probe's dates, the
   release files a layout names and the documents that point to the file.
4. **It fails at once.** The three rules fail from core 0.4.1 on, with no release that warns
   first, as every new family check of 0.4.1 does. A source meets them when its patch moves
   its lock to 0.4.1. sdk-eurostat's `FETCHED.md` has no row, and the source fails the
   first rule until its patch writes it, which its capture script does at its next run
   (https://github.com/xippios/sdk-eurostat/issues/49).

## Consequences

- The check has its consumers in the six sources that keep the file, five of which hold a
  copy today (ADR-0023, decision 3). sdk-usda-esmis, sdk-usda-wasde, sdk-usda-esr and
  sdk-cashctrl delete from their `tests/test_observed.py`, and sdk-faostat from its
  `tests/test_refresh_upstream.py`, what the family check now holds and keep what is their
  own. The changelog's Hand-apply note names each test.
- The check reads text: whether a date is the day the probe ran, and whether a probe names
  an operation of the snapshot, is the source's own test. A note that a renderer reads
  otherwise than line by line, under a setext heading or in an indented code block, is the
  review's.
- A file cited by a path relative to `docs/upstream/`, or by a bare name such as a release
  file's, is not held, and a source that cites so keeps its own test of those citations.
