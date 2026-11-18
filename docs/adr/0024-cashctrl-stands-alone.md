# ADR-0024: cashctrl stands alone — tenants, the tenant lock and the recorder extras leave core

Status: Accepted · Date: 2026-10-27 · Decided by Johannes on 2026-10-25 (sdk-cashctrl
stands alone on one core minor) and on 2026-10-27 (the family check's write-server test,
the recorder's `rewrite` and verify) · Decision 6 reversed in part by ADR-0025 (2026-10-29) ·
Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

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
   decisions 1 to 4, 6, 7 and 11 and two consequences: the template's `multi_tenant`
   question, and the in-process client tests of `tests/mcp/test_lock.py` as the guard of
   the `mcp` SDK's provisional middleware API, which the argument check's tests through
   `mcp_call_text` are now.
2. **What core keeps, and why.** `ResultMeta.tenant` (ADR-0014, decision 5) is a field
   of the envelope every source returns, `None` for a single-tenant source: a family
   invariant (ADR-0023, decision 3 (a)). The `confirm: bool = False` check of
   `register_tasks(read_only=False)`, `is_write_server` and `main`'s loopback rule with
   `--allow-remote` (decision 9) stay because conventions §8 requires them of every
   write server and the family review's C8 keeps them in core; the template's cleanup
   drops its write scaffold (T2), not the rule. `main`'s option hooks (decision 8)
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

- sdk-cashctrl's adoption of 0.3.0 copies the code from the commit on `main` that merges
  the PR before this move, named in `docs/handover.md`'s Adopting core 0.3.0 section
  (`git show <that sha>:<path>`): `src/xippios/core/tenants.py` as a module of its own;
  `src/xippios/core/mcp/server.py` for the lock (`TenantLock` and the functions that
  served it), which becomes a wrapper that binds `org` on its tools, no middleware, as
  the family review's C8 has it, so its tests follow the wrapper and no middleware order
  is involved; decision 7 of ADR-0014 binds it no longer.
  `src/xippios/core/testing/adapters.py` for `assert_write_tools`, which it extends with
  a check that `confirm` is the last parameter (queue row 26 f);
  `src/xippios/core/testing/scrub.py` for the host placeholder, the percent-encoded
  matching, the JSON-decoded verify and `rewrite`, into `scripts/record_fixture.py`. The
  tests come from `tests/test_tenants.py`, `tests/mcp/test_lock.py`,
  `tests/testing/test_adapters.py`, `tests/testing/test_scrub.py`,
  `tests/testing/test_fixtures.py` and `tests/testing/test_record_replay.py` at the same
  commit. `Tenants.client_for`, which drops a replaced client without closing it (queue
  row 24 b), goes with the code. `CHANGELOG.md` lists the files to change under
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
- ADR-0019's text cut spares a secret value, no longer the request host (a dated line
  there); ADR-0005, ADR-0013, ADR-0014, ADR-0017 and ADR-0023 get one each as well.
- Conventions 1.21: §1 names the per-tenant variables as sdk-cashctrl's scheme; §3 makes
  the rewrite by key the source's own recorder step; §7 has a multi-tenant source carry
  its tenant registry itself; §8 loses the tenant list and the lock and keeps the write
  server's rules; §10 loses the placeholder host and the JSON-aware verify, keeps the
  plain verify and `allow_binary`, and the family check no longer names the write
  server.

Amended 2026-10-29 (ADR-0025, D-d; decided by Johannes on 2026-10-29, D108 and D109
(5)): decision 6, "nothing replaces what leaves", is reversed for the pieces queue row
281 names, (a) `Tenants`, (b) `list_task`, (c) the binding lock wrapper sdk-cashctrl
built in place of the middleware, (d) `assert_write_tools` and (e) the demo-only
conftest strip, with (f) the `_cli.py` serve command. sdk-google-mail copies them from
sdk-cashctrl under ADR-0023, decision 4, so each has two consumers (ADR-0023, decision
2), and they return to core in 0.4.0. The rest of this ADR stands, the recorder's extras
(decisions 3 and 4) among it.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **Core exports the writer** (step 10; https://github.com/xippios/sdk-core/issues/125,
found by sdk-usda-wasde; decided by Johannes on 2026-11-17,
https://github.com/xippios/sdk-core/issues/236). Decision 4's "core adds no writer" is
reversed: four sources copied core's private one, sdk-cashctrl, sdk-google-mail and sdk-x
in their recorders and sdk-usda-wasde in its sample cutter, and code that two consumers
carry is core's (ADR-0023, decision 2). `xippios.core.testing` exports
`write_fixture(fixture, path)`, which writes a `Fixture` laid out as `record` writes it,
and `fixture_text(fixture)`, which gives that text; both refuse a fixture that
`load_fixture` would not read back, since `model_copy` checks nothing. `write_fixture`
took a response before and was no export; `write_fixture(fixture_from_response(response,
scrub=...), path)` does what it did. The rewrite stays the source's step, and core still
adds no hook for it.

(b) **`Tenants` and `list_task` return** (decision 6; step 3, the first two pieces of
https://github.com/xippios/sdk-core/issues/166; decided by Johannes on 2026-10-29, D108
and D109 (5), ADR-0025, D-d). Decision 6, "nothing replaces what leaves", is reversed for
`Tenants` and `list_task`: sdk-cashctrl carries them since 0.3.0 and sdk-google-mail copied
them from it, two consumers (ADR-0023, decision 2). Of decision 1, `xippios.core.tenants`
returns, and both names are exported from `xippios.core`. The code is the copies', with the
close that the consequences left to sdk-cashctrl (queue row 24 b): `client_for` closes the
client that a changed variable replaces, on the running loop or, outside one, on core's
background loop. Where the copies differ, core takes sdk-google-mail's: `list_task(...,
source=None)` names the source of `meta.source`, the registry's slug by default. New in
neither copy, `Tenants(source, *, var_prefix=None, ...)` takes the variables' prefix apart
from the source slug, since sdk-google-mail's copy took the `GOOGLE_` prefix as its source
and its errors named `google` (ADR-0014, amendment 2026-11-18, (c); ADR-0025, amendment
2026-11-18, (b)). The lock wrapper, `assert_write_tools`, the conftest strip and the serve
command stay the sources' until they return in turn.

(c) **`Scrub` reads secrets from the answer** (decisions 2 and 3; step 11;
https://github.com/xippios/sdk-core/issues/164, found by sdk-faostat).
`Scrub(response_secrets=...)` takes a function of the response that returns the values
that must never be written, for a value known only once upstream answers, such as a
login's or a refresh's tokens, whose names (`AccessToken`, `IdToken`, `RefreshToken`)
the credential rule does not match. The recorder calls it once, with the whole answer,
an error answer included and before any cut, and scrubs and verifies each value it
returns as decision 3 does a named one, so such an exchange records through
`record_sync` instead of a step of the source's own. One string, a value that is no
string and an empty value are refused, with nothing written. sdk-faostat wrote its
login fixture outside `record_sync` for this reason, and sdk-google-mail reads the
tokens from the answer before it names them; secret scrubbing stays core's (ADR-0023,
decision 3 (b)). Decision 4 stands: a rewrite by key stays the source's step.

(d) **The lock, the serve command, the write checks and the strip return** (decision 6;
step 4, the other four pieces of https://github.com/xippios/sdk-core/issues/166; decided by
Johannes on 2026-10-29, D108 and D109 (5), ADR-0025, D-d). Decision 6 is reversed for the
rest of the kit, which sdk-cashctrl carries since 0.3.0 and sdk-google-mail copied from it,
two consumers (ADR-0023, decision 2): the binding lock wrapper, `TenantLock` with
`bind_tasks` and `tenant_instructions` in `xippios.core.tenants`, one name for
sdk-cashctrl's `OrgLock` and sdk-google-mail's `AccountLock` (ADR-0014, amendment
2026-11-18, (d)); the serve command, `xippios.core.mcp.serve_tenants`;
`assert_write_tools`, async now, back in `xippios.core.testing` with sdk-cashctrl's check
that `confirm` is the last parameter (queue row 26 f); and the demo-only strip,
`keep_reserved_tenants(tenants)` in `xippios.core.testing`. Of decision 1,
`assert_write_tools` returns as the helper of a source's own test: the family check tests
no write server still, and a source tests its write server with it, which fails the test
unless the server is a write server whose tools are exactly the write tasks, each taking
`confirm: bool = False` as its last parameter, and none of them a tool of the read server
or a route of the router. A multi-tenant source's `tests/conftest.py` calls
`keep_reserved_tenants(TENANTS)` when pytest imports it. Where the copies differ, core
takes sdk-google-mail's: `tenant_instructions(..., bound=...)`, the bound server's own
text, which sdk-cashctrl's `instructions` lacked, and the strip by the registry's scheme,
the list variable and every other tenant's field variables, which keeps the rest of a
shared prefix, the Google client's variables, where sdk-cashctrl's removed every variable
under its prefix but demo's pair. The two serve commands checked a bound tenant each in its
own way, sdk-cashctrl its subdomain through `Tenants.field` and sdk-google-mail that its
refresh token is set, so `serve_tenants` takes that check from the source as `check`. The
rest of this ADR stands, the recorder's extras (decisions 3 and 4) among it.
