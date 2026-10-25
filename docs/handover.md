# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2, and 2026-10-25 with the state after core PR G.

## State

Done: WSL2 distro, user johan, toolchain (uv, copier, pre-commit, gh, direnv), folder tree
`~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code permissions, Cursor workspace;
GitHub org ruleset `sdk-main-protection` (PR + `ci` check on `main` for `sdk-*`); repos
`sdk-core`, `sdk-template`, `.github` created, topics set, `pypi` environments with
required reviewer `jdidaskalu`; PyPI account `xippios`.

- **`sdk-core`**: 0.1.0 on PyPI since 2026-10-22. The consolidation for 0.2.0, what the
  first four sources taught core, is merged up to PR F and written up to PR G (below);
  the release PR follows.
- **`sdk-template`**: v0.1.5 tagged. Generated repositories depend on `xippios-core` from
  PyPI.
- **Sources**: `sdk-usda-nass` (the pilot), `sdk-comtrade` and `sdk-usda-psd` are built
  on core 0.1.0 from PyPI. `sdk-cashctrl` already adopted `Tenants`, `TenantLock`,
  `Scrub` and the plugin's guarantees on a git pin of core 863a443 (sdk-cashctrl#7,
  a835da4, 2026-10-24). `sdk-usda-esr` and `sdk-usda-gats` are briefed and start from
  `QuotaPolicy` (ADR-0015).

Work runs as parallel sessions from the workspace root, one per source plus `core` and
`template`. A session is an orchestrator: it plans, delegates to the `worker` subagent,
passes every branch through the `reviewer` subagent, and works in worktrees under
`.worktrees/`. sdk-core and sdk-template are changed only under the lock in
`COORDINATION.md`, which, with `coordination/`, holds the live state (locks, queue, core
pin, open PRs, the human inbox). This file is the narrative; session briefings live in
`.claude/briefings/`.

## Sessions 3 and 4 — `sdk-usda-nass` and `sdk-comtrade`: done

The pilot, `sdk-usda-nass`, wraps Quick Stats' `get_counts`, `get_data` and
`list_param_values`, with packaged reference lists, generated enums, filter-key
validation and four task-shaped slices (crop progress and condition, county yield and
production, acreage, prices received). What it taught core is ADR-0007 and ADR-0008.
`published_at` stays empty: Quick Stats publishes no release time and `load_time`
carries no zone, so reading one into it would be a guess (ADR-0003).

`sdk-comtrade` exercises the flat branch of ADR-0006 (`xippios.comtrade`) and is wrapped
through core's client against the documented REST endpoints (ADR-0002); the official
`comtradeapicall` package is a second reference, not a dependency. v0.1.0 is tagged.
`sdk-usda-psd` (v0.1.0) and `sdk-cashctrl` followed the same sequence: `/new-source`,
the snapshot PR first, API-shaped tasks, reference data, then task-shaped slices.

## Core consolidation for 0.2.0 (session `core`)

What the sources had to build around core, moved into core one PR at a time, each with
its ADR and a conventions version:

| PR | sdk-core | What | ADR | Conventions |
| --- | --- | --- | --- | --- |
| A | #14 `fix/client-correctness` | cache replay without wire headers, 5xx retried for idempotent methods only, host-free error messages | ADR-0011, ADR-0005 amendment | 1.6 |
| | #15 `feature/result-meta-total` | `ResultMeta.total`, upstream's record count | ADR-0012 | 1.7 |
| B | #16 `feature/testing` | recorder scrub, request bodies, form data, replay params, offline guarantees owned by the plugin | ADR-0013 | 1.8 |
| C | #17 `feature/tenants` | `Tenants`, tenant lock, CLI option hooks, `ResultMeta.tenant`, the `confirm` check | ADR-0014 | 1.9 |
| D | #18 `feature/client-policy` | request hooks, `QuotaPolicy`, retries shaped by `classify`, `auth=` per request | ADR-0015; ADR-0010's "core today" note resolved | 1.10 |
| E | #19 `feature/mcp-result-cap` | per-tool result caps, a cap note that promises no filter | ADR-0016 | 1.11 |
| F | #20 `feature/reference` | ruff-clean ASCII enum rendering, `render_int_enums`, `id_name_pairs` | ADR-0008 amendment | 1.12 |
| G | `docs/adoption-and-hygiene` | §15 adoption checklist and the definition of done's Adoption PR block, adoption PRs auto-merged, the one-minor core bound and the 0.x rule (§11, §12), `InvalidRequestError` wording (§5), `Fetched` as a UTC time, HTML tables, vendor snapshots, personal identifiers out of task projections (§3, §4), CI runs pre-commit, docstring examples on `xippios.usda.nass`, the `RateLimit` docstring | ADR-0017, ADR-0018; ADR-0003 and ADR-0007 amendments | 1.13 |

ADR-0017 is a rule for sources: nothing in core implements it. Ahead is the release PR,
`chore/release-0.2.0`: version and CHANGELOG section. Johannes then tags `v0.2.0` and
approves the `pypi` run.

## After PR G

- **Template (session `template`)**: T1, `feature/template-hygiene-2`, brings the
  template's hygiene rows and the core bound (`xippios-core~=X.Y.0`, §12, ADR-0018); T2
  adds the `/adopt-release` command, which walks conventions §15. The template's half of
  the 0.2.0 ADRs goes into the template release that adopts core 0.2.0, tagged after
  core's: `ci.yml` runs pre-commit (ADR-0018), the `QuotaPolicy` scaffold (ADR-0015),
  the `IntEnum` path through `render_int_enums` (ADR-0008 amendment), the
  `multi_tenant` question (ADR-0014), `caps=getattr(tasks, "MCP_CAPS", None)` in
  `mcp.py` (ADR-0016), the placeholder key through the plugin (ADR-0013) and a comment
  on personal identifiers in the model scaffold (ADR-0017).
- **Sources**: each adopts core 0.2.0 and that template release in one adoption PR before
  its next release (conventions §12, §15, ADR-0018), a `chore/template-update*` PR
  judged against the definition of done's Adoption PR block and nothing else, and
  auto-merged after the reviewer's `ready`. The release's ADRs and CHANGELOG list per
  source what goes: the hand-written placeholder fixtures (ADR-0013); sdk-usda-psd's
  `QuotaAwareClient` and sdk-comtrade's `reference_client` (ADR-0015); the caps of
  comtrade's and PSD's reference lists (ADR-0016). Generated enum files are re-rendered
  once (ADR-0008 amendment). sdk-cashctrl, which adopted ADR-0013 and ADR-0014 on its
  git pin already, has left the unpin, the bound, ADR-0015 and ADR-0016, and keeping
  `ssn` and `iban` out of its task projections (ADR-0017). Sources already published
  with an open bound stay as published and get the bound with their next release.
- **Later**: install the Claude GitHub App on the org and move to issue-driven work: one
  issue per endpoint or change, `@claude` in the issue, PR arrives, CI gates, a human
  merges. The ruleset keeps no required approving review, which would hold every
  auto-merge (ADR-0018).

## Standing human gates

Every tag and every `pypi` approval; the merge of every PR except `chore/template-update*`
and `chore/release-*`, which a session sets to auto-merge after the reviewer's `ready`;
new API keys and org secrets; changes to `docs/conventions.md`; repository creation
(approved at the prompt); the decisions asked as an interview before each work package.
