# Changelog fragments

Every change to xippios-core brings its changelog entry as a file of its own in this folder, a
fragment, so that two pull requests never edit the same lines of `CHANGELOG.md`. The release
assembles the fragments into its section of `CHANGELOG.md` and deletes them. This README stays.

## A fragment

- **Its name.** `changelog/<group>-<slug>.md`, one file per change. `<group>` is one of
  `added`, `changed`, `fixed`, `removed`, `security` and `breaking`, and `<slug>` names the
  change in lowercase letters and digits, its words joined by hyphens. A change to the
  documents takes its group by what it does, as a change to the code does: a new ADR is
  `added`, a rule the conventions change is `changed`.
- **Its bullet.** The file holds one bullet, as it will stand in the release's section: its
  first line starts with `- `, and a line it continues is indented by two spaces. The lead
  sentence says what changes for a source package or another user of core, or for this
  repository, and up to two more say how it is used or what it replaces. Its citations close
  it in parentheses: an `ADR-NNNN` it follows, a section of the conventions as `§N`, and the
  URL of the issue it answers or of its pull request.
- **Its Hand-apply note.** A change that a source's adoption of the release follows by hand in
  its own files (conventions §15) adds one note under its bullet, indented by two spaces,
  `` - Hand-apply: `<path>` — <what> — <why>. ``: the port the source makes in its adoption. A
  change has one note at most, and a change that several files of a source follow names each
  in it, one item `` `<path>` — <what> — <why>. `` per file, each after the first on a line of
  its own indented by four spaces, as every line the note continues is. A file that only some
  sources have names them in parentheses after its path. A change that no source's code or
  tests follow, such as a new task a source may take up later, has no note.
- **When.** Every pull request but a release's and Dependabot's adds one, a change to the
  documents included, since the conventions and the ADRs bind every source. A pull request that
  changes an entry not yet released edits its fragment.

`changelog/added-response-from-fixture.md`:

```markdown
- `response_from_fixture(load_fixture(path))` gives a recorded answer as an `httpx.Response`,
  its request attached, for calling a source's `classify` directly.
  (ADR-0023, https://github.com/xippios/sdk-core/issues/<n>)
  - Hand-apply: `tests/test_client.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats) — the
    helper `recorded()` → `response_from_fixture` — a shared test helper.
```

The note of a change that two files follow:

```markdown
  - Hand-apply: `tests/test_tasks.py` — <what> — <why>.
    `scripts/refresh_reference.py` — <what> — <why>.
```

## The release

The release's pull request writes `## [X.Y.Z] - YYYY-MM-DD` into `CHANGELOG.md` in place of
`## [Unreleased]`, or above the last release where there is none, and deletes the fragments
it took. The section holds:

- the groups in the order above, each under its heading, `### Added`, `### Changed` and so
  on, and only those with an entry;
- in each group the fragments newest first, by the commit that added each, then the entries
  that `## [Unreleased]` held under that heading;
- after them, any other group that `## [Unreleased]` held, as it stood, such as the
  `### Documentation` entries and the `### Hand-apply for sources` list written before this
  folder;
- each Hand-apply note under its bullet.

The section may gain a lead paragraph above its groups, which says what the release brings a
source and what its adoption takes. Its merge runs `.github/workflows/publish.yml`, which tags
`vX.Y.Z` once `pyproject.toml` names that version and `CHANGELOG.md` holds its heading.
