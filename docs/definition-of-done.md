# Definition of done

What a change satisfies before its pull request is opened, each item that applies to it.
CI enforces the first block; the rest is checked in review (`docs/review-checklist.md`).
The Adoption PR block is an adoption PR's alone (conventions §15), which is judged against
it with the Enforced by CI and Process blocks and nothing else: the Code, Tests and Docs
blocks do not apply to it. A release PR changes only the files of conventions §12, no
code, test or fixture, so the Code and Tests blocks have nothing to judge in it. In the
host `xippios-mcp`, a package that is no source (ADR-0026, decision 1), the Code and
Tests blocks and the Docs block's lines on agent docstrings and `docs/upstream/` are
written for a source and do not apply, and its adoption PR meets the items of conventions
§15 that §15 names for the host (ADR-0026, amendment 2026-11-18, point e).

## Enforced by CI
- [ ] `ruff check` and `ruff format --check` pass
- [ ] `mypy --strict` passes
- [ ] unit tests pass offline (no network in the default test run)
- [ ] `pre-commit run --all-files` passes (includes secret detection)

## Code
- [ ] change is in the right layer (ADR-0001); no logic in `mcp.py` / `http.py`
- [ ] every new task function returns `Result[T]` with full `ResultMeta`
- [ ] every new endpoint wrapper matches `docs/upstream/` — names, parameters, semantics
- [ ] errors raised are from the taxonomy in `docs/conventions.md` §5
- [ ] public surface changes are reflected in the `__init__.py` exports, and in a source's README status table (conventions §13) or, in core, whose README keeps none, in the release's statement of the surface, the run-time part and the workbench counted apart by `scripts/count_surface.py` (ADR-0068, decision 6)
- [ ] a core PR names the two consumers of each piece it adds that a caller can name, a source or the host each by the code it runs (in its ADR, or in its description when it has none), or, in its ADR, the part of the family's contract that a piece with one consumer serves: the envelope, the error taxonomy, the package contract with the host, the family check or one of the three security properties (ADR-0059, decisions 1, 2 and 4), or, in its ADR, for a piece that a maintainer's answer adds and decided with fewer than two consumers, that answer and the piece's one consumer or none, which the release's statement of the surface names too (ADR-0059, amendment 2026-11-24)

## Tests
- [ ] each new task function has a fixture-backed unit test (`tests/fixtures/...` recorded, not hand-written)
- [ ] each new task function has a `@pytest.mark.live` smoke test
- [ ] fixtures contain no credentials: grep `tests/fixtures/` for key patterns and for the values of fields the source keeps out of its projections (ADR-0017) before committing
- [ ] the fixture files this PR adds or changes stay under 256 KiB, a file it only moves, its content unchanged, being neither; a truncated one is marked `truncated: true` with the full count or byte size and sha256 (ADR-0040), and a download fixture whose body is its parser tests' sample is marked `sample: true` with the full file's byte size and sha256 (ADR-0020, amendment 2026-11-18, point a)
- [ ] a file-distributed source: each file kind has a sample under `tests/fixtures/files/<file_kind>/` with its provenance line and one live parser test (ADR-0020); a sample of a file over the cap that cannot be cut by bytes is written by a script from one download in the file's own form, and its row says what it keeps (conventions §10; ADR-0020, amendment 2026-11-18, point d)
- [ ] a body a test serves where it was not recorded is one of the kinds of conventions §10 and says where it comes from (ADR-0028, decision 8)
- [ ] a recorded fixture that no test replays after the change, and that no test or document cites, is deleted, and the description names it (conventions §10; ADR-0039, decision 8)

## Docs
- [ ] docstrings written for agents: one-line summary, `Args:` with valid-value examples
- [ ] the change's entry is a fragment under `changelog/`, in the form `changelog/README.md` gives (conventions §12)
- [ ] README updated if install, usage, or endpoint coverage changed
- [ ] if `docs/upstream/` was refreshed: `FETCHED.md` updated and the diff summarised in the PR

## Adoption PR (conventions §15)
An adoption PR meets the items of conventions §15, its routes and its reading for the host,
and the reviewer judges it against them with the Enforced by CI and Process blocks and
nothing else: no new endpoints, tasks or fixtures ride along, and it deletes only the
fixtures, mounts and tests the adoption itself makes dead (ADR-0039, decision 2). The items
stand in §15 alone, and this file copies none of them (ADR-0068, decision 4).

## Process
- [ ] commit messages follow Conventional Commits
- [ ] no tag pushed by hand: a `v*` tag comes from the release train alone (conventions §12)
- [ ] assumptions and open questions listed in the PR description
- [ ] live calls spent by this PR are counted in the description: every request it sent to an upstream, a probe's, a recording's or a live test run's, the keyed ones by number (`none` is a count), since a keyed call spends the quota that every source and process holding its key draws on (ADR-0032, decision 7)
- [ ] the description carries a `## Decisions taken` block: one line per decision the change takes, each backed by a convention, an ADR, a maintainer's decision with its date, or the issue that records the gap; a line backed by none of these is a blocking finding
- [ ] a release PR changes only the files of conventions §12; the reference refresh ran before it, in a PR of its own only when a record changed or `fetched` went from a bare date to the full time, otherwise cited by the release PR
