# ADR-0069: How a release run that fails is finished

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/484

## Context

ADR-0039, decision 6, states the release train: the release PR's merge on `main` runs
`publish.yml`, which tags `vX.Y.Z` on the merge commit and waits at the environment `pypi` for a
maintainer's approval before the trusted publisher uploads. The tag comes before the build, and
the job `release-check` stops a run that finds its version tagged. How a release run that fails
is finished was written with the train on 2026-10-26, in the handover's part for core 0.2.1
(https://github.com/xippios/sdk-core/blob/v0.4.1/docs/handover.md), and no record took it.

When the handover kept one part (ADR-0068, decision 5), the answer on
https://github.com/xippios/sdk-core/issues/484 moved those sentences to conventions §12, which
cited ADR-0039, decision 6, for them. That decision states none of them, and one of them, that a
release PR is not merged while another release run waits at `pypi`, bears on what ADR-0039,
decision 3, leaves to the process of the work: the organization's conventions check found both
(finding 2 of https://github.com/xippios/sdk-core/pull/558#issuecomment-7140020024;
https://github.com/xippios/sdk-core/issues/559).

This record states the four sentences of §12 on a failed release run as they stand, and the
scope of the third and the fourth that a fifth sentence gives, so no rule changes, and supersedes
no record, since these rules were never among ADR-0039's decisions. ADR-0039, decision 3, leaves
who merges a release PR, and when, to the process of the work, which binds no repository. This
record adds to it the one constraint that the missing `concurrency` group imposes on when a
release PR merges (decision 3), and everything else about who merges and when stays the process
of the work. ADR-0039 holds two amendments already, both of 2026-11-24, so the change is a record
of its own, to which ADR-0039 points.

## Decision

1. **Once the tag stands, the failed jobs finish the run.** A release run that fails is finished
   by its own jobs, never by a push: once the tag stands, only "Re-run failed jobs" finishes it,
   since a dispatch or "Re-run all jobs" stops at `release-check`, which finds the tag. A build
   that fails for good after the tag leaves a tag without a release, which a patch release
   mends.
2. **Before the tag, the same.** A `ci` that fails before the tag is re-run the same way, by its
   failed jobs and never by a push of a fix, and so is a run that the deployment-branch policy of
   `pypi` refused, once a maintainer has set the policy to `main`.
3. **No `concurrency` group, and no release PR merged while a release run waits.** `publish.yml`
   keeps no `concurrency` group, since GitHub keeps one pending run of a group and cancels it for
   the next, so a release run queued behind a run that waits at `pypi` would be lost. Two pushes
   to `main` close together can therefore both find the version untagged, which decision 4
   finishes, and a release PR is not merged while another release run waits at `pypi`. That is
   the one constraint that the missing group imposes on when a release PR merges, and this record
   adds it to ADR-0039, decision 3; everything else about who merges a release PR, and when, stays
   the process of the work. The constraint holds where a release has a `pypi` stage, as
   `publish.yml`'s has; sdk-template's `release.yml`, which publishes nothing to PyPI, has none.
4. **Two runs that found the version untagged.** The second run's push of the tag fails or,
   where the first run's `ci` failed, the second tags a later commit. The failed jobs of the run
   whose commit is the release are re-run, and where the other run tagged a later commit, a
   maintainer rejects its deployment at `pypi` and the release is made again as a patch. The
   rejection holds where a release has a `pypi` stage, as decision 3's constraint does.

## Consequences

- Conventions §12 states decisions 1 to 4, each in a sentence that cites its decision, and the
  scope of decisions 3 and 4 in one more. The
  handover's part for 0.5.0 cites this record for how a release run that fails is finished.
- Who merges a release PR, and when, stays the process of the work by ADR-0039, decision 3, but
  for the one constraint of decision 3 here.
- No source's code, workflow or test changes, and the conventions keep version 1.30, since every
  rule reads as it did.
