# ADR-0014: Multi-tenant sources

Status: Accepted · Date: 2026-10-23

## Context

CashCtrl serves every organisation from a subdomain of its own
(`https://<subdomain>.cashctrl.com/api/v1`), and an API user, whose key is the HTTP basic
user name, belongs to exactly one organisation. A package for it cannot have one client:
every call has to say which organisation it is for, and the package needs that
organisation's subdomain and key to send it. The family had no notion of a tenant:
conventions §1 and §7 name one key variable per source, `ResultMeta` carries no tenant,
and `build_server` builds one server for whoever calls it.

sdk-cashctrl built what it needed itself, in its PR #5:

- An organisation registry in `_client.py`. `CASHCTRL_ORGS` lists the names,
  comma-separated; `CASHCTRL_<NAME>_SUBDOMAIN` and `CASHCTRL_<NAME>_API_KEY` hold each
  organisation's values. The reserved organisation `demo`, the synthetic one that
  fixtures, live tests and the recorder use, is declared by its own two variables and is
  never listed. `client_for(org)` keeps one client per organisation, with its own base
  URL, key and token bucket and no shared cache, rebuilt when the subdomain changes.
  An undeclared name is an `InvalidRequestError` listing the declared ones.
- Every task takes `org` first and records it in `meta.request`, where nothing marks it
  as the tenant.
- An `--org` option that locks either MCP server to one organisation (`_org_lock.py`).
  A middleware on the `mcp` SDK's middleware API, provisional in 2.x, answers a call
  naming another organisation with the family's error text before the tool runs. The
  instructions name the organisation by writing to the SDK's private low-level server,
  and the command line is parsed twice: once by a parser of its own, core's options plus
  `--org`, and once more by core's `main`.
- Tests that drive `mcp.Client(server)` by hand, because `xippios.core.testing.mcp_call`
  called `MCPServer.call_tool`, which bypasses the middleware and so cannot test a lock.

The organisation's host is treated like a key: it names the tenant, so core's error
messages leave it out and the request log is quieted (ADR-0005 and its amendment).

The review of that PR found most of it generic: any upstream that serves its tenants
from hosts or under keys of their own needs the same registry, the same lock and the same
test path, and a second source would copy the first. It asked whether the tenant belongs
in `ResultMeta` rather than only in `request`, for a reference tool listing the tenants,
for an option hook in `mcp.main` instead of a second parse, and for `mcp_call` to run the
middleware. Two gaps showed in the write server: `register_tasks(read_only=False)` did
not check that a task takes `confirm: bool = False`, which conventions §8 requires, and
`--http` served a write server, which carries no authentication, on any `--host`.

## Decision

1. **Tenants come from the environment.** `xippios.core.Tenants(source, *, list_var,
   fields, reserved=(), validate=None)` holds a source's scheme. `list_var` lists the
   tenant names, comma-separated, each matching `^[a-z0-9_]+$`, read on every call.
   Each tenant's values sit in `<SOURCE>_<NAME>_<FIELD>`, source and name upper-cased
   with `-` made `_` (`CASHCTRL_ACME_SUBDOMAIN`, `CASHCTRL_ACME_API_KEY`); `fields`
   names the suffixes and `validate` checks a value where the source knows its shape.
   This is sdk-cashctrl's scheme, so no environment changes.
2. **A reserved test tenant is declared by its own variables.** It exists when every one
   of its field variables is set and is never listed; listing it is a `ConfigError`. A
   deployment that does not set them has no test tenant.
3. **One client per tenant.** `Tenants.client_for(name, build)` builds a tenant's client
   with the source's `build` on first use and keeps it under a digest of the tenant's
   current values, so a changed value, the key included, builds a new client; the values
   themselves are not kept. `build` gives each tenant its own rate limiter and no cache
   shared with another tenant. The key is read on the first request (`EnvKeyAuth`), so a
   declared tenant without one fails then.
4. **Errors split by whose mistake it is.** A name that is not declared is the caller's:
   `InvalidRequestError` (ADR-0007), text over MCP and 422 over HTTP, listing the
   declared names, or the variables to set when there are none. A malformed list, or a
   missing or refused value of a declared tenant, is the operator's: `ConfigError`,
   naming the variable. No message carries a value.
5. **The tenant is in the envelope.** `ResultMeta.tenant: str | None`: the tenant the
   data came from, by name, set by every task of a multi-tenant source; never a
   credential, a host or another of the tenant's values. `None` for a single-tenant
   source and for the list of tenants.
6. **A list tool.** `xippios.core.tenants.list_task(tenants, *, name)` is a task with no
   argument that returns the declared names, names only (ADR-0005), registered as
   `<source>_list_<tenants>` (`cashctrl_list_organisations`), so an agent can form valid
   calls (conventions §8).
7. **The lock is a server option, implemented once.** `TenantLock(param, value)` in
   `xippios.core.mcp`. `build_server(..., tenant_lock=...)` and
   `register_tasks(..., tenant_lock=...)` install, once per server, a middleware that runs
   before every tool call. A tool that takes the tenant parameter must receive it on a
   locked server; a default is refused. A call whose `param` is `value` passes; one
   naming another tenant is answered with `error: InvalidRequestError: this server is
   locked to <param>=<value>; the call named another tenant`, and one that leaves `param`
   out while the tool's input schema declares it with `...; the call did not name the
   tenant`; the tool does not run. `register_tasks` refuses with `ValueError` a task whose
   `param` has a default on a locked server, and the lock on a server that already has
   such a task, since the default would name a tenant the caller never chose. A tool
   that does not take `param`, the tenant list for one, listing tools and every other
   request are untouched. `build_server` passes the instructions one more
   sentence, "This server is locked to <param> <value>; every tool call that takes
   <param> must pass <param>=<value>.", through the constructor. The list tool of a locked server lists the
   locked tenant only. The HTTP router has no lock: a deployment that needs one declares
   only that tenant.
8. **A source's options go through hooks.** `main(server, argv=None, *, add_options=None,
   apply_options=None)` and `build_parser(prog, *, add_options=None)`: `add_options` puts
   the source's arguments on core's parser, the line is parsed once, and
   `apply_options(namespace, server)` returns the server to run, a locked one built with
   `build_server(..., tenant_lock=...)` for instance. A `XippiosError` it raises, an
   undeclared tenant or a missing variable, ends the process like an argparse error:
   the message on stderr, exit status 2, nothing served.
9. **Write servers are checked at registration and kept on loopback.**
   `register_tasks(read_only=False)` refuses with `ValueError`, before anything is
   registered, a task without a parameter `confirm` whose annotation resolves to `bool`
   and whose default is `False`, and records the server as a write server
   (`is_write_server`). `main` serves a write server over `--http` on `127.0.0.1`,
   `localhost` or `::1` only, unless `--allow-remote` is passed: the server carries no
   authentication, and beyond loopback a gateway in front of it has to.
10. **Tests go through the middleware.** `xippios.core.testing.mcp_call` and the new
    `mcp_call_text` connect `mcp.Client(server)` in-process, so a lock and any other
    middleware run as they do for a real client; `mcp_call_text` returns the tool's text,
    so a test can assert a refusal.
11. **Nothing spans tenants.** No task, tool or helper in core works across tenants, and
    the list returns names only. Isolation is by configuration: a deployment reaches
    exactly the tenants its environment declares.

## Consequences

- sdk-cashctrl, adopting core 0.2.0, deletes from `_client.py` its registry: `orgs`,
  `require_org`, `subdomain_env`, `api_key_env`, `_is_set`, the client cache and
  `reset_clients`. One `Tenants("cashctrl", list_var="CASHCTRL_ORGS",
  fields=("SUBDOMAIN", "API_KEY"), reserved=("demo",), validate={"SUBDOMAIN": ...})`
  replaces them; `client_for(org)` becomes `tenants.client_for(org, build)`, the
  subdomain pattern of `_subdomain` becomes the `validate` check, and its conftest's
  `demo_only` calls `tenants.reset()`. `_org_lock.py` goes: `--org` reaches core's
  `main` through `add_options`, and `apply_options` returns
  `build_server(..., tenant_lock=TenantLock("org", tenants.require(org)))`, so neither
  the private instructions nor the second parse remain. Its tests use `mcp_call_text`
  instead of driving `mcp.Client` by hand. Its tasks set `ResultMeta(tenant=org)`, it
  registers `cashctrl_list_organisations`, and the messages for an unknown organisation
  read "unknown tenant" now, which its tests assert.
- A changed key rebuilds a tenant's client; sdk-cashctrl rebuilt it only for a changed
  subdomain.
- sdk-template gains a `multi_tenant` question that scaffolds the `Tenants` instance, the
  list task, the `--<param>` lock through the hooks and their tests, in a template PR
  after the core release that carries this ADR.
- **Breaking**, pre-1.0 (conventions §12): a write server whose task lacks
  `confirm: bool = False` no longer builds, and a write server started with `--http` on
  a host other than loopback needs `--allow-remote`. `mcp_call` needs a server
  `mcp.Client` connects to (an `MCPServer` or a low-level `Server`), and a call that the
  server answers with an MCP error, arguments the tool's schema refuses or an unknown
  tool, fails the test with `AssertionError` instead of raising the SDK's `ToolError`.
- The `mcp` SDK's middleware API is provisional in 2.x and core declares no upper bound
  for it; the in-process client tests in `tests/mcp/test_lock.py` are the guard.
- Core adds no authentication to MCP servers. A write server beyond loopback is the
  deployment's to protect.
- Conventions 1.9: §1 names the per-tenant variables, §7 the scheme and the error split,
  §8 the lock, the list tool, the `confirm` check and the loopback rule.
