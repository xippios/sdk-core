# ADR-0058: A fourth reason for one consumer and what a core patch keeps compatible

Status: Accepted · Date: 2026-11-22 · Decided by https://github.com/xippios/sdk-core/issues/455

## Context

The organization's conventions check judged `main` at the last step of core 0.4.1 before its
release, the range from `v0.4.0` on, and held it on two decisions of the maintainer that the
documents did not carry yet (https://github.com/xippios/sdk-core/pull/453#issuecomment-7082327015,
findings 1, 2 and 7).

Two public names entered core with one consumer. `naive_time` has one caller, sdk-usda-esr, by
the maintainer's answer on https://github.com/xippios/sdk-core/issues/371, part 1 (ADR-0052), and
`record_task` with `record_task_sync` one source that records through tasks, sdk-google-mail, by
his answer on https://github.com/xippios/sdk-core/issues/364, part 3 (ADR-0057). ADR-0023,
decision 2, admits code with two consumers, and its decision 3 admits code with one only for a
reason of three kinds, a family invariant, one of three security properties and what the
adapters need, which the definition of done asks a core PR's ADR to name. ADR-0052 and ADR-0057
each said that its reason was none of the three, so neither met the definition of done's line
as it read. ADR-0023 holds two amendments already, of 2026-10-27 and of 2026-10-29, so the
change is a record of its own, to which ADR-0023 points.

Two decided changes of 0.4.1 make a source's own test fail when its lock moves to 0.4.1 inside
`xippios-core~=0.4.0`: the new tests of the family check, which fail at once (ADR-0044,
decision 4, by https://github.com/xippios/sdk-core/issues/359), and the recorder's refusal of an
answer of a 1xx or a 3xx status on every path (ADR-0048, decision 4, by
https://github.com/xippios/sdk-core/issues/364), which fails one test of sdk-cashctrl that hands
a built 302 to `fixture_from_response` (https://github.com/xippios/sdk-cashctrl/issues/134).
Neither changes a source's package or what its callers see. Conventions §12 and ADR-0039,
decision 1, say "Core patch releases stay compatible." and do not say whether such a change
keeps a patch compatible.

## Decision

1. **The maintainer's decision on a step's closed design question is a fourth reason for one
   consumer.** This supersedes the closed list of ADR-0023, decision 3, "the reason is one of
   three": the reason is one of four, (a), (b) and (c) as ADR-0023 words them, and (d) the
   maintainer's decision on the closed design question of the step that adds the code, which
   that step's record names by the question's URL. For `record_task`, which step 17.1 added as
   the follow-up that the answer on step 17's question made, the follow-up counts as part of
   step 17, so the question of (d) is step 17's, as the answer on
   https://github.com/xippios/sdk-core/issues/455 takes it. The rest of ADR-0023 stands as
   written: the reason is stated in the ADR that introduces the code, and "A second source will
   probably need it" stays no reason. ADR-0052 and ADR-0057 name the reason (d) of their names in an
   amendment of 2026-11-22 each. For `naive_time` it is the answer on
   https://github.com/xippios/sdk-core/issues/371, part 1, the design question of step 8 of
   0.4.1, which added it. For `record_task` it is the answer on
   https://github.com/xippios/sdk-core/issues/364, part 3, the design question of step 17, which
   made the recording of every exchange of a task ride with the recorder's frame of 0.4.1,
   against its recommendation, and so admitted the helper with one consumer. Step 17's
   follow-up, 17.1, built it, and the answer on https://github.com/xippios/sdk-core/issues/376,
   the follow-up's own design question, decided its shape and not its entry. The recommendation of
   https://github.com/xippios/sdk-core/issues/455, which its answer took, names the answer on
   https://github.com/xippios/sdk-core/issues/364 as the reason of `record_task`.
2. **A core patch keeps a source's package and its callers compatible.** "Core patch releases
   stay compatible.", in conventions §12 and in ADR-0039, decision 1, means that a patch of
   core keeps a source's package and what its callers see through its Python API, its MCP tools
   and its routes compatible, while a check of `xippios.core.testing` that a record makes
   stricter, a test of the family check or the recorder's refusal of an answer, may fail a
   source's own test when its lock moves to the patch. The handover's section `Adopting core
   X.Y.Z` lists each such check in its part for every source, and the source meets it in the
   adoption PR of the patch. A change that breaks a source's package or what its callers see
   still bumps core's minor, as §12 says. The rest of ADR-0039 stands as written.

## Consequences

- The definition of done's line on a core PR's consumers and the review checklist's item 11
  name the fourth reason beside ADR-0023, decision 3, so ADR-0052 and ADR-0057 meet them as they
  read after their amendments. ADR-0023 carries an amendment of 2026-11-22 that names decision 1
  here as the one that supersedes its closed list.
- The release of 0.4.1 stays a patch, which every source's bound `xippios-core~=0.4.0` takes, and
  each source meets the checks that the handover lists for 0.4.1 in the adoption PR of its
  patch. The handover no longer calls every change of 0.4.1 additive.
- The other options of https://github.com/xippios/sdk-core/issues/455 were to take `naive_time`
  and `record_task` out of the public surface until a second consumer came, which took back two
  answers of the maintainer, to have the definition of done alone name the exception, which left
  the rule and the record it cites saying different things, to release 0.5.0, which no source's
  bound takes, so that each source would adopt it by a minor of its own, and to leave §12 as it
  read, for the release review to hold the same point again.

Conventions §12, the definition of done's Code block, the review checklist's item 11 and the
handover's section `Adopting core 0.4.1` state its decisions from 1.29 on.
