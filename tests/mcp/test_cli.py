import argparse
import logging
import os
from typing import Any

import pytest
from mcp.server.mcpserver import MCPServer

from xippios.core import ConfigError, InvalidRequestError, Tenants, XippiosError
from xippios.core.mcp import TenantLock, build_parser, build_server, main


def test_parser_defaults() -> None:
    args = build_parser("x").parse_args([])
    assert (args.http, args.host, args.port) == (False, "127.0.0.1", 8000)


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
        seen.update({name: logging.getLogger(name).level for name in ("httpx", "httpcore")})

    monkeypatch.setattr(server, "run", fake_run)
    # Something between build_server and main puts the request log back on.
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    main(server, [])
    assert seen == {"httpx": logging.WARNING, "httpcore": logging.WARNING}


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
    locked = runs.attach(build_server("example", [], tenant_lock=TenantLock("org", "acme")))
    seen: list[argparse.Namespace] = []

    def apply(args: argparse.Namespace, given: MCPServer) -> MCPServer:
        assert given is server
        seen.append(args)
        return given if args.org is None else locked

    main(
        server,
        ["--org", "acme", "--http", "--port", "9001"],
        add_options=add_org,
        apply_options=apply,
    )
    main(server, ["--http"], add_options=add_org, apply_options=apply)
    assert [args.org for args in seen] == ["acme", None]
    assert runs.calls == [
        (locked, "streamable-http", {"host": "127.0.0.1", "port": 9001}),
        (server, "streamable-http", {"host": "127.0.0.1", "port": 8000}),
    ]


def test_help_lists_core_and_source_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(build_server("example", []), ["--help"], add_options=add_org)
    assert info.value.code == 0
    out = capsys.readouterr().out
    for option in ("--http", "--host", "--port", "--org"):
        assert option in out


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
    assert f"xippios-example: error: {message}" in err
    assert "Traceback" not in err
    assert runs.calls == []


def test_an_undeclared_tenant_from_tenants_require_stops_at_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in [name for name in os.environ if name.startswith("FICTIVE_CLI_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FICTIVE_CLI_TENANTS", "acme")
    tenants = Tenants("fictive-cli", list_var="FICTIVE_CLI_TENANTS", fields=["SUBDOMAIN"])
    runs = Runs(monkeypatch)
    server = runs.attach(build_server("fictive-cli", []))

    def apply(args: argparse.Namespace, given: MCPServer) -> MCPServer:
        lock = TenantLock("org", tenants.require(args.org))
        return runs.attach(build_server("fictive-cli", [], tenant_lock=lock))

    with pytest.raises(SystemExit) as info:
        main(server, ["--org", "nope"], add_options=add_org, apply_options=apply)
    assert info.value.code == 2
    assert "unknown tenant 'nope'; declared tenants: acme" in capsys.readouterr().err
    main(server, ["--org", "acme"], add_options=add_org, apply_options=apply)
    [(served, transport, _)] = runs.calls
    assert served is not server
    assert transport == "stdio"
    assert served.instructions == (
        "This server is locked to org acme; every tool call must pass org=acme."
    )
