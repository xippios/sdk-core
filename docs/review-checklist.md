# Review checklist

The checklist a reviewer applies to a PR in any `sdk-*` repository. A review changes
nothing in the repository it reviews.

## Before judging

- Read the diff (`git diff origin/main...HEAD`) and the history
  (`git log --oneline origin/main..HEAD`), and the PR description.
- Read the family documents: `docs/conventions.md`, the ADRs under `docs/adr/`,
  `docs/definition-of-done.md` and this checklist. `sdk-core` `main`'s apply to every PR;
  a PR that changes one of them is judged against its branch's own version of it. Read
  the repository's `CLAUDE.md`, and its `docs/upstream/` for every claim about the
  upstream API.
- Never read or print `.envrc`, `.env` or a variable ending in `_API_KEY`,
  `_REFRESH_TOKEN` or `_SECRET`; a leak check greps the files for key patterns, it never
  compares against a key.

## Check, in this order

1. **Layering** (ADR-0001): the adapters register `tasks.__all__`, minus `BULK_TASKS`
   (ADR-0019), and hold no logic.
2. **Fidelity** (ADR-0003): upstream names and semantics, no cross-source
   normalisation; every parameter and default traceable to `docs/upstream/` or listed as
   an assumption in the description.
3. **Errors**: mapped through the taxonomy (conventions §5) and the `classify` hook
   (§6).
4. **Fixtures**: recorded, never hand-written; scrubbed; free of key patterns and of
   production tenant names; the fixture files this PR adds or changes under 256 KiB, a
   file it only moves, its content unchanged, being neither, and a truncated one marked
   `truncated: true` (ADR-0019; binds from the source's 0.3.0 adoption).
5. **Checks green**: the PR's `ci` check passes; a reviewer who runs the checks runs
   `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
   && uv run pre-commit run --all-files`.
6. **Definition of done**: the change meets each item of `docs/definition-of-done.md`
   that applies to it.
7. **CHANGELOG**: the change's entry is a fragment under `changelog/`, in the form
   `changelog/README.md` gives; a release PR assembles the fragments instead, and
   Dependabot's carries none (conventions §12).
8. **Nothing forbidden**: nothing committed to `main`, no secrets, no tag pushed by hand;
   the tag a merged release PR gets from its workflow, from 0.2.1 on, is legitimate
   (conventions §12).
9. **Decisions taken**: the description carries a `## Decisions taken` block, and every
   line is backed by a convention, an ADR, a maintainer's decision with its date, or the
   issue that records the gap. A line backed by none of these is a blocking finding.
10. **Live calls**: the description counts the live calls the PR spent, keyed calls by
    number (`none` is a count).
11. **Core PR** (`sdk-core`, code added): it names the two consumers of what it adds (in
    its ADR, or in its description when it has none), or, in its ADR, the one-consumer
    reason of ADR-0023 decision 3.
12. **Adoption PR** (conventions §15): judged against conventions §15 and nothing else,
    that is the definition of done's Adoption PR block with its Enforced by CI and
    Process blocks; it deletes only what the adoption itself makes dead (ADR-0018,
    amendment 2026-10-26). On §15's routes (1) and (3), a core release without a
    template tag and a source frozen on a template tag, §15's item 2 does not apply: the
    first raises the bound with `copier update --vcs-ref=:current:`, the second runs no
    `copier update` and lists the template changes it hand-applies file by file
    (ADR-0018, amendment (i)).
13. **Release PR** (the version in `pyproject.toml` changed, or for sdk-template the top
    heading of `CHANGELOG.md`): it changes only the files of conventions §12
    (`pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`,
    `docs/handover.md`, and the fragments under `changelog/`, which it deletes); the
    reference-data refresh ran before it, in a PR of its own only when a record changed
    or `fetched` went from a bare date to the full time, otherwise cited by the release
    PR (conventions §12; ADR-0018, amendment (h)).
14. **Stale sentences**: no sentence in a changed `README.md`, `CLAUDE.md`, docstring or
    document contradicts the state after the change (a version, a count, a file name, a
    rule the PR replaced).
15. **Conventions** (`sdk-core`): a change to `docs/conventions.md` carries an ADR or an
    ADR amendment, and the conventions version bumps once per PR.
16. **Wrapper and fixture names** (conventions §2, §10): a new endpoint wrapper's module
    and function carry the upstream operation name by §2's rule, and its fixtures live
    under `tests/fixtures/<wrapper>/`; the verbatim operation id is in the first line of
    the wrapper function's docstring and in the `endpoint=` it passes.

## Report

- **Verdict**: `ready` or `not ready`. Any blocking finding makes it `not ready`.
- **Blocking findings**, each with file and line.
- **Non-blocking findings**, each with file and line where there is one.
- **Concerns for `sdk-core` or `sdk-template`** rather than for this repository.
