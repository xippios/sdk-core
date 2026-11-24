# Review checklist

The checklist a reviewer applies to a PR in any `sdk-*` repository, and in the host
`xippios-mcp`, a package that is no source (ADR-0026, decision 1). Items 1 to 4 and 16
are written for a source's adapters, upstream names, error shapes, fixtures and wrappers,
and do not apply to the host; item 12 judges its adoption PR against conventions §15's
items for the host (ADR-0026, amendment 2026-11-18, point e). A review changes nothing in
the repository it reviews.

## Before judging

- Read the diff (`git diff origin/main...HEAD`) and the history
  (`git log --oneline origin/main..HEAD`), and the PR description.
- Read the family documents: `docs/conventions.md`, the ADRs under `docs/adr/`,
  `docs/definition-of-done.md` and this checklist. `sdk-core` `main`'s apply to every PR;
  a PR that changes one of them is judged against its branch's own version of it. Read
  the repository's `CLAUDE.md`, and its `docs/upstream/` for every claim about the
  upstream API.
- Never read or print `.envrc`, `.env` or a variable that holds a credential, any whose
  name ends in `_API_KEY`, `_TOKEN` or `_SECRET` among them; a leak check greps the files
  for key patterns, it never compares against a key (conventions §7; ADR-0030,
  decision 6).

## Check, in this order

1. **Layering** (ADR-0001; not the host's): the adapters register `tasks.__all__`, minus
   `BULK_TASKS` (ADR-0040), and hold no logic.
2. **Fidelity** (ADR-0028, ADR-0060, ADR-0061; not the host's): upstream names and semantics,
   no cross-source normalisation; every parameter and default traceable to `docs/upstream/`, its
   hand-written `OBSERVED.md` included (conventions §3), or listed as an assumption in the
   description. A source's `scripts/refresh_upstream.py` on core's frame names its `Snapshot`
   `SNAPSHOT` at its top level, which loads with no request and no write, its run under
   `if __name__ == "__main__":`, since no check of core reads the script and the review alone
   holds its form (conventions §3; ADR-0062, decision 3). A change stays inside the boundary of
   conventions §14, each of its six sentences as the section of its subject applies it, and a
   record that a package shapes itself follows §3's four rules, of which the family check holds
   the form of a reading alone, so the review judges whether a reading that can lose something
   keeps its text beside it (ADR-0060). Each way of ADR-0061 holds as its section states it, the
   order of a source's arguments and the bound of its requests among the ways that no test holds
   (ADR-0061).
3. **Errors** (not the host's): mapped through the taxonomy (conventions §5) and the
   `classify` hook (§6); each shape `classify` maps is documented in `docs/upstream/` or
   recorded in a fixture that a test passes to it (ADR-0031, decision 2); a message names
   its request as §5 says, a refusal the package makes of the call as given and a decoder's
   subject naming none (ADR-0030, decision 4; ADR-0043).
4. **Fixtures** (conventions §10; not the host's): recorded, never hand-written; scrubbed;
   free of key patterns and of production tenant names; the fixture files this PR adds or
   changes under 256 KiB, a file it only moves, its content unchanged, being neither, and
   a truncated one marked `truncated: true` (ADR-0040; binds from the source's 0.3.0
   adoption); a download fixture whose body is its parser tests' sample marked
   `sample: true` with the whole file's size and sha256 (ADR-0020, amendment 2026-11-18,
   point a; binds from the source's adoption of core 0.4.0); a sample a script wrote from
   a file over the cap in the file's own form, its row saying what it keeps (ADR-0020,
   amendment 2026-11-18, point d); a body a test serves where it was not recorded one of
   §10's kinds, saying where it comes from, and its test asserting what the source does
   with it (ADR-0028, decision 8), the three cases that §10 settles between the kinds
   judged as it settles them: a recording changed in its status, content type and body at
   once of the second kind, a value that no route serves and no `classify` reads an input of
   the test with no kind, and a recording replayed at its own path for other parameters of
   the third, naming its condition (ADR-0043); each such body marked as §10 states the mark,
   within its reach, an input by its sentence and a replay for another request as the third
   kind, which `xippios.core.testing.built_answers` holds in a source that collects it, while
   whether a value marked as an input is served, and so takes a kind, is the review's
   (ADR-0064); a recorded fixture that no test
   replays after the change, and no test or document cites, deleted and named in the
   description (ADR-0039, decision 8).
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
10. **Live calls**: the description counts the live calls the PR spent, every request it
    sent to an upstream, a probe's, a recording's or a live test run's, the keyed ones by
    number (`none` is a count), since a keyed call spends the quota that every source and
    process holding its key draws on (ADR-0032, decision 7).
11. **Core PR** (`sdk-core`, code added): it names the two consumers of each piece it adds
    that a caller can name (in its ADR, or in its description when it has none), or, in its
    ADR, the part of the family's contract that a piece with one consumer serves (ADR-0059,
    decisions 1, 2 and 4).
12. **Adoption PR** (conventions §15): judged against conventions §15 and nothing else,
    that is the definition of done's Adoption PR block with its Enforced by CI and
    Process blocks; it deletes only what the adoption itself makes dead (ADR-0039,
    decision 2). On §15's routes (1) and (3), a core release without a
    template tag and a source frozen on a template tag, §15's item 2 does not apply: the
    first raises the bound with `copier update --vcs-ref=:current:`, the second runs no
    `copier update` and lists the template changes it hand-applies file by file
    (ADR-0039, decision 2). The host's adoption PR runs no `copier update` and is
    judged against §15's items 1, 3, 4, 7, 8 and 9, read for the host as §15 reads them,
    and lists the template changes it hand-applies file by file (ADR-0026, amendment
    2026-11-18, point e). A source's adoption fragment names the core bound, the template's
    tag and the conventions' version as they stand after the adoption, changed or not, and
    is `breaking` where it brings a core minor and `changed` where it brings none
    (conventions §15, item 9; ADR-0043). An adoption of a core release is held against the
    two lists of the handover's section `Adopting core X.Y.Z` for that release: each of the
    conventions' rules changed since the version before holds in the source, as §15 item 8
    asks, and each of the changes that a source's callers see that the adoption brings to
    them has its entry among the adoption's fragments
    (https://github.com/xippios/sdk-core/issues/334,
    https://github.com/xippios/sdk-core/issues/349).
13. **Release PR** (the version in `pyproject.toml` changed, or for sdk-template the top
    heading of `CHANGELOG.md`): it changes only the files of conventions §12
    (`pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `CLAUDE.md`,
    `docs/handover.md`, and the fragments under `changelog/`, which it deletes); the
    reference-data refresh ran before it, in a PR of its own only when a record changed
    or `fetched` went from a bare date to the full time, otherwise cited by the release
    PR (conventions §12; ADR-0039, decision 6). It assembles each entry as its fragment
    reads, under its fragment's group, rewording none, and a source's release PR cites a
    green run of `live.yml` on the commit of `main` that it starts from, never a run on an
    earlier commit (conventions §12; ADR-0043).
14. **Stale sentences**: no sentence in a changed `README.md`, `CLAUDE.md`, docstring or
    document contradicts the state after the change (a version, a count, a file name, a
    rule the PR replaced).
15. **Conventions** (`sdk-core`): a change to `docs/conventions.md` carries an ADR or an
    ADR amendment. The conventions version is raised once per core release, by the
    release's last change to the conventions; a change before it leaves the version line
    as it stands.
16. **Wrapper and fixture names** (conventions §2, §10; not the host's): a new endpoint
    wrapper's module and function carry the upstream operation name by §2's rule, and its
    fixtures live under `tests/fixtures/<wrapper>/`, under `<service>_<wrapper>/` where
    two wrappers carry its name, or under the tasks that record its every exchange, where
    none is its own (ADR-0028, decision 3); the verbatim operation id
    is in the first line of the wrapper function's docstring and in the `endpoint=` it
    passes.
17. **One tenant per call** (`sdk-core`, and a multi-tenant source): no task, tool or helper
    in core works across tenants; each task of the source takes exactly one tenant,
    required, the tenant list returns names only, and nothing is shared between tenants, no
    client, rate limiter or cache (conventions §7; ADR-0036, decisions 3, 11 and 13).
    `bind_tasks` and the family check
    read signatures, so the review judges what a task reaches inside, a task that takes one
    tenant and opens another's client say (https://github.com/xippios/sdk-core/issues/302).
18. **Write tools** (a source with a write server, from its patch on core 0.4.1): each write
    task's docstring says whether its preview reads first and what the read costs, its
    preview sends no write and carries `reads`, the operations it read, `[]` for none, and the
    source's tests hold it with `assert_write_tools(..., preview_reads=True)`, the dry run of
    each tool (`dry_run=`) at the source's choice (conventions §8; ADR-0050). The check
    compares `reads` with the requests sent and reads no docstring, so what a docstring says
    of the read and its cost is the review's to judge.

## Report

- **Verdict**: `ready` or `not ready`. Any blocking finding makes it `not ready`.
- **Blocking findings**, each with file and line.
- **Non-blocking findings**, each with file and line where there is one.
- **Concerns for `sdk-core` or `sdk-template`** rather than for this repository.
