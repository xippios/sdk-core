- The family check tests the one package with a `tasks.py` under `src/xippios/`, and the ini
  option `xippios_package`, which no source set, leaves. `assert_time_between` loses `slack=`,
  which no source passed, and brackets a time with `CLOCK_SLACK` alone.
  (ADR-0035, §10, https://github.com/xippios/sdk-core/issues/475)
