# ADR-0039: Core versioning and source adoption

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0018 ·
Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/484 ·
Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/494 ·
Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/484

## Context

Sources declared `xippios-core>=0.1.0` with no upper bound while core 0.2.0 broke source code
and test suites, adoption went by hand per source and per change with no list of what it must
do, and no workflow ran the definition of done's pre-commit. Johannes decided on 2026-10-23
that a source depends on one core minor. This record states ADR-0018 with its amendments of
2026-10-26, (a) to (e) and the note of 2026-10-28, 2026-10-27, (f), 2026-10-29, (g) to (i),
2026-11-13, (j) to (p), and 2026-11-18, (q) to (t), as they stand, and changes no decision;
their history stays in ADR-0018.

## Decision

1. **One core minor per source.** A source depends on `xippios-core~=X.Y.0`, its extras
   likewise (`xippios-core[mcp]~=0.2.0`), or on `~=X.Y.Z` when patch Z shipped what the
   source adopts, still one minor. Core patch releases stay compatible. While core is 0.x it
   keeps no backward compatibility across minors: a new minor may break, and a source adopts
   it before its next release. From 1.0 a breaking change bumps the major (SemVer), and the
   `~=` bound stays. A source already published with an open bound stays as published and
   gets the bound with its next release (conventions §11, §12).
   - Pre-1.0 only a breaking change bumps the minor; added tasks or parameters make a patch,
     which reaches every dependent inside its `~=X.Y.0` bound, so the adoption release of
     ADR-0021's amendment of 2026-10-29 follows a breaking minor only. Johannes decided it
     on 2026-10-29 (D110 (1)).
   - "A minor" (https://github.com/xippios/sdk-core/issues/243): a source's adoption of a core
     minor takes a minor, whatever else its release brings: the adoption moves the source's
     core bound to the new minor, so its release no longer installs beside a package still
     bound to the old one, and the adoption is therefore a breaking change of the source; an
     added surface alone still makes a patch. The host
     keeps its minors (ADR-0026, amendment 2026-10-30, point e).
2. **One adoption PR, against one checklist.** Conventions §15 lists what an adoption PR
   does: raise the core floor, `copier update`, delete the workarounds a core change
   replaced, move logic duplicated across sources into core or drop it, mark or override the
   tests that asserted a limiter wait, a quota pause or key resolution, re-render the
   generated enum files once, run `mypy --strict` over `scripts/`, apply the current
   conventions version, and add its changelog entry. The definition of done's Adoption PR
   block mirrors the list. An adoption PR is judged against that block with the Enforced by
   CI and Process blocks and nothing else, and no new endpoints, tasks or fixtures ride
   along; it may delete the fixtures, mounts and tests
   that the adoption itself makes dead, and nothing else. The definition of done is what a
   change satisfies, not a list its pull request's description copies and ticks; a release
   PR, which changes no code, test or fixture, has nothing for its Code and Tests blocks to
   judge. No document names a branch a change must carry: a release PR is told by its
   version, an adoption PR by what §15 lists. Beside the adoption that §15's list describes,
   a core minor with its template release through `copier update`, three routes:
   1. A core release without a template tag: the bound is raised with `copier update
      --vcs-ref=:current: -d core_version=X.Y.Z`, §15 item 2 does not apply, and a core minor
      without its template release is no adoption until the template follows.
   2. A dependency's minor whose new surface the dependent uses: the adoption PR stays pure
      and the use is the next PR (ADR-0021, amendment 2026-10-29, point 3).
   3. A source frozen on a template tag (sdk-cashctrl, Johannes's D35 and D85): no `copier
      update`; the template-rendered files are the source's own and listed in its
      `CLAUDE.md`; the template changes the new conventions version needs are hand-applied
      and listed file by file in the PR description.
3. **The merge is not the family's rule.** Who merges an adoption PR or a release PR, and
   when, is the process of the work: ADR-0018's decision 3 and its amendments (a) and (e),
   which had them auto-merge after the reviewer's `ready`, stand as written on their dates
   and bind no repository from conventions 1.26 on.
4. **The template keeps its adoption command.** sdk-template's `/adopt-release`, which takes a
   source through §15 step by step, is the template's to keep; conventions §15 names it no
   longer.
5. **CI runs pre-commit.** Core's `ci.yml` runs `uv run pre-commit run --all-files` after the
   tests, its hook environments cached, so the definition of done's CI block holds; the
   template's CI does the same.
6. **The release train.** The release PR's merge on `main` runs `publish.yml`, which tags
   `vX.Y.Z` from `pyproject.toml` on the merge commit; the human gate is the approval of the
   `pypi` environment run, and a tag ruleset admits no other `v*` tag. sdk-template, which
   publishes nothing to PyPI, tags from the top `## [X.Y.Z] - ` heading of its
   `CHANGELOG.md` with its own `release.yml`. Every repository's workflow tags its own
   release, and a `v*` tag comes from the release train alone. Johannes decided the release
   train on 2026-10-26.
   - Every pull request but a release's and Dependabot's brings its changelog entry as a
     fragment, a file of its own under `changelog/`, which the release PR assembles into its
     section of `CHANGELOG.md` and deletes, as `changelog/README.md` says; the files a
     release PR may change include the fragments. A repository that keeps no `changelog/`
     yet writes its entry under `## [Unreleased]`.
   - `publish.yml` writes a release's section of `CHANGELOG.md` into the message of the tag
     it pushes, which a reader of the release sees without the issues and plans behind it,
     so the section says an internal label, such as a decision's number or a plan's item, in
     plain words. A dependent that bundles its adoption with feature work says so in that
     section.
   - The reference-data refresh runs before the release and gets a PR of its own only when a
     record changed or `fetched` goes from a bare date to the full time (ADR-0041, decision
     4); otherwise the release PR cites the run, and where the run is recorded is not the
     family's rule. "Unchanged" means the records, not the files: a run whose records are
     unchanged still moves every `fetched` to the run's time, which changes the files and
     `meta.retrieved_at`, and gets no PR for it. Johannes decided it on 2026-10-29 (D110
     (2)).
7. **Workflow hardening.** Every workflow of the family follows conventions §13: every
   action pinned to a commit SHA with its version in a comment; `persist-credentials: false`
   on every checkout except in a job that pushes with the token, the `tag` job of
   `publish.yml`, which says so in a comment; `permissions: contents: read` at the top of
   every workflow and, per job, only what the job needs; no `secrets: inherit`, a secret
   passed by name to the one job that uses it. The reusable workflows of `xippios/.github`,
   the organization's repository, are called at `@main` by design, since they read their
   own `main`: the one reference to another repository that is not pinned. Johannes decided
   the hardening on 2026-10-27, and the caller mode on 2026-10-26.
8. **A pull request deletes the fixture it makes dead.** A pull request deletes a recorded
   fixture that no test replays after its change and names it in its description, so no
   fixture outlives every test that read it; a fixture that a test or a document still cites
   stays, as a fixture that a source's `CLAUDE.md` or a docstring names as the evidence of an
   upstream answer does. An adoption PR keeps the limit of decision 2: it deletes what the
   adoption makes dead and nothing else.
9. **A convention that seems wrong is followed.** A change that meets a convention that seems
   wrong to it follows the convention and says so in its pull request, until the
   convention's ADR and its change of the conventions land, since a change of the
   conventions comes with an ADR, as their header requires, and a source applies the version
   it adopted (decision 2, conventions §15 item 8).

## Consequences

- Sources bounded to different core minors cannot be installed together in one environment.
  Adoption is therefore coordinated per core minor: every source adopts a new minor before
  its next release, and a consumer that installs several sources waits until they share one.
- The template renders the bound from its core version answer, as `~=X.Y.0`, or `~=X.Y.Z` as
  decision 1 admits.
- A breaking core change reaches a source only through an adoption PR, so the release's ADRs
  and CHANGELOG name, per source, what the adoption deletes.

The conventions' header, §10, §12, §13 and §15, the review checklist's items 4, 12 and 13,
the definition of done's Tests and Adoption PR blocks, the README, the family check's
docstrings, core's pull request template and `publish.yml` state its decisions from 1.28 on.

## Amendment 2026-11-24

Amended by ADR-0068 (https://github.com/xippios/sdk-core/issues/484): decision 2's third route,
a source frozen on a template tag, leaves conventions §15, since no source stands on a frozen
tag and the conventions keep no history, and the adoption's items stand once, in §15, where the
definition of done's Adoption PR block and the review checklist point without mirroring the
list, while the rest of decision 2 stands as written.

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/494: in decision 7 the
checkout of the `tag` job of `publish.yml`, which keeps its credentials to push the tag with
the token, carries no comment that says so, since a workflow carries no comment but the
version after a pinned action (https://github.com/xippios/.github/issues/111), and the
README's paragraph on `publish.yml` names the exception in its place, while the rest of
decision 7, the other decisions and the amendment above stand as written.

ADR-0069 (https://github.com/xippios/sdk-core/issues/484), decision 3, adds to decision 3 the one
constraint that the missing `concurrency` group of `publish.yml` imposes on when a release PR
merges: a release PR is not merged while another release run waits at `pypi`. The rest of
decision 3, the other decisions and the amendments above stand as written.
