"""The environment of a multi-tenant source's tests: its reserved tenants and no other.

A source whose ``Tenants`` declares a reserved tenant for fixtures and live tests, ``demo``,
calls ``keep_reserved_tenants`` once in its ``tests/conftest.py``, when pytest imports
it, so that no fixture of any scope and no test can see another tenant's name or
credential, a productive one the shell holds among them::

    from xippios.core.testing import keep_reserved_tenants

    from xippios.example._client import TENANTS

    pytest_plugins = ["xippios.core.testing.plugin"]

    keep_reserved_tenants(TENANTS)
"""

import os
import re

from xippios.core.tenants import Tenants

__all__ = ["keep_reserved_tenants"]


def keep_reserved_tenants(tenants: Tenants) -> None:
    """Remove every tenant from the process's environment but the reserved ones.

    Removes ``tenants.list_var`` and every variable the registry's scheme names for a
    tenant that is not reserved, ``<PREFIX>_<NAME>_<FIELD>`` for each of its ``fields``,
    and keeps the reserved tenants' own variables, which the live tests read. A variable
    the scheme names for no tenant stays: the rest of a shared prefix,
    ``EXAMPLE_CLOUD_CLIENT_ID`` and ``EXAMPLE_CLOUD_CLIENT_SECRET`` say, or a key variable
    the source reads for no tenant. Names only: no value is read, kept or shown.

    Call it at the module level of ``tests/conftest.py``, before any fixture runs; a
    source's own fixture removes ``list_var`` again for every test, with
    ``monkeypatch.delenv``, and resets its clients around each.

    Args:
        tenants: The source's registry, e.g. ``TENANTS``.
    """
    fields = "|".join(re.escape(field) for field in tenants.fields)
    scheme = re.compile(rf"{re.escape(tenants.var_prefix)}_[A-Z0-9_]+_(?:{fields})")
    reserved = {tenants.var(name, field) for name in tenants.reserved for field in tenants.fields}
    for name in list(os.environ):
        if name == tenants.list_var or (scheme.fullmatch(name) and name not in reserved):
            del os.environ[name]
