- `NO_TENANT_TASKS` leaves with its reads: `bind_tasks` refuses every task that takes no
  tenant but the tenant list, so a bound server serves the tenant's tasks and the tenant list,
  and the family check excepts the tenant list alone. No source declares it, and a task that
  touches no tenant waits for the first source that has one.
  (ADR-0036, §7, https://github.com/xippios/sdk-core/issues/475)
