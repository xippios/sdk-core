# Architecture decision records

The decisions of this repository, one line per record, written by `scripts/adr_index.py` from the headers of the
records in `docs/adr/`. A record changes, and this file follows when the script runs again.

- <a id="0001"></a>[ADR-0001](adr/0001-three-layer-architecture.md): Three-layer architecture for source packages · Accepted · 2026-10-20 · amended 2026-11-18
- <a id="0002"></a>[ADR-0002](adr/0002-runtime-stack.md): Runtime stack — Python 3.12, httpx, pydantic v2, sync facade over async core · Accepted · 2026-10-20
- <a id="0006"></a>[ADR-0006](adr/0006-nested-namespace-for-multi-api-providers.md): Nested import path for providers with several APIs · Accepted · 2026-10-22
- <a id="0007"></a>[ADR-0007](adr/0007-invalid-request-error-and-post-routes.md): InvalidRequestError, and POST routes for non-scalar task parameters · Accepted · 2026-10-22 · amended 2026-11-18
- <a id="0011"></a>[ADR-0011](adr/0011-retries-and-non-idempotent-methods.md): Retries — a 429 for every method, a 5xx and a transport failure for idempotent ones · Accepted · 2026-10-23
- <a id="0017"></a>[ADR-0017](adr/0017-sensitive-upstream-fields.md): Sensitive upstream fields — personal identifiers stay out of task projections · Accepted · 2026-10-25
- <a id="0020"></a>[ADR-0020](adr/0020-file-distributed-sources.md): File-distributed sources · Accepted · 2026-10-26 · amended 2026-11-18
- <a id="0021"></a>[ADR-0021](adr/0021-dependencies-between-source-packages.md): Dependencies between source packages · Accepted · 2026-10-26
- <a id="0023"></a>[ADR-0023](adr/0023-core-scope-two-consumers.md): Core scope — code enters `xippios-core` with two consumers · Accepted · 2026-10-26
- <a id="0025"></a>[ADR-0025](adr/0025-google-mail.md): Google Mail — loopback, the renewing bearer, scopes, the kit's return and the decoded view · Accepted · 2026-10-29 · amended 2026-11-18
- <a id="0026"></a>[ADR-0026](adr/0026-the-host-xippios-mcp.md): The host xippios-mcp · Accepted · 2026-10-29 · amended 2026-11-18
- <a id="0027"></a>[ADR-0027](adr/0027-x-metered-content-source.md): X as a metered, content-bearing source · Accepted · 2026-10-30
- <a id="0028"></a>[ADR-0028](adr/0028-upstream-fidelity.md): Upstream fidelity — no cross-source normalization in SDK packages · Accepted · 2026-11-18
- <a id="0029"></a>[ADR-0029](adr/0029-core-layout-and-mcp-sdk.md): Core internal layout, dependency direction and MCP SDK choice · Accepted · 2026-11-18
- <a id="0030"></a>[ADR-0030](adr/0030-no-credentials-in-envelope.md): Credentials never enter the result envelope; core is exempt from the upstream snapshot · Accepted · 2026-11-18
- <a id="0031"></a>[ADR-0031](adr/0031-hardening-from-the-first-source.md): Hardening core from the first source package · Accepted · 2026-11-18
- <a id="0032"></a>[ADR-0032](adr/0032-one-key-per-issuer-for-shared-gateways.md): One key variable per issuer when one key serves several sources · Accepted · 2026-11-18
- <a id="0033"></a>[ADR-0033](adr/0033-rate-limit-policy.md): Rate-limit policy — a fast pace, quotas spent, the 429 interpreted · Accepted · 2026-11-18
- <a id="0034"></a>[ADR-0034](adr/0034-upstream-totals-in-the-result-envelope.md): Upstream totals in the result envelope · Accepted · 2026-11-18
- <a id="0035"></a>[ADR-0035](adr/0035-offline-tests-guaranteed-by-the-plugin.md): Offline tests guaranteed by the plugin · Accepted · 2026-11-18
- <a id="0036"></a>[ADR-0036](adr/0036-multi-tenant-sources.md): Multi-tenant sources · Accepted · 2026-11-18
- <a id="0037"></a>[ADR-0037](adr/0037-client-request-hooks-and-quota-policy.md): Client request hooks and a quota policy · Accepted · 2026-11-18
- <a id="0038"></a>[ADR-0038](adr/0038-per-tool-result-caps.md): Per-tool result caps · Accepted · 2026-11-18
- <a id="0039"></a>[ADR-0039](adr/0039-core-versioning-and-source-adoption.md): Core versioning and source adoption · Accepted · 2026-11-18
- <a id="0040"></a>[ADR-0040](adr/0040-bulk-downloads-and-non-json-payloads.md): Bulk downloads and non-JSON payloads in core · Accepted · 2026-11-18
- <a id="0041"></a>[ADR-0041](adr/0041-packaged-answers-and-release-times.md): Packaged answers and release times in `ResultMeta` · Accepted · 2026-11-18
- <a id="0042"></a>[ADR-0042](adr/0042-the-recorder-extras-stay-the-sources.md): The recorder extras stay the source's, and the multi-tenant kit returns to core · Accepted · 2026-11-18
- <a id="0045"></a>[ADR-0045](adr/0045-one-check-of-an-argument-against-a-packaged-list.md): One check of an argument against a packaged list · Accepted · 2026-11-21

The superseded records follow, kept as written: the record that each status names holds its decision now.

- <a id="0003"></a>[ADR-0003](adr/0003-upstream-fidelity.md): Upstream fidelity — no cross-source normalization in SDK packages · Superseded by ADR-0028 · 2026-10-20 · amended 2026-11-18
- <a id="0004"></a>[ADR-0004](adr/0004-core-layout-and-mcp-sdk.md): Core internal layout, dependency direction and MCP SDK choice · Superseded by ADR-0029 · 2026-10-20
- <a id="0005"></a>[ADR-0005](adr/0005-no-credentials-in-envelope.md): Credentials never enter the result envelope; core is exempt from the upstream snapshot · Superseded by ADR-0030 · 2026-10-22 · amended 2026-11-18
- <a id="0008"></a>[ADR-0008](adr/0008-hardening-from-the-first-source.md): Hardening core from the first source package · Superseded by ADR-0031 · 2026-10-22 · amended 2026-11-18
- <a id="0009"></a>[ADR-0009](adr/0009-one-key-per-issuer-for-shared-gateways.md): One key variable per issuer when one key serves several sources · Superseded by ADR-0032 · 2026-10-23 · amended 2026-11-18
- <a id="0010"></a>[ADR-0010](adr/0010-rate-limit-policy.md): Rate-limit policy — a fast pace, quotas spent, the 429 interpreted · Superseded by ADR-0033 · 2026-10-23 · amended 2026-11-18
- <a id="0012"></a>[ADR-0012](adr/0012-upstream-totals-in-the-result-envelope.md): Upstream totals in the result envelope · Superseded by ADR-0034 · 2026-10-23 · amended 2026-11-18
- <a id="0013"></a>[ADR-0013](adr/0013-offline-tests-guaranteed-by-the-plugin.md): Offline tests guaranteed by the plugin · Superseded by ADR-0035 · 2026-10-23 · amended 2026-11-18
- <a id="0014"></a>[ADR-0014](adr/0014-multi-tenant-sources.md): Multi-tenant sources · Superseded by ADR-0036 · 2026-10-23 · amended 2026-11-18
- <a id="0015"></a>[ADR-0015](adr/0015-client-request-hooks-and-quota-policy.md): Client request hooks and a quota policy · Superseded by ADR-0037 · 2026-10-24 · amended 2026-11-18
- <a id="0016"></a>[ADR-0016](adr/0016-per-tool-result-caps.md): Per-tool result caps · Superseded by ADR-0038 · 2026-10-24 · amended 2026-11-18
- <a id="0018"></a>[ADR-0018](adr/0018-core-versioning-and-source-adoption.md): Core versioning and source adoption · Superseded by ADR-0039 · 2026-10-25 · amended 2026-11-18
- <a id="0019"></a>[ADR-0019](adr/0019-bulk-downloads-and-non-json-payloads.md): Bulk downloads and non-JSON payloads in core · Superseded by ADR-0040 · 2026-10-26 · amended 2026-11-18
- <a id="0022"></a>[ADR-0022](adr/0022-packaged-answers-and-release-times.md): Packaged answers and release times in `ResultMeta` · Superseded by ADR-0041 · 2026-10-26 · amended 2026-11-18
- <a id="0024"></a>[ADR-0024](adr/0024-cashctrl-stands-alone.md): cashctrl stands alone — tenants, the tenant lock and the recorder extras leave core · Superseded by ADR-0042 · 2026-10-27 · amended 2026-11-18
