"""The body of every ``xippios-<source>-mcp`` entry point: stdio by default, ``--http`` opt-in.

A source adds its own options through two hooks instead of parsing the command line a
second time: ``add_options`` puts them on core's parser, so ``--help`` lists every
option and a typo fails as usual, and ``apply_options`` turns the parsed options into
the server to run, a server locked to one tenant for instance (ADR-0014).
"""

import argparse
from collections.abc import Callable, Sequence

from mcp.server.mcpserver import MCPServer

from xippios.core.errors import XippiosError
from xippios.core.mcp.server import is_write_server, quiet_request_logging

__all__ = ["build_parser", "main"]

_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
"""The ``--host`` values a write server may be served on over HTTP without ``--allow-remote``."""

_ALLOW_REMOTE_HELP = (
    "serve a write server beyond loopback; it carries no authentication, put it behind a gateway"
)


def build_parser(
    prog: str, *, add_options: Callable[[argparse.ArgumentParser], None] | None = None
) -> argparse.ArgumentParser:
    """The command line accepted by ``main``: core's options, then the source's.

    Args:
        prog: Program name shown in usage and errors, e.g. ``"xippios-cashctrl"``.
        add_options: Adds the source's arguments to the parser, e.g.
            ``lambda parser: parser.add_argument("--org", help="...")``.
    """
    parser = argparse.ArgumentParser(prog=prog, description="Run the MCP server.")
    parser.add_argument(
        "--http", action="store_true", help="serve streamable HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address for --http")
    parser.add_argument("--port", type=int, default=8000, help="port for --http")
    parser.add_argument("--allow-remote", action="store_true", help=_ALLOW_REMOTE_HELP)
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
    it raises (an undeclared tenant is an ``InvalidRequestError``, a missing variable a
    ``ConfigError``) stops the process like an argparse error: the message on stderr,
    exit status 2, no traceback. A write server (``is_write_server``) is served over
    ``--http`` on a loopback ``--host`` only (``127.0.0.1``, ``localhost``, ``::1``),
    unless ``--allow-remote`` is passed: it carries no authentication.

    The httpx and httpcore loggers are quieted again right before the server runs
    (``quiet_request_logging``), in case the server was built another way or a level was
    raised in between.

    Args:
        server: A server from ``build_server``.
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.
        add_options: Adds the source's arguments to core's parser (see ``build_parser``).
        apply_options: Builds the server to run from the parsed options, e.g. one with
            ``tenant_lock=TenantLock("org", namespace.org)`` when ``--org`` was given;
            returns ``server`` itself when there is nothing to change.
    """
    parser = build_parser(server.name, add_options=add_options)
    args = parser.parse_args(argv)
    if apply_options is not None:
        try:
            server = apply_options(args, server)
        except XippiosError as exc:
            parser.error(str(exc))
    remote = args.http and args.host not in _LOOPBACK_HOSTS
    if remote and is_write_server(server) and not args.allow_remote:
        parser.error(
            f"{server.name} is a write server and carries no authentication; serve it over "
            f"--http on a loopback --host ({', '.join(_LOOPBACK_HOSTS)}), or pass "
            "--allow-remote and put it behind a gateway"
        )
    quiet_request_logging()
    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
