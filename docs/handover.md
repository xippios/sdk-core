# Handover: adopting core 0.5.0

This file holds one part, for the coming release, and it names no source: the changes that a
source's callers see, the conventions' rules that changed, by section, and what every source does
(ADR-0068, decision 5; ADR-0065, decisions 4 and 5). The part of an earlier release stands in that
release's tag, `git show v0.4.1:docs/handover.md` for the parts of core 0.2.0 to 0.4.1, and the
records and `CHANGELOG.md` tell its history. Each source's own list, every Hand-apply item of the
release's changelog fragments that names it, one item per file with the tests that break without
it, stands on the source's adoption issue in its own repository
(https://github.com/xippios/sdk-core/issues/485, part 4).

## Adopting core 0.5.0

Core 0.5.0 is a consolidating minor: each mechanism stands as the one way, what it supersedes left
in the same release, and a name with one consumer went back to its source (ADR-0059, ADR-0061). A
source adopts it and sdk-template 0.5.0 together, in one adoption PR before its next release,
judged against conventions §15 and nothing else. A core minor is a breaking change of the source,
so the adoption's fragment is `breaking` and the source's release a minor (§12; §15 item 9), and
the conventions that the source then applies read 1.30.

The tag follows a proof: three sources adopt core's and the template's `main` on branches that pin
both by commit, and what they meet comes back to core as follow-ups of its steps and to this part
before the tag (https://github.com/xippios/sdk-core/issues/485). The other sources adopt from the
tags.

The two lists below and the items on each adoption issue are written from the release's changelog
fragments, read on `main` with every step of the package merged: each Hand-apply note gives a file,
what changes in it and the tests that break without it, at the line numbers of the source's `main`
on 2026-11-24, and the adoption PR confirms every item against the source as it is then. §15 items
8 and 9 hold an adoption against the two lists (https://github.com/xippios/sdk-core/issues/334,
https://github.com/xippios/sdk-core/issues/349).

What binds in core names no source, and core's test `tests/test_what_core_names.py` refuses every
name outside the shapes that core may name in the package, its tests and scripts and the documents
that bind. A step of the organization's conventions check that finds each source's names from its
template answers is planned with the organization's package after the sources' first wave: 0.5.0
promises nothing of it, and no adoption waits for it (ADR-0065, decision 6;
https://github.com/xippios/.github/issues/169, https://github.com/xippios/.github/issues/170).

### The changes that a source's callers see

Each change below reaches a source's callers, through its Python API, its MCP tools or its routes,
once its adoption takes it up; the tasks and tools that it reaches in a source stand on that
source's adoption issue. Its entry is a fragment of the adoption PR, worded for the source's own
tasks and citing the issue, in the group given here by what the change does to the callers
(`changelog/README.md`), and the release takes it as the fragment reads (conventions §12;
ADR-0043, decision 2).

1. **A refusal before a request says that nothing was sent**
   (https://github.com/xippios/sdk-core/issues/481; ADR-0045, ADR-0053; §5). Every refusal of a
   call as given, core's and the source's own, says `Nothing was sent.` after its first sentence,
   and so does the MCP adapter's refusal of an argument, while a refusal after a request says what
   was sent. A list of codes is checked by one call, which names the first code that it refuses
   and refuses an empty list. Entry: under `changed`, the refusals' words, their classes
   unchanged.
2. **A write is sent once** (https://github.com/xippios/sdk-core/issues/480; ADR-0011;
   ADR-0061, decision 10; §6). A write is never repeated, after a 429 or a renewing bearer's 401
   too, and its error after a 5xx or a failure in transit says that the request was sent once and
   that its outcome is unknown, or that nothing was sent where the connection failed, while a 4xx
   keeps upstream's words. Each write task's docstring names the read that shows whether a failed
   write was applied, and a source whose reads upstream bills sends each read once. Entry: under
   `changed`, the write tasks' errors and docstrings, and a billed read that a 5xx no longer
   repeats.
3. **A tool's description and its arguments' text** (https://github.com/xippios/sdk-core/issues/485;
   ADR-0063, decision 9; §8). A tool's description is its task's docstring before `Args:`, under
   1,000 characters, and each argument's text under `Args:` stands in the tool's input schema.
   Entry: under `changed`, the tools whose description the adoption trims, and the arguments'
   text in the schema.
4. **A tool of a task that pages itself takes no `offset`**
   (https://github.com/xippios/sdk-core/issues/476; ADR-0063, decision 3; ADR-0061, decision 9;
   §8). A paged cap is refused for a task that takes `start`, so its tool loses the adapter's
   `offset`, and a caller pages it by the task's own `start`. Entry: under `breaking`, each tool
   that loses `offset`.
5. **Notes, the names of a record's codes, and integers**
   (https://github.com/xippios/sdk-core/issues/478; ADR-0067; §3, §4). `meta.notes` holds one
   sentence per fact that a task says about its answer. A record's model names the codes of its
   rows in `meta.names` where its code field declares their packaged list, or the field in which
   upstream sends the name, and a row's code that the list lacks is left out of the names and said
   in a note, so no answer is withheld for it. A `Decimal` without fractional digits is a JSON
   integer, `16217` where it read `16217.0`. Entry: under `added`, the names of the rows' codes
   and each task's notes, and under `changed`, the integers.
6. **When an answer was retrieved** (https://github.com/xippios/sdk-core/issues/479; ADR-0037;
   §4). `meta.retrieved_at` is the client's time of the answer for every task, the oldest where a
   task assembles several answers. Entry: under `changed`, the tasks whose `retrieved_at` read
   another time.
7. **A walk of pages refuses at its bound** (https://github.com/xippios/sdk-core/issues/480;
   ADR-0034; ADR-0061, decision 8; §4). A task that collects offset pages sends no request at or
   past upstream's count, and where it needs more pages than its stated bound it refuses with
   `InvalidRequestError` and returns nothing, naming the count, the bound, the paging argument,
   the requests sent, the page reached and the total of pages. Entry: under `changed`, the tasks
   whose walk refuses, with their bound.
8. **The boundary of a source package and the twelve ways**
   (https://github.com/xippios/sdk-core/issues/474; ADR-0060; ADR-0061; §1 to §14). A read task's
   name starts with `list_`, `get_`, `search_`, `count_` or `download_`, a reading `<stem>_number`
   or `<stem>_label` stands beside its text, a task that fixes filters, sorts, ranks or cuts for
   the caller leaves, and each way of ADR-0061 holds. The arguments that identify a record are
   positional in the order of upstream's path and every other is keyword-only, and a time that
   upstream prints is read into the type that keeps all it sends, naive where it states no zone,
   with no text beside it (https://github.com/xippios/sdk-usda-esr/issues/60, parts 1 and 3).
   Entry: under `breaking`, each task, argument or field renamed or removed.
9. **Answers kept by path prefix** (https://github.com/xippios/sdk-core/issues/479; ADR-0040;
   ADR-0061, decision 11; §6). A read-only source of public data keeps upstream's answers in core's
   cache, each for the lifetime of the longest path prefix that its path starts with, none where no
   prefix matches, an expired one dropped and the bodies held under a bound of bytes. Entry: under
   `changed`, the lifetimes, or under `added` where the source kept no cache.
10. **The refusal of a spent quota** (https://github.com/xippios/sdk-core/issues/485; ADR-0065,
    decision 2; §7). The refusal before sending into a spent quota says "quota" with the policy's
    source and no longer names the key's variable. Entry: under `changed`, its words, where the
    source's quota is shared with other sources under one key.
11. **One client per tenant until reset** (https://github.com/xippios/sdk-core/issues/475;
    ADR-0036; §7). A tenant source keeps one client per tenant until `Tenants.reset()`, so a
    tenant's changed variable takes effect at the next start, and a value that the source checks is
    refused by the source's own `ConfigError`, which names the variable and no value. Entry: under
    `changed`, where a running server built a new client when a variable changed.
12. **One entry, one name, one wording** (https://github.com/xippios/sdk-core/issues/476; ADR-0063,
    decision 7; §8). Both servers of a source are named `xippios-<source>`, the help of
    `--allow-remote` takes core's one wording, and the server's instructions come from the tasks
    module. Entry: under `changed`, a server whose name changes.
13. **One read timeout** (https://github.com/xippios/sdk-core/issues/475; ADR-0059; §6). The client
    reads each answer within one read timeout, 60 s by default, and connects, writes and waits for
    a connection within 10 s each. Entry: under `changed`, where the source's timeouts change.
14. **Credential names kept for each source** (https://github.com/xippios/sdk-core/issues/485;
    ADR-0040; §4). In a host that loads several sources, one source's key name no longer turns
    another source's data into `REDACTED`. Entry: none, since a source's answers change by it only
    beside another source, which the host's release states.

### The conventions' rules changed since 1.29

Conventions 1.30 differ from 1.29 by the rules below, read from the diff of `docs/conventions.md`
since `v0.4.1`. Each points to the sentence that states it in its section, with its record, and
§15 item 8 holds the source to it at the adoption. Every section's cases now use the invented
source, and the history of its rules left (ADR-0068, decisions 2 and 3), which changes no rule of
its own. §9 and §11 are unchanged.

- **The header**: what binds names no source but `example` outside the citation of a public
  record of the organization, which is an issue, a pull request, a record or a report, and the
  organization's check is planned (ADR-0065, decisions 5 and 6;
  ADR-0068, decision 1).
- **§1, naming**: the slug `example` is the invented source's (ADR-0065, decision 4), the list of
  the family's sources leaves (ADR-0068, decision 2), and the verbs of a task's name and the words
  of a package's own arguments (ADR-0061, decisions 3 and 4).
- **§2, layering**: several values of one filter as a list, a filter of the package's own only
  where upstream has none and one order of arguments (ADR-0061, decisions 1, 2, 4 and 5), the
  arguments that identify a record in the order of upstream's path
  (https://github.com/xippios/sdk-usda-esr/issues/60, part 1), what an answer holds (ADR-0060,
  decisions 4 and 8; ADR-0001, amendment 2026-11-24), and a documented parameter that a caller
  cannot set yet, which stands while the README's `## Scope` names it with its public issue
  (ADR-0060, decision 8; https://github.com/xippios/sdk-core/issues/611).
- **§3, upstream fidelity**: values, labels and a record that a package shapes itself (ADR-0060,
  decisions 1, 3, 7 and 8; ADR-0020, amendment 2026-11-24), a printed time
  (https://github.com/xippios/sdk-usda-esr/issues/60, part 3), a number's form in JSON (ADR-0067,
  decision 10), and the two refresh frames: one declaration each under one `run`, the snapshot
  fetched through core's client, the mark of `FETCHED.md`'s form, no check without a request and
  the reference list's one table header (ADR-0062), whose rules §3 cites in place of ADR-0046 and
  ADR-0051.
- **§4, the envelope**: notes and the names of a record's codes (ADR-0067), `retrieved_at` from
  `get_answer` (ADR-0037), the walk of pages that refuses at its bound and the stated bound of
  requests per call (ADR-0034, amendment 2026-11-24; ADR-0061, decision 8), credential and data
  names kept for each source (ADR-0040), the entry's names (ADR-0063, decision 7), a release as
  upstream states it (ADR-0060, decisions 2 and 8), and a catalogue on another origin of the
  publisher, which goes as its files go, through the one client without its credentials and under
  its one limiter (ADR-0060, decision 8; https://github.com/xippios/sdk-core/issues/610).
- **§5, errors**: the refusal that says nothing was sent and the check of a list (ADR-0045 and
  ADR-0053, amendments 2026-11-24), one answer for "no data" per kind of task, with a period not
  yet released answered by §4's case of one period (ADR-0041, decision 6), one refusal that names
  the first problem (ADR-0061, decisions 6 and 7), a refusal after another operation's read that
  names that read (ADR-0054, amendment 2026-11-22), and `request_description` in a shared
  package's messages about an answer (ADR-0043, decision 6; ADR-0065, decision 3).
- **§6, the HTTP client**: a write and a billed read sent once (ADR-0011, amendment 2026-11-24;
  ADR-0061, decision 10), `get_answer` the one reader of JSON and `request("DELETE", ...)` in place
  of `delete_json` (ADR-0037), the cache by path prefix (ADR-0040; ADR-0061, decision 11), a
  download's `params=` and `headers=` (ADR-0040), the quota policy's own headers and window and no
  `pause_cap` (ADR-0037), and one read timeout (ADR-0059).
- **§7, configuration**: one key class (ADR-0059), the tenants' registry without `validate=`,
  `hints=` and `NO_TENANT_TASKS` (ADR-0036), the tool set's names (ADR-0063, decision 2), and the
  code that several sources share for one key in their publisher's shared package and never in
  core (ADR-0065, decisions 1 and 3; ADR-0032, decision 1).
- **§8, MCP**: a tool set alone builds a server and is checked when it is built, a paged cap only
  for a task that takes no `start`, one entry, the adapter's refusal and the host's reading
  (ADR-0063, decisions 1 to 7; ADR-0061, decision 9), a tool's description and its bound (ADR-0063,
  decision 9), a write tool's preview in every call (ADR-0050), a stated bound of requests in
  the tool's description, about two dozen before the client's retries (ADR-0061, decision 8), and
  the answer that the response cache holds for a paged continuation, one under its bound within
  its path's lifetime (ADR-0061, decision 9; https://github.com/xippios/sdk-core/issues/608).
- **§10, testing**: the family check's contract tests and what a source no longer tests (ADR-0063,
  decision 8), a reading's form and a value set held offline (ADR-0060, decision 9; ADR-0061,
  decisions 3 and 12), the key class's slug (ADR-0040;
  https://github.com/xippios/sdk-core/issues/526), the built-answer check (ADR-0064), with a
  recorded body that no route serves and no `classify` reads an input of the test (ADR-0064,
  decision 3; https://github.com/xippios/sdk-core/issues/609), the plugin's `ENV_VARS` and the
  checks that keep what a source uses (ADR-0035), and the recorder (ADR-0066).
- **§12, versioning and releases**: a dependency on a publisher's shared package and the sections
  that bind one (ADR-0021, amendment 2026-11-24; ADR-0065, decision 3), sdk-template's own
  `CHANGELOG.md`, which names the tag whose file holds its older sections (ADR-0068, decision 5;
  https://github.com/xippios/sdk-template/issues/300, part 4), and how a release run that fails
  is finished, the remedy of the race where a release has a `pypi` stage (ADR-0069).
- **§13, repository hygiene**: a workflow carries no comment but the version after a pinned action
  (ADR-0039, decision 7, amendment 2026-11-24; https://github.com/xippios/.github/issues/111).
- **§14, the boundary of a source package**: the six sentences, word for word (ADR-0060).
- **§15, adoption**: the adoption's items stand here once, and route (3) leaves (ADR-0068,
  decision 4; ADR-0039, amendment 2026-11-24), and the copies of code with one consumer follow the
  record of core's scope (ADR-0059, decisions 2, 5 and 8).

### Every source

- **Item 1, the core floor**: `core_version=0.5.0`, so `xippios-core~=0.5.0` and each of its
  extras likewise, from PyPI, with `uv.lock` updated. A dependency on another source package or on
  a publisher's shared package takes its minor on core 0.5.0, released first (§12; ADR-0021;
  ADR-0065, decision 3). The environment then takes every extra, `uv sync --all-extras`: a
  `uv sync` or a `uv run --exact` without `--all-extras` removes the extras, and
  `uv run --isolated` builds an environment without them, so an isolated `pytest` run of a test
  that imports an extra takes `--all-extras` too, while a plain `uv run` keeps what is installed.
- **Item 2, `copier update` to sdk-template 0.5.0**, which renders what the template's changelog
  lists for 0.5.0: among it, a rendered `mcp.py` holds no line that a source edits (ADR-0063,
  decision 7), `reference/README.md` takes the one header of its provenance table (ADR-0062), and
  `pyproject.toml` loses the ini options that core no longer reads (ADR-0035).
- **What the lock's move fails at once.** The family check's eight new tests fail a source that does
  not meet them: `test_family_mcp_build_holds_the_package_contract`,
  `test_family_project_scripts_name_the_entry_points` and
  `test_family_package_re_exports_its_tasks` (ADR-0063, decision 8),
  `test_family_tool_descriptions_stay_under_the_bound` (ADR-0063, decision 9),
  `test_family_read_tasks_start_with_a_read_verb` (ADR-0061, decision 3),
  `test_family_readings_stand_beside_their_text` (ADR-0060, decision 9),
  `test_family_key_class_names_the_package_s_own_slug` (ADR-0040) and
  `test_family_code_names_are_declared_on_the_model` (ADR-0067, decision 8), which takes the place
  of `test_family_country_codes_are_named_in_the_answer`, while
  `test_family_fetched_md_agrees_with_the_snapshot` leaves (ADR-0062, decision 9). A paged cap for
  a task that takes `start` fails the tool set when `mcp.py` builds it, and so every test that
  imports the server (ADR-0063, decision 3).
- **The names that left**, each failing a source at its import or its call until the port stands,
  with what takes its place in the fragment that names it:
  - the client's: `get_json`, `delete_json`, `request(raise_on_error=)`, `Timeouts`, `decode_text`,
    `decode_csv`'s response branch and `delimiter=`, `decode_json` from the lists, `QueryKeyAuth`,
    `HeaderKeyAuth`, `BearerAuth`, `BasicKeyAuth`, `RenewingBearerAuth(margin=)`, the client's
    `async with`, `RetryPolicy(retry_non_idempotent=, retry_transport_errors=)`,
    `QuotaPolicy(pause_cap=)`, the policy's default headers and window, `MemoryCache(ttl=)`,
    `ClientConfig.cache_filter`, and `register_data_name` and `register_credential_name` without
    `source=`;
  - the walk's and the lists': `paginate_offset` and `collect`, `QueryTooLarge(bound=)`,
    `closest(cutoff=)`, the unread members of `PackagedCodes`, `names_codes(separator=)`,
    `UNNAMED_CODES`, `naive_time`, `load_table` and `load_csv`;
  - the server's: the slug forms of `build_server` and `register_tasks`, `serve_tenants`,
    `is_write_server`, `is_loopback_only`, `build_parser(server=)`, `ResultCap` from
    `xippios.core.mcp`, `NO_TENANT_TASKS`, `list_task(source=)`, `Tenants(validate=, hints=)` and
    the noun of `TenantLock`, which `Tenants(noun=)` takes;
  - the testing support's: `record_sync`, `send_once_sync`, `record_task`, `record_task_sync`,
    `array_key=`, `mount_fixture`, `assert_write_tools(source=, preview_reads=)` with its write
    server, `assert_time_between(slack=)`, `assert_list_current` from the list of
    `xippios.core.testing`, and the ini options `xippios_placeholder_key_envs` and
    `xippios_package`;
  - the refresh frames': the overloads and the six keywords of `run`, `Enumeration.values` and
    `.key`, `render_enums` from `xippios.core.reference`, `Credentials`, `quota_wait`,
    `Page.keep_recorded`, `Page.origin`, `--out`, `indent`, `load_json`, now `read_json`, and
    `compare_fetched`;
  - `xippios.core.data_gov`, which a publisher's shared package holds (ADR-0065, decision 1).
- **What a source does by hand**, each by the fragment that names it, the files on its issue:
  1. Each wrapper reads JSON by `get_answer`, takes `answer.payload` and hands `answer.retrieved_at`
     to its task's `ResultMeta` (ADR-0037). A live test that holds `meta.retrieved_at` to the
     test's own window with `assert_time_between` fails where the run's cache serves an answer
     that an earlier test stored, since a kept answer's time is when it was stored and a task
     dates its answer by the oldest of its reads, so the test checks the time as the task dates
     it: equal to the oldest of the call's reads, or no later than the call's end and no earlier
     than the cache's lifetime before its start (§4; ADR-0037, decision 5;
     https://github.com/xippios/sdk-core/issues/479).
  2. Each refusal before a request says `Nothing was sent.`, a loop over codes becomes one call of
     `check` with the list, and a check of a download's `dest` gives way to `check_dest`
     (ADR-0045, ADR-0053).
  3. Each tool's description stays under 1,000 characters, what an argument needs moved to its
     line under `Args:` (ADR-0063, decision 9).
  4. `tasks.py` declares what `mcp.py` held, `MCP_INSTRUCTIONS`, `MCP_BOUND_INSTRUCTIONS`, the two
     option hooks and `MCP_LOOPBACK_ONLY`, and `MCP_CAPS` holds no paged cap for a task that takes
     `start` (ADR-0063, decisions 3 and 7).
  5. The source's own tests of the package contract, of its entry points, of the re-export of its
     tasks and of what core's adapters and entry answer leave, and so does its live probe of
     upstream's base URL beside each task's smoke test (ADR-0063, decision 8).
  6. `_client.py` declares its secret variables in `ENV_VARS`, which the plugin reads (ADR-0035),
     sends its key by `KeyAuth` with its location and its name (ADR-0059), a query key with
     `source=` (ADR-0040), and sets one read timeout where it set `Timeouts`.
  7. A record's code field declares its packaged list or its label field by `NamedBy`, and a
     task's facts about its answer go to `meta.notes` (ADR-0067).
  8. A write task's docstring names the read that shows whether a failed write was applied, and a
     client whose reads upstream bills takes `RetryPolicy(max_attempts=1)` (ADR-0011).
  9. A walk of offset pages is one `fetch_pages` with its bound, and the tool's description, the
     task's docstring before `Args:`, states the most requests of a call, retries counted
     (ADR-0034; ADR-0061, decision 8).
  10. A read-only source of public data gives its client core's cache with a lifetime per path
      prefix (ADR-0040; ADR-0061, decision 11).
  11. The reference script declares a `Lists`, the snapshot script fetches through core's client,
      and the first refresh on this core writes `FETCHED.md` whole, in its form 2 (ADR-0062).
      A count of a snapshot run's most requests takes at most 22 a page and one a keyed sample:
      the frame sends each request once through the client, whose retries never apply, asks a
      page once more at most, after a network error, a 5xx or a 429 that the client gives a
      wait, and follows at most ten redirects on the page's host in each attempt, while a
      renewing auth's token requests and its one resend come beside them (ADR-0062,
      decision 4). A page that answers 401 or 403 has its row under `Not fetched` with its
      status and host and no size or hash, so its body may differ from run to run while
      `--check` holds (ADR-0062, decision 7). After a reference refresh the records, not the
      files, tell what changed: the frame writes each list it fetched, the provenance table and
      `enums.py` again with the new fetch time and prints each list's count of records alone,
      so a refresh that changed no record still leaves a diff in each, and §12 asks a pull
      request of its own only for a changed record
      (https://github.com/xippios/sdk-core/issues/592). A script that wraps a frame tells a
      run that fetches nothing by what the frame reports, the line of the requests sent that a
      run prints once it began to fetch, never by the literal `--render-only`: the frame's
      parser takes `--render` as the same option, and `--help` and a refused `--only` fetch
      nothing either (https://github.com/xippios/sdk-core/issues/591).
  12. A script that records and the one-off recordings call `record` and `send_once`, sync under
      their plain names or awaited by `async_fn`, and a recording names a secret once, `Scrub`
      covering its encoded forms (ADR-0066).
  13. `tests/test_built_answers.py` keeps its collecting line alone, its empty `READERS` and
      `ALLOWED` with the comment above them deleted where a render wrote them, and each place the
      check fails takes a kind of §10 or the input's sentence (ADR-0064). A publisher's shared
      package collects the same check, so a test of its own that builds an answer takes the
      mark there too (§10; ADR-0065, decision 3).
  14. Each way of ADR-0061 and each sentence of ADR-0060 that the source does not meet yet: a
      renamed read task, a reading beside its text, the arguments in upstream's order, a printed
      time read naive, and the tasks that fix filters, sorts, ranks or cuts left (§14).
  15. Code that core removed for its one consumer is copied in from `v0.4.1` by that consumer,
      `git show v0.4.1:<path>`: `naive_time` from `src/xippios/core/models.py`, `load_table` and
      `load_csv` from `src/xippios/core/reference.py`, `validate=` and `hints=` of `Tenants` from
      `src/xippios/core/tenants.py`, and `record_task` with `record_task_sync` from
      `src/xippios/core/testing/record.py`, each listed in the PR with the record that moved it
      (§15 item 3; ADR-0059, decision 2).
  16. A source behind a publisher's shared package imports the gateway's names from it, declares
      it with one minor through the template's answer, and deletes its tests of the gateway's
      own answers, the 429 cases and the quota policy's headers among them, which the shared
      package holds (ADR-0065, decisions 1 and 3; §12). The shared package's gateway names the
      request of each of its three messages about an answer, the refusal of a key, the answer
      to a spent rate limit and the answer for an unknown route, with `request_description`,
      as §5 asks of a source's `classify`, though they came from core word for word (ADR-0030,
      decision 4; ADR-0043, decision 6; ADR-0065, decision 3). A package that builds on the
      script frames, a shared package's kit of the snapshot frame say, keeps them out of its
      root's imports, so that a source's run time loads no frame, as `xippios.core` keeps
      `xippios.core.refresh` out of its own (ADR-0062, decision 1).
  17. The adoption's `breaking` fragment names the core bound `~=0.5.0`, the template's tag
      `v0.5.0` and conventions 1.30, and each change of the first list that the adoption brings to
      its callers has its entry among the adoption's fragments (§15 item 9).
