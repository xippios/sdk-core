"""The body of every MCP entry point: stdio by default, ``--http`` opt-in.

The entry points are ``xippios-<source>-mcp`` for a read-only source, and
``xippios-<source>-mcp-read`` and ``xippios-<source>-mcp-write`` for a source with a
write server (conventions §8, ADR-0026); the usage line names the one that runs.

A source adds its own options through two hooks instead of parsing the command line a
second time: ``add_options`` puts them on core's parser, so ``--help`` lists every
option and a typo fails as usual, and ``apply_options`` turns the parsed options into
the server to run (ADR-0014, decision 8).
"""

import argparse
from collections.abc import Callable, Sequence

from mcp.server.mcpserver import MCPServer

from xippios.core.errors import XippiosError
from xippios.core.mcp.server import is_loopback_only, is_write_server, quiet_request_logging

__all__ = ["LOOPBACK_HOSTS", "build_parser", "main"]

# Exactly the mcp SDK's own list (mcp 2.3.0, mcp/server/lowlevel/server.py and
# mcp/server/mcpserver/server.py): for these hosts, without transport_security, the SDK
# turns on its DNS-rebinding protection (Host and Origin checks). Every host a server held
# to loopback is served on without --allow-remote therefore gets those checks too, which
# is why the match is exact: another loopback address such as 127.0.0.2 would not get them.
LOOPBACK_HOSTS: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
"""The ``--host`` values a server held to loopback (``is_loopback_only``) is served on
over HTTP without ``--allow-remote``; a host that serves such a server itself binds one
of them too (ADR-0026, decision 5)."""


def _held(server: MCPServer) -> str | None:
    """What ``server`` is, as a refusal names it, when it is held to loopback; else ``None``."""
    if is_write_server(server):
        return "a write server"
    if is_loopback_only(server):
        return "a read server held to loopback"
    return None


def _allow_remote_help(server: MCPServer | None) -> str:
    """The help of ``--allow-remote``, naming the kind of ``server`` when it is given."""
    if server is None:
        return (
            "serve a write server, or a read server built with loopback_only=True, beyond "
            "loopback; it carries no authentication, put it behind a gateway"
        )
    if _held(server) is None:
        return "changes nothing: this read server is not held to loopback"
    kind = "write" if is_write_server(server) else "read"
    return (
        f"serve this {kind} server beyond loopback; it carries no authentication, put it "
        "behind a gateway"
    )


def build_parser(
    prog: str | None = None,
    *,
    server: MCPServer | None = None,
    add_options: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.ArgumentParser:
    """The command line accepted by ``main``: core's options, then the source's.

    Args:
        prog: Program name shown in usage and errors, e.g. ``"xippios-cashctrl-mcp-read"``;
            defaults to argparse's, the name of the script that runs, the entry point.
        server: The server to run, whose kind the help of ``--allow-remote`` names; the
            help names both kinds that are held to loopback without it.
        add_options: Adds the source's arguments to the parser, e.g.
            ``lambda parser: parser.add_argument("--org", help="...")``.
    """
    parser = argparse.ArgumentParser(prog=prog, description="Run the MCP server.")
    parser.add_argument(
        "--http", action="store_true", help="serve streamable HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address for --http")
    parser.add_argument("--port", type=int, default=8000, help="port for --http")
    parser.add_argument("--allow-remote", action="store_true", help=_allow_remote_help(server))
    if add_options is not None:
        add_options(parser)
    return parser


def main(
    server: MCPServer,
    argv: Sequence[str] | None = None,
    *,
    add_options: Callable[[argparse.ArgumentParser], None] | None = None,
    apply_options: Callable[[argparse.Namespace, MCPServer], MCPServer] | None = None,
) -> None:
    """Parse ``argv`` once and run the server on stdio or streamable HTTP.

    ``apply_options(namespace, server)`` returns the server to run; a ``XippiosError``
    it raises (an option value the source refuses is an ``InvalidRequestError``, a
    missing variable a ``ConfigError``) stops the process like an argparse error: the
    message on stderr, exit status 2, no traceback. A server held to loopback
    (``is_loopback_only``), a write server or a read server built with
    ``loopback_only=True``, is served over ``--http`` on a loopback ``--host`` only
    (``LOOPBACK_HOSTS``: ``127.0.0.1``, ``localhost``, ``::1``), unless
    ``--allow-remote`` is passed: it carries no authentication. On any other read server
    ``--allow-remote`` changes nothing. The usage line and the errors name the entry
    point that runs, ``sys.argv[0]``, since ``server.name`` is one slug for a source's
    read and write servers.

    The request loggers are quieted again right before the server runs
    (``quiet_request_logging``), in case the server was built another way or a level was
    raised in between.

    Args:
        server: A server from ``build_server``.
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.
        add_options: Adds the source's arguments to core's parser (see ``build_parser``).
        apply_options: Builds the server to run from the parsed options, e.g. one built
            anew for an option of the source's; returns ``server`` itself when there is
            nothing to change.
    """
    parser = build_parser(server=server, add_options=add_options)
    args = parser.parse_args(argv)
    if apply_options is not None:
        try:
            server = apply_options(args, server)
        except XippiosError as exc:
            parser.error(str(exc))
    held = _held(server)
    remote = args.http and args.host not in LOOPBACK_HOSTS
    if held is not None and remote and not args.allow_remote:
        parser.error(
            f"{server.name} is {held} and carries no authentication; serve it over "
            f"--http on a loopback --host ({', '.join(LOOPBACK_HOSTS)}), or pass "
            "--allow-remote and put it behind a gateway"
        )
    quiet_request_logging()
    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
