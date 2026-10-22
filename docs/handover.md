# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude)

## State at handover

Done: WSL2 distro Ubuntu-22.04-ex, user johan, toolchain (uv 0.13, copier, pre-commit, gh 2.102, direnv),
folder tree `~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code
permissions, Cursor workspace; GitHub org ruleset `sdk-main-protection` (PR + `ci`
check on `main` for `sdk-*`); repos `sdk-core`, `sdk-template`, `.github` created,
cloned, topics set, `pypi` environments with required reviewer `jdidaskalu`;
PyPI account `xippios`.

Open (human): pending publisher for `xippios-core` on PyPI; API keys in `.envrc` and
as org secrets; Claude GitHub App after the template is proven.

## Session 1 — `sdk-core`

Place this bundle in the repo first:

```bash
cd ~/github/sdk/sdk-core
# CLAUDE.md, docs/conventions.md, docs/adr/, docs/definition-of-done.md, docs/handover.md
git checkout -b chore/governing-docs
git add -A && git commit -m "docs: add conventions, ADRs, definition of done, handover"
git push -u origin chore/governing-docs
gh pr create --fill
```

That PR cannot merge yet (no `ci` check exists). Leave it open; the scaffold PR will
add the workflow, and this one merges right after it, or fold the docs into the
scaffold branch — your choice. Then start the session from inside the repo so direnv
is loaded:

```bash
cd ~/github/sdk/sdk-core && claude
```

Opening prompt:

```text
Read CLAUDE.md, docs/conventions.md, docs/adr/*.md and docs/definition-of-done.md.
Scaffold xippios-core exactly as those documents describe. Deliverables:

1. pyproject.toml (uv, src layout, namespace package xippios/core, extras: mcp, http,
   testing, dev), uv.lock, Python >= 3.12, ruff + mypy strict config, pre-commit config
   with ruff, mypy and detect-secrets.
2. src/xippios/core: client.py, config.py, errors.py, models.py, reference.py,
   pagination.py, mcp.py, http.py, testing.py, __init__.py — per the layout in CLAUDE.md
   and the specifications in conventions.md §4–§10.
3. tests covering client retries/rate limiting (respx), error mapping, Result/ResultMeta,
   reference loader, mcp result caps and error-to-text, http router factory.
4. .github/workflows/ci.yml (job name "ci": ruff, mypy, pytest on 3.12 and 3.13) and
   publish.yml (on tags v*, needs ci, environment pypi, trusted publishing via
   pypa/gh-action-pypi-publish, permissions id-token: write).
5. README.md per conventions §13, CHANGELOG.md (Keep a Changelog, Unreleased section).

Work on branch feature/scaffold. Commit in small Conventional Commits. When done, run the
full check suite, then open a PR with the definition-of-done checklist in the body.
Do not tag, merge or release. If a specification is ambiguous, pick the simplest
reading, note it in the PR, and continue.
```

Human gates: review the PR (public surface in `__init__.py` is the thing to read
closely), merge, then:

```bash
git checkout main && git pull
git tag v0.1.0 && git push origin v0.1.0
# approve the pypi environment run in the Actions tab
```

## Session 2 — `sdk-template`

Start after `xippios-core` 0.1.0 is on PyPI (or installable from git).

```bash
cd ~/github/sdk/sdk-template && claude
```

Opening prompt:

```text
Read ../sdk-core/CLAUDE.md, ../sdk-core/docs/conventions.md and ../sdk-core/docs/adr/*.md.
Build a copier template that generates a complete xippios-<source> repository conforming
to those documents. Template requirements:

- copier.yml questions: source_slug (e.g. usda-nass), source_name (human), upstream_url,
  upstream_docs_url, api_key_env (e.g. NASS_API_KEY or empty), rate_limit_per_minute,
  needs_write_tools (bool, default false), domain_topic (e.g. agriculture).
- Generated layout: src/xippios/<source_pkg>/{__init__.py, _client.py, models.py, tasks.py,
  api/__init__.py, mcp.py, http.py, reference/README.md}, tests/{conftest.py, fixtures/,
  test_tasks.py, test_live.py}, docs/upstream/FETCHED.md, CLAUDE.md, README.md,
  CHANGELOG.md, LICENSE (Apache-2.0), pyproject.toml with extras mcp/http/testing/dev,
  .pre-commit-config.yaml, .github/workflows/{ci.yml,publish.yml} (job "ci", env "pypi"),
  .github/PULL_REQUEST_TEMPLATE.md containing the definition-of-done checklist,
  .claude/commands/{add-endpoint.md, record-fixture.md, refresh-upstream.md,
  refresh-reference-data.md, release-prep.md}, .claude/settings.json (allow/deny per the
  family settings).
- The generated CLAUDE.md must contain: what the package wraps, where upstream docs live,
  the layering rule, how to add an endpoint (pointing at the slash command), how to record
  a fixture, the workflow rules, and the never-do list.
- A `/new-source` command in this repo that runs: copier copy, gh repo create
  xippios/sdk-<source> --public --license Apache-2.0, topics, pypi environment PUT, initial
  commit on branch feature/scaffold, PR. It must print the three remaining human steps
  (PyPI pending publisher, API key to .envrc and org secret, review/merge).
- Prove it: generate a throwaway `sdk-example` into /tmp, run uv sync, ruff, mypy, pytest
  there, and include the log in the PR description. Do not create a GitHub repo for it.
- Document `copier update` for rolling template changes into existing repos.

Work on branch feature/template, Conventional Commits, PR with the definition-of-done
checklist. Do not tag, merge or release.
```

Human gates: review generated `sdk-example` output quality (is the CLAUDE.md something
you would hand a new engineer?), merge, tag `v0.1.0`.

## Session 3 — `sdk-usda-nass` (pilot)

Run `/new-source` from the template repo with `usda-nass`. Before the session, put the
NASS Quick Stats documentation snapshot into `docs/upstream/` (the `refresh-upstream`
command does this; review the result). Your domain input, which the session will ask
for: which Quick Stats `source_desc`/`sector_desc` combinations matter first, and how
the task functions should be cut (by commodity? by report?). Give that as a short
list in the opening prompt.

## After session 3

Install the Claude GitHub App on the org (`/install-github-app` inside Claude Code),
raise `required_approving_review_count` to 1 in the ruleset, and move to issue-driven
work: one issue per endpoint or change, `@claude` in the issue, PR arrives, CI gates,
you merge.

## Standing human gates

Merge on `sdk-core`; every tag and `pypi` approval; new API keys and org secrets;
changes to `docs/conventions.md`.
