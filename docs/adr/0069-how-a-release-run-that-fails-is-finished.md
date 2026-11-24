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
release PR is not merged while another release run waits at `pypi`, is what ADR-0039, decision
3, leaves to the process of the work: the organization's conventions check found both (finding 2
of https://github.com/xippios/sdk-core/pull/558#issuecomment-7140020024;
https://github.com/xippios/sdk-core/issues/559).

This record states the four sentences of §12 as they stand, the third without its clause on a
release PR's merge, so no rule changes. It changes no decision of ADR-0039, which keeps its two amendments, and supersedes
no record, since these rules were never among ADR-0039's decisions. When a release PR merges is
not decided here: ADR-0039, decision 3, leaves who merges a release PR, and when, to the process
of the work, which binds no repository.

## Decision

1. **Once the tag stands, the failed jobs finish the run.** A release run that fails is finished
   by its own jobs, never by a push: once the tag stands, only "Re-run failed jobs" finishes it,
   since a dispatch or "Re-run all jobs" stops at `release-check`, which finds the tag. A build
   that fails for good after the tag leaves a tag without a release, which a patch release
   mends.
2. **Before the tag, the same.** A `ci` that fails before the tag is re-run the same way, by its
   failed jobs and never by a push of a fix, and so is a run that the deployment-branch policy of
   `pypi` refused, once a maintainer has set the policy to `main`.
3. **No `concurrency` group.** `publish.yml` keeps no `concurrency` group, since GitHub keeps one
   pending run of a group and cancels it for the next, so a release run queued behind a run that
   waits at `pypi` would be lost. Two pushes to `main` close together can therefore both find the
   version untagged, which decision 4 finishes.
4. **Two runs that found the version untagged.** The second run's push of the tag fails or,
   where the first run's `ci` failed, the second tags a later commit. The failed jobs of the run
   whose commit is the release are re-run, and where the other run tagged a later commit, a
   maintainer rejects its deployment at `pypi` and the release is made again as a patch.

## Consequences

- Conventions §12 states decisions 1 to 4, one sentence each that cites its decision, and says
  that whether a release PR merges while another release run waits at `pypi` is the process of
  the work (ADR-0039, decision 3). The handover's part for 0.5.0 cites this record for how a
  release run that fails is finished.
- No source's code, workflow or test changes, and the conventions keep version 1.30, since every
  rule reads as it did.
