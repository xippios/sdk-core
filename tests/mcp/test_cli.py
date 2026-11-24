"""The one entry, ``main(build, *, tenants=None, check=None, argv=None)`` (ADR-0063, decision 7).

``main`` takes a package's ``build``, reads the option hooks from the tool set that it
returns, builds the server that it runs and binds a tenant where ``tenants`` is given. Every
package is built here as a rendered ``mcp.py`` builds it, by ``ToolSet.from_tasks`` from a
tasks module of the invented source. ``MCPServer.run`` is replaced, so nothing is served.
"""

import argparse
import json
import logging
import os
import sys
import types
from collections.abc import Callable
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer

import xippios.core.mcp
from xippios.core import ConfigError, InvalidRequestError, TenantLock, Tenants, XippiosError
from xippios.core.mcp import LOOPBACK_HOSTS, ToolSet, build_parser, build_server, cli, main
from xippios.core.testing import mcp_call_text

REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")
ENTRY_POINT = "xippios-example-mcp-read"
SOURCE = "example"
ALLOW_REMOTE = (
    "--allow-remote serve a write server, or a read server held to loopback, beyond "
    "loopback; it carries no authentication, put it behind a gateway"
)
"""The one help of ``--allow-remote``, whatever the server (https://github.com/xippios/sdk-core/issues/485)."""

Served = list[tuple[MCPServer, str, dict[str, Any]]]


@pytest.fixture(autouse=True)
def entry_point(monkeypatch: pytest.MonkeyPatch) -> str:
    """The program name ``main`` runs under: the entry point's script, as installed.

    An installed script runs as ``__main__`` without a module spec, which argparse reads
    to tell it from ``python -m``, whichever way pytest itself was started.
    """
    monkeypatch.setattr(sys, "argv", [f"/opt/venv/bin/{ENTRY_POINT}"])
    monkeypatch.setattr(sys.modules["__main__"], "__spec__", None)
    return ENTRY_POINT


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> Served:
    """Every server ``main`` would have run, with its transport and options."""
    calls: Served = []

    def run(self: MCPServer, transport: str = "stdio", **options: Any) -> None:
        calls.append((self, transport, options))

    monkeypatch.setattr(MCPServer, "run", run)
    return calls


def get_series(series_id: str) -> dict[str, str]:
    """Fetch one series.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
    """
    return {"series_id": series_id}


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name}


def tasks_module(*tasks: Callable[..., Any], **declarations: Any) -> types.ModuleType:
    """A source's tasks module: ``tasks`` in ``__all__``, and its declarations for core."""
    module = types.ModuleType("xippios.example.tasks")
    module.__all__ = [fn.__name__ for fn in tasks]  # type: ignore[attr-defined]
    for fn in tasks:
        setattr(module, fn.__name__, fn)
    for name, value in declarations.items():
        setattr(module, name, value)
    return module


class Builds:
    """A package's ``build``, as a rendered ``mcp.py`` writes it, counting its calls.

    Called without a lock it builds the tool set of every declared tenant, as a source
    without tenants builds its only one.
    """

    def __init__(self, tasks: types.ModuleType, *, read_only: bool = True) -> None:
        self.tasks = tasks
        self.read_only = read_only
        self.locks: list[TenantLock | None] = []

    def __call__(self, lock: TenantLock | None = None) -> ToolSet:
        self.locks.append(lock)
        return ToolSet.from_tasks(
            SOURCE, self.tasks, version="1.2.0", lock=lock, read_only=self.read_only
        )


def reads() -> Builds:
    """A read package without options of its own."""
    return Builds(tasks_module(get_series))


def writes() -> Builds:
    """A write package, whose server is held to loopback."""
    return Builds(tasks_module(create_thing), read_only=False)


def held() -> Builds:
    """A read package whose tasks module holds its server to loopback."""
    return Builds(tasks_module(get_series, MCP_LOOPBACK_ONLY=True))


def help_of(build: Callable[..., ToolSet], capsys: pytest.CaptureFixture[str], **given: Any) -> str:
    """The help ``main`` prints for ``build``, its lines joined as argparse wraps them."""
    with pytest.raises(SystemExit) as info:
        main(build, argv=["--help"], **given)
    assert info.value.code == 0
    return " ".join(capsys.readouterr().out.split())


# The entry ----------------------------------------------------------------------------


def test_the_loopback_hosts_are_the_mcp_sdks() -> None:
    # The SDK's DNS-rebinding protection covers exactly these hosts (mcp 2.3.0).
    assert LOOPBACK_HOSTS == ("127.0.0.1", "localhost", "::1")


def test_parser_defaults() -> None:
    args = build_parser("x").parse_args([])
    assert (args.http, args.host, args.port, args.allow_remote) == (
        False,
        "127.0.0.1",
        8000,
        False,
    )


def test_parser_has_allow_remote_off_by_default() -> None:
    assert build_parser("x").parse_args([]).allow_remote is False
    assert build_parser("x").parse_args(["--allow-remote"]).allow_remote is True


def test_main_builds_the_server_of_the_tool_set_and_runs_it(served: Served) -> None:
    build = reads()
    main(build, argv=[])
    main(build, argv=["--http", "--host", "0.0.0.0", "--port", "9000"])
    assert [(transport, options) for _, transport, options in served] == [
        ("stdio", {}),
        ("streamable-http", {"host": "0.0.0.0", "port": 9000}),
    ]
    first, second = (server for server, _, _ in served)
    assert first is not second, "each run builds the server that it runs"
    assert (first.name, first.version) == ("xippios-example", "1.2.0")
    assert build.locks == [None, None], "build is called once, without a lock"


def test_main_takes_the_package_s_build_and_its_arguments_by_keyword(served: Served) -> None:
    # https://github.com/xippios/sdk-core/issues/476, parts 2 and 7.
    server = build_server(reads()())
    with pytest.raises(TypeError, match=r"^main takes the package's build, e.g. main\(build\)"):
        main(server, argv=[])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^build returns the package's ToolSet; it returned "):
        main(lambda: server, argv=[])  # type: ignore[arg-type, return-value]
    with pytest.raises(TypeError):
        main(reads(), [])  # type: ignore[call-arg, arg-type]
    assert served == []


def test_main_quiets_request_loggers_right_before_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, int] = {}

    def run(self: MCPServer, transport: str = "stdio", **options: Any) -> None:
        seen.update({name: logging.getLogger(name).level for name in REQUEST_LOGGERS})

    def build_and_log(tool_set: ToolSet) -> MCPServer:
        server = build_server(tool_set)
        # Something after the server is built puts the request log back on.
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)
        logging.getLogger("httpx2").setLevel(logging.INFO)
        logging.getLogger("httpcore2").setLevel(logging.DEBUG)
        return server

    monkeypatch.setattr(MCPServer, "run", run)
    monkeypatch.setattr(cli, "build_server", build_and_log)
    main(reads(), argv=[])
    assert seen == dict.fromkeys(REQUEST_LOGGERS, logging.WARNING)


SPLIT_YEARS: list[int] = []
"""What the source's ``apply_options`` was handed, run by run."""


def add_split_years(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--split-years", type=int, default=5, help="years one call splits")


def apply_split_years(namespace: argparse.Namespace) -> None:
    if namespace.split_years > 20:
        raise InvalidRequestError("--split-years takes 1 to 20", source=SOURCE)
    SPLIT_YEARS.append(namespace.split_years)


def with_options(*tasks: Callable[..., Any], **declarations: Any) -> types.ModuleType:
    """A tasks module that declares the two option hooks beside ``declarations``."""
    return tasks_module(
        *tasks,
        mcp_add_options=add_split_years,
        mcp_apply_options=apply_split_years,
        **declarations,
    )


def test_the_source_s_options_are_parsed_once_with_core_s_and_applied(
    monkeypatch: pytest.MonkeyPatch, served: Served
) -> None:
    monkeypatch.setattr(sys.modules[__name__], "SPLIT_YEARS", [])
    build = Builds(with_options(get_series))
    main(build, argv=["--split-years", "7", "--http", "--port", "9001"])
    main(build, argv=[])
    assert SPLIT_YEARS == [7, 5], "the hook takes the parsed options and returns nothing"
    assert [(transport, options) for _, transport, options in served] == [
        ("streamable-http", {"host": "127.0.0.1", "port": 9001}),
        ("stdio", {}),
    ]


def test_help_lists_core_and_source_options(capsys: pytest.CaptureFixture[str]) -> None:
    text = help_of(Builds(with_options(get_series)), capsys)
    for option in ("--http", "--host", "--port", "--allow-remote", "--split-years"):
        assert option in text
    assert ALLOW_REMOTE in text


def test_the_usage_line_names_the_entry_point(capsys: pytest.CaptureFixture[str]) -> None:
    # https://github.com/xippios/sdk-core/issues/167: server.name is one slug for both servers
    assert help_of(reads(), capsys).startswith(f"usage: {ENTRY_POINT} ")


@pytest.mark.parametrize("build", [reads, writes, held], ids=["read", "write", "held"])
def test_the_help_of_allow_remote_is_one_wording_whatever_the_server(
    capsys: pytest.CaptureFixture[str], build: Callable[[], Builds]
) -> None:
    assert ALLOW_REMOTE in help_of(build(), capsys)


def test_a_parser_takes_no_server() -> None:
    parser = build_parser("xippios-example-mcp")
    assert parser.prog == "xippios-example-mcp"
    assert ALLOW_REMOTE in " ".join(parser.format_help().split())
    assert build_parser().prog == ENTRY_POINT  # argparse's default: the script's name
    with pytest.raises(TypeError, match="server"):
        build_parser(server=build_server(reads()()))  # type: ignore[call-arg]


def test_unknown_options_still_fail(served: Served, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(Builds(with_options(get_series)), argv=["--split-years", "3", "--nope"])
    assert info.value.code == 2
    assert "unrecognized arguments: --nope" in capsys.readouterr().err
    assert served == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (InvalidRequestError, "--split-years takes 1 to 20"),
        (ConfigError, "EXAMPLE_ACME_SUBDOMAIN is not set"),
    ],
)
def test_an_error_from_apply_options_exits_2_without_a_traceback(
    served: Served,
    capsys: pytest.CaptureFixture[str],
    error: type[XippiosError],
    message: str,
) -> None:
    def refuse(namespace: argparse.Namespace) -> None:
        raise error(message, source=SOURCE)

    tasks = tasks_module(get_series, mcp_add_options=add_split_years, mcp_apply_options=refuse)
    build = Builds(tasks)
    with pytest.raises(SystemExit) as info:
        main(build, argv=["--split-years", "21"])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: {message}" in err
    assert "Traceback" not in err
    assert served == []


# The hold to loopback, read from the tool set (ADR-0063, decision 5) --------------------


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "::", "example.test"])
def test_a_write_server_is_not_served_beyond_loopback(
    served: Served, capsys: pytest.CaptureFixture[str], host: str
) -> None:
    with pytest.raises(SystemExit) as info:
        main(writes(), argv=["--http", "--host", host])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert "xippios-example is a write server and carries no authentication" in err
    assert "--allow-remote" in err
    assert served == []


def test_allow_remote_serves_a_write_server_beyond_loopback(served: Served) -> None:
    main(writes(), argv=["--http", "--host", "0.0.0.0", "--allow-remote"])
    assert [(transport, options) for _, transport, options in served] == [
        ("streamable-http", {"host": "0.0.0.0", "port": 8000})
    ]


@pytest.mark.parametrize("host", LOOPBACK_HOSTS)
def test_a_write_server_is_served_on_loopback(served: Served, host: str) -> None:
    main(writes(), argv=["--http", "--host", host])
    main(writes(), argv=["--host", "0.0.0.0"])  # stdio: --host is not used
    assert [(transport, options) for _, transport, options in served] == [
        ("streamable-http", {"host": host, "port": 8000}),
        ("stdio", {}),
    ]


def test_a_write_server_takes_its_slug_s_name(served: Served) -> None:
    # https://github.com/xippios/sdk-core/issues/476, part 4: one name for both servers.
    main(writes(), argv=[])
    ((server, _, _),) = served
    assert server.name == "xippios-example"


def test_a_read_only_server_is_served_anywhere(served: Served) -> None:
    main(reads(), argv=["--http", "--host", "0.0.0.0"])
    assert [(transport, options) for _, transport, options in served] == [
        ("streamable-http", {"host": "0.0.0.0", "port": 8000})
    ]


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "::", "example.test"])
def test_a_read_server_held_to_loopback_is_not_served_beyond_it(
    served: Served, capsys: pytest.CaptureFixture[str], host: str
) -> None:
    # ADR-0025, D-a; https://github.com/xippios/sdk-core/issues/167; the hold is a
    # declaration of the tasks module (https://github.com/xippios/sdk-core/issues/476, part 4)
    with pytest.raises(SystemExit) as info:
        main(held(), argv=["--http", "--host", host])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert (
        f"{ENTRY_POINT}: error: xippios-example is a read server held to loopback and carries "
        "no authentication; serve it over --http on a loopback --host (127.0.0.1, localhost, "
        "::1), or pass --allow-remote and put it behind a gateway"
    ) in err
    assert served == []


def test_allow_remote_serves_a_read_server_held_to_loopback_beyond_it(served: Served) -> None:
    main(held(), argv=["--http", "--host", "0.0.0.0", "--allow-remote"])
    for host in LOOPBACK_HOSTS:
        main(held(), argv=["--http", "--host", host])
    main(held(), argv=["--host", "0.0.0.0"])  # stdio: --host is not used
    assert [(transport, options) for _, transport, options in served] == [
        ("streamable-http", {"host": "0.0.0.0", "port": 8000}),
        *[("streamable-http", {"host": host, "port": 8000}) for host in LOOPBACK_HOSTS],
        ("stdio", {}),
    ]


# tenants=: --<param> binds a multi-tenant source's server to one tenant ------------------
# The serve command of the multi-tenant sources (ADR-0036, decision 8; ADR-0063,
# decision 7), on the invented source, whose variables no shell sets.

TENANTS = Tenants(
    SOURCE,
    list_var="EXAMPLE_ORGS",
    param="org",
    fields=("SUBDOMAIN", "API_KEY"),
    reserved=("demo",),
    noun="organisation",
)
TEXT = "Example via xippios. Every tool takes org."
BOUND = "Example via xippios."
SENTENCE = (
    "This server is bound to org acme; every tool acts on that organisation and takes no org."
)


@pytest.fixture
def acme(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tenant ``acme`` declared with placeholder values, and no other."""
    for name in [name for name in os.environ if name.startswith("EXAMPLE_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(TENANTS.list_var, "acme")
    monkeypatch.setenv(TENANTS.var("acme", "SUBDOMAIN"), "placeholder")
    monkeypatch.setenv(TENANTS.var("acme", "API_KEY"), "placeholder")


def check_subdomain(name: str) -> str:
    """A source's own check of a tenant's subdomain, one label; its message quotes no value."""
    subdomain = TENANTS.field(name, "SUBDOMAIN")
    if not subdomain.isalnum():
        variable = TENANTS.var(name, "SUBDOMAIN")
        raise ConfigError(
            f"{variable} does not hold a valid SUBDOMAIN for tenant {name!r}", source=SOURCE
        )
    return subdomain


async def echo_org(org: str) -> dict[str, str]:
    """Return the organisation the tool was called for.

    Args:
        org: A declared organisation, e.g. ``acme``.
    """
    return {"org": org}


async def echo_account(account: str) -> dict[str, str]:
    """Return the account the tool was called for.

    Args:
        account: A declared account, e.g. ``acme``.
    """
    return {"account": account}


async def echo_org_name(org_name: str) -> dict[str, str]:
    """Return the organisation the tool was called for.

    Args:
        org_name: A declared organisation, e.g. ``acme``.
    """
    return {"org_name": org_name}


async def create_note(org: str, text: str, confirm: bool = False) -> dict[str, str]:
    """Create a note for an organisation; without confirm, return a preview.

    Args:
        org: A declared organisation, e.g. ``acme``.
        text: The note, e.g. ``"Paid"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"org": org, "text": text}


def orgs(**declarations: Any) -> Builds:
    """A multi-tenant read package whose one tool echoes its organisation."""
    return Builds(
        tasks_module(echo_org, MCP_INSTRUCTIONS=TEXT, MCP_BOUND_INSTRUCTIONS=BOUND, **declarations)
    )


@pytest.mark.anyio
@pytest.mark.usefixtures("acme")
async def test_main_binds_a_tenant_then_serves_the_bound_server(served: Served) -> None:
    build = orgs()
    argv = ["--host", "127.0.0.1", "--org=acme", "--http", "--port", "9001"]
    main(build, tenants=TENANTS, argv=argv)
    assert build.locks == [None, TenantLock(TENANTS, "acme")]
    ((server, transport, options),) = served
    assert (transport, options) == ("streamable-http", {"host": "127.0.0.1", "port": 9001})
    assert (server.name, server.version) == ("xippios-example", "1.2.0")
    assert server.instructions == f"{BOUND} {SENTENCE}"
    tool = {t.name: t for t in await server.list_tools()}["example_echo_org"]
    assert "org" not in tool.input_schema["properties"]
    assert json.loads(await mcp_call_text(server, "example_echo_org", {})) == {"org": "acme"}


@pytest.mark.usefixtures("acme")
def test_without_the_option_main_serves_every_declared_tenant(served: Served) -> None:
    build = orgs()
    checked: list[str] = []
    main(build, tenants=TENANTS, check=checked.append, argv=[])
    ((server, transport, _),) = served
    assert (transport, server.instructions) == ("stdio", TEXT)
    assert build.locks == [None]
    assert checked == [], "no tenant, no check"


@pytest.mark.usefixtures("acme")
def test_an_undeclared_tenant_stops_the_process_before_anything_is_built(
    served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    build = orgs()
    checked: list[str] = []
    with pytest.raises(SystemExit) as info:
        main(build, tenants=TENANTS, check=checked.append, argv=["--org", "nope"])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: unknown tenant 'nope'; declared tenants: acme" in err
    assert "Traceback" not in err
    assert (build.locks, checked, served) == ([None], [], [])


@pytest.mark.usefixtures("acme")
def test_the_check_is_given_the_declared_tenant_before_the_bound_build(served: Served) -> None:
    build = orgs()
    order: list[str] = []

    def check(name: str) -> None:
        order.append(f"check {name}, built {len(build.locks)}")

    main(build, tenants=TENANTS, check=check, argv=["--org", "acme"])
    assert order == ["check acme, built 1"], "after the unbound build, before the bound one"
    assert len(served) == 1


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "EXAMPLE_ACME_SUBDOMAIN is not set; export the SUBDOMAIN of tenant 'acme'"),
        ("evil.example/x?", "EXAMPLE_ACME_SUBDOMAIN does not hold a valid SUBDOMAIN"),
    ],
)
@pytest.mark.usefixtures("acme")
def test_an_error_of_the_check_stops_the_process_and_names_no_value(
    monkeypatch: pytest.MonkeyPatch,
    served: Served,
    capsys: pytest.CaptureFixture[str],
    value: str | None,
    message: str,
) -> None:
    """A source's check: the subdomain read as ``client_for`` reads it, at startup."""
    if value is None:
        monkeypatch.delenv(TENANTS.var("acme", "SUBDOMAIN"))
        monkeypatch.setenv(TENANTS.list_var, "acme")
    else:
        monkeypatch.setenv(TENANTS.var("acme", "SUBDOMAIN"), value)
    build = orgs()
    with pytest.raises(SystemExit) as info:
        main(build, tenants=TENANTS, check=check_subdomain, argv=["--org", "acme"])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: {message}" in err
    assert "evil.example" not in err
    assert (build.locks, served) == ([None], [])


SLUG_AND_PREFIX = Tenants(
    "example-mail",
    var_prefix="EXAMPLE",
    list_var="EXAMPLE_ACCOUNTS",
    param="account",
    fields=("REFRESH_TOKEN",),
)
PREFIX_AS_SLUG = Tenants(
    SOURCE, list_var="EXAMPLE_ACCOUNTS", param="account", fields=("REFRESH_TOKEN",)
)


@pytest.mark.parametrize(
    "registry", [SLUG_AND_PREFIX, PREFIX_AS_SLUG], ids=["slug-and-prefix", "prefix-as-slug"]
)
@pytest.mark.usefixtures("acme")
def test_a_registry_under_a_shared_prefix_binds_either_way(
    monkeypatch: pytest.MonkeyPatch,
    served: Served,
    capsys: pytest.CaptureFixture[str],
    registry: Tenants,
) -> None:
    """A registry whose prefix is not its slug binds as one whose prefix is.

    The command's text names the registry's tenants and variables, never its source, so
    a registry whose slug is its prefix and one that names the prefix apart print the same;
    the registry's name: https://github.com/xippios/sdk-core/issues/279.
    """
    monkeypatch.setenv("EXAMPLE_ACCOUNTS", "acme")
    monkeypatch.setenv("EXAMPLE_ACME_REFRESH_TOKEN", "placeholder")
    build = Builds(tasks_module(echo_account))
    main(build, tenants=registry, argv=["--account", "acme"])
    assert build.locks == [None, TenantLock(registry, "acme")]
    with pytest.raises(SystemExit):
        main(build, tenants=registry, argv=["--account", "nope"])
    assert f"{ENTRY_POINT}: error: unknown tenant 'nope'; declared tenants: acme" in (
        capsys.readouterr().err
    )
    assert len(served) == 1


def test_the_help_names_the_option_with_the_registry_s_noun_beside_core_s_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # https://github.com/xippios/sdk-core/issues/476, part 4: the noun is the registry's.
    text = help_of(orgs(), capsys, tenants=TENANTS)
    assert (
        "--org ORG serve only this organisation, e.g. demo; every tool acts on it and takes no org"
    ) in text
    for option in ("--http", "--host", "--port", "--allow-remote"):
        assert option in text


def test_without_a_noun_or_a_reserved_tenant_the_help_names_the_parameter(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = Tenants(SOURCE, list_var="EXAMPLE_ACCOUNTS", param="account", fields=("API_KEY",))
    text = help_of(Builds(tasks_module(echo_account)), capsys, tenants=registry)
    assert "serve only this account; every tool acts on it and takes no account" in text


@pytest.mark.usefixtures("acme")
def test_an_underscored_parameter_is_a_hyphenated_option(served: Served) -> None:
    registry = Tenants(
        SOURCE, list_var="EXAMPLE_ORGS", param="org_name", fields=("SUBDOMAIN", "API_KEY")
    )
    build = Builds(tasks_module(echo_org_name))
    main(build, tenants=registry, argv=["--org-name", "acme"])
    assert build.locks == [None, TenantLock(registry, "acme")]


@pytest.mark.usefixtures("acme")
def test_unknown_options_still_fail_with_tenants(
    served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    build = orgs()
    with pytest.raises(SystemExit) as info:
        main(build, tenants=TENANTS, argv=["--org", "acme", "--nope"])
    assert info.value.code == 2
    assert "unrecognized arguments: --nope" in capsys.readouterr().err
    assert (build.locks, served) == ([None], [])


@pytest.mark.usefixtures("acme")
def test_the_option_is_the_parameter_the_registry_declares(
    served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    """One declaration, ``Tenants(param=...)``: the command names no parameter of its own."""
    build = orgs()
    with pytest.raises(SystemExit):
        main(build, tenants=TENANTS, argv=["--account", "acme"])
    assert "unrecognized arguments: --account acme" in capsys.readouterr().err
    assert (build.locks, served) == ([None], [])


@pytest.mark.parametrize(
    ("build", "kind"),
    [
        (lambda: Builds(tasks_module(create_note), read_only=False), "a write server"),
        (lambda: orgs(MCP_LOOPBACK_ONLY=True), "a read server held to loopback"),
    ],
    ids=["write", "loopback-only"],
)
@pytest.mark.usefixtures("acme")
def test_a_bound_server_stays_held_to_loopback(
    served: Served,
    capsys: pytest.CaptureFixture[str],
    build: Callable[[], Builds],
    kind: str,
) -> None:
    """``main`` holds the bound server as it holds the unbound one, by its tool set."""
    remote = ["--org", "acme", "--http", "--host", "0.0.0.0"]
    with pytest.raises(SystemExit) as info:
        main(build(), tenants=TENANTS, argv=remote)
    assert info.value.code == 2
    assert f"xippios-example is {kind} and carries no authentication" in (capsys.readouterr().err)
    assert served == []
    for argv in ([*remote, "--allow-remote"], ["--org", "acme", "--http"]):
        main(build(), tenants=TENANTS, argv=argv)
    assert [(options["host"], server.instructions) for server, _, options in served] == [
        ("0.0.0.0", served[0][0].instructions),
        ("127.0.0.1", served[0][0].instructions),
    ]
    assert all((server.instructions or "").endswith(SENTENCE) for server, _, _ in served)


@pytest.mark.usefixtures("acme")
def test_main_keeps_request_urls_out_of_the_log_when_it_binds(served: Served) -> None:
    for name in REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    main(orgs(), tenants=TENANTS, argv=["--org", "acme"])
    assert [logging.getLogger(name).level for name in REQUEST_LOGGERS] == [logging.WARNING] * 4


@pytest.mark.usefixtures("acme")
def test_a_tenant_source_s_own_options_and_its_tenant_are_parsed_together(
    monkeypatch: pytest.MonkeyPatch, served: Served, capsys: pytest.CaptureFixture[str]
) -> None:
    # The hooks of a multi-tenant source reach its entry too, where serve_tenants dropped them.
    monkeypatch.setattr(sys.modules[__name__], "SPLIT_YEARS", [])
    build = Builds(with_options(echo_org, MCP_INSTRUCTIONS=TEXT))
    main(build, tenants=TENANTS, argv=["--split-years", "9", "--org", "acme"])
    assert SPLIT_YEARS == [9]
    assert build.locks == [None, TenantLock(TENANTS, "acme")]
    assert len(served) == 1
    text = help_of(build, capsys, tenants=TENANTS)
    assert "--split-years" in text
    assert "--org ORG" in text


def test_serve_tenants_is_gone() -> None:
    # ADR-0063, decision 7: one entry.
    assert not hasattr(xippios.core.mcp, "serve_tenants")
    assert not hasattr(cli, "serve_tenants")
