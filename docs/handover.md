# Handover — from planning to Claude Code

Date: 2026-10-20 · Author: Johannes Didaskalu (with Claude) · Refreshed 2026-10-22 with the state after sessions 1 and 2, 2026-10-25 with the state after the core 0.2.0 release PR, 2026-10-26 with core 0.2.1, the release train and the family check (the sections from "Core 0.2.1" on), 2026-10-27 with `sdk-core`'s state line at the core 0.2.1 release PR, and 2026-10-27 at the core 0.3.0 release PR (the State block, the session model, the sections from "Core 0.3.0" on, and notes where 0.3.0 changed an earlier line), 2026-11-13, when the process of the work left this file (the session model, the standing gates, the plan for issue-driven work and the switch of the retired gates) and the documents' own rules stayed, 2026-11-17 at the core 0.3.2 release PR (the State block's `sdk-core` line), 2026-11-18 at the core 0.4.0 release PR (the State block's `sdk-core` line and the sections from "Core 0.4.0" on), and 2026-11-22 before the core 0.4.1 release PR (the State block's `sdk-core` line and the sections from "Core 0.4.1" on).

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
  what two or more sources kept as copies, since 2026-11-18, released the same way. 0.4.1
  (below) solves once in core what two or more sources solve alike, every change additive,
  so a source takes it inside its one minor.
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
| Release | `chore/release-0.4.0` | version 0.4.0 and the lock; the README's install lines and Status at 0.4.0; the CHANGELOG's `[0.4.0]` section, assembled from the fragments, with its 29 Hand-apply notes; `CLAUDE.md`'s layout; this section and "Adopting core 0.4.0" | — | — | — |

Before the release PR, one branch in sdk-google-mail
(https://github.com/xippios/sdk-google-mail/issues/19) and one in sdk-cashctrl
(https://github.com/xippios/sdk-cashctrl/issues/61) pin core's `main`, delete what core
then provides and run their tests, the trial that
https://github.com/xippios/sdk-core/issues/242 decided; each opens no PR before core's
tag. Both branches, `trial/core-0.4.0` in each repository, passed on 2026-11-18 on core's
`main` at `96b16f841add49efe01c4fd32205cc1adcdc0ab3`, the merge of the follow-up 4.1, with
no misfit and no row filed: sdk-google-mail with 313 tests passed
(https://github.com/xippios/sdk-google-mail/issues/19#issuecomment-6977372927) and
sdk-cashctrl with 1,424
(https://github.com/xippios/sdk-cashctrl/issues/61#issuecomment-6977674083).
The release PR changes only what conventions §12 lets a release PR change. Its merge
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
  - its tests: in `tests/test_org_lock.py` the test of a call that still passes `org` goes
    with the lock's tests, which core holds, and the bound read server refuses `org`
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

## Core 0.4.1

What two or more sources solve alike, solved once in core in one patch
(https://github.com/xippios/sdk-core/issues/309): the check of a code against a packaged list,
the rest of an answer that the result cap cut, the series over periods, the country an answer
is for (https://github.com/xippios/sdk-core/issues/310), the count before a query over
upstream's limit, the `since` filter, the preview of a write, the nightly comparison of a
packaged list with the live one, and the frames of the snapshot, reference and recorder
scripts, with the rules that the reviews of the sources' adoptions of 0.4.0 settled. Every
change is additive (conventions §12; ADR-0039, decision 1): every name that
`tests/test_public_surface.py` pinned at v0.4.0 stays pinned. Steps 1 to 17 and the follow-up
17.1, one PR each, merged with a merge commit between 2026-11-21 18:31 and 2026-11-22 02:10
UTC, so their own commits are on `main` too. Each step that changes a rule brings its record,
decided by its question, ADR-0043 to ADR-0057, and step 17 amends ADR-0037 and ADR-0042; the
conventions keep the version line 1.28 until step 18 raises it to 1.29.

| Step | sdk-core | What | ADR | Conventions | Merge commit on `main` |
| --- | --- | --- | --- | --- | --- |
| 1 | #360 `step/0.4.1-1` | `scripts/adr_index.py` as the organization's repositories share it, run as `python3 -I scripts/adr_index.py`; `docs/adr.md` opens each record's line with its anchor and lists the records in force first; ruff leaves the shared file alone | — | — | `a70a54ea0489821f7ecfff9bddedaf35a313c6d6` |
| 2 | #381 `step/0.4.1-2` | what the reviews of the adoptions of 0.4.0 settled: an adoption's entry names three versions and takes `breaking` or `changed`, a release rewords no entry and cites a live run on its base, three cases between the kinds of a built answer, two kinds of a source's messages that name no request | ADR-0043 | §5, §10, §12, §15 | `0fba7d8f3471c8bf8b8fe89f25c95b94eb0d2a0c` |
| 3 | #358 `step/0.4.1-3` | a live run prints the requests it sent, by host | — | — | `f36f0578e2bece55179719b164774d9c7eb9c2e5` |
| 4 | #356 `step/0.4.1-4` | the first line of `publish.yml` cites ADR-0039, decision 6 | — | — | `e043437c601b584511184a2351fadac334158e97` |
| 5 | #396 `step/0.4.1-5` | `xippios.core.testing.built_answers`, the check of a built answer's mark and its census | ADR-0049 | §10 | `25862322c859cd4eb55334f7bf5ce0546133d152` |
| 6 | #383 `step/0.4.1-6` | the family check holds `OBSERVED.md` to three rules | ADR-0044 | §3 | `88cd703e8fec70f4816c2c41b47271534ad6cd6b` |
| 7 | #384 `step/0.4.1-7` | `PackagedList.codes` and the `check` of its `PackagedCodes` | ADR-0045 | §5 | `627fd56ce06f2f16934495a54891f497aa27ee27` |
| 8 | #392 `step/0.4.1-8` | `newer_than` and `naive_time` | ADR-0052 | §4 | `345ecad12910b35d27964e0606b4751e673ea643` |
| 9 | #403 `step/0.4.1-9` | `QueryTooLarge` and `fetch_counted` | ADR-0053, with its amendment | §5 | `a30b26cb2cad184850bd5dcb34d3c5b2b80467be` |
| 10 | #404 `step/0.4.1-10` | `Ceiling` and `fetch_periods` in `xippios.core.series` | ADR-0054 | §4 | `357075594f1d708bca4194bdd53fd33c137dc2f6` |
| 11 | #395 `step/0.4.1-11` | `xippios.core.testing.live` and `assert_list_current`; the family check holds `LIVE_LISTS` and `NO_LIVE_LIST` | ADR-0055 | §10 | `5f8a005f18c97f66686d8c176dfd7907ed602abc` |
| 12 | #406 `step/0.4.1-12` | `ResultMeta.names`, `names_codes` and `UNNAMED_CODES`; the family check holds them | ADR-0056 | §4 | `605f73c2dd6dd4aea3f2a98f86b44b06ed9219a0` |
| 13 | #388 `step/0.4.1-13` | `ResultCap(paged=True)` and `ResultCap(keep="last")` | ADR-0047 | §8 | `14a99242e28ed7c36de9017f2abe1c4cb2258af0` |
| 14 | #397 `step/0.4.1-14` | what a write task's preview shows; `assert_write_tools(..., preview_reads=..., dry_run=...)` | ADR-0050 | §8 | `a4854e4542660450388528101e0fbe02820c722b` |
| 15 | #400 `step/0.4.1-15` | the reference refresh script's frame: `Listed`, `Enumeration` and `run(lists, ...)` in `xippios.core.refresh` | ADR-0051 | §3 | `bd8cff563c4f3f09e51c5efca38cb999c37f5318` |
| 16 | #386 `step/0.4.1-16` | the snapshot script's frame: `Snapshot` and `run(snapshot)` in `xippios.core.refresh` | ADR-0046 | §3 | `f086b417d5f2c6e353705a9c4664bc7d79b1161a` |
| 17 | #390 `step/0.4.1-17` | `rewrite=` on `record` and `fixture_from_response`, `send_once`, the refusal of a 1xx or a 3xx on every path | ADR-0048; ADR-0037 and ADR-0042 amendments | §3, §10 | `b25dd53c7ef507c141220c70078651807f219ecf` |
| 17.1 | #401 `step/0.4.1-17.1` | `record_task` and `record_task_sync` | ADR-0057 | §10 | `328a572bf59aa1d18b6e3bd5f9c01a7a9f505490` |

Step 18 writes this section, "Adopting core 0.4.1" and the conventions' version line 1.29
from the merged text of the steps above, and the release PR adds the rows of step 18 and of
the release. The release PR changes only what conventions §12 lets a release PR change. Its
merge runs `publish.yml`, which tags `v0.4.1` on the merge commit and waits at `pypi` for the
maintainer's approval; the recovery path is the one under "Core 0.2.1". sdk-template 0.4.1
follows the tag and renders the snapshot script and the reference refresh script that a new
source starts from on core's frames (ADR-0046 and ADR-0051, Consequences).

## Adopting core 0.4.1

Each source adopts core 0.4.1 and sdk-template 0.4.1 together, once, in the adoption PR of its
patch on core 0.4.1, after its adoption of core 0.4.0, and the patch releases with a live run
on its base (conventions §12 and §15; ADR-0043, Consequences); the reviewer judges the
adoption PR against the definition of done's Adoption PR block and nothing else. A core patch
brings no core minor, so the adoption is judged against the items of §15 that it touches and
its fragment is `changed` (§15 item 9; ADR-0043, decision 3), while a change of the source's
own that breaks its callers makes its release a minor, as sdk-comtrade's below does, and
sdk-usda-nass's and sdk-usda-gats's where their ports remove the two functions of their
ceilings that their changelogs named (§12).
The lock's move to 0.4.1 brings the family check's six new tests. The first five fail at once
on a source that does not meet them, with no release that warns first (ADR-0044, decision 4),
so the adoption PR meets them, and the sixth holds a source from its first refresh on:

- `test_family_country_codes_are_named_in_the_answer` (§4; ADR-0056): sdk-usda-psd,
  sdk-usda-gats, sdk-usda-esr, sdk-comtrade, sdk-eurostat and sdk-faostat;
- `test_family_fetched_md_lists_observed_md_in_a_row_of_its_own`,
  `test_family_observed_notes_end_with_their_probe_and_date` and
  `test_family_observed_md_cites_files_that_exist` (§3; ADR-0044): the six sources that keep
  `docs/upstream/OBSERVED.md`, sdk-usda-esmis, sdk-usda-wasde, sdk-usda-esr, sdk-cashctrl,
  sdk-faostat and sdk-eurostat;
- `test_family_every_packaged_list_is_declared_for_the_live_run` (§10; ADR-0055): the nine
  sources that package lists, sdk-comtrade, sdk-eurostat, sdk-faostat, sdk-usda-esmis,
  sdk-usda-esr, sdk-usda-gats, sdk-usda-nass, sdk-usda-psd and sdk-usda-wasde;
- `test_family_fetched_md_agrees_with_the_snapshot` (§3; ADR-0046, decision 6): every source,
  from the first run of its ported snapshot script that fetches, which writes `FETCHED.md` with
  the line that names its form. It passes a script that declares no `SNAPSHOT` and a file
  without that line, a copy's or sdk-template's stub, so the adoption PR, which fetches nothing,
  meets it as it stands.

Pre-filled below from the 19 fragments of steps 1 to 17.1, which the CHANGELOG's `[0.4.1]`
section assembles, whose Hand-apply
notes give each file, what it changes and the tests that break without it, from the records
ADR-0043 to ADR-0057 and from the Consumers of each step's PR, all read on `main` at the merge
of step 12; each item cites the issue its fragment answers. The adoption PR confirms every
item against the source as it is then. Two lists come first: the changes of the release that
a source's callers see, and the rules of conventions 1.29 that changed since 1.28. The review
checklist's item 12 holds an adoption against both
(https://github.com/xippios/sdk-core/issues/334, https://github.com/xippios/sdk-core/issues/349).
Before the release six sources ported core's `main` at
[a23bd94](https://github.com/xippios/sdk-core/commit/a23bd94f5829b6490427c31864b2a4c07f2a74f6)
on a trial branch, ran their tests offline with their copies deleted, and the parts and the notes
were corrected wherever a port had to do otherwise than they said, each correction citing its
source's trial row (https://github.com/xippios/sdk-core/issues/410,
https://github.com/xippios/sdk-core/issues/435).

### The changes that a source's callers see

Core 0.4.1 changes no answer of a source by itself: `meta.names` is left out of a dumped
answer while it is empty, and a paged cap, a cap that keeps the newest rows, the preview's
check and the new helpers act only where a source takes them up. Each change below reaches a
source's callers, through its Python API, its MCP tools or its routes, once the source takes it
up, and names the sources whose Hand-apply note takes it. Its entry is a fragment of the pull
request that brings the change, worded for the source's own tasks and citing the issue, in the
group given here by what the change does to the callers (`changelog/README.md`), and the
release takes it as the fragment reads (conventions §12; ADR-0043, decision 2). Where a
source's change does more than its entry here says, its fragment says so in the group of what
it does.

1. **The rest of a cut answer** (https://github.com/xippios/sdk-core/issues/314; ADR-0047). A
   tool whose cap is `ResultCap(paged=True)` takes the adapter's `offset`, the rows already
   shown, and every page of the tool carries its note, the last too, so an answer without a
   note is whole: the note of every page but the last ends with `; continue with offset=<n>`,
   and the last page's names its rows alone (ADR-0047, decisions 3 and 4); a cap with
   `keep="last"` shows the newest rows of a series
   ordered oldest first, and the tool's `offset` walks to older rows. It reaches the tools that
   sdk-cashctrl, sdk-comtrade, sdk-eurostat, sdk-faostat, sdk-usda-esmis, sdk-usda-esr,
   sdk-usda-gats, sdk-usda-nass and sdk-usda-psd name in `MCP_CAPS`, and none of
   sdk-google-mail's or sdk-x's (https://github.com/xippios/sdk-google-mail/issues/38,
   https://github.com/xippios/sdk-x/issues/35). Entry: under `added`, the tools that take
   `offset`, each continuation running the task again; under `changed`, the tools whose cut
   series now shows its newest rows, and the notes that named a way around the cut.
2. **The name of each country code** (https://github.com/xippios/sdk-core/issues/316,
   https://github.com/xippios/sdk-core/issues/310; ADR-0056). An answer of a task that takes a
   country, area, reporter or partner code carries `meta.names`, each such parameter's codes
   with the names that its packaged list holds, `{"country_code": {"CN": "Comoros"}}`, and a
   code its list lacks that reaches the answer unchecked withholds the answer with the list's
   refusal. It reaches the decorated tasks of sdk-usda-psd, sdk-usda-gats, sdk-usda-esr,
   sdk-comtrade and sdk-eurostat, and sdk-faostat's `get_series`. Entry: under `added`, the
   tasks whose answers name their codes; a task that sent a code unchecked, as sdk-faostat's
   `get_series` sent a code of a domain outside its five area tables
   (https://github.com/xippios/sdk-core/pull/406, Consumers), names in a fragment of its own
   the refusal that now withholds such an answer.
3. **sdk-comtrade's alpha-3 codes** (https://github.com/xippios/sdk-core/issues/375, with
   https://github.com/xippios/sdk-core/issues/316). sdk-comtrade's tasks refuse an ISO alpha-3
   code where they resolved it before the call, naming the UN Comtrade code it stands for:
   `"CHE"` is refused naming `757 (Switzerland)`, and since a value of the source's hint table
   is no code of upstream's, the refusal ends with its hint and its reason and leaves out that
   the packaged list may be out of date (ADR-0041, decision 8, and ADR-0045, decision 3, each
   amended 2026-11-22; https://github.com/xippios/sdk-core/issues/430,
   https://github.com/xippios/sdk-core/issues/440). Entry: under `breaking`, which makes
   sdk-comtrade's release a minor (§12), as the decision of
   https://github.com/xippios/sdk-core/issues/375 has it.
4. **The refusal after one count** (https://github.com/xippios/sdk-core/issues/317; ADR-0053,
   amended by https://github.com/xippios/sdk-core/issues/405). A query over upstream's per-call
   record limit is refused with core's `QueryTooLarge`, an `InvalidRequestError` whose message
   core words from the count, the limit, what narrows the query and, for upstream's refusal that
   a source's `classify` maps, the request it names; a count of 0 answers with the task's empty
   answer and sends no data request. It reaches sdk-comtrade's `get_data`, whose answer may
   carry the count as `meta.total`, sdk-usda-nass's `get_data` and its `classify` of upstream's
   413, and the tasks of sdk-eurostat and sdk-faostat where their patches take the error or the
   runner (https://github.com/xippios/sdk-eurostat/issues/53,
   https://github.com/xippios/sdk-faostat/issues/35). Entry: under `changed`, the refusal's
   wording, and sdk-comtrade's `meta.total`. sdk-comtrade's patch deletes its own
   `QueryTooLarge` from `xippios.comtrade.errors`, a name of its `__all__` that its README
   names, so a caller's import of it fails and the class to catch is core's
   `xippios.core.QueryTooLarge` (https://github.com/xippios/sdk-core/issues/317; ADR-0053,
   Consequences): that removal takes an entry of its own under `breaking`, in the minor of its
   alpha-3 codes (§12).
5. **One check of an argument against a packaged list**
   (https://github.com/xippios/sdk-core/issues/313; ADR-0045). A source's refusal of a code its
   list lacks comes from core's check, with the list's name, its fetch date and the closest codes
   by core's strategy or the source's, and a value of the other type than the list's codes is
   refused with `InvalidRequestError`, which names the integer or the text to pass: a text of
   digits given for sdk-usda-psd's and sdk-usda-gats's integer codes, which they compared by
   its text and their tasks declare as integers, and an integer given for sdk-usda-nass's text
   codes (ADR-0045, Consequences). Another text given for integer codes names the codes that
   the source's `closest=` strategy names for it, else those whose name holds it, so a
   strategy of integer codes takes a text as well and returns no pair for one it does not read
   (ADR-0045, decision 4, amended 2026-11-22; https://github.com/xippios/sdk-core/issues/418),
   this refusal ends with the source's `reason=` as `UnknownCode`'s does
   (https://github.com/xippios/sdk-core/issues/432), and every value of a source's hint table,
   which is no code, is refused with its hint and its reason and without the sentence that the
   packaged list is out of date, by `UnknownCode(..., outdated=False)`, while a refusal with
   `otherwise=` keeps it (ADR-0041, decision 8, and ADR-0045, decision 3, each amended
   2026-11-22; https://github.com/xippios/sdk-core/issues/430,
   https://github.com/xippios/sdk-core/issues/440). It
   reaches the nine sources that package lists. Entry: under `changed`, the refusals whose
   wording or class the port changes, as the tests that the port changes show them.
6. **A `since` that takes back a vintage** (https://github.com/xippios/sdk-core/issues/318;
   ADR-0052). sdk-usda-esr's refusal of a `since` it cannot read takes core's wording, `since
   must be the meta.vintage text of an earlier call, an ISO date and time without a time zone
   such as '2026-10-06T08:00:00'`, its class and its two reasons kept; sdk-usda-psd's wording
   stays as it is. Entry: under `changed`, for sdk-usda-esr alone.
7. **A series over periods** (https://github.com/xippios/sdk-core/issues/315; ADR-0054). A
   range over a series' ceiling is refused in core's wording before the first request, naming
   the range, the ceiling, its unit and, where the MCP server's ceiling is lower, the option
   that raises it, and then, before its advice, that nothing was sent, which holds since a task
   calls `check` before any request of the call. A request after the first that fails raises
   its error, its class kept, naming the periods answered before it by their count, the first
   and the last, with nothing returned (ADR-0054, amendment 2026-11-22). The tests of
   sdk-usda-esr, sdk-usda-psd, sdk-usda-gats and sdk-usda-nass that assert a refusal over the
   ceiling or a failed period read these words, `Nothing was sent.` and `after 2 periods
   answered, 2021 to 2022`, and sdk-usda-nass's pass over its counts may run on `fetch_periods`
   as its pass over its data does, since a year counted is a year answered
   (https://github.com/xippios/sdk-core/issues/443). sdk-usda-nass's split of `year__GE` alone
   checks the range after its count of it, so on that path the port words a refusal of its own
   that says that the count was sent, as its part below says, and its
   `test_split_of_year_ge_alone_refuses_more_than_twenty_years_after_the_first_count` asserts
   that refusal, not core's (https://github.com/xippios/sdk-core/issues/454). It reaches
   sdk-usda-esr, sdk-usda-psd, sdk-usda-gats and sdk-usda-nass, and sdk-comtrade where its patch
   takes `fetch_periods` (https://github.com/xippios/sdk-comtrade/issues/36). Entry: under
   `changed`, the refusal's wording, its class `InvalidRequestError` and the option's name
   unchanged, and the failure's message. The port replaces sdk-usda-nass's
   `tasks.split_ceiling` and `tasks.set_split_ceiling`, which its 0.2.0 entry named, and
   sdk-usda-gats's `tasks.series_ceiling` and `tasks.set_series_ceiling`, which its changelog
   and its README name, by one `Ceiling`: their removal breaks a caller's call, so it takes an
   entry of its own under `breaking`, which makes the source's release a minor (§12), unless
   the port keeps the two names (https://github.com/xippios/sdk-usda-nass/issues/86).
8. **What a write task's preview shows** (https://github.com/xippios/sdk-core/issues/182;
   ADR-0050). A write task's preview carries `reads`, the operations it read, `[]` for none,
   and the task's docstring says whether its preview reads first and what the read costs. It
   reaches the write tools of sdk-cashctrl and sdk-google-mail. Entry: under `added`, the field
   and the docstrings' sentence.

### The conventions' rules changed since 1.28

Conventions 1.29 differ from 1.28 by the rules below, read from the diff of
`docs/conventions.md` since `v0.4.0`, each with its record and what a source does for it,
which §15 item 8 holds at its adoption. Item 8 of "Adopting core 0.4.0" stays the record of
the rules of 1.28.

§3, the snapshot, the reference lists and fixtures:

1. **The snapshot script's frame** (ADR-0046, decisions 1 to 3). A source's
   `scripts/refresh_upstream.py` declares a `Snapshot` of `xippios.core.refresh` and calls
   `run(snapshot)`: the fetch, the attribution check, `FETCHED.md`, the write and `--check` are
   the frame's, a converter its hooks use is the source's own dependency, and every file but
   `FETCHED.md` is written as its hooks make it. The source ports its script, its own code kept
   as hooks, as https://github.com/xippios/sdk-core/issues/320 names per source, and declares
   the converter its hooks use itself. Its attribution check reads an image's alternative text
   and passes a statement recorded with a link only as the text of that link (ADR-0046,
   decision 7), and it holds an API document's `info` as conventions §3 state it (ADR-0046,
   Consequences).
2. **`FETCHED.md` in one form** (ADR-0046, decisions 3 and 4). The frame writes `FETCHED.md`
   in one form for every source, and the first run of the ported script rewrites it once;
   every ETag stands in a code span on a row that ends in the secret scan's allowlist mark, and
   a `Last-Modified` in UTC. The source commits the rewritten file with the first run that
   fetches after the port, since an adoption PR fetches nothing (§15; ADR-0028, decision 4).
3. **The check of the committed `FETCHED.md`** (ADR-0046, decision 6). A source's
   `scripts/refresh_upstream.py` names its `Snapshot` `SNAPSHOT` at its top level, which
   imports and declares alone, sends no request and writes no file, its run under
   `if __name__ == "__main__":`. The frame ends `FETCHED.md` with the line that names its form,
   and the family check fails a source whose file of that form differs from its `SNAPSHOT`
   where the declaration decides, reading back what only a response knows, and passes a file
   without the line or of an older form. The source names its declaration so in its port,
   declares no `linked` where it links no page, since a `linked` hook makes the check read back
   every row that no declared page owns, and is held from the first run of its ported script
   that fetches.
4. **The observed-behavior file** (ADR-0044). A note of `OBSERVED.md` is a `###` section whose
   last paragraph opens with `Probe: <date>` or `Observed: <date>`, and the family check fails
   a source whose `FETCHED.md` lists the file in no row of its own, whose note lacks its label
   and date, or whose code span cites a file that does not exist, from core 0.4.1 on with no
   warning; a source without the file passes. The six sources that keep the file meet the
   three rules from the lock's move and delete their own tests of them, keeping what the
   family check does not read (https://github.com/xippios/sdk-core/issues/348).
5. **`Not fetched` and a redirect** (ADR-0046, decision 4). The table `Not fetched` stands under
   its heading even with no row, and a page that redirects to another host stops the run unless
   the snapshot records it by that status, its row then naming the host. A port whose script
   followed such a redirect records the page by its status, as sdk-usda-esmis's does.
6. **A keyed sample** (ADR-0046, decision 5; ADR-0037, decision 4). A sample that needs
   credentials is marked `keyed` and sent with the snapshot's `Credentials` alone, under the
   origin of their base, with no redirect followed and no retry, and `FETCHED.md` names the
   variables the login reads, never their values. sdk-faostat declares its login so and marks
   its samples `keyed`.
7. **A personal identifier in a fixture** (ADR-0017, ADR-0048). A recording that rewrites a
   personal identifier by key does it in its own rewrite step, which the recorder runs on the
   `Fixture` before the write. The source passes that step as `rewrite=` (rule 21).
8. **The reference refresh script's frame** (ADR-0051). A source's
   `scripts/refresh_reference.py` declares one `Listed` of `xippios.core.refresh` per packaged
   list, with its fetch, its enum and its origin, and calls `run(lists, package=...)`, which
   fetches every list before it writes one, then writes the packaged files, the provenance rows
   of `reference/README.md` and `enums.py`. The nine sources that package lists port their
   script, as https://github.com/xippios/sdk-core/issues/321 names per source: each request is
   sent once where a source's client retried, and an option of the source's own is read before
   the call and passed on as `argv`, so the frame's `--help` lists `--only` and
   `--render-only` and no option of the source's own (ADR-0051, decisions 5 and 7).

§4, the result envelope:

9. **The name of each country code** (https://github.com/xippios/sdk-core/issues/310;
   ADR-0056; ADR-0028). A country argument takes upstream's code alone, and `meta.names` maps
   each country parameter of the request to its codes and their names; a task that takes a
   country, an area, a reporter or a partner fills it with `names_codes`, one `PackagedCodes`
   per parameter, a parameter whose codes no packaged list can name stands in `UNNAMED_CODES`
   of its tasks module with the reason, and the family check fails a task whose parameter
   holds `country`, `countries`, `area`, `reporter` or `partner` and stands in neither. The six
   sources of the first list's second change decorate their tasks, and sdk-faostat exempts
   `get_data`'s `area` and `area_cs` (https://github.com/xippios/sdk-faostat/issues/34).
10. **A `since` that takes back a vintage** (ADR-0052). A parameter that takes back a
    `meta.vintage` filters with `newer_than`, read by the source's reader of its vintage text or
    core's `naive_time`, and the task sets `meta.vintage` and `meta.published_at` from the whole
    answer; a `since` beside an `until` is an inclusive bound, a rule of its own. sdk-usda-esr
    and sdk-usda-psd filter with `newer_than`, and sdk-usda-esmis, sdk-usda-wasde, sdk-faostat
    and sdk-eurostat keep their inclusive bounds
    (https://github.com/xippios/sdk-usda-esmis/issues/35).
11. **A series over periods** (ADR-0054, amended 2026-11-22). A task states a period series'
    ceiling with `Ceiling`, whose `check`, called before any request of the call, refuses a
    range over it, saying that nothing was sent, and whose two methods are the tool set's
    option hooks, and sends the series with `fetch_periods`, which passes over a period whose
    fetch raises one of `skip` and, on a later failure, returns nothing and raises the error
    naming the periods answered. A task that checks a range only after a request words that
    refusal itself and says what was sent. sdk-usda-esr, sdk-usda-psd,
    sdk-usda-gats and sdk-usda-nass replace their ceilings, setters and loops, and sdk-comtrade
    keeps its ceiling in `validate_slice` (ADR-0054, Consequences).

§5, errors:

12. **A query over upstream's limit** (ADR-0053). `QueryTooLarge` joins the taxonomy under
    `InvalidRequestError`: a query over upstream's per-call record limit is refused with it,
    core wording the message, a source subclasses it only for an attribute of its own, and a
    task whose upstream counts a query's records on request counts first with `fetch_counted`.
    sdk-comtrade deletes its class, sdk-usda-nass keeps a subclass for `year`, and sdk-eurostat
    and sdk-faostat choose in their patches (https://github.com/xippios/sdk-core/issues/317).
13. **One check of an argument** (ADR-0045). A source checks an argument against a packaged
    list with the `check` of the list's declaration `PackagedList.codes(code, name,
    fold_case=...)`, which returns the value as the caller gave it or raises `UnknownCode`. The
    nine sources that package lists replace their copies
    (https://github.com/xippios/sdk-core/issues/313). A refusal of a value of the check's hint
    table, which is no code, names the table's text and the reason and leaves out that the
    packaged list is out of date (ADR-0041, decision 8, amendment 2026-11-22): a source's test
    that asserts that sentence on such a refusal drops it, sdk-eurostat's
    `test_get_total_production_refuses_a_product_its_list_lacks` among them
    (https://github.com/xippios/sdk-core/issues/440).
14. **The messages that name their request** (ADR-0030, decision 4; ADR-0043). A message about
    an answer, core's or one that a source's `classify` maps, and a refusal of a request
    already built name their request; a refusal that the package makes of the call as given
    names the argument, the record or the tool and says that nothing was sent, and a decoder's
    subject names the operation that its caller gives. A source's own messages follow that
    line, through `request_description` where they name a request
    (https://github.com/xippios/sdk-core/issues/346).

§8, MCP:

15. **What a write task's preview shows** (ADR-0036, decision 9; ADR-0050). A preview sends no
    write and shows the action as the confirmed call would send it, by upstream's names, its
    task's docstring says whether it reads first and what that costs, and it carries `reads`;
    `assert_write_tools(..., preview_reads=True)` holds the field and `dry_run=` the requests a
    preview sends, both off by default. A source with a write server declares `reads` and
    passes `preview_reads=True` from its patch on core 0.4.1, the dry run at its choice:
    sdk-cashctrl and sdk-google-mail (https://github.com/xippios/sdk-core/issues/182).
16. **The rest of a cut answer** (ADR-0047). A tool whose cut answer a caller can continue
    takes `ResultCap(paged=True)` where a second run of its task costs little, a packaged
    table or an answer the response cache holds; a task that records its own `start` or takes
    a parameter named `offset` stays unpaged, a write task is never paged, and `keep="last"`
    keeps the newest rows of a series ordered oldest first. The source adds an entry to
    `MCP_CAPS` for each cut tool whose second run costs little
    (https://github.com/xippios/sdk-core/issues/314).

§10, testing:

17. **Three cases between the kinds of a built answer** (ADR-0028, decision 8; ADR-0043). A
    recording changed in its status, its content type and its body at once is of the second
    kind; a value that no route serves and no `classify` reads is an input of the test and takes
    no kind; a recording replayed at its own path for other parameters is of the third kind,
    its test naming the condition. The source's tests take the kind that each case is given
    (https://github.com/xippios/sdk-core/issues/345).
18. **The mark of a built answer** (ADR-0049). A test marks a body it builds by naming `§10`
    and its kind in one docstring or block of comments, within the mark's reach, an input of
    the test by its sentence and a replay for another request as the third kind, and
    `xippios.core.testing.built_answers`, collected in `tests/test_built_answers.py`, fails an
    unmarked place, naming its file and line, and runs the census of the replays after every
    other test. The source marks its places and holds the collecting line that sdk-template
    renders (https://github.com/xippios/sdk-core/issues/344).
    The input's sentence marks an exchange that reaches `fixture_from_response` alone, built in
    the test or returned by a function of the module, each call judged on its own, and handed
    on directly, by a local name or through one function of the module, and the check reads a
    module's imports, so the frame's `Response` takes it too (ADR-0049, decision 10;
    https://github.com/xippios/sdk-core/issues/439).
19. **The recording of a task** (ADR-0057). `record_task` records every exchange that a task
    makes, in order, each sent once and none answered from the cache, writes all or none as
    `<case>.json` and `<case>_<k>.json`, records no token request inside an auth flow, refuses
    a task that downloads and reads each answer whole. sdk-google-mail records its tasks with it
    (https://github.com/xippios/sdk-core/issues/174).
20. **The recorder's one send and its final answers** (ADR-0037, decision 6; ADR-0048,
    decisions 3 and 4). The recorder sends one request and keeps a final answer whatever its
    status, a source that needs the answer itself sends it with `send_once`, and an answer of a
    1xx or a 3xx status is refused on every path before anything is written. A recorder that
    built a client for one attempt sends with `send_once`, and a recording that ended in a
    redirect records the request that upstream answers itself
    (https://github.com/xippios/sdk-core/issues/281,
    https://github.com/xippios/sdk-core/issues/364).
21. **The rewrite step** (ADR-0048, decisions 1 and 2). What a source replaces beyond its named
    secrets it replaces in its rewrite step, passed as `rewrite=` to `record` or
    `fixture_from_response`, which returns the fixture with the values it replaced; a value it
    returned that is left in the URL, a header value, a body or a string decoded from a JSON
    body refuses the write, `REDACTED` alone masked first. sdk-x, sdk-google-mail and
    sdk-cashctrl pass their steps (https://github.com/xippios/sdk-core/issues/322).
    A recorder writes `REDACTED` for a field of a request that it must not keep and drops none,
    so that the census compares a replay with its recording key by key; sdk-google-mail does so
    for `raw` before its adoption, as its part says (ADR-0048, decision 7;
    https://github.com/xippios/sdk-core/issues/439).
22. **The live comparison of a packaged list** (ADR-0055). A source declares in
    `tests/test_live.py` each packaged list that its nightly run compares with upstream's, in
    `LIVE_LISTS`, and each it does not, in `NO_LIVE_LIST` with the reason; a code gone, new or
    changed fails the run, the log naming codes and never a record's other fields, and the
    family check fails a packaged list that stands in neither. The nine sources that package
    lists declare them from the lock's move (https://github.com/xippios/sdk-core/issues/319).

§12, releases:

23. **A release rewords no entry** (https://github.com/xippios/sdk-core/issues/355; ADR-0043).
    A release PR assembles each entry as its fragment reads, under its fragment's group, and a
    wrong entry is corrected in its fragment by a pull request before the release. The source
    corrects its fragments, the entries of the first list among them, before its release PR.
24. **The live run a release cites** (https://github.com/xippios/sdk-core/issues/351,
    https://github.com/xippios/sdk-core/issues/382; ADR-0043). A source's release PR cites a
    green run of `live.yml` on the commit of `main` that it starts from, and a run on an earlier
    commit is none, whatever the merges after it changed. A release whose base moved after its
    run waits for the next nightly run or one more dispatch of `live.yml` on `main`.

§15, adoptions:

25. **The adoption's entry** (https://github.com/xippios/sdk-core/issues/355,
    https://github.com/xippios/sdk-core/issues/342; ADR-0043). Item 9's fragment names the core
    bound, the template's tag and the conventions' version as they stand after the adoption,
    changed or not, and is `breaking` where the adoption brings a core minor and `changed`
    where it brings none. The adoption of core 0.4.1 is `changed` and names
    `xippios-core~=0.4.1`, sdk-template v0.4.1 and conventions 1.29.
26. **The host's entry** (https://github.com/xippios/sdk-core/issues/355; ADR-0043). The host's
    item 9 names the core bound and the conventions' version as they stand after its adoption,
    and no template tag.

### Every source

- Item 1, core floor: `core_version=0.4.1`, so `xippios-core~=0.4.1` and its `[mcp]`, `[http]`
  and `[testing]` extras likewise, from PyPI, with `uv.lock` updated (§12: `~=X.Y.Z` when patch
  Z shipped what the source adopts); all twelve read `~=0.4.0` today. The family check's five
  new tests hold the source from this move, as listed above.
- Item 2, `copier update` to sdk-template 0.4.1, which renders what "sdk-template" below lists.
  Its `tests/test_built_answers.py` brings the collecting line of the built-answer check, which
  then fails each place of the source's tests that builds or serves a body without its mark, so
  the adoption marks them (https://github.com/xippios/sdk-core/issues/344): an upper bound,
  counted on 2026-11-21, of 10 in sdk-usda-esmis, 31 in sdk-eurostat, 20 in sdk-usda-psd, 20 in
  sdk-usda-nass, 27 in sdk-comtrade, 38 in sdk-faostat, 14 in sdk-usda-wasde, 40 in
  sdk-usda-gats, 34 in sdk-usda-esr, 52 in sdk-x and 49 in sdk-google-mail, and none in
  sdk-cashctrl, whose own check core's replaces. The bound counts the places without a mark
  alone. The census fails, in the same run, further tests, those whose replay answered another
  request than the recorded one, each marked as the third kind or narrowed: the trial counted,
  at core's commit of the trial, 6 such tests beside 42 places in sdk-google-mail
  (https://github.com/xippios/sdk-google-mail/issues/72), 4 beside 27 places in sdk-comtrade,
  21 after its port (https://github.com/xippios/sdk-comtrade/issues/60), 24 beside 12 in
  sdk-usda-nass (https://github.com/xippios/sdk-usda-nass/issues/86), 5 beside 26 in
  sdk-usda-esr (https://github.com/xippios/sdk-usda-esr/issues/59), 11 beside 51 in sdk-x
  (https://github.com/xippios/sdk-x/issues/57) and none beside none in sdk-cashctrl
  (https://github.com/xippios/sdk-cashctrl/issues/134).
- Items 3 and 4, the copies each core change replaced, deleted with their tests, and the core
  change named for each in the PR description; per source below:
  - the check of an argument against a packaged list → `PackagedList.codes(...)` and its
    `check` (https://github.com/xippios/sdk-core/issues/313): esr, psd, nass, gats, comtrade,
    faostat, eurostat, wasde, esmis;
  - a `since` filter → `newer_than`, and esr's reader → `naive_time`
    (https://github.com/xippios/sdk-core/issues/318): esr, psd;
  - a count before the data request and its error → `fetch_counted` and `QueryTooLarge`
    (https://github.com/xippios/sdk-core/issues/317): comtrade, nass;
  - a ceiling with its setter and its option hooks, and a loop over periods → `Ceiling` and
    `fetch_periods` (https://github.com/xippios/sdk-core/issues/315): esr, psd, gats, nass;
  - a nightly comparison of a packaged list → `xippios.core.testing.live` with `LIVE_LISTS`,
    or `assert_list_current` (https://github.com/xippios/sdk-core/issues/319): esr, psd, gats,
    comtrade, esmis, wasde, and faostat's assertion of the removed codes in
    `test_list_elements`;
  - the tests of `OBSERVED.md` that the family check now makes
    (https://github.com/xippios/sdk-core/issues/348): esmis, wasde, esr, cashctrl, faostat;
  - the frame of `scripts/refresh_upstream.py` → a `Snapshot` named `SNAPSHOT` at the script's
    top level and run by `xippios.core.refresh` (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-core/issues/428), and the tests of the frame in
    `tests/test_refresh_upstream.py` with it, as the item on that file below says
    (https://github.com/xippios/sdk-core/issues/415): every source;
  - the frame of `scripts/refresh_reference.py` → `Listed` and `run(lists, ...)`
    (https://github.com/xippios/sdk-core/issues/321): comtrade, eurostat, faostat, esmis, esr,
    gats, nass, psd, wasde;
  - a recorder's client built for one attempt and its copy of the frame → `send_once`,
    `rewrite=` and core's check (https://github.com/xippios/sdk-core/issues/322,
    https://github.com/xippios/sdk-core/issues/281): x, google-mail, cashctrl, and wasde's
    `scripts/cut_sample.py`;
  - a task's capture of its exchanges → `record_task_sync`
    (https://github.com/xippios/sdk-core/issues/174): google-mail;
  - a check of a built answer's mark and a census of its own →
    `xippios.core.testing.built_answers` (https://github.com/xippios/sdk-core/issues/344):
    cashctrl.
- What core does not provide stays the source's, named in the PR description (§15 item 4): a
  list filter that answers an empty list for a value the list lacks, which each source refuses
  through the check under its own row (ADR-0045, Consequences); the order of a range, a start
  after its end (ADR-0054, Consequences); a `since` that is an inclusive bound beside an
  `until` (ADR-0052); a recorder's command line, its guards and its rules
  (https://github.com/xippios/sdk-core/issues/364); an option of a refresh script's own, read
  before the frame's `run` (ADR-0051, decision 7); and what sdk-cashctrl's snapshot script does
  that the frame does not carry (below).
- `tests/test_refresh_upstream.py`, 64 tests in the twelve sources, calls `render_fetched` and,
  in all but sdk-eurostat, `write_snapshot` and `Response`, which the port deletes from the
  script, so it follows the port as §15 items 3 and 4 delete a copy with its tests, each
  source's part below naming the tests that go and those that stay
  (https://github.com/xippios/sdk-core/issues/415,
  https://github.com/xippios/sdk-core/issues/425):
  - the tests of what the frame now does go with the copy, each kind held in core's
    `tests/refresh/test_upstream.py`: the row of `OBSERVED.md` and a write that leaves the file
    as written by `test_observed_md_has_its_row_and_is_left_as_written`; the sentence that
    nothing here is edited by hand but `OBSERVED.md`, "where it exists", which the frame
    writes in one form with the file and without it, so that a copy's sentence naming no
    `OBSERVED.md` while there is none gives way to it (ADR-0046, decision 3), by
    `test_fetched_md_says_that_nothing_but_observed_md_is_edited_by_hand`; the two sentences
    that cite sdk-core ADR-0028, and no ADR-0003, by
    `test_fetched_md_cites_the_standing_record_of_upstream_fidelity`; the table `Not fetched`
    by `test_not_fetched_lists_the_pages_left_out_and_those_no_anonymous_client_reads`; an
    ETag in its code span by `test_every_etag_stands_in_a_code_span_with_the_mark`; the write,
    and `--check` with its comparison of the committed `FETCHED.md`, by
    `test_the_frame_fetches_writes_and_checks`; the removal of a file no longer produced, which
    `--check` names, in the subdirectories that the run writes to alone, by
    `test_a_file_no_longer_produced_goes_from_the_subdirectories_the_run_writes_to`; and a
    declared page that the frame cannot record stopping the run before any request, by
    `test_every_declared_page_is_checked_before_the_first_request`;
  - the tests that compare the committed `FETCHED.md` with the script's render, in
    sdk-cashctrl, sdk-faostat, sdk-usda-esr and sdk-usda-wasde, go with the copy at the
    adoption as well, since the committed file keeps the copy's form until the first run of the
    ported script that fetches (ADR-0046, decision 3; §15); from that run on the family check's
    `test_family_fetched_md_agrees_with_the_snapshot` holds the file to the script's `SNAPSHOT`
    in their place, with no request and no test of the source's own (ADR-0046, decision 6);
  - the tests of the source's own code stay: a hook's, calling the hook, and those of what its
    `Snapshot` declares, its `capture`, its pages and its `not_fetched`, reading the
    declaration (ADR-0046, decision 2).
- A test of a hook that builds the frame's `Response`, imported from `xippios.core.refresh` by
  its bare name or called as `refresh.Response(...)`, marks it with the input's sentence, since
  no route serves it, and needs no entry of `ALLOWED` (ADR-0049, decision 10;
  https://github.com/xippios/sdk-core/issues/439).
- Item 5, unchanged.
- Item 6: each of the nine sources that package lists runs its ported reference script once
  with `--render-only`, which writes `enums.py` and the provenance rows of `reference/README.md`
  from the packaged files as committed (ADR-0051, decision 4); sdk-eurostat's and
  sdk-faostat's empty `enums.py` stays as committed. A `Listed` without its `origin` writes
  its list's endpoint in a code span as the row's Origin (`Listed.origin` in
  `src/xippios/core/refresh/reference.py`), so a port declares the origin of every list whose
  committed row names more than that, or `--render-only` rewrites the row: the parts below
  name it for each source but sdk-eurostat, whose nineteen rows name the endpoint alone, and
  sdk-usda-nass's port declares eleven (https://github.com/xippios/sdk-usda-nass/issues/86).
- Item 7, unchanged.
- Item 8, conventions 1.29: every rule of the list above holds in the source, those of the
  family check from the lock's move, and its check of `FETCHED.md` from the first run of the
  ported snapshot script that fetches (rule 3).
- Item 9: the adoption's fragment under `changelog/` is `changed` and names
  `xippios-core~=0.4.1`, sdk-template v0.4.1 and conventions 1.29 (§15 item 9; ADR-0043,
  decisions 1 and 3), and each change of the first list that the adoption brings to the
  source's callers has its own fragment (the definition of done's Adoption PR block; review
  checklist, item 12).
- `FETCHED.md` is the frame's alone: the first run of the ported snapshot script that fetches
  rewrites it once in the frame's form, every row with an ETag gaining the code span and the
  mark and the 403 rows moving to `Not fetched` (https://github.com/xippios/sdk-core/issues/320;
  ADR-0046, decision 3), and an adoption PR, which fetches nothing, leaves it to that run
  (§15). That run writes, as the file's last line, the mark of the frame's one form,
  `<!-- form 1 of the FETCHED.md that xippios.core.refresh writes -->`, from which the family
  check holds the committed file to the script's `SNAPSHOT` (ADR-0046, decision 6). sdk-eurostat's row of `OBSERVED.md`, which the family check asks from the lock's move
  and its committed `FETCHED.md` lacks, comes from a refresh by its present script, in a pull
  request of its own before the adoption PR (below).
- The frame's attribution check holds an API document that it parses, an OpenAPI or Swagger
  document in JSON: each of `info.license`, `info.termsOfService` and `info.contact` that the
  document holds must be quoted, by one of its values, as the text or the link of a
  `Statement` recorded from that document, or the run stops before anything is written
  (`INFO_TERMS` and `_searched` in `src/xippios/core/refresh/upstream.py`), so a port records
  each, sdk-x its document's `info.contact` among them
  (https://github.com/xippios/sdk-x/issues/57). The frame parses no YAML document
  (`_api_document`, the same module), so sdk-faostat and sdk-usda-esmis keep their check of
  their YAML document's `info` in a hook of their own (below).
- A check of each page's title stays the source's own: core's `Page` holds no title, and core
  takes none, since the three sources that check one compare three different things, so
  sdk-google-mail, sdk-usda-wasde and sdk-x keep their titles in a table that their `reduce`
  reads (below; https://github.com/xippios/sdk-google-mail/issues/72).
- The ported script's attribution check reads an image's alternative text as text of the page,
  searching the same text without it as well, and reads past a statement recorded with a link
  only as the text of a link to its target, on any page that prints the link, while a
  statement without a link and the vocabulary pass wherever they stand (ADR-0046, decision 7;
  https://github.com/xippios/sdk-core/issues/437). An alternative text that holds a word of
  terms or copyright, or that stands inside the words of a recorded statement, and a linked
  statement's words outside its link stop the source's first run that fetches until the
  attribution records them, which no offline run shows: that run's pull request records each,
  as a statement of its page or a word of the vocabulary. An image with an alternative text
  inside a recorded link, beside its words, is part of the link's text, so the page stops with
  "no longer links" until the statement records the link's text as the page reads it, a link
  `<a href="…"><img alt="icon"> Terms of Service</a>` as "icon Terms of Service" with its
  target (ADR-0046, Consequences).
- A live run prints the requests it sent by host, `requests sent by the live run: 15
  (api.example.org: 15)`, from which the source's release PR reads its count of live calls,
  and a run that built a `Tenants` registry names no host; the source changes no file for it
  (https://github.com/xippios/sdk-core/issues/335).
- The first line of `.github/workflows/publish.yml` cites ADR-0039, decision 6, by `copier
  update` (https://github.com/xippios/sdk-core/issues/323).

### sdk-cashctrl

- Deletes (item 3):
  - `tests/test_built_answers.py`'s own check → the collecting line, with `READERS =
    frozenset({"merge_custom"})` and its one entry of `ALLOWED` as it stands, and
    `tests/replay_census.py` → the census in the same run
    (https://github.com/xippios/sdk-core/issues/344). Core's census compares a replay's body
    as well as its query and judges what a test's fixtures mount, where its own counted from
    the call alone, and its suite had not run under core's census when the step merged
    (https://github.com/xippios/sdk-core/pull/396), so a test its census passed may fail;
  - in `scripts/record_fixture.py`, `recording_client` → `send_once_sync(client_for(DEMO),
    ...)`, `--wrong-key` as `auth=`, and `TenantScrub(...).apply` as the step of
    `fixture_from_response(..., rewrite=...)`, and in `tests/test_record_fixture.py`
    `test_the_recording_client_never_retries` goes
    (https://github.com/xippios/sdk-core/issues/322,
    https://github.com/xippios/sdk-cashctrl/issues/91); as a step, `apply` returns the pair of
    the rewritten fixture and the values it replaced, here none, `(rewritten, [])`, since its
    verify by pattern refuses what survives, and the three tests of
    `tests/test_record_fixture.py` that read what it returns,
    `test_secrets_are_redacted_plain_and_percent_encoded`,
    `test_the_host_then_the_secrets_then_the_rewrite` and
    `test_the_verify_passes_a_clean_fixture`, unpack the pair; the guards' reads of
    `order/read.json` and `order/bookentry/read.json` are sent once by `send_once` too, since
    the demo organisation's own client retries a 5xx where
    `test_an_order_write_naming_an_unmarked_or_unreadable_order_is_refused` holds one read,
    and a read that core refuses as a 1xx or 3xx refuses the write
    (https://github.com/xippios/sdk-cashctrl/issues/134);
  - its refusal of a 1xx or 3xx on its five file paths becomes core's on every path, and its
    refusal of another 2xx and of a binary body at a file path stays (ADR-0048,
    Consequences). In `tests/test_record_fixture.py`,
    `test_the_host_then_the_secrets_then_the_rewrite`, which hands a built 302 to
    `fixture_from_response`, fails from the lock's move and builds a 200; the redirect of
    `test_a_file_path_writes_no_answer_but_an_error_or_a_refusal` fails once the recorder
    sends with `send_once`, which refuses the 302 before the recorder's own check of a file
    path's answer reads it, and asserts that refusal, which names the method, the path and the
    status, where the recorder's named the file path
    (https://github.com/xippios/sdk-core/issues/364,
    https://github.com/xippios/sdk-cashctrl/issues/134);
  - in `tests/test_observed.py`, `test_every_file_the_notes_cite_exists`,
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own`, whose row as the file's last line
    and whose sentence "never edited by hand" are the copy's form, which the first run of the
    ported snapshot script replaces with the frame's, the row standing before `Not fetched`,
    and the label and the date of `test_every_note_ends_with_its_probe`, which the family
    check holds, the whole of `FETCHED.md` from that first run on
    (https://github.com/xippios/sdk-core/issues/348,
    https://github.com/xippios/sdk-core/issues/428);
  - in `tests/test_refresh_upstream.py`,
    `test_fetched_lists_observed_in_a_row_of_its_own_where_it_exists`,
    `test_a_snapshot_keeps_observed_and_removes_a_stale_file`, whose removal of a stale file
    the frame makes in the subdirectories that it writes to alone, the port giving up the
    removal at the top of `docs/upstream/` (below), and
    `test_the_committed_fetched_md_is_the_scripts_text`, whose comparison without a request the
    family check's `test_family_fetched_md_agrees_with_the_snapshot` makes from the first run of
    the ported script that fetches, reading back the page's size, sha256, ETag and Fetched, as
    that test did, and the names of the files that its `split` makes, and computing no digest
    (https://github.com/xippios/sdk-core/issues/415,
    https://github.com/xippios/sdk-core/issues/425, https://github.com/xippios/sdk-core/issues/428).
- Keeps, in `tests/test_refresh_upstream.py`,
  `test_an_entry_that_would_be_written_as_observed_is_refused`, calling its `split`, whose check
  refuses `observed.md` and `fetched.md` in lower case, where the frame refuses `OBSERVED.md`
  and `FETCHED.md` by those names (https://github.com/xippios/sdk-core/issues/415).
- Changes:
  - `models.py`: `WritePreview` declares `reads: list[str]`, and `tasks_write.py`'s `_preview`
    sets it from the read it made, the eight previews that read their record once naming its
    `read.json`, such as `["journal/read.json"]`, and the six that send no request `[]`; each
    of the fourteen docstrings says which and what it costs, and
    `tests/test_tasks_write.py` passes `preview_reads=True`
    (https://github.com/xippios/sdk-core/issues/182,
    https://github.com/xippios/sdk-cashctrl/issues/88);
  - `tasks.py`: `paged=True` in `MCP_CAPS` for the lists that upstream returns whole, the four
    lists that record `start` left as they are
    (https://github.com/xippios/sdk-cashctrl/issues/87), and in `tests/test_org_lock.py`
    `test_the_bound_read_server_reaches_the_bound_organisation_only` reads that
    `cashctrl_list_currencies` takes `offset` where it read that it takes no arguments, since
    the refusal of an argument a tool does not declare names those it takes
    (https://github.com/xippios/sdk-cashctrl/issues/134);
  - `scripts/refresh_upstream.py`: ported with `split` for its one page, its word check inside
    it, `note` for the files that keep a nested table as HTML and `sections` for its vendor
    examples, its attribution recording "Terms of Service" from its page with its link to
    https://cashctrl.com/en/about/terms, which the error handling's text links, or the frame
    stops the run (https://github.com/xippios/sdk-cashctrl/issues/134). It gives up six things
    that the frame carries for no single source: `--from-file`, its own User-Agent, its request
    for the page gzipped, the removal of an entry's file at the top of `docs/upstream/` once
    the table of contents drops the entry, so its port puts its entries under a subdirectory or
    removes such a file by hand, `--check` naming no leftover, the fragment of its entry in
    each split file's row of `FETCHED.md`, `index.html#/order`, since the frame's row of a file
    split from a page names the page's URL, the file's first line keeping the fragment, and its
    check that the notice stands in the footer's logo, below (ADR-0046, decisions 2 and 7, and
    Consequences; https://github.com/xippios/sdk-cashctrl/issues/134).
- Its footer's copyright notice, `NOTICE`, is recorded from `PAGE_URL`, since the frame reads it
  in the alternative text of the footer's logo and checks it on every run, and its link to the
  terms passes as that link (ADR-0046, decision 7;
  https://github.com/xippios/sdk-cashctrl/issues/134). The check of the notice in `split`,
  `copyright_year` with `_COPYRIGHT` and the year it compares, goes as a copy of the frame's
  check, and with it the sixth thing of those above, the check that the notice stands in the
  footer's logo, a part of the page that the frame does not tell apart; a test of the port that
  held the notice to `split` holds it to the declaration.
- Takes nothing of `record_task`: it records exchange by exchange into 44 directories named
  after wrappers, and three of its tasks download (ADR-0057, Consequences).
- The first list: the rest of a cut answer and what a write task's preview shows.

### sdk-google-mail

- Deletes (item 3): in `scripts/record_fixture.py`, `recording_client`,
  `task_exchanges_async`, `task_exchanges`, the seed of `TENANTS` with its guard and the loop of
  its own `record_task` → `record_task_sync(RECORDED_TASKS[name], DEMO, fixtures=FIXTURES,
  case=args.case, scrub=scrub, rewrite=step, **arguments)`
  (https://github.com/xippios/sdk-core/issues/174); the single exchange → `send_once_sync`
  through the demo account's client, the token request with `auth=None`, and every exchange's
  fixture built by `fixture_from_response(response, scrub=..., rewrite=step)`, the step running
  `rewrite` and `check` (https://github.com/xippios/sdk-core/issues/322,
  https://github.com/xippios/sdk-google-mail/issues/42). It keeps its command line, the write
  safety rule, `MessageScrub`, `rewrite` and `check`.
- Changes: `models.py`'s `ComposePreview` and `ActionPreview` declare `reads`, each of the five
  previews of `tasks_write.py` sets it, `["gmail.users.messages.get"]` for the preview of a
  reply by `create_draft` or `send_message` and `[]` for the others, each docstring says whether
  its preview reads and what it costs, a reply's read 20 quota units, and
  `tests/test_tasks_write.py` passes `preview_reads=True`, a dry run's `is_read` taking the
  token request that a reply's read sends first
  (https://github.com/xippios/sdk-core/issues/182,
  https://github.com/xippios/sdk-google-mail/issues/39); `scripts/refresh_upstream.py` ported
  with `reduce` alone (https://github.com/xippios/sdk-core/issues/320): every note of its
  pages is static and stands on its `Page`, so no `note` hook runs, and its check of each
  page's `<h1>` against the page's title, which core's `Page` does not hold, reads a table of
  its own, `TITLES`, in `reduce`, which also stops on a developers.google.com page that does
  not print the content footer, recorded once from the quota page since a `Statement` names
  one page (https://github.com/xippios/sdk-google-mail/issues/72).
- `tests/test_refresh_upstream.py`: its five tests,
  `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
  `test_fetched_md_has_no_row_of_observed_md_while_there_is_none`,
  `test_fetched_md_cites_the_standing_record_of_sdk_core`,
  `test_a_snapshot_leaves_observed_md_as_written_and_check_reads_it` and
  `test_no_page_is_kept_as_observed_md`, go with the copy
  (https://github.com/xippios/sdk-core/issues/415).
- Its rule on a linked statement stays, with no hook of its own: the frame reads past "Terms of
  Service" only as the text of a link to one of its three recorded targets, on any of its
  pages, as its script did, and searches its discovery document, which is no HTML, for those
  words (ADR-0046, decision 7; https://github.com/xippios/sdk-google-mail/issues/72).
- No paged cap: `get_thread` keeps its `start` and `get_message` is one record
  (https://github.com/xippios/sdk-google-mail/issues/38).
- Before the adoption, in a pull request of its own: its recorder writes `REDACTED` for `raw`
  in a write's request body, where it dropped the key, and records `send_message/ok.json` and
  `create_draft/ok.json` again with it, a keyed run on the demo mailbox that needs the
  maintainer's go and a budget, so that core's census compares the four tests that replay them
  with their recordings key by key (ADR-0048, decision 7;
  https://github.com/xippios/sdk-core/issues/439). At the adoption, its recorder tests mark
  the exchanges of their four helpers with the input's sentence, in each helper's docstring or
  at the calls (ADR-0049, decision 10).
- The first list: what a write task's preview shows.

### sdk-faostat

- Changes, items 3 and 4:
  - `tasks.py`: `_check_codes` → `check(dimension, code, reason=...)` on a declaration with
    `list_name=` of its table (https://github.com/xippios/sdk-core/issues/313);
    `names_codes(area=..., separator=",")` on `get_series`, over its five area tables, which
    agree on every name they share, and `get_data`'s `area` and `area_cs` in `UNNAMED_CODES`
    with their reasons, since under `area_cs` an M49 code can be an FAO code of another
    country, until https://github.com/xippios/sdk-faostat/issues/34 decides
    (https://github.com/xippios/sdk-core/issues/316); `paged=True` for `get_data`, `list_items`
    and the other list tools and `keep="last"` for `get_series`, the notes that named
    `page_number` or a raised bound shrinking to the filters
    (https://github.com/xippios/sdk-faostat/issues/32), and where `list_domains` is paged,
    `tests/test_contract.py`'s `test_a_tool_refuses_an_argument_it_does_not_declare` reads
    that it takes `search, offset`, as the refusal names a paged tool's `offset`
    (https://github.com/xippios/sdk-cashctrl/issues/134); whether `get_data` counts with
    `no_records=true` against a limit of its own is its patch's
    (https://github.com/xippios/sdk-faostat/issues/35);
  - `tests/test_live.py`: the removed-codes assertion of `test_list_elements` goes, and
    `element_QCL` stands in `LIVE_LISTS` with its fetch, each of its fourteen other tables
    there, 14 more keyed requests a night, or in `NO_LIVE_LIST` with its reason
    (https://github.com/xippios/sdk-core/issues/319);
  - `tests/test_refresh_upstream.py`: `test_every_file_a_note_cites_exists` and the label and
    date of its probe test, `test_every_note_ends_with_its_probe_its_date_and_its_operation`,
    go, its operation staying (https://github.com/xippios/sdk-core/issues/348);
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none`,
    `test_fetched_md_cites_the_standing_record_of_sdk_core`,
    `test_a_snapshot_leaves_observed_md_as_written_and_check_reads_it`,
    `test_a_page_left_out_has_a_row_in_not_fetched`, `test_a_rows_etag_stands_in_a_code_span`,
    and the comparisons `test_the_committed_fetched_md_is_the_scripts_text`, whose row of
    `OBSERVED.md` the family check holds, and `test_the_committed_etags_are_the_renderers_cells`
    go with the copy, the family check's `test_family_fetched_md_agrees_with_the_snapshot`
    holding the file's prose, its rows and the form of each ETag's cell from the first run of the
    ported script that fetches (https://github.com/xippios/sdk-core/issues/428);
    `test_the_script_keeps_no_observed_notes` and
    `test_every_page_the_documentation_links_is_fetched_or_not_fetched` stay, reading its
    `Snapshot` and its `note` (https://github.com/xippios/sdk-core/issues/415);
  - `scripts/refresh_upstream.py` ported with `credentials` and its samples `keyed`, `reduce`,
    `note` and `canonical` (https://github.com/xippios/sdk-core/issues/320), its check that
    the `info` of its OpenAPI document, which is YAML and which the frame does not parse,
    names no licence, terms of service or contact kept in one of its hooks, and
    `scripts/refresh_reference.py` to fifteen `Listed` of `getCodeList`, each with its origin,
    the operation and its path, its count of logins kept around the call
    (https://github.com/xippios/sdk-core/issues/321).
- `get_series` withholds the answer for a code of a domain outside its five area tables, which
  it sent unchecked: a refusal its callers see, as the first list's second change says.
- Its check of the order of `since` and `until` stays its own
  (https://github.com/xippios/sdk-faostat/issues/33; ADR-0054, Consequences).
- The first list: the rest of a cut answer, the name of each country code, one check of an
  argument, and the refusal after one count where its patch takes it.

### sdk-x

- Changes, items 3 and 4: `scripts/record_fixture.py` deletes the client built with
  `RetryPolicy(max_attempts=1)`, `exchange`, `survivors`, `_strings`, `_masked` and its calls of
  `fixture_from_response` and `write_fixture`, and records with `record_sync(client, ...,
  rewrite=step)`, the step running `unknown_answered`, `rewrite` and the 256 KiB test and
  returning the values `rewrite` replaced, stripped; the two tests of `survivors` in
  `tests/test_record_fixture.py` assert core's refusal, which names the place, `response body`
  (https://github.com/xippios/sdk-core/issues/322, https://github.com/xippios/sdk-x/issues/38).
  A replaced value found only inside a placeholder that its step wrote, `rewritten` inside
  `[name rewritten]`, is refused, where sdk-x wrote it: such a recording is narrowed, or the
  step leaves the value out of what it returns (ADR-0048, Consequences).
- `scripts/refresh_upstream.py` ported with `canonical` for its scope lists and `reduce`
  (https://github.com/xippios/sdk-core/issues/320), its check of each Markdown page's first
  level-one heading and of the document's `info.title` reading a table of its own, `TITLES`, and
  `SPEC_TITLE` in `reduce`, since core's `Page` holds no title. Its attribution records the
  OpenAPI document's `info.contact` as a `Statement` from the document, its name
  `X Developers` the text and https://developer.x.com/ the link, or the frame stops the run.
  The page it read for its site
  footer alone, https://docs.x.com/x-api/introduction, is searched whole, since the frame has
  no hook for a part of a page, and is declared without a file and with `stable=False`, its row
  keeping no size, sha256 or ETag where the script kept the footer text's; only the first run
  that fetches shows whether its whole visible text passes the search
  (https://github.com/xippios/sdk-x/issues/57).
- Its rule on a linked statement stays, with no hook of its own: the frame reads past "Terms of
  Service" only as the text of the footer's link to https://x.com/en/tos, and searches its
  Markdown pages, which are no HTML, for those words, as its script did (ADR-0046, decision 7;
  https://github.com/xippios/sdk-x/issues/57).
- `tests/test_refresh_upstream.py`: its five tests,
  `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
  `test_fetched_md_has_no_row_of_observed_md_while_there_is_none`,
  `test_fetched_md_cites_the_standing_record_of_sdk_core`,
  `test_a_snapshot_leaves_observed_md_as_written_and_check_reads_it` and
  `test_no_page_is_kept_as_observed_md`, go with the copy
  (https://github.com/xippios/sdk-core/issues/415).
- No paged cap, since X bills every page that a second run fetches
  (https://github.com/xippios/sdk-x/issues/35), and nothing of `record_task`, since each of its
  seven tasks makes one call (ADR-0057, Consequences).
- The first list: none of its changes.

### sdk-eurostat

- Changes, items 3 and 4:
  - `tasks.py`: `_labels` and `_check_code` → `check(param, value, hints=..., reason=...)` on a
    declaration with `list_name=` of its codelist
    (https://github.com/xippios/sdk-core/issues/313), the refusal of its one hint, a product
    that another dataset lists and whose hint says where it is, leaving out that the packaged
    list is out of date, as every value of a hint table's does, so
    `tests/test_tasks.py`'s `test_get_total_production_refuses_a_product_its_list_lacks` asserts
    the message without it (ADR-0045, decision 3, amended 2026-11-22;
    https://github.com/xippios/sdk-core/issues/440); `names_codes(reporters=COUNTRIES,
    partners=COUNTRIES)` on `get_trade`, `get_trade_hs` and `download_trade` and
    `names_codes(reporters=COUNTRIES)` on `get_sold_production` and `get_total_production`,
    `COUNTRIES` declared from `cxt_free_iso` by `code` and `label`, a country inside
    `get_data`'s `filters` unnamed until https://github.com/xippios/sdk-eurostat/issues/52
    decides (https://github.com/xippios/sdk-core/issues/316); `paged=True, keep="last"` for
    `get_series` and `paged=True` for `get_data` where its answer is a list of rows or a model
    of one list (https://github.com/xippios/sdk-eurostat/issues/51);
  - `_client.py`: whether `classify` maps upstream's refusal over its limit to `QueryTooLarge`,
    with the count and the limit read from it, or a task raises it before the request with
    `bound=True`, is its patch's (https://github.com/xippios/sdk-eurostat/issues/53);
  - `docs/upstream/FETCHED.md`: the row of `OBSERVED.md`, which the family check asks from the
    lock's move and which its capture script writes at its next run (ADR-0044, decision 4;
    https://github.com/xippios/sdk-eurostat/issues/49). On its `main` of 2026-11-20
    `docs/upstream/OBSERVED.md` exists, added that day, and `FETCHED.md`, last written on
    2026-10-28, has no row of it. Its present script, the copy and not the port, appends
    `| OBSERVED.md | - | - | - | - | written by hand: what upstream does but never documents;
    not fetched or checked |` wherever the file exists, and `tests/test_refresh_upstream.py`
    holds that row: its first cell is the file's name, its four cells between are `-` and its
    last cell says that the file is written by hand, so the family check passes it. A refresh
    by that script, in a pull request of its own before the adoption PR, writes the row; the
    adoption PR then meets the check and fetches nothing (§15), and the first fetching run of
    the ported script writes `FETCHED.md` again in the frame's form;
  - `tests/test_live.py`: its nineteen packaged lists in `LIVE_LISTS`, 15 more files a night,
    or in `NO_LIVE_LIST` with their reasons (https://github.com/xippios/sdk-core/issues/319);
  - `scripts/refresh_upstream.py` ported with `quota_wait`, `keep_recorded` with `canonical`
    for its WADL, `pause=5.0` and `reduce` (https://github.com/xippios/sdk-core/issues/320),
    and `scripts/refresh_reference.py` to nineteen `Listed`, `lists.json` and the samples
    written in `after`, `--samples` and `--only` by a codelist's id read before the call, its
    empty `enums.py` as committed, `tests/test_refresh_reference.py` keeping the tests of its
    own fetches (https://github.com/xippios/sdk-core/issues/321);
  - `tests/test_refresh_upstream.py`: its two tests,
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own` and
    `test_fetched_md_names_no_observed_md_while_there_is_none`, go with the copy in the adoption
    PR, after the refresh by its present script above, whose row they hold
    (https://github.com/xippios/sdk-core/issues/415).
- The first list: the rest of a cut answer, the name of each country code, one check of an
  argument, and the refusal after one count where its patch takes it.

### sdk-comtrade

- Changes, items 3 and 4:
  - `params.py`: `_resolve_iso3` and the alpha-3 branch of `_resolve_area` → the refusal of
    `check` with a hint table keyed by the alpha-3 codes of `Reporters` and `partnerAreas`,
    each naming its code, a breaking change that makes its release a minor
    (https://github.com/xippios/sdk-core/issues/375,
    https://github.com/xippios/sdk-comtrade/issues/37), the refusal of a value of that table
    ending with its hint and its reason and leaving out that the packaged list may be out of
    date, since an alpha-3 code is no code of upstream's (ADR-0041, decision 8, and ADR-0045,
    decision 3, each amended 2026-11-22; https://github.com/xippios/sdk-core/issues/430); another
    text given for an area, such as `"US"` for a partner, is asked of the `closest=` strategy
    that the port passes to that `check`, which names `842 (USA)` where it reads the list's ISO
    alpha-2 codes and takes a text, and without one core names the codes whose name holds the
    text, `"US"` naming `36 (Australia), 40 (Austria), 112 (Belarus)` (ADR-0045, decision 4,
    amended 2026-11-22; https://github.com/xippios/sdk-core/issues/418,
    https://github.com/xippios/sdk-core/issues/440,
    https://github.com/xippios/sdk-comtrade/issues/60); the `UnknownCode` branches of
    `_check_list` and `_check_areas` → `check`, with `fold_case=True` for `customsCode` and
    without it for `motCode`, the area codes converted to integers first, while an unknown
    `flowCode`, which upstream refuses with HTTP 400, stays one of the problems gathered into
    one `InvalidRequestError` (https://github.com/xippios/sdk-core/issues/313,
    https://github.com/xippios/sdk-comtrade/issues/60);
  - `tasks.py`: `names_codes(..., separator=",")` on seven tasks and `names_codes(...)` on the
    four slice tasks, every reporter parameter with `Reporters` and every partner parameter
    with `partnerAreas` (https://github.com/xippios/sdk-core/issues/316); the gate of `get_data`
    → `fetch_counted(count, fetch, limit=RECORD_LIMIT, empty=[], narrow=..., source=SOURCE)`
    and `_bounded` → core's `QueryTooLarge(bound, limit=RECORD_LIMIT, narrow=..., bound=True,
    source=SOURCE)` (https://github.com/xippios/sdk-comtrade/issues/38); `paged=True` for
    `get_world_trade`, `get_data`, `get_data_availability`, `get_bilateral_data` and
    `get_mirror_flows` (https://github.com/xippios/sdk-comtrade/issues/35); its ceiling stays in
    `validate_slice`, and `fetch_periods` over its chunks of 12 is its patch's choice
    (https://github.com/xippios/sdk-comtrade/issues/36);
  - `errors.py`: `QueryTooLarge` deleted from the module and its `__all__`, `RECORD_LIMIT` and
    `MAX_PERIODS` kept, and its two pieces of advice passed as `narrow`
    (https://github.com/xippios/sdk-core/issues/317);
  - `tests/test_tasks.py`, `tests/test_live.py` and `README.md`: every alpha-3 code given to a
    slice task becomes its numeric code, `"757"` and `"842"` among them
    (https://github.com/xippios/sdk-core/issues/375), the error is built with `limit=` and
    `narrow=` from `xippios.core` (https://github.com/xippios/sdk-core/issues/317), and
    `tests/test_live.py` declares `Reporters`, `partnerAreas`, `motCode` and `ListofReferences`
    in `LIVE_LISTS` and each of its eleven other lists there or in `NO_LIVE_LIST`, the four
    taken from the specification in `NO_LIVE_LIST`, each list fetched from
    `api.reference_rows` and read through its model, as `scripts/refresh_reference.py` writes
    it, and not compared as the payload, whose `id` stands where the packaged `motCode` list
    has `motCode` and whose `"True"` the packaged `TradeDataItems` holds as `true`
    (https://github.com/xippios/sdk-core/issues/319,
    https://github.com/xippios/sdk-comtrade/issues/60);
  - `scripts/refresh_upstream.py` ported with `linked`, `reduce`, `note` for the note that each
    article's and product file's answer gives, which stops the run where an article's
    `data-wp-key` image id comes or goes against its declared stability, and `sections`
    (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-comtrade/issues/60), and `scripts/refresh_reference.py` to
    fifteen `Listed` with the origins that its README keeps by hand and
    `packaged=[*PACKAGED_LISTS, *PACKAGED_TABLES]`, its `tests/test_scripts.py` reading the
    frame's usage and `--render-only` (https://github.com/xippios/sdk-core/issues/321);
  - `tests/test_refresh_upstream.py`: its three tests,
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none` and
    `test_a_snapshot_leaves_observed_md_as_written`, go with the copy
    (https://github.com/xippios/sdk-core/issues/415).
- Its release is a minor, by its refusal of alpha-3 codes and the removal of its own
  `QueryTooLarge` from `xippios.comtrade.errors` (§12), and its adoption's fragment is
  `changed` all the same, since the adoption brings no core minor (§15 item 9; ADR-0043,
  decision 3).
- The first list: its alpha-3 codes, the name of each country code, the refusal after one
  count with the removal of its own class, the rest of a cut answer, one check of an argument,
  and a series over periods where its patch takes `fetch_periods`.

### sdk-usda-psd

- Changes, items 3 and 4:
  - `params.py`: `_codes` and `_validate_code` → a declaration per list and `check(param,
    value, hints=COUNTRY_HINTS, reason=...)`, and `validate_attribute_id` → `check` on the
    integer list (https://github.com/xippios/sdk-core/issues/313), its refusals of `"all"` and
    `"00"`, the values of `COUNTRY_HINTS`, leaving out that the packaged list is out of date
    (ADR-0045, decision 3, amended 2026-11-22;
    https://github.com/xippios/sdk-core/issues/440);
  - `tasks.py`: `names_codes(country_code=COUNTRIES)` on `get_balance_sheet`, `get_data`,
    `get_release_dates` and `get_time_series`, `COUNTRIES` declared from `countries` by
    `countryCode` and `countryName` (https://github.com/xippios/sdk-usda-psd/issues/21); the
    ceiling of `get_time_series` → `Ceiling(100, unit="market years", source=SOURCE)` and its
    loop → `fetch_periods(..., skip=(NoDataForYear,))`
    (https://github.com/xippios/sdk-usda-psd/issues/32); the `since` test of
    `get_release_dates` and the check of `get_latest_release` → `newer_than(since, ...,
    released=_release, read=validate_since)`, its wording unchanged
    (https://github.com/xippios/sdk-usda-psd/issues/33); `paged=True` for `get_latest_release`,
    `get_data`, `get_release_dates` and `get_time_series`, and `keep="last"` for the two ordered
    oldest first where its patch keeps the newest
    (https://github.com/xippios/sdk-usda-psd/issues/31), so in `tests/test_tasks.py`
    `test_the_adapters_refuse_a_bad_argument_before_the_task_runs` reads that `get_data` takes
    `commodity_code, market_year, country_code, offset`, as the refusal names a paged tool's
    `offset` (https://github.com/xippios/sdk-usda-esr/issues/59);
  - `tests/test_live.py`: `LISTS` and `test_packaged_list_equals_the_live_list` →
    `commodities`, `commodityAttributes`, `countries`, `regions` and `unitsOfMeasure` in
    `LIVE_LISTS` (https://github.com/xippios/sdk-core/issues/319); `tests/test_slices.py`: the
    refusals of a range over the ceiling in core's wording, and
    `test_a_series_may_span_exactly_the_bound`, which lowers the ceiling by patching
    `SERIES_MAX_YEARS`, sets the `Ceiling` instead, the source having neither a setter nor an
    option (https://github.com/xippios/sdk-core/issues/315,
    https://github.com/xippios/sdk-usda-esr/issues/59);
  - `scripts/refresh_upstream.py` ported with `note`, `linked`, `reduce` and `sections` for how
    its parts of the two documents compare, which its `FETCHED.md` prints and which needs both
    rows, as only `sections` is given them (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-usda-esr/issues/59), and `scripts/refresh_reference.py` to
    five `Listed`, each with its origin made from the list, gaining `--only` and the count of
    its requests (https://github.com/xippios/sdk-core/issues/321);
  - `tests/test_refresh_upstream.py`: `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none` and
    `test_a_snapshot_leaves_observed_md_as_written` go with the copy, and
    `test_fetched_md_says_when_and_where_the_portal_document_was_found` stays, reading the
    `capture` of its `Snapshot` (https://github.com/xippios/sdk-core/issues/415).
- Its own: `list_countries(region_code=...)`, whose value its row refuses through the check
  (https://github.com/xippios/sdk-usda-psd/issues/30).
- The first list: the name of each country code, the rest of a cut answer, one check of an
  argument and a series over periods.

### sdk-usda-esr

- Changes, items 3 and 4:
  - `params.py`: `_codes` and `_validate_code` → a declaration per list and `check(param,
    value, closest=_closest, reason=_REASON)`, `_closest` taking a `Mapping` and a text, which
    core now asks it for as well, and returning no pair for a text, so that core names the
    codes by name (ADR-0045, decision 4, amended 2026-11-22;
    https://github.com/xippios/sdk-core/issues/418,
    https://github.com/xippios/sdk-core/issues/440), and the tests of a text given for an
    integer code taking core's wording, which ends with `_REASON`
    (https://github.com/xippios/sdk-core/issues/313,
    https://github.com/xippios/sdk-core/issues/432);
  - `tasks.py`: `names_codes(country_code=COUNTRIES)` on `get_exports` and
    `get_weekly_series`, `COUNTRIES` declared from `countries` by `countryCode` and
    `countryDescription` (https://github.com/xippios/sdk-usda-esr/issues/30); the ceiling of
    `_series_range` → `Ceiling(10, unit="market years", source=SOURCE)` and the loop of
    `get_weekly_series` → `fetch_periods(..., skip=(NoDataForYear,))`
    (https://github.com/xippios/sdk-usda-esr/issues/29); `_since` and `_SINCE_EXAMPLE` →
    `read_since = partial(naive_time, source=SOURCE)` and `newer_than(...)`
    (https://github.com/xippios/sdk-usda-esr/issues/31); `paged=True, keep="last"` for
    `get_exports` and `keep="last"` alone for `get_weekly_series`, which stays unpaged since a
    second run spends up to 11 requests (https://github.com/xippios/sdk-usda-esr/issues/28);
  - its tests: `tests/test_tasks.py` asserts the refusals of `since` in core's wording, and
    `test_the_adapters_refuse_a_bad_argument_before_the_task_runs` that `get_exports` takes
    `commodity_code, market_year, country_code, offset`
    (https://github.com/xippios/sdk-core/issues/318,
    https://github.com/xippios/sdk-usda-esr/issues/59); `tests/test_slices.py` asserts the
    refusals of a range over the ceiling in core's wording, and
    `test_the_ceiling_counts_market_years_ends_included`, which lowers the ceiling by patching
    `SERIES_MAX_YEARS`, sets the `Ceiling` instead, the source having neither a setter nor an
    option (https://github.com/xippios/sdk-core/issues/315,
    https://github.com/xippios/sdk-usda-esr/issues/59); `tests/test_live.py`'s `LISTS` and its
    test → `commodities`, `countries`, `regions` and `unitsOfMeasure` in `LIVE_LISTS`
    (https://github.com/xippios/sdk-core/issues/319); `tests/test_observed.py` loses what the
    family check holds, `test_fetched_md_lists_observed_md_in_a_row_of_its_own` whole, since
    its sentence "Nothing here was edited by hand" is the copy's and the first run of the
    ported snapshot script words it as the frame does
    (https://github.com/xippios/sdk-core/issues/348,
    https://github.com/xippios/sdk-core/issues/428);
  - `scripts/refresh_upstream.py` ported with `note`, `linked`, `reduce` and `sections` for how
    its parts of the two documents compare, which its `FETCHED.md` prints and which needs both
    rows, as only `sections` is given them (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-usda-esr/issues/59), and `scripts/refresh_reference.py` to
    four `Listed`, each with its origin made from the list, with
    `quota_header="x-ratelimit-remaining"`, `tests/test_params.py` reading the port's `Listed`
    endpoints (https://github.com/xippios/sdk-core/issues/321);
  - `tests/test_refresh_upstream.py`: `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none`,
    `test_fetched_md_cites_core_s_standing_record`,
    `test_a_snapshot_leaves_observed_md_as_written` and the comparison
    `test_the_committed_fetched_md_is_the_scripts_text` go with the copy, but for the
    assertion of `test_a_snapshot_leaves_observed_md_as_written` that `document_row`'s cut
    gives back the committed part, which is its `reduce`'s and stays with that hook, the family
    check's `test_family_fetched_md_agrees_with_the_snapshot` holding the file from the first
    run of the ported script that fetches, where the bundle's name in a note that `note` makes
    and the rows of the pages that `linked` finds are read back
    (https://github.com/xippios/sdk-core/issues/428); and
    `test_fetched_md_says_when_and_where_the_portal_document_was_found` stays, reading the
    `capture` of its `Snapshot` and the script (https://github.com/xippios/sdk-core/issues/415).
- Its own: `list_countries(region_id=...)`, whose value its row refuses through the check
  (https://github.com/xippios/sdk-usda-esr/issues/27).
- The first list: the name of each country code, the rest of a cut answer, one check of an
  argument, a `since` that takes back a vintage, and a series over periods.

### sdk-usda-gats

- Changes, items 3 and 4:
  - `params.py`: `_codes`, `validate_country_code` and `validate_customs_district_id` →
    `check(param, value, closest=..., otherwise=..., reason=...)`
    (https://github.com/xippios/sdk-core/issues/313);
  - `tasks.py`: `names_codes(partner_code=COUNTRIES)` on the six Census tasks and the three
    customs-district tasks, `names_codes(reporter_code=COUNTRIES, partner_code=COUNTRIES)` on
    `get_un_exports`, `get_un_imports` and `get_un_reexports`, and
    `names_codes(reporter_code=COUNTRIES)` on `get_un_release_dates`
    (https://github.com/xippios/sdk-usda-gats/issues/34); `series_ceiling`,
    `set_series_ceiling`, `mcp_add_options`, `mcp_apply_options` and the span check of
    `_series_months` → one `Ceiling(60, unit="months", mcp=24, option="--series-months",
    help=..., source=SOURCE)`, its two hooks under the two names, and the month loop of
    `_series` → `fetch_periods` (https://github.com/xippios/sdk-usda-gats/issues/33), the
    removal of `series_ceiling` and `set_series_ceiling`, which its changelog and its README
    name, taking a `breaking` entry unless the port keeps the two names, as the first list's
    seventh change says; `paged=True` for its sixteen cut tools and `keep="last"` for the three
    series tools, each continuation downloading the answer again
    (https://github.com/xippios/sdk-usda-gats/issues/32);
  - its tests: `tests/test_live.py`'s `_keyed`, `LISTS` and its test → five lists in
    `LIVE_LISTS` (https://github.com/xippios/sdk-core/issues/319); `tests/test_tasks.py`: the
    ceiling's refusals in core's wording (https://github.com/xippios/sdk-core/issues/315), and,
    where `list_countries` is paged,
    `test_a_tool_error_answer_is_flagged_and_an_undeclared_argument_refused` reads that it
    takes `region_code, search, offset`, as the refusal names a paged tool's `offset`
    (https://github.com/xippios/sdk-usda-nass/issues/86);
  - `scripts/refresh_upstream.py` ported with `note`, `linked`, `reduce` and `sections` for how
    its parts of the two documents compare, which its `FETCHED.md` prints and which needs both
    rows, as only `sections` is given them (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-usda-esr/issues/59), and `scripts/refresh_reference.py` to
    five `Listed`, each with its origin made from the list, since its rows name the request and
    the operation where the list's endpoint is the operation alone
    (https://github.com/xippios/sdk-core/issues/321);
  - `tests/test_refresh_upstream.py`: `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none`,
    `test_fetched_md_cites_the_standing_record_of_sdk_core` and
    `test_a_snapshot_leaves_observed_md_as_written` go with the copy, and
    `test_fetched_md_says_when_and_where_the_portal_document_was_found` stays, reading the
    `capture` of its `Snapshot` (https://github.com/xippios/sdk-core/issues/415).
- Its own: `list_countries(region_code=...)` and `list_commodities(product_type=...)`, whose
  values its row refuses through the check (https://github.com/xippios/sdk-usda-gats/issues/31).
- The first list: the name of each country code, the rest of a cut answer, one check of an
  argument and a series over periods.

### sdk-usda-nass

- Changes, items 3 and 4:
  - `params.py`: `_packaged` and `_check_value` → a declaration per parameter with
    `fold_case=True` and `check(param, value, otherwise=..., reason=...)`
    (https://github.com/xippios/sdk-core/issues/313);
  - `errors.py`: `QueryTooLarge` → a subclass of core's that keeps `year`, words it in
    `narrow` and passes `request` on; `_client.py`'s 413 → `QueryTooLarge(None,
    request=request_description(response))`; `tasks.py`'s gate of `get_data` → `fetch_counted`
    in a `try` that splits by year on a counted refusal and passes an error with a count of
    `None` as raised (https://github.com/xippios/sdk-usda-nass/issues/57);
  - `tasks.py`: `split_ceiling`, `set_split_ceiling`, `mcp_add_options`, `mcp_apply_options` and
    the check of `_split_by_year` → one `Ceiling(20, unit="years", mcp=5,
    option="--split-years", help=..., source=SOURCE)` and its two passes → `fetch_periods`
    (https://github.com/xippios/sdk-usda-nass/issues/56); the two-sided split takes
    `Ceiling.check` before any call, while on the split of `year__GE` alone, which checks the
    range after its count of the whole range, the port words a refusal of its own that says
    that the count was sent and no data was fetched, where core's says that nothing was sent,
    and `test_split_of_year_ge_alone_refuses_more_than_twenty_years_after_the_first_count`
    asserts the source's refusal, not core's (https://github.com/xippios/sdk-core/issues/454);
    the removal of `split_ceiling` and `set_split_ceiling`, which its 0.2.0 entry named, taking
    a `breaking` entry unless the port keeps the two names, as the first list's seventh change
    says (https://github.com/xippios/sdk-usda-nass/issues/86); `paged=True` for
    `list_param_values`, `get_data` unpaged, and `get_county_yield`, `get_county_production`
    and `get_census_farms` paged only where one run is one keyed call
    (https://github.com/xippios/sdk-usda-nass/issues/55);
  - its tests: `tests/test_tasks.py` asserts core's prefix `query would return 57,873,464
    records` and the ceiling's wording (https://github.com/xippios/sdk-core/issues/317,
    https://github.com/xippios/sdk-core/issues/315), and
    `test_a_tool_error_answer_is_flagged_and_an_undeclared_argument_refused` that
    `list_param_values` takes `param, offset`, as the refusal names a paged tool's `offset`
    (https://github.com/xippios/sdk-usda-nass/issues/86); `tests/test_live.py` declares the nine
    lists of `PACKAGED_PARAMS` in `LIVE_LISTS`, 9 keyed requests a night, or in
    `NO_LIVE_LIST`, and the derived `progress_stages` and `condition_categories` in
    `NO_LIVE_LIST` (https://github.com/xippios/sdk-core/issues/319);
  - `scripts/refresh_upstream.py` ported with `reduce` and a `vocabulary`, the phrases in which
    its api page prints "Terms of Service" or "terms and conditions" and states nothing new:
    the frame's search reads "terms and conditions", which the terms on that page print twice,
    and matches visible text alone, where the script took three references to its terms out by
    their markup, so the label of the Terms of Service tab is named with its neighbours' text,
    which only the first run that fetches confirms (https://github.com/xippios/sdk-core/issues/320,
    https://github.com/xippios/sdk-usda-nass/issues/86), and `scripts/refresh_reference.py` to
    eleven `Listed`, each with its origin, `GET /api/get_param_values?param=<param>` for the
    nine parameter lists and the query of each derived list, or `--render-only` rewrites the
    eleven rows of `reference/README.md` to the bare endpoint, `columns.csv` parsed in `before`
    and written in `after` on a full run and its read timeout set around the call
    (https://github.com/xippios/sdk-core/issues/321,
    https://github.com/xippios/sdk-usda-nass/issues/86);
  - `tests/test_refresh_upstream.py`: its four tests,
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none`,
    `test_fetched_md_cites_the_standing_record_of_sdk_core` and
    `test_a_snapshot_leaves_observed_md_as_written_and_check_reads_it`, go with the copy
    (https://github.com/xippios/sdk-core/issues/415).
- The first list: the refusal after one count, the rest of a cut answer, one check of an
  argument and a series over periods.

### sdk-usda-esmis

- Changes, items 3 and 4: `tasks.py`'s check of `agency_acronym` in `list_publications` →
  `check("agency_acronym", agency_acronym, reason=...)`
  (https://github.com/xippios/sdk-core/issues/313), and `paged=True` for `list_publications`,
  which reads the packaged table, the three tools that take `page` left as they are
  (https://github.com/xippios/sdk-usda-esmis/issues/34); `params.py` declares `PACKAGED_TABLES
  = ("agency", "publication")` (https://github.com/xippios/sdk-core/issues/321);
  `tests/test_live.py`'s `test_the_packaged_agency_table_matches_upstream_live` → `agency` in
  `LIVE_LISTS` with `api.agency_find_all`, and `publication` in `LIVE_LISTS`, at 101 requests a
  fetch, or in `NO_LIVE_LIST` (https://github.com/xippios/sdk-core/issues/319);
  `tests/test_observed.py` loses what the family check holds
  (https://github.com/xippios/sdk-core/issues/348).
- `scripts/refresh_upstream.py` ported with `linked` and `reduce`, its followed redirect to
  another host recorded by its status (https://github.com/xippios/sdk-core/issues/320), its
  check that the `info` of its OpenAPI document, which is YAML and which the frame does not
  parse, names no licence, terms of service or contact kept in one of its hooks, and
  `scripts/refresh_reference.py` to two `Listed`, each with its origin made from the list and
  its note, gaining `--only`, `--render-only` and the count of its requests
  (https://github.com/xippios/sdk-core/issues/321).
- `tests/test_refresh_upstream.py`: its three tests,
  `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
  `test_fetched_md_names_no_observed_md_while_there_is_none` and
  `test_a_snapshot_leaves_observed_md_as_written`, go with the copy
  (https://github.com/xippios/sdk-core/issues/415).
- Its own: `since` and `until` as an inclusive range (ADR-0052;
  https://github.com/xippios/sdk-usda-esmis/issues/35).
- The first list: the rest of a cut answer and one check of an argument.

### sdk-usda-wasde

- Changes, items 3 and 4: `tasks.py`'s refusals of `table` and `commodity` → `check(param,
  value, closest=..., reason=...)` (https://github.com/xippios/sdk-core/issues/313);
  `tests/test_live.py`'s `vocabulary.differences` → `assert_list_current(codes, current,
  packaged=...)`, with `table`, `commodity`, `region` and `attribute` in `NO_LIVE_LIST`, and
  `_vocabulary.py`'s `differences` deleted (https://github.com/xippios/sdk-core/issues/319);
  `tests/test_observed.py` loses what the family check holds
  (https://github.com/xippios/sdk-core/issues/348); `scripts/cut_sample.py`'s `fetch` sends
  with `send_once(AsyncClient(config), chosen.url)` and keeps its refusal of every status but
  200 (https://github.com/xippios/sdk-core/issues/281,
  https://github.com/xippios/sdk-usda-wasde/issues/29).
- `scripts/refresh_upstream.py` ported with `origin` for USDA's CDN origin, `linked` and
  `reduce` (https://github.com/xippios/sdk-core/issues/320), its check of the `<h1>` of each
  page's `<main>` against the page's title, which core's `Page` does not hold, reading a table
  of its own in `reduce`, the release page that `linked` makes keyed by its file, since its
  URL changes with every release (https://github.com/xippios/sdk-google-mail/issues/72), and
  `scripts/refresh_reference.py` to four `Listed` built from one download through
  xippios-usda-esmis, whose client it passes to `run`, each with its origin made from its
  list's note, gaining `--only`, `--render-only` and the count of its requests
  (https://github.com/xippios/sdk-core/issues/321).
- `tests/test_refresh_upstream.py` (https://github.com/xippios/sdk-core/issues/415):
  - `test_the_notes_written_by_hand_are_observed_md`,
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own`,
    `test_fetched_md_names_no_observed_md_while_there_is_none`,
    `test_a_snapshot_leaves_observed_md_as_written`,
    `test_a_page_left_out_has_a_row_in_not_fetched` and the comparison
    `test_the_committed_fetched_md_carries_the_renderers_table_and_prose`, whose row of
    `OBSERVED.md` the family check holds, go with the copy, but for the line of the second and
    third that the text names no `layout.md`, the notes' former name, which reads its own text
    and stays with the tests of its `capture`; the family check's
    `test_family_fetched_md_agrees_with_the_snapshot` holds the table `Not fetched` and the
    prose from the first run of the ported script that fetches, the row of its CDN origin's 403
    and the rows of the pages that `linked` finds read back
    (https://github.com/xippios/sdk-core/issues/428);
  - `test_fetched_md_lists_no_page_left_out_in_prose`,
    `test_every_row_of_not_fetched_gives_its_reason`, `test_no_url_of_not_fetched_holds_a_space`,
    `test_every_page_the_snapshot_links_is_fetched_or_not_fetched` and
    `test_every_row_of_not_fetched_is_a_page_the_snapshot_links` stay, reading its `Snapshot`,
    its `capture` and its `not_fetched`;
  - the fourth of those reads the committed table through `recorded()`, which takes a row of
    nine cells and skips any other, and once the frame writes `FETCHED.md` each row with an
    ETag ends in the allowlist mark (ADR-0046, decision 4), so the adoption makes `recorded()`
    read the first nine cells of a row that ends in the mark, which reads the copy's rows and
    the frame's alike.
- The first list: one check of an argument.

### xippios-mcp

- The host takes the first line of `publish.yml` by its copy of the file
  (https://github.com/xippios/sdk-core/pull/356, Consumers), and its adoption's fragment names
  the core bound and conventions 1.29 as they stand after it, and no template tag (§15;
  ADR-0043, decision 1). Where it adopts core 0.4.0 and 0.4.1 in one PR, the adoption brings a
  core minor, and its fragment is `breaking` (§15 item 9; ADR-0043, decision 3).

### sdk-template

sdk-template 0.4.1 follows core's tag and renders what the sources' adoption takes:

- `core_version=0.4.1`, the bound of item 1.
- The snapshot script and the reference refresh script that a new source starts from, short
  scripts on core's frames (ADR-0046 and ADR-0051, Consequences), the snapshot script naming
  its declaration `SNAPSHOT` at its top level and declaring no `linked` while it links no
  page, as the README's short script does, and its stub of `FETCHED.md` carrying no mark of the
  frame's form, so the family check passes a new source until its first refresh
  (ADR-0046, decision 6); of its
  `tests/test_capture.py`, the three tests of its command, its stub and its `CLAUDE.md` remain
  its own (https://github.com/xippios/sdk-core/pull/386, Consumers).
- `tests/test_built_answers.py` with the collecting line of the built-answer check
  (https://github.com/xippios/sdk-core/issues/344).
- The first line of `.github/workflows/publish.yml`, copied from core's
  (https://github.com/xippios/sdk-core/issues/323).
- `scripts/adr_index.py`, the version the organization's repositories share
  (https://github.com/xippios/sdk-template/issues/246).
- The rendered `ci.yml` comment on item 9, which still words the versions adopted
  (https://github.com/xippios/sdk-template/issues/251).
- `/release-prep` citing each live run's count of requests
  (https://github.com/xippios/sdk-template/issues/237).
- The command for a new task naming the check of an argument in place of an `UnknownCode`
  raised by hand (https://github.com/xippios/sdk-template/issues/250).
- A new source's `tests/test_live.py` and `/refresh-reference-data` taking the declarations of
  the live comparison (https://github.com/xippios/sdk-template/issues/252).
- `/record-fixture` naming `rewrite=`, `send_once` and the refusal of a 1xx or 3xx, where it
  sends through a client built for one attempt (https://github.com/xippios/sdk-core/pull/390,
  Consumers).
- `/refresh-upstream` worded for the ported script: its `Snapshot` run by core's frame, and the
  converter that its hooks use pinned in the dev group of `pyproject.toml` alone, where its
  rendered text at v0.4.0 still tells a source to declare it in the script's `# /// script`
  block, which the port drops (ADR-0046, decision 1;
  https://github.com/xippios/sdk-google-mail/issues/72).
- No test of its own for the row of `OBSERVED.md`, which core holds
  (https://github.com/xippios/sdk-template/issues/236,
  https://github.com/xippios/sdk-core/pull/383, Consumers).
