- The client's `auth` goes to the base URL's origin only, so a file link on another host
  gets no key unless the call passes an `httpx.Auth` of its own, and a signed link in
  `meta.request` reads its signature (`sig`, `X-Amz-Signature`) `REDACTED`. A request sent
  with `auth=None` or to another origin spends no quota: the `QuotaPolicy` neither holds it
  back nor reads its answer, the limiter still paces it, and the api.data.gov gateway's
  `classify` reads the base URL's answers alone. Every request carries the extensions
  `xippios_auth` and `xippios_origin`, which say where its credentials go.
  (ADR-0015, ADR-0019, ADR-0009, §4, §6, §7, https://github.com/xippios/sdk-core/issues/163)
  - Hand-apply: `src/xippios/comtrade/_client.py` (sdk-comtrade) — the comment above `auth`
    (lines 206 to 213) says that the keyless reference files and public operations take
    the pace alone, no longer `policy` — a spent key quota holds no keyless call back.
    `src/xippios/comtrade/api/get_comtrade_releases.py` (sdk-comtrade) — the module
    docstring (lines 12 to 14) drops "and its `policy`: once upstream has said the key's
    quota is spent, this call is held back too" — the same.
    `src/xippios/comtrade/api/get_world_share.py` (sdk-comtrade) — the module docstring
    (lines 14 to 16), the same sentence — the same.
    `CLAUDE.md` (sdk-comtrade) — the reference files' "and a spent quota holds it back
    too" (line 70) and the public operations' "and `policy`, so a spent key quota holds
    them back too" (lines 77 and 78) go — the same.
