# ADR-0036: Multi-tenant sources

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0014 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/475

## Context

An upstream that serves each tenant from a host or under a key of its own, CashCtrl's
organisations and Gmail's mailboxes, needs a source that knows its tenants, a client per
tenant, a server that can serve one tenant alone and a write server that cannot be reached
unprotected. This record states ADR-0014 with its supersession in part by ADR-0024 of
2026-10-27, its amendments of 2026-10-27, 2026-10-29 (by ADR-0025 and by ADR-0026) and
2026-11-18 as they stand, and changes no decision of theirs but by decision 13; their
history stays in ADR-0014. Its
decisions 1 to 4, 6, 7 and 11 left core with the kit in 0.3.0, when ADR-0024 moved the code
to sdk-cashctrl. ADR-0025, D-d named the pieces that return in 0.4.0, which bring decisions 1
to 4, 6 and 7 back, decision 7 as the binding wrapper, and the human's answer of 2026-11-18
(https://github.com/xippios/sdk-core/issues/298) returns decision 11 with them. Decision 13,
the line of decision 11 for a source's own tasks and core's checks of it, is new in this
record, the human's answer of 2026-11-18 (https://github.com/xippios/sdk-core/issues/299).
It changes three signatures that ADR-0014's amendment of 2026-11-18 first gave, as
decisions 1, 7 and 8 state them: `Tenants` takes `param`, the parameter that names a tenant,
`TenantLock(tenants, value, noun=None)` takes the registry in place of a parameter, and
`serve_tenants` takes no `param` of its own; that amendment's points (c) and (d) give the
forms of decision 13 since.

## Decision

1. **Tenants come from the environment.** `Tenants(source, *, var_prefix=None, list_var,
   param, fields, reserved=(), validate=None, hints=None)`, exported from `xippios.core` out
   of the module `xippios.core.tenants`, holds a source's scheme and `param`, the task
   parameter that names a tenant (decision 13). `list_var` lists the tenant names,
   comma-separated, each matching `^[a-z0-9_]+$`, read on every call. Each tenant's values
   sit in `<PREFIX>_<NAME>_<FIELD>`, the name upper-cased, the prefix `var_prefix` where the
   source gives one, `GOOGLE` for sdk-google-mail, and otherwise the source upper-cased with
   `-` made `_` (`CASHCTRL_ACME_SUBDOMAIN`, `CASHCTRL_ACME_API_KEY`); the source slug names
   the source in every error either way. `fields` names the suffixes, `validate` checks a
   value where the source knows its shape, and `hints` tells the operator what a field holds
   when `validate` refuses its value. sdk-cashctrl's scheme is unchanged.
2. **A reserved test tenant is declared by its own variables.** It exists when every one of
   its field variables is set and is never listed; listing it is a `ConfigError`. A
   deployment that does not set them has no test tenant.
3. **One client per tenant.** `Tenants.client_for(name, build)` builds a tenant's client with
   the source's `build` on first use and keeps it under a digest of the tenant's current
   values, so a changed value, the key included, builds a new client and closes the one it
   replaces, on the running loop or, outside one, on core's background loop; the values
   themselves are not kept. `build` gives each tenant its own rate limiter and no cache
   shared with another tenant. The key is read on the first request (`EnvKeyAuth`), so a
   declared tenant without one fails then.
4. **Errors split by whose mistake it is.** A name that is not declared is the caller's:
   `InvalidRequestError` (ADR-0007), text over MCP and 422 over HTTP, listing the declared
   names, or the variables to set when there are none. A malformed list, or a missing or
   refused value of a declared tenant, is the operator's: `ConfigError`, naming the
   variable. No message carries a value.
5. **The tenant is in the envelope.** `ResultMeta.tenant: str | None`: the tenant the data
   came from, by name, set by every task of a multi-tenant source; never a credential, a host
   or another of the tenant's values. `None` for a single-tenant source and for the list of
   tenants.
6. **A list tool.** `list_task(tenants, *, name, doc=None, source=None)`, exported from
   `xippios.core`, is a task with no argument that returns the declared names, names only
   (ADR-0030), registered as `<source>_list_<tenants>` (`cashctrl_list_organisations`), so
   an agent can form valid calls (conventions §8). Its `source` names `meta.source` where the
   registry's slug is not the source's, for a registry that several sources share. It stays
   on the read server: a write server exposes write tools only.
7. **The lock binds a server's tools to one tenant.** `TenantLock(tenants, value,
   noun=None)`, `bind_tasks(tasks, lock)` and `tenant_instructions(text, lock, *,
   bound=None)` come from `xippios.core`, out of the module `xippios.core.tenants`. The lock
   takes the source's registry, and its `param` is the registry's (decision 13). A bound
   task keeps its `__name__` and awaits the task with `param=value`; its signature, annotations and
   docstring lose `param`, so no tool of a bound server declares the tenant's argument and
   the argument check refuses a call that names it (decision 12). The lock is no
   middleware, takes no `tenant_lock=` parameter and refuses no defaulted tenant parameter.
   The tenant list of a bound server lists the bound tenant alone, and its instructions end
   "This server is bound to <param> <value>; every tool acts on that <noun> and takes no
   <param>.", the noun the lock's or else `param`, after `bound`, the bound server's own
   text, where the source gives one, since its unbound text may say that every tool takes
   the argument. The HTTP router takes no lock: a deployment that needs one declares only
   that tenant.
8. **A source's options go through hooks.** `main(server, argv=None, *, add_options=None,
   apply_options=None)` and `build_parser(prog, *, add_options=None)`: `add_options` puts the
   source's arguments on core's parser, the line is parsed once, and
   `apply_options(namespace, server)` returns the server to run. A `XippiosError` it raises,
   an undeclared tenant or a missing variable, ends the process like an argparse error: the
   message on stderr, exit status 2, nothing served. The bound server is core's:
   `xippios.core.mcp.serve_tenants(server, build, tenants, *, noun=None, check=None)` puts
   `--<param>`, the registry's `param`, on `main`'s parser through the hooks, checks the
   named tenant with `tenants.require` and then with the source's `check`, and runs
   `build(TenantLock(tenants, name, noun=noun))`; an undeclared tenant or an error of the check
   stops the process with exit status 2 before the bound server is built. A multi-tenant
   source's servers are bound so: its entry point runs `serve_tenants`, and its
   `build(lock)` passes its tasks through `bind_tasks` and its instructions through
   `tenant_instructions`.
9. **Write servers are checked at registration and kept on loopback.**
   `register_tasks(read_only=False)` refuses with `ValueError`, before anything is
   registered, a task without a parameter `confirm` whose annotation resolves to `bool` and
   whose default is `False`, and records the server as a write server (`is_write_server`).
   `main` serves a write server over `--http` on `127.0.0.1`, `localhost` or `::1` only,
   unless `--allow-remote` is passed: the server carries no authentication, and beyond
   loopback a gateway in front of it has to. For the packages the host xippios-mcp serves,
   that gateway is the host, with its per-endpoint bearer, the default, and, for claude.ai,
   the OAuth authorization server in front of it; Johannes decided it on 2026-10-29 (D109,
   D110 (4); ADR-0026).
10. **Tests go through the middleware.** `xippios.core.testing.mcp_call` and `mcp_call_text`
    connect `mcp.Client(server)` in-process, so the argument check and any other middleware
    run as they do for a real client. `mcp_call` raises `AssertionError` on every `error:`
    text; `mcp_call_text` returns the tool's text, an error answer's flagged `isError`
    included, so a test can assert a refusal, and fails a call that the SDK answers with an
    error of another kind, an unknown tool or a task that crashed, which it tells by its text
    (ADR-0026, amendment 2026-11-18, point b); an unknown tool fails both.
11. **Nothing spans tenants.** No task, tool or helper in core works across tenants, and the
    list returns names only. Isolation is by configuration: a deployment reaches exactly the
    tenants its environment declares. It holds in core again with the kit
    (https://github.com/xippios/sdk-core/issues/298).
12. **The argument check.** `register_tasks` installs a middleware, once per server, that
    validates a call's arguments before the tool runs, with the argument model the `mcp` SDK
    builds for the tool (`func_metadata`) from the task's hints with their `Annotated`
    metadata, so a `Field` constraint, a description or a validator that a parameter
    declares reaches the tool's input schema, and the check refuses what it refuses in the
    same form. It refuses an argument that the model does not declare, whatever the value, a
    null included: `error: InvalidRequestError: <argument>: Not an argument of this tool; it
    takes <the declared arguments>`, or `it takes no arguments`. It answers a refusal as
    `error: InvalidRequestError: <argument>: <message>`, never with pydantic's URL, input
    type or input value: the undeclared arguments first, in the call's order, then what the
    schema refuses, and the answer names the first with the count of all. The check is
    appended to `server.middleware` at the first registration, and the SDK runs that list
    outermost-first, so a middleware appended later runs inside the check; a source that
    installs middleware of its own chooses its place in the list, index 0 being ahead of the
    SDK's own middleware too. It is a family invariant (ADR-0023, decision 3 (a)), for every
    source's schema-typed arguments. Johannes decided the check on 2026-10-27. The HTTP
    router keeps a parameter's `Annotated` metadata too (ADR-0007, amendment 2026-11-18,
    point a).
13. **One tenant per call, in a source's own tasks too.** A multi-tenant source's tasks keep
    the line of decision 11: each task takes exactly one tenant, required, the tenant list
    returns names only, and nothing is shared between tenants. The source declares the
    parameter that names a tenant once, `Tenants(..., param="org")`, required: the family
    check, the serve command's option and every `TenantLock`, which takes the registry, read
    it there, so none names another parameter. Core checks the rule where it can break
    unseen. `bind_tasks` refuses with `ValueError`, naming the task and the parameter
    and binding nothing, a task that lacks the lock's parameter, unless it is the tenant
    list of decision 6 or its module declares it by name as touching no tenant, in
    `NO_TENANT_TASKS`, a frozenset of task names beside `BULK_TASKS` in `tasks.py` or
    `tasks_write.py`; a task so declared is served as it is on a bound server. The family
    check holds every task of a source with a `Tenants` registry, which its `_client`,
    `tasks` or `tasks_write` module holds, to the rule, with no opt-in: the registry's
    `param` once, required with no default, of a type that names one tenant, a `str`, the
    tenant list and the declared tasks excepted. The lock still binds a defaulted tenant parameter
    (decision 7); the family check refuses one. Both read signatures, which show neither
    what a task reaches nor what it shares: a task that takes one tenant and opens another's
    client is the review's to find (https://github.com/xippios/sdk-core/issues/302). The
    rule binds a source from its adoption of core 0.4.0. Johannes decided it on 2026-11-18
    (https://github.com/xippios/sdk-core/issues/299).

## Consequences

- A changed key rebuilds a tenant's client.
- A multi-tenant source's registry names its tenant's parameter, which it cannot leave out,
  and a task that touches no tenant is named in `NO_TENANT_TASKS`, or its bound server is
  not built and its family check fails.
- The `mcp` SDK's middleware API is provisional in 2.x and core declares no upper bound for
  it; the argument check's tests through `mcp_call_text` guard it.
- Core adds no authentication to MCP servers. A write server beyond loopback is the
  deployment's to protect.

Conventions §1, §4, §7 and §8, the README and the docstrings of `xippios.core.tenants`,
`xippios.core.mcp`, `main`, `serve_tenants`, `register_tasks` and `InvalidRequestError`
state its decisions from 1.28 on; decisions 11 and 13 conventions §7, item 17 of the review
checklist, the README and the docstrings of `xippios.core.tenants`, `bind_tasks` and the
family check, and the parameter that decision 13 declares on the registry conventions §8 and
the docstrings of `Tenants`, `TenantLock` and `serve_tenants` too.

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/475: in decision 1 `validate`
and `hints` return to their one consumer, sdk-cashctrl, which checks the value that `field`
returns itself and refuses it with a `ConfigError` that names the variable and never the value,
by ADR-0059, decision 2, and part 2 of the answer on
https://github.com/xippios/sdk-core/issues/473, while `var_prefix` stays with its one consumer,
sdk-google-mail, whose variables carry the prefix `GOOGLE` that its slug does not give; in
decision 3 the digest of a tenant's variables leaves, so that `client_for` keeps one client per
tenant until `Tenants.reset()`, the one way to a new client, and closes none, since no code of
core, of a source or of the host changes a tenant's variables after start; in decision 6
`list_task` loses `source`, which no source passes, by part 7 of the answer on
https://github.com/xippios/sdk-core/issues/475; and in decision 13 `NO_TENANT_TASKS` leaves with its reads in `bind_tasks`, in the family check and in core's
reader of a tasks module, since no source declares it, so that a bound server serves the
tenant's tasks and the tenant list and the family check excepts the tenant list alone until a
source has a task that touches no tenant, while decisions 2, 4, 5 and 7 to 12, the rest of
decisions 1, 3, 6 and 13 and the consequences, but the first and the second's clause on
`NO_TENANT_TASKS`, stand as written.
