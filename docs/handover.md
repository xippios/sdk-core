# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2, 2026-10-25 with the state after the core 0.2.0 release PR, 2026-10-26 with core 0.2.1, the release train and the family check (the sections from "Core 0.2.1" on), 2026-10-27 with `sdk-core`'s state line at the core 0.2.1 release PR, and 2026-10-27 at the core 0.3.0 release PR (the State block, the session model, the sections from "Core 0.3.0" on, and notes where 0.3.0 changed an earlier line), 2026-11-13, when the process of the work left this file (the session model, the standing gates, the plan for issue-driven work and the switch of the retired gates) and the documents' own rules stayed, 2026-11-17 at the core 0.3.2 release PR (the State block's `sdk-core` line), and 2026-11-18 at the core 0.4.0 release PR (the State block's `sdk-core` line and the sections from "Core 0.4.0" on).

## State

Done: WSL2 distro, user johan, toolchain (uv, copier, pre-commit, gh, direnv), folder tree
`~/github/sdk/`, family `CLAUDE.md`, `.envrc`, Claude Code permissions, Cursor workspace;
GitHub org ruleset `sdk-main-protection` (PR + `ci` check on `main` for `sdk-*`); repos
`sdk-core`, `sdk-template`, `.github` (renamed `sdk-gates` on 2026-10-27) created, topics
set, `pypi` environments with required reviewer `jdidaskalu`; PyPI account `xippios`.

- **`sdk-core`**: 0.1.0 on PyPI since 2026-10-22 and 0.2.0, what the first four sources
  taught core (below), since 2026-10-25, both tagged by Johannes; 0.2.1 since
  2026-10-27, the first release whose release PR tagged itself (`publish.yml` tagged
  `v0.2.1` on the merge commit, Johannes approved the `pypi` run). 0.3.0 (below), the
  family review's core scope, the code of ADR-0019 and ADR-0022, and ADR-0024, since
  2026-10-27, released the same way. 0.3.1 since 2026-11-13, documents only: conventions
  1.22 to 1.27, the index of the 27 decision records and the changelog's fragments. 0.3.2
  since 2026-11-17 keeps the code of 0.3.0 but for a docstring: the repository's own
  `.github/` names nothing that stands around it. 0.4.0 (below) gives the host xippios-mcp
  the loopback option, the package contract and the multi-tenant kit, and takes into core
  what two or more sources kept as copies. Its release PR's merge tags `v0.4.0` and waits
  at `pypi` for the maintainer's approval.
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
  needs and moves to `~=0.3.0` in its one v0.3.0 adoption. (2026-10-28: sdk-eurostat
  moved to `~=0.3.0` from PyPI with no re-pin, in
  https://github.com/xippios/sdk-eurostat/pull/3 on 2026-10-27, and its v0.3.0
  adoption, https://github.com/xippios/sdk-eurostat/pull/8, changed no bound.)

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
| C | #17 `feature/tenants` | `Tenants`, tenant lock, CLI option hooks, `ResultMeta.tenant`, the `confirm` check (`Tenants` and the lock moved to sdk-cashctrl in 0.3.0, ADR-0024) | ADR-0014 | 1.9 |
| D | #18 `feature/client-policy` | request hooks, `QuotaPolicy`, retries shaped by `classify`, `auth=` per request | ADR-0015; ADR-0010's "core today" note resolved | 1.10 |
| E | #19 `feature/mcp-result-cap` | per-tool result caps, a cap note that promises no filter | ADR-0016 | 1.11 |
| F | #20 `feature/reference` | ruff-clean ASCII enum rendering, `render_int_enums`, `id_name_pairs` (both renderers replaced by `render_enums` in 0.3.0) | ADR-0008 amendment | 1.12 |
| G | #21 `docs/adoption-and-hygiene` | §15 adoption checklist and the definition of done's Adoption PR block, adoption PRs auto-merged, the one-minor core bound and the 0.x rule (§11, §12), `InvalidRequestError` wording (§5), `Fetched` as a UTC time, HTML tables, vendor snapshots, personal identifiers out of task projections (§3, §4), CI runs pre-commit, docstring examples on `xippios.usda.nass`, the `RateLimit` docstring | ADR-0017, ADR-0018; ADR-0003 and ADR-0007 amendments | 1.13 |
| Release | `chore/release-0.2.0` | version 0.2.0; the CHANGELOG's `[0.2.0]` section, breaking changes first; "Adopting core 0.2.0" below | — | — |

ADR-0017 is a rule for sources: nothing in core implements it. The release PR merged
through auto-merge after the reviewer's `ready` (ADR-0018). 0.2.0 was the last release
tagged by hand. From 0.2.1 on the release train runs it (conventions §12): the release
PR's merge runs `publish.yml`, which tags `vX.Y.Z` from `pyproject.toml` on the merge
commit, runs CI, checks the tag against the version and builds; the human gate is a
maintainer's approval of the run in the environment `pypi`. A source adopts a release
from PyPI once it is there.

## Adopting core 0.2.0

Each source adopts core 0.2.0, and the sdk-template release that goes with it, in one
adoption PR before its next release (conventions §12 and §15, ADR-0018); the reviewer
judges it against the definition of done's Adoption PR block and nothing else. Below,
the checklist is pre-filled from the ADRs' consequences, the CHANGELOG's `[0.2.0]`
section and each source's `main` on 2026-10-25:
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

## Core 0.2.1 (session `family`)

Step 0 of the roadmap, before 0.3.0: one feature PR and its release PR.

| PR | sdk-core | What | ADR | Conventions |
| --- | --- | --- | --- | --- |
| | `feature/release-train-and-family-tests` | the release train (`publish.yml` tags from `pyproject.toml`, `ci.yml` without its push trigger, actions pinned by SHA), `gates.yml` switched off, `xippios.core.testing.family`, the shared test helpers (C12), anchored sdist patterns, the live workflow and the family check in §10, adoption auto-merge by merge class in §15, the roadmap sentences | ADR-0009 amendment; ADR-0013 amendment; ADR-0018 amendments (b), (c), (e) | 1.15 |
| Release | `chore/release-0.2.1` | version 0.2.1; the CHANGELOG's `[0.2.1]` section; README install lines `~=0.2.1`; the first release PR that tags itself | — | — |

The release PR changes only the subset of conventions §12. Its merge runs `publish.yml`,
which tags `v0.2.1` on the merge commit and waits at `pypi`; the first run also shows
whether the environment's deployment-branch policy "protected branches only" admits a
ruleset-protected `main`, and if it does not, a maintainer sets the policy to `main` and
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
a maintainer rejects its `pypi` deployment and the release is re-done as a patch. A
release is not merged while another release run is waiting.

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
  check no longer tests the write server (ADR-0024): cashctrl moves that test to a test
  file of its own, with its own copy of `assert_write_tools`, as "Adopting core 0.3.0"
  says.
- `anyio_backend` in `tests/conftest.py` → the plugin's.

### Template v0.2.1: the two family checks that are CI steps

The excerpt below is template v0.2.1's, kept as the record of that release. From v0.3.0
the CHANGELOG step exempts a release and Dependabot only, no longer an adoption, whose
entry conventions §15 item 9 asks for; from v0.3.2 the fixture-cap step reads renames as
the paragraph after the excerpt says.

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
exit, and template v0.3.0 with `LEVEL: error`. From template v0.3.2 the step diffs with
`--find-renames=100%`: a fixture a PR only moves, its content unchanged, is a rename,
which `--diff-filter=AM` leaves out, so it passes, and one moved and changed is listed as
added, so one moved and grown is judged (conventions §10). Dependabot's branches
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

Each source adopts core 0.3.0 and template v0.3.0, which tags with it (`docs/roadmap.md`
§3), in one adoption PR before its next release (conventions §12 and §15, ADR-0018),
with `/adopt-release`; the reviewer judges it against the definition of done's Adoption
PR block and nothing else. The rules of
ADR-0019 and ADR-0022, and the renderer rule of conventions 1.20, bind a source from
this adoption (conventions, header of 1.21). Pre-filled below from the CHANGELOG's
`[0.3.0]` section, whose Hand-apply list names the files and the changed texts, and from
the family review's per-source items; the adoption PR confirms every item against the
source as it is then. A source that has not adopted core 0.2.1 by then carries "Adopting
core 0.2.1" into the same PR, since the update from its template release brings v0.2.1's
and v0.2.2's changes too, as the template's CHANGELOG says for a repository still on
v0.2.0.

### Every source

- Item 1, core floor: `core_version=0.3.0`, so `xippios-core~=0.3.0` and its `[mcp]`,
  `[http]` and `[testing]` extras likewise, from PyPI, with no git pin left in
  `[tool.uv.sources]` (`core_git_ref` `''`) and `uv.lock` updated. Core no longer
  depends on `pydantic-settings`: a source that imports it declares it itself.
- Item 2, `copier update` to template v0.3.0 in the same adoption PR: the template tags
  with core 0.3.0, and a source waits for that tag. Its CHANGELOG lists what it renders
  and its own Hand-apply, the one-time `CLAUDE.md` split among them.
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
- Item 8, conventions 1.22 (an existing source applies §2's name rule to its wrappers
  and fixture directories in one PR of its own, right after its core 0.3.0 adoption and
  never inside the adoption PR). The existing sources apply 1.13 on 2026-10-27
  (comtrade, until its 0.2.0 adoption, an earlier version): one that adopts 0.2.1 first
  goes from 1.15; one that carries "Adopting core 0.2.1" into this PR goes from 1.13 and
  takes the rules changed in 1.14 and 1.15 as well (the CHANGELOG's `[0.2.1]` section;
  "Adopting core 0.2.1", item 8). Binding from this adoption: the fixture files a PR
  adds or changes under 256 KiB, a cut one marked `truncated` (§10; template v0.3.0's
  fixture-cap step fails), `BULK_TASKS` (§8), the packaged-list file
  `reference/<name>.json` (§3), `published_at_naive`, the `None` rule, `get_answer` for
  a cache hit's `retrieved_at`, `matches`, the frozen and the period series (§4),
  `UnknownCode` (§5), `render_enums` and the module committed as formatted (§3), and
  what an enum's class docstring holds (§8). Changed since 1.15 as well, for every
  source: the environment read through the `EnvKeyAuth` helpers and
  `xippios.core.data_gov` for the sources behind api.data.gov (§7), the quota pause
  bounded by `pause_cap` and `install` replacing the config's hooks (§6), the credential
  rule without a bare `key` (§4), refused arguments as `InvalidRequestError` text and
  the resume hint (§8), the workflow hardening for a source's own workflows (§13), and a
  multi-tenant source carrying its tenant registry and its recorder's rewrite (§1, §3,
  §7, §8, §10).
- Item 9: `CHANGELOG.md` has a line under Unreleased naming core 0.3.0, template v0.3.0
  and conventions 1.22 (an existing source applies §2's name rule to its wrappers and
  fixture directories in one PR of its own, right after its core 0.3.0 adoption and
  never inside the adoption PR).
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
  otherwise. (2026-10-29: cashctrl decided it in its adoption,
  https://github.com/xippios/sdk-cashctrl/pull/13: its copy closes the replaced client
  through `aclose()`, queue rows 24 (b) and 118.)
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
- The write server: the family check no longer tests it. cashctrl is on template v0.2.0,
  so the update to v0.3.0 deletes `tests/test_adapters.py`;
  `test_the_write_server_serves_write_tasks_only` moves to a test file of cashctrl's
  own, such as `tests/test_tasks_write.py`, and calls the copied `assert_write_tools`.
  (2026-10-29: cashctrl stays on template v0.2.2, its last tag before v0.3.0, and runs
  no `copier update` after it, conventions §15's route for a source frozen on a template
  tag (queue row 118): its adoption, https://github.com/xippios/sdk-cashctrl/pull/13,
  updated it to v0.2.2, which deleted `tests/test_adapters.py`, and
  https://github.com/xippios/sdk-cashctrl/pull/18 hand-applied template v0.3.0's
  changes.)
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

## Core 0.4.0

What the host xippios-mcp waits for, the read server's loopback option, the package
contract and the multi-tenant kit's return, and what two or more sources kept as copies,
moved into core in one minor with the rules the conventions lacked
(https://github.com/xippios/sdk-core/issues/240, its scope decided in
https://github.com/xippios/sdk-core/issues/234). Eighteen steps and two follow-ups, one PR
each, merged with a merge commit between 2026-11-17 23:48 and 2026-11-18 11:08 UTC, so
their own commits are on `main` too; follow-up 4.1 merged last, after step 18. Each step
adds its lettered points to one amendment of 2026-11-18 per record it changes, and the
conventions keep the version line 1.27 until step 18 raises it to 1.28. The ADR column
names the records as each step amended them: step 18 restates the fifteen that then
carried three amendments or a reversal as ADR-0028 to ADR-0042, and each old number leads
through `docs/adr.md` to its successor.

| Step | sdk-core | What | ADR | Conventions | Merge commit on `main` |
| --- | --- | --- | --- | --- | --- |
| 1 | #267 `step/0.4.0-1` | `xippios.core.mcp` exports `register_tasks`, `is_write_server`, `quiet_request_logging` and `tool_functions`; `build_server(..., loopback_only=True)` with `is_loopback_only` and `LOOPBACK_HOSTS`; the `httpx2` and `httpcore2` loggers quieted | ADR-0013, ADR-0025, ADR-0026 amendments | §8, §10 | `1a8ef3894c3ae6c7ea2221b002937c4d773be612` |
| 2 | #273 `step/0.4.0-2` | an error answer flagged `isError`; an argument a tool does not declare refused; an `Annotated` parameter's metadata kept in both adapters; a route's refused argument as problem details | ADR-0007, ADR-0014, ADR-0026 amendments | §8, §9 | `6192aea379e95a91c533a9873edd288f5e4f5045` |
| 3 | #277 `step/0.4.0-3` | `Tenants` and `list_task` back in core, in `xippios.core.tenants` | ADR-0014, ADR-0024, ADR-0025 amendments | — | `049b2e61cf6d59cd6807280b3497a07e5b29ab58` |
| 4 | #284 `step/0.4.0-4` | `TenantLock`, `bind_tasks`, `tenant_instructions`, `serve_tenants`, `assert_write_tools` and `keep_reserved_tenants` back in core | ADR-0014, ADR-0024, ADR-0025 amendments | §7, §8 | `a06cd60f9eb80b60abba62705056710310bfabfa` |
| 4.1 | #303 `step/0.4.0-4.1` | one tenant per call: `Tenants(..., param=...)` required, `bind_tasks` refusing a task without it but the tenant list and `NO_TENANT_TASKS`, the family check's `test_family_tasks_take_one_tenant` | ADR-0036, decision 13, with decisions 1, 7 and 8; ADR-0014, ADR-0024, ADR-0025 amendments | §7, §8 | `96b16f841add49efe01c4fd32205cc1adcdc0ab3` |
| 5 | #288 `step/0.4.0-5` | the package contract's types, `EnvVar` in `xippios.core.contract` and `ToolSet` in `xippios.core.mcp.toolset`; `build_server(tool_set)`, `register_tasks(server, tool_set)`, `option_defaults()` | ADR-0026 amendment | §7, §8 | `5276d12f9df68fd84a343ac724ff6aaf9d15364e` |
| 6 | #266 `step/0.4.0-6` | the cache stores a 200 once `get_answer` decoded it; a miss carries its stored time; the generic `Answer` | ADR-0015 amendment | §4, §6 | `be6ae3a1c5eac90b4fce2359d867a1ae0e0a53ad` |
| 7 | #275 `step/0.4.0-7` | the client's auth to the base URL's origin only, no quota for `auth=None` or another origin; the gateway's own answers and `NoDataForYear`; a signed link through `scrub_url`; `register_data_name` | ADR-0009, ADR-0015, ADR-0019 amendments | §4, §6, §7, §10 | `f07f7ac4690592a1155cd96d232fed5f4000c2cb` |
| 8 | #283 `step/0.4.0-8` | `RenewingBearerAuth` and `BearerToken`; the plugin pins every credential a token request reads | ADR-0013, ADR-0025 amendments | §7, §10 | `1d47167ced544fc0a6b63ded8d79fa916149ad27` |
| 9 | #282 `step/0.4.0-9` | `post_json` and `delete_json`; `decode_csv` of an open text stream; `download` refuses a bad `dest` with `InvalidRequestError` and states the mode `0600` of the file it writes; a sync task hands `SystemExit` back | ADR-0015, ADR-0019 amendments | §6 | `c79582349f289a653564e16b721118a1a0826adc` |
| 10 | #268 `step/0.4.0-10` | `write_fixture` and `fixture_text` exported, the `sample` mark; `array_key=` and `keep="last"`; the response headers that only identify a request dropped | ADR-0019, ADR-0020, ADR-0024 amendments | §10 | `8e3b9b3d85c2716b9228c87c12afb92e9b9644ec` |
| 11 | #278 `step/0.4.0-11` | a recording sends once and reads up to `max_read_bytes`; `Scrub` reads the values to scrub from a login's or a refresh's answer; `sent_bodies`; `request_description` | ADR-0005, ADR-0013, ADR-0015, ADR-0019, ADR-0024 amendments | §5, §10 | `dac2d7219150f53edeebe4721c468f8c2582e1a2` |
| 12 | #265 `step/0.4.0-12` | `cap_result` cuts the rows of a model that holds one list; a cut whose first row alone passes the byte cap names no resume offset | ADR-0016 amendment | §8 | `0a8fbe7de1ebfb547008c5950566e95cbfdab072` |
| 13 | #285 `step/0.4.0-13` | `UnknownCode`'s text and `closest(cutoff=)`; `nearest`; `render_enums` keeps a camelCase hump; `parse_decimal` gives `None` for NaN and the infinities; an error naming another task names its tool | ADR-0008, ADR-0022 amendments | §5, §8 | `1f378bd52317a1b7d24b13ae6f348f96ce0dfebf` |
| 14 | #269 `step/0.4.0-14` | six rules of layers, the snapshot and hosts | ADR-0001, ADR-0003, ADR-0008, ADR-0010, ADR-0020 amendments | §2, §3, §4, §6 | `06163c6974bb91b1ae04ae785eddc95f27569651` |
| 15 | #274 `step/0.4.0-15` | seven rules of release metadata and paging | ADR-0012, ADR-0020, ADR-0022 amendments | §4, §6 | `e8e228ed701dbf29fa4f528ec2da3f49129f47ff` |
| 15.1 | #296 `step/0.4.0-15.1` | the `meta.endpoint` of a file from the publisher's origin or mirror and of a file named after its dataset; the registry's name | ADR-0010, ADR-0020, ADR-0025 amendments | §4, §6 | `3ae28163941d44c7c555342984e042b71c96b1f4` |
| 16 | #286 `step/0.4.0-16` | seven rules of refusals, caps and fixtures; the review checklist and the definition of done | ADR-0003, ADR-0007, ADR-0016, ADR-0018, ADR-0020, ADR-0022 amendments | §5, §8, §10 | `d0787db74c2e198febef7fd865447f27c9061433` |
| 17 | #289 `step/0.4.0-17` | a source's adoption of a core minor takes a minor; what binds the host; the `_TOKEN` suffix; the secret scan skips a cut or sampled body's sha256 line | ADR-0005, ADR-0009, ADR-0018, ADR-0026 amendments | header, §7, §10, §12, §15 | `2ce4f9680bf4e919a40601b2d15c83dd9e696956` |
| 18 | #297 `step/0.4.0-18` | fifteen records restated as ADR-0028 to ADR-0042; the documents and docstrings cite `ADR-NNNN, decision N` | ADR-0028 to ADR-0042, superseding ADR-0003, ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0018, ADR-0019, ADR-0022, ADR-0024 | 1.28 | `10d56f96b55ad86f21d1ed24a038f89557876869` |
| Release | `chore/release-0.4.0` | version 0.4.0 and the lock; the CHANGELOG's `[0.4.0]` section, assembled from the fragments, with its 29 Hand-apply notes; `CLAUDE.md`'s layout; this section and "Adopting core 0.4.0" | — | — | — |

Before the release PR, one branch in sdk-google-mail
(https://github.com/xippios/sdk-google-mail/issues/19) and one in sdk-cashctrl
(https://github.com/xippios/sdk-cashctrl/issues/61) pin core's `main`, delete what core
then provides and run their tests, the trial that
https://github.com/xippios/sdk-core/issues/242 decided; each opens no PR before core's
tag. The release PR changes only what conventions §12 lets a release PR change. Its merge
runs `publish.yml`, which tags `v0.4.0` on the merge commit and waits at `pypi` for the
maintainer's approval; the recovery path is the one under "Core 0.2.1". sdk-template
0.4.0 follows the tag and renders the package contract
(https://github.com/xippios/sdk-template/issues/159).

## Adopting core 0.4.0

Each source adopts core 0.4.0 and sdk-template 0.4.0 together, once, in one adoption PR
before its next release (https://github.com/xippios/sdk-template/issues/159; conventions
§12 and §15, ADR-0039); the reviewer judges it against the definition of done's Adoption
PR block and nothing else. A source's adoption of a core minor takes a minor (conventions
§12, ADR-0039, decision 1). A dependency adopts before its dependent, sdk-usda-esmis
before sdk-usda-wasde (conventions §12), and the host adopts after the sources
(https://github.com/xippios/xippios-mcp/issues/21). Pre-filled below from the 29
Hand-apply notes of the CHANGELOG's `[0.4.0]` section, which give each file's lines and
the texts that change, and checked against each repository's `main` on 2026-11-18; each
item cites the issue its note's bullet answers. The adoption PR confirms every item
against the source as it is then.

### Every source

- Item 1, core floor: `core_version=0.4.0`, so `xippios-core~=0.4.0` and its `[mcp]`,
  `[http]` and `[testing]` extras likewise, from PyPI, with no git pin left in
  `[tool.uv.sources]` and `uv.lock` updated; all read `~=0.3.0` today.
- Item 2, `copier update` to sdk-template 0.4.0: `mcp.py`'s `build()` returns a `ToolSet`
  of `tool_functions(tasks)` with `caps=getattr(tasks, "MCP_CAPS", None)`, its
  instructions, version and option hooks, `server = build_server(build())`, and `main`
  takes the tool set's hooks, so a host serves what the entry point serves
  (https://github.com/xippios/sdk-core/issues/245; ADR-0026, amendment 2026-11-18, points c
  and d). `_client.py`, the source's own, declares the variables it reads as `EnvVar`
  entries, each with `secret=` and `required=`, in the list the template renders beside
  `SOURCE` (https://github.com/xippios/sdk-template/issues/81), since a host reads the
  list.
- Items 3 and 4, the copies each core change replaced, deleted with their tests, and the
  core change named for each in the PR description; per source below:
  - the multi-tenant kit, `Tenants`, `list_task`, the binding lock, the serve command,
    `assert_write_tools` and the demo-only strip → core's
    (https://github.com/xippios/sdk-core/issues/166; ADR-0042, decision 6): cashctrl,
    google-mail;
  - a login's or a refresh's own bearer flow → `RenewingBearerAuth`
    (https://github.com/xippios/sdk-core/issues/156): faostat, google-mail;
  - a write's `request` and its own decode → `post_json` and `delete_json`
    (https://github.com/xippios/sdk-core/issues/178): google-mail, cashctrl, faostat;
  - a description of the request of its own → `request_description`
    (https://github.com/xippios/sdk-core/issues/62): eurostat, x, google-mail, faostat,
    esmis;
  - the nearest-integer pass → `nearest` (https://github.com/xippios/sdk-core/issues/107):
    esr, gats;
  - `NoDataForYear` with its `classify` branch → `xippios.core.data_gov.NoDataForYear`
    through `Gateway(SOURCE, data_path=...)`
    (https://github.com/xippios/sdk-core/issues/106): psd, esr;
  - a pair of a value and its `retrieved_at` → `Answer[T]`
    (https://github.com/xippios/sdk-core/issues/123): comtrade's `ReferenceFile`, nass's
    `ParamValues`;
  - a CSV reader of its own over an open stream → `decode_csv`
    (https://github.com/xippios/sdk-core/issues/89): eurostat, faostat;
  - a fixture writer of its own → `write_fixture` and `fixture_text`
    (https://github.com/xippios/sdk-core/issues/125): cashctrl, google-mail, x, wasde;
  - the `class_names[id_field]` line of `scripts/refresh_reference.py` → `render_enums`'
    default class name (https://github.com/xippios/sdk-core/issues/95): esr, gats, psd,
    cashctrl, faostat, google-mail, x, and comtrade's `class_names=` argument.
- What core does not provide stays the source's, named in the PR description (§15 item
  4): the client built for one attempt that a recorder sends through to rewrite a fixture
  before its write, in sdk-cashctrl's, sdk-google-mail's and sdk-x's
  `scripts/record_fixture.py` and sdk-usda-wasde's `scripts/cut_sample.py`, until
  https://github.com/xippios/sdk-core/issues/281 decides it (ADR-0037, decision 6); the
  audited entries of the bodies stored base64 in `.secrets.baseline`, sdk-eurostat's
  three, sdk-faostat's one and sdk-usda-wasde's two, until
  https://github.com/xippios/sdk-core/issues/290 lets the scan tell them from a text body.
- Item 5, unchanged: the plugin pins every credential a `RenewingBearerAuth` reads through
  `credential`, so `xippios_placeholder_key_envs` names each variable a token request
  reads, as sdk-faostat's and sdk-google-mail's do today
  (https://github.com/xippios/sdk-core/issues/156).
- Item 6: `enums.py` re-rendered once; `render_enums`' default class name gives every class
  name a source commits, sdk-usda-nass's `ProgressStage` and `ConditionCategory` kept in its
  `class_names`, so the re-render writes the same module
  (https://github.com/xippios/sdk-core/issues/95).
- Item 7, unchanged: `files = ["src", "tests", "scripts"]` under `[tool.mypy]`.
- Item 8, conventions 1.28: every rule changed since the version the source last applied
  holds in it; among them an error that names another task names that task's MCP tool too
  (§8, https://github.com/xippios/sdk-core/issues/111), in nine sources below, and one
  tenant per call for a source with a `Tenants` registry, which the family check holds
  every task to (§7, https://github.com/xippios/sdk-core/issues/298,
  https://github.com/xippios/sdk-core/issues/299). The source's own files that cite a
  restated record cite its successor as `ADR-NNNN, decision N`, per source below; an old
  number still resolves through core's index
  (https://github.com/xippios/sdk-core/pull/297, Consumers).
- Item 9: the adoption's fragment under `changelog/` names core 0.4.0, sdk-template 0.4.0
  and conventions 1.28.
- A fixture recorded on core 0.4.0 carries none of the response headers that only identify
  a request, `x-amz-cf-id`, `x-request-id` and `x-transaction-id` among them, so it adds no
  audited entry for them (https://github.com/xippios/sdk-core/issues/161).

### sdk-cashctrl

The trial branch of https://github.com/xippios/sdk-cashctrl/issues/61, which pins core's
`main` and deletes the copies below, becomes the adoption PR once core's tag and
sdk-template 0.4.0 are out.

- Deletes (item 3), the kit's copies (https://github.com/xippios/sdk-core/issues/166):
  - `src/xippios/cashctrl/_tenants.py` and `tests/test_tenants.py` → `Tenants` and
    `list_task` from `xippios.core`, the close of a replaced client included;
  - `src/xippios/cashctrl/_org_lock.py` → `TenantLock(TENANTS, name,
    noun="organisation")`, `bind_tasks` and `tenant_instructions`, the same sentence;
  - `src/xippios/cashctrl/_cli.py` → `serve_tenants(server, build, TENANTS,
    noun="organisation", check=check_org)`, its subdomain check moved to `check_org` in
    `_client.py`;
  - in `tests/test_tasks_write.py`, the copy of `assert_write_tools` with `_confirm_problem`,
    `_tool_names`, `_serves` and the helper's own tests → `xippios.core.testing`;
  - in `tests/conftest.py`, `DEMO_PAIR` and `_strip_productive_organisations` →
    `keep_reserved_tenants(TENANTS)`, then `os.environ.pop("CASHCTRL_API_KEY", None)`:
    core strips by the registry's scheme, so it removes `CASHCTRL_ORGS` and every
    organisation's pair but demo's and keeps a variable the scheme names for no
    organisation;
  - in `tests/test_org_lock.py`, the tests of the lock and the command, which core's
    `tests/test_tenant_lock.py` and `tests/mcp/test_cli.py` hold; what stays tests the
    package's own wiring;
  - in `scripts/record_fixture.py`, `to_json` and `_CUT_MARKS` → `fixture_text`, its write
    → `write_fixture` (https://github.com/xippios/sdk-core/issues/125);
  - in `src/xippios/cashctrl/api/_form.py`, `post_form`'s `request` and its decode →
    `post_json(path, data=fields, headers=...)`
    (https://github.com/xippios/sdk-core/issues/178).
- Changes:
  - `_client.py`: `Tenants` from `xippios.core`, `param="org",` after
    `list_var="CASHCTRL_ORGS",` in `TENANTS = Tenants(...)`, which core's `Tenants`
    requires and the family check holds each of the 46 tasks to
    (https://github.com/xippios/sdk-core/issues/298,
    https://github.com/xippios/sdk-core/issues/299), and `check_org(org)` in `__all__`;
  - `tasks.py`: `list_task` from `xippios.core`;
  - `mcp.py` and `mcp_write.py`: `build(lock: TenantLock | None = None)` returns
    `ToolSet(SOURCE, bind_tasks(tool_functions(...), lock), ...)`, `read_only=False` for the
    write server, `server = build_server(build())`, the write server named
    `xippios-cashctrl-write`, and the entry points `serve_tenants(...)`
    (https://github.com/xippios/sdk-core/issues/166,
    https://github.com/xippios/sdk-core/issues/245);
  - `tasks_write.py`: the messages that name `list_order_categories`, `create_person`,
    `update_order` and `list_accounts` name each task's tool beside it, and the tests that
    pin a message follow (https://github.com/xippios/sdk-core/issues/111);
  - `api/_download.py`: `check_dest` stays, since `download` streams into a temporary file
    of its own, and its docstrings and `download`'s drop "where core's `download` raises
    `ValueError`" (https://github.com/xippios/sdk-core/issues/152), though the trial's issue
    listed the check among the deletions;
  - `scripts/refresh_reference.py`: the `class_names[id_field]` line, its dict and its
    argument dropped (https://github.com/xippios/sdk-core/issues/95);
  - its tests: in `tests/test_org_lock.py` a call that still passes `org` is refused,
    `org: Not an argument of this tool; it takes note`
    (https://github.com/xippios/sdk-core/issues/84), and the `xippios-cashctrl: error:`
    assertions name the entry point (https://github.com/xippios/sdk-core/issues/167); in
    `tests/test_tasks_write.py` `sent_body` → `sent_bodies(route)[-1]`
    (https://github.com/xippios/sdk-core/issues/183); in `tests/test_tasks.py` the route's
    refusal has the title `InvalidRequestError`
    (https://github.com/xippios/sdk-core/issues/66) and `get_report_data` over its cap has
    its rows cut and its other fields whole (https://github.com/xippios/sdk-core/issues/131);
    `tests/test_registry.py` and `tests/test_tasks.py` name core's registry and list task;
  - `CLAUDE.md`: Organisations, the `--org` bullet, Demo only, the Layout and
    `assert_write_tools` name core's kit; the sentence that a call that still passes `org`
    is not refused goes; a report's result has its rows cut
    (https://github.com/xippios/sdk-core/issues/166,
    https://github.com/xippios/sdk-core/issues/84,
    https://github.com/xippios/sdk-core/issues/131).
- Stays: the one-attempt client of `scripts/record_fixture.py`
  (https://github.com/xippios/sdk-core/issues/281).
- Cite a restated record: `README.md`, `scripts/record_fixture.py`, `api/_download.py`,
  `models.py` and nine test files, beside the copies the adoption deletes
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-google-mail

The trial branch of https://github.com/xippios/sdk-google-mail/issues/19, which pins
core's `main` and deletes the copies below, becomes the adoption PR once core's tag and
sdk-template 0.4.0 are out.

- Deletes (item 3):
  - `src/xippios/google/mail/_tenants.py` → `Tenants` and `list_task` from `xippios.core`,
    `list_task`'s `source=` included (https://github.com/xippios/sdk-core/issues/166);
  - `src/xippios/google/mail/_account_lock.py` → `TenantLock(TENANTS, name)`, `bind_tasks`
    and `tenant_instructions(..., bound=...)` (https://github.com/xippios/sdk-core/issues/166);
  - `src/xippios/google/mail/_cli.py` → `serve_tenants(server, build, TENANTS,
    check=check_account)`, its refresh token check moved to `check_account` in
    `_client.py`; its copy of the loopback hosts and `REMOTE_REFUSAL` go, since core's
    `main` holds the read server to loopback, refusing a remote `--host` in its own words
    after the account check (https://github.com/xippios/sdk-core/issues/166,
    https://github.com/xippios/sdk-core/issues/167);
  - in `_auth.py`, `RefreshTokenAuth`'s own flow: it becomes a `RenewingBearerAuth`, and
    `_credential`, `EXPIRY_MARGIN`, `requires_response_body`, `_access_token`,
    `_lapses_at`, `reset`, `_current`, `apply` and `auth_flow` go; `keep` splits into
    `read_token` and `token_refused` (https://github.com/xippios/sdk-core/issues/156);
  - in `tests/test_tasks_write.py`, the copy of `assert_write_tools` with its helpers and
    its own tests → `xippios.core.testing` (https://github.com/xippios/sdk-core/issues/166);
  - in `tests/conftest.py`, `DEMO_TOKEN`, `_ACCOUNT_TOKEN` and `_strip_productive_accounts`
    → `keep_reserved_tenants(TENANTS)`, the same strip
    (https://github.com/xippios/sdk-core/issues/166);
  - in `tests/test_account_lock.py`, the tests of the lock and the command, and
    `test_the_loopback_rule_comes_before_the_account`
    (https://github.com/xippios/sdk-core/issues/166);
  - in `scripts/record_fixture.py`, `to_json` and `_CUT_MARKS` → `fixture_text` and
    `write_fixture` (https://github.com/xippios/sdk-core/issues/125), and the answer's
    tokens added to `Scrub(secrets=...)` → `Scrub(secrets=secret_values(),
    response_secrets=answer_tokens)` (https://github.com/xippios/sdk-core/issues/164);
  - in `api/drafts_create.py`, `api/messages_send.py`, `api/messages_modify.py` and
    `api/messages_trash.py`, the `request` and `decode_json` → `post_json`, and in
    `api/drafts_delete.py` the `request("DELETE", ...)` → `delete_json`, which returns
    `None` for the 204 (https://github.com/xippios/sdk-core/issues/178).
- Changes:
  - `_client.py`: `Tenants` from `xippios.core`, its first argument `SOURCE,
    var_prefix="GOOGLE"` for `"google"`, so the variables keep the shared prefix and its
    errors name `google-mail` (ADR-0025, amendment 2026-11-18, point b;
    https://github.com/xippios/sdk-core/issues/279), and `param="account",` after
    `list_var="GOOGLE_ACCOUNTS",`, which the family check holds each of the 11 tasks to
    (https://github.com/xippios/sdk-core/issues/298,
    https://github.com/xippios/sdk-core/issues/299); `check_account(account)`; the inline
    `where` → `request_description(response)`, and in `_auth.py` the same
    (https://github.com/xippios/sdk-core/issues/62);
  - `tasks.py`: `list_task` from `xippios.core` without `source=SOURCE`, and the refusal
    naming `list_messages` names its tool (https://github.com/xippios/sdk-core/issues/111);
  - `mcp.py`: `build(lock: TenantLock | None = None)` returns `ToolSet(SOURCE,
    bind_tasks(tool_functions(tasks), lock), ..., loopback_only=True)`, the read server held
    to loopback by core, bound or not (ADR-0025, D-a), `server = build_server(build())`, the
    entry point `serve_tenants(...)`; `mcp_write.py` likewise with `read_only=False`
    (https://github.com/xippios/sdk-core/issues/245,
    https://github.com/xippios/sdk-core/issues/167);
  - `scripts/refresh_reference.py`: the `class_names[id_field]` line, its dict and its
    argument dropped (https://github.com/xippios/sdk-core/issues/95);
  - its tests: `tests/test_auth.py` reads `auth.margin`, `tests/test_tasks.py` calls
    `auth.read_token`, `tests/conftest.py`'s comment names `RenewingBearerAuth.credential`
    (https://github.com/xippios/sdk-core/issues/156); in `tests/test_account_lock.py` a
    call that still passes `account` is refused
    (https://github.com/xippios/sdk-core/issues/84) and the `xippios-google-mail: error:`
    assertions name the entry point (https://github.com/xippios/sdk-core/issues/167);
    `tests/test_tasks_write.py`, `tests/test_record_fixture.py` and `tests/test_consent.py`
    read `sent_bodies` (https://github.com/xippios/sdk-core/issues/183);
  - `CLAUDE.md`: the Layout drops `_tenants.py`, `_account_lock.py` and `_cli.py`; the
    strip, `assert_write_tools` and the lock are core's; `RefreshTokenAuth` is a subclass
    of core's `RenewingBearerAuth` (https://github.com/xippios/sdk-core/issues/166,
    https://github.com/xippios/sdk-core/issues/156).
- Stays: the one-attempt client of `scripts/record_fixture.py`
  (https://github.com/xippios/sdk-core/issues/281).
- Cite a restated record: `scripts/record_fixture.py`, `_account_lock.py`, `_cli.py`,
  `_tenants.py`, `mcp_write.py`, `models.py`, `tasks_write.py` and three test files
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-faostat

- Changes, items 3 and 4:
  - `_client.py`: `LoginAuth` becomes a `RenewingBearerAuth` that keeps what is
    FAOSTAT's, with `renew_on = REFUSED`, since FAOSTAT refuses a bearer with a 401 or a
    403 (ADR-0025, amendment 2026-11-18, point c); `_credential`, `EXPIRY_MARGIN`,
    `reset`, `_current`, `_keep`, `_sign`, `async_auth_flow` and `sync_auth_flow` go
    (https://github.com/xippios/sdk-core/issues/156); the inline request descriptions →
    `request_description(response)` (https://github.com/xippios/sdk-core/issues/62); the
    refusal naming `list_domains` names its tool
    (https://github.com/xippios/sdk-core/issues/111);
  - `api/auth_login.py`: `request` and `decode_json` → `post_json(LOGIN_PATH, data=...,
    auth=None)` (https://github.com/xippios/sdk-core/issues/178);
  - `parse/bulk_csv.py`: the table's rows through `decode_csv(io.TextIOWrapper(...))`, its
    header read apart for the check of a column named twice; its errors name the member
    alone, as `tests/test_parse.py` then expects
    (https://github.com/xippios/sdk-core/issues/89);
  - `tasks.py`: the refusal naming `get_data` names its tool
    (https://github.com/xippios/sdk-core/issues/111);
  - `tests/test_client.py` reads `timed.margin`, and `CLAUDE.md` names core's
    `RenewingBearerAuth` and `token_refused` (https://github.com/xippios/sdk-core/issues/156);
  - `scripts/refresh_reference.py`: the `class_names[id_field]` line, its dict and its
    argument dropped (https://github.com/xippios/sdk-core/issues/95).
- Stays: its audited binary body in `.secrets.baseline`
  (https://github.com/xippios/sdk-core/issues/290).
- Once it runs on core 0.4.0: its first fixture recorded then, which carries no
  `x-amz-cf-id` and adds no baseline entry, is the second proof of
  https://github.com/xippios/sdk-core/issues/161, which waits for this adoption.
- Cite a restated record: `docs/handover.md`, `models.py`, `params.py`,
  `reference/README.md`, `tests/fixtures/files/README.md`, `tests/test_tasks.py`
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-x

- Changes, items 3 and 4:
  - `_client.py`: `register_data_name("next_token")` and
    `register_data_name("pagination_token")` at import, so `meta.request`, a fixture and
    replay keep X's cursors (https://github.com/xippios/sdk-core/issues/184); `_where` →
    `request_description` (https://github.com/xippios/sdk-core/issues/62);
  - `tasks.py`: the module docstring and the `Args:` of the five paged tasks say that
    `meta.request` keeps the token as sent (https://github.com/xippios/sdk-core/issues/184);
  - its tests: `tests/test_tasks.py`, `tests/test_api.py` and
    `tests/test_probe_accounts.py` assert the token as sent, and their comparisons with the
    two page-2 fixtures, which recorded `next_token=REDACTED`, leave `next_token` out until
    a PR records them again (https://github.com/xippios/sdk-core/issues/184);
  - paging: a page past its byte bound has its rows cut, keeps its other fields and keeps
    its `next_token`, which points past the rows the cut left out, where it came back as a
    note and a preview that lost it; a page that must return whole keeps its byte bound of
    its own, 128,000 bytes for the four post tools (ADR-0038, decision 4;
    https://github.com/xippios/sdk-core/issues/131). `tests/test_tasks.py`'s `count_posts`
    over its cap and `CLAUDE.md`'s MCP caps paragraph say so;
  - `scripts/record_fixture.py`: `to_json` and `_CUT_MARKS` → `fixture_text` and
    `write_fixture` (https://github.com/xippios/sdk-core/issues/125);
  - `scripts/refresh_reference.py`: the `class_names[id_field]` line, its dict and its
    argument dropped (https://github.com/xippios/sdk-core/issues/95);
  - `CLAUDE.md`: the fixtures' paragraph and the task layer's `meta` say that the cursors
    are data (https://github.com/xippios/sdk-core/issues/184).
- Stays: the one-attempt client of `scripts/record_fixture.py`
  (https://github.com/xippios/sdk-core/issues/281).
- Cite a restated record: `scripts/probe_accounts.py`, `scripts/record_fixture.py`,
  `models.py`, `tests/test_client.py`, `tests/test_record_fixture.py`
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-eurostat

- Changes, items 3 and 4:
  - `_client.py`: `_where` and its five uses → `request_description`
    (https://github.com/xippios/sdk-core/issues/62);
  - `parse/sdmx_csv.py`: `_gzip_records` yields from `decode_csv(text, source=SOURCE)`, and
    the module docstring says both files' rows go through it
    (https://github.com/xippios/sdk-core/issues/89);
  - `tasks.py`: `_target` goes, and `download_dataset_async` and `download_trade_async` pass
    `Path(dest)`, which core refuses with the same two texts; `api/sdmx.py`'s `Raises:`
    names `InvalidRequestError` (https://github.com/xippios/sdk-core/issues/152); the
    refusals naming its tasks name their tools
    (https://github.com/xippios/sdk-core/issues/111);
  - its tests: `tests/test_tasks.py`'s unknown product ends with `UnknownCode`'s new tail
    (https://github.com/xippios/sdk-core/issues/111), and its route refusal asserts
    problem details (https://github.com/xippios/sdk-core/issues/66).
- Stays: its three audited binary bodies (https://github.com/xippios/sdk-core/issues/290).
- Cite a restated record: `docs/handover.md`, `api/__init__.py`, `api/catalogue.py`,
  `api/sdmx.py`, `errors.py`, `models.py`, `params.py`, `parse/sdmx_csv.py`,
  `reference/README.md`, `tests/test_client.py`, `tests/test_tasks.py`
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-comtrade

- Changes, items 3 and 4:
  - `api/reference.py`: `ReferenceFile[T]` goes, `reference_rows` returns
    `Answer[list[dict[str, Any]]]` from `get_answer(..., parse=..., endpoint=...)` and
    `reference` an `Answer[list[M]]`; `api/__init__.py` drops `ReferenceFile`; `tasks.py`,
    `scripts/refresh_reference.py`, `tests/test_tasks.py` and `tests/test_live.py` read
    `.payload` and `.retrieved_at` (https://github.com/xippios/sdk-core/issues/123);
  - `errors.py` and `params.py`: `QueryTooLarge`'s advice and the reasons and refusals
    that name a task name its tool beside it, and `tests/test_tasks.py`'s `REFUSED_756`
    and `REFUSED_C16` end with `UnknownCode`'s new tail
    (https://github.com/xippios/sdk-core/issues/111);
  - `_client.py`'s comment, the docstrings of `api/get_comtrade_releases.py` and
    `api/get_world_share.py`, and `CLAUDE.md`: a spent key quota holds no keyless call back
    (https://github.com/xippios/sdk-core/issues/163);
  - `scripts/refresh_reference.py`: `class_names=class_names` leaves the `render_enums`
    call, the dict kept for its order (https://github.com/xippios/sdk-core/issues/95).
- Cite a restated record: `api/reference.py`, `models.py`, `params.py`,
  `reference/README.md`, `tests/test_tasks.py`
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-psd

- Deletes (item 3): `src/xippios/usda/psd/errors.py`, `NoDataForYear` being all it holds →
  `xippios.core.data_gov.NoDataForYear`, which `Gateway(SOURCE, data_path=DATA_PATH)` maps;
  `classify`'s empty-404 branch keeps its plain `NotFoundError`, `tasks.py` imports
  core's class and `_absent` passes `source=exc.source`, and `tests/test_client.py`,
  `tests/test_tasks.py`, `tests/test_slices.py` and `CLAUDE.md` follow
  (https://github.com/xippios/sdk-core/issues/106).
- Changes: `params.py`'s messages that name a task name its tool beside it, and
  `tests/test_params.py` meets `UnknownCode`'s new tail
  (https://github.com/xippios/sdk-core/issues/111); `scripts/refresh_reference.py` drops
  the `class_names[id_field]` line, its dict and its argument
  (https://github.com/xippios/sdk-core/issues/95).
- Cite a restated record: `errors.py`, `models.py` and six test files
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-esr

- Deletes (item 3): `src/xippios/usda/esr/errors.py` → `xippios.core.data_gov.NoDataForYear`,
  as for psd: `_client.py`, `tasks.py`, the docstrings of `api/get_country_data.py`,
  `api/get_all_countries_data.py` and `params.py`, `tests/test_client.py`,
  `tests/test_tasks.py`, `tests/test_slices.py` and `CLAUDE.md` follow
  (https://github.com/xippios/sdk-core/issues/106); `_closest`'s first pass in
  `params.py` → `nearest(value, codes, n=2)`, its digit pass ESR's own
  (https://github.com/xippios/sdk-core/issues/107).
- Changes: the docstrings of `get_exports`, `get_latest_week` and `get_top_destinations`
  say that an empty list may be a market year not yet released
  (https://github.com/xippios/sdk-core/issues/136); `tests/test_params.py` meets
  `UnknownCode`'s new tail (https://github.com/xippios/sdk-core/issues/111);
  `scripts/refresh_reference.py` drops the `class_names[id_field]` line, its dict and its
  argument (https://github.com/xippios/sdk-core/issues/95).
- Cite a restated record: `errors.py`, `models.py`, `params.py` and six test files
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-gats

- Deletes (item 3): `_nearest` in `params.py` and its call →
  `nearest(customs_district_id, codes)`, the same three ids in the same order
  (https://github.com/xippios/sdk-core/issues/107).
- Changes: `errors.py`'s `HS6_REASON` and `params.py`'s messages that name a list task
  name its tool beside it, and `tests/test_params.py` meets `UnknownCode`'s new tail
  (https://github.com/xippios/sdk-core/issues/111); `scripts/refresh_reference.py` drops
  the `class_names[id_field]` line, its dict and its argument
  (https://github.com/xippios/sdk-core/issues/95).
- Cite a restated record: four `api/*_release_info.py` wrappers and
  `api/get_commodities.py`, `errors.py`, `models.py`, `params.py` and four test files
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-nass

- Deletes (item 3): `ParamValues` in `api/get_param_values.py` and in `api/__init__.py` →
  `Answer[list[str]]`, which `tasks.py`, `scripts/refresh_reference.py` and
  `tests/test_tasks.py` read as `.payload` and `.retrieved_at`
  (https://github.com/xippios/sdk-core/issues/123).
- Changes: `params.py`'s `_check_value` passes its own hint only when `closest` finds
  nothing (https://github.com/xippios/sdk-core/issues/111); the docstring of each task
  that fetches one year says that an empty answer may be a year not yet released
  (https://github.com/xippios/sdk-core/issues/136). Its errors name the tool already, the
  example of conventions §8.
- Cite a restated record: `README.md`, `api/get_param_values.py`, `models.py`,
  `tests/test_tasks.py` (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-esmis

- Changes: `_client.py`'s inline description → `request_description(response)`, the line
  that shows the encoded slash keeping its raw path
  (https://github.com/xippios/sdk-core/issues/62); `tasks.py`'s refusals naming
  `search_publications` and `list_releases` name their tools
  (https://github.com/xippios/sdk-core/issues/111); `scripts/refresh_reference.py`'s
  `Refused` loses the reason that a `SystemExit` stops the loop's thread, and may stay as
  the walk's refusal (https://github.com/xippios/sdk-core/issues/77).
- It adopts before sdk-usda-wasde, its dependent (conventions §12).
- Cite a restated record: `README.md`, `params.py`, `reference/README.md`,
  `tests/test_tasks.py` (https://github.com/xippios/sdk-core/pull/297).

### sdk-usda-wasde

- Item 1 also raises `xippios-usda-esmis` to the minor sdk-usda-esmis releases on core
  0.4.0 (conventions §12, §15 item 1; ADR-0021).
- Changes: `scripts/cut_sample.py` marks the replay fixture `sample` for `truncated`, writes
  the download fixtures again and writes them with `write_fixture`
  (https://github.com/xippios/sdk-core/issues/125); `parse/wasde_xml.py`'s `_value` returns
  `parse_decimal(text)` without its `is_finite()` guard
  (https://github.com/xippios/sdk-core/issues/128); `tasks.py`'s reasons and refusals that
  name a task name its tool (https://github.com/xippios/sdk-core/issues/111).
- Stays: the one-attempt client of `scripts/cut_sample.py`
  (https://github.com/xippios/sdk-core/issues/281) and its two audited binary bodies
  (https://github.com/xippios/sdk-core/issues/290).
- Cite a restated record: `README.md`, `scripts/cut_sample.py`, `_vocabulary.py`,
  `models.py`, `reference/README.md`, `tests/test_live.py`, `tests/test_tasks.py`
  (https://github.com/xippios/sdk-core/pull/297).

### xippios-mcp

The host adopts in an adoption PR of its own without `copier update`, judged against
conventions §15's items 1, 3, 4, 7, 8 and 9 (ADR-0026, amendment 2026-11-18, point e):

- Item 1: `xippios-core[mcp]` and `xippios-core[testing]` `~=0.4.0`, both `~=0.3.0` today,
  while its sources keep their `>=` floors (ADR-0026, decision 9).
- Items 3 and 4: `app.py`'s copy of `_LOOPBACK_HOSTS` → `LOOPBACK_HOSTS`, and its loopback
  check holds an endpoint with `auth: none` by `is_loopback_only`, so sdk-google-mail's
  read server is held as a write server is; `tests/test_app.py`'s
  `test_the_loopback_hosts_are_cores` goes, its loopback cases parametrized on
  `LOOPBACK_HOSTS` (https://github.com/xippios/sdk-core/issues/167); `packages.py`'s
  `is_bulk_task` from `xippios.core._tasks` → the names of `tool_functions(tasks)`, and the
  imports from `xippios.core.mcp.server` in `servers.py`, `app.py` and `cli.py` →
  `xippios.core.mcp` (https://github.com/xippios/sdk-core/issues/170).
- The package contract (https://github.com/xippios/sdk-core/issues/245): `packages.py`
  reads a package's `ToolSet` from `<path>.mcp.build()` (`mcp_write.build()`) for what it
  read by name; `servers.py` builds each endpoint's server with `build_server(tool_set)`
  and a server it builds from several with `register_tasks(server,
  dataclasses.replace(tool_set, tasks=kept, caps=cut))` and each tool set's hooks; and
  `app.py`'s `_check_mounted_once` goes. Whether the adoption PR takes the contract up or
  a later pull request of that minor does, ADR-0026, amendment 2026-11-18, point e, leaves
  open.
- Item 8: from core 0.4.0 an error answer carries `isError` beside its text (ADR-0026,
  amendment 2026-11-18, point b).
- Item 9: its fragment names core 0.4.0 and conventions 1.28; the template changes the new
  conventions version needs in the files it was scaffolded from are hand-applied and listed
  file by file in the PR description.
- Cite a restated record: `CLAUDE.md`, `README.md`, `src/xippios/mcp/app.py`, `cli.py`,
  `config.py`, `packages.py`, `tests/conftest.py`, `ci.yml` and `publish.yml`
  (https://github.com/xippios/sdk-core/pull/297).

### sdk-template

sdk-template 0.4.0 follows core's tag and renders what the sources' adoption takes
(https://github.com/xippios/sdk-template/issues/159):

- `core_version=0.4.0`, the bound of item 1.
- The package contract: `mcp.py.jinja` builds `build()`'s `ToolSet` and `server =
  build_server(build())` and gives `main` the tool set's hooks, where it passes
  `[getattr(tasks, name) for name in tasks.__all__]` to `build_server` today, and
  `_client.py.jinja` renders the list of `EnvVar` entries beside `SOURCE`
  (https://github.com/xippios/sdk-core/issues/245,
  https://github.com/xippios/sdk-template/issues/81).
- `.pre-commit-config.yaml`, which differs from core's by step 17 alone: the secret scan's
  `--exclude-lines` rule for the sha256 line of a cut or sampled body, and the comment that
  `.copier-answers.yml` can name a key's variable
  (https://github.com/xippios/sdk-template/issues/42,
  https://github.com/xippios/sdk-core/issues/210).
- `template/scripts/refresh_reference.py.jinja` renders the `class_names[id_field]` line
  that four sources drop, which `render_enums`' default makes redundant for an id field in
  camelCase (https://github.com/xippios/sdk-core/issues/95).
- Its skeleton and its own files that cite a restated record:
  `template/CLAUDE.md.jinja`, the four `template/.claude/commands/*.md.jinja`,
  `template/.github/workflows/ci.yml`, `live.yml.jinja` and `publish.yml`,
  `template/docs/upstream/FETCHED.md.jinja`, `template/pyproject.toml.jinja`,
  `template/scripts/refresh_*.py.jinja`, the four package modules under `template/src/`
  and `template/tests/conftest.py.jinja`, and `README.md`, `CLAUDE.md`, `copier.yml`,
  `scripts/prove.sh`, `tests/test_template.py` and `.github/workflows/release.yml`
  (https://github.com/xippios/sdk-core/pull/297).
