# ADR-0018: Core versioning and source adoption

Status: Accepted · Date: 2026-10-25

## Context

Every source declares `xippios-core>=0.1.0`, and its extras the same, with no upper
bound. Core 0.2.0 breaks source code and source test suites: the plugin owns the offline
guarantees (ADR-0013), a write server is checked at registration (ADR-0014), `classify`
shapes retries (ADR-0015), and `EnvKeyAuth.apply` takes no key. A source resolved after
0.2.0 is published would install a core it was never tested against.

Adoption has so far been by hand, per source and per change. sdk-template 0.1.5's
placeholder-key fixture reached no existing source through `copier update` and was
patched into four sources one by one (ADR-0013); sdk-usda-nass's update to template
0.1.5 ported its test files by hand; sdk-cashctrl adopted `Tenants`, `TenantLock`,
`Scrub` and the plugin's guarantees on a git pin of core's `main` (sdk-cashctrl#7,
2026-10-24), before any release carried them. No list said what an adoption has to do,
so a reviewer could not tell a finished adoption from a partial one, and new work could
ride along with it.

The definition of done lists `pre-commit run --all-files` under "Enforced by CI", but no
workflow ran it (found in the review of sdk-cashctrl's scaffold).

Johannes decided on 2026-10-23 that a source depends on one core minor, and on
2026-10-25 that adoption PRs merge automatically after the reviewer's `ready`.

## Decision

1. **One core minor per source.** A source depends on `xippios-core~=X.Y.0`, its extras
   likewise (`xippios-core[mcp]~=0.2.0`). Core patch releases stay compatible. While core
   is 0.x it keeps no backward compatibility across minors: a new minor may break, and a
   source adopts it before its next release. From 1.0 a breaking change bumps the major
   (SemVer), and the `~=` bound stays. A source already published with an open bound
   stays as published and gets the bound with its next release (conventions §11, §12).
2. **One adoption PR, against one checklist.** Conventions §15 lists what an adoption PR
   does: raise the core floor, `copier update`, delete the workarounds a core change
   replaced, move logic duplicated across sources into core or drop it, mark or override
   the tests that asserted a limiter wait, a quota pause or key resolution, re-render the
   generated enum files once, run `mypy --strict` over `scripts/`, apply the current
   conventions version, and add a CHANGELOG line. The definition of done's "Adoption PR"
   block mirrors it; the reviewer judges an adoption PR against that list and nothing
   else, and no new endpoints, tasks or fixtures ride along.
3. **Adoption PRs auto-merge.** An adoption PR is a `chore/template-update*` PR: after
   the reviewer's `ready` the session enables auto-merge, and GitHub merges it once `ci`
   is green and review threads are resolved. A release PR (`chore/release-*`, core's or
   a source's) auto-merges the same way after the reviewer's `ready`, once `ci` is green
   and review threads are resolved; the tag stays Johannes's.
4. **The template walks the list.** sdk-template's `/adopt-release` command takes a
   source through §15 step by step.
5. **CI runs pre-commit.** Core's `ci.yml` runs `uv run pre-commit run --all-files` after
   the tests, its hook environments cached, so the definition of done's CI block holds;
   the template's CI does the same.

## Consequences

- Sources bounded to different core minors cannot be installed together in one
  environment. Adoption is therefore coordinated per core minor: every source adopts a
  new minor before its next release, and a consumer that installs several sources waits
  until they share one.
- The template renders the bound as `~=X.Y.0` from its core version answer.
- Auto-merge waits for every required approving review, so the org ruleset must require
  none for these PRs to merge on `ci` alone.
- A breaking core change reaches a source only through an adoption PR, so the release's
  ADRs and CHANGELOG name, per source, what the adoption deletes.
- Conventions 1.13: §11 and §12 state the bound and the 0.x rule, §15 the checklist; the
  definition of done gains the "Adoption PR" block.

## Amendment 2026-10-26

(a) Decision 3 applies to sdk-template's release PRs as well as to core's and a source's: a
`chore/release-*` PR of the template auto-merges the same way after the reviewer's
`ready`, once `ci` is green and review threads are resolved, as sdk-template#12
(`chore/release-0.2.0`) did on Johannes's instruction of 2026-10-25. The decision named
core's and a source's release PRs only; raised by sdk-template on 2026-10-25.

(b) The last clause of decision 3, which left the tag to Johannes, is superseded by the
release train of conventions §12 (1.14). The release PR's merge on `main` runs
`publish.yml`, which tags `vX.Y.Z` from `pyproject.toml` on the merge commit; the human
gate is the approval of the `pypi` environment run, and a tag ruleset admits no other
`v*` tag. sdk-template, which publishes nothing to PyPI, tags from the top
`## [X.Y.Z] - ` heading of its `CHANGELOG.md` with its own `release.yml`; the tag
ruleset's "no other `v*` tag" covers it the same way. Until a repository's workflow tags
itself (core 0.2.1, template v0.2.1, then each source through its adoption of v0.2.1),
its tag is pushed by Johannes from his own account. Johannes decided the release train
on 2026-10-26; conventions §12 states it from 1.14 on.

(c) Decision 1's bound, and the consequence that the template renders it as `~=X.Y.0`,
admit `~=X.Y.Z` when patch Z shipped what the source adopts, still one minor, as the
help of `core_version` in sdk-template's `copier.yml` says. Core 0.2.1 is the first
case: its family check is what the template-rendered `tests/test_family.py` imports, and
0.2.0 lacks it, so a source adopting it is bound `~=0.2.1`. Conventions §12 states it
from 1.14 on.

(d) Decision 2's "no new endpoints, tasks or fixtures ride along" admits deletions: an
adoption PR may delete the fixtures, mounts and tests that the adoption itself makes
dead, and nothing else rides along (queue row 36 g). Conventions §15 and the definition
of done's Adoption PR block state it from 1.14 on.

(e) Decision 3's auto-merge, of an adoption PR and of a release PR after the reviewer's
`ready`, applies only to a pull request whose merge class is `auto`. A `human` adoption
or release (a source-owned workflow, a changed template answer, a protected path, a
build or install route) waits for Johannes. The classes are defined in the README of the
`xippios/.github` repository, whose `merge-class` check computes them for every pull
request. This rests on Johannes's merge-class decision of 2026-10-26: a pull request
merges automatically after CI, the merge-class check and the review, unless its class is
`human`. Conventions §15, the definition of done's Adoption PR intro and its Process
line (and the Process line's copy in the PR template) state it from 1.15 on, citing
"ADR-0018, amendment (e)".

Note 2026-10-28 (queue row 55): the gates repository (e) names has been
`xippios/sdk-gates` since 2026-10-27, when `xippios/.github` was renamed; its README
defines the merge classes and its `merge-class` check computes them. (e) stands as
written on its date; conventions §15, the definition of done's Adoption PR intro and its
copy in the PR template name `xippios/sdk-gates` from 1.22 on.

## Amendment 2026-10-27

(f) The release train's workflows, and every workflow of the family, follow the hardening
that conventions §13 states from 1.20 on (queue row 51, the family's; decided by Johannes
on 2026-10-27): every action pinned to a commit SHA with its version in a comment;
`persist-credentials: false` on every checkout except in a job that pushes with the token,
the `tag` job of `publish.yml`, which says so in a comment; `permissions: contents: read`
at the top of every workflow and, per job, only what the job needs; no `secrets: inherit`,
a secret passed by name to the one job that uses it. The family's reusable workflows in
`xippios/sdk-gates` are called at `@main` by design, since the gates read their own `main`
(Johannes's caller-mode decision of 2026-10-26): the one reference to another
repository that is not pinned. Core's
`ci.yml`, `publish.yml` and `gates.yml` met it except for the `tag` job's comment, which
the change that brought this amendment added.

## Amendment 2026-10-29

Two rules the source briefings kept asking, decided by Johannes on 2026-10-29 in the
interview for conventions 1.23 (D110 (1) and (2)), and the adoption routes the queue
found, with Johannes's D35 and D85 for the frozen source.

(g) **The version rule** (D110 (1); queue row 233). Conventions §12's "Pre-1.0: breaking
changes bump minor", on which decision 1 builds, reads: pre-1.0 only a breaking change
bumps the minor, as `/release-prep` step 4 reads ("pre-1.0, a breaking change bumps the
minor"). Added tasks or parameters make a patch, which reaches every dependent inside
its `~=X.Y.0` bound, so the adoption release of ADR-0021's amendment of 2026-10-29
follows a breaking minor only. The sdk-usda-gats 0.3.0 briefing had read added surface
as a minor; the sdk-usda-esmis 0.3.0 and sdk-usda-psd 0.4.0 briefings recommended the
patch.

(h) **The refresh rule** (D110 (2); queue rows 109 and 110). The reference-data refresh
of the release train (amendment (b), conventions §12) runs before the release and gets a
PR of its own only when a record changed or `fetched` goes from a bare date to the full
time (ADR-0022, amendment 2026-10-27, point 1); otherwise the run is a coordination log
line the release PR cites. "Unchanged" means the records, not the files: a run whose
records are unchanged still moves every `fetched` to the run's time, which changes the
files and `meta.retrieved_at`, and gets no PR for it. It is Johannes's ruling for
sdk-usda-esmis 0.1.0 of 2026-10-27, with sdk-usda-psd's exception of 2026-10-28, the
bare date that becomes the full time. The coordination rules' rule 9 is reworded in
rules v5, and the template's `/release-prep` follows (queue row 110).

(i) **Conventions §15's three routes** (queue rows 232, 273 and 118), beside the
adoption its list describes, a core minor with its template release through `copier
update`. (1) A core release without a template tag (row 232): the bound is raised with
`copier update --vcs-ref=:current: -d core_version=X.Y.Z` on
`chore/template-update-core-X.Y.Z`, §15 item 2 does not apply, and a core minor without
its template release is no adoption until the template follows; the `/adopt-release`
mode for it is the template's. (2) A dependency's minor whose new surface the dependent
uses (row 273): the adoption PR stays pure and the use is the next PR (ADR-0021,
amendment 2026-10-29, point 3). (3) A source frozen on a template tag (row 118;
sdk-cashctrl, on template v0.2.2 since its core 0.3.0 adoption, D35 and D85): no `copier
update`; the template-rendered files are the source's own and listed in its `CLAUDE.md`;
the template changes the new conventions version needs are hand-applied and listed file
by file in the PR description, as https://github.com/xippios/sdk-cashctrl/pull/18 did.

Conventions §12 states (g) and (h) from 1.23 on, §15 (i); the review checklist's items
12 and 13, the definition of done's `copier update` line and its last Process line, and
their copies in the PR template, state (h) and (i).
