# ADR-0024: cashctrl stands alone — tenants, the tenant lock, the write-server check and the recorder extras leave core

Status: Accepted · Date: 2026-10-27 · Decided by Johannes on 2026-10-25 (sdk-cashctrl
stands alone on one core minor) and on 2026-10-27 (the family check's write-server test,
the recorder's `rewrite` and verify)

## Context

ADR-0014 (2026-10-23) moved sdk-cashctrl's organisation registry, its `--org` lock and
its write-server checks into core as `Tenants`, `list_task`, `TenantLock` and
`assert_write_tools`, on the expectation that a second multi-tenant source would need
them. ADR-0013 and ADR-0017 did the same for its recorder: a placeholder for the tenant's
host, secrets matched plain or percent-encoded, a verify that decodes JSON bodies, and a
`rewrite` hook for values only the source knows how to neutralise. No second consumer
came. The family review of 2026-10-25 counted these names among the 24 with exactly one
consumer and scheduled their move to sdk-cashctrl as C8 (tenants, the lock, the write
checks) and C9 (the recorder's host placeholder, the encoded matching and the JSON
verify). Johannes decided on 2026-10-25 that sdk-cashctrl stands alone on one core
minor, its tenants, its lock and its write checks leaving core in 0.3.0. ADR-0023
(2026-10-26) gives the test: code with one consumer stays in core only for a reason of
its decision 3, and its consequences name C8 as failing it and cashctrl's recorder
extras as cashctrl's under decision 3 (b), whose closed list leaves "a recorder's
pre-write hooks" to the source. On 2026-10-27 Johannes decided the two open points: the
family check no longer tests a source's write server, which cashctrl tests itself with
the moved helper; and `Scrub.rewrite` leaves core with C9, while core keeps a plain
verify.

## Decision

1. **What leaves core in 0.3.0.** `xippios.core.tenants` (`Tenants`, `list_task` and
   the marker the MCP adapter read); `TenantLock` with its middleware, the refusal of a
   defaulted tenant parameter, the instructions sentence, the narrowing of the tenant
   list on a locked server and the `tenant_lock=` parameter of `build_server` and
   `register_tasks`; `assert_write_tools`; `Scrub(host=...)` with its checks and the
   placeholder, the percent-encoded matching of secrets, the JSON-decoded verify, the
   host check of the verify, and `Scrub(rewrite=...)`; the family check's
   `test_family_write_server_serves_the_write_tasks`. Of ADR-0014 this supersedes
   decisions 1 to 4, 6, 7 and 11 and the consequence that has a source call
   `assert_write_tools`.
2. **What core keeps, and why.** `ResultMeta.tenant` (ADR-0014, decision 5) is a field
   of the envelope every source returns, `None` for a single-tenant source: a family
   invariant (ADR-0023, decision 3 (a)). The `confirm: bool = False` check of
   `register_tasks(read_only=False)`, `is_write_server` and `main`'s loopback rule with
   `--allow-remote` (decision 9) are what conventions §8 requires of any write server,
   so they are invariants of the family's write servers (3 (a)); the template's
   cleanup drops its write scaffold, not the rule. `main`'s option hooks (decision 8)
   and `mcp_call` and `mcp_call_text` through the in-process client (decision 10) are
   every source's entry point and test path (3 (a) and (c)). `Scrub(secrets=...)`,
   `allow_binary` and the verify are secret scrubbing in recorded fixtures (3 (b)).
3. **A plain verify is ADR-0005's backstop.** `Scrub(secrets=...)` replaces each value
   as given, the longest first, in the letter case given, in the URL, the headers and
   the text bodies. Before anything is kept or written, the verify searches the URL,
   every header value and both text bodies for each value as given, a plain substring;
   `REDACTED` is masked first. A hit refuses the exchange with a message that names the
   location (`request URL`, `response header 'location'`, `response body`) and never
   the value. A percent-encoded form, a form behind a JSON escape and the tenant's host
   are the source's to look for, in its recorder.
4. **Rewriting is the source's step.** A source that rewrites a fixture's values by key,
   or its host, does so on the `Fixture` that `fixture_from_response` returns and writes
   the result itself, as sdk-cashctrl's recorder already does. Core adds no hook and no
   writer for it.
5. **The binary refusal states the rule.** A body that is not UTF-8 text is refused
   with "a binary body cannot be scrubbed; the recording is refused unless
   Scrub(allow_binary=True) stores it base64, flagged", which no longer tells every
   caller to pass the flag (queue row 24 a).
6. **Nothing replaces what leaves.** No new helper, no compatibility alias: the code is
   removed as it stood and sdk-cashctrl copies it from the last commit that holds it
   (ADR-0023, decision 5; the family review's guard rail for 0.3.0).

## Consequences

- sdk-cashctrl's adoption of 0.3.0 copies the code from `git show 7814062:<path>`:
  `src/xippios/core/tenants.py` as a module of its own;
  `src/xippios/core/mcp/server.py` for the lock (`TenantLock` and the functions that
  served it), as a wrapper that binds `org` or as a middleware of its own, its choice,
  since decision 7 of ADR-0014 binds it no longer; `src/xippios/core/testing/adapters.py`
  for `assert_write_tools`, which it extends with a check that `confirm` is the last
  parameter (queue row 26 f); `src/xippios/core/testing/scrub.py` for the host
  placeholder, the percent-encoded matching, the JSON-decoded verify and `rewrite`, into
  `scripts/record_fixture.py`. The tests come from `tests/test_tenants.py`,
  `tests/mcp/test_lock.py`, `tests/testing/test_adapters.py`,
  `tests/testing/test_scrub.py` and `tests/testing/test_fixtures.py` at the same commit.
  `Tenants.client_for`, which drops a replaced client without closing it (queue row
  24 b), goes with the code. `CHANGELOG.md` lists the files to change under
  "Hand-apply for sources".
- The family check has ten tests. It still reads `tasks_write` for the two task checks
  and the README status table; a source's write server is its own to test.
- sdk-template: the `multi_tenant` question ADR-0014's consequences announced is not
  built (the family review's T1), and the template's 0.3.0 cleanup drops
  `needs_write_tools` and the generated write tests (T2).
- **Breaking**, pre-1.0 (conventions §12): `Tenants`, `TenantLock` and
  `assert_write_tools` leave the export lists (42 to 41, 8 to 7, 20 to 19 names),
  `build_server`, `register_tasks` and `Scrub` refuse the removed arguments, and a
  recording whose secret appears only percent-encoded or behind a JSON escape is no
  longer refused by core.
- Conventions 1.21: §1 names the per-tenant variables as sdk-cashctrl's scheme; §3 makes
  the rewrite by key the source's own recorder step; §7 has a multi-tenant source carry
  its tenant registry itself; §8 loses the tenant list and the lock and keeps the write
  server's rules; §10 loses the placeholder host and the JSON-aware verify, keeps the
  plain verify and `allow_binary`, and the family check no longer names the write
  server.
