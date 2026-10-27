"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` is a handful of lines::

    from xippios.core.mcp import build_server, main
    from xippios.usda.nass import tasks

    server = build_server("usda-nass", [tasks.get_series, tasks.list_commodities])

    def run() -> None:
        main(server)

A multi-tenant source adds ``--org`` and locks the server to one tenant (ADR-0014)::

    def lock(args: argparse.Namespace, server: MCPServer) -> MCPServer:
        if args.org is None:
            return server
        org = tenants.require(args.org)  # undeclared: exit status 2
        tenants.field(org, "SUBDOMAIN")  # missing or malformed: exit status 2
        return build_server("cashctrl", TASKS, tenant_lock=TenantLock("org", org))

    def run() -> None:
        main(server, add_options=lambda parser: parser.add_argument("--org"), apply_options=lock)

``ResultCap`` is defined in ``xippios.core.models`` and exported from ``xippios.core``
too, so a source's ``tasks.py`` declares its caps without this extra; it is re-exported
here for the sources that import it from this package. ``register_tasks``,
``is_write_server`` and ``quiet_request_logging``, which ``build_server`` and ``main``
call, are importable from ``xippios.core.mcp.server``.

Requires the ``mcp`` extra: ``uv add "xippios-core[mcp]"``.
"""

try:
    import mcp.server.mcpserver  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError("xippios.core.mcp needs the 'mcp' extra: uv add 'xippios-core[mcp]'") from exc

from xippios.core.mcp.cli import build_parser, main
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.server import TenantLock, build_server, tool_name
from xippios.core.models import ResultCap

__all__ = [
    "ResultCap",
    "TenantLock",
    "build_parser",
    "build_server",
    "cap_result",
    "error_to_text",
    "main",
    "tool_name",
]
