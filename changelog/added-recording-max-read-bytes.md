- `record` and `record_sync` read at most `max_read_bytes` of a response body, 32 MiB by
  default (`xippios.core.testing.record.MAX_READ_BYTES`): past it the reading stops and the
  recording raises, naming the method, the path and the bound, and writes nothing.
  `None` reads the body whole. (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/62)
