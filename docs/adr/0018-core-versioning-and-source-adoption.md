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
