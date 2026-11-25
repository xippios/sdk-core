# The surface of core 0.5.0 and its consumers among the proving packages, 2026-11-25

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
- The five proving packages, as consumers, each counted at the commit that the proof ends on,
  extracted by `git archive` and read as committed:
  - sdk-faostat, the tree of its adoption's second step,
    https://github.com/xippios/sdk-faostat/commit/0e4d3bd26154f52ffdc9d96401b49cbbd47b4954
    (https://github.com/xippios/sdk-faostat/pull/70), with `scripts/refresh_reference.py` of its
    third step put in its place, from
    https://github.com/xippios/sdk-faostat/commit/81e48a10ca9f11b889644edd6619115c7acd96cc
    (https://github.com/xippios/sdk-faostat/pull/76), which declares its lists in `Lists` with
    `Listed`, `run` and the `before` hook; the two count as one consumer;
  - sdk-cashctrl,
    https://github.com/xippios/sdk-cashctrl/commit/16ea4a086d8a3030d66d499a73b8a84fb4aca542
    (https://github.com/xippios/sdk-cashctrl/pull/157);
  - sdk-usda-esr, at commit `40ae344e4b4f256d4cc030b5c701af38c255f8f0`, not yet public;
  - sdk-usda-fas, the shared package of the three FAS sources, proven as code before its
    repository exists, at commit `f3f02faf5f2b059c2d7299d28a1b7e83247bdeeb`, not yet public;
  - xippios-mcp, the host, at commit `a2557c4001a55e14192e1aecdc1e52659e9b51ce`, not yet public.
- The nine other sources, as a second count that a later adoption changes, on `main` before
  their adoption of 0.5.0:
  https://github.com/xippios/sdk-comtrade/commit/da27cd23d4dc26853698fd0bb93d58e56c576743,
  https://github.com/xippios/sdk-eurostat/commit/1713cf7ff17283a012f1b40721140b10a82b54c3,
  https://github.com/xippios/sdk-google-mail/commit/bae345a5c167d2b0e1a554e7d7d8b8b98f912e72,
  https://github.com/xippios/sdk-usda-esmis/commit/755aa6810cce1d0a6e9e74aa062fd9f1bd2f4cc2,
  https://github.com/xippios/sdk-usda-gats/commit/2bcd2c6924059d321645179a349f02cebfae2784,
  https://github.com/xippios/sdk-usda-nass/commit/58f376df35072c25fc9d8d9a3cc85a2f2e6c028c,
  https://github.com/xippios/sdk-usda-psd/commit/dacd424fbe3bd36a0127ee9d27e3ca16d0cfe235,
  https://github.com/xippios/sdk-usda-wasde/commit/8ab32e1e16101b36cdd7cfd81981f5afdf85fe85 and
  https://github.com/xippios/sdk-x/commit/fca9eb27a5bdedd6cd4be3df16170d843598c09c. Their code
  imports core 0.4.1's names, so a name that 0.5.0 renamed, `record` for `record_sync` say,
  counts none there.
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
| `xippios.core:REDACTED` | sdk-cashctrl, also by `xippios.core.testing` | four |
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

## The additions that no proving package uses

Some additions of 0.5.0 are values or fields that the script does not count, so the five trees
were read for them. No proving package uses these yet; each is built in core and first used by
its source at that source's adoption: the option hooks of a tool set without `server`
(`ToolSet(add_options=, apply_options=)`), the loopback declaration of a read tool set
(`ToolSet(loopback_only=)`), the cache's lifetime by path prefix (`MemoryCache(lifetimes=)`),
the walk's stop rule and key (`fetch_pages(stop=, key=)`), the key class for a query key and for
a bearer (`KeyAuth` with `location="query"` or `"bearer"`), `after` of `Lists`, and the snapshot
frame's `pause`. Three pieces that ADR-0062 names with one consumer each are used here:
sdk-cashctrl's snapshot marks its page `split`, sdk-faostat's marks its samples `keyed`, and
sdk-faostat's reference script, from its third step, hands its declaration a `before` hook.

## Imports from outside the lists

None of the five imports a name that no list pins. The modules of the family check, the
built-answer check, the live comparison, the plugin and the recorder are imported by their path
as the template renders them, and sdk-usda-esr imports `request_description` from
`xippios.core.errors`, whose object `xippios.core` pins.
