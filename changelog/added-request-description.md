- `xippios.core.errors.request_description(response)`, exported from `xippios.core`,
  gives the method and path that core's error messages name, `GET /v1/series`, so a
  source's `classify` words the errors it maps with it instead of a copy of its own.
  (ADR-0005, §5, https://github.com/xippios/sdk-core/issues/62)
  - Hand-apply: `src/xippios/eurostat/_client.py` (sdk-eurostat) — `_where` (lines 102 to
    104) and its five uses → `request_description` — core's description.
    `src/xippios/x/_client.py` (sdk-x) — `_where` (lines 96 to 98) and its use at line
    146 → `request_description` — core's description.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — the inline `where` of line
    247 → `request_description(response)` — core's description.
    `src/xippios/google/mail/_auth.py` (sdk-google-mail) — the inline `where` of line 297
    → `request_description(response)` — core's description.
    `src/xippios/faostat/_client.py` (sdk-faostat) — the inline
    `{request.method} {request.url.path}` of lines 166, 376 and 383 →
    `request_description(response)` — core's description.
    `src/xippios/usda/esmis/_client.py` (sdk-usda-esmis) — the inline
    `{request.method} {path}` of line 124 → `request_description(response)`, line 115
    keeping its raw path, which shows the encoded slash — core's description.
