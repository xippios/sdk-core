- `Tenants` and `list_task` are back in core, exported from `xippios.core` out of the module
  `xippios.core.tenants`: a multi-tenant source's tenants declared in the environment, one
  client each, which closes the client that a changed variable replaces, and the tool that
  names them. `Tenants(source, var_prefix=...)` takes the variables' prefix apart from the
  source slug, so its errors name the source, and `list_task(..., source=...)` names the
  `meta.source` of a registry that several sources share, the registry's slug by default.
  (ADR-0014, ADR-0024, ADR-0025, https://github.com/xippios/sdk-core/issues/166)
  - Hand-apply: `src/xippios/cashctrl/_tenants.py` (sdk-cashctrl) — deleted — core's module
    is this copy, the close of a replaced client included, and its default prefix is the
    slug's, `CASHCTRL`.
    `src/xippios/cashctrl/_client.py` (sdk-cashctrl) — `from xippios.cashctrl._tenants
    import Tenants` (line 45) → `from xippios.core import Tenants`, and the docstring's
    sentence on `_tenants.py` (lines 9 to 11) names core's `Tenants`; the declaration
    (line 97) stands — core's registry reads the same variables.
    `src/xippios/cashctrl/tasks.py` (sdk-cashctrl) — `from xippios.cashctrl._tenants import
    list_task` (line 79) → `from xippios.core import list_task`, and the docstring's
    `_tenants.list_task` (line 9) → core's `list_task`; the call (line 2273) stands — as
    above.
    `src/xippios/cashctrl/_org_lock.py` (sdk-cashctrl) — the import of `_LISTS_TENANTS`
    from `_tenants` (line 36) → `_LISTS_TENANTS = "__xippios_lists_tenants__"` in the
    module — core's `list_task` sets that mark, so the bound server still lists the bound
    organisation alone until core's lock wrapper replaces the file.
    `tests/test_tenants.py` (sdk-cashctrl) — deleted, with its import of the copy (line 30)
    — core's `tests/test_tenants.py` holds its tests, the close of row 24 b among them.
    `tests/test_registry.py` (sdk-cashctrl) — the docstring's lines 3 to 6, which name
    `_tenants.py` and `tests/test_tenants.py` → core's `Tenants`, tested in core — as above.
    `tests/test_tasks.py` (sdk-cashctrl) — the docstring of `TENANT_LIST` (line 51) → core's
    `list_task` — as above.
    `CLAUDE.md` (sdk-cashctrl) — Organisations, `_tenants.py` and `_tenants.list_task` (lines
    28, 31 to 34 and 52) → core's `Tenants` and `list_task`, and the Layout's `_tenants.py`
    and `test_tenants.py` lines (135, 173) dropped — the registry is core's again.
    `src/xippios/google/mail/_tenants.py` (sdk-google-mail) — deleted — core's module is
    this copy, `list_task`'s `source=` included, where the two copies differ.
    `src/xippios/google/mail/_client.py` (sdk-google-mail) — `from
    xippios.google.mail._tenants import Tenants` (line 55) → `from xippios.core import
    Tenants`; the declaration's first argument, `"google"` (line 105) → `SOURCE,
    var_prefix="GOOGLE"`; the docstring's lines 10 to 11 and 22 to 23 → core's `Tenants`,
    whose errors name `google-mail` — the variables keep the shared prefix, and an unknown
    account's `InvalidRequestError` and the registry's `ConfigError` name the source,
    `google` before, in an HTTP problem's `source` too (ADR-0025, amendment 2026-11-18,
    (b)).
    `src/xippios/google/mail/tasks.py` (sdk-google-mail) — `from
    xippios.google.mail._tenants import list_task` (line 34) → `from xippios.core import
    list_task`, `source=SOURCE` dropped from the call (line 112), and the docstring's
    `_tenants.list_task` (line 8) → core's `list_task` — the registry names the source now.
    `src/xippios/google/mail/_account_lock.py` (sdk-google-mail) — the import of
    `_LISTS_TENANTS` from `_tenants` (line 41) → `_LISTS_TENANTS =
    "__xippios_lists_tenants__"` in the module — as in sdk-cashctrl's `_org_lock.py`.
    `src/xippios/google/mail/_cli.py` (sdk-google-mail) — the import of `_is_set` from
    `_tenants` (line 42) → `os.environ.get(variable, "").strip()` in its one use (line 97)
    — core keeps `_is_set` private, until core's serve command replaces the file.
    `tests/test_tasks.py` (sdk-google-mail) — the docstring of `TENANT_LIST` (line 49) →
    core's `list_task`, and `test_list_accounts_lists_the_declared_names_only` (line 95)
    asserts `TENANTS.source == SOURCE` and `TENANTS.var("work", "REFRESH_TOKEN") ==
    "GOOGLE_WORK_REFRESH_TOKEN"` — the registry names the source, its variables the prefix.
    `CLAUDE.md` (sdk-google-mail) — the Layout's `_tenants.py` line (34) dropped — the
    registry is core's.
