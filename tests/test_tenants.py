"""Tenants and list_task: declaration in the environment, lookup, one client per tenant.

The tests of the two copies that return to core (ADR-0042, decision 1),
a source's ``tests/test_tenants.py`` and core's own tests at ``cb8ecdf``, and the
variable prefix apart from the source slug (ADR-0036, decision 1). A field's check, a
client rebuilt on a changed variable and ``list_task(source=)`` left core in 0.5.0
(ADR-0036, amendment 2026-11-24). All on invented sources whose variables no shell sets.
"""

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from xippios.core import (
    AsyncClient,
    ClientConfig,
    ConfigError,
    InvalidRequestError,
    KeyAuth,
    RateLimit,
    Result,
    Tenants,
    list_task,
)
from xippios.core.mcp import ToolSet, build_server
from xippios.core.testing import mcp_call

SOURCE = "example-src"
PREFIX = "EXAMPLE_SRC_"
LIST_VAR = "EXAMPLE_SRC_TENANTS"
FIELDS = ("SUBDOMAIN", "API_KEY")

# A source whose variables carry a prefix that is not its slug, as the sources of one
# publisher share one prefix for their <PREFIX>_<NAME>_REFRESH_TOKEN.
MAIL_SOURCE = "example-mail"
MAIL_PREFIX = "EXAMPLE"
MAIL_LIST_VAR = "EXAMPLE_ACCOUNTS"

# Values that must never appear in a message.
HIDDEN_SUBDOMAIN = "xa-hidden-subdomain"
HIDDEN_KEY = "xa-hidden-key-value"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def no_example_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts without a variable of the fictitious sources, by name."""
    for name in [name for name in os.environ if name.startswith(f"{MAIL_PREFIX}_")]:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def placeholder_api_key() -> None:
    """Pins nothing: one test here proves a missing key fails on the first request.

    Every key variable this module reads belongs to a fictitious source and is set by the
    test itself, never taken from the shell.
    """
    return None


def make(**overrides: object) -> Tenants:
    arguments: dict[str, object] = {
        "list_var": LIST_VAR,
        "param": "org",
        "fields": FIELDS,
        "reserved": ("demo",),
    }
    arguments.update(overrides)
    return Tenants(SOURCE, **arguments)  # type: ignore[arg-type]


def make_mail() -> Tenants:
    return Tenants(
        MAIL_SOURCE,
        var_prefix=MAIL_PREFIX,
        list_var=MAIL_LIST_VAR,
        param="account",
        fields=("REFRESH_TOKEN",),
        reserved=("demo",),
    )


def declare(monkeypatch: pytest.MonkeyPatch, name: str, *, key: bool = True) -> None:
    monkeypatch.setenv(f"{PREFIX}{name.upper()}_SUBDOMAIN", f"{name}-{HIDDEN_SUBDOMAIN}")
    if key:
        monkeypatch.setenv(f"{PREFIX}{name.upper()}_API_KEY", f"{name}-{HIDDEN_KEY}")


def declare_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_SRC_DEMO_SUBDOMAIN", "demo")
    monkeypatch.setenv("EXAMPLE_SRC_DEMO_API_KEY", "demo-key")  # pragma: allowlist secret


def assert_no_value(message: str) -> None:
    assert HIDDEN_SUBDOMAIN not in message
    assert HIDDEN_KEY not in message


# -- construction and variable names ----------------------------------------------------


def test_variable_names_follow_the_scheme() -> None:
    tenants = make()
    assert tenants.var("acme_test", "SUBDOMAIN") == "EXAMPLE_SRC_ACME_TEST_SUBDOMAIN"
    assert tenants.var("demo", "API_KEY") == "EXAMPLE_SRC_DEMO_API_KEY"  # pragma: allowlist secret
    assert Tenants("example", list_var="EXAMPLE_ORGS", param="org", fields=["SUBDOMAIN"]).var(
        "acme", "SUBDOMAIN"
    ) == ("EXAMPLE_ACME_SUBDOMAIN")
    with pytest.raises(ValueError, match="unknown field 'subdomain'; fields: SUBDOMAIN, API_KEY"):
        tenants.var("acme", "subdomain")


def test_attributes_and_repr_name_the_scheme_only(monkeypatch: pytest.MonkeyPatch) -> None:
    declare(monkeypatch, "xa")
    tenants = make()
    assert tenants.source == SOURCE
    assert tenants.var_prefix == "EXAMPLE_SRC"  # the slug upper-cased, "-" made "_"
    assert tenants.list_var == LIST_VAR
    assert tenants.param == "org"
    assert tenants.fields == FIELDS
    assert tenants.reserved == ("demo",)
    assert tenants.noun is None, "the parameter stands for the noun"
    assert repr(tenants) == (
        "Tenants('example-src', var_prefix='EXAMPLE_SRC', list_var='EXAMPLE_SRC_TENANTS', "
        "param='org', fields=('SUBDOMAIN', 'API_KEY'), reserved=('demo',), noun=None)"
    )


def test_the_registry_holds_the_noun_of_one_tenant() -> None:
    """The word the serve command's help and a bound server's sentence use for one tenant.

    The registry's, where the serve command took it before 0.5.0
    (https://github.com/xippios/sdk-core/issues/476, part 4).
    """
    tenants = make(noun="organisation")
    assert tenants.noun == "organisation"
    assert repr(tenants).endswith("reserved=('demo',), noun='organisation')")


@pytest.mark.parametrize(
    ("overrides", "error", "match"),
    [
        ({"list_var": ""}, ValueError, "list_var must not be empty"),
        ({"param": ""}, ValueError, "param '' is not a parameter name"),
        ({"param": "an org"}, ValueError, "param 'an org' is not a parameter name"),
        ({"param": "org-name"}, ValueError, "param 'org-name' is not a parameter name"),
        ({"var_prefix": ""}, ValueError, "var_prefix '' is not upper-case"),
        ({"var_prefix": "example"}, ValueError, "var_prefix 'example' is not upper-case"),
        ({"var_prefix": "EXAMPLE-SRC"}, ValueError, "var_prefix 'EXAMPLE-SRC' is not upper"),
        ({"fields": ()}, ValueError, "at least one"),
        ({"fields": ("subdomain",)}, ValueError, "field 'subdomain' is not upper-case"),
        ({"fields": ("A", "B", "A")}, ValueError, "field given twice: A"),
        ({"fields": "SUBDOMAIN"}, TypeError, "fields is a sequence"),
        ({"reserved": "demo"}, TypeError, "reserved is a sequence"),
        ({"reserved": ("Demo",)}, ValueError, "reserved name 'Demo' is not lower-case"),
        ({"reserved": ("demo", "demo")}, ValueError, "reserved name given twice: demo"),
        ({"noun": ""}, ValueError, "noun must be the word for one tenant, or None"),
        ({"noun": " "}, ValueError, "noun must be the word for one tenant, or None"),
    ],
)
def test_construction_refuses_a_malformed_scheme(
    overrides: dict[str, object], error: type[Exception], match: str
) -> None:
    with pytest.raises(error, match=match):
        make(**overrides)


@pytest.mark.parametrize("keyword", ["validate", "hints"])
def test_the_registry_takes_no_check_of_a_value(keyword: str) -> None:
    """A field's check is its one source's, on the value ``field`` returns.

    ``validate=`` and ``hints=`` went back to it in 0.5.0 (ADR-0059, decision 2).
    """
    with pytest.raises(TypeError, match=keyword):
        Tenants(
            "example",
            list_var="EXAMPLE_TENANTS",
            param="org",
            fields=("SUBDOMAIN",),
            **{keyword: {}},  # type: ignore[arg-type]
        )


def test_construction_refuses_an_empty_source() -> None:
    with pytest.raises(ValueError, match="source must not be empty"):
        Tenants("", list_var=LIST_VAR, param="org", fields=FIELDS)


def test_construction_needs_the_tenant_s_parameter() -> None:
    """The one declaration of the parameter that names a tenant (ADR-0036, decision 13).

    The family check, the serve command's option and a lock read it from the registry, so a
    source cannot declare its tenants without it.
    """
    with pytest.raises(TypeError, match="param"):
        Tenants(SOURCE, list_var=LIST_VAR, fields=FIELDS)  # type: ignore[call-arg]


# -- the variable prefix apart from the source slug ---------------------------------------


def test_the_variable_prefix_names_the_variables_and_the_slug_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shared prefix: EXAMPLE_<NAME>_REFRESH_TOKEN for the source example-mail."""
    tenants = make_mail()
    assert tenants.source == MAIL_SOURCE
    assert tenants.var_prefix == MAIL_PREFIX
    assert tenants.var("work", "REFRESH_TOKEN") == "EXAMPLE_WORK_REFRESH_TOKEN"
    assert repr(tenants) == (
        "Tenants('example-mail', var_prefix='EXAMPLE', list_var='EXAMPLE_ACCOUNTS', "
        "param='account', fields=('REFRESH_TOKEN',), reserved=('demo',), noun=None)"
    )
    monkeypatch.setenv(MAIL_LIST_VAR, "work")
    monkeypatch.setenv("EXAMPLE_DEMO_REFRESH_TOKEN", "demo-token")
    assert tenants.names() == ("work", "demo")


def test_errors_name_the_source_slug_and_the_prefixed_variables() -> None:
    tenants = make_mail()
    with pytest.raises(InvalidRequestError) as info:
        tenants.require("work")
    assert str(info.value) == (
        "unknown tenant 'work'; no tenant is declared; set EXAMPLE_ACCOUNTS and, per name, "
        "EXAMPLE_<NAME>_REFRESH_TOKEN; 'demo' is declared by EXAMPLE_DEMO_REFRESH_TOKEN alone. "
        "Nothing was sent."
    )
    assert info.value.source == MAIL_SOURCE


def test_a_missing_field_under_the_prefix_names_its_variable_and_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MAIL_LIST_VAR, "work")
    with pytest.raises(ConfigError) as info:
        make_mail().field("work", "REFRESH_TOKEN")
    assert str(info.value) == (
        "EXAMPLE_WORK_REFRESH_TOKEN is not set; export the REFRESH_TOKEN of tenant 'work'"
    )
    assert info.value.source == MAIL_SOURCE


# -- names --------------------------------------------------------------------------------


def test_nothing_declared_means_no_tenant() -> None:
    assert make().names() == ()


def test_listed_tenants_in_declared_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, " xb, xa ,,")
    assert make().names() == ("xb", "xa")


def test_a_reserved_tenant_is_appended_when_all_its_variables_are_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xb")
    declare_demo(monkeypatch)
    assert make().names() == ("xa", "xb", "demo")


def test_reserved_tenants_follow_in_their_given_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare_demo(monkeypatch)
    monkeypatch.setenv("EXAMPLE_SRC_SANDBOX_SUBDOMAIN", "sandbox")
    monkeypatch.setenv("EXAMPLE_SRC_SANDBOX_API_KEY", "sandbox-key")  # pragma: allowlist secret
    assert make(reserved=("sandbox", "demo")).names() == ("xa", "sandbox", "demo")


@pytest.mark.parametrize("missing", ["SUBDOMAIN", "API_KEY"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_reserved_tenant_needs_every_variable(
    monkeypatch: pytest.MonkeyPatch, missing: str, value: str | None
) -> None:
    declare_demo(monkeypatch)
    if value is None:
        monkeypatch.delenv(f"EXAMPLE_SRC_DEMO_{missing}")
    else:
        monkeypatch.setenv(f"EXAMPLE_SRC_DEMO_{missing}", value)
    assert make().names() == ()


def test_the_environment_is_read_on_every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    tenants = make()
    assert tenants.names() == ()
    declare_demo(monkeypatch)
    assert tenants.names() == ("demo",)
    monkeypatch.setenv(LIST_VAR, "xa")
    assert tenants.names() == ("xa", "demo")


def test_a_reserved_tenant_cannot_be_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,demo")
    with pytest.raises(ConfigError, match="reserved") as info:
        make().names()
    assert "EXAMPLE_SRC_DEMO_SUBDOMAIN and EXAMPLE_SRC_DEMO_API_KEY alone" in str(info.value)
    assert info.value.source == SOURCE


@pytest.mark.parametrize("name", ["Xa", "a-b", "a b", "ä", HIDDEN_SUBDOMAIN, HIDDEN_KEY])
def test_malformed_names_are_refused_by_position_never_quoted(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(LIST_VAR, f"xa,,{name}")
    with pytest.raises(ConfigError) as info:
        make().names()
    message = str(info.value)
    assert message == (
        "entry 3 of EXAMPLE_SRC_TENANTS is not a tenant name; names use only lower-case "
        "letters, digits and underscores"
    )
    assert name not in message


def test_duplicate_names_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xb,xa")
    with pytest.raises(ConfigError, match="lists 'xa' twice"):
        make().names()


# -- require ------------------------------------------------------------------------------


def test_require_returns_a_declared_name_and_lists_them_otherwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xb")
    declare(monkeypatch, "xa")
    declare(monkeypatch, "xb")
    declare_demo(monkeypatch)
    tenants = make()
    assert tenants.require("xa") == "xa"
    assert tenants.require("demo") == "demo"
    with pytest.raises(InvalidRequestError) as info:
        tenants.require("nope")
    message = str(info.value)
    assert message == "unknown tenant 'nope'; declared tenants: xa, xb, demo. Nothing was sent."
    assert info.value.source == SOURCE
    assert_no_value(message)


def test_require_without_any_declaration_names_the_variables() -> None:
    with pytest.raises(InvalidRequestError) as info:
        make().require("demo")
    assert str(info.value) == (
        "unknown tenant 'demo'; no tenant is declared; set EXAMPLE_SRC_TENANTS and, per "
        "name, EXAMPLE_SRC_<NAME>_SUBDOMAIN and EXAMPLE_SRC_<NAME>_API_KEY; 'demo' is "
        "declared by EXAMPLE_SRC_DEMO_SUBDOMAIN and EXAMPLE_SRC_DEMO_API_KEY alone. Nothing was "
        "sent."
    )


def test_require_names_the_variables_of_an_absent_reserved_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("EXAMPLE_SRC_DEMO_SUBDOMAIN", HIDDEN_SUBDOMAIN)  # the key is missing
    with pytest.raises(InvalidRequestError) as info:
        make().require("demo")
    assert str(info.value) == (
        "unknown tenant 'demo'; declared tenants: xa; 'demo' is declared by "
        "EXAMPLE_SRC_DEMO_SUBDOMAIN and EXAMPLE_SRC_DEMO_API_KEY alone. Nothing was sent."
    )
    with pytest.raises(InvalidRequestError) as info:
        make().require("nope")
    assert str(info.value) == "unknown tenant 'nope'; declared tenants: xa. Nothing was sent."


def test_require_refuses_a_malformed_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xa")
    with pytest.raises(ConfigError, match="twice"):
        make().require("xa")


# -- field --------------------------------------------------------------------------------


def test_field_returns_the_value_stripped_and_unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    """The source checks the value's shape itself, its message quoting no value."""
    monkeypatch.setenv("EXAMPLE_TENANTS", "acme")
    monkeypatch.setenv("EXAMPLE_ACME_SUBDOMAIN", "  Acme-Books ")
    monkeypatch.setenv("EXAMPLE_ACME_API_KEY", f" {HIDDEN_KEY}\n")
    tenants = Tenants(
        "example", list_var="EXAMPLE_TENANTS", param="org", fields=("SUBDOMAIN", "API_KEY")
    )
    assert tenants.field("acme", "SUBDOMAIN") == "Acme-Books"
    assert tenants.field("acme", "API_KEY") == HIDDEN_KEY


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_field_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    if value is not None:
        monkeypatch.setenv("EXAMPLE_SRC_XA_SUBDOMAIN", value)
    with pytest.raises(ConfigError) as info:
        make().field("xa", "SUBDOMAIN")
    expected = "EXAMPLE_SRC_XA_SUBDOMAIN is not set; export the SUBDOMAIN of tenant 'xa'"
    assert str(info.value) == expected


def test_field_of_an_undeclared_tenant_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    declare(monkeypatch, "xa")  # its variables are set, but it is not listed
    with pytest.raises(InvalidRequestError, match="unknown tenant 'xa'"):
        make().field("xa", "SUBDOMAIN")


def test_field_refuses_an_unknown_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    with pytest.raises(ValueError, match="unknown field 'HOST'"):
        make().field("xa", "HOST")


# -- client_for ---------------------------------------------------------------------------

RATE = RateLimit(per_minute=60)


class Builder:
    """Builds a tenant's client as a source would, and counts the builds."""

    def __init__(self, tenants: Tenants, transport: httpx.AsyncBaseTransport | None = None):
        self.tenants = tenants
        self.transport = transport
        self.built: list[str] = []

    def __call__(self, name: str) -> AsyncClient:
        self.built.append(name)
        subdomain = self.tenants.field(name, "SUBDOMAIN")
        config = ClientConfig(
            source=self.tenants.source,
            version="1",
            base_url=f"https://{subdomain}.example.test/api",
            rate_limit=RATE,
        )
        auth = KeyAuth(
            self.tenants.var(name, "API_KEY"), location="basic", source=self.tenants.source
        )
        return AsyncClient(config, auth=auth, transport=self.transport)


def test_each_tenant_has_its_own_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xb")
    declare(monkeypatch, "xa")
    declare(monkeypatch, "xb")
    tenants = make()
    build = Builder(tenants)
    a, b = tenants.client_for("xa", build), tenants.client_for("xb", build)
    assert a is not b
    assert tenants.client_for("xa", build) is a
    assert build.built == ["xa", "xb"]
    assert a.config.base_url == f"https://xa-{HIDDEN_SUBDOMAIN}.example.test/api"
    assert b.config.base_url == f"https://xb-{HIDDEN_SUBDOMAIN}.example.test/api"
    assert a._bucket is not None
    assert b._bucket is not None
    assert a._bucket is not b._bucket


@pytest.mark.parametrize("field", ["SUBDOMAIN", "API_KEY"])
def test_a_changed_variable_keeps_the_client_until_reset(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """One client per tenant: ``reset()`` is the one way to a new one.

    No code of the family changes a tenant's variables after start, so the registry reads
    them when it builds and never compares them again (ADR-0036, amendment 2026-11-24).
    """
    tenants = Tenants(
        "example", list_var="EXAMPLE_TENANTS", param="org", fields=("SUBDOMAIN", "API_KEY")
    )
    monkeypatch.setenv("EXAMPLE_TENANTS", "acme")
    monkeypatch.setenv("EXAMPLE_ACME_SUBDOMAIN", "acme")
    monkeypatch.setenv("EXAMPLE_ACME_API_KEY", "acme-placeholder")  # pragma: allowlist secret
    build = Builder(tenants)
    first = tenants.client_for("acme", build)
    monkeypatch.setenv(tenants.var("acme", field), "other")
    assert tenants.client_for("acme", build) is first
    assert build.built == ["acme"]
    tenants.reset()
    second = tenants.client_for("acme", build)
    assert second is not first
    assert build.built == ["acme", "acme"]
    if field == "SUBDOMAIN":
        assert second.config.base_url == "https://other.example.test/api"


def test_the_cache_keeps_no_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa")
    tenants = make()
    tenants.client_for("xa", Builder(tenants))
    assert HIDDEN_KEY not in repr(tenants._clients)
    assert HIDDEN_KEY not in repr(vars(tenants))


def test_client_for_refuses_an_undeclared_tenant_without_building() -> None:
    tenants = make()
    build = Builder(tenants)
    with pytest.raises(InvalidRequestError, match="unknown tenant 'xa'"):
        tenants.client_for("xa", build)
    assert build.built == []


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_value_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    if value is not None:
        monkeypatch.setenv("EXAMPLE_SRC_XA_SUBDOMAIN", value)
    tenants = make()
    with pytest.raises(ConfigError, match="EXAMPLE_SRC_XA_SUBDOMAIN is not set"):
        tenants.client_for("xa", Builder(tenants))


@pytest.mark.anyio
async def test_a_declared_tenant_without_its_key_fails_on_the_first_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={})

    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa", key=False)
    tenants = make()
    client = tenants.client_for("xa", Builder(tenants, httpx.MockTransport(answer)))
    with pytest.raises(ConfigError, match="EXAMPLE_SRC_XA_API_KEY is not set"):
        await client.get("/fiscalperiod/list.json")
    assert sent == []


def test_reset_drops_every_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa")
    tenants = make()
    build = Builder(tenants)
    first = tenants.client_for("xa", build)
    tenants.reset()
    assert tenants.client_for("xa", build) is not first
    assert build.built == ["xa", "xa"]


def test_reset_drops_without_closing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dropped client's pools go with it: nothing awaits its ``aclose``."""
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa")
    tenants = make()
    first = tenants.client_for("xa", Builder(tenants))
    closed: list[AsyncClient] = []

    async def aclose() -> None:
        closed.append(first)

    monkeypatch.setattr(first, "aclose", aclose)
    tenants.reset()
    assert closed == []


def test_client_for_builds_once_under_concurrent_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa")
    tenants = make()
    build = Builder(tenants)
    workers = 8
    barrier = threading.Barrier(workers)

    def call(_: int) -> AsyncClient:
        barrier.wait()
        return tenants.client_for("xa", build)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        clients = list(pool.map(call, range(workers)))
    assert build.built == ["xa"]
    assert all(client is clients[0] for client in clients)


# -- list_task ----------------------------------------------------------------------------


def test_list_task_returns_the_names_in_the_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xb,xa")
    declare(monkeypatch, "xa")
    declare_demo(monkeypatch)
    task = list_task(make(), name="list_organisations")
    assert task.__name__ == "list_organisations"
    assert task.__qualname__ == "list_organisations"
    result = task()
    assert isinstance(result, Result)
    assert result.data == ["xb", "xa", "demo"]
    assert result.meta.source == SOURCE
    assert result.meta.endpoint == "list_organisations"
    assert result.meta.tenant is None
    assert result.meta.request == {}
    assert_no_value(result.model_dump_json())
    monkeypatch.setenv(LIST_VAR, "xc")
    assert task().data == ["xc", "demo"]  # read on every call


def test_list_task_names_its_registry_s_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """``meta.source`` is the registry's slug, whatever prefix its variables carry."""
    monkeypatch.setenv(MAIL_LIST_VAR, "work")
    result = list_task(make_mail(), name="list_accounts")()
    assert result.data == ["work"]
    assert (result.meta.source, result.meta.endpoint) == (MAIL_SOURCE, "list_accounts")


def test_list_task_takes_no_other_source() -> None:
    """``source=`` had no caller and left core in 0.5.0 (ADR-0036, amendment 2026-11-24)."""
    tenants = Tenants("example", list_var="EXAMPLE_TENANTS", param="org", fields=("API_KEY",))
    with pytest.raises(TypeError, match="source"):
        list_task(tenants, name="list_tenants", source="other")  # type: ignore[call-arg]


def test_list_task_marks_its_task_for_a_bound_server() -> None:
    """The mark a lock that binds one tenant reads, to list that tenant alone."""
    task = list_task(make(), name="list_organisations")
    assert getattr(task, "__xippios_lists_tenants__", None) is True


def test_list_task_has_a_docstring_for_agents() -> None:
    tenants = make()
    task = list_task(tenants, name="list_tenants")
    assert task.__doc__ is not None
    assert task.__doc__.startswith("List the tenants this server can reach, by name.\n")
    assert "never a credential" in task.__doc__
    own = list_task(tenants, name="list_organisations", doc="List the organisations.")
    assert own.__doc__ == "List the organisations."


@pytest.mark.parametrize("name", ["", "list organisations", "list-organisations"])
def test_list_task_refuses_a_name_that_is_no_identifier(name: str) -> None:
    with pytest.raises(ValueError, match="not a Python identifier"):
        list_task(make(), name=name)


@pytest.mark.anyio
async def test_list_task_is_a_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    tenants = make()
    task: Callable[[], Result[list[str]]] = list_task(tenants, name="list_organisations")
    server = build_server(ToolSet(SOURCE, [task]))
    tools = {tool.name: tool for tool in await server.list_tools()}
    tool = tools["example_src_list_organisations"]
    assert tool.input_schema.get("properties", {}) == {}
    assert tool.description is not None
    assert tool.description.startswith("List the tenants")
    payload = await mcp_call(server, "example_src_list_organisations", {})
    assert payload["data"] == ["xa"]
    assert payload["meta"]["endpoint"] == "list_organisations"
    assert payload["meta"]["tenant"] is None
    monkeypatch.setenv(LIST_VAR, "xa,xa")
    with pytest.raises(AssertionError, match=r"error: ConfigError: .* lists 'xa' twice"):
        await mcp_call(server, "example_src_list_organisations", {})
