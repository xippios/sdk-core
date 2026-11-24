- A name that a query `KeyAuth` sends its key under is a credential of its source alone, and
  a name that a source declares data is data of that source alone, so one source's key name
  no longer turns another source's data into `REDACTED` in a host that loads both.
  `KeyAuth(location="query")` takes `source=`, `register_data_name` and
  `register_credential_name` take `source=` by keyword, `ResultMeta` reads its own source's
  names, and a testing helper that is given no source reads those of every source.
  (ADR-0040, §4, https://github.com/xippios/sdk-core/issues/485)
  - Hand-apply: `src/xippios/x/_client.py` (sdk-x) — at `:59-60`,
    `register_data_name("next_token")` and `register_data_name("pagination_token")` take
    `source=SOURCE` — the registry is kept for each source, and until it stands every test
    fails at the import of `_client.py`.
