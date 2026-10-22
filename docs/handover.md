# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2.

## State

Done: WSL2 distro, user johan, toolchain (uv, copier, pre-commit, gh, direnv), folder tree
`~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code permissions, Cursor workspace;
GitHub org ruleset `sdk-main-protection` (PR + `ci` check on `main` for `sdk-*`); repos
`sdk-core`, `sdk-template`, `.github` created, topics set, `pypi` environments with
required reviewer `jdidaskalu`; PyPI account `xippios`.

- **Session 1, `sdk-core`: done.** PR #1 merged 2026-10-22. Layout and decisions are in
  `CLAUDE.md` and ADR-0004 (subpackages `client/`, `mcp/`, `http/`, `testing/`; official
  `mcp` SDK 2.x with `MCPServer`; one background loop for the sync facade). Review
  follow-ups are in PR #2 (conventions §4/§13 + ADR-0005) and the `chore/release-0.1.0` PR.
- **Session 2, `sdk-template`: done.** PR sdk-template#1 open with CI green, including the
  end-to-end proof (generate `sdk-example`, run every check). Generated repos depend on
  `xippios-core` from git (`core_git_ref=main`) until the package is on PyPI.

Open (human): merge sdk-core #2 and the release PR, tag `v0.1.0`, approve the `pypi` run
(pending publisher first); merge sdk-template#1 and tag it `v0.1.0`; API keys in `.envrc`
and as org secrets; Claude GitHub App after the pilot.

## Session 3 — `sdk-usda-nass` (pilot): done

Completed 2026-10-22: scaffold, documentation snapshot, `get_counts`, `get_data`,
`list_param_values`, packaged reference lists with generated enums, filter-key
validation, and the four task-shaped slices (crop progress and condition, county yield
and production, acreage, prices received). What the pilot taught core is ADR-0007 and
ADR-0008. The architect's review fixes (raw value plus `value_number` on projections,
slices skipping the count, `get_acreage_forecasts`, `published_at` from `load_time`)
land in the pilot's adoption PR before its first tag.

## Session 4 — `sdk-comtrade`

Decided 2026-10-22: UN Comtrade is a single-API provider, so it exercises the flat branch
of ADR-0006 (`xippios.comtrade`), and it is wrapped through core's client against the
documented REST endpoints (ADR-0002 holds); the official `comtradeapicall` package is a
second reference next to the documentation, not a dependency. Same sequence as the
pilot: `/new-source comtrade`, snapshot PR first, API-shaped tasks, reference data, then
task-shaped slices after a pattern review.

## Session 3 — original plan

Decisions already taken (2026-10-22 interview):

- A session runs `/new-source usda-nass` from `sdk-template`; the human approves the
  `gh repo create` and environment prompts. Nothing is created outside the script.
- The first PR in the new repo is the documentation snapshot alone (`/refresh-upstream`),
  reviewed before any wrapper is written.
- Task functions mirror the API (ADR-0003): `get_data(...)` exposing `api_GET`'s filter
  parameters under upstream names, `list_param_values(param)`, `get_counts(...)`. Named
  convenience tasks come later, once the `source_desc`/`sector_desc` combinations that
  matter are named.
- `api_base_url` is `https://quickstats.nass.usda.gov/api`; the key is sent as the `key`
  query parameter from `NASS_API_KEY`. NASS documents no per-minute limit; the client
  enforces a self-imposed 30 per minute, and the generated CLAUDE.md says so.
- Import path `xippios.usda.nass` (ADR-0006): the `/new-source` answer `import_path`
  keeps its default, `usda.nass`.
- Quick Stats rejects queries over 50,000 records and does not paginate: `get_data`
  calls `get_counts` first and raises a taxonomy error with the count and a narrowing
  hint before fetching.
- Reference data: package only the small stable parameter lists (`sector_desc`,
  `group_desc`, `agg_level_desc`, `source_desc`, `freq_desc`, `state_alpha`) with
  provenance; `commodity_desc` and other large lists stay live via `list_param_values`.
- Second wave, task-shaped functions after the three API-shaped ones: crop progress and
  condition, county yield and production, planted and harvested acreage, prices received.

Opening prompt, from inside `sdk-template`:

```text
Run /new-source usda-nass with the answers from docs/handover.md in sdk-core (session 3).
Then, in the generated repository: run /refresh-upstream and open that PR first. After it
is merged, add get_data, list_param_values and get_counts with /add-endpoint, one PR each,
with recorded fixtures and live smoke tests. Do not tag, merge or release.
```

Human gates: approve the repository-creation prompts; review the snapshot PR; review
the first endpoint PR closely (is the task signature what an agent wants?); merge; tag.

## After session 3

Install the Claude GitHub App on the org (`/install-github-app` inside Claude Code),
raise `required_approving_review_count` to 1 in the ruleset, and move to issue-driven
work: one issue per endpoint or change, `@claude` in the issue, PR arrives, CI gates,
you merge. Switch generated repos to the PyPI release of `xippios-core` with
`copier update -d core_git_ref=` once it is published.

## Standing human gates

Merge on every repo; every tag and `pypi` approval; new API keys and org secrets;
changes to `docs/conventions.md`; repository creation (approved at the prompt).
