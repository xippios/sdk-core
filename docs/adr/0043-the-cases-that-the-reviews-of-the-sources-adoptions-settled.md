# ADR-0043: The cases that the reviews of the sources' adoptions settled

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/355

## Context

The sources' adoptions of core 0.4.0 and their releases met cases that conventions 1.28 leave
open, and their reviews and the organization's release check settled each by a decision of a
pull request. The check judged one adoption entry and one age of a live run two ways on releases
of two days (https://github.com/xippios/.github/issues/116), and from step 6 of `.github 0.5.0`
a finding blocks only where it quotes the sentence that a change breaks
(https://github.com/xippios/.github/issues/119), so a case that a pull request settled binds the
next release only once the conventions say it. Each of the twelve source patches on core 0.4.1
adopts core and the template, adds refusals, decoders and tests of built answers, and releases
with a live run, so each meets every case again. The rows are
https://github.com/xippios/sdk-core/issues/342, https://github.com/xippios/sdk-core/issues/345,
https://github.com/xippios/sdk-core/issues/346, https://github.com/xippios/sdk-core/issues/347
and https://github.com/xippios/sdk-core/issues/351.

## Decision

1. **An adoption's entry names all three versions as they stand after it.** The changelog entry
   of an adoption names the core bound, the template's tag and the conventions' version as they
   stand after the adoption, changed or not, so that one form fits the adoption of a core minor
   and a template-only update alike and the tooling can write it. The human decided it on
   2026-11-21 (https://github.com/xippios/sdk-core/issues/355). The other option, an entry that
   names what the adoption changed, such as `Adopts sdk-template v0.3.2, from v0.3.0.`, is the
   shortest, and a reviewer has to know what the adoption changed to judge it: the check passed
   that line on https://github.com/xippios/sdk-usda-gats/pull/52 and
   https://github.com/xippios/sdk-usda-wasde/pull/46 and held
   https://github.com/xippios/sdk-google-mail/pull/65 on it
   (https://github.com/xippios/sdk-core/issues/347).
2. **A release's pull request rewords no entry.** It assembles the entries as their fragments
   read, and a wrong entry is corrected in its fragment, by a pull request before the release,
   so the released text is the one that was reviewed and the same entry gets the same verdict on
   every release. The human decided it with decision 1. The release of sdk-google-mail reworded
   its adoption's entry in its own pull request (decision 8 of
   https://github.com/xippios/sdk-google-mail/pull/65), which saved a pull request and released
   a text that no review had read as a fragment. A release regroups no entry either: it takes
   each fragment under the group that its name gives (`changelog/README.md`).
3. **An adoption's fragment takes its group by what the adoption does.** The fragment of a
   source's adoption that brings a core minor is `breaking`, since §12 makes that adoption a
   breaking change of the source (ADR-0039, decision 1), so that no release moves it by hand:
   the ten later releases of the adoptions of core 0.4.0 moved the entry from Changed to
   Breaking by hand, each by a decision of its pull request, after sdk-usda-esmis 0.3.0 and
   sdk-eurostat 0.3.0 had shipped it under Changed (finding 3 of the review of
   https://github.com/xippios/sdk-usda-nass/pull/81,
   https://github.com/xippios/sdk-core/issues/342). The fragment of an adoption that brings no
   core minor, a template-only update or a core patch inside the source's bound, is `changed`:
   the row names the group of a core minor alone, and this is the reading the releases shipped.
   `changelog/README.md` gives a change its group by what it does, such an adoption breaks
   nothing of the source's, and every adoption entry without a core minor in the released
   sections of the twelve sources' `CHANGELOG.md` stands under Changed.
4. **A source's release cites a live run on its base.** The release's pull request cites a green
   run of `live.yml` on the commit of `main` that it starts from, the nightly run or one dispatch
   of `live.yml` on `main`, as step 3 of each source's `/release-prep` has it
   (https://github.com/xippios/sdk-core/issues/351). A run on an earlier commit of `main` is no
   such run, whatever the merges after it changed, so a release whose base moved after its run
   waits for the next nightly or one more dispatch. Reviews accepted a run one merge older,
   where the later merge changed tests alone, on https://github.com/xippios/sdk-usda-wasde/pull/46
   and https://github.com/xippios/sdk-google-mail/pull/65, whose decision 2 named it a departure
   from the letter of step 3, and the check held https://github.com/xippios/sdk-cashctrl/pull/120
   on the same, which then cited a third run, on its base (decision 2 there). The rule takes the
   letter of step 3, for two reasons. The row that gave step 3 its rule,
   https://github.com/xippios/sdk-template/issues/73, has the run postdate the last pull request
   before the release, an adoption that lands late included, so that no task reaches its tag
   without a live test. And a judgment of what the later merge changed is the reading that gave
   one case two verdicts (https://github.com/xippios/.github/issues/116), while the commit that a
   run tested and the commit that a release starts from compare without one. The cost is one
   more run where a merge lands after the live run.
5. **Three cases fall between the kinds of a built answer.** Conventions §10 name five kinds of
   a body that a test serves or reads where it was not recorded (ADR-0028, decision 8), and the
   reviews settled three cases between them (https://github.com/xippios/sdk-core/issues/345).
   - A recorded answer changed in its status, its content type and its body at once is a new
     answer composed in a recorded shape, the second kind, which stands only where the snapshot
     documents it, and not a recording changed in memory, the fourth: decision 2 of
     https://github.com/xippios/sdk-usda-esr/pull/55, which therefore serves no empty 404 off
     an exports path, and decision 3 of https://github.com/xippios/sdk-cashctrl/pull/127, whose
     status errors keep a body composed in the shape of the recorded 401.
   - A value that no route serves as an answer and no `classify` reads, handed to the code under
     test, is an input of the test and takes no kind: a literal given to a model or a scrub, or
     an exchange given to a recorder's step alone. Decision 3 of
     https://github.com/xippios/sdk-google-mail/pull/68 and decision 2 of
     https://github.com/xippios/sdk-cashctrl/pull/127 settled it, and the second has an answer
     that a route serves or that `classify` reads take a kind. How a test says that a value is
     an input is the mark's, which https://github.com/xippios/sdk-core/issues/367 decided.
   - A recording replayed at its own path for other parameters is the third kind, and the test
     names the condition under which upstream answers alike there, or says that it asserts only
     what was sent: decision 5 of https://github.com/xippios/sdk-google-mail/pull/68 and
     decision 10 of https://github.com/xippios/sdk-cashctrl/pull/127. In sdk-google-mail the
     condition took a second round: the recorded answer of a refresh stands for that of a code
     exchange only without `access_type=offline` (decision 4 there).
6. **Two kinds of a source's own messages name no request.** The rule of §5, that a message names
   its request with `request_description`, binds the messages about an answer and a refusal of a
   request already built (ADR-0030, decision 4). A refusal that the package makes of the call as
   given, before any request or after a read and before the write, names the argument, the
   record or the tool that it refuses and that nothing was sent. The subject of a decoder that
   reads a body without its response names the operation that its caller gives it, as `parse`
   names the `endpoint` that a wrapper passes. Decisions 3 and 8 of
   https://github.com/xippios/sdk-cashctrl/pull/122 drew the line by ADR-0030, decision 4
   (https://github.com/xippios/sdk-core/issues/346).

## Consequences

- Each rule is one sentence of the conventions that cites this record, so the release check
  quotes it alone, and `tests/test_conventions.py` holds each sentence and the item of the review
  checklist that judges it.
- The twelve source patches on core 0.4.1 write their adoption's entry in one form, under
  `changed`, since core 0.4.1 is a patch inside their bound.
- A release whose base moves after its live run takes one more run before it merges.
- The check of a built answer's mark, step 5 of sdk-core 0.4.1, reads the cases of decision 5.

Conventions §5, §10, §12 and §15 and the review checklist's items 3, 4, 12 and 13 state its
decisions from 1.29 on.
