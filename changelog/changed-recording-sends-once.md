- `record` and `record_sync` send once through the client they are given, whatever its
  `RetryPolicy` says, and never answer from the cache, so a 429 or a 5xx is recorded as it
  came and spends no second request. A source with a quota or a bill no longer builds a
  client on `RetryPolicy(max_attempts=1)` to record through `record`.
  (ADR-0015, §10, https://github.com/xippios/sdk-core/issues/148)
