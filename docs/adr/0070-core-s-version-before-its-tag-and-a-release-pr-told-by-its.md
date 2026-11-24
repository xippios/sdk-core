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

The answer on https://github.com/xippios/sdk-core/issues/561 had a pull request before the
candidate raise the version, https://github.com/xippios/sdk-core/pull/564, and the answer on
https://github.com/xippios/sdk-core/issues/566 gave that pull request its changelog fragment, as
§12 asks of every pull request but a release's and Dependabot's. The organization's conventions
check then found item 13 and ADR-0039, decision 2, stale for core: the pull request that raised
the version is no release PR, and the release PR raises none (finding 2 of
https://github.com/xippios/sdk-core/pull/572#issuecomment-7142719021). The organization's
workflow of that check already tells a release PR by its `release` label or by a title that ends
in ` Release`
(https://github.com/xippios/.github/blob/main/.github/workflows/conventions.yml).

ADR-0039 holds two amendments already, both of 2026-11-24, so the change of its decision 2 is a
record of its own, to which ADR-0039 points, as it points to ADR-0069.

## Decision

1. **Core's `main` carries the coming version before its tag.** A pull request before the
   candidate raises `version` in core's `pyproject.toml` to the coming release, with its
   `uv.lock`, and changes nothing under `src/`, so a package pinned to a commit of `main`
   installs within the coming minor's bound, `~=X.Y.0`. It tags nothing, since `CHANGELOG.md`
   holds no heading of that version yet, and it brings its changelog fragment, as every pull
   request but a release's and Dependabot's does
   (https://github.com/xippios/sdk-core/issues/566).
2. **Core's release PR raises no version, and its merge tags.** Core's release PR raises no
   version: it leaves `version` in `pyproject.toml` as decision 1 set it and still changes only
   the files of conventions §12, writing the release's `## [X.Y.Z] - ` heading into
   `CHANGELOG.md` from the fragments, and its merge tags `vX.Y.Z`, since `publish.yml` tags only
   once that heading stands beside a version that has no tag.
3. **A release PR is told by its title.** A release PR is told by its title, `X.Y.Z Release`, or
   by the `release` label, as the organization's workflow of its conventions check tells it
   (https://github.com/xippios/.github/blob/main/.github/workflows/conventions.yml), and no
   longer by its version, which core's release PR leaves as decision 1 set it. This changes
   ADR-0039, decision 2, in part, where it tells a release PR by its version; the rest of
   decision 2 stands as written.

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
