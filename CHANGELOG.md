# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) (pre-1.0: breaking changes bump the minor).

## [Unreleased]

### Removed

- **`xippios.core.config` and the `pydantic-settings` dependency** (ADR-0002, amendment
  2026-10-27; ADR-0023, decision 5; no consumer, counted by the family review of
  2026-10-25): `SourceSettings` goes; `resolve_api_key`, whose one caller was
  `EnvKeyAuth`, is folded into `xippios.core.client.auth` as a private helper with the
  same behaviour for that caller and the same `ConfigError` message. `pydantic` stays,
  `SecretStr` with it. Conventions 1.16 §7: the environment is read through the
  `EnvKeyAuth` helpers.
- **The sync `Client`** (ADR-0002 and ADR-0015, amendments 2026-10-27; no consumer):
  every source derives its sync task functions with `xippios.core.sync`, which stays.
  `xippios.core.client` no longer re-exports `UseClientDefault`, and core no longer
  imports it from httpx's private `httpx._client`: `auth=` keeps its three states on
  `AsyncClient.request`, `get` and `get_json` and on `record` and `record_sync` (the
  client's credentials by default, `None` for none, an `httpx.Auth` to replace them),
  its default now a sentinel of core's own.
- **`AsyncClient.derive`, the `limiter=` argument and the `limiter` property, and
  `retry=` and `timeouts=` on `record` and `record_sync`** (ADR-0015, amendment
  2026-10-27; the overrides queue row 12 asked for, found by sdk-comtrade; no source
  calls them): the rate limiter is built from `config.rate_limit` alone, and the testing
  plugin, which patches `TokenBucket.acquire`, needs neither. A recording goes through
  the client it is given; one that must not retry a 5xx records through a client whose
  config says `RetryPolicy(max_attempts=1)`. `auth=` per call stays: sdk-comtrade
  records its keyless reference files with it.
- **`paginate_pages` and `paginate_cursor`** (no consumer): `paginate_offset` keeps its
  signature, and its docstring shows how a page-numbered endpoint maps the offset to its
  page, `page = first_page + offset // page_size`. sdk-cashctrl, its one consumer, is
  unaffected.
- **26 names leave the export lists** (ADR-0023, decision 5: an `__init__.py` exports
  only what consumers import), each still importable from the module that defines it:
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot` and `load_csv` from `xippios.core`;
  `CacheBackend`, `EnvKeyAuth`, `QuotaSnapshot`, `WIRE_HEADERS`, `Params`, `TokenBucket`,
  `send_with_retries` and `strip_wire_headers` from `xippios.core.client`; `LIVE_ENV`,
  `PLACEHOLDER_KEY`, `FixtureRequest`, `live_enabled`, `mount_fixture`, `replay`,
  `write_fixture`, `scrub_headers`, `scrub_params` and `scrub_url` from
  `xippios.core.testing`; `is_write_server`, `quiet_request_logging` and
  `register_tasks` from `xippios.core.mcp`; `PROBLEM_MEDIA_TYPE`, `STATUS_BY_ERROR`,
  `install_error_handlers` and `problem_response` from `xippios.core.http`. With the
  six deleted names above, the five lists go from 113 entries (98 names) to 81 (69
  names). No source imports a removed name from a package.
- **`QuotaPolicy`'s `reset_header`, with the reset header's three formats** (the family
  review's C6; ADR-0015, amendment 2026-10-27; no source sets it, and api.data.gov sends
  no reset header): delay-seconds, epoch seconds and an HTTP-date are no longer read. A
  spent quota is back after a 429's `Retry-After`, the seconds `spent` names, or
  `window`, each cut to `window`.
- **`QuotaPolicy.mark_spent`** (C6; no caller): `spent=` stays, for an upstream that
  answers a spent limit with something other than a 429.
- **The per-config cap and the hook check of `QuotaPolicy.install`** (C6): `install` no
  longer binds the pause to each config's `retry.backoff_max` through a hook of its own,
  nor refuses with `ValueError` a config that has a `before_request` or `observe` hook of
  its own; `pause_cap=None` and the 30 s of a `before_request` called directly go with
  them (Changed, below).

### Changed

- **`pause_cap` is the one bound of a quota pause** (C6; ADR-0010, decision 4, and
  ADR-0015, amended 2026-10-27): 30.0 by default, the default `backoff_max`, whether
  `before_request` runs as the hook or is called directly; a config's
  `retry.backoff_max` bounds the retries alone.
- **`QuotaPolicy.install(config)` sets the policy's own hooks** (C6):
  `dataclasses.replace(config, before_request=policy.before_request,
  observe=policy.observe)`, reading nothing else from the config. Hooks the config had
  are replaced; a source that needs hooks of its own as well composes them itself.
  Installing again changes nothing. Since the hook is `before_request` itself, a
  subclass's override is called through it; the testing plugin still turns off the
  pause step alone.
- **The api.data.gov 429's wait comes from the quota snapshot** (queue row 30 c, found
  by sdk-usda-psd): the gateway's `classify` counts to `Gateway.policy.snapshot()`'s
  `resumes_at` on the policy's clock, since `observe` ran before it, instead of
  restating "`Retry-After`, else the window" as the three copies did; no
  `QuotaPolicy.wait_for` is added. Its message names the gateway's allowance, that every
  package using the key shares it, and the quota as the snapshot reports it, or the wait
  in seconds where no snapshot shows it spent, and no longer says what was retried: the
  retry loop's bound decides that.
- **`ResultCap` is defined in `xippios.core.models` and exported from `xippios.core`**
  (queue row 30 a, found by sdk-usda-psd; the per-tool cap of ADR-0016): a source's
  `tasks.py` declares its `MCP_CAPS` without the `mcp` extra and without the
  `ImportError` guard around the import. `xippios.core.mcp` keeps re-exporting it, and
  `cap_result` stays there.
- **`.claude/settings.json`** (queue row 31 b, found by sdk-template, which copies the
  file verbatim): `gh pr merge --auto` is allowed and `gh pr merge` is no longer denied,
  as in the workspace root's settings. A deny shadows every allow, so the session's one
  merge action, enabling auto-merge (ADR-0018, amendment (e)), was refused here.
- `gates.yml` calls the gates repository under its new name `xippios/sdk-gates` (renamed
  from `.github` on 2026-10-27).

### Added

- **`BODY_LIMIT`, `error_from_response` and `parse_retry_after` exported from
  `xippios.core`** (ADR-0023, decision 5: a name keeps or gains its export when a
  consumer imports it): sdk-cashctrl imports the first two from `xippios.core.errors`,
  and sdk-usda-psd, then sdk-usda-esr and sdk-usda-gats, the third. The module path
  keeps working.
- **`xippios.core.data_gov`, the api.data.gov gateway module** (the family review's C14;
  ADR-0009, amendment 2026-10-27; ADR-0023; queue row 30 d, found by sdk-usda-psd, and
  row 39 e, by sdk-usda-gats). `Gateway(source)` gives `auth`, a `HeaderKeyAuth` on
  `X-Api-Key` from `DATA_GOV_API_KEY` with the source's slug for its `ConfigError`;
  `classify(response)`, the gateway's `API_KEY_*` answer to a 401 or 403 as `AuthError`,
  its 429 as `RateLimitError` and its `NOT_FOUND` 404 as `NotFoundError`, in the source's
  name with the gateway's URL written `<host>`, and `None` for every other answer; and
  `install(config)`, the hooks of `Gateway.policy`, one `QuotaPolicy` per process on
  `x-ratelimit-limit` and `x-ratelimit-remaining` with a one-hour window, which every
  source in the process shares. The policy's refusal before sending speaks for
  `api.data.gov` and names the variable. `API_KEY_ENV`, `KEY_HEADER`, `WINDOW`,
  `LIMIT_HEADER` and `REMAINING_HEADER` come with it. Consumers: sdk-usda-psd,
  sdk-usda-esr and sdk-usda-gats, which carry the same code as copies today, and the
  template's api.data.gov gateway answer of v0.3.0. Imported from its module;
  `xippios.core` does not re-export it.

### Documentation

- **ADR-0002, amendment 2026-10-27**: `pydantic-settings` and `xippios.core.config` are
  gone, keys are read by the `EnvKeyAuth` helpers, and the sync facade is
  `xippios.core.sync`.
- **ADR-0015, amended 2026-10-27**: the sync `Client`, `UseClientDefault` and `derive` leave
  decisions 2 and 4 and the consequences; `QuotaSnapshot` is importable from
  `xippios.core.client.quota`. **ADR-0004** and **ADR-0009** get a line each for the
  deleted `config` module and `resolve_api_key`.
- **Conventions 1.16**: §7 reads the environment through the `EnvKeyAuth` helpers.
- **ADR-0009, ADR-0010 and ADR-0015, amended 2026-10-27**: the gateway module as the
  code side of one key per issuer; the quota pause bounded by `pause_cap`; C6's
  removals, `install`'s contract and the 429's wait read from the snapshot.
- **Conventions 1.17**: §6 bounds the quota pause by the policy's `pause_cap` and says
  that `install` replaces the config's hooks; §7 names `xippios.core.data_gov` for the
  sources behind api.data.gov.

### Hand-apply for sources

What a source's adoption of 0.3.0 changes because of the changes above. No source
imports a deleted name; the tests of the api.data.gov sources read a deleted attribute
and texts that change, listed here.

- `src/xippios/usda/nass/tasks.py`, `src/xippios/usda/psd/tasks.py`,
  `src/xippios/usda/esr/tasks.py`, `src/xippios/usda/gats/tasks.py` — the
  `ImportError`-guarded `from xippios.core.mcp import ResultCap` → an unguarded
  `from xippios.core import ResultCap`, and the comment that names the `mcp` extra goes
  — `ResultCap` lives in `xippios.core.models` (queue row 30 a).
- `src/xippios/cashctrl/_client.py`, `src/xippios/cashctrl/api/_form.py`,
  `tests/test_errors.py` (sdk-cashctrl: `BODY_LIMIT`, `error_from_response`);
  `src/xippios/usda/psd/_client.py`, `src/xippios/usda/esr/_client.py`,
  `src/xippios/usda/gats/_client.py` (`parse_retry_after`) — `from xippios.core.errors
  import ...` may become `from xippios.core import ...` — the names are exported now; the
  module path keeps working.
- `src/xippios/cashctrl/_cli.py` (sdk-cashctrl) — its module docstring names
  `xippios.core.mcp.quiet_request_logging`, which is importable from
  `xippios.core.mcp.server` only → name that path — docstring only, nothing breaks.
- `src/xippios/usda/psd/_client.py`, `src/xippios/usda/esr/_client.py`,
  `src/xippios/usda/gats/_client.py` — the gateway block (`API_KEY_ENV`,
  `policy = QuotaPolicy(...)`, `_URL`, `_gateway_error`, `_over_rate_limit`, the
  `API_KEY_*`, 429 and `NOT_FOUND` branches of `classify`, `auth = HeaderKeyAuth(...)`) →
  `gateway = Gateway(SOURCE)` from `xippios.core.data_gov`: `classify` returns
  `gateway.classify(response)` when that is not `None` and keeps its own branches after
  it (psd's empty 404, esr's 400), `config = gateway.install(ClientConfig(...))`,
  `client = AsyncClient(config, auth=gateway.auth)`; where the package keeps the names
  `API_KEY_ENV`, `policy` and `auth`, they become `xippios.core.data_gov.API_KEY_ENV`,
  `Gateway.policy` and `gateway.auth`; the `parse_retry_after` import goes when nothing
  else uses it; the module docstring's "waiting within `RetryPolicy.backoff_max`" reads
  "waiting within the policy's `pause_cap`" — the gateway module replaces the three
  copies (C14, ADR-0023), and the pause has one cap (C6).
- `tests/test_client.py` (psd, esr, gats) — the wiring test drops
  `policy.reset_header`, which is gone, and may assert
  `config.before_request == Gateway.policy.before_request` next to
  `config.observe == Gateway.policy.observe`; the assertion on "Nothing was retried"
  goes, since the message no longer speaks of retries; a `retry_after` read through the
  client is the snapshot's wait from now, so `== 3151.0` or `== 3600` becomes a bracket
  with `CLOCK_SLACK`, while `classify` called on its own still gives the exact wait; the
  policy's refusal before sending carries `source == "api.data.gov"`, not the slug, and
  starts "api.data.gov quota of the key in DATA_GOV_API_KEY spent" — C6, C14.
- `tests/test_tasks.py` (sdk-usda-gats), the 429 test of `get_census_export_series` —
  `info.value.retry_after == 3151.0` is read through the client, so it becomes the
  snapshot's wait, a fraction under 3151: bracket it with `CLOCK_SLACK` — C14.
- `CLAUDE.md` (psd, esr, gats), the rate-limit row — "within `RetryPolicy.backoff_max`
  (30 s by default)" → "within the policy's `pause_cap` (30 s by default)", and the
  gateway's key, answers and quota named as `xippios.core.data_gov`'s — ADR-0010,
  decision 4, amended 2026-10-27.

sdk-comtrade's planned `QuotaPolicy(limit_header=None, remaining_header=None,
window=86400, spent=...)` is unaffected: `spent=` stays.

## [0.2.1] - 2026-10-27

This patch release carries the release train, the family conformance check every source
runs, and the shared test helpers brought forward from 0.3.0; `gates.yml` ships switched
off. ADR-0019 to ADR-0023 and conventions 1.14 and 1.15 come as documentation; the code
of ADR-0019 and ADR-0022 ships in 0.3.0. As a patch, it keeps 0.2.0's compatibility
(conventions §12). A source adopts it in one adoption PR with `/adopt-release`, moving
its bound to `xippios-core~=0.2.1` (ADR-0018, amendment (c)); "Hand-apply for sources"
below lists what that PR changes by hand.

### Added

- **The release train** (conventions §12; ADR-0018, amendment (b); Johannes's decision
  of 2026-10-26): `publish.yml` keeps its name and runs on every push to `main` and on
  dispatch. Its `release-check` looks at a push that changed `pyproject.toml` or
  `CHANGELOG.md` (a new source's first release PR changes only the CHANGELOG, since the
  scaffold already says 0.1.0) and lets it through when the version in `pyproject.toml`
  has no tag and `CHANGELOG.md` has its `## [X.Y.Z] - ` heading; a changed
  `pyproject.toml` without that heading leaves a notice, anything else ends quietly.
  Then CI, the annotated tag `vX.Y.Z` on the merge commit with the CHANGELOG section as
  its message, the build checked against that tag, and the `pypi` environment that
  Johannes approves. A session never pushes a tag; sdk-usda-psd's v0.2.0 tag on the
  wrong commit, caught by the old workflow, was the case. `publish.yml` has no
  `concurrency` group, whose one pending run would lose a release run queued behind a
  run waiting at `pypi`. The workflow's header and `docs/handover.md` give the recovery
  path ("Re-run failed jobs" once the tag exists; a build that fails for good after the
  tag needs a patch release) and the race of two pushes to `main` close together (the
  second run's tag push fails red, or tags a later commit when the first run's `ci`
  failed; re-run the failed jobs of the run whose commit is the release, and if the
  other run already tagged a later commit, Johannes rejects its `pypi` deployment and
  the release is re-done as a patch; a release is not merged while another release run
  is waiting).
- **The family conformance check** (conventions §10; ADR-0013, amendment 2026-10-26;
  Johannes's decision of 2026-10-26), `xippios.core.testing.family`: what every source
  shares, tested once, collected with one line,
  `from xippios.core.testing.family import *  # noqa: F403`, in a template-rendered
  `tests/test_family.py`. Empty namespace levels, `py.typed`, `__version__`; `mcp.py`
  and `http.py` serve exactly `tasks.__all__` minus `BULK_TASKS`, the write server
  exactly `tasks_write.__all__`; every task synchronous (no `async_fn` required,
  conventions §6), returning `Result[T]`, with an agent docstring; the README status
  table, in the format of sdk-template's `README.md.jinja`, lists exactly the read and
  the write tasks; `.copier-answers.yml` names a template tag; `pyproject.toml` bounds
  `xippios-core` and its extras with `~=X.Y.Z`. The package under test is the ini option
  `xippios_package`, which the plugin registers, or the one `tasks.py` under
  `src/xippios/`. It replaces the three copies a review across the family counted in
  every source on 2026-10-25, `tests/test_layout.py`, `tests/test_adapters.py` and the
  structural part of `tests/test_tasks.py` (sdk-usda-psd, sdk-usda-nass, sdk-usda-esr,
  sdk-usda-gats, sdk-comtrade, sdk-cashctrl). Two family checks are CI steps instead,
  documented for the template in `docs/handover.md`: a CHANGELOG entry on every PR but a
  release, an adoption or Dependabot's, and the 256 KiB cap on the fixture files a PR
  adds or changes, a moved one included (ADR-0019), a warning in template v0.2.1 and an
  error from v0.3.0.
- **Shared test helpers** (ADR-0023 decision 2, each carried by two sources or more;
  brought forward from 0.3.0 by Johannes's decision of 2026-10-26):
  - the plugin's `anyio_backend`, asyncio, which the conftest of all six sources and of
    the template defined;
  - `sent_query(route)`, the scrubbed query of the last request a route received (asked
    for by sdk-usda-nass; sdk-usda-nass's `sent_query`, sdk-comtrade's `_sent`,
    sdk-cashctrl inline);
  - `recorded_query(fixture)`, the scrubbed query a fixture was recorded with
    (sdk-comtrade's `recorded_params` and `_recorded`, sdk-cashctrl's `recorded_query`);
  - `response_from_fixture(fixture)`, a recorded answer as an `httpx.Response` with its
    request, for calling `classify` (`recorded()` in sdk-usda-psd, sdk-usda-esr,
    sdk-usda-gats and sdk-cashctrl);
  - `url=` on `mount_fixture`, `replay` and the plugin's `replay_fixture`, serving a
    recorded answer at another URL (`_mount_recorded_404` in sdk-usda-psd and
    sdk-usda-esr, found by sdk-usda-esr);
  - `CLOCK_SLACK` and `assert_time_between(value, before, after)`, bracketing a time read
    around a call with five seconds of slack for the WSL2 host's clock, which steps back
    about two seconds (sdk-usda-gats's `CLOCK_SLACK`; the same bracket without slack in
    sdk-usda-psd and sdk-usda-esr).
  A query parameter sent or recorded more than once fails the two query helpers rather
  than losing a value.
- **`.github/workflows/gates.yml`** (Johannes's decision of 2026-10-26, as a fallback;
  ADR-0018, amendment (e): the merge classes its check posts): calls the `merge-class`
  and `family-review` workflows of `xippios/.github` as jobs, each only when the
  repository variable `GATES_CALLER` is `1`, which Johannes sets per repository if the
  ruleset editor offers no "Require workflows" rule. It ships off.

### Changed

- **`ci.yml` has no push trigger** (the release train, above): CI runs once per push to
  `main`, through `publish.yml`, for a release; the strict up-to-date policy tests every
  tree before it merges.
- **Every action in the three workflows is pinned by commit SHA**, its version in a
  comment, as in the `xippios/.github` repository.
- **The sdist's include and exclude patterns are anchored at the root** (found by
  sdk-template): unanchored, `README.md` and `LICENSE` match a file of that name at any
  depth. The sdist's file list is unchanged.
- **The `testing` extra declares `packaging>=22`**, which the family check reads the
  core bound with and which pytest already required; 22.0 is the first release whose
  versions and specifiers are PEP 440 only.

### Documentation

- **ADR-0019, bulk downloads and non-JSON payloads**: a streaming `download` that never
  touches the cache, `decode_text` and `decode_csv`, a byte bound on the cache, bulk
  tasks named in `BULK_TASKS` and skipped by the adapters, the fixture files a PR adds
  or changes under 256 KiB (a fixture over the cap recorded before the rule stays until
  re-recorded; small real samples for XML, ZIP, gzip, XLS and XLSX, never
  byte-truncated, byte truncation for text bodies only; JSON arrays truncated by
  elements and marked), and a `key` parameter that is data when the key is not sent in
  the query. The code ships in 0.3.0.
- **ADR-0020, file-distributed sources**: layer 1 is fetch plus `parse/`, one parser per
  file kind; fidelity applies to files; CSV/TSV, XML, gzip and zip are read with the
  standard library, XLS/XLSX or a hardened XML library through the source's own
  dependency; a PDF yields narrative text only, never numbers; the download's recorded
  exchange is replayed for the download call and the sample file is what the parser
  tests read, its provenance one row in `tests/fixtures/files/README.md`.
- **ADR-0021, dependencies between source packages**: a source may consume another
  source's task layer, bound to one minor, sharing one core minor, the dependency
  tagged first.
- **ADR-0022, packaged answers and release times**: `meta` of a packaged list carries
  the upstream's fetch time, operation and release identifier; `published_at_naive`
  admits a release time printed without a zone; `None` filters are left out of
  `meta.request`. The code ships in 0.3.0.
- **ADR-0023, core scope**: code enters `xippios-core` with two consumers, or one
  consumer for a stated reason from a closed list; a helper is copied to a second
  source at most; a public name with no consumer for two minors is removed.
- **ADR-0003, amendment 2026-10-26**: a source whose API is one part of a shared
  upstream document snapshots its part and records the full document's byte size and
  sha256; a `project` override that drops a personal identifier inside a kept list field
  (`bankAccounts[].iban`) is still parsing only; an adoption PR, which fetches nothing,
  leaves `FETCHED.md` to the next `/refresh-upstream` and ports only the capture
  script's changes.
- **ADR-0018, amendment 2026-10-26**: (a) decision 3 covers sdk-template's release PRs,
  which auto-merge after the reviewer's `ready` like core's and a source's; (b) the
  release train replaces the human tag: the release PR's merge runs `publish.yml`, which
  tags `vX.Y.Z` on the merge commit, and the approval of the `pypi` environment run is
  the human gate; sdk-template tags from its CHANGELOG's top heading with its own
  `release.yml`; until a repository's workflow tags itself, Johannes pushes its tag;
  (c) the core bound may read `~=X.Y.Z` when patch Z shipped what the source adopts,
  still one minor; (d) an adoption PR may delete the fixtures, mounts and tests the
  adoption itself makes dead, and nothing else rides along.
- **`docs/roadmap.md`**: core 0.2.1 and template v0.2.1 as the first step, core 0.3.0
  opening with a PR that deletes what has no consumer, and the order of the next
  sources; faostat's API is keyed by a login bearer token (probed 2026-10-26), and
  wasde's tables come from the release's XLS or XML, decided with Johannes when its work
  starts.
- **Conventions 1.14**: the rules of ADR-0019 and ADR-0022 bind a source from its 0.3.0
  adoption, or, when it starts on a git pin of core 0.3.0, each rule from its first PR
  on a pin that carries the rule's code; `usda-wasde` among the source names (§1;
  ADR-0020, ADR-0021); files and bulk tasks (§2, §3, §6, §8, §9, §10; ADR-0019,
  ADR-0020); a snapshot of one part of a shared upstream document and personal
  identifiers inside a kept list field (§3; ADR-0003 amendment); packaged answers, naive
  release times and the spared `key` (§4; ADR-0019, ADR-0022); source dependencies (§11,
  §12, §15; ADR-0021); the release train and the patch case of the core bound (§12;
  ADR-0018 amendment); copies of a helper (§15; ADR-0023); dead fixtures an adoption PR
  may delete (§15; ADR-0018 amendment); an adoption PR leaves `FETCHED.md` to the next
  `/refresh-upstream` (§15; ADR-0003 amendment).
- **Definition of done**: the fixture cap on the files a PR adds or changes and the
  `truncated` marker, file samples, a core PR's consumer statement in its ADR or
  description, the adoption line per ADR-0023 and the patch case of the bound, the
  live-call count, the `Decisions taken` block with what backs each line (as in the
  review checklist) and the release subset.
- **`docs/review-checklist.md`**: the checklist a reviewer applies to any `sdk-*` PR:
  `main`'s documents for every PR and the branch's own for a PR that changes them, a
  release PR's own tag allowed, a decision backed by a convention, an ADR, a
  coordination rule, a dated decision of Johannes's or a row, and a conventions change
  carrying an ADR or an amendment.
- **`.github/PULL_REQUEST_TEMPLATE.md`** mirrors the definition of done, its Adoption PR
  block included, with the Assumptions, Open questions and Decisions taken headings.
- **Conventions 1.15**: §10 states the one live workflow, `.github/workflows/live.yml`,
  in the shape the template renders, which a source whose secrets differ keeps: one job,
  `contents: read`, nightly and on `workflow_dispatch`, the key reaching only its pytest
  step, sources that share a key staggering their start (ADR-0009 amendment; found by
  sdk-template); §10 names the family conformance check, `xippios.core.testing.family`,
  which the rendered `tests/test_family.py` collects and every source's CI runs
  (ADR-0013 amendment); §15 and the definition of done's Adoption PR intro: the session
  enables auto-merge on an adoption PR only when its merge class is `auto`, and a
  `human` adoption waits for Johannes (ADR-0018, amendment (e); the merge classes of the
  `.github` repository's README), and the definition of done's Process line allows the
  session's one merge action, auto-merge on an adoption or `chore/release-*` PR, only
  when its merge class is `auto` (ADR-0018, amendment (e)).
  `.github/PULL_REQUEST_TEMPLATE.md` mirrors both.
- **ADR-0009, amendment 2026-10-26**: the live workflow's shape is the rule for every
  source, since the nightly live tests spend a shared key too.
- **ADR-0013, amendment 2026-10-26**: the plugin's guarantees extend to the family
  invariants the template-rendered `tests/test_family.py` collects.
- **ADR-0018, amendment (e)**: decision 3's auto-merge of adoption and release PRs after
  the reviewer's `ready` applies only to a PR whose merge class is `auto`; a `human`
  adoption or release (a source-owned workflow, a changed template answer, a protected
  path, a build or install route) waits for Johannes (his merge-class decision of
  2026-10-26).
- **`docs/roadmap.md`**: a pinned new source swaps to `~=0.3.0` in its single v0.3.0
  adoption PR, since a release PR changes only the §12 subset; eurostat's design round
  is the first decision put to Johannes when its work starts; faostat's paging and
  limits are verified with the credential first, once Johannes provides the FAO account
  on approving its package; the release check fires on a change of the version or of
  `CHANGELOG.md`, so a first release tags itself; the snapshot and design-round PRs of
  esmis and eurostat start on template v0.2.1 and core 0.2.1 without a pin, the scaffold
  carries `core_git_ref` only when core's `main` has merged the api.data.gov gateway
  module and the bulk downloads of ADR-0019, else a re-pin PR precedes the first tasks
  PR, and a re-pin to a SHA with ADR-0022's code precedes the reference-data PR;
  eurostat proves a keyless render of template v0.2.1 with `new-source.sh --local-only`,
  and the login-keyed case (faostat) is not a template variant (ADR-0023, ADR-0008).
- **`CLAUDE.md` and `docs/handover.md`** describe the release train: a session never
  tags, the release PR's merge tags, Johannes approves `pypi`. `docs/handover.md` gains
  "Core 0.2.1", with the release's recovery path, and "Adopting core 0.2.1", per source,
  with the template's two CI steps.

### Hand-apply for sources

What a source's adoption of 0.2.1 changes by hand: files the template does not update,
and the values `copier update` takes from the answers; `docs/handover.md`, "Adopting core
0.2.1", names them per source.

- `pyproject.toml` — `xippios-core~=0.2.1` and its extras likewise, from
  `core_version=0.2.1` — `tests/test_family.py` imports what 0.2.0 lacks (ADR-0018,
  amendment (c)).
- `tests/test_tasks.py` — delete `test_package_has_a_version` and
  `test_task_is_a_sync_facade_with_an_agent_docstring` — the family check makes them.
- `tests/test_client.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_errors.py` (sdk-cashctrl) — `recorded()` → `response_from_fixture` — a
  shared test helper (ADR-0023).
- `tests/test_slices.py` (sdk-usda-psd, sdk-usda-esr) — `_mount_recorded_404` →
  `replay_fixture(..., url=...)` — a shared test helper, found by sdk-usda-esr.
- `tests/test_tasks.py` (sdk-usda-nass `sent_query`, sdk-comtrade `_sent`, sdk-cashctrl
  inline) — the query of the last request → `sent_query` — a shared test helper, asked
  for by sdk-usda-nass.
- `tests/conftest.py` and `tests/test_tasks.py` (sdk-comtrade `recorded_params` and
  `_recorded`), `tests/test_tasks.py` (sdk-cashctrl `recorded_query`) — the recorded
  query → `recorded_query` — a shared test helper (ADR-0023).
- `tests/test_lists.py` (sdk-usda-psd, sdk-usda-esr, sdk-usda-gats),
  `tests/test_tasks.py` (sdk-usda-gats) — the `retrieved_at` bracket →
  `assert_time_between`, `CLOCK_SLACK` from core — a shared test helper (ADR-0023).
- `tests/test_adapters.py` (sdk-comtrade, sdk-cashctrl) — the tests of their own move to
  `tests/test_tasks.py` or `tests/test_tasks_write.py` before the update deletes the
  file — the family check makes the rest.

## [0.2.0] - 2026-10-25

What the first four sources, sdk-usda-nass, sdk-comtrade, sdk-usda-psd and sdk-cashctrl,
had to build around core 0.1.0, moved into core: ADR-0009 to ADR-0018, amendments to
ADR-0003, ADR-0005, ADR-0007, ADR-0008, ADR-0010, ADR-0013 and ADR-0015, a follow-up
pointer in ADR-0011, and conventions 1.5 to 1.13 (0.1.0 shipped 1.4). While core is 0.x
a minor keeps no compatibility with the one before it: a source depends on
`xippios-core~=0.2.0` and adopts this release in one adoption PR before its next release
(conventions §12 and §15, ADR-0018). The section "Adopting core 0.2.0" of
[`docs/handover.md`](https://github.com/xippios/sdk-core/blob/main/docs/handover.md), in
the repository and not in the sdist, lists per source what that PR deletes and what
replaces it.

### Breaking changes

- **Writes are not retried after a 5xx** (ADR-0011): a 5xx and a transport failure are
  retried for GET, HEAD and OPTIONS only; a POST, PUT, PATCH or DELETE answered with a
  5xx is raised as `UpstreamError` after one attempt, so a write upstream applied before
  answering 502 is not sent twice (sdk-cashctrl). A 429 is still retried for every
  method. `RetryPolicy(retry_non_idempotent=True)` retries writes again, for an upstream
  that makes a repeated write safe or a source that only reads through POST.
- **Error messages name no host** (ADR-0005 amendment): `error_from_response` writes
  `404 from GET /v1/series: ...`, and `error_from_exception` writes `<host>` where a
  transport failure's text quotes the host. A multi-tenant source's host names the
  tenant; sdk-cashctrl had to mask it in its own `classify`.
- **Binary bodies are refused when recording** (ADR-0013): a body that is not UTF-8 text
  raises `ValueError` ("binary body cannot be scrubbed") and nothing is written, unless
  `Scrub(allow_binary=True)` stores it base64, flagged `body_base64: true` and
  unscrubbed, as 0.1.0 stored every such body (sdk-cashctrl).
- **`EnvKeyAuth.apply(self, request)`**: `apply` reads the key through `self.key()`
  instead of taking it as an argument, which pytest's long tracebacks printed
  (sdk-usda-nass); core's auth classes keep the key in no argument and no local
  variable. A subclass outside core that implements `apply(request, key)` drops the
  parameter; none is known.
- **The pytest plugin keeps the default run offline on its own** (ADR-0013, decision 4
  added by ADR-0015). In every test not marked `live`: a request through httpx's default
  transports or httpcore's pools raises `RuntimeError` naming method and path, from
  `pytest_configure` on, fixtures and collection included (`respx` answers and a
  transport a test passes itself are unaffected; a `respx` pass-through is refused); a
  rate limiter neither waits nor takes a token; every `QuotaPolicy` snapshot is
  forgotten before and after the test, and no policy waits or refuses; every
  `EnvKeyAuth` sends `PLACEHOLDER_KEY`, pinned on the class, and the variables named in
  the ini option `xippios_placeholder_key_envs` hold it. The `httpx` and `httpcore`
  logger levels come back after every test. A test that must reach the network is
  marked `network`; one that asserts a limiter wait, a quota pause or a quota refusal
  is marked `rate_limited`; a module that tests key resolution overrides
  `placeholder_api_key` with a fixture that pins nothing. A source deletes its own
  placeholder fixture, which could not reach one auth object per tenant (sdk-comtrade,
  sdk-cashctrl), and its replays stop waiting behind its limiter (sdk-comtrade,
  sdk-usda-psd).
- **`confirm: bool = False` is enforced at registration** (ADR-0014):
  `register_tasks(..., read_only=False)`, and so `build_server`, refuses with
  `ValueError`, before registering anything, a task without a parameter `confirm`
  annotated `bool` (`Annotated[bool, ...]` counts, `bool | None` does not) defaulting
  to `False`; before, only `assert_write_tools` caught it, in a test (sdk-cashctrl).
- **Write servers listen on loopback only** (ADR-0014): `main` serves a write server
  over `--http` on `127.0.0.1`, `localhost` or `::1` and otherwise exits with status 2,
  unless `--allow-remote` is passed: a write server carries no authentication, so
  beyond loopback a gateway in front of it has to. Read-only servers and stdio are
  unaffected.
- **`mcp_call` runs the server's middleware** (ADR-0014): it calls the tool through an
  in-process `mcp.Client` instead of `MCPServer.call_tool`, so a tenant lock applies
  (sdk-cashctrl). An MCP error, arguments the tool's schema refuses or an unknown tool
  now fail the test with `AssertionError` instead of raising the SDK's `ToolError`, and
  the server must be one `mcp.Client` connects to (an `MCPServer` or a low-level
  `Server`).
- **`classify` shapes retries** (ADR-0015): before a 429 or 5xx is retried, the client
  asks `classify`, also with `raise_on_error=False`. A `RateLimitError` sets the wait
  from its `retry_after`, so a wait beyond `RetryPolicy.backoff_max` is raised after
  one attempt; an `UpstreamError` for a 5xx, or `None`, keeps the status rule; any other
  error, an `AuthError` say, ends the retries. api.data.gov's 429 without `Retry-After`
  was sent three more times into the spent quota (sdk-usda-psd). `send_with_retries`
  takes `classify=`.
- **Result caps count UTF-8 bytes and promise no filter** (ADR-0016): `cap_result`
  measures `max_bytes` in UTF-8 bytes of the compact JSON text, as the convention said,
  not in characters, so non-ASCII text keeps fewer rows; the preview cuts no character.
  The default note ends "narrow the query to see the rest" ("showing {shown} of {total}
  rows (cap: {max_rows} rows or {max_bytes} bytes); ...", for a non-list result "result
  is {n} bytes, over the cap of {max_bytes}; ..."), where it suggested "more filters or
  a shorter date range" that a reference list does not have (sdk-comtrade). A test that
  asserts the old text changes; none is known.
- **Generated enum modules are ASCII-only and pass ruff as rendered** (ADR-0008
  amendment): `render_str_enums` writes each value as `ascii()` does
  (`"C\xf4te d\u2019Ivoire"`, unchanged at runtime), lays out a long member as ruff
  formats it, sorts `__all__` in ruff's order (RUF022), one name per line, and wraps its
  docstrings at 100 columns. It refuses with `ValueError` what made a file ruff rejects:
  caller text it cannot write as printable ASCII, a `generator`, `fetched` text, key or
  class name (a class name must also be an identifier, no keyword, at most 84
  characters), the error naming the argument and position, never the text; a member name
  over 92 columns, the error naming the key and quoting the value; and a key over 75
  characters, the error quoting the key. A value with nothing to derive a member name
  from (a Greek, Cyrillic or CJK label) is named once through the new `member_names=`. A
  source re-renders its enum file once and commits the one-time diff (sdk-usda-nass's
  first line only); the formatting step after a refresh goes (sdk-comtrade).
- **`Tenants` splits the caller's mistake from the operator's** (ADR-0014): new in this
  release, so it breaks only a source that moves its own tenant registry onto it. An
  undeclared tenant is `InvalidRequestError` (MCP text, HTTP 422), "unknown tenant ...";
  a missing or malformed variable of a declared one is `ConfigError` naming the
  variable, never the value (sdk-cashctrl, on its git pin already).
- **Personal identifiers stay out of task projections** (ADR-0017, conventions §3), a
  rule for sources: documented personal identifiers (CashCtrl's `ssn` and `iban`, and
  what a source judges equivalent) are left out of the projections tasks return unless
  a task fetches them deliberately and says so, and a write task does not echo one in
  `meta.request`; read models stay faithful; fixtures never carry the values, which a
  recording names in `Scrub(secrets=...)` or rewrites with `Scrub(rewrite=...)`.
  Nothing in core changes.

### Added

- **Request hooks and a quota policy** (ADR-0015, sdk-usda-psd).
  `ClientConfig.before_request` runs once per call, after the cache lookup and before
  the rate limiter, with no credentials on the request yet; sync or async, it may wait,
  or raise a taxonomy error and nothing is sent. `ClientConfig.observe` sees every
  response from the wire, retried attempts and raw responses included, a cache hit
  never, before `classify`. `QuotaPolicy` and `QuotaSnapshot` (in `xippios.core` and
  `xippios.core.client`) implement ADR-0010's quota rules on them:
  `QuotaPolicy(...).install(config)` sets both, and the policy keeps a thread-safe
  snapshot from the quota headers (`limit_header`, `remaining_header`, `reset_header`,
  each `None` to turn it off); a 429, or `remaining` at 0, marks the quota spent until
  `Retry-After`, the reset header or `window` from now, upstream's wait cut to `window`
  (`window=86400` for a daily quota); `spent=` reads any other answer to a spent limit,
  such as sdk-comtrade's 403 "replenished in HH:MM:SS", and `mark_spent()` marks it from
  code. A request into a spent quota waits within `pause_cap` (else
  `retry.backoff_max`), logged once, or raises `RateLimitError` with `retry_after`,
  saying nothing was sent and when the quota is back. `install` refuses a config with a
  hook of its own, and a subclass's `before_request` override is not called through the
  hook it sets; `snapshot()`, `reset()`, and `QuotaSnapshot.describe()`, numbers and
  times only. Replaces sdk-usda-psd's `QuotaAwareClient`, `Quota`, `observe_quota` and
  `quota_pause`, which sdk-usda-esr and sdk-usda-gats would otherwise copy.
- **Keyless calls on a keyed client** (ADR-0015, sdk-comtrade): `auth=` per call on
  `request`, `get` and `get_json` of `AsyncClient` and `Client`, and on `record` and
  `record_sync`, default `httpx.USE_CLIENT_DEFAULT` (its type, `UseClientDefault`, is
  re-exported from `xippios.core.client`). `None` sends the call, retries included,
  without the client's credentials and shares the cache; an `httpx.Auth` replaces them
  for that call and bypasses the cache. sdk-comtrade needed a second client to keep its
  key off public files on its data API's host.
- **Cache provenance and a cache filter** (ADR-0015, sdk-usda-psd): a cache hit carries
  `extensions["xippios_cache_stored_at"]`, the entry's time in epoch seconds, from which
  a task sets `retrieved_at` (conventions §4); `xippios.core.client.decode_json` is
  `get_json`'s decoding for a wrapper that calls `get` to read it.
  `ClientConfig.cache_filter` decides which GETs the cache takes, so one endpoint can be
  cached without a second client. `WIRE_HEADERS` and `strip_wire_headers` name the
  headers dropped from cache entries and fixtures (`content-length`,
  `content-encoding`, `transfer-encoding`, `connection`).
- **A shared pace** (sdk-usda-psd): `limiter=` for `AsyncClient` and `Client` takes a
  `TokenBucket` instead of building one from `config.rate_limit`, and
  `AsyncClient.limiter` returns the bucket in use, so two clients can share one pace.
- **Form bodies and retried writes** (ADR-0011, sdk-cashctrl): `data=` on
  `AsyncClient.request`, `Client.request`, `record` and `record_sync` sends a
  form-encoded body (passing `json=` too raises `ValueError`); `RetryPolicy`'s
  `retry_non_idempotent` (default `False`) retries a 5xx and a transport failure for
  POST, PUT, PATCH and DELETE too.
- **`AsyncClient.derive(retry=..., timeouts=...)`** (sdk-comtrade): a client with only
  those replaced, sharing auth, transport, sleep, rate limiter and cache. Closing it
  closes its own pools and leaves the borrowed transport open for its parent, as
  `record` needs after a recording with `retry=` or `timeouts=`; a transport a caller
  passed to a client is still closed with that client. `record` and `record_sync` take
  `headers=`, `scrub=`, `retry=` and `timeouts=`, overrides going through `derive`.
- **Upstream totals** (ADR-0012, sdk-cashctrl): `ResultMeta.total`, upstream's count of
  the records matching the request, `None` when it reports none. A paginated task sets
  it from upstream's count whether it returns one page or all, never from
  `len(data)`; a negative count is refused; `cap_result` and HTTP responses keep it.
- **Multi-tenant sources** (ADR-0014, sdk-cashctrl). `ResultMeta.tenant`, the tenant by
  name, never a value (`"tenant": null` for a single-tenant source).
  `xippios.core.Tenants(source, *, list_var, fields, reserved=(), validate=None,
  hints=None)` reads the tenants from the environment, names listed in `list_var` and
  values in `<SOURCE>_<NAME>_<FIELD>`, which `var(name, field)` names, a reserved tenant
  (`demo`) present when its variables are set; `names()`, `require(name)`,
  `field(name, field)` through `validate`, with `hints` text for a refused value,
  `client_for(name, build)`, one client per tenant rebuilt when a value changes,
  `reset()`. `xippios.core.tenants.list_task` is the task behind a
  `<source>_list_<tenants>` tool, names only. `TenantLock(param, value)`, as
  `tenant_lock=` for `build_server` and `register_tasks`, refuses without running the
  tool a call that names another tenant or leaves the tenant out, and names the tenant
  in the instructions; the list tool lists that tenant alone, and a locked server
  refuses a task whose tenant parameter has a default. `main(..., add_options=,
  apply_options=)` and `build_parser(prog, *, add_options=)` put a source's options on
  core's parser, parsed once, a `XippiosError` from `apply_options` exiting with status
  2; `is_write_server(server)` serves the loopback rule. Generalises sdk-cashctrl's
  organisation registry and `--org` lock.
- **Per-tool result caps** (ADR-0016, sdk-comtrade, sdk-usda-psd): `caps=` on
  `register_tasks` and `build_server` maps a task function's `__name__`
  (`list_partners`, not the tool name) to a `ResultCap` replacing `cap` for that tool;
  an unknown name is refused before anything is registered. A source keeps it as
  `MCP_CAPS` in `tasks.py`, passed by its `mcp.py` as
  `caps=getattr(tasks, "MCP_CAPS", None)`. `ResultCap(note=...)` replaces the text after
  the counts. The default, 200 rows or 65,536 bytes, cut `comtrade_list_reporters` (255
  rows, 69,011 bytes) and `comtrade_list_partners` (310 rows, 83,270 bytes) at 200
  rows, and `usda_psd_list_countries` (251 rows) before the United States.
- **Integer-id enums** (ADR-0008 amendment, sdk-usda-psd):
  `xippios.core.reference.render_int_enums` renders one `IntEnum` per list of
  `(id, name)` pairs, values the ids in upstream order, so a member equals the id in
  upstream's data; member names come from the names, `_<id>` appended to a name several
  ids share (`TOTAL_DISAPPEARANCE_126`); layout, `member_names=` and refusals as in
  `render_str_enums`, and an id listed twice is refused. `id_name_pairs(records, *,
  id_field, name_field)` builds the pairs, refusing a bad record by field and position,
  never by content. Replaces sdk-usda-psd's `render_id_enums`.
- **Scrubbed recording** (ADR-0013, sdk-cashctrl): `xippios.core.testing.Scrub(host=,
  secrets=, rewrite=, allow_binary=)`, as `scrub=` on `write_fixture`, `record` and
  `fixture_from_response` (now exported from `xippios.core.testing`), removes in memory,
  before the one write, what credential scrubbing does not: the request's host, replaced
  by a placeholder in every form (letter case, IDNA, percent-encoded), named values made
  `REDACTED`, and a text hook for bodies and response headers, for signed URLs. The
  scrubbed exchange is then verified, a JSON body also decoded; a host or value left
  raises `ValueError` saying where, never what, and nothing is written. A placeholder
  that would write what it hides is refused; one that contains the original host
  (`demo.example.test` for `example.test`) is allowed. `Scrub`'s `repr` leaves `secrets`
  out. `FixtureRequest.body`, `body_base64` and `content_type` keep the scrubbed request
  body for a write test to assert; fixtures from 0.1.0 still load. Ports the recorder
  sdk-cashctrl kept locally.
- **Replay by query parameter** (ADR-0013, sdk-comtrade): `match_params=` on
  `mount_fixture`, `replay` and the plugin's `replay_fixture` names recorded query
  parameters a request must carry too, so a count call (`countOnly=true`) and the data
  call on one path are told apart; a name not recorded, or recorded as `REDACTED`, is
  refused. Absence cannot be matched: the more specific fixture is mounted first.
  `ReplayFixture` types the fixture.
- **`xippios.core.testing.sent_urls(route)`** (sdk-usda-nass): the URLs a `respx` route
  received, through `scrub_url`, for a test to compare instead of keeping a request,
  key included, in its frame, which a failing assertion or `pytest -l` prints.
- **Offline-test names** (ADR-0013): `xippios.core.testing.PLACEHOLDER_KEY`
  (`"placeholder-for-fixture-replay"`), the ini option `xippios_placeholder_key_envs`
  and the markers `network` and `rate_limited`, described under Breaking changes.
- **Write-server checks** (sdk-cashctrl): `xippios.core.testing.assert_write_tools(
  write_server, write_tasks, *, source, read_server=None, router=None)` fails a test,
  naming the tool, unless the server is a write server whose tools are exactly the write
  tasks, each with `confirm: bool = False`, and no write tool is on the read server or
  the router. `mcp_call_text(server, name, arguments)` returns a tool's text through
  the same in-process client as `mcp_call`, for asserting an `error:` text.
- **ADR-0009 and ADR-0010** (sdk-usda-psd, sdk-comtrade): one key variable per issuer
  when one key serves several sources (`DATA_GOV_API_KEY`), and the rate-limit policy:
  a fast pace within a documented limit or a stated self-imposed one, longer-window
  quotas spent rather than rationed, the answer to a spent limit interpreted in
  `classify`, no request fired into a spent quota, pauses stated.
- **ADR-0018, core versioning and source adoption**: a source depends on one core minor
  (`xippios-core~=X.Y.0`) and adopts each new minor in one adoption PR against
  conventions §15, the definition of done's "Adoption PR" block. Adoption
  (`chore/template-update*`) and `chore/release-*` PRs are auto-merged after the
  reviewer's `ready`.

### Changed

- **Conventions 1.5 to 1.13**: 1.5 the key variable per issuer and the rate-limit
  policy (§1, §5, §6, §7; ADR-0009, ADR-0010); 1.6 error messages without the host and
  the retry rule (§5, §6; ADR-0011); 1.7 `ResultMeta.total` (§4; ADR-0012); 1.8 form
  bodies, the recorder's rules and the plugin's guarantees (§6, §10; ADR-0013); 1.9
  tenants, the `confirm` check, the loopback rule, the tenant lock and the option hooks
  (§1, §4, §7, §8, §10; ADR-0014); 1.10 the hooks, `QuotaPolicy`, `classify` in retries,
  `auth=` per call and a cache hit's `retrieved_at` (§4, §6, §10; ADR-0015); 1.11 the
  UTF-8 byte cap, per-tool caps in `MCP_CAPS` and a note that promises no filter (§8;
  ADR-0016); 1.12 `IntEnum` for integer ids and ASCII-only, ruff-clean enum modules
  (§3; ADR-0008 amendment); 1.13 `Fetched` as a UTC time with `Z`, HTML for tables a
  pipe table cannot hold, vendor snapshots (§3; ADR-0003 amendment), personal
  identifiers out of task projections (§3, §4; ADR-0017), `InvalidRequestError` also
  for upstream's own refusal mapped in `classify` (§5; ADR-0007 amendment, its
  docstring and the README with it), the one-minor core bound and the 0.x rule (§11,
  §12) and the adoption checklist (§15; ADR-0018). The definition of done gains the
  "Adoption PR" block, and its fixture grep covers the identifiers' values.
- **The edges of the plugin's quota guarantee are documented** (ADR-0013 and ADR-0015,
  amended by ADR-0016): consecutive live tests share every policy's snapshot; a quota
  spent while a fixture of wider scope is set up is forgotten before the body of the
  next test not marked `live`; a `QuotaPolicy` subclass's `before_request` override is
  neither called through `install`'s hook nor neutralised.
- **The `testing` extra declares `httpcore>=1.0`**, which the plugin patches and which
  only httpx's own dependency provided before.
- **CI runs `uv run pre-commit run --all-files`** after the tests, so the definition of
  done's "Enforced by CI" block holds.

### Fixed

- **A gzip answer replayed from the cache** raised `httpx.DecodingError`: the decoded
  body was stored with `content-encoding`. Entries are stored without wire headers, and
  those a persistent backend kept from 0.1.0 are stripped when replayed (sdk-usda-psd).
- **`parse_retry_after`** let `ValueError` or `OverflowError` out of the retry loop for
  non-ASCII digits (`"²"`) or an HTTP-date with a huge zone offset, and returned an
  infinite `retry_after` for a value too long for a finite float. It reads ASCII digits
  only and returns `None` for what it cannot read.
- **The live gate** skipped every test under a directory named `live`, marked or not;
  it follows the marker now.
- **Taxonomy errors survive `copy.copy`, `copy.deepcopy` and `pickle`**: errors with
  keyword-only arguments raised `TypeError`; `XippiosError.__reduce__` restores every
  attribute (sdk-cashctrl).
- **`RateLimit.per_minute`'s docstring**: the pace is the one a source sets within
  upstream's limit, or a self-imposed one (ADR-0010), not upstream's limit.

### Security

- **The MCP servers no longer log request URLs** (ADR-0005). Constructing an `MCPServer`
  configures root logging at `INFO`, and httpx logs every request URL at `INFO`, so
  every `xippios-<source>-mcp` wrote upstream URLs into its MCP client's logs:
  sdk-usda-nass's key, sent as `key=`, and sdk-cashctrl's tenant host.
  `xippios.core.mcp.quiet_request_logging()` sets the `httpx` and `httpcore` loggers to
  `WARNING`; `build_server` calls it after constructing the server, and `main` again
  right before running it, after `apply_options`. A consumer who wants the log raises
  the level and runs the server without `main`.
- **`.gitignore`** also ignores `.env.*` and `.envrc.*` (sdk-comtrade).
- **The secret scan no longer skips paths containing "swagger"**: detect-secrets'
  `is_swagger_file` filter, which exempted a verbatim upstream Swagger snapshot, is
  dropped (sdk-usda-psd); `.secrets.baseline` and the detect-secrets hook exclude
  `.copier-answers.yml` with sdk-template's pattern, so the template copies both files
  verbatim again (sdk-comtrade).

## [0.1.0] - 2026-10-22

First release, cut after the first source package (sdk-usda-nass) had exercised it.

### Added

- `xippios.core.errors`: the family error taxonomy (`XippiosError` and seven
  subclasses), `error_from_response`, `raise_for_status`, `parse_retry_after`.
- `xippios.core.models`: `UpstreamModel`, `ResultMeta`, `Result[T]`, `parse`.
- `xippios.core.config`: `SourceSettings` base and `resolve_api_key`.
- `xippios.core.sync`: derive a sync function from an async one on a shared
  background event loop.
- `xippios.core.client`: `AsyncClient` and `Client` with `ClientConfig`, `Timeouts`,
  `RetryPolicy`, `RateLimit`, `MemoryCache` and the `CacheBackend` protocol.
- `xippios.core.client.auth`: `QueryKeyAuth`, `HeaderKeyAuth`, `BearerAuth`,
  `BasicKeyAuth` and the `EnvKeyAuth` base, resolving the key from the environment on
  the first request. Re-exported from `xippios.core`.
- `ResultMeta` redacts credential-like keys in `request` at construction (ADR-0005).
- `resolve_api_key` is typed to return `SecretStr` when the key is required.
- `xippios.core.pagination`: `paginate_offset`, `paginate_pages`, `paginate_cursor`,
  `collect`.
- `xippios.core.reference`: `load_csv`, `load_json`, `load_table`.
- `xippios.core.mcp` (extra `mcp`): `build_server`, `register_tasks`, `cap_result`,
  `error_to_text`, `main`.
- `xippios.core.http` (extra `http`): `router_from_tasks`, `problem_response`,
  `install_error_handlers`.
- `xippios.core.testing` (extra `testing`): pytest plugin with the `live` gate,
  fixture format, `record`, `replay`, scrubbing helpers.
- CI on Python 3.12, 3.13 and 3.14; trusted publishing on `v*` tags.
- `UpstreamModel` serialises `Decimal` fields as JSON numbers in both adapters
  (ADR-0008); `UpstreamModel.project` builds projections; `parse_decimal` reads
  published figures with separators or suppression codes.
- `ClientConfig.classify`: a source's error mapping, called on every response before
  the default status mapping.
- `xippios.core.reference.render_str_enums` and `enum_member_name`: generated
  `StrEnum` source for packaged value lists.
- `xippios.core.testing.assert_projection` and `mcp_call`.
- `InvalidRequestError` in the taxonomy (ADR-0007): a request refused before it is
  sent; HTTP 422, MCP text. Re-exported from `xippios.core`.
- `xippios.core.http.is_scalar`.

### Changed

- `router_from_tasks`: a task with any non-scalar parameter becomes a `POST` route whose
  JSON body is an object keyed by parameter name; scalar-only tasks stay `GET`.
