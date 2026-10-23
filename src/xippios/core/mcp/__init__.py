"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` is a handful of lines::

    from xippios.core.mcp import build_server, main
    from xippios.usda_nass import tasks

    server = build_server("usda-nass", [tasks.get_series, tasks.list_commodities])

    def run() -> None:
        main(server)

A multi-tenant source adds ``--org`` and locks the server to one tenant (ADR-0014)::

    def run() -> None:
        main(
            server,
            add_options=lambda parser: parser.add_argument("--org"),
            apply_options=lambda args, server: server if args.org is None else build_server(
                "cashctrl", TASKS, tenant_lock=TenantLock("org", tenants.require(args.org))
            ),
        )

Requires the ``mcp`` extra: ``uv add "xippios-core[mcp]"``.
"""

try:
    import mcp.server.mcpserver  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError("xippios.core.mcp needs the 'mcp' extra: uv add 'xippios-core[mcp]'") from exc

from xippios.core.mcp.cli import build_parser, main
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import ResultCap, cap_result
from xippios.core.mcp.server import (
    TenantLock,
    build_server,
    is_write_server,
    quiet_request_logging,
    register_tasks,
    tool_name,
)

__all__ = [
    "ResultCap",
    "TenantLock",
    "build_parser",
    "build_server",
    "cap_result",
    "error_to_text",
    "is_write_server",
    "main",
    "quiet_request_logging",
    "register_tasks",
    "tool_name",
]
