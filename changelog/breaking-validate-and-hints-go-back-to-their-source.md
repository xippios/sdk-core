- `Tenants` loses `validate=` and `hints=` to their one consumer, sdk-cashctrl. `field` returns
  a value stripped, and a source that knows its shape checks it and raises a `ConfigError` that
  names the variable and no value. `var_prefix=` stays, with its one consumer, sdk-google-mail.
  (ADR-0036, ADR-0059, §7, https://github.com/xippios/sdk-core/issues/473)
  - Hand-apply: `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — the `Tenants(...)` call
    loses `validate=` and `hints=` (lines 120 and 121 on its `main`), and one function of about
    ten lines reads `TENANTS.field(org, "SUBDOMAIN")`, passes it to `check_subdomain` and on a
    refusal raises, outside the `except`, the `ConfigError` that core raised, which names the
    variable, the tenant and the hint and quotes no value, for `_build` (line 375) and
    `check_org` (line 138) to call in place of `TENANTS.field` — core checks no value, so until
    the call loses the two keywords every test fails at the import of `_client.py` with a
    `TypeError`, and then `test_a_missing_or_malformed_subdomain_is_a_config_error` and
    `test_a_malformed_subdomain_says_what_the_variable_should_hold` of `tests/test_registry.py`
    (lines 211 and 223) hold the package's check as they held core's.
    `tests/test_registry.py` (sdk-cashctrl) — the docstring of
    `test_a_malformed_subdomain_says_what_the_variable_should_hold` (line 226) names the
    package's own check in place of `Tenants(hints=...)` — the parameter has left core, and no
    test breaks.
