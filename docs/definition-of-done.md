# Definition of done

Copy this list into every PR description and tick honestly. An unticked item needs a
one-line reason. CI enforces the first block; the rest is reviewed by a human. An
adoption PR (conventions §15) copies the blocks Enforced by CI, Adoption PR and Process
instead.

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
- [ ] public surface changes are reflected in `__init__.py` exports and the README status table

## Tests
- [ ] each new task function has a fixture-backed unit test (`tests/fixtures/...` recorded, not hand-written)
- [ ] each new task function has a `@pytest.mark.live` smoke test
- [ ] fixtures contain no credentials and no value of a field declared sensitive (grep for the key pattern and those values before committing; ADR-0017)

## Docs
- [ ] docstrings written for agents: one-line summary, `Args:` with valid-value examples
- [ ] `CHANGELOG.md` has an entry under Unreleased
- [ ] README updated if install, usage, or endpoint coverage changed
- [ ] if `docs/upstream/` was refreshed: `FETCHED.md` updated and the diff summarised in the PR

## Adoption PR (conventions §15)
The reviewer judges an adoption PR against this list and nothing else: no new endpoints,
tasks or fixtures ride along.
- [ ] core floor raised: `xippios-core~=<minor>` and its extras likewise, from PyPI, no git pin, `uv.lock` updated
- [ ] `copier update` to the template release, conflicts resolved
- [ ] every local workaround a core change replaced is deleted, the core change named for each in the PR description
- [ ] logic duplicated across sources moved into core or dropped; what core lacks is proposed to sdk-core, not copied
- [ ] every test that asserted a limiter wait or key resolution is marked `rate_limited` or overrides `placeholder_api_key` (ADR-0013)
- [ ] generated enum files re-rendered once and committed as rendered
- [ ] `mypy --strict` covers `scripts/` too
- [ ] the current conventions version applied
- [ ] `CHANGELOG.md` line under Unreleased naming the core, template and conventions versions adopted

## Process
- [ ] branch named `feature/`, `fix/`, `chore/`, or `docs/`; Conventional Commits
- [ ] no tag, release, merge, or secret operation performed by the session
- [ ] assumptions and open questions listed in the PR description
