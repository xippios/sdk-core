- `QuotaPolicy` reads no quota header unless the source names it, and its `window` is given:
  `limit_header` and `remaining_header` default to `None`, and `window` has no default. The
  three defaults were one gateway's values, and every source that builds a policy passes
  its own already.
  (ADR-0037, §6, https://github.com/xippios/sdk-core/issues/485)
