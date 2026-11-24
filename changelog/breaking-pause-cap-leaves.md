- `QuotaPolicy(pause_cap=)` and its attribute leave, since no source passes or reads them. A
  request into a spent quota waits it out inside the call within 30 s, the default
  `backoff_max`, and is refused without sending beyond that, as before.
  (ADR-0037, §6, https://github.com/xippios/sdk-core/issues/475)
