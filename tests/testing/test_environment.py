"""keep_reserved_tenants: the demo-only strip of a multi-tenant source's ``tests/conftest.py``.

The strip of the two copies (ADR-0042, decision 1), by the registry's
scheme: a source's, which removes the list variable and every listed tenant's
field variables and keeps the rest of the shared prefix. On fictitious sources whose
variables no shell sets; every value here is a placeholder.
"""

import os

import pytest

from xippios.core import Tenants
from xippios.core.testing import keep_reserved_tenants

TENANTS = Tenants(
    "example-src",
    list_var="EXAMPLE_SRC_ORGS",
    param="org",
    fields=("SUBDOMAIN", "API_KEY"),
    reserved=("demo",),
)
SHARED = Tenants(
    "example-mail",
    var_prefix="EXAMPLE",
    list_var="EXAMPLE_ACCOUNTS",
    param="account",
    fields=("REFRESH_TOKEN",),
    reserved=("demo",),
)


@pytest.fixture(autouse=True)
def no_example_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [name for name in os.environ if name.startswith("EXAMPLE_")]:
        monkeypatch.delenv(name, raising=False)


def example_names() -> set[str]:
    return {name for name in os.environ if name.startswith("EXAMPLE_")}


def test_only_the_reserved_tenants_variables_stay(monkeypatch: pytest.MonkeyPatch) -> None:
    stripped = {
        "EXAMPLE_SRC_ORGS",
        "EXAMPLE_SRC_ACME_SUBDOMAIN",
        "EXAMPLE_SRC_ACME_API_KEY",
        "EXAMPLE_SRC_ACME_TEST_API_KEY",  # the tenant acme_test
        "EXAMPLE_SRC_DEMO_TEST_SUBDOMAIN",  # demo_test, not the reserved demo
    }
    kept = {"EXAMPLE_SRC_DEMO_SUBDOMAIN", "EXAMPLE_SRC_DEMO_API_KEY", "OTHER_ACME_API_KEY"}
    for name in stripped | kept:
        monkeypatch.setenv(name, "placeholder")
    keep_reserved_tenants(TENANTS)
    assert not stripped & set(os.environ)
    assert kept <= set(os.environ)
    assert TENANTS.names() == ("demo",)


def test_the_rest_of_the_prefix_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    """A source's ``EXAMPLE_CLIENT_ID`` and ``EXAMPLE_CLIENT_SECRET``, which it shares.

    A variable the scheme does not name, the prefix and a field with no tenant between, or
    a field the registry does not declare, is no tenant's and stays.
    """
    names = {
        "EXAMPLE_CLIENT_ID",
        "EXAMPLE_CLIENT_SECRET",
        "EXAMPLE_REFRESH_TOKEN",  # no tenant between the prefix and the field
        "EXAMPLE_WORK_API_KEY",  # not a field of this registry
        "EXAMPLE_DEMO_REFRESH_TOKEN",
    }
    for name in names | {"EXAMPLE_ACCOUNTS", "EXAMPLE_WORK_REFRESH_TOKEN"}:
        monkeypatch.setenv(name, "placeholder")
    keep_reserved_tenants(SHARED)
    assert example_names() == names
    assert SHARED.names() == ("demo",)


def test_a_registry_whose_slug_is_its_prefix_strips_the_same(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source's registry, its prefix apart, strips as the copy's did.

    The registry's name: https://github.com/xippios/sdk-core/issues/279.
    """
    copy = Tenants(
        "example",
        list_var="EXAMPLE_ACCOUNTS",
        param="account",
        fields=("REFRESH_TOKEN",),
        reserved=("demo",),
    )
    variables = ("EXAMPLE_ACCOUNTS", "EXAMPLE_WORK_REFRESH_TOKEN", "EXAMPLE_DEMO_REFRESH_TOKEN")
    left: list[set[str]] = []
    for registry in (SHARED, copy):
        for name in variables:
            monkeypatch.setenv(name, "placeholder")
        keep_reserved_tenants(registry)
        left.append(example_names())
    assert left == [{"EXAMPLE_DEMO_REFRESH_TOKEN"}] * 2


def test_without_a_reserved_tenant_no_tenant_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = Tenants("example-src", list_var="EXAMPLE_SRC_ORGS", param="org", fields=("API_KEY",))
    for name in ("EXAMPLE_SRC_ORGS", "EXAMPLE_SRC_DEMO_API_KEY", "EXAMPLE_SRC_ACME_API_KEY"):
        monkeypatch.setenv(name, "placeholder")
    keep_reserved_tenants(registry)
    assert example_names() == set()


def test_an_environment_without_the_registry_s_variables_is_left_as_it_is() -> None:
    before = set(os.environ)  # names only: a failed comparison prints no value
    keep_reserved_tenants(TENANTS)
    assert set(os.environ) == before
