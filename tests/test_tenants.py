"""Tenants: declaration in the environment, lookup, field values, one client per tenant.

The behaviours are the ones sdk-cashctrl's organisation registry established
(tests/test_registry.py there), on a fictitious source whose variables no shell sets.
"""

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from xippios.core import (
    AsyncClient,
    BasicKeyAuth,
    ClientConfig,
    ConfigError,
    InvalidRequestError,
    RateLimit,
    Tenants,
)
from xippios.core.mcp import build_server
from xippios.core.models import Result
from xippios.core.tenants import list_task
from xippios.core.testing import mcp_call

SOURCE = "fictive-src"
PREFIX = "FICTIVE_SRC_"
LIST_VAR = "FICTIVE_SRC_TENANTS"
FIELDS = ("SUBDOMAIN", "API_KEY")

# Values that must never appear in a message.
HIDDEN_SUBDOMAIN = "xa-hidden-subdomain"
HIDDEN_KEY = "xa-hidden-key-value"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def no_fictive_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts without a variable of the fictitious source."""
    for name in [name for name in os.environ if name.startswith(PREFIX)]:
        monkeypatch.delenv(name, raising=False)
    for name in (LIST_VAR, "FICTIVE_SRC_DEMO_SUBDOMAIN", "FICTIVE_SRC_DEMO_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def placeholder_api_key() -> None:
    """Pins nothing: one test here proves a missing key fails on the first request.

    Every key variable this module reads belongs to the fictitious source and is set by
    the test itself, never taken from the shell.
    """
    return None


def check_subdomain(value: str) -> str:
    lowered = value.lower()
    if not lowered.replace("-", "").isalnum():
        raise ValueError(f"not a subdomain: {value}")  # quotes the value on purpose
    return lowered


def make(**overrides: object) -> Tenants:
    arguments: dict[str, object] = {
        "list_var": LIST_VAR,
        "fields": FIELDS,
        "reserved": ("demo",),
        "validate": {"SUBDOMAIN": check_subdomain},
    }
    arguments.update(overrides)
    return Tenants(SOURCE, **arguments)  # type: ignore[arg-type]


def declare(monkeypatch: pytest.MonkeyPatch, name: str, *, key: bool = True) -> None:
    monkeypatch.setenv(f"{PREFIX}{name.upper()}_SUBDOMAIN", f"{name}-{HIDDEN_SUBDOMAIN}")
    if key:
        monkeypatch.setenv(f"{PREFIX}{name.upper()}_API_KEY", f"{name}-{HIDDEN_KEY}")


def declare_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FICTIVE_SRC_DEMO_SUBDOMAIN", "demo")
    monkeypatch.setenv("FICTIVE_SRC_DEMO_API_KEY", "demo-key")  # pragma: allowlist secret


def assert_no_value(message: str) -> None:
    assert HIDDEN_SUBDOMAIN not in message
    assert HIDDEN_KEY not in message


# -- construction and variable names ----------------------------------------------------


def test_variable_names_follow_the_scheme() -> None:
    tenants = make()
    assert tenants.var("acme_test", "SUBDOMAIN") == "FICTIVE_SRC_ACME_TEST_SUBDOMAIN"
    assert tenants.var("demo", "API_KEY") == "FICTIVE_SRC_DEMO_API_KEY"  # pragma: allowlist secret
    assert Tenants("cashctrl", list_var="CASHCTRL_ORGS", fields=["SUBDOMAIN"]).var(
        "acme", "SUBDOMAIN"
    ) == ("CASHCTRL_ACME_SUBDOMAIN")
    with pytest.raises(ValueError, match="unknown field 'subdomain'; fields: SUBDOMAIN, API_KEY"):
        tenants.var("acme", "subdomain")


def test_attributes_and_repr_name_the_scheme_only(monkeypatch: pytest.MonkeyPatch) -> None:
    declare(monkeypatch, "xa")
    tenants = make()
    assert tenants.source == SOURCE
    assert tenants.list_var == LIST_VAR
    assert tenants.fields == FIELDS
    assert tenants.reserved == ("demo",)
    assert repr(tenants) == (
        "Tenants('fictive-src', list_var='FICTIVE_SRC_TENANTS', "
        "fields=('SUBDOMAIN', 'API_KEY'), reserved=('demo',))"
    )


@pytest.mark.parametrize(
    ("overrides", "error", "match"),
    [
        ({"list_var": ""}, ValueError, "list_var must not be empty"),
        ({"fields": ()}, ValueError, "at least one"),
        ({"fields": ("subdomain",)}, ValueError, "field 'subdomain' is not upper-case"),
        ({"fields": ("A", "B", "A")}, ValueError, "field given twice: A"),
        ({"fields": "SUBDOMAIN"}, TypeError, "fields is a sequence"),
        ({"reserved": "demo"}, TypeError, "reserved is a sequence"),
        ({"reserved": ("Demo",)}, ValueError, "reserved name 'Demo' is not lower-case"),
        ({"reserved": ("demo", "demo")}, ValueError, "reserved name given twice: demo"),
        ({"validate": {"HOST": check_subdomain}}, ValueError, "fields not in fields: HOST"),
        ({"hints": {"HOST": "a host"}}, ValueError, "hints names fields not in fields: HOST"),
        (
            {"validate": {}, "hints": {"SUBDOMAIN": "the subdomain alone"}},
            ValueError,
            "hints names fields without a validate check: SUBDOMAIN",
        ),
    ],
)
def test_construction_refuses_a_malformed_scheme(
    overrides: dict[str, object], error: type[Exception], match: str
) -> None:
    with pytest.raises(error, match=match):
        make(**overrides)


def test_construction_refuses_an_empty_source() -> None:
    with pytest.raises(ValueError, match="source must not be empty"):
        Tenants("", list_var=LIST_VAR, fields=FIELDS)


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
    monkeypatch.setenv("FICTIVE_SRC_SANDBOX_SUBDOMAIN", "sandbox")
    monkeypatch.setenv("FICTIVE_SRC_SANDBOX_API_KEY", "sandbox-key")  # pragma: allowlist secret
    assert make(reserved=("sandbox", "demo")).names() == ("xa", "sandbox", "demo")


@pytest.mark.parametrize("missing", ["SUBDOMAIN", "API_KEY"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_reserved_tenant_needs_every_variable(
    monkeypatch: pytest.MonkeyPatch, missing: str, value: str | None
) -> None:
    declare_demo(monkeypatch)
    if value is None:
        monkeypatch.delenv(f"FICTIVE_SRC_DEMO_{missing}")
    else:
        monkeypatch.setenv(f"FICTIVE_SRC_DEMO_{missing}", value)
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
    assert "FICTIVE_SRC_DEMO_SUBDOMAIN and FICTIVE_SRC_DEMO_API_KEY alone" in str(info.value)
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
        "entry 3 of FICTIVE_SRC_TENANTS is not a tenant name; names use only lower-case "
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
    assert message == "unknown tenant 'nope'; declared tenants: xa, xb, demo"
    assert info.value.source == SOURCE
    assert_no_value(message)


def test_require_without_any_declaration_names_the_variables() -> None:
    with pytest.raises(InvalidRequestError) as info:
        make().require("demo")
    assert str(info.value) == (
        "unknown tenant 'demo'; no tenant is declared; set FICTIVE_SRC_TENANTS and, per "
        "name, FICTIVE_SRC_<NAME>_SUBDOMAIN and FICTIVE_SRC_<NAME>_API_KEY; 'demo' is "
        "declared by FICTIVE_SRC_DEMO_SUBDOMAIN and FICTIVE_SRC_DEMO_API_KEY alone"
    )


def test_require_names_the_variables_of_an_absent_reserved_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("FICTIVE_SRC_DEMO_SUBDOMAIN", HIDDEN_SUBDOMAIN)  # the key is missing
    with pytest.raises(InvalidRequestError) as info:
        make().require("demo")
    assert str(info.value) == (
        "unknown tenant 'demo'; declared tenants: xa; 'demo' is declared by "
        "FICTIVE_SRC_DEMO_SUBDOMAIN and FICTIVE_SRC_DEMO_API_KEY alone"
    )
    with pytest.raises(InvalidRequestError) as info:
        make().require("nope")
    assert str(info.value) == "unknown tenant 'nope'; declared tenants: xa"


def test_require_refuses_a_malformed_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa,xa")
    with pytest.raises(ConfigError, match="twice"):
        make().require("xa")


# -- field --------------------------------------------------------------------------------


def test_field_returns_the_value_stripped_and_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", "  Acme-Books ")
    monkeypatch.setenv("FICTIVE_SRC_XA_API_KEY", f" {HIDDEN_KEY}\n")
    tenants = make()
    assert tenants.field("xa", "SUBDOMAIN") == "acme-books"  # normalised by the check
    assert tenants.field("xa", "API_KEY") == HIDDEN_KEY  # no check: stripped only


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_field_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    if value is not None:
        monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", value)
    with pytest.raises(ConfigError) as info:
        make().field("xa", "SUBDOMAIN")
    expected = "FICTIVE_SRC_XA_SUBDOMAIN is not set; export the SUBDOMAIN of tenant 'xa'"
    assert str(info.value) == expected


@pytest.mark.parametrize("value", ["evil.com/x?", "a_b", f"{HIDDEN_SUBDOMAIN}.x"])
def test_a_refused_value_names_the_variable_and_not_the_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", value)
    with pytest.raises(ConfigError) as info:
        make().field("xa", "SUBDOMAIN")
    message = str(info.value)
    assert message == "FICTIVE_SRC_XA_SUBDOMAIN does not hold a valid SUBDOMAIN for tenant 'xa'"
    assert value not in message
    assert info.value.__cause__ is None
    assert info.value.__context__ is None  # the check's error, which quotes it, is not kept


HINT = "set the subdomain alone, e.g. acme for acme.example.org"


@pytest.mark.parametrize("value", ["evil.com/x?", f"{HIDDEN_SUBDOMAIN}.x"])
def test_a_refused_value_ends_with_the_field_s_hint_and_not_the_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", value)
    with pytest.raises(ConfigError) as info:
        make(hints={"SUBDOMAIN": HINT}).field("xa", "SUBDOMAIN")
    message = str(info.value)
    assert message == (
        "FICTIVE_SRC_XA_SUBDOMAIN does not hold a valid SUBDOMAIN for tenant 'xa'; " + HINT
    )
    assert value not in message
    assert "not a subdomain" not in message  # the check's own text quotes the value
    assert info.value.__context__ is None


def test_a_hint_is_for_a_refused_value_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    tenants = make(hints={"SUBDOMAIN": HINT})
    with pytest.raises(ConfigError) as info:
        tenants.field("xa", "SUBDOMAIN")
    assert str(info.value) == (
        "FICTIVE_SRC_XA_SUBDOMAIN is not set; export the SUBDOMAIN of tenant 'xa'"
    )
    monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", "Acme")
    assert tenants.field("xa", "SUBDOMAIN") == "acme"


def test_a_check_failing_with_any_exception_refuses_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(value: str) -> str:
        raise TypeError(f"cannot check {value}")  # quotes the value on purpose

    monkeypatch.setenv(LIST_VAR, "xa")
    monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", HIDDEN_SUBDOMAIN)
    with pytest.raises(ConfigError) as info:
        make(validate={"SUBDOMAIN": broken}).field("xa", "SUBDOMAIN")
    assert str(info.value) == (
        "FICTIVE_SRC_XA_SUBDOMAIN does not hold a valid SUBDOMAIN for tenant 'xa'"
    )
    assert info.value.__cause__ is None
    assert info.value.__context__ is None


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
            source=SOURCE,
            version="1",
            base_url=f"https://{subdomain}.example.test/api",
            rate_limit=RATE,
        )
        auth = BasicKeyAuth(self.tenants.var(name, "API_KEY"), source=SOURCE)
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


@pytest.mark.parametrize("variable", ["FICTIVE_SRC_XA_SUBDOMAIN", "FICTIVE_SRC_XA_API_KEY"])
def test_a_changed_value_builds_a_new_client(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa")
    tenants = make()
    build = Builder(tenants)
    first = tenants.client_for("xa", build)
    monkeypatch.setenv(variable, "other")
    second = tenants.client_for("xa", build)
    assert second is not first
    assert tenants.client_for("xa", build) is second
    assert build.built == ["xa", "xa"]


def test_a_variable_set_later_builds_a_new_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    declare(monkeypatch, "xa", key=False)
    tenants = make()
    build = Builder(tenants)
    first = tenants.client_for("xa", build)
    monkeypatch.setenv("FICTIVE_SRC_XA_API_KEY", "")
    assert tenants.client_for("xa", build) is not first  # unset and empty differ


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


@pytest.mark.parametrize("value", [None, "", "evil.com/x?"])
def test_a_missing_or_malformed_value_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    monkeypatch.setenv(LIST_VAR, "xa")
    if value is not None:
        monkeypatch.setenv("FICTIVE_SRC_XA_SUBDOMAIN", value)
    tenants = make()
    with pytest.raises(ConfigError, match="FICTIVE_SRC_XA_SUBDOMAIN") as info:
        tenants.client_for("xa", Builder(tenants))
    if value:
        assert value not in str(info.value)


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
    with pytest.raises(ConfigError, match="FICTIVE_SRC_XA_API_KEY is not set"):
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
    server = build_server(SOURCE, [task])
    tools = {tool.name: tool for tool in await server.list_tools()}
    tool = tools["fictive_src_list_organisations"]
    assert tool.input_schema.get("properties", {}) == {}
    assert tool.description is not None
    assert tool.description.startswith("List the tenants")
    payload = await mcp_call(server, "fictive_src_list_organisations", {})
    assert payload["data"] == ["xa"]
    assert payload["meta"]["endpoint"] == "list_organisations"
    assert payload["meta"]["tenant"] is None
    monkeypatch.setenv(LIST_VAR, "xa,xa")
    with pytest.raises(AssertionError, match=r"error: ConfigError: .* lists 'xa' twice"):
        await mcp_call(server, "fictive_src_list_organisations", {})
