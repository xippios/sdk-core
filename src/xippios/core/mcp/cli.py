"""The body of every MCP entry point: stdio by default, ``--http`` opt-in.

The entry points are ``xippios-<source>-mcp`` for a read-only source, and
``xippios-<source>-mcp-read`` and ``xippios-<source>-mcp-write`` for a source with a
write server (conventions §8, ADR-0026); the usage line names the one that runs.

A source adds its own options through two hooks instead of parsing the command line a
second time: ``add_options`` puts them on core's parser, so ``--help`` lists every
option and a typo fails as usual, and ``apply_options`` turns the parsed options into
the server to run (ADR-0036, decision 8). ``serve_tenants`` is those hooks for a
multi-tenant source: ``--org acme`` serves the server bound to one tenant.
"""

import argparse
from collections.abc import Callable, Sequence

from mcp.server.mcpserver import MCPServer

from xippios.core.errors import XippiosError
from xippios.core.mcp.server import (
    build_server,
    is_loopback_only,
    is_write_server,
    quiet_request_logging,
)
from xippios.core.mcp.toolset import ToolSet
from xippios.core.tenants import TenantLock, Tenants

__all__ = ["LOOPBACK_HOSTS", "build_parser", "main", "serve_tenants"]

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


def serve_tenants(
    server: MCPServer,
    build: Callable[[TenantLock | None], ToolSet | MCPServer],
    tenants: Tenants,
    *,
    param: str,
    noun: str | None = None,
    check: Callable[[str], object] | None = None,
    argv: Sequence[str] | None = None,
) -> None:
    """Run a multi-tenant source's server, or the one ``--<param>`` binds, through ``main``.

    The serve command of sdk-cashctrl's ``--org`` and sdk-google-mail's ``--account``
    (ADR-0036, decision 8). It puts ``--<param>`` on core's parser, ``_``
    written ``-``, so ``--help`` lists it beside core's options. Given ``--org acme``, it
    checks the tenant as a call would, declared (``tenants.require``) and then by
    ``check``, and runs the server of ``build(TenantLock(param, "acme", noun=noun))``, built
    anew: every tool acts on ``acme`` and takes no ``org``. A ``build`` that returns its
    ``ToolSet``, as a source's ``build(**options)`` does under the package contract, has
    the bound server built from it with ``build_server``, named as ``server`` is (ADR-0026,
    amendment 2026-11-18, point d); one that returns a server has that server run. An
    undeclared name, or an error ``check`` raises, stops the process with exit status 2
    and the message, before the bound server is built or anything is served. Without the
    option it runs ``server`` as built, for every tenant the environment declares.
    ``main`` then applies its loopback rule to the server it runs, bound or not, and
    quiets the request log.

    A source's entry point is one line, ``build`` returning its tool set and ``server``
    being ``build_server(build())``::

        def run() -> None:
            serve_tenants(server, build, TENANTS, param="org", noun="organisation")

    Args:
        server: The source's server for every declared tenant, ``build_server(build())``.
        build: Builds the source's tool set, bound to the lock it is given or, given
            ``None``, unbound, with ``bind_tasks`` and ``tenant_instructions``; or the
            source's server so bound.
        tenants: The source's registry, e.g. ``TENANTS``; its messages name its tenants
            and variables, never its source or a value.
        param: The task parameter that names the tenant, e.g. ``"org"`` for ``--org``.
        noun: The word for one tenant, e.g. ``"organisation"``, in the option's help and
            the lock's sentence; ``None`` uses ``param``.
        check: Called with the declared tenant's name before the bound server is built,
            e.g. ``lambda name: TENANTS.field(name, "SUBDOMAIN")``, which reads the value
            as the tenant's client would; a ``XippiosError`` it raises, naming a variable
            and never its value, stops the process. ``None`` checks nothing more.
        argv: Arguments without the program name; defaults to ``sys.argv[1:]``.

    Raises:
        ValueError: ``param`` is not a parameter name, before anything is parsed.
    """
    if not param.isidentifier():
        raise ValueError("param must be a parameter name such as 'org'")
    word = param if noun is None else noun
    example = f", e.g. {tenants.reserved[0]}" if tenants.reserved else ""
    help_text = f"serve only this {word}{example}; every tool acts on it and takes no {param}"

    def add_tenant(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(f"--{param.replace('_', '-')}", dest=param, help=help_text)

    def bound(namespace: argparse.Namespace, unbound: MCPServer) -> MCPServer:
        name = getattr(namespace, param)
        if name is None:
            return unbound
        tenants.require(name)
        if check is not None:
            check(name)
        built = build(TenantLock(param, name, noun=noun))
        if isinstance(built, ToolSet):
            return build_server(built, name=unbound.name)
        return built

    main(server, argv, add_options=add_tenant, apply_options=bound)
