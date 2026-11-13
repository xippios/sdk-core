## Summary

<!-- what and why, two or three sentences -->

## Definition of done

The list below copies sdk-core's `docs/definition-of-done.md`, what the change
satisfies, as a reminder: the description need not tick it (ADR-0018, amendment
2026-11-13). CI enforces the first block, and the review checks the rest against
sdk-core's `docs/review-checklist.md`, reading the description for the assumptions, the
open questions, the live calls and `## Decisions taken`. An adoption PR (conventions §15)
is judged against the Adoption PR block with the Enforced by CI and Process blocks.

### Enforced by CI
- [ ] `ruff check` and `ruff format --check` pass
- [ ] `mypy --strict` passes
- [ ] unit tests pass offline (no network in the default test run)
- [ ] `pre-commit run --all-files` passes (includes secret detection)

### Code
- [ ] change is in the right layer (ADR-0001); no logic in `mcp.py` / `http.py`
- [ ] every new task function returns `Result[T]` with full `ResultMeta`
- [ ] every new endpoint wrapper matches `docs/upstream/` — names, parameters, semantics
- [ ] errors raised are from the taxonomy in `docs/conventions.md` §5
- [ ] public surface changes are reflected in `__init__.py` exports and the README status table
- [ ] a core PR names the two consumers of what it adds (in its ADR, or in its description when it has none), or, in its ADR, the one-consumer reason of ADR-0023 decision 3

### Tests
- [ ] each new task function has a fixture-backed unit test (`tests/fixtures/...` recorded, not hand-written)
- [ ] each new task function has a `@pytest.mark.live` smoke test
- [ ] fixtures contain no credentials: grep `tests/fixtures/` for key patterns and for the values of fields the source keeps out of its projections (ADR-0017) before committing
- [ ] the fixture files this PR adds or changes stay under 256 KiB, a file it only moves, its content unchanged, being neither; a truncated one is marked `truncated: true` with the full count or byte size and sha256 (ADR-0019; binds from the source's 0.3.0 adoption)
- [ ] a file-distributed source: each file kind has a sample under `tests/fixtures/files/<file_kind>/` with its provenance line and one live parser test (ADR-0020)

### Docs
- [ ] docstrings written for agents: one-line summary, `Args:` with valid-value examples
- [ ] the change's entry is a fragment under `changelog/`, in the form `changelog/README.md` gives (conventions §12)
- [ ] README updated if install, usage, or endpoint coverage changed
- [ ] if `docs/upstream/` was refreshed: `FETCHED.md` updated and the diff summarised in the PR

### Adoption PR (conventions §15)
The reviewer judges an adoption PR against this list and nothing else: no new endpoints,
tasks or fixtures ride along, and it deletes only the fixtures, mounts and tests the
adoption itself makes dead (ADR-0018, amendment 2026-10-26).
- [ ] core floor raised: `xippios-core~=X.Y.0`, or `~=X.Y.Z` when patch Z shipped what the source adopts (§12), and its extras likewise; a source package the source depends on bound to its own minor the same way (ADR-0021); from PyPI, no git pin, `uv.lock` updated
- [ ] `copier update` to the template release, conflicts resolved; not applicable on §15's routes (1), a core release without a template tag, and (3), a source frozen on a template tag, whose hand-applied template changes are listed file by file in the PR description
- [ ] every local workaround a core change replaced is deleted, its tests with it, the core change named for each in the PR description
- [ ] code core removed for this source alone is copied in from the commit core's handover names, every copied file listed in the PR description with the ADR that moved it (conventions §15 item 3; ADR-0023, decision 5; ADR-0024)
- [ ] logic duplicated across sources moved into core or dropped; what core lacks is carried by the source and named in an issue of sdk-core, a second copy only when the issue names both sources, never a third (ADR-0023)
- [ ] every test that asserted a limiter wait or a quota pause is marked `rate_limited`, and one that asserted key resolution has a module-level `placeholder_api_key` override that pins nothing (ADR-0013, ADR-0015)
- [ ] generated enum files re-rendered once through the template's refresh script and committed as formatted, after its `ruff format && ruff check --fix`
- [ ] `mypy --strict` covers `scripts/` too
- [ ] the current conventions version applied (1.22's name rule excepted, §2)
- [ ] the changelog fragment names the core, template and conventions versions adopted (§15 item 9)

### Process
- [ ] commit messages follow Conventional Commits
- [ ] no tag pushed by hand: a `v*` tag comes from the release train alone (conventions §12)
- [ ] assumptions and open questions listed in the PR description
- [ ] live calls spent by this PR are counted in the description (keyed calls by number; `none` is a count)
- [ ] the description carries a `## Decisions taken` block: one line per decision the change takes, each backed by a convention, an ADR, a maintainer's decision with its date, or the issue that records the gap; a line backed by none of these is a blocking finding
- [ ] a release PR changes only the files of conventions §12; the reference refresh ran before it, in a PR of its own only when a record changed or `fetched` went from a bare date to the full time, otherwise cited by the release PR

## Assumptions

<!-- one per line, or "none" -->

## Open questions

<!-- one per line, or "none" -->

## Decisions taken

<!-- one line per decision the change takes, each backed by a convention, an ADR, a
maintainer's decision with its date, or the issue that records the gap; or "none" -->
