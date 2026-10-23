"""The body of every ``xippios-<source>-mcp`` entry point: stdio by default, ``--http`` opt-in."""

import argparse
from collections.abc import Sequence

from mcp.server.mcpserver import MCPServer

from xippios.core.mcp.server import quiet_request_logging

__all__ = ["build_parser", "main"]


def build_parser(prog: str) -> argparse.ArgumentParser:
    """The command line accepted by ``main``."""
    parser = argparse.ArgumentParser(prog=prog, description="Run the MCP server.")
    parser.add_argument(
        "--http", action="store_true", help="serve streamable HTTP instead of stdio"
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind address for --http")
    parser.add_argument("--port", type=int, default=8000, help="port for --http")
    return parser


def main(server: MCPServer, argv: Sequence[str] | None = None) -> None:
    """Parse ``argv`` and run ``server`` on stdio or streamable HTTP.

    Quiets the httpx and httpcore loggers again first (``quiet_request_logging``), in
    case the server was built another way or a level was raised in between.

    Args:
        server: A server from ``build_server``.
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.
    """
    quiet_request_logging()
    args = build_parser(server.name).parse_args(argv)
    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
