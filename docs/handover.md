# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2, and 2026-10-25 with the state after the core 0.2.0 release PR.

## State

Done: WSL2 distro, user johan, toolchain (uv, copier, pre-commit, gh, direnv), folder tree
`~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code permissions, Cursor workspace;
GitHub org ruleset `sdk-main-protection` (PR + `ci` check on `main` for `sdk-*`); repos
`sdk-core`, `sdk-template`, `.github` created, topics set, `pypi` environments with
required reviewer `jdidaskalu`; PyPI account `xippios`.

- **`sdk-core`**: 0.1.0 on PyPI since 2026-10-22. 0.2.0, what the first four sources
  taught core (below), is merged with its release PR, `chore/release-0.2.0`: version
  0.2.0 and the CHANGELOG's `[0.2.0]` section, dated 2026-10-25. The tag `v0.2.0` and
  the approval of its `pypi` run are Johannes's and still to come.
- **`sdk-template`**: v0.1.5 tagged. Generated repositories depend on `xippios-core` from
  PyPI.
- **Sources**: `sdk-usda-nass` (the pilot), `sdk-comtrade` and `sdk-usda-psd` are built
  on core 0.1.0 from PyPI. `sdk-cashctrl` already adopted `Tenants`, `TenantLock`,
  `Scrub` and the plugin's guarantees on a git pin of core 863a443 (sdk-cashctrl#7,
  a835da4, 2026-10-24). Each adopts 0.2.0 as "Adopting core 0.2.0" below lists.
  `sdk-usda-esr` and `sdk-usda-gats` are briefed and start from `QuotaPolicy`
  (ADR-0015).

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
| F | #20 `feature/reference` | ruff-clean ASCII enum rendering, `render_int_enums`, `id_name_pairs` | ADR-0008 amendment | 1.12 |
| G | #21 `docs/adoption-and-hygiene` | §15 adoption checklist and the definition of done's Adoption PR block, adoption PRs auto-merged, the one-minor core bound and the 0.x rule (§11, §12), `InvalidRequestError` wording (§5), `Fetched` as a UTC time, HTML tables, vendor snapshots, personal identifiers out of task projections (§3, §4), CI runs pre-commit, docstring examples on `xippios.usda.nass`, the `RateLimit` docstring | ADR-0017, ADR-0018; ADR-0003 and ADR-0007 amendments | 1.13 |
| Release | `chore/release-0.2.0` | version 0.2.0; the CHANGELOG's `[0.2.0]` section, breaking changes first; "Adopting core 0.2.0" below | — | — |

ADR-0017 is a rule for sources: nothing in core implements it. The release PR merged
through auto-merge after the reviewer's `ready` (ADR-0018). The gates that remain are
Johannes's: he tags `v0.2.0` on `main`, which runs `publish.yml` (CI, a check that the
tag matches the version in `pyproject.toml`, the build), and approves its run in the
environment `pypi`. A source adopts 0.2.0 from PyPI once it is there.

## Adopting core 0.2.0

Each source adopts core 0.2.0, and the sdk-template release that goes with it, in one
adoption PR, a `chore/template-update*` PR, before its next release (conventions §12 and
§15, ADR-0018). Its description is the §15 checklist, ticked; the reviewer judges it
against the definition of done's Adoption PR block and nothing else, and it auto-merges
after the reviewer's `ready`. Below, the checklist is pre-filled from the ADRs'
consequences, the CHANGELOG's `[0.2.0]` section and each source's `main` on 2026-10-25:
each local workaround a source deletes with the core change that replaced it (§15 item
3), and what it declares or marks (item 5). The adoption PR confirms every item against
the source as it is then.

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
  sorted, one name per line (ADR-0008 amendment).
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
    docstring, `/refresh-reference-data`) → gone.
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
- Item 6: `AttributeId` and `UnitId` re-rendered through `render_int_enums`.
- Item 8: `MCP_CAPS = {"list_countries": ResultCap(max_rows=300)}` in `tasks.py`, so all
  251 countries reach an agent, the United States included (ADR-0016); `Fetched` as a
  UTC time where it records the UTC date.

### sdk-comtrade

- Deletes (item 3):
  - `reference_client`, the second, keyless client in `_client.py` → the one `client`
    with `auth=None` for the reference files (ADR-0015); `REFERENCE_CACHE` can stay as
    that client's cache, narrowed to the reference paths by `cache_filter`, and a task
    answered from it sets `retrieved_at` from `xippios_cache_stored_at`, reading the
    response with `get()` and `decode_json()` (conventions §4). On the one client a
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
    sorted (ADR-0008 amendment).
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
  guarantees, and its tests use `assert_write_tools` and `mcp_call_text` already.
- Item 4, a candidate for sdk-core rather than a copy: `scripts/record_fixture.py`
  writes the fixture itself, because core's `record` writes as soon as core's verify
  passes, before a source's final check could run, and `Scrub.rewrite` does not reach
  the request URL.
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
  refused `CASHCTRL_<NAME>_SUBDOMAIN` should hold.

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
  on personal identifiers in the model scaffold (ADR-0017).
- **Sources**: each adopts core 0.2.0 and that template release as "Adopting core 0.2.0"
  lists, once both are published. Sources already published with an open bound stay as
  published and get the bound with their next release.
- **Later**: install the Claude GitHub App on the org and move to issue-driven work: one
  issue per endpoint or change, `@claude` in the issue, PR arrives, CI gates, a human
  merges. Auto-merge waits for every required approving review, so the ruleset must
  require none for adoption and release PRs to merge on `ci` alone (ADR-0018).

## Standing human gates

Every tag and every `pypi` approval; the merge of every PR except `chore/template-update*`
and `chore/release-*`, which a session sets to auto-merge after the reviewer's `ready`;
new API keys and org secrets; changes to `docs/conventions.md`; repository creation
(approved at the prompt); the decisions asked as an interview before each work package.
