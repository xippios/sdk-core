# ADR-0070: Core's version before its tag, and a release PR told by its title

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/561

## Context

ADR-0039 states the release train (decision 6): the release PR's merge on `main` runs
`publish.yml`, which tags `vX.Y.Z` from `pyproject.toml` on the merge commit. Its job
`release-check` lets a push through only when the version that `pyproject.toml` names has no tag
yet and `CHANGELOG.md` holds that version's `## [X.Y.Z] - ` heading, which the release PR alone
writes. Until 0.5.0 core's release PR also raised `version` in `pyproject.toml`, and ADR-0039,
decision 2, tells a release PR by its version, as the review checklist's item 13 did, by the
version in `pyproject.toml` changed. Conventions §12 say which files a release PR changes and
forbid no earlier pull request to raise the version.

Core 0.5.0 is proven before its tag on a commit of `main`, its candidate, with the packages that
prove it pinned to that commit (https://github.com/xippios/sdk-core/issues/485). At the
candidate, `pyproject.toml` named version 0.4.1, while every package rendered for 0.5.0 bounds
core at `xippios-core~=0.5.0`, so a package built from such a render could not install beside
the candidate.

The answer on https://github.com/xippios/sdk-core/issues/561 had a pull request before 0.5.0's
candidate raise the version, https://github.com/xippios/sdk-core/pull/564, a departure from the
usual order for 0.5.0 that no written rule forbids, and the answer on
https://github.com/xippios/sdk-core/issues/566 gave that pull request its changelog fragment, as
§12 asks of every pull request but a release's and Dependabot's. The organization's conventions
check then found item 13 and ADR-0039, decision 2, stale for core: the pull request that raised
the version is no release PR, and 0.5.0's release PR raises none (finding 2 of
https://github.com/xippios/sdk-core/pull/572#issuecomment-7142719021). That check reviews a pull
request as a release PR when it carries the `release` label or its title is `X.Y.Z Release`
whole: the condition of its workflow's job admits a title by its last word, and its gate matches
the title whole and passes any other title with a notice
(https://github.com/xippios/.github/blob/main/.github/workflows/conventions.yml,
https://github.com/xippios/.github/pull/124).

The answer on https://github.com/xippios/sdk-core/issues/575 kept this record in 0.5.0, its
decisions on the version before the tag written for 0.5.0 alone, as #561 decided, and its tell of
a release PR by the title, as the organization's gate tells it. ADR-0039 holds two amendments
already, both of 2026-11-24, so the change of its decision 2 is a record of its own, to which
ADR-0039 points, as it points to ADR-0069.

## Decision

1. **Core's `main` carries 0.5.0 before its tag.** For 0.5.0, a pull request before the
   candidate, https://github.com/xippios/sdk-core/pull/564, raises `version` in core's
   `pyproject.toml` to 0.5.0, with its `uv.lock`, and changes nothing under `src/`, so a package
   pinned to a commit of `main` installs within `~=0.5.0`. It tags nothing, since `CHANGELOG.md`
   holds no heading of 0.5.0 yet, and it brings its changelog fragment, as every pull request but
   a release's and Dependabot's does (https://github.com/xippios/sdk-core/issues/566). A later
   release of core is left to conventions §12 as it stands.
2. **0.5.0's release PR raises no version, and its merge tags.** Core's 0.5.0 release PR raises
   no version: it leaves `version = "0.5.0"` as decision 1 set it and still changes only the
   files of conventions §12, writing the `## [0.5.0] - ` heading into `CHANGELOG.md` from the
   fragments, and its merge tags `v0.5.0`, since `publish.yml` tags only once that heading stands
   beside a version that has no tag.
3. **A release PR is told by its title.** A release PR is told by its title, `X.Y.Z Release`
   whole, or by the `release` label, as the organization's conventions check tells it
   (https://github.com/xippios/.github/blob/main/.github/workflows/conventions.yml,
   https://github.com/xippios/.github/pull/124), and no longer by its version, which 0.5.0's
   release PR leaves as decision 1 set it (https://github.com/xippios/sdk-core/issues/561,
   https://github.com/xippios/sdk-core/issues/575). This changes ADR-0039, decision 2, in part,
   where it tells a release PR by its version; the rest of decision 2 stands as written.

## Consequences

- The review checklist's item 13 tells a release PR by its title or its label and cites
  decision 3; what the item judges in a release PR stands as it was.
- ADR-0039 names this record in a status field, `Decision 2 changed in part by ADR-0070
  (2026-11-24)`, and points to it in one paragraph of its section of 2026-11-24, and keeps its
  two amendments.
- The conventions keep version 1.30, since none of their sentences told a release PR by its
  version or had it raise core's: §12's release train, whose `publish.yml` tags `vX.Y.Z` from
  `pyproject.toml` on the release PR's merge commit, reads as it did. No code, workflow or test
  of a source changes.
