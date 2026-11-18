import argparse
import json
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer

from xippios.core import (
    ConfigError,
    InvalidRequestError,
    TenantLock,
    Tenants,
    XippiosError,
    bind_tasks,
    tenant_instructions,
)
from xippios.core.mcp import (
    LOOPBACK_HOSTS,
    ToolSet,
    build_parser,
    build_server,
    main,
    serve_tenants,
)
from xippios.core.testing import mcp_call_text

REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")
ENTRY_POINT = "xippios-example-mcp-read"


@pytest.fixture(autouse=True)
def entry_point(monkeypatch: pytest.MonkeyPatch) -> str:
    """The program name ``main`` runs under: the entry point's script, as installed.

    An installed script runs as ``__main__`` without a module spec, which argparse reads
    to tell it from ``python -m``, whichever way pytest itself was started.
    """
    monkeypatch.setattr(sys, "argv", [f"/opt/venv/bin/{ENTRY_POINT}"])
    monkeypatch.setattr(sys.modules["__main__"], "__spec__", None)
    return ENTRY_POINT


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


def test_main_dispatches_to_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_server("example", [])
    calls: list[tuple[Any, ...]] = []

    def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
        calls.append((transport, kwargs))

    monkeypatch.setattr(server, "run", fake_run)
    main(server, [])
    main(server, ["--http", "--host", "0.0.0.0", "--port", "9000"])
    assert calls == [
        ("stdio", {}),
        ("streamable-http", {"host": "0.0.0.0", "port": 9000}),
    ]


def test_main_quiets_request_loggers_before_running(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_server("example", [])
    seen: dict[str, int] = {}

    def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
        seen.update({name: logging.getLogger(name).level for name in REQUEST_LOGGERS})

    monkeypatch.setattr(server, "run", fake_run)
    # Something between build_server and main puts the request log back on.
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    logging.getLogger("httpx2").setLevel(logging.INFO)
    logging.getLogger("httpcore2").setLevel(logging.DEBUG)
    main(server, [])
    assert seen == dict.fromkeys(REQUEST_LOGGERS, logging.WARNING)


def test_parser_has_allow_remote_off_by_default() -> None:
    assert build_parser("x").parse_args([]).allow_remote is False
    assert build_parser("x").parse_args(["--allow-remote"]).allow_remote is True


def add_org(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--org", help="serve only this tenant")


class Runs:
    """Records ``run`` on every server it is attached to, instead of serving."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        self.calls: list[tuple[MCPServer, str, dict[str, Any]]] = []

    def attach(self, server: MCPServer) -> MCPServer:
        def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
            self.calls.append((server, transport, kwargs))

        self.monkeypatch.setattr(server, "run", fake_run)
        return server


def test_an_added_option_is_parsed_once_and_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", []))
    acme = runs.attach(build_server("example", [], name="xippios-example-acme"))
    seen: list[argparse.Namespace] = []

    def apply(args: argparse.Namespace, given: MCPServer) -> MCPServer:
        assert given is server
        seen.append(args)
        return given if args.org is None else acme

    main(
        server,
        ["--org", "acme", "--http", "--port", "9001"],
        add_options=add_org,
        apply_options=apply,
    )
    main(server, ["--http"], add_options=add_org, apply_options=apply)
    assert [args.org for args in seen] == ["acme", None]
    assert runs.calls == [
        (acme, "streamable-http", {"host": "127.0.0.1", "port": 9001}),
        (server, "streamable-http", {"host": "127.0.0.1", "port": 8000}),
    ]


def test_help_lists_core_and_source_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(build_server("example", []), ["--help"], add_options=add_org)
    assert info.value.code == 0
    out = capsys.readouterr().out
    for option in ("--http", "--host", "--port", "--allow-remote", "--org"):
        assert option in out
    help_text = " ".join(out.split())  # argparse wraps the help lines
    assert "--allow-remote changes nothing: this read server is not held to loopback" in help_text


def help_of(server: MCPServer, capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as info:
        main(server, ["--help"])
    assert info.value.code == 0
    return " ".join(capsys.readouterr().out.split())  # argparse wraps the help lines


def test_the_usage_line_names_the_entry_point(capsys: pytest.CaptureFixture[str]) -> None:
    # https://github.com/xippios/sdk-core/issues/167: server.name is one slug for both servers
    assert help_of(build_server("example", []), capsys).startswith(f"usage: {ENTRY_POINT} ")


def test_the_help_of_allow_remote_names_the_server_kind(
    capsys: pytest.CaptureFixture[str],
) -> None:
    write = build_server("example", [create_thing], read_only=False)
    assert (
        "--allow-remote serve this write server beyond loopback; it carries no "
        "authentication, put it behind a gateway"
    ) in help_of(write, capsys)
    held = build_server("example", [], loopback_only=True)
    assert (
        "--allow-remote serve this read server beyond loopback; it carries no "
        "authentication, put it behind a gateway"
    ) in help_of(held, capsys)


def test_a_parser_built_without_a_server_names_both_kinds() -> None:
    parser = build_parser("xippios-example-mcp")
    assert parser.prog == "xippios-example-mcp"
    help_text = " ".join(parser.format_help().split())
    assert (
        "--allow-remote serve a write server, or a read server built with loopback_only=True, "
        "beyond loopback; it carries no authentication, put it behind a gateway"
    ) in help_text
    assert build_parser().prog == ENTRY_POINT  # argparse's default: the script's name


def test_unknown_options_still_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", []))
    with pytest.raises(SystemExit) as info:
        main(server, ["--org", "acme", "--nope"], add_options=add_org)
    assert info.value.code == 2
    assert "unrecognized arguments: --nope" in capsys.readouterr().err
    assert runs.calls == []


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (InvalidRequestError, "unknown tenant 'nope'; declared tenants: acme"),
        (ConfigError, "EXAMPLE_ACME_SUBDOMAIN is not set"),
    ],
)
def test_an_error_from_apply_options_exits_2_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: type[XippiosError],
    message: str,
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [], name="xippios-example"))

    def apply(args: argparse.Namespace, given: MCPServer) -> MCPServer:
        raise error(message, source="example")

    with pytest.raises(SystemExit) as info:
        main(server, ["--org", "nope"], add_options=add_org, apply_options=apply)
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: {message}" in err
    assert "Traceback" not in err
    assert runs.calls == []


def create_thing(name: str, confirm: bool = False) -> dict[str, str]:
    """Create a thing; without confirm, return a preview.

    Args:
        name: The thing's name, e.g. ``"Corn"``.
        confirm: ``True`` writes, ``False`` previews.
    """
    return {"name": name}


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "::", "example.test"])
def test_a_write_server_is_not_served_beyond_loopback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], host: str
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [create_thing], read_only=False))
    with pytest.raises(SystemExit) as info:
        main(server, ["--http", "--host", host])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert "xippios-example is a write server and carries no authentication" in err
    assert "--allow-remote" in err
    assert runs.calls == []


def test_allow_remote_serves_a_write_server_beyond_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [create_thing], read_only=False))
    main(server, ["--http", "--host", "0.0.0.0", "--allow-remote"])
    assert runs.calls == [(server, "streamable-http", {"host": "0.0.0.0", "port": 8000})]


@pytest.mark.parametrize("host", LOOPBACK_HOSTS)
def test_a_write_server_is_served_on_loopback(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [create_thing], read_only=False))
    main(server, ["--http", "--host", host])
    main(server, ["--host", "0.0.0.0"])  # stdio: --host is not used
    assert runs.calls == [
        (server, "streamable-http", {"host": host, "port": 8000}),
        (server, "stdio", {}),
    ]


def test_a_read_only_server_is_served_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", []))
    main(server, ["--http", "--host", "0.0.0.0"])
    assert runs.calls == [(server, "streamable-http", {"host": "0.0.0.0", "port": 8000})]


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.10", "::", "example.test"])
def test_a_read_server_held_to_loopback_is_not_served_beyond_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], host: str
) -> None:
    # ADR-0025, D-a; https://github.com/xippios/sdk-core/issues/167
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [], loopback_only=True))
    with pytest.raises(SystemExit) as info:
        main(server, ["--http", "--host", host])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert (
        f"{ENTRY_POINT}: error: xippios-example is a read server held to loopback and carries "
        "no authentication; serve it over --http on a loopback --host (127.0.0.1, localhost, "
        "::1), or pass --allow-remote and put it behind a gateway"
    ) in err
    assert runs.calls == []


def test_allow_remote_serves_a_read_server_held_to_loopback_beyond_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", [], loopback_only=True))
    main(server, ["--http", "--host", "0.0.0.0", "--allow-remote"])
    for host in LOOPBACK_HOSTS:
        main(server, ["--http", "--host", host])
    main(server, ["--host", "0.0.0.0"])  # stdio: --host is not used
    assert runs.calls == [
        (server, "streamable-http", {"host": "0.0.0.0", "port": 8000}),
        *[(server, "streamable-http", {"host": host, "port": 8000}) for host in LOOPBACK_HOSTS],
        (server, "stdio", {}),
    ]


def test_the_server_from_apply_options_is_the_one_checked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("example", []))
    write = runs.attach(build_server("example", [create_thing], read_only=False))
    with pytest.raises(SystemExit) as info:
        main(server, ["--http", "--host", "0.0.0.0"], apply_options=lambda args, given: write)
    assert info.value.code == 2
    assert "is a write server" in capsys.readouterr().err
    assert runs.calls == []


def test_the_request_log_is_quiet_when_the_server_from_apply_options_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = build_server("example", [])
    seen: dict[str, int] = {}

    def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
        seen.update({name: logging.getLogger(name).level for name in REQUEST_LOGGERS})

    monkeypatch.setattr(server, "run", fake_run)

    def apply(args: argparse.Namespace, given: MCPServer) -> MCPServer:
        # Something the source does here, building a server another way say, raises it.
        for name in REQUEST_LOGGERS:
            logging.getLogger(name).setLevel(logging.INFO)
        return given

    main(server, [], apply_options=apply)
    assert seen == dict.fromkeys(REQUEST_LOGGERS, logging.WARNING)


# serve_tenants: --<param> binds a multi-tenant source's server to one tenant ----------
# The tests of the two copies' serve commands, sdk-cashctrl's --org and sdk-google-mail's
# --account (ADR-0042, decision 1), on a fictitious source whose variables
# no shell sets.

TENANTS = Tenants(
    "fictive-src",
    list_var="FICTIVE_SRC_TENANTS",
    param="org",
    fields=("SUBDOMAIN", "API_KEY"),
    reserved=("demo",),
    validate={"SUBDOMAIN": lambda value: value if value.isalnum() else _refuse(value)},
)
LOCK = TenantLock(TENANTS, "demo", noun="organisation")
TEXT = "Fictive via xippios."
SENTENCE = (
    "This server is bound to org demo; every tool acts on that organisation and takes no org."
)


def _refuse(value: str) -> str:
    raise ValueError(f"not one label: {value}")


@pytest.fixture
def fictive_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reserved ``demo`` declared with placeholder values, and no other tenant."""
    for name in [name for name in os.environ if name.startswith("FICTIVE_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(TENANTS.var("demo", "SUBDOMAIN"), "placeholder")
    monkeypatch.setenv(TENANTS.var("demo", "API_KEY"), "placeholder")


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[tuple[MCPServer, str, dict[str, Any]]]:
    """Every server ``main`` would have run, the ones ``serve_tenants`` builds included."""
    calls: list[tuple[MCPServer, str, dict[str, Any]]] = []

    def run(self: MCPServer, transport: str = "stdio", **options: Any) -> None:
        calls.append((self, transport, options))

    monkeypatch.setattr(MCPServer, "run", run)
    return calls


async def echo_org(org: str, confirm: bool = False) -> dict[str, str]:
    """Return the organisation the tool was called for.

    Args:
        org: A declared organisation, e.g. ``demo``.
        confirm: Ignored, e.g. ``true``.
    """
    return {"org": org}


async def echo_account(account: str) -> dict[str, str]:
    """Return the account the tool was called for.

    Args:
        account: A declared account, e.g. ``demo``.
    """
    return {"account": account}


async def echo_org_name(org_name: str) -> dict[str, str]:
    """Return the organisation the tool was called for.

    Args:
        org_name: A declared organisation, e.g. ``demo``.
    """
    return {"org_name": org_name}


class Builds:
    """A source's ``build(lock)``: one tool that echoes its tenant, ``echo_org`` by default.

    The tool takes the tenant's parameter that the lock binds, since ``bind_tasks`` refuses
    a task that takes none (https://github.com/xippios/sdk-core/issues/299).
    """

    def __init__(
        self,
        *,
        read_only: bool = True,
        loopback_only: bool = False,
        task: Callable[..., Any] = echo_org,
    ) -> None:
        self.locks: list[TenantLock | None] = []
        self.read_only = read_only
        self.loopback_only = loopback_only
        self.task = task

    def __call__(self, lock: TenantLock | None = None) -> MCPServer:
        self.locks.append(lock)
        return build_server(
            "fictive-src",
            bind_tasks([self.task], lock),
            instructions=tenant_instructions(TEXT, lock),
            read_only=self.read_only,
            loopback_only=self.loopback_only,
        )


@pytest.mark.anyio
@pytest.mark.usefixtures("fictive_demo")
async def test_serve_tenants_binds_the_server_then_hands_over_to_main(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    build = Builds()
    unbound = build()
    argv = ["--host", "127.0.0.1", "--org=demo", "--http", "--port", "9001"]
    serve_tenants(unbound, build, TENANTS, noun="organisation", argv=argv)
    assert build.locks == [None, LOCK]
    ((server, transport, options),) = served
    assert server is not unbound, "the bound server is built anew"
    assert (transport, options) == ("streamable-http", {"host": "127.0.0.1", "port": 9001})
    assert json.loads(await mcp_call_text(server, "fictive_src_echo_org", {})) == {"org": "demo"}
    assert server.instructions == f"{TEXT} {SENTENCE}"


@pytest.mark.usefixtures("fictive_demo")
def test_serve_tenants_without_the_option_serves_the_server_as_built(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    build = Builds()
    unbound = build()
    checked: list[str] = []
    serve_tenants(unbound, build, TENANTS, check=checked.append, argv=[])
    assert served == [(unbound, "stdio", {})]
    assert build.locks == [None]
    assert checked == [], "no tenant, no check"


@pytest.mark.usefixtures("fictive_demo")
def test_an_undeclared_tenant_stops_the_process_before_anything_is_built(
    served: list[tuple[MCPServer, str, dict[str, Any]]], capsys: pytest.CaptureFixture[str]
) -> None:
    build = Builds()
    checked: list[str] = []
    with pytest.raises(SystemExit) as info:
        serve_tenants(build(), build, TENANTS, check=checked.append, argv=["--org", "nope"])
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: unknown tenant 'nope'; declared tenants: demo" in err
    assert "Traceback" not in err
    assert (build.locks, checked, served) == ([None], [], [])


@pytest.mark.usefixtures("fictive_demo")
def test_the_check_is_given_the_declared_tenant_before_the_build(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    build = Builds()
    order: list[str] = []

    def check(name: str) -> None:
        order.append(f"check {name}, built {len(build.locks)}")

    serve_tenants(build(), build, TENANTS, check=check, argv=["--org", "demo"])
    assert order == ["check demo, built 1"], "after the unbound build, before the bound one"
    assert len(served) == 1


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "FICTIVE_SRC_XA_SUBDOMAIN is not set; export the SUBDOMAIN of tenant 'xa'"),
        ("evil.example/x?", "FICTIVE_SRC_XA_SUBDOMAIN does not hold a valid SUBDOMAIN"),
    ],
)
@pytest.mark.usefixtures("fictive_demo")
def test_an_error_of_the_check_stops_the_process_and_names_no_value(
    monkeypatch: pytest.MonkeyPatch,
    served: list[tuple[MCPServer, str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
    value: str | None,
    message: str,
) -> None:
    """sdk-cashctrl's check: the subdomain read as ``client_for`` reads it, at startup."""
    monkeypatch.setenv(TENANTS.list_var, "xa")
    if value is not None:
        monkeypatch.setenv(TENANTS.var("xa", "SUBDOMAIN"), value)
    build = Builds()
    with pytest.raises(SystemExit) as info:
        serve_tenants(
            build(),
            build,
            TENANTS,
            check=lambda name: TENANTS.field(name, "SUBDOMAIN"),
            argv=["--org", "xa"],
        )
    assert info.value.code == 2
    err = capsys.readouterr().err
    assert f"{ENTRY_POINT}: error: {message}" in err
    assert "evil.example" not in err
    assert (build.locks, served) == ([None], [])


SLUG_AND_PREFIX = Tenants(
    "fictive-mail",
    var_prefix="FICTIVE",
    list_var="FICTIVE_ACCOUNTS",
    param="account",
    fields=("REFRESH_TOKEN",),
    reserved=("demo",),
)
PREFIX_AS_SLUG = Tenants(
    "fictive",
    list_var="FICTIVE_ACCOUNTS",
    param="account",
    fields=("REFRESH_TOKEN",),
    reserved=("demo",),
)


@pytest.mark.parametrize(
    "registry", [SLUG_AND_PREFIX, PREFIX_AS_SLUG], ids=["slug-and-prefix", "prefix-as-slug"]
)
@pytest.mark.usefixtures("fictive_demo")
def test_a_registry_under_a_shared_prefix_binds_either_way(
    monkeypatch: pytest.MonkeyPatch,
    served: list[tuple[MCPServer, str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
    registry: Tenants,
) -> None:
    """sdk-google-mail's registry, its prefix apart, binds as the copy's did.

    The command's text names the registry's tenants and variables, never its source, so
    a registry whose slug is its prefix and one that names the prefix apart print the same;
    the registry's name: https://github.com/xippios/sdk-core/issues/279.
    """
    monkeypatch.setenv("FICTIVE_DEMO_REFRESH_TOKEN", "placeholder")
    build = Builds(task=echo_account)
    serve_tenants(build(), build, registry, argv=["--account", "demo"])
    assert build.locks == [None, TenantLock(registry, "demo")]
    with pytest.raises(SystemExit):
        serve_tenants(build(), build, registry, argv=["--account", "nope"])
    assert f"{ENTRY_POINT}: error: unknown tenant 'nope'; declared tenants: demo" in (
        capsys.readouterr().err
    )
    assert len(served) == 1


@pytest.mark.usefixtures("fictive_demo")
def test_the_help_names_the_option_with_its_noun_beside_core_s_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    build = Builds()
    with pytest.raises(SystemExit) as info:
        serve_tenants(build(), build, TENANTS, noun="organisation", argv=["--help"])
    assert info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())  # argparse wraps the help lines
    assert (
        "--org ORG serve only this organisation, e.g. demo; every tool acts on it and takes no org"
    ) in out
    for option in ("--http", "--host", "--port", "--allow-remote"):
        assert option in out


def test_without_a_reserved_tenant_the_help_gives_no_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = Tenants(
        "fictive-src", list_var="FICTIVE_SRC_TENANTS", param="account", fields=("API_KEY",)
    )
    build = Builds()
    with pytest.raises(SystemExit):
        serve_tenants(build(), build, registry, argv=["--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "serve only this account; every tool acts on it and takes no account" in out


@pytest.mark.usefixtures("fictive_demo")
def test_an_underscored_parameter_is_a_hyphenated_option(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    registry = Tenants(
        "fictive-src",
        list_var="FICTIVE_SRC_TENANTS",
        param="org_name",
        fields=("SUBDOMAIN", "API_KEY"),
        reserved=("demo",),
    )
    build = Builds(task=echo_org_name)
    serve_tenants(build(), build, registry, argv=["--org-name", "demo"])
    assert build.locks == [None, TenantLock(registry, "demo")]


@pytest.mark.usefixtures("fictive_demo")
def test_unknown_options_still_fail_with_serve_tenants(
    served: list[tuple[MCPServer, str, dict[str, Any]]], capsys: pytest.CaptureFixture[str]
) -> None:
    build = Builds()
    with pytest.raises(SystemExit) as info:
        serve_tenants(build(), build, TENANTS, argv=["--org", "demo", "--nope"])
    assert info.value.code == 2
    assert "unrecognized arguments: --nope" in capsys.readouterr().err
    assert (build.locks, served) == ([None], [])


@pytest.mark.usefixtures("fictive_demo")
def test_the_option_is_the_parameter_the_registry_declares(
    served: list[tuple[MCPServer, str, dict[str, Any]]], capsys: pytest.CaptureFixture[str]
) -> None:
    """One declaration, ``Tenants(param=...)``: the command names no parameter of its own."""
    build = Builds()
    with pytest.raises(SystemExit):
        serve_tenants(build(), build, TENANTS, argv=["--account", "demo"])
    assert "unrecognized arguments: --account demo" in capsys.readouterr().err
    assert (build.locks, served) == ([None], [])


@pytest.mark.parametrize(
    ("build", "kind"),
    [
        (Builds(read_only=False), "a write server"),
        (Builds(loopback_only=True), "a read server held to loopback"),
    ],
    ids=["write", "loopback-only"],
)
@pytest.mark.usefixtures("fictive_demo")
def test_a_bound_server_stays_held_to_loopback(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
    build: Builds,
    kind: str,
) -> None:
    """``main`` checks the bound server ``build`` returns, as it checks the unbound one."""
    remote = ["--org", "demo", "--http", "--host", "0.0.0.0"]
    with pytest.raises(SystemExit) as info:
        serve_tenants(build(), build, TENANTS, noun="organisation", argv=remote)
    assert info.value.code == 2
    assert f"xippios-fictive-src is {kind} and carries no authentication" in (
        capsys.readouterr().err
    )
    assert served == []
    for argv in ([*remote, "--allow-remote"], ["--org", "demo", "--http"]):
        serve_tenants(build(), build, TENANTS, noun="organisation", argv=argv)
    assert [(options["host"], server.instructions) for server, _, options in served] == [
        ("0.0.0.0", f"{TEXT} {SENTENCE}"),
        ("127.0.0.1", f"{TEXT} {SENTENCE}"),
    ]


@pytest.mark.usefixtures("fictive_demo")
def test_serve_tenants_keeps_request_urls_out_of_the_log(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    build = Builds()
    server = build()
    for name in REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET)
    serve_tenants(server, build, TENANTS, argv=["--org", "demo"])
    assert [logging.getLogger(name).level for name in REQUEST_LOGGERS] == [logging.WARNING] * 4


class ToolSetBuilds:
    """A source's ``build(lock)`` that returns its tool set, as the package contract has it."""

    def __init__(self, *, read_only: bool = True, loopback_only: bool = False) -> None:
        self.locks: list[TenantLock | None] = []
        self.read_only = read_only
        self.loopback_only = loopback_only

    def __call__(self, lock: TenantLock | None = None) -> ToolSet:
        self.locks.append(lock)
        return ToolSet(
            "fictive-src",
            bind_tasks([echo_org], lock),
            instructions=tenant_instructions(TEXT, lock),
            version="0.4.0",
            read_only=self.read_only,
            loopback_only=self.loopback_only,
        )


@pytest.mark.anyio
@pytest.mark.usefixtures("fictive_demo")
async def test_serve_tenants_builds_the_bound_server_from_the_tool_set_build_returns(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
) -> None:
    # Finding 2 of https://github.com/xippios/sdk-core/pull/288: a multi-tenant source's
    # build(lock) returns its tool set, and its entry point stays serve_tenants(server,
    # build, TENANTS, ...), as sdk-cashctrl and sdk-google-mail write it.
    build = ToolSetBuilds()
    unbound = build_server(build(), name="xippios-fictive-src-write")
    serve_tenants(unbound, build, TENANTS, noun="organisation", argv=["--org=demo"])
    assert build.locks == [None, LOCK]
    ((server, transport, _),) = served
    assert server is not unbound, "the bound server is built anew"
    assert (server.name, server.version, transport) == (
        "xippios-fictive-src-write",
        "0.4.0",
        "stdio",
    )
    assert server.instructions == f"{TEXT} {SENTENCE}"
    tool = {t.name: t for t in await server.list_tools()}["fictive_src_echo_org"]
    assert "org" not in tool.input_schema["properties"]
    assert json.loads(await mcp_call_text(server, "fictive_src_echo_org", {})) == {"org": "demo"}


@pytest.mark.parametrize(
    ("build", "kind"),
    [
        (ToolSetBuilds(read_only=False), "a write server"),
        (ToolSetBuilds(loopback_only=True), "a read server held to loopback"),
    ],
    ids=["write", "loopback-only"],
)
@pytest.mark.usefixtures("fictive_demo")
def test_a_server_bound_from_a_tool_set_stays_held_to_loopback(
    served: list[tuple[MCPServer, str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
    build: ToolSetBuilds,
    kind: str,
) -> None:
    remote = ["--org", "demo", "--http", "--host", "0.0.0.0"]
    with pytest.raises(SystemExit) as info:
        serve_tenants(build_server(build()), build, TENANTS, argv=remote)
    assert info.value.code == 2
    assert f"xippios-fictive-src is {kind} and carries no authentication" in (
        capsys.readouterr().err
    )
    assert served == []
