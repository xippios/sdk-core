# ADR-0026: The host xippios-mcp

Status: Accepted · Date: 2026-10-29 · Decided by Johannes on 2026-10-29 (D109, D110 (4);
panel B's decisions 2 to 4 as amended; drafted by the family; decision 5's loopback rule
the session's recommendation, queue row 296)

## Context

Each source package runs its own MCP server from its own entry point, so a client that
wants several sources' tools configures one server per package (ADR-0021, decision 2),
and a server served beyond loopback is the deployment's to protect, since core adds no
authentication to MCP servers (ADR-0014's consequences). On 2026-10-29 an analysis panel
with Johannes, panel B, decided that the family gets a self-hosted MCP host: stdio
locally, streamable HTTP on a server, a Docker image and a Forge recipe; a config file
that names endpoints and groups (`mcp.xippios.com/<group>/mcp`), the secrets staying in
the environment; each package's own server mounted, a group combining several sources'
tools on one endpoint; tools included or excluded per source by exact task name, checked
at startup the way core checks result-cap keys; a bearer token first and OAuth later; an
allowed-hosts setting so it works behind a reverse proxy (its decision 2). Its decision
3 named the servers of a source with write tools `-read` and `-write`, with no alias
since nobody uses the packages yet, groups following the rule and startup refusing a
group that mixes read and write; its decision 4 asked the template for a package
contract and for tool errors flagged `isError`. Johannes confirmed and amended them in
the interview of the same day (D109 (2) to (4)).

Two proofs of concept of panel B's, read as data and never run in this package, bound
the design; queue row 289 keeps their counts:

- The mount: one process, one Starlette app that mounts each package's own server by
  path, each server's streamable-HTTP app under its own prefix, served by uvicorn on
  loopback: sdk-usda-nass's module-level `server` with 16 tools, sdk-cashctrl's read
  server from `build()` with 24 and its write server with 11. Each package builds its
  own server, so sdk-cashctrl's organisation lock and its split into a read and a write
  server stay inside the package.
- The umbrella: one `MCPServer` with the tasks of nine packages registered through
  `register_tasks`, 130 tools on one server. The source name of each package came from
  its private `_client.SOURCE`, since no package exports a public one.

The claude.ai edge, from the investigation of 2026-10-29
(`coordination/reviews/2026-10-29-gmail-investigation.md` in the coordination
repository, F11 to F15 and its §2.5): "A `401` is required to start sign-in", with
`WWW-Authenticate: Bearer resource_metadata="..."`; a client registers by DCR or CIMD,
with PKCE S256 and RFC 8707's `resource` (F11), and Claude Code does the same (F12).
Pomerium Core is itself the OAuth authorization server toward the client, advertises
CIMD, accepts loopback redirects on any port for `localhost` and `127.0.0.1`, signs the
operator in at their own Google or GitHub and requires no authentication logic of the
server behind it (F13; F15, the identity provider's client). oauth2-proxy is no
authorization server, Cloudflare Access binds the operator to a domain on Cloudflare,
and sigbit/mcp-auth-proxy has had no release in five months (F14).

Core and the packages, read in the local checkouts on 2026-10-29: core's `_answer`
builds an error answer's `CallToolResult` without `isError` (queue row 283), so a client
tells an error answer from data only by its text, `error: <ErrorClass>: <message>`
(conventions §8); `build_server` names a server `xippios-<source>` unless it is given a
name; sdk-usda-nass exposes a module-level `server` in `mcp.py`; sdk-cashctrl has
`build()` and `server` in `mcp.py` and in `mcp_write.py`, its write server named
`xippios-cashctrl-write`, behind the entry points `xippios-cashctrl-mcp` and
`xippios-cashctrl-mcp-write`. For a loopback host without `transport_security`, the
`mcp` SDK turns on its DNS-rebinding protection, the Host and Origin checks (the comment
on `_LOOPBACK_HOSTS` in core's `mcp/cli.py`).

## Decision

1. **A public package that is no source.** The host is the package `xippios-mcp`: GitHub
   `xippios/xippios-mcp`, directory and session `xippios-mcp`, PyPI `xippios-mcp`,
   import `xippios.mcp` (D109 (2)); the one repository, package and session of the
   family not named `sdk-*` (the root `CLAUDE.md`'s exception, queue row 287). It has no
   tasks, no `api/`, no fixtures and no `docs/upstream/` snapshot. It is scaffolded by
   hand from the template's shared files (`ci.yml` with the gates caller, `publish.yml`,
   pre-commit, ruff, `pyproject.toml`, the PR template) and records the deviation in its
   `CLAUDE.md`; a host flavour of the scaffold is the template's part of queue row 284
   (row 289). Of the conventions, decisions 2 (§7), 4, 5, 6 (§8's error text) and 7
   below bind it, and decision 9 exempts it from §12's one-minor bound; the shared files
   it is scaffolded from carry §11's tooling, §12's release train and §13's hygiene to
   it; the rules written for a source's layers, envelope, fixtures and adoption have
   nothing to bind in it.
2. **0.1.0 runs on today's packages**: stdio locally, streamable HTTP on a server, a
   Docker image (D109 (2)) and the Forge recipe (queue row 289). A config file names the
   endpoints and the groups (`mcp.xippios.com/<group>/mcp`); the secrets stay in the
   environment and never in the file (conventions §7).
3. **Mounted by path.** Each endpoint mounts one or more packages' existing servers by
   path in one process, and a group combines several sources' tools on one endpoint (the
   two proofs of concept). A package's server is built by the package, its lock and its
   read and write split included.
4. **Groups and tool lists are checked at startup.** A group never mixes read and write
   tools; startup refuses one that does. Tools are included or excluded per source by
   exact task name, and a name that names no task of the source is refused at startup,
   as `build_server` refuses a key of `caps` that names no task that becomes a tool
   (panel B's decision 2; D109).
5. **Per-endpoint auth.** Each endpoint's auth is none or a bearer token from 0.1.0, the
   bearer the default (D109 (2)). The allowed hosts and `transport_security` are stated
   in the config, so the host works behind a reverse proxy. The loopback rules of
   ADR-0014, decision 9, and ADR-0025, D-a, run in core's `main` and in a source's
   `apply_options`, which the host does not use (the mount proof serves each server's
   `streamable_http_app` under uvicorn), so the host applies them itself: an endpoint
   with `auth: none` that serves a write server (core's `is_write_server`, importable
   from `xippios.core.mcp.server`, outside core's public surface; whether core 0.4.0
   exports it, with `register_tasks`, is queue row 297) binds a loopback host only, and
   startup refuses it on another host unless the endpoint sets `allow_remote: true`. A
   read server a source holds to loopback is covered the same way once core carries the
   `loopback_only` option (queue row 282), of which the host is the second consumer
   (ADR-0023, decision 2), so the option enters core 0.4.0 and the host reads it from
   its 0.2.0 interface (decision 8, queue row 284); until then an endpoint with `auth:
   none` that mounts sdk-google-mail's read server is the operator's to keep on
   loopback, which the host's README says. This is the session's recommendation of
   2026-10-29, queue row 296; Johannes can overturn it at G3 of the conventions 1.23 PR.
6. **Error answers are flagged.** Once core sets `isError` on an error answer (queue row
   283; ADR-0023, decision 3 (c): one signature for every adapter), the host reads the
   flag; until then it reads the text `error: <ErrorClass>: <message>` of conventions
   §8.
7. **The names** (D109 (3)). A source with a write server names its servers
   `xippios-<source>-mcp-read` and `xippios-<source>-mcp-write`, with no alias for the
   old name, since nobody uses the packages yet; a read-only source keeps
   `xippios-<source>-mcp`; a host group follows the rule (`accounting-read`,
   `accounting-write`); `server.name` stays the slug. The rule binds sdk-cashctrl at its
   0.4.0, a breaking change of an entry point under conventions §12 (queue row 286), and
   sdk-google-mail from its 0.1.0 (queue row 280).
8. **What 0.1.0 reads.** The host's 0.1.0 reads `xippios.<pkg>.mcp.server`
   (`mcp_write.server` for a write server) and `server.name` as the packages have them
   today. Queue row 284's package contract, a public `build(**options)`, the package's
   environment variables as `EnvVar` entries, a public `SOURCE`, an entry point, and a
   copier answer that renders the `-read` and `-write` names, lands in template v0.4.0
   and is the host's 0.2.0 interface (D109 (4)).
9. **The sources are extras with `>=` bounds.** The host declares each source package as
   an extra with a `>=` lower bound: an exception to ADR-0021's decision 1, and to the
   one-minor `~=` bound of conventions §12, for the host alone, since it serves every
   package at its latest (D109 (2)). Its first joint resolve follows queue row 260,
   sdk-usda-wasde's adoption of xippios-usda-esmis 0.2.0 (D106; queue row 269).
10. **The claude.ai edge** (D110 (4)). claude.ai needs an OAuth authorization server in
    front of the host: it starts sign-in on a 401 with `WWW-Authenticate: Bearer
    resource_metadata="..."` and needs PKCE S256, RFC 8707's `resource` and DCR or CIMD
    (F11), as Claude Code does (F12), so a bearer token alone does not serve claude.ai.
    The runbook's choice of 2026-10-29 is Pomerium Core (F13, F14). The runbook is
    written when the host first serves claude.ai, and Pomerium fronts the host as a
    whole (D109 (2)); no source package carries it (D108).

## Consequences

- Conventions 1.23: its version line applies the conventions to the host where this ADR
  binds it (decision 1); §1's entry-point row and §8 name the servers by decision 7; §8
  carries the group rule and `isError`, which binds a source from its adoption of the
  core release that carries the code (core 0.4.0 as planned, queue row 283).
- Dated lines under ADR-0014 (the host, with its per-endpoint bearer and the
  authorization server in front, is the deployment that protects a write server beyond
  loopback) and ADR-0021 (the `>=` exception, in its amendment of 2026-10-29).
- Queue rows: 282 (`loopback_only`, the host its second consumer, core 0.4.0), 283
  (`isError`, core 0.4.0), 284 (the package contract and the host flavour of the
  scaffold, template v0.4.0), 286 (sdk-cashctrl's `-read` at its 0.4.0), 287 (the root's
  naming exception and the guard), 289 (the host's 0.1.0), 296 (the host applies the
  loopback rules itself), 297 (the export of `register_tasks` and `is_write_server`,
  core 0.4.0). The host's briefing is written once this ADR is on sdk-core `main`.
- Core still adds no authentication to MCP servers (ADR-0014): the bearer and the
  authorization server are the host's and its deployment's.

## Amendment 2026-10-30

Five dated lines from the host's 0.1.0 package and D114, all of queue row 306.

(a) **Host-built servers** (decisions 3 and 8; Johannes 2026-10-29, the host's G5
question 2). A single package without a tool list mounts its own server as built. A
group, or an endpoint with an include or exclude list, is one `MCPServer` the host builds
with `register_tasks` over the kept names of `tasks.__all__` (of `tasks_write.__all__`
with `read_only=False`), `MCP_CAPS` cut to the kept tasks first, its slug the config's
package key, never `server.name`. So decision 3's "a package's server is built by the
package" holds for the first case only, and decision 8's list of what 0.1.0 reads gains
`tasks.__all__`, `tasks_write.__all__` and `MCP_CAPS`. A host-built server lacks the
package's instructions, version, hooks and locks until the package contract of decision
8 carries them, at the minor (e) names.

(b) **No Forge recipe in the public repository** (decision 2; Johannes 2026-10-29, the
host's G5 question 4). Decision 2's Forge recipe (queue row 289) stays out of the public
repository and out of row 289's scope; the host's PR 4 of 0.1.0 is the Dockerfile and its
CI build only.

(c) **The entry point** (decision 1). The host's entry point is `xippios-mcp`, the host's
briefing's recommendation after conventions §1's `xippios-<source>-mcp`, approved by
Johannes at its G1 on 2026-10-29.

(d) **Endpoint names are the operator's** (decision 7; the host session's, row 306 (d)).
The host does not check an endpoint's name against the `-read` and `-write` rule, an
endpoint name being any path segment; the rule is the operator's to follow, and the
host's sample config follows it. Decision 4's refusal of a group that mixes read and
write tools is unchanged.

(e) **The host's minors** (decision 9; D114, Johannes 2026-10-29). The host has no
dependents, so its minors cost nobody an adoption: an added surface bumps its minor as
SemVer reads it, and its next release is 0.2.0 (the wasde and google-mail extras, a
Dependabot config, a config check). The package contract of decision 8 and D109 (2)
lands at the host's first minor after core 0.4.0 and template v0.4.0, not at 0.2.0, and
decision 8's "the host's 0.2.0 interface", with decision 5's reading of `loopback_only`
from it, means that minor. The sources keep D110 (1) and conventions §12's patch slot
for the `~=` bound of their dependents.
