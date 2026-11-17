- `quiet_request_logging` sets the `httpx2` and `httpcore2` loggers to `WARNING` with
  `httpx` and `httpcore`, so the `mcp` SDK's own HTTP client logs no request URL either.
  The testing plugin gives all four levels back after every test.
  (ADR-0005, ADR-0013, §10, https://github.com/xippios/sdk-core/issues/176)
