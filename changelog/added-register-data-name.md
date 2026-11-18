- `register_data_name(name)` of `xippios.core.redaction` declares a parameter whose name
  holds the whole word `token` data, a paging cursor such as X's `next_token`, so that
  `meta.request`, a recorded fixture and replay keep its value. Every other name with a
  whole-word `token` stays a credential, and `token`, `access_token`, `refresh_token`,
  `id_token` and a name with another credential word are refused with `ValueError`.
  (ADR-0019, §4, §10, https://github.com/xippios/sdk-core/issues/184)
  - Hand-apply: `src/xippios/x/_client.py` (sdk-x) — `register_data_name("next_token")`
    and `register_data_name("pagination_token")` at import — X's cursors are data.
    `src/xippios/x/tasks.py` (sdk-x) — the module docstring (lines 28 and 29) and the
    `Args:` of the five paged tasks (lines 273, 327, 386, 432 and 475) say that
    `meta.request` keeps the token as sent, no longer `REDACTED` — the same.
    `tests/test_tasks.py` (sdk-x) — the token as sent, for `REDACTED`, in the docstring
    of line 203 and the asserts of lines 218, 223, 266 and 323, and the comparisons of
    lines 265 and 322 with the `next_token=REDACTED` that the page-2 fixtures recorded
    leave `next_token` out until a PR records them again — the same.
    `tests/test_api.py` (sdk-x) — the token as sent, for `REDACTED`, at lines 283, 357, 384
    and 528, and the comparisons of lines 282 and 356 with the page-2 fixtures leave
    `next_token` out — the same.
    `tests/test_probe_accounts.py` (sdk-x) — the cursors as sent, for `REDACTED`, at line
    232 — the same.
    `CLAUDE.md` (sdk-x) — the fixtures' paragraph (lines 335 to 340) and the task layer's
    `meta` (line 383) say that the cursors are data, and that the two page-2 fixtures
    keep `next_token=REDACTED` until recorded again — the same.
