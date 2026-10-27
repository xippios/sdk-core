# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2, 2026-10-25 with the state after the core 0.2.0 release PR, 2026-10-26 with core 0.2.1, the release train and the family check (the sections from "Core 0.2.1" on), 2026-10-27 with `sdk-core`'s state line at the core 0.2.1 release PR, and 2026-10-27 at the core 0.3.0 release PR (the State block, the session model, the sections from "Core 0.3.0" on, and notes where 0.3.0 changed an earlier line).

## State

Done: WSL2 distro, user johan, toolchain (uv, copier, pre-commit, gh, direnv), folder tree
`~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code permissions, Cursor workspace;
GitHub org ruleset `sdk-main-protection` (PR + `ci` check on `main` for `sdk-*`); repos
`sdk-core`, `sdk-template`, `.github` (renamed `sdk-gates` on 2026-10-27) created, topics
set, `pypi` environments with required reviewer `jdidaskalu`; PyPI account `xippios`.

- **`sdk-core`**: 0.1.0 on PyPI since 2026-10-22 and 0.2.0, what the first four sources
  taught core (below), since 2026-10-25, both tagged by Johannes; 0.2.1 since
  2026-10-27, the first release whose release PR tagged itself (`publish.yml` tagged
  `v0.2.1` on the merge commit, Johannes approved the `pypi` run). 0.3.0 (below) brings
  the family review's core scope, the code of ADR-0019 and ADR-0022, and ADR-0024; its
  release PR, `chore/release-0.3.0`, releases it the same way: the merge tags `v0.3.0`
  and waits at `pypi` for Johannes's approval.
- **`sdk-template`**: v0.2.0 tagged 2026-10-25; v0.2.1 and v0.2.2 on 2026-10-27, each
  tagged by its own `release.yml` on its release PR's merge (v0.2.2 renders `gates.yml`
  calling the renamed gates repository, `xippios/sdk-gates`). Template v0.3.0, the
  template's cleanup and the 0.3.0 halves, tags with core 0.3.0. Generated repositories
  depend on `xippios-core` from PyPI.
- **Sources**: on 2026-10-27, `sdk-usda-nass`, `sdk-usda-psd`, `sdk-usda-esr`,
  `sdk-usda-gats` and `sdk-cashctrl` are bound to core `~=0.2.0` on template v0.2.0, and
  `sdk-comtrade` to `>=0.1.0` on template v0.1.5 until its 0.2.0 adoption. Each adopts
  core 0.2.1 with template v0.2.2, then core 0.3.0, as "Adopting core 0.3.0" below
  lists. `sdk-usda-esmis` and `sdk-eurostat`, the first of the next sources
  (`docs/roadmap.md` §4), started on core 0.2.1 and template v0.2.2; by the roadmap's
  pin rule (`docs/roadmap.md` §3) each re-pins core's `main` to the SHA its next PR
  needs and moves to `~=0.3.0` in its one v0.3.0 adoption.

Work runs as parallel sessions from the workspace root, on the rules of
`coordination/RULES.md` (rules v2 since 2026-10-26): one `family` session owns sdk-core,
sdk-template, the coordination repository and the gates repository `xippios/sdk-gates`,
and one session per source owns its `sdk-<source>` (`coordination/owners.toml`); a
source never writes core or the template, it queues a row. A session is an orchestrator:
it plans, delegates to the `worker` subagent, passes every branch through the `reviewer`
subagent, and works in worktrees under `.worktrees/`. sdk-core and sdk-template are
changed only under their lock, which `family` alone takes. `coordination/` holds the
live state (claims, locks, the queue, the log, the human inbox, the ledger, and
`state.md`, generated hourly from GitHub and PyPI), and a dashboard rendered from it
locally points to the rules. This file is the narrative; session briefings live in
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

## Core 0.2.0 (session `core`)

What the sources had to build around core, moved into core one PR at a time, each with
its ADR and a conventions version, then released:

| PR | sdk-core | What | ADR | Conventions |
| --- | --- | --- | --- | --- |
| A | #14 `fix/client-correctness` | cache replay without wire headers, 5xx retried for idempotent methods only, host-free error messages | ADR-0011, ADR-0005 amendment | 1.6 |
| | #15 `feature/result-meta-total` | `ResultMeta.total`, upstream's record count | ADR-0012 | 1.7 |
| B | #16 `feature/testing` | recorder scrub, request bodies, form data, replay params, offline guarantees owned by the plugin | ADR-0013 | 1.8 |
| C | #17 `feature/tenants` | `Tenants`, tenant lock, CLI option hooks, `ResultMeta.tenant`, the `confirm` check | ADR-0014 | 1.9 |
| D | #18 `feature/client-policy` | request hooks, `QuotaPolicy`, retries shaped by `classify`, `auth=` per request | ADR-0015; ADR-0010's "core today" note resolved | 1.10 |
| E | #19 `feature/mcp-result-cap` | per-tool result caps, a cap note that promises no filter | ADR-0016 | 1.11 |
| F | #20 `feature/reference` | ruff-clean ASCII enum rendering, `render_int_enums`, `id_name_pairs` (both renderers replaced by `render_enums` in 0.3.0) | ADR-0008 amendment | 1.12 |
| G | #21 `docs/adoption-and-hygiene` | §15 adoption checklist and the definition of done's Adoption PR block, adoption PRs auto-merged, the one-minor core bound and the 0.x rule (§11, §12), `InvalidRequestError` wording (§5), `Fetched` as a UTC time, HTML tables, vendor snapshots, personal identifiers out of task projections (§3, §4), CI runs pre-commit, docstring examples on `xippios.usda.nass`, the `RateLimit` docstring | ADR-0017, ADR-0018; ADR-0003 and ADR-0007 amendments | 1.13 |
| Release | `chore/release-0.2.0` | version 0.2.0; the CHANGELOG's `[0.2.0]` section, breaking changes first; "Adopting core 0.2.0" below | — | — |

ADR-0017 is a rule for sources: nothing in core implements it. The release PR merged
through auto-merge after the reviewer's `ready` (ADR-0018). 0.2.0 was the last release
tagged by hand. From 0.2.1 on the release train runs it (conventions §12): the release
PR's merge runs `publish.yml`, which tags `vX.Y.Z` from `pyproject.toml` on the merge
commit, runs CI, checks the tag against the version and builds; Johannes's gate is the
approval of the run in the environment `pypi`. A source adopts a release from PyPI once
it is there.

## Adopting core 0.2.0

Each source adopts core 0.2.0, and the sdk-template release that goes with it, in one
adoption PR, a `chore/template-update*` PR, before its next release (conventions §12 and
§15, ADR-0018). Its description is the §15 checklist, ticked; the reviewer judges it
against the definition of done's Adoption PR block and nothing else, and it auto-merges
after the reviewer's `ready`. Below, the checklist is pre-filled from the ADRs'
consequences, the CHANGELOG's `[0.2.0]` section and each source's `main` on 2026-10-25:
each local workaround a source deletes with the core change that replaced it (§15 item
3), and what it declares or marks (item 5). The adoption PR confirms every item against
the source as it is then. This section is the record of 0.2.0; where 0.3.0 replaced an
item, a parenthesis says so.

### Every source

- Item 1, core floor: `xippios-core~=0.2.0`, and `xippios-core[mcp]~=0.2.0`, `[http]`
  and `[testing]` likewise, from PyPI, with `uv.lock` updated; all four read `>=0.1.0`
  today.
- Item 2: `copier update` to the template release that adopts core 0.2.0, tagged after
  core's: `ci.yml` runs pre-commit, `mcp.py` passes
  `caps=getattr(tasks, "MCP_CAPS", None)`, the placeholder key goes through the plugin.
- Items 3 and 4, the workarounds deleted and the logic moved into core: per source
  below.
- Item 5: `xippios_placeholder_key_envs` under `[tool.pytest.ini_options]` names the
  key variable, and `tests/conftest.py` keeps no `placeholder_api_key` fixture or
  `PLACEHOLDER_KEY` of its own, nor the imports that served only them (ADR-0013). A
  test that reaches the network is marked `network`; one that asserts a limiter wait, a
  quota pause or a quota refusal is marked `rate_limited`; a module that tests key
  resolution defines a `placeholder_api_key` that pins nothing.
- Item 6: `enums.py` re-rendered once and committed as rendered: ASCII-only, `__all__`
  sorted, one name per line (ADR-0008 amendment of 2026-10-24; from 0.3.0, `render_enums`
  and the refresh script's ruff step, committed as formatted, conventions §15 item 6).
- Item 7: `files = ["src", "tests", "scripts"]` under `[tool.mypy]`; all four read
  `["src", "tests"]` today.
- Item 8, conventions 1.13, among the rest: no request into a spent quota, through one
  `QuotaPolicy` (§6, ADR-0015), after checking that any `x-ratelimit-*` header it reads
  describes the long-window quota, not a pace, and a source whose 429 is a pace refusal
  without a long-window quota sets a short `window` (the documented pause) or installs
  no policy, since the default `window=3600` would turn one 429 without `Retry-After`
  into an hour of refusals; caps kept as `MCP_CAPS` in `tasks.py` (§8, ADR-0016);
  `Fetched` in `docs/upstream/FETCHED.md` as the UTC time with `Z`
  (`2026-10-24T09:15:00Z`, §3), where all four record a date today.
- Item 9: `CHANGELOG.md` has a line under Unreleased naming core 0.2.0, the template
  release and conventions 1.13.

### sdk-usda-psd

- Deletes (item 3):
  - `QuotaAwareClient` with its cache probe, `observe_quota`, `quota_pause`, `quota()`,
    the module-level snapshot and `Quota` in `_client.py` →
    `policy = QuotaPolicy(window=QUOTA_WINDOW, source=SOURCE)` and
    `client = AsyncClient(policy.install(config), auth=auth)` (ADR-0015). `classify`
    reads `policy.snapshot()` for its message instead of updating a snapshot, and
    `QuotaSnapshot.describe()` replaces `Quota.describe()`. The policy's default
    headers, `x-ratelimit-limit` and `x-ratelimit-remaining`, are api.data.gov's hourly
    quota. The tests of the deleted pieces in `tests/test_client.py` go with them.
  - `render_id_enums` and its `member_names` in `scripts/refresh_reference.py` →
    `render_int_enums` with `id_name_pairs(records, id_field=..., name_field=...)`
    (ADR-0008 amendment); the step that formats `enums.py` after a refresh (the script's
    docstring, `/refresh-reference-data`) → gone. (0.3.0: `render_enums` replaces
    `render_int_enums`, and the script formats `enums.py` with ruff again, ADR-0008,
    amendment 2026-10-27.)
  - `fresh_quota` in `tests/conftest.py` → the plugin forgets every policy's snapshot
    around each offline test (ADR-0013, decision 4).
  - `placeholder_api_key` and `PLACEHOLDER_KEY` in `tests/conftest.py` → the plugin's pin
    (ADR-0013).
- Its tests see: a 429 without `Retry-After` is raised after one request, carrying the
  one-hour `retry_after`, so `test_core_retries_a_429_only_within_its_backoff` expects
  1 attempt for it, not 4 (ADR-0015, `classify` shapes retries).
- Declares and marks (item 5): `xippios_placeholder_key_envs = ["DATA_GOV_API_KEY"]`;
  the tests that assert what a spent quota does, a pause or a refusal without sending
  (today `test_the_wrapper_raises_once_on_the_recorded_429_and_refuses_the_next`,
  `test_a_spent_quota_beyond_backoff_max_is_refused_without_sending`,
  `test_a_spent_quota_within_backoff_max_is_waited_out`,
  `test_the_bound_is_the_clients_backoff_max` and
  `test_a_cache_hit_is_served_while_the_quota_is_spent`) are marked `rate_limited`.
- Item 6: `AttributeId` and `UnitId` re-rendered through `render_int_enums` (through
  `render_enums` from 0.3.0).
- Item 8: `MCP_CAPS = {"list_countries": ResultCap(max_rows=300)}` in `tasks.py`, so all
  251 countries reach an agent, the United States included (ADR-0016); `Fetched` as a
  UTC time where it records the UTC date.

### sdk-comtrade

- Deletes (item 3):
  - `reference_client`, the second, keyless client in `_client.py` → the one `client`
    with `auth=None` for the reference files (ADR-0015); `REFERENCE_CACHE` can stay as
    that client's cache, narrowed to the reference paths by `cache_filter`, and a task
    answered from it sets `retrieved_at` from `xippios_cache_stored_at` (conventions §4),
    reading the response with `get()` and `decode_json()` in 0.2.0 and with `get_answer`,
    whose `retrieved_at` is that stored time, from 0.3.0. On the one client a
    reference fetch shares `RATE_LIMIT`'s pace, and `before_request` runs for an
    `auth=None` call too: a file not yet cached waits for, or is refused by, a spent
    daily quota once the policy below is installed, though fetching it costs none.
  - `replay_query` in `tests/conftest.py`, a route on the whole recorded query → the
    plugin's `replay_fixture("get", case, match_params=[...])`, naming the parameters a
    test relies on (ADR-0013); `replay_get`'s `countOnly` split likewise, the count
    fixture mounted before the data fixture, since absence cannot be matched.
  - The `ruff format` step after `scripts/refresh_reference.py` (its docstring,
    `/refresh-reference-data`), and the class ordering it does so that `__all__` comes
    out sorted → gone: `render_str_enums` writes a ruff-clean module with `__all__`
    sorted (ADR-0008 amendment). (0.3.0 brings the ruff step back, after one
    `render_enums` call, ADR-0008, amendment 2026-10-27.)
  - `placeholder_api_key` and `PLACEHOLDER_KEY` in `tests/conftest.py`, and
    `test_replay_tests_send_the_placeholder_key` in `tests/test_tasks.py` → the
    plugin's pin, which core's own tests prove (ADR-0013).
- Declares and marks (item 5): `xippios_placeholder_key_envs = ["COMTRADE_API_KEY"]`; a
  test that asserts the policy's pause or refusal is marked `rate_limited`.
- Item 6: `enums.py` re-rendered once.
- Item 8: `QuotaPolicy(limit_header=None, remaining_header=None, spent=...,
  window=86400)` installed on `config`, its `spent` reading the 403's "replenished in
  HH:MM:SS", which `_quota_reset` reads for `classify` today: its `x-ratelimit-*`
  headers describe the per-second pace (`x-ratelimit-limit: 1`), not the daily quota of
  500 calls (ADR-0015). `MCP_CAPS` in `tasks.py`: `list_reporters` and `list_partners`
  at `ResultCap(max_rows=400, max_bytes=100_000)`, so both lists reach an agent whole,
  their `search` filters dropped or kept as a convenience; `list_commodities`, about
  2 MB for HS, keeps `search` and a cap of its own whose `note` names it (ADR-0016).
  `Fetched` as a UTC time where it records the local calendar date.

### sdk-usda-nass

- Deletes (item 3): `placeholder_api_key` and `PLACEHOLDER_KEY` in `tests/conftest.py`,
  with the imports of `API_KEY_ENV` and `auth` that served only them, and
  `test_replay_tests_send_the_placeholder_key` in `tests/test_tasks.py` → the plugin's
  pin (ADR-0013).
- Declares and marks (item 5): `xippios_placeholder_key_envs = ["NASS_API_KEY"]`; a test
  that asserts the policy's pause or refusal is marked `rate_limited`.
- Item 6: `enums.py` re-rendered once through `scripts/refresh_reference.py`; its first
  line changes, nothing else.
- Item 8: ADR-0015 lists usda-nass among the sources that adopt ADR-0010's decision 4 by
  installing a `QuotaPolicy` on `config`. Quick Stats sends no `x-ratelimit-*` header in
  the recorded fixtures and documents no long-window quota, so its 429 is a pace refusal
  and a policy would act on it alone. A source in that position sets a short `window`,
  the documented pause (60 s, say), or installs no `QuotaPolicy` at all, because the
  default `window=3600` would turn one 429 without `Retry-After` into an hour of
  refusals once a call's retries are exhausted (ADR-0015). `Fetched` as a UTC time where
  `/refresh-upstream` writes the date.
- `sent_urls(route)`, which sdk-usda-nass asked for, is there for the tests that read
  the sent query, key included, from `route.calls`.

### sdk-cashctrl

- Item 1: the `[tool.uv.sources]` git pin of core 863a443 goes, `core_git_ref` is `''`
  in `.copier-answers.yml`, and core and its extras are bound `~=0.2.0` from PyPI.
- Item 3: nothing of ADR-0013 or ADR-0014 is left to delete. sdk-cashctrl#7 moved it to
  `Tenants`, `TenantLock`, `list_task`, `Scrub` in its recorder and the plugin's
  guarantees, and its tests use `assert_write_tools` and `mcp_call_text` already. (From
  0.3.0, ADR-0024 hands `Tenants`, `TenantLock`, `list_task`, `assert_write_tools` and the
  recorder's extras back to cashctrl; "Adopting core 0.3.0" lists the copy.)
- Item 4, a candidate for sdk-core rather than a copy: `scripts/record_fixture.py`
  writes the fixture itself, because core's `record` writes as soon as core's verify
  passes, before a source's final check could run, and `Scrub.rewrite` does not reach
  the request URL. (ADR-0024, decision 4, settled it the other way: a source rewrites and
  writes its fixture itself, and core adds no hook.)
- Declares and marks (item 5): `xippios_placeholder_key_envs =
  ["CASHCTRL_DEMO_API_KEY"]` is set already; a test that asserts the policy's pause or
  refusal is marked `rate_limited`.
- Item 6: `enums.py` re-rendered once.
- Item 8, what came after its pin (core PRs D to G): ADR-0015 lists cashctrl among the
  sources that adopt ADR-0010's decision 4 by installing a `QuotaPolicy`, one per
  organisation client in `_build`, and its CLAUDE.md has decision 4 waiting for this
  helper. CashCtrl sends no `x-ratelimit-*` header, `x-cashctrl-requests-left` has no
  documented window, and its documented 429 asks only to "add delays": a pace refusal
  with no long-window quota behind it. A source in that position sets a short `window`,
  the documented pause (60 s, say), or installs no `QuotaPolicy` at all, because the
  default `window=3600` would turn one 429 without `Retry-After` into an hour of
  refusals once a call's retries are exhausted (ADR-0015). Its `classify` maps every 5xx
  to `UpstreamError` through `error_from_response`, so its read retries stay (ADR-0015).
  `MCP_CAPS` only for a reference list an agent needs whole; none is known. The
  projections its tasks return leave out `ssn` and `iban`, and `create_person` and
  `update_person`, which take `ssn`, do not echo it in `meta.request`; the fixture grep
  covers their values (ADR-0017). `Fetched` as a UTC time where it records the UTC date.
  New since the pin and optional: `Tenants(..., hints=...)` tells the operator what a
  refused `CASHCTRL_<NAME>_SUBDOMAIN` should hold (`Tenants` is cashctrl's own from
  0.3.0, ADR-0024).

### sdk-usda-esr and sdk-usda-gats

Not built yet: each starts on core 0.2.0 from PyPI with one `QuotaPolicy` for
api.data.gov's hourly quota on every client that sends `DATA_GOV_API_KEY` (ADR-0009,
ADR-0015), not a copy of PSD's client, and meets the §15 checklist from its first PR.

## After the release

- **Template (session `template`)**: T1, `feature/template-hygiene-2`, brings the
  template's hygiene rows and the core bound (`xippios-core~=X.Y.0`, §12, ADR-0018); T2,
  next, adds the `/adopt-release` command, which walks conventions §15. The template's
  half of the 0.2.0 ADRs goes into the template release that adopts core 0.2.0, tagged
  after core's: `ci.yml` runs pre-commit (ADR-0018), the `QuotaPolicy` scaffold
  (ADR-0015), the `IntEnum` path through `render_int_enums` (ADR-0008 amendment), the
  `multi_tenant` question (ADR-0014), `caps=getattr(tasks, "MCP_CAPS", None)` in
  `mcp.py` (ADR-0016), the placeholder key through the plugin (ADR-0013) and a comment
  on personal identifiers in the model scaffold (ADR-0017). The `multi_tenant` question
  was never built (ADR-0024).
- **Sources**: each adopts core 0.2.0 and that template release as "Adopting core 0.2.0"
  lists, once both are published. Sources already published with an open bound stay as
  published and get the bound with their next release.
- **Later**: install the Claude GitHub App on the org and move to issue-driven work: one
  issue per endpoint or change, `@claude` in the issue, PR arrives, CI gates, a human
  merges. Auto-merge waits for every required approving review, so the ruleset must
  require none for adoption and release PRs to merge on `ci` alone (ADR-0018).

## Core 0.2.1 (session `family`)

Step 0 of the roadmap, before 0.3.0: one feature PR and its release PR.

| PR | sdk-core | What | ADR | Conventions |
| --- | --- | --- | --- | --- |
| | `feature/release-train-and-family-tests` | the release train (`publish.yml` tags from `pyproject.toml`, `ci.yml` without its push trigger, actions pinned by SHA), `gates.yml` switched off, `xippios.core.testing.family`, the shared test helpers (C12), anchored sdist patterns, the live workflow and the family check in §10, adoption auto-merge by merge class in §15, the roadmap sentences | ADR-0009 amendment; ADR-0013 amendment; ADR-0018 amendments (b), (c), (e) | 1.15 |
| Release | `chore/release-0.2.1` | version 0.2.1; the CHANGELOG's `[0.2.1]` section; README install lines `~=0.2.1`; the first release PR that tags itself | — | — |

The release PR changes only the subset of conventions §12. Its merge runs `publish.yml`,
which tags `v0.2.1` on the merge commit and waits at `pypi`; the first run also shows
whether the environment's deployment-branch policy "protected branches only" admits a
ruleset-protected `main`, and if it does not, Johannes sets the policy to `main` and
re-runs the failed jobs. Once the tag exists, only "Re-run failed jobs" finishes the
release: a dispatch or "Re-run all jobs" stops at `release-check`, which finds the tag.
The tag precedes the build, so a build that fails for good leaves a tag without a
release; the fix is a patch release. If `ci` fails before the tag, re-run the failed jobs
rather than pushing a fix. `publish.yml` has no `concurrency` group: GitHub keeps one
pending run per group and cancels it for the next, so a release run queued behind a run
waiting at `pypi` would be lost. Two pushes to `main` close together can therefore both
see an untagged version: the second run's tag push then fails red, or, if the first
run's `ci` failed, the second tags a later commit. The fix: re-run the failed jobs of
the run whose commit is the release; if the other run already tagged a later commit,
Johannes rejects its `pypi` deployment and the release is re-done as a patch. A release
is not merged while another release run is waiting.
`gates.yml` stays off until Johannes sets the repository variable `GATES_CALLER` to `1`,
which he does only if the ruleset editor offers no "Require workflows" rule.

## Adopting core 0.2.1

Each source adopts core 0.2.1 and template v0.2.2 in one adoption PR before its next
release (conventions §15): not v0.2.1, whose `gates.yml` calls the gates repository by
its old name, which a `uses:` reference does not follow to the renamed one. Pre-filled
below from each source's `main` on 2026-10-26; the adoption PR confirms every item
against the source as it is then.

### Every source

- Item 1, core floor: `core_version=0.2.1`, so `xippios-core~=0.2.1` and its `[mcp]`,
  `[http]` and `[testing]` extras likewise (ADR-0018, amendment c): the rendered
  `tests/test_family.py` imports `xippios.core.testing.family`, which 0.2.0 lacks.
- Item 2, `copier update` to template v0.2.2 (v0.2.1's changes, and `gates.yml` calling
  `xippios/sdk-gates`): it renders `tests/test_family.py`, one
  line, `from xippios.core.testing.family import *  # noqa: F403`, and deletes
  `tests/test_layout.py` and `tests/test_adapters.py`, whose checks the family check
  makes; `tests/conftest.py` loses `anyio_backend`, which the plugin provides;
  `publish.yml` and `ci.yml` move to the release train, so the source's next release PR
  tags itself; `gates.yml` arrives switched off.
- Items 3 and 4, by hand in `tests/test_tasks.py`, which the template does not update:
  `test_package_has_a_version` and `test_task_is_a_sync_facade_with_an_agent_docstring`
  go; the family check's `test_family_package_has_a_version`,
  `test_family_tasks_return_results` and `test_family_tasks_carry_agent_docstrings`
  replace them. The family check asserts that a task is synchronous, not that it carries
  an `async_fn`: conventions §6 makes the async variant optional, and `list_task`, core's
  until 0.3.0 and cashctrl's from then on (ADR-0024), has none. Then the local copies of
  the shared helpers, per source below.
- The package under test needs no declaration: the family check finds the one `tasks.py`
  under `src/xippios/`. The ini option `xippios_package` names it where there are
  several, which none of the six sources has.
- Item 8, conventions 1.15: the live workflow of §10 is the template's `live.yml`, which
  every source but comtrade renders already; comtrade renders it only with its v0.2.0
  adoption (`chore/template-update-v0.2.0`). §10's family check is the
  `tests/test_family.py` of item 2.
- Item 9: `CHANGELOG.md` has a line under Unreleased naming core 0.2.1, template v0.2.2
  and conventions 1.15.

The family check, run on each source's `main` of 2026-10-26 with this core installed:
usda-psd, usda-nass, usda-esr and usda-gats pass, the write-server test skipped;
cashctrl passes all eleven; comtrade fails only the core bound (`xippios-core>=0.1.0`,
before its own 0.2.0 adoption, which sets `~=0.2.0`).

### sdk-usda-psd

- `recorded()` in `tests/test_client.py` → `response_from_fixture(load_fixture(path))`.
- `_mount_recorded_404` in `tests/test_slices.py` →
  `replay_fixture(DATA, "unknown_year", url=f"https://api.fas.usda.gov{_path(year)}")`;
  the assertion that the recording is the empty 404 stays in the test that relies on it.
- `before <= result.meta.retrieved_at <= after` in `tests/test_lists.py` →
  `assert_time_between(result.meta.retrieved_at, before, after)`, which allows the
  WSL2 host's clock step.
- `anyio_backend` in `tests/conftest.py` → the plugin's (the template update removes it).

### sdk-usda-esr

- `recorded()` in `tests/test_client.py` → `response_from_fixture`.
- `_mount_recorded_404` in `tests/test_slices.py` →
  `replay_fixture(COUNTRY, "year_1900", url=f"{BASE_URL}{path}")`.
- The `retrieved_at` bracket in `tests/test_lists.py` → `assert_time_between`.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### sdk-usda-gats

- `recorded()` in `tests/test_client.py` → `response_from_fixture`.
- `CLOCK_SLACK` in `tests/test_lists.py` and `tests/test_tasks.py` → `CLOCK_SLACK` and
  `assert_time_between` from `xippios.core.testing`.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### sdk-usda-nass

- `sent_query` in `tests/test_tasks.py` → `xippios.core.testing.sent_query`, the same
  scrubbed query of the last request; a parameter sent twice fails it, where the local
  one kept the last value.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### sdk-comtrade

After its own adoption of 0.2.0 (`chore/template-update-v0.2.0`):

- `_sent` in `tests/test_tasks.py` and the inline `dict(route.calls.last.request.url.params)`
  → `sent_query(route)`; `recorded_params` in `tests/conftest.py` and `_recorded` in
  `tests/test_tasks.py` → `recorded_query(load_fixture(path))`.
- `tests/test_adapters.py`, which the update deletes, carries one test of comtrade's
  own, `test_every_task_is_exposed_without_touching_the_adapters`: the family check makes
  its registration half; its check that `mcp.py` and `http.py` name no task moves to
  `tests/test_tasks.py` if comtrade keeps it.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### sdk-cashctrl

- `recorded()` in `tests/test_errors.py` → `response_from_fixture`.
- `recorded_query` in `tests/test_tasks.py` → `xippios.core.testing.recorded_query`; the
  inline `dict(route.calls.last.request.url.params)` → `sent_query(route)`.
- `tests/test_adapters.py`, which the update deletes: `test_the_write_server_serves_write_tasks_only`
  is the family check's `test_family_write_server_serves_the_write_tasks` (the same
  `assert_write_tools` call); `test_the_organisation_list_is_on_the_read_server`,
  `test_write_tools_are_the_write_tasks_with_their_parameters` and
  `test_the_order_categories_are_on_the_read_server_and_the_router` are cashctrl's own
  and move to `tests/test_tasks_write.py` or `tests/test_tasks.py`. From 0.3.0 the family
  check no longer tests the write server (ADR-0024): cashctrl keeps that test with its
  own copy of `assert_write_tools`, as "Adopting core 0.3.0" says.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### Template v0.2.1: the two family checks that are CI steps

Two family checks read the pull request, not the package, so they are steps of the
template's `ci.yml`, not tests; the checkout needs the history (`fetch-depth: 0`):

```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0 # both steps below diff against origin/<base>
          persist-credentials: false
      # Conventions §12: every PR but a release, an adoption or Dependabot's (which writes
      # no entry) adds a CHANGELOG entry.
      - name: CHANGELOG.md has an entry
        if: >-
          github.event_name == 'pull_request'
          && !startsWith(github.head_ref, 'chore/release-')
          && !startsWith(github.head_ref, 'chore/template-update')
          && !startsWith(github.head_ref, 'dependabot/')
        env:
          BASE: ${{ github.base_ref }}
        run: |
          if ! git diff --name-only "origin/${BASE}...HEAD" | grep -qx 'CHANGELOG.md'; then
            echo "::error::CHANGELOG.md has no entry under Unreleased (conventions §12)"
            exit 1
          fi
      # ADR-0019: the fixture files a PR adds or changes stay under 256 KiB. --no-renames
      # lists a moved fixture as added, so one moved and grown is seen. LEVEL is warning in
      # template v0.2.1 and error from v0.3.0, when the cap binds a source.
      - name: Fixture files under 256 KiB
        if: github.event_name == 'pull_request'
        env:
          BASE: ${{ github.base_ref }}
          LEVEL: warning
        run: |
          over=0
          while IFS= read -r -d '' path; do
            size="$(stat -c %s "$path")"
            if [ "$size" -ge 262144 ]; then
              echo "::${LEVEL} file=${path}::${size} bytes, over the 256 KiB cap (ADR-0019)"
              over=1
            fi
          done < <(git diff -z --name-only --no-renames --diff-filter=AM "origin/${BASE}...HEAD" -- tests/fixtures/)
          if [ "$LEVEL" = error ]; then
            exit "$over"
          fi
```

The cap binds a source from its 0.3.0 adoption (conventions, header of 1.14), so
template v0.2.1 renders the second step with `LEVEL: warning`, a warning and no failing
exit, and template v0.3.0 with `LEVEL: error`. Without `--no-renames`, git would report a
moved fixture as a rename, which `--diff-filter=AM` leaves out. Dependabot's branches
(`dependabot/`) are exempt from the first step, since Dependabot writes no CHANGELOG
entry (the family session, 2026-10-26, confirmed at the merge; the merge gates'
Dependabot rule).

## Core 0.3.0 (session `family`)

The family review's core scope in one minor (`docs/roadmap.md` §3), one PR at a time
under the sdk-core lock, then the release PR. Each PR merged with a merge commit, so its
own commits are on `main` too; all six merged on 2026-10-27, between 14:52 and 16:08
UTC. Before them, sdk-core#26 (`chore/gates-sdk-gates`, merge commit `9d7ff47`) pointed
`gates.yml` at the renamed gates repository; it ships in 0.3.0 as well.

| PR | sdk-core | What | ADR | Conventions | Merge commit on `main` |
| --- | --- | --- | --- | --- | --- |
| 0 | #27 `feature/deletions-no-consumer` | the deletions with no consumer (C1 to C5): `xippios.core.config` and `pydantic-settings`, the sync `Client`, `derive`, `limiter=` and the recorder's overrides, page and cursor paging; the export lists cut from 113 entries (98 names) to 81 (69), `BODY_LIMIT`, `error_from_response`, `parse_retry_after` and `ResultCap` exported from `xippios.core`; core's `.claude/settings.json` allows `gh pr merge --auto` | ADR-0002 and ADR-0015 amendments; ADR-0004, ADR-0009, ADR-0012 lines | 1.16 | `5bab785a39b504ab89603747f02e99aec7f3e180` |
| 1 | #28 `feature/gateway-module` | C14, `xippios.core.data_gov` (`Gateway`, one `QuotaPolicy` per process for the key); C6, the slimmed `QuotaPolicy` (one cap, `pause_cap`; a plain `install`; no reset-header formats, no `mark_spent`) | ADR-0009, ADR-0010, ADR-0015 amendments; ADR-0016 line | 1.17 | `2a98d7d8aabdaa505853fd27dfa1680983aa745f` |
| 2 | #29 `feature/bulk-downloads` | C15 by ADR-0019: `download` and `Downloaded`, `decode_text`, `decode_csv`, `cache_max_bytes`, the adapters skipping `BULK_TASKS`, the recorder's `max_bytes=`; C10, one credential rule in `xippios.core.redaction`. Its merge commit is the pin for a new source that starts on the gateway module and the downloads (the roadmap's pin rule) | ADR-0019 amendment; ADR-0004, ADR-0005, ADR-0013 lines | 1.18 | `787b60cab89918a3ef7946065ba02e6bc5f20f9e` |
| 3 | #30 `feature/packaged-answers` | ADR-0022's code: `published_at_naive`, unknown fields refused, `None` filters left out of `meta.request`; C13, `PackagedList`, `matches`, `closest`, `UnknownCode`; `get_answer`; `dump_upstream`. Its merge commit is the first that carries ADR-0022's code, the re-pin before a new source's reference-data PR | ADR-0022 amendment; ADR-0004, ADR-0012, ADR-0015 lines | 1.19 | `6fcdbf64ce51961b77b9377f48c724503aa4ab63` |
| 4 | #31 `feature/renderer-and-plugin-guard` | C7, `render_enums`; C11, the network guard on the pools; the cache clearing, the live run's quota summary, the argument check, the resume hint, payload-free parse failures; the workflow hardening of §13 and `publish.yml`'s comment. Its merge commit is the last tree that holds the code that moves to sdk-cashctrl | ADR-0008 and ADR-0018 (f) amendments; ADR-0013, ADR-0014, ADR-0016 lines | 1.20 | `cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff` |
| 5 | #32 `feature/cashctrl-moves-out` | C8 and C9 by ADR-0024: tenants, the tenant lock, `assert_write_tools` and the recorder's host placeholder, encoded matching, JSON verify and `rewrite` leave core; the plain verify, the neutral binary-body text, the family check with ten tests | ADR-0024, superseding ADR-0014 in part; ADR-0005, ADR-0013, ADR-0017, ADR-0019, ADR-0023 lines | 1.21 | `f906f2791c6f566b80aa0459500542d5d735e23f` |
| Release | `chore/release-0.3.0` | version 0.3.0; the CHANGELOG's `[0.3.0]` section, breaking changes first, with the test-line count and the Hand-apply list per source; README install lines `~=0.3.0`; this section and "Adopting core 0.3.0" | — | — | — |

The release PR changes only the subset of conventions §12. Its merge runs `publish.yml`,
which tags `v0.3.0` on the merge commit and waits at `pypi` for Johannes's approval; the
recovery path is the one under "Core 0.2.1". Template v0.3.0 tags with it
(`docs/roadmap.md` §3). The test suite counts 6,830 lines at the release PR's base,
against the family review's target of about 4,500 to 5,000; the lead of the CHANGELOG's
`[0.3.0]` section says where the lines went.

## Adopting core 0.3.0

Each source adopts core 0.3.0, and template v0.3.0 once it is tagged, in one adoption
PR, a `chore/template-update*` PR, before its next release (conventions §12 and §15,
ADR-0018), with `/adopt-release`; the reviewer judges it against the definition of
done's Adoption PR block and nothing else. The rules of ADR-0019 and ADR-0022, and the
renderer rule of conventions 1.20, bind a source from this adoption (conventions, header
of 1.21). Pre-filled below from the CHANGELOG's `[0.3.0]` section, whose Hand-apply list
names the files and the changed texts, and from the family review's per-source items;
the adoption PR confirms every item against the source as it is then. A source that has
not adopted core 0.2.1 by then carries "Adopting core 0.2.1" into the same PR, since the
update from its template release brings v0.2.1's and v0.2.2's changes too, as the
template's CHANGELOG says for a repository still on v0.2.0.

### Every source

- Item 1, core floor: `core_version=0.3.0`, so `xippios-core~=0.3.0` and its `[mcp]`,
  `[http]` and `[testing]` extras likewise, from PyPI, with no git pin left in
  `[tool.uv.sources]` (`core_git_ref` `''`) and `uv.lock` updated. Core no longer
  depends on `pydantic-settings`: a source that imports it declares it itself.
- Item 2, `copier update` to template v0.3.0 once it is tagged; its CHANGELOG lists what
  it renders and its own Hand-apply, the one-time `CLAUDE.md` split among them. Until it
  is tagged, the core adoption goes first, item 2 unticked with that reason, and the
  template update follows in its own `chore/template-update*` PR, judged against the
  items it touches (§15).
- Items 3 and 4, the local helpers each core change replaced, deleted with their tests,
  and the core change named for each in the PR description:
  - the api.data.gov gateway block of `_client.py` (`API_KEY_ENV`, the module's
    `policy`, `_URL`, `_gateway_error`, `_over_rate_limit`, the gateway's branches of
    `classify`, `auth`) → `xippios.core.data_gov.Gateway` (C14): psd, esr, gats;
  - the `PackagedList` class and `packaged_values` of `params.py`, `_packaged` and
    `_packaged_meta` of `tasks.py` → `xippios.core.PackagedList` (C13): psd, esr, gats,
    and comtrade's `_packaged_meta`;
  - `_matches` → `matches` (C13): psd, esr, gats, comtrade; psd's `_closest` →
    `closest`, which gats calls behind its three-letter pass;
  - the local `UnknownCode` of `errors.py` → `xippios.core.UnknownCode` (ADR-0022,
    amendment): psd, esr, gats;
  - `upstream_record` in `scripts/refresh_reference.py` → `UpstreamModel.dump_upstream`:
    psd, esr, gats, and comtrade's `_columns`; psd's `write(...)` and comtrade's
    `_write_table` → `PackagedList.write`;
  - gats's `(records, stored_at)` wrappers with `_client.stored_at`, and comtrade's
    `get()` with `decode_json()` for its cached `list_commodities` →
    `AsyncClient.get_answer` (ADR-0015, decision 5);
  - `render_str_enums` and `render_int_enums`, with the refusal of a value list and an
    id list together and `--render-only`'s refusal of lists fetched on different days
    (psd, esr, gats) and comtrade's per-class docstring rewrite → one `render_enums`
    call (C7);
  - comtrade's `empty_reference_cache` and gats's autouse cache-clearing fixture → the
    plugin's cache clearing (ADR-0013, amendment 2026-10-27);
  - the `ImportError` guard around `ResultCap` (nass, psd, esr, gats) → `from
    xippios.core import ResultCap`.
- What core does not provide stays the source's, named in the PR description (§15 item
  4): esr's integer-nearest `_closest`; gats's three-letter pass, `_nearest` and
  `_sharing_digits`; cashctrl's tenants, lock, write-server test and recorder extras
  (ADR-0024, below).
- Item 5, unchanged: a test that asserts a limiter wait or a quota pause is marked
  `rate_limited`, and one that asserts key resolution has a module-level
  `placeholder_api_key` that pins nothing (ADR-0013, ADR-0015). `Gateway.policy` is a
  `QuotaPolicy` like any other, so a test that asserts its pause or its refusal is
  marked `rate_limited` too; a test that counted on a `MemoryCache` filled by an earlier
  test finds it empty, since the plugin clears every one around each offline test.
- Item 6: `enums.py` re-rendered once with one `render_enums` call through
  `scripts/refresh_reference.py` as template v0.3.0 renders it (the template does not
  update the script once it exists, so the source ports it by hand, as the CHANGELOG's
  Hand-apply list says), then `ruff format` and `ruff check --fix`, and committed as
  formatted (ADR-0008, amendment 2026-10-27). Each class docstring becomes one line,
  "Values of ``<key>`` (fetched <date>).", which a tool's input schema shows the agent
  (conventions §8).
- Item 7, unchanged: `files = ["src", "tests", "scripts"]` under `[tool.mypy]`.
- Item 8, conventions 1.21, from 1.15 (the 0.2.1 adoption's). Binding from this
  adoption: the fixture files a PR adds or changes under 256 KiB, a cut one marked
  `truncated` (§10; template v0.3.0's fixture-cap step fails), `BULK_TASKS` (§8), the
  packaged-list file `reference/<name>.json` (§3), `published_at_naive`, the `None`
  rule, `get_answer` for a cache hit's `retrieved_at`, `matches`, the frozen and the
  period series (§4), `UnknownCode` (§5), `render_enums` and the module committed as
  formatted (§3), and what an enum's class docstring holds (§8). Changed since 1.15 as
  well: the environment read through the `EnvKeyAuth` helpers and
  `xippios.core.data_gov` for the sources behind api.data.gov (§7), the quota pause
  bounded by `pause_cap` and `install` replacing the config's hooks (§6), the credential
  rule without a bare `key` (§4), refused arguments as `InvalidRequestError` text and
  the resume hint (§8), the workflow hardening for a source's own workflows (§13), and a
  multi-tenant source carrying its tenant registry and its recorder's rewrite (§1, §3,
  §7, §8, §10).
- Item 9: `CHANGELOG.md` has a line under Unreleased naming core 0.3.0, the template
  release adopted (v0.3.0, or the one the source stays on while item 2 waits) and
  conventions 1.21.
- Every source's tests meet the texts and refusals the CHANGELOG's Hand-apply list names
  under "Every source": the credential rule, unknown `ResultMeta` fields, refused tool
  arguments, parse failures.
- With the adoption, the family review's per-source cleanup assigned to it: the result
  cap's prose leaves the task docstrings, since `MCP_CAPS` and the cap's note carry it
  (ADR-0016, conventions §8).

### sdk-usda-nass

- Items 3 and 4: the `ImportError` guard around `ResultCap` in `tasks.py` → `from
  xippios.core import ResultCap`.
- ADR-0022, rule 1 (the family review's item for nass): the value files in `reference/`
  become packaged-list files, converted without network: `endpoint` `get_param_values`
  where nass wrote "reference", its `derived_from` into `note`, and
  `condition_categories` and `progress_stages` in files of their own names with `param:
  "unit_desc"` and `endpoint: "api_GET"`. The list tasks read them with
  `PackagedList.load`, still return strings, and take their `meta` from
  `packaged.meta(SOURCE, request=...)`: `endpoint` the list's operation, `retrieved_at`
  its `fetched`, `vintage` `None`. `published_at` stays empty: Quick Stats publishes no
  release time.
- The dead `get_counts` mounts in its tests go, as the family review assigned them to
  this adoption.
- The credential rule: nothing; its `QueryKeyAuth("key", ...)` registers `key`, so every
  envelope and recording keeps `key=REDACTED`.
- Item 6: `enums.py` through `render_enums`; its script calls `render_str_enums` today.

### sdk-comtrade

On `>=0.1.0` and template v0.1.5 on 2026-10-27: its 0.2.0 adoption
(`chore/template-update-v0.2.0`) and "Adopting core 0.2.1" come first or into the same
PR.

- Items 3 and 4: `_packaged_meta` and `_matches` in `tasks.py` → `packaged.meta(SOURCE,
  request=...)` and `matches`; the cached `list_commodities` → `client.get_answer(...)`
  for its `retrieved_at`, instead of `get()` and `decode_json()`; `_columns` and
  `_write_table` in `scripts/refresh_reference.py` → `PackagedList(...).write(path)`
  with the records from `dump_upstream()`; the per-class docstring rewrite →
  `render_enums(..., fetched={name: date, ...})`, its notes into the packaged list's
  `note`; `empty_reference_cache` in `tests/conftest.py` → the plugin's cache clearing.
- ADR-0022 and C13 (the family review's item for comtrade): the value files and the CSV
  tables with `reference/tables.json` become packaged-list files, converted without
  network: `endpoint` `files/v1/app/reference/<file>.json`, its `origin` → `endpoint`,
  its `note` and `exceptions` into `note`; `meta.vintage` is `None` and
  `meta.retrieved_at` the list's `fetched`, and the docstrings and tests that say
  otherwise change.
- The snapshot count of packaged lists (38) → structure checks.
- `.claude/commands/refresh-reference-data.md`: its ruff step and its note on the
  renderer's layout go, since the script runs ruff.
- Unchanged: `QuotaPolicy(limit_header=None, remaining_header=None, window=86400,
  spent=...)` from its 0.2.0 adoption (`spent=` stays), and `auth=None` per call for its
  keyless reference files.

### sdk-usda-psd

- Items 3 and 4: the gateway block of `_client.py` → `gateway = Gateway(SOURCE)`,
  `classify` keeping psd's empty 404 after `gateway.classify(response)`, `config =
  gateway.install(ClientConfig(...))`, `auth=gateway.auth`; `PackagedList` and
  `packaged_values` in `params.py` → `PackagedList.load(PACKAGE, name)`, `_closest` →
  `closest(value, codes)`; the local `UnknownCode` → `xippios.core.UnknownCode` with
  `reason=` and `source=SOURCE`; `_packaged`, `_packaged_meta` and `_matches` →
  `packaged.parse`, `packaged.meta` and `matches`; in `scripts/refresh_reference.py`,
  `upstream_record` → `dump_upstream`, `write(...)` → `PackagedList.write`, the two
  renderers and both refusals → one `render_enums`; the `ResultCap` guard.
- Its tests: `tests/test_client.py`'s wiring test without `policy.reset_header`, a
  `retry_after` read through the client bracketed with `CLOCK_SLACK`, the refusal before
  sending with `source == "api.data.gov"`; the `UnknownCode` texts; `{"search": None}` →
  `{}`; the list tasks' `meta.vintage` and `meta.retrieved_at`; the snapshot count (42)
  → structure checks.
- Item 5: the tests its 0.2.0 adoption marked `rate_limited` (a pause, a refusal without
  sending) now meet `Gateway.policy`.
- Item 6: `AttributeId`, `UnitId` and its string enums through one `render_enums` call.
- Item 8: `CLAUDE.md`'s rate-limit row names `pause_cap` and `xippios.core.data_gov`;
  `get_time_series` already states its ceiling and its skipped market years (conventions
  §4), so nothing changes there.

### sdk-cashctrl

What leaves core comes to cashctrl (ADR-0024; the family review's C8 and C9). It copies
the code from `cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff`, the merge commit of
sdk-core#31 on `main`, the last tree that holds it (sdk-core#32 removed it):

- `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/tenants.py` —
  `Tenants` and `list_task`, as a module of its own; `client_for` keeps its shape, and
  the replaced client it drops without closing stays so until cashctrl decides
  otherwise.
- `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/mcp/server.py` —
  the lock pieces, `TenantLock`'s validation of the parameter and the tenant,
  `_only_the_locked_tenant` and `_lock_sentence`, for a lock that is a wrapper binding
  `org` on its tools, no middleware (C8; ADR-0014's decision 7 binds it no longer);
  `_lock_middleware`, `_declares`, `_refusal`, `_check_lock` and `_defaulted` have no
  part in it.
- `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/testing/adapters.py`
  — `assert_write_tools` with `_tool_names` and `_serves`, extended with a check that
  `confirm` is the last parameter.
- `git show cb8ecdf379c04522e5f1dcd91ea5e8bdfa1fb3ff:src/xippios/core/testing/scrub.py`
  — the host placeholder (`Scrub.host`, its checks and the host forms),
  `_plain_or_encoded`, the JSON verify (`_json_strings`, `_strings`) and `rewrite`, into
  `scripts/record_fixture.py` as a step of its own on the `Fixture` that
  `fixture_from_response` returns, before its one write (ADR-0024, decision 4).
- The tests, at the same commit: `tests/test_tenants.py`, `tests/mcp/test_lock.py`, and
  the moved parts of `tests/testing/test_adapters.py`, `tests/testing/test_scrub.py`,
  `tests/testing/test_fixtures.py` and `tests/testing/test_record_replay.py`.

Then, by the CHANGELOG's Hand-apply list:

- `_client.py`, `tasks.py`, `_cli.py`, `mcp.py`, `mcp_write.py` import the copies
  instead of `xippios.core.tenants` and `xippios.core.mcp.TenantLock`, and pass no
  `tenant_lock=` to `build_server`; `tests/test_org_lock.py` follows the wrapper (its
  refusal texts and instructions sentence change with it) and `tests/test_registry.py`
  tests the package's own registry; `scripts/record_fixture.py` passes
  `Scrub(secrets=[...])` to core and runs its own step, and
  `tests/test_record_fixture.py` meets the recorder's own verify and core's neutral
  binary-body text; `CLAUDE.md` ("Organisations", "How to record a fixture") describes
  the registry, `list_organisations`, the `--org` lock and the recorder's checks as the
  package's own.
- The write server: the family check no longer tests it.
  `test_the_write_server_serves_write_tasks_only` calls the copied `assert_write_tools`;
  where the 0.2.1 adoption deleted it with `tests/test_adapters.py`, as the family check
  then made it, this adoption puts it back in a test file of cashctrl's own.
- Unchanged: every task's `ResultMeta(tenant=org)` (`ResultMeta.tenant` stays, ADR-0024,
  decision 2), its `REDACTED` imports, the `confirm` check and the loopback rule.
  `BODY_LIMIT` and `error_from_response` may come from `xippios.core`; `_cli.py`'s
  docstring names `xippios.core.mcp.server.quiet_request_logging`.
- Its tests: a capped note of an offset-paged list ends `; resume with start=<n>`.
- Item 8: conventions 1.21's §1, §3, §7, §8 and §10, the per-tenant variables as its own
  scheme, the rewrite by key and the tenant registry its own, the write server's rules
  unchanged, core's plain verify.

### sdk-usda-esr

- Items 3 and 4: the gateway block of `_client.py` → `gateway = Gateway(SOURCE)`,
  `classify` keeping esr's 400 after `gateway.classify(response)`; `PackagedList` and
  `packaged_values` in `params.py` → `PackagedList.load` (its integer-nearest `_closest`
  stays its own); the local `UnknownCode` → `xippios.core.UnknownCode`; `_packaged`,
  `_packaged_meta` and `_matches`; in `scripts/refresh_reference.py`, `upstream_record`
  → `dump_upstream` and the two renderers and both refusals → one `render_enums`; the
  `ResultCap` guard.
- ADR-0022, rule 2 (the family review's item for esr): `published_at` from its naive
  release times with `published_at_naive=published_at is not None`, `vintage` keeping
  the release text as upstream prints it.
- Its tests: as psd's for the gateway, the `UnknownCode` texts and the list tasks'
  `meta`.
- Item 8: `CLAUDE.md`'s rate-limit row names `pause_cap` and `xippios.core.data_gov`.

### sdk-usda-gats

- Items 3 and 4: the gateway block of `_client.py` → `gateway = Gateway(SOURCE)`;
  `PackagedList` and `packaged_values` in `params.py` → `PackagedList.load` (its
  three-letter pass, `_nearest` and `_sharing_digits` stay its own, in front of
  `closest`); the local `UnknownCode` → `xippios.core.UnknownCode`, its example codes as
  `hint=` only when `closest` is empty; `_packaged`, `_packaged_meta` and `_matches`;
  the five wrappers in `api/` that return `(records, stored_at)` →
  `client.get_answer(path)`, and `_client.stored_at` goes (the family review's item for
  gats); the autouse cache-clearing fixture of `tests/test_client.py` → the plugin's; in
  `scripts/refresh_reference.py`, `upstream_record` → `dump_upstream` and the two
  renderers and both refusals → one `render_enums`; the `ResultCap` guard.
- ADR-0022, rule 2: `published_at` with `published_at_naive`, as for esr; the census
  series need nothing, since they already refuse a range with an unreleased month with
  `NotFoundError` (ADR-0022, amendment).
- Its tests: as psd's for the gateway; the 429 test of `get_census_export_series`
  brackets `retry_after` with `CLOCK_SLACK`, since it is read through the client.
- Item 8: `CLAUDE.md`'s rate-limit row names `pause_cap` and `xippios.core.data_gov`.

## Standing human gates

Every `pypi` approval (a merged release PR tags itself through `publish.yml`; until a
repository's workflow does, its tag comes from Johannes, conventions §12); the merge of
every PR except an adoption (`chore/template-update*`) or `chore/release-*` PR of merge
class `auto`, which a session sets to auto-merge after the reviewer's `ready` (ADR-0018,
amendment (e)); new API keys and org secrets; changes to `docs/conventions.md`; repository
creation (approved at the prompt); the decisions asked as an interview before each work
package.
