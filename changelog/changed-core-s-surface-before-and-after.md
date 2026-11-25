- Core's surface, counted by `scripts/count_surface.py` in two parts while the package stays one,
  is 112 unique names in 16,480 lines, where v0.4.1's was 126 in 17,045: the run-time part holds
  72 names in 8,740 lines, where it held 81 in 9,068, and the workbench, `xippios.core.testing`
  and `xippios.core.refresh` with their modules, 41 names in 7,740 lines, where it held 46 in
  7,977, with `REDACTED` in both parts, where `load_json` was. No piece left by the count alone,
  and each one with fewer than two consumers among the proving packages stands in the report of
  the count with its consumers. The additions that no proving package uses yet are built here and
  first used by their sources at their adoptions: the option hooks of a tool set without
  `server`, the loopback declaration of a read tool set, the cache's lifetime by path prefix, the
  walk's stop rule and key, the key class for a query key and for a bearer, `after` of `Lists`,
  and the snapshot frame's `pause`.
  (ADR-0059, ADR-0068, https://github.com/xippios/sdk-core/issues/485,
  https://github.com/xippios/sdk-core/issues/582,
  https://github.com/xippios/sdk-core/blob/main/docs/reports/2026-11-25-the-surface-and-its-consumers.md)
