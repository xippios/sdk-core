- `AsyncClient.download` takes `params=` and `headers=` as `get` and `get_answer` take them,
  so a download's query is no longer written into its URL by hand. `before_request` sees the
  request with both, and the response cache stays untouched.
  (ADR-0040, §6, https://github.com/xippios/sdk-core/issues/510)
  - Hand-apply: `src/xippios/cashctrl/api/_download.py` (sdk-cashctrl) — at `:144`,
    `client.download(str(httpx.URL(f"/{endpoint}", params=params)), partial)` becomes
    `client.download(f"/{endpoint}", partial, params=params)` — the client sends a
    download's query as it sends a read's, and the tests that assert the sent URLs pass
    unchanged.
    `src/xippios/eurostat/api/sdmx.py` (sdk-eurostat) — at `:210-211`, the query leaves the
    path, and `client.download(url_for(flow_ref, path), dest, params=params)` sends it —
    the same.
