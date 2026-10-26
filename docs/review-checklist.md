# Review checklist

The checklist a reviewer applies to a PR in any `sdk-*` repository, read from `sdk-core`
`main` by the local `reviewer` subagent and by the `family-review` workflow alike. A
review changes nothing in the repository it reviews.

## Before judging

- Read the diff (`git diff origin/main...HEAD`) and the history
  (`git log --oneline origin/main..HEAD`), and the PR description.
- Read the family documents from `sdk-core` `main`: `docs/conventions.md`, the ADRs
  under `docs/adr/`, `docs/definition-of-done.md`. Read the repository's `CLAUDE.md`,
  and its `docs/upstream/` for every claim about the upstream API.
- Never read or print `.envrc`, `.env` or a variable ending in `_API_KEY`; a leak check
  greps the files for key patterns, it never compares against a key.

## Check, in this order

1. **Layering** (ADR-0001): the adapters register `tasks.__all__`, minus `BULK_TASKS`
   (ADR-0019), and hold no logic.
2. **Fidelity** (ADR-0003): upstream names and semantics, no cross-source
   normalisation; every parameter and default traceable to `docs/upstream/` or listed as
   an assumption in the description.
3. **Errors**: mapped through the taxonomy (conventions §5) and the `classify` hook
   (§6).
4. **Fixtures**: recorded, never hand-written; scrubbed; free of key patterns and of
   production tenant names; no file under `tests/fixtures/` over 256 KiB, a truncated
   one marked `truncated: true` (ADR-0019).
5. **Checks green**: `uv run ruff check . && uv run ruff format --check . && uv run mypy
   && uv run pytest && uv run pre-commit run --all-files`, run by the reviewer where it
   has a shell, else read from the PR's `ci` check.
6. **Definition of done**: the checklist is in the description and ticked honestly; an
   unticked item carries a one-line reason.
7. **CHANGELOG**: an entry under Unreleased.
8. **Nothing forbidden**: nothing committed to `main`, no secrets, no tag.
9. **Decisions taken**: the description carries a `## Decisions taken` block after the
   checklist, and every line names the convention or ADR it rests on, or `gap, row N`.
   A line backed by neither is a blocking finding.
10. **Live calls**: the description counts the live calls the PR spent, keyed calls by
    number (`none` is a count).
11. **Core PR** (`sdk-core`, code added): its ADR names the two consumers of what it
    adds, or states the one-consumer reason under ADR-0023 decision 3.
12. **Adoption PR** (`chore/template-update*`): judged against conventions §15 and
    nothing else, that is the definition of done's Adoption PR block with its Enforced by
    CI and Process blocks; it deletes only what the adoption itself makes dead.
13. **Release PR** (`chore/release-*`, the version in `pyproject.toml` changed): it
    changes only the subset of conventions §12 (`pyproject.toml`, `uv.lock`,
    `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `docs/handover.md`, and
    `scripts/check-siblings.sh` until the siblings check is template-owned); the
    reference-data refresh was its own PR.
14. **Stale sentences**: no sentence in a changed `README.md`, `CLAUDE.md`, docstring or
    document contradicts the state after the change (a version, a count, a file name, a
    rule the PR replaced).

## Report

- **Verdict**: `ready` or `not ready`. Any blocking finding makes it `not ready`.
- **Blocking findings**, each with file and line.
- **Non-blocking findings**, each with file and line where there is one.
- **Concerns for `sdk-core` or `sdk-template`** rather than for this repository.
