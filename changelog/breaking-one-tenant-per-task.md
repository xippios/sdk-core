- A server bound to one tenant no longer serves a task unbound: `bind_tasks` refuses, with
  `ValueError` naming the task and the parameter, a task that lacks the lock's parameter,
  where it returned the task as it was, unless it is the tenant list or its module names it
  in `NO_TENANT_TASKS`, beside `BULK_TASKS`, as touching no tenant, which is served as it
  is. The family check gains `test_family_tasks_take_one_tenant`, which holds every task of
  a source with a `Tenants` registry, with no opt-in, to the tenant's parameter once,
  required with no default, a `str`, the same two excepted. Conventions §7 states the line
  for core and for a source's own tasks: one tenant per task, required, names only from the
  tenant list, nothing shared between tenants.
  (ADR-0036, §7, https://github.com/xippios/sdk-core/issues/298,
  https://github.com/xippios/sdk-core/issues/299)
  - Hand-apply: `src/xippios/<package>/tasks.py` (sdk-cashctrl, sdk-google-mail) — nothing
    today, and a task added later that touches no tenant is named in `NO_TENANT_TASKS =
    frozenset({"<task>"})` beside `BULK_TASKS`, in `tasks_write.py` for a write task — each
    of their 57 tasks takes `org` or `account` once, required, a `str`, and their tenant
    lists are `list_task`s, while an undeclared task without the tenant makes building the
    bound server raise `ValueError` and fails the family check.
