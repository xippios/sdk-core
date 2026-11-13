# Architecture decision records

The decisions of this repository, one line per record, written by `scripts/adr_index.py` from
the headers of the records in `docs/adr/`. A record changes, and this file follows when the
script runs again.

- [ADR-0001](adr/0001-three-layer-architecture.md): Three-layer architecture for source packages · Accepted · 2026-10-20
- [ADR-0002](adr/0002-runtime-stack.md): Runtime stack — Python 3.12, httpx, pydantic v2, sync facade over async core · Accepted · 2026-10-20
- [ADR-0003](adr/0003-upstream-fidelity.md): Upstream fidelity — no cross-source normalization in SDK packages · Accepted · 2026-10-20
- [ADR-0004](adr/0004-core-layout-and-mcp-sdk.md): Core internal layout, dependency direction and MCP SDK choice · Accepted · 2026-10-20
- [ADR-0005](adr/0005-no-credentials-in-envelope.md): Credentials never enter the result envelope; core is exempt from the upstream snapshot · Accepted · 2026-10-22
- [ADR-0006](adr/0006-nested-namespace-for-multi-api-providers.md): Nested import path for providers with several APIs · Accepted · 2026-10-22
- [ADR-0007](adr/0007-invalid-request-error-and-post-routes.md): InvalidRequestError, and POST routes for non-scalar task parameters · Accepted · 2026-10-22
- [ADR-0008](adr/0008-hardening-from-the-first-source.md): Hardening core from the first source package · Accepted · 2026-10-22
- [ADR-0009](adr/0009-one-key-per-issuer-for-shared-gateways.md): One key variable per issuer when one key serves several sources · Accepted · 2026-10-23
- [ADR-0010](adr/0010-rate-limit-policy.md): Rate-limit policy — a fast pace, quotas spent, the 429 interpreted · Accepted · 2026-10-23
- [ADR-0011](adr/0011-retries-and-non-idempotent-methods.md): Retries — a 429 for every method, a 5xx and a transport failure for idempotent ones · Accepted · 2026-10-23
- [ADR-0012](adr/0012-upstream-totals-in-the-result-envelope.md): Upstream totals in the result envelope · Accepted · 2026-10-23
- [ADR-0013](adr/0013-offline-tests-guaranteed-by-the-plugin.md): Offline tests guaranteed by the plugin · Accepted · 2026-10-23
- [ADR-0014](adr/0014-multi-tenant-sources.md): Multi-tenant sources · Accepted · 2026-10-23
- [ADR-0015](adr/0015-client-request-hooks-and-quota-policy.md): Client request hooks and a quota policy · Accepted · 2026-10-24
- [ADR-0016](adr/0016-per-tool-result-caps.md): Per-tool result caps · Accepted · 2026-10-24
- [ADR-0017](adr/0017-sensitive-upstream-fields.md): Sensitive upstream fields — personal identifiers stay out of task projections · Accepted · 2026-10-25
- [ADR-0018](adr/0018-core-versioning-and-source-adoption.md): Core versioning and source adoption · Accepted · 2026-10-25
- [ADR-0019](adr/0019-bulk-downloads-and-non-json-payloads.md): Bulk downloads and non-JSON payloads in core · Accepted · 2026-10-26
- [ADR-0020](adr/0020-file-distributed-sources.md): File-distributed sources · Accepted · 2026-10-26
- [ADR-0021](adr/0021-dependencies-between-source-packages.md): Dependencies between source packages · Accepted · 2026-10-26
- [ADR-0022](adr/0022-packaged-answers-and-release-times.md): Packaged answers and release times in `ResultMeta` · Accepted · 2026-10-26
- [ADR-0023](adr/0023-core-scope-two-consumers.md): Core scope — code enters `xippios-core` with two consumers · Accepted · 2026-10-26
- [ADR-0024](adr/0024-cashctrl-stands-alone.md): cashctrl stands alone — tenants, the tenant lock and the recorder extras leave core · Accepted · 2026-10-27
- [ADR-0025](adr/0025-google-mail.md): Google Mail — loopback, the renewing bearer, scopes, the kit's return and the decoded view · Accepted · 2026-10-29
- [ADR-0026](adr/0026-the-host-xippios-mcp.md): The host xippios-mcp · Accepted · 2026-10-29
- [ADR-0027](adr/0027-x-metered-content-source.md): X as a metered, content-bearing source · Accepted · 2026-10-30
