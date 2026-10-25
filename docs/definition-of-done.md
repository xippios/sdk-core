# Definition of done

Copy this list into every PR description and tick honestly. An unticked item needs a
one-line reason. CI enforces the first block; the rest is reviewed by a human. Every PR
leaves the Adoption PR block out, except an adoption PR (conventions §15), which copies
the Enforced by CI and Process blocks with it and leaves Code, Tests and Docs out.

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
- [ ] fixtures contain no credentials: grep `tests/fixtures/` for key patterns and for the values of fields the source keeps out of its projections (ADR-0017) before committing

## Docs
- [ ] docstrings written for agents: one-line summary, `Args:` with valid-value examples
- [ ] `CHANGELOG.md` has an entry under Unreleased
- [ ] README updated if install, usage, or endpoint coverage changed
- [ ] if `docs/upstream/` was refreshed: `FETCHED.md` updated and the diff summarised in the PR

## Adoption PR (conventions §15)
The reviewer judges an adoption PR against this list and nothing else: no new endpoints,
tasks or fixtures ride along. An adoption PR is a `chore/template-update*` PR: after the
reviewer's `ready` the session enables auto-merge, and GitHub merges it once `ci` is
green and review threads are resolved (ADR-0018).
- [ ] core floor raised: `xippios-core~=X.Y.0` (e.g. `~=0.2.0`, §12) and its extras likewise, from PyPI, no git pin, `uv.lock` updated
- [ ] `copier update` to the template release, conflicts resolved
- [ ] every local workaround a core change replaced is deleted, its tests with it, the core change named for each in the PR description
- [ ] logic duplicated across sources moved into core or dropped; what core lacks is proposed to sdk-core, not copied
- [ ] every test that asserted a limiter wait or a quota pause is marked `rate_limited`, and one that asserted key resolution has a module-level `placeholder_api_key` override that pins nothing (ADR-0013, ADR-0015)
- [ ] generated enum files re-rendered once and committed as rendered
- [ ] `mypy --strict` covers `scripts/` too
- [ ] the current conventions version applied
- [ ] `CHANGELOG.md` line under Unreleased naming the core, template and conventions versions adopted

## Process
- [ ] branch named `feature/`, `fix/`, `chore/`, or `docs/`; Conventional Commits
- [ ] no tag, release, merge, or secret operation performed by the session; the one exception is enabling auto-merge on an adoption or `chore/release-*` PR after the reviewer's `ready`, ADR-0018
- [ ] assumptions and open questions listed in the PR description
