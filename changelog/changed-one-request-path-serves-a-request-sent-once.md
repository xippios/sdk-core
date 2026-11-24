- `AsyncClient` sends `request`, the recorder's `send_once`, which the snapshot frame's fetch
  goes through, and `download` along one private request path, so `before_request`, the
  limiter's wait, `observe` and the retry decision are written once in the client. Nothing
  changes for a caller: the hooks run in the same order, a refusal by `before_request` still
  sends nothing, and no name or keyword enters or leaves.
  (ADR-0037, ADR-0066, https://github.com/xippios/sdk-core/issues/480)
