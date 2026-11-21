- `record_task` and `record_task_sync` record every exchange that a task makes, in order,
  through every client the task reaches, each request sent once and none answered from the
  cache, and write them under the task's name as `<case>.json`, `<case>_2.json` and so on. Each
  exchange passes the refusal of a 1xx or a 3xx, the scrub, the rewrite step and the check of
  `record`, and all are written or none, nothing for a task that raises or downloads. sdk-cashctrl
  takes nothing now, since it records exchange by exchange into 44 fixture directories named
  after wrappers, and nor does sdk-x, whose seven tasks make one call each.
  (ADR-0057, §10, https://github.com/xippios/sdk-core/issues/174, https://github.com/xippios/sdk-core/issues/376)
  - Hand-apply: `scripts/record_fixture.py` (sdk-google-mail) — deletes `recording_client`,
    `task_exchanges_async`, `task_exchanges`, the seed of `TENANTS` with its guard and the loop
    of its own `record_task` function that numbers, builds, checks and writes the fixtures, and
    records with `record_task_sync(RECORDED_TASKS[name], DEMO, fixtures=FIXTURES,
    case=args.case, scrub=scrub, rewrite=step, **arguments)`, its step running `rewrite` and
    `check` as for a single exchange (ADR-0048). It keeps the command line, `TASKS`, `WRITE_TASKS`, `task_arguments`,
    `prepare_write` with the write safety rule, `MessageScrub`, `rewrite`, `check` and the lines
    it prints, read from the fixtures returned — core collects the task's exchanges through the
    client the task fetches itself, numbers them and writes all or none.
