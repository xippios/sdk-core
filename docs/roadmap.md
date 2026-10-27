# Roadmap

As of 2026-10-26 · Decided by Johannes on 2026-10-26 (architect interview; step 0 and
PR 0 from the coordination review of the same day)

The order in which `sdk-core`, `sdk-template` and the next source packages are built.
The conventions and the ADRs bind; this file only sequences them, and it changes by PR
when Johannes decides a new order. It supersedes nothing published; within the family it
replaces the order set by the review of 2026-10-25. The C- and T-labels are that review's
item labels for core and for the template; each is said in words where it appears.

## 1. Close what is in flight

Released: core 0.2.0 and template v0.2.0; usda-nass 0.1.0, usda-psd 0.2.0, comtrade
0.1.0, cashctrl 0.1.0, usda-esr 0.1.0, usda-gats 0.1.0.

In flight on core 0.2.x, as scoped, no scope widening: usda-nass 0.2.0, comtrade 0.2.0,
usda-esr 0.2.0, usda-psd 0.3.0, usda-gats 0.2.0, cashctrl 0.2.0. None needs anything
from core 0.3.0. Each adopts core 0.2.1 and template v0.2.1 (step 0) if they are tagged
before its own release.

## 2. Step 0: core 0.2.1 and template v0.2.1

Before 0.3.0, one patch release of core and one of the template:

- **The release train** (conventions §12). `publish.yml` keeps its name and runs on
  every push to `main`; when the push changes the version in `pyproject.toml` or changes
  `CHANGELOG.md`, that version has no tag yet and `CHANGELOG.md` has its section, it tags
  `vX.Y.Z` on the release PR's merge commit, builds, and waits at environment `pypi` for
  a human's approval. So a first release, whose version the scaffold already names,
  tags itself from its `CHANGELOG.md` change. `ci.yml` drops its own push trigger, so CI
  runs once per push to `main`.
  Core 0.2.1's release PR is the first that tags itself; the template carries the same
  workflows for generated repositories.
- **The family conformance check.** `xippios.core.testing.family` holds the tests every
  source shares (namespace levels empty and `py.typed` present; the adapters register
  exactly `tasks.__all__` minus `BULK_TASKS`; every task returns `Result[T]` with an
  agent docstring; the README status table lists exactly the tasks; `.copier-answers.yml`
  names a template tag; the core bound uses `~=`). A template-rendered
  `tests/test_family.py` collects them and replaces each source's layout and adapter
  tests.
- **C12, shared test helpers** in `core.testing`, `anyio_backend` from the plugin
  (moved here from 0.3.0).
- **A helper that serves a recorded fixture at another request path**, for the empty
  404 recorded on one path and asserted on another, which psd and esr each carry as
  `_mount_recorded_404` (row 41 b).
- **Adoption.** Sources adopt v0.2.1 in one adoption PR (conventions §15) with
  `core_version=0.2.1` and the bound `~=0.2.1`, since `tests/test_family.py` imports
  what 0.2.0 lacks.

## 3. Core 0.3.0 and template v0.3.0

The review's full scope in one minor, one lock, one PR at a time, in this order.
The numbers stay as decided; item 4 is empty.

0. **PR 0, deletions with no consumer, before C14.**
   - C1: `SourceSettings` and the pydantic-settings dependency deleted,
     `resolve_api_key` folded into `auth.py` (ADR-0002 and conventions §7 amended).
   - C2: the sync `Client` deleted; httpx's private `UseClientDefault` no longer
     imported.
   - C3: `derive`, `_BorrowedTransport`, `limiter=` and `record`'s retry and timeout
     overrides dropped (row 12).
   - C4: page paging folded into offset paging; cursor paging deleted.
   - C5: the public API cut to what consumers import, from 111 names to about 65, with
     `BODY_LIMIT`, `error_from_response` and `parse_retry_after` exported and
     `ResultCap` importable without the `mcp` extra (rows 17, 30 a).
1. **C14, the api.data.gov gateway module** (three copies exist: psd, esr, gats):
   `HeaderKeyAuth` on `X-Api-Key` from `DATA_GOV_API_KEY`, the gateway's `classify`, one
   `QuotaPolicy` per key shared in-process. **C6, the slimmed `QuotaPolicy`, lands
   inside this PR**: header reading, a 429 as spent, wait-or-refuse, `install`, `reset`
   and the registry stay; the three reset-header formats, `mark_spent`, per-config caps
   with foreign-hook detection and the pause/backoff duality go (ADR-0015 amended).
2. **C15, bulk downloads and non-JSON payloads**, with C10, one redaction module and the
   SDMX `key` case (ADR-0019).
3. **ADR-0022**: `published_at_naive` and C13, `PackagedList` with its loader.
4. *(Removed: C12 ships in core 0.2.1, step 0.)*
5. **C7, the reference renderer** writing plain, ruff-clean output (ADR-0008 amended);
   **C11, the plugin's network guard** on the connection pools only.
6. **C8, C9, the moves out of core to cashctrl**: tenants, the tenant lock, the write
   checks and the recorder's host placeholder, after Johannes's decision of 2026-10-25
   that cashctrl stands alone (ADR-0014 superseded in part).
7. The ADR-0020 and ADR-0021 conventions text landed with the ADRs (conventions 1.14),
   ahead of the code; the template's `source_dependencies` answer follows in v0.3.0.
8. **Release PR; tag 0.3.0.** Template v0.3.0 tags with it: the template cleanup, which
   drops `needs_write_tools`, the generated write tests and the `basic` key location
   (T2), takes one api.data.gov gateway answer after C14 (T9) and makes the siblings
   check template-owned (T10), and the 0.3.0 halves: `BULK_TASKS`, `parse/`,
   `source_dependencies`. Every source adopts once through conventions §15.

Every 0.3.0 PR deletes its own surplus tests (per module a happy path, each documented
refusal, one test per ADR rule); the release PR states the test-line count against the
review's target of about 4,500 to 5,000 lines, down from 7,546.

Pin rule for this period: a new source session may start on a git pin of the core SHA
that merged C14 and C15 (`core_git_ref`) and swaps to `~=0.3.0` in its single v0.3.0
adoption PR, not in a release PR, which changes only the subset of conventions §12.
Existing sources wait for the tag. The snapshot and design-round PRs of esmis and
eurostat start on template v0.2.1 and core 0.2.1 without a pin. Their scaffold carries
`core_git_ref` (a full SHA on `main`) only when the C14+C15 SHA exists at their start;
otherwise a re-pin PR follows before the first tasks PR. Before the reference-data PR
they re-pin to a SHA that carries ADR-0022's code. Both adopt template v0.3.0 once.

## 4. New sources, in order

| Order | Package | Starts after | Shape |
| --- | --- | --- | --- |
| 1 | `sdk-usda-esmis` | C14 + C15 merged | catalog + download, no parsers (ADR-0019, ADR-0020) |
| 1 | `sdk-eurostat` | C15 merged; its design round | keyless, flat; JSON-stat cubes, SDMX-CSV; codelists as packaged tables |
| 2 | `sdk-usda-wasde` | esmis 0.1.0 on PyPI | parser package depending on esmis (ADR-0020, ADR-0021) |
| 2 | `sdk-faostat` | Eurostat's CSV/bulk pattern settled | keyed (a login bearer token), JSON data plus open bulk ZIP/CSV |
| 3 | `sdk-usda-nass` 0.3.0 | nass 0.2.0 released; core 0.3.0 | the bulk datasets as `parse/` modules and bulk tasks |

The "Starts after" column marks the start of a package's tasks work; the snapshot and
design-round PRs of esmis and eurostat start earlier, on core 0.2.1 and template v0.2.1
without a pin (§3).

Per package:

- **esmis.** Host `https://esmis.nal.usda.gov`. Precondition check: fetch the OpenAPI
  YAML, verify whether a key is needed and how a release's download URL is shaped.
  Tasks: agencies, publications, releases, the release calendar, the latest release of
  a series, the files of a release; `download_release_file` as a bulk task. Publication
  identifiers as a packaged table. The catalog, never a parser (2,000+ publications).
- **eurostat.** The design round is the session's first interview (open decision); C10
  needed; a keyless render of template v0.2.1 is proven with `new-source.sh --local-only`
  before anything is created (v0.2.1's template tests carry a keyless case).
- **wasde.** Tables from the release's XLS or XML, decided at its first interview from
  the samples; a CSV to verify; the narrative from the PDF as text only; tasks per table
  and report month; `vintage` = the report date as printed; no re-exposure of PSD's
  world balance sheets (ADR-0003). The first table set: its briefing interview.
- **faostat.** The API is keyed: a bearer token from `POST /api/v1/auth/login` with a
  username and password (probed 2026-10-26: the old keyless host is down; the bulk
  catalogue and ZIPs are open). Its live run needs a FAO account, which Johannes
  provides when he approves the package (G1); paging and limits are verified with that
  credential at the session's step 0. The login-keyed case is not a template variant:
  core has no login auth (ADR-0023, one consumer), and ADR-0008 forbids source-specific
  scaffolding, so faostat carries its login auth until a second consumer.
- **nass 0.3.0.** The datasets at nass.usda.gov/datasets as `parse/` modules sharing the
  Quick Stats models; last.
