- `REDACTED` is exported from `xippios.core`, the path by which a source's package imports the
  mark of a redacted value, since core writes it and a source's package reads it.
  `xippios.core.testing` keeps it for a source's tests.
  (ADR-0059, https://github.com/xippios/sdk-core/issues/473)
  - Hand-apply: `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — `from xippios.core import
    REDACTED` in place of `from xippios.core.models import REDACTED` (line 74 on its `main`) —
    the root's list is the path that core pins for a package, while `xippios.core.models` holds
    it outside the pinned lists, and no test breaks, since the old path still imports.
