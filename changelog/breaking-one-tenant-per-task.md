- A multi-tenant source declares the parameter that names a tenant once, on its registry,
  `Tenants(..., param="org")`, required, and a server bound to one tenant no longer serves a
  task unbound: `bind_tasks` refuses, with `ValueError` naming the task and the parameter, a
  task that lacks it, where it returned the task as it was, unless it is the tenant list or
  its module names it in `NO_TENANT_TASKS`, beside `BULK_TASKS`, as touching no tenant. The
  family check gains `test_family_tasks_take_one_tenant`, which holds every task of a source
  with a `Tenants` registry, with no opt-in, to the registry's `param` once, required with
  no default, a `str`, the same two excepted, and `serve_tenants` takes its option from the
  registry and `TenantLock(TENANTS, "acme")` takes the registry, where both took a `param`
  of their own. Conventions §7 states the line for core and for a source's own tasks: one
  tenant per task, required, names only from the tenant list, nothing shared between
  tenants.
  (ADR-0036, §7, §8, https://github.com/xippios/sdk-core/issues/298,
  https://github.com/xippios/sdk-core/issues/299)
  - Hand-apply: `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `param="org",` after
    `list_var="CASHCTRL_ORGS",` in the declaration `TENANTS = Tenants(...)` (line 97) —
    core's `Tenants` requires the parameter that names a tenant, and the family check holds
    each of the 46 tasks to it, which takes `org` once, required, a `str`.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — `param="account",` after
    `list_var="GOOGLE_ACCOUNTS",` in the declaration `TENANTS = Tenants(...)` (line 104) —
    as above, for the 11 tasks, which take `account`.
