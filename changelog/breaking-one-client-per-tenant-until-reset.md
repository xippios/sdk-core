- `Tenants.client_for` keeps one client per tenant until `Tenants.reset()`, the one way to a new
  client. It replaces a digest of the tenant's variables that built a new client when one
  changed and closed the one it replaced, since no code of the family changes them after start.
  (ADR-0036, https://github.com/xippios/sdk-core/issues/475)
  - Hand-apply: `tests/test_registry.py` (sdk-cashctrl) —
    `test_a_changed_subdomain_builds_a_new_client` and `test_a_changed_key_builds_a_new_client`
    (lines 173 to 185 on its `main`) are deleted — both fail once a changed variable keeps the
    client, which `test_reset_drops_every_cached_client` (line 188) still renews.
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — the docstrings of `_build` (lines 371
    and 372) and `client_for` (lines 393 to 396) say that the registry keeps one client per
    organisation until `TENANTS.reset()` — core keeps no digest, and no test breaks.
    `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — the docstring of `_REPORT_TYPES` (lines
    1310 and 1311) loses "and a changed subdomain or key builds a new one" — no client is
    rebuilt but by `TENANTS.reset()`, and no test breaks.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — the module's docstring (lines 28
    to 30) and the docstring of `client_for` (lines 393 to 396) say that the registry keeps one
    client per account until `TENANTS.reset()`, in place of a client kept under a digest of the
    refresh token — core keeps no digest, and no test breaks.
