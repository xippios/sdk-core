# ADR-0042: The recorder extras stay the source's, and the multi-tenant kit returns to core

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0024

## Context

ADR-0014 moved sdk-cashctrl's tenant registry, its lock and its write checks into core, and
ADR-0013 and ADR-0017 its recorder's extras, on the expectation of a second multi-tenant
source that did not come; the family review of 2026-10-25 counted them among the names with
one consumer. Johannes decided on 2026-10-25 that sdk-cashctrl stands alone on one core minor,
and on 2026-10-27 that the family check no longer tests a source's write server and that
`Scrub.rewrite` leaves core while core keeps a plain verify. sdk-google-mail then copied the
kit, which gave it two consumers. This record states ADR-0024, titled "cashctrl stands alone
— tenants, the tenant lock and the recorder extras leave core", with its reversal in part by
ADR-0025 of 2026-10-29 and its amendment of 2026-11-18 as they stand, and changes no
decision; its title says what stands, and their history stays in ADR-0024.

## Decision

1. **What left core in 0.3.0, and what returned in 0.4.0.** Core 0.3.0 removed
   `xippios.core.tenants` (`Tenants`, `list_task` and the marker the MCP adapter read);
   `TenantLock` with its middleware, the refusal of a defaulted tenant parameter, the
   instructions sentence, the narrowing of the tenant list on a locked server and the
   `tenant_lock=` parameter of `build_server` and `register_tasks`; `assert_write_tools`;
   `Scrub(host=...)` with its checks and the placeholder, the percent-encoded matching of
   secrets, the JSON-decoded verify, the host check of the verify, and `Scrub(rewrite=...)`;
   and the family check's `test_family_write_server_serves_the_write_tasks`. Of these, the
   kit returns in 0.4.0, as decision 6 has it: `xippios.core.tenants` with `Tenants` and
   `list_task`, both exported from `xippios.core`; the binding lock wrapper, `TenantLock`
   with `bind_tasks` and `tenant_instructions`, one name for sdk-cashctrl's `OrgLock` and
   sdk-google-mail's `AccountLock` (ADR-0036, decisions 1, 3, 6 and 7); the serve command,
   `xippios.core.mcp.serve_tenants` (ADR-0036, decision 8); `assert_write_tools`, async,
   in `xippios.core.testing`; and the demo-only strip, `keep_reserved_tenants(tenants)` in
   `xippios.core.testing`, which a multi-tenant source's `tests/conftest.py` calls when
   pytest imports it. Where the two copies differ, core takes sdk-google-mail's:
   `list_task(..., source=...)`, `tenant_instructions(..., bound=...)`, and the strip by the
   registry's scheme, the list variable and every other tenant's field variables, which
   keeps the rest of a shared prefix. `serve_tenants` takes the check of a bound tenant from
   the source as `check`. The family check tests no write server still: `assert_write_tools`
   is the helper of a source's own test, which fails unless the server is a write server
   whose tools are exactly the write tasks, each taking `confirm: bool = False` as its last
   parameter, and none of them a tool of the read server or a route of the router. The
   recorder's extras stay out of core.
2. **What core keeps, and why.** `ResultMeta.tenant` (ADR-0036, decision 5) is a field of the
   envelope every source returns, `None` for a single-tenant source: a family invariant
   (ADR-0023, decision 3 (a)). The `confirm: bool = False` check of
   `register_tasks(read_only=False)`, `is_write_server` and `main`'s loopback rule with
   `--allow-remote` (ADR-0036, decision 9) stay because conventions §8 requires them of
   every write server. `main`'s option hooks (ADR-0036, decision 8) and `mcp_call` and
   `mcp_call_text` through the in-process client (ADR-0036, decision 10) are every source's
   entry point and test path (3 (a) and (c)). `Scrub(secrets=...)`,
   `Scrub(response_secrets=...)`, `allow_binary` and the verify are secret scrubbing in
   recorded fixtures (3 (b)).
3. **A plain verify is ADR-0030's backstop.** `Scrub(secrets=...)` replaces each value as
   given, the longest first, in the letter case given, in the URL, the headers and the text
   bodies. Before anything is kept or written, the verify searches the URL, every header
   value and both text bodies for each value as given, a plain substring; `REDACTED` is
   masked first. A hit refuses the exchange with a message that names the location
   (`request URL`, `response header 'location'`, `response body`) and never the value. A
   percent-encoded form, a form behind a JSON escape and the tenant's host are the source's
   to look for, in its recorder, so a recording whose secret appears only percent-encoded or
   behind a JSON escape is not refused by core. `Scrub(response_secrets=...)` takes a
   function of the response that returns the values that must never be written, for a value
   known only once upstream answers, such as a login's or a refresh's tokens, whose names
   (`AccessToken`, `IdToken`, `RefreshToken`) the credential rule does not match. The
   recorder calls it once, with the whole answer, an error answer included and before any
   cut, and scrubs and verifies each value it returns as it does a named one, so such an
   exchange records through `record_sync`. One string, a value that is no string and an
   empty value are refused, with nothing written.
4. **Rewriting is the source's step, with core's writer.** A source that rewrites a fixture's
   values by key, or its host, does so on the `Fixture` that `fixture_from_response` returns
   and writes the result with core's writer; core adds no hook for it. "Export the writer"
   (https://github.com/xippios/sdk-core/issues/236): `xippios.core.testing` exports
   `write_fixture(fixture, path)`, which writes a `Fixture` laid out as `record` writes it,
   and `fixture_text(fixture)`, which gives that text; both refuse a fixture that
   `load_fixture` would not read back, since `model_copy` checks nothing.
   `write_fixture(fixture_from_response(response, scrub=...), path)` writes a response's
   fixture.
5. **The binary refusal states the rule.** A body that is not UTF-8 text is refused with "a
   binary body cannot be scrubbed; the recording is refused unless Scrub(allow_binary=True)
   stores it base64, flagged", which does not tell every caller to pass the flag.
6. **Nothing replaces the recorder's extras.** For what stays out of core, no new helper and
   no compatibility alias: the code was removed as it stood, and sdk-cashctrl copied it from
   the last commit that held it (ADR-0023, decision 5), its recorder's into
   `scripts/record_fixture.py`. For the kit, six pieces, `Tenants`, `list_task`, the binding
   lock wrapper, `assert_write_tools`, the demo-only conftest strip and the serve command,
   the decision is reversed: sdk-google-mail copied them from sdk-cashctrl, so each has two
   consumers (ADR-0023, decision 2), and they return to core in 0.4.0. Johannes decided the
   return on 2026-10-29 (D108, D109 (5); ADR-0025, D-d).

## Consequences

- The family check reads `tasks_write` for its two task checks and the README status table;
  a source's write server is its own to test.

Conventions §1, §3, §7, §8, §10 and §15, the definition of done's Adoption PR block, the
README and the docstrings of `xippios.core.tenants`, `xippios.core.testing`,
`keep_reserved_tenants`, the family check, the fixtures and `Scrub` state its decisions from
1.28 on.
