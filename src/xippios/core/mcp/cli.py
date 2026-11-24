"""The one entry of every MCP server: stdio by default, ``--http`` opt-in (ADR-0063, decision 7).

The entry points are ``xippios-<source>-mcp`` for a read-only source, and
``xippios-<source>-mcp-read`` and ``xippios-<source>-mcp-write`` for a source with a
write server (conventions §8, ADR-0026); the usage line names the one that runs.

``main(build)`` takes the package's ``build``, reads the two option hooks from the tool set
that it returns, so a source's options are parsed once with core's and ``--help`` lists
them, builds the server that it runs and, given ``tenants``, binds it to the tenant that
``--<param>`` names (ADR-0036, decision 8).
"""

import argparse
from collections.abc import Callable, Sequence

from xippios.core.errors import XippiosError
from xippios.core.mcp.server import build_server, quiet_request_logging
from xippios.core.mcp.toolset import ToolSet
from xippios.core.tenants import TenantLock, Tenants

__all__ = ["LOOPBACK_HOSTS", "build_parser", "main"]

# Exactly the mcp SDK's own list (mcp 2.3.0, mcp/server/lowlevel/server.py and
# mcp/server/mcpserver/server.py): for these hosts, without transport_security, the SDK
# turns on its DNS-rebinding protection (Host and Origin checks). Every host a server held
# to loopback is served on without --allow-remote therefore gets those checks too, which
# is why the match is exact: another loopback address such as 127.0.0.2 would not get them.
LOOPBACK_HOSTS: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
"""The ``--host`` values a server held to loopback is served on over HTTP without
``--allow-remote``, one built from a tool set that writes or is ``loopback_only``; a host
that serves such a tool set itself binds one of them too (ADR-0026, decision 5)."""

_ALLOW_REMOTE_HELP = (
    "serve a write server, or a read server held to loopback, beyond loopback; it carries "
    "no authentication, put it behind a gateway"
)


def _held(tool_set: ToolSet) -> str | None:
    """What the server of ``tool_set`` is, as a refusal names it, when it is held to loopback.

    A tool set that writes or is ``loopback_only`` holds its server there (ADR-0063,
    decision 5); ``None`` for any other.
    """
    if not tool_set.read_only:
        return "a write server"
    return "a read server held to loopback" if tool_set.loopback_only else None


def build_parser(
    prog: str | None = None,
    *,
    add_options: Callable[[argparse.ArgumentParser], None] | None = None,
) -> argparse.ArgumentParser:
    """The command line accepted by ``main``: core's options, then the source's.

    Args:
        prog: Program name shown in usage and errors, e.g. ``"xippios-example-mcp-read"``;
            defaults to argparse's, the name of the script that runs, the entry point.
        add_options: Adds the source's arguments to the parser, e.g. a tool set's
            ``add_options``, ``lambda parser: parser.add_argument("--split-years", ...)``.
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


def _add_tenant(parser: argparse.ArgumentParser, tenants: Tenants) -> None:
    """Put ``--<param>`` on ``parser``, the registry's ``param`` with ``_`` written ``-``."""
    param = tenants.param
    word = param if tenants.noun is None else tenants.noun
    example = f", e.g. {tenants.reserved[0]}" if tenants.reserved else ""
    parser.add_argument(
        f"--{param.replace('_', '-')}",
        dest=param,
        help=f"serve only this {word}{example}; every tool acts on it and takes no {param}",
    )


def main(
    build: Callable[..., ToolSet],
    *,
    tenants: Tenants | None = None,
    check: Callable[[str], object] | None = None,
    argv: Sequence[str] | None = None,
) -> None:
    """Run the server of the package's tool set on stdio or streamable HTTP.

    ``build()`` gives the tool set, whose ``add_options`` puts the source's options on
    core's parser, so ``argv`` is parsed once and ``--help`` lists every option, and whose
    ``apply_options`` is handed the parsed options. A ``XippiosError`` it raises (an option
    value the source refuses is an ``InvalidRequestError``, a missing variable a
    ``ConfigError``) stops the process like an argparse error: the message on stderr, exit
    status 2, no traceback, nothing served.

    Given ``tenants``, the source's registry, ``main`` puts ``--<param>`` on the parser,
    ``param`` the one the registry declares and ``_`` written ``-``, its help naming the
    registry's ``noun``. Given ``--org acme``, it checks the tenant as a call would,
    declared (``tenants.require``) and then by ``check``, and runs the server of
    ``build(TenantLock(tenants, "acme"))``: every tool acts on ``acme`` and takes no
    ``org``. An undeclared name, or an error ``check`` raises, stops the process the same
    way before the bound tool set is built. Without the option it runs the server of
    ``build()``, for every tenant the environment declares.

    The server is ``build_server(tool_set)``, named ``xippios-<source>`` for a source's
    read and write servers alike, so the usage line and the errors name the entry point
    that runs, ``sys.argv[0]``. A tool set that writes or is ``loopback_only`` is served
    over ``--http`` on a loopback ``--host`` only (``LOOPBACK_HOSTS``: ``127.0.0.1``,
    ``localhost``, ``::1``), unless ``--allow-remote`` is passed: it carries no
    authentication. On any other ``--allow-remote`` changes nothing. The request loggers
    are quieted again right before the server runs (``quiet_request_logging``).

    A source's entry point is one line of its rendered ``mcp.py``::

        def run() -> None:
            main(build)  # a multi-tenant source: main(build, tenants=TENANTS, check=check_org)

    Args:
        build: The package's ``build``, which returns its ``ToolSet``; called without
            arguments, and with the lock alone where ``tenants`` binds a tenant.
        tenants: The source's registry, e.g. ``TENANTS``, whose ``param`` names the option,
            ``"org"`` for ``--org``; ``None`` for a source without tenants.
        check: Called with the declared tenant's name before the bound tool set is built,
            e.g. ``lambda name: TENANTS.field(name, "SUBDOMAIN")``, which reads the value
            as the tenant's client would; a ``XippiosError`` it raises, naming a variable
            and never its value, stops the process. ``None`` checks nothing more.
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.

    Raises:
        TypeError: ``build`` is no function, a server say, or returns no ``ToolSet``.
    """
    if not callable(build):
        raise TypeError(
            "main takes the package's build, e.g. main(build), not its server; build "
            "returns the package's ToolSet"
        )
    tool_set = build()
    if not isinstance(tool_set, ToolSet):
        raise TypeError(
            f"build returns the package's ToolSet; it returned {type(tool_set).__name__}"
        )
    parser = build_parser(add_options=tool_set.add_options)
    if tenants is not None:
        _add_tenant(parser, tenants)
    args = parser.parse_args(argv)
    try:
        if tool_set.apply_options is not None:
            tool_set.apply_options(args)
        name = None if tenants is None else getattr(args, tenants.param)
        if tenants is not None and name is not None:
            tenants.require(name)
            if check is not None:
                check(name)
            tool_set = build(TenantLock(tenants, name))
    except XippiosError as exc:
        parser.error(str(exc))
    server = build_server(tool_set)
    held = _held(tool_set)
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
