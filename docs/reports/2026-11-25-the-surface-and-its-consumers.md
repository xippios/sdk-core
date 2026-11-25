# The surface of core 0.5.0 and its consumers among the proving packages, 2026-11-25

**A draft.** The five proving packages were still moving when this was counted: the figures of
core's own surface below are final for its candidate, and the consumers' figures are counted again
on the commits that the proof ends on, before this report lands.

Core's surface went from 126 unique names in 17,045 lines at v0.4.1 to 112 in 16,480 lines on the
candidate for 0.5.0: the run-time part from 81 names in 9,068 lines to 72 in 8,740, and the
workbench from 46 names in 7,977 lines to 41 in 7,740. Of the 112 names, 51 have fewer than two
consumers among the five proving packages, and 23 have fewer than two among them and the nine
other sources on their `main` together. No name and no parameter leaves core by this count alone
(ADR-0059, decision 2; ADR-0068, decision 6;
https://github.com/xippios/sdk-core/issues/485, part 6): each piece under two consumers that its
mechanism's record does not name stands below, for the ledger of the next minor.

## Basis

- Core: the candidate,
  https://github.com/xippios/sdk-core/commit/4060d9615012b09487d87a51064c610de34be069, and the
  tag https://github.com/xippios/sdk-core/tree/v0.4.1, each counted by
  `python3 -I scripts/count_surface.py --json --core <tree>` of the candidate, which reads by
  `ast` and imports nothing (README, Counting the surface and its consumers).
- The five proving packages, as consumers, at the commits counted:
  - sdk-faostat, https://github.com/xippios/sdk-faostat/commit/5ab5f48e7997a3d7347ef5c85eda54b8063b054a;
  - sdk-cashctrl, https://github.com/xippios/sdk-cashctrl/commit/a3aa9f9e56345627a8079cbfa1fa0b2cb37df11b;
  - sdk-usda-esr, https://github.com/xippios/sdk-usda-esr/commit/8acbdcd5e19f06194a742bdbac19b692bbac9164;
  - sdk-usda-fas, the shared package of the three FAS sources, proven as code before its
    repository exists, at its commit `fdb28c2a747b0597a8bcd0fa0d43e629a33b5e57`;
  - xippios-mcp, the host, https://github.com/xippios/xippios-mcp/commit/cd682d954ac2cc60c1235024c3e0d8427b56f6f2.
- The nine other sources, as a second count that a later adoption changes, on `main`, before
  their adoption of 0.5.0: sdk-comtrade, sdk-eurostat, sdk-google-mail, sdk-usda-esmis,
  sdk-usda-gats, sdk-usda-nass, sdk-usda-psd, sdk-usda-wasde and sdk-x. Their code imports core
  0.4.1's names, so a name that 0.5.0 renamed, `record` for `record_sync` say, counts none there.
- The lines of core's `tests/` are the lines of its Python files.

## The surface before and after

| part | v0.4.1 names | v0.4.1 lines | 0.5.0 names | 0.5.0 lines |
| --- | ---: | ---: | ---: | ---: |
| run time | 81 | 9,068 in 31 files | 72 | 8,740 in 30 files |
| workbench | 46 | 7,977 in 15 files | 41 | 7,740 in 15 files |
| package | 126, `load_json` in both | 17,045 in 46 files | 112, `REDACTED` in both | 16,480 in 45 files |

By list: `xippios.core` 59 to 57, `xippios.core.client` 20 to 15, `xippios.core.mcp` 15 to 11,
`xippios.core.http` 3 to 3, `xippios.core.testing` 30 to 25 and `xippios.core.refresh` 16 to 16.
The workbench is `xippios.core.testing` and `xippios.core.refresh` with the modules under
`testing/` and `refresh/` (ADR-0068, decision 6).

Core's `tests/` hold 27,643 lines, where they held 24,308 at v0.4.1.

## The consumers among the five

Of the 112 names, 15 have no consumer among the five, 36 have one and 61 have two or more, and 15
entries repeat a name that another list pins. Of the keyword-only parameters, 92 have no consumer,
60 have one and 40 have two or more.

Each name with fewer than two consumers among the five, by its list, with its consumers among the
five, then among the nine on `main` (a count where more than three):

| name | among the five | among the nine |
| --- | --- | --- |
| `xippios.core:BODY_LIMIT` | sdk-cashctrl | none |
| `xippios.core:REDACTED` | sdk-cashctrl, also by `xippios.core.testing` | four, by `xippios.core.testing` |
| `xippios.core:BearerToken` | sdk-faostat | sdk-google-mail |
| `xippios.core:QueryTooLarge` | none | none |
| `xippios.core:QuotaPolicy` | sdk-usda-fas | sdk-comtrade, sdk-google-mail |
| `xippios.core:RenewingBearerAuth` | sdk-faostat | sdk-google-mail |
| `xippios.core:RetryPolicy` | sdk-usda-fas | eight |
| `xippios.core:TenantLock` | sdk-cashctrl | sdk-google-mail |
| `xippios.core:Tenants` | sdk-cashctrl | sdk-google-mail |
| `xippios.core:TransportError` | sdk-cashctrl | sdk-usda-nass |
| `xippios.core:__version__` | none | none |
| `xippios.core:bind_tasks` | sdk-cashctrl | sdk-google-mail |
| `xippios.core:closest` | sdk-faostat | seven |
| `xippios.core:fetch_counted` | none | none |
| `xippios.core:fetch_pages` | sdk-cashctrl | none |
| `xippios.core:fetch_periods` | sdk-usda-esr | none |
| `xippios.core:list_task` | sdk-cashctrl | sdk-google-mail |
| `xippios.core:load_json` | none | sdk-eurostat, sdk-usda-nass |
| `xippios.core:names_codes` | none | none |
| `xippios.core:nearest` | sdk-usda-esr | sdk-usda-gats |
| `xippios.core:newer_than` | sdk-usda-esr | none |
| `xippios.core:parse_decimal` | sdk-faostat | sdk-usda-nass, sdk-usda-wasde |
| `xippios.core:parse_retry_after` | sdk-usda-fas | sdk-comtrade |
| `xippios.core:tenant_instructions` | none | sdk-google-mail |
| `xippios.core.client:CachedResponse` | none | sdk-usda-gats |
| `xippios.core.client:cache_key` | none | sdk-eurostat, sdk-usda-gats, sdk-usda-nass |
| `xippios.core.client:decode_csv` | sdk-faostat | sdk-eurostat |
| `xippios.core.mcp:LOOPBACK_HOSTS` | xippios-mcp | none |
| `xippios.core.mcp:build_parser` | none | sdk-usda-gats, sdk-usda-nass |
| `xippios.core.mcp:cap_result` | sdk-usda-esr | sdk-google-mail, sdk-usda-esmis |
| `xippios.core.mcp:error_to_text` | none | none |
| `xippios.core.mcp:quiet_request_logging` | xippios-mcp | none |
| `xippios.core.mcp:register_tasks` | xippios-mcp | none |
| `xippios.core.http:is_scalar` | none | none |
| `xippios.core.http:status_for` | sdk-usda-esr | four |
| `xippios.core.testing:FixtureResponse` | none | sdk-usda-gats |
| `xippios.core.testing:Rewrite` | none | none |
| `xippios.core.testing:Scrub` | sdk-cashctrl | sdk-google-mail, sdk-usda-wasde, sdk-x |
| `xippios.core.testing:assert_projection` | none | six |
| `xippios.core.testing:assert_write_tools` | sdk-cashctrl | sdk-google-mail |
| `xippios.core.testing:fixture_from_response` | sdk-cashctrl | sdk-google-mail, sdk-usda-wasde, sdk-x |
| `xippios.core.testing:fixture_text` | sdk-cashctrl | sdk-google-mail, sdk-usda-wasde, sdk-x |
| `xippios.core.testing:keep_reserved_tenants` | sdk-cashctrl | sdk-google-mail |
| `xippios.core.testing:record` | none | none |
| `xippios.core.testing:send_once` | sdk-cashctrl | none |
| `xippios.core.testing:sent_bodies` | sdk-cashctrl | sdk-google-mail |
| `xippios.core.testing:write_fixture` | sdk-cashctrl | sdk-google-mail, sdk-usda-wasde, sdk-x |
| `xippios.core.refresh:Enumeration` | sdk-usda-esr | none |
| `xippios.core.refresh:NotFetched` | sdk-faostat | none |
| `xippios.core.refresh:dump_json` | sdk-usda-fas | none |
| `xippios.core.refresh:read_json` | sdk-usda-fas | none |

## The pieces under two consumers in all fourteen trees

Over the five and the nine together, 8 names have no consumer and 15 have one, and 64 parameters
have none and 35 have one.

The names: `BODY_LIMIT`, `QueryTooLarge`, `__version__`, `fetch_counted`, `fetch_pages`,
`fetch_periods`, `names_codes`, `newer_than` and `tenant_instructions` of `xippios.core`;
`CachedResponse` of `xippios.core.client`; `LOOPBACK_HOSTS`, `error_to_text`,
`quiet_request_logging` and `register_tasks` of `xippios.core.mcp`; `is_scalar` of
`xippios.core.http`; `FixtureResponse`, `Rewrite`, `record` and `send_once` of
`xippios.core.testing`; and `Enumeration`, `NotFetched`, `dump_json` and `read_json` of
`xippios.core.refresh`. Two take the place of 0.4.1 names that the nine call on `main`,
`record` and `send_once` of `record_sync` and `send_once_sync` (ADR-0066), and four serve the
refresh scripts that each source declares on the frames at its adoption, `Enumeration`,
`NotFetched`, `dump_json` and `read_json`, while the nine's scripts on `main` import nothing of
`xippios.core.refresh` (ADR-0062; `docs/handover.md`).

The parameters, by the object that takes them, with their consumer where they have one:

- `AsyncClient(transport=)` sdk-usda-fas; `ClientConfig(read_timeout=, retry=, before_request=,
  observe=)` none, `(cache_max_bytes=)` sdk-usda-gats; `KeyAuth(name=)` sdk-usda-fas,
  `(key=)` sdk-cashctrl; `MemoryCache(lifetimes=, max_bytes=)` none, `(clock=)` sdk-usda-gats;
  `QuotaPolicy(clock=)` sdk-usda-fas, `(sleep=)` none; `RenewingBearerAuth(credentials=)`
  sdk-google-mail; `RetryPolicy(backoff_base=, backoff_max=)` none, `(jitter=)` sdk-x.
- `PackagedCodes(fold_case=, list_name=, source=)` none; `closest(n=)` sdk-faostat;
  `nearest(n=)` sdk-usda-esr; `newer_than(released=, read=)` sdk-usda-esr.
- `QueryTooLarge(limit=, narrow=, request=, source=)`, `TransportError(source=)`,
  `UnknownCode(outdated=)` and `XippiosError(source=)` none.
- `fetch_counted(limit=, empty=, narrow=, source=)` none; `fetch_pages(page_size=, most=,
  paging=, start=, source=)` sdk-cashctrl, `(stop=, key=)` none; `fetch_periods(skip=)`
  sdk-usda-esr; `Ceiling(mcp=, option=)` xippios-mcp, `(help=)` none.
- `ResultCap(keep=)` sdk-usda-esr; `ResultMeta(names=)` none, `(notes=)` sdk-usda-esr;
  `parse_retry_after(now=)` sdk-usda-fas.
- `Tenants(var_prefix=)` sdk-google-mail, `(noun=)` sdk-cashctrl; `tenant_instructions(bound=)`
  sdk-google-mail; `main(tenants=, check=)` sdk-cashctrl, `(argv=)` none.
- `ToolSet(read_only=, loopback_only=)` sdk-google-mail; `build_server(name=)` xippios-mcp;
  `cap_result(offset=)` none; `router_from_tasks(prefix=, tags=)` none.
- `Fixture(recorded_at=, request=, response=)` and the nine fields of `FixtureResponse` none;
  `Scrub(response_secrets=)` sdk-google-mail; `assert_write_tools(dry_run=, sent=)` sdk-cashctrl,
  `(is_read=)` none; `fixture_from_response(max_bytes=, keep=)` none, `(rewrite=)` sdk-cashctrl;
  the eleven keywords of `record` and the seven of `send_once` none, since the nine call the
  0.4.1 names.

Their records name these with their consumer: `fetch_pages(stop=, key=)` (ADR-0034, amendment
2026-11-24), `MemoryCache(max_bytes=)` (ADR-0040, amendment 2026-11-24), `Tenants(var_prefix=)`
(ADR-0036, amendment 2026-11-24), the loopback declaration and the noun of a tenant (ADR-0063),
and the frames' `split`, `Snapshot.pause`, `Page.keyed` and `Lists.before` (ADR-0062). The rest
stand here for the ledger of the next minor.

## Imports from outside the lists

Among the five, sdk-faostat imports `INFO_TERMS` in a script and `check_attribution` and
`render_fetched` in its tests from `xippios.core.refresh.upstream`, and sdk-cashctrl imports
`replay` in its tests from `xippios.core.testing.replay`: four names that no list pins. The
modules of the family check, the built-answer check, the live comparison and the plugin are
imported as the template renders them, and `request_description` is pinned in `xippios.core`.
