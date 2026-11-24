- `AsyncClient.download` takes `params=` and `headers=` as `get` and `get_answer` take them,
  so a download's query is no longer written into its URL by hand. `before_request` sees the
  request with both, and the response cache stays untouched.
  (ADR-0040, §6, https://github.com/xippios/sdk-core/issues/510)
