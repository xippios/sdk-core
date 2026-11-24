- The family check tests the one package with a `tasks.py` under `src/xippios/`, and the ini
  option `xippios_package`, which no source set, leaves. `assert_time_between` loses `slack=`,
  which no source passed, and brackets a time with `CLOCK_SLACK` alone. The census of the
  built-answer check judges a worker of pytest-xdist as any run, where it skipped, since no
  source runs its tests under it.
  (ADR-0035, ADR-0064, §10, https://github.com/xippios/sdk-core/issues/475)
