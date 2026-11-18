"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` is a handful of lines::

    from xippios.core.mcp import build_server, main, tool_functions
    from xippios.usda.nass import tasks

    server = build_server("usda-nass", tool_functions(tasks))

    def run() -> None:
        main(server)

``tool_functions(tasks)`` is ``tasks.__all__`` minus ``BULK_TASKS``, read from the module
it is given, each name its function's ``__name__``.

A source's own command-line options reach ``main`` through two hooks, parsed once with
core's: ``add_options`` puts them on the parser, ``apply_options`` returns the server to
run, and a ``XippiosError`` it raises stops the process with exit status 2 (ADR-0036).
A multi-tenant source runs ``serve_tenants`` instead, whose ``--org acme`` serves the
server bound to one tenant (``xippios.core.TenantLock``).

The package contract's tool set, ``ToolSet``, is what a source's ``build(**options)``
returns: its tasks as its lock binds them, its caps, instructions and version, its option
hooks, and whether it writes and is held to loopback. ``build_server(tool_set)`` builds
the source's server from it, and a host builds one server from several with
``register_tasks(server, tool_set)`` and applies each one's hooks with
``option_defaults()`` (ADR-0026, amendment 2026-11-18, points c and d).

``ResultCap`` is defined in ``xippios.core.models`` and exported from ``xippios.core``
too, so a source's ``tasks.py`` declares its caps without this extra; it is re-exported
here for the sources that import it from this package. A host that builds its servers
itself imports ``register_tasks``, ``is_write_server``, ``quiet_request_logging`` and
``tool_functions``, and, to hold a server to loopback as ``main`` does,
``is_loopback_only`` and ``LOOPBACK_HOSTS``: ``build_server(..., loopback_only=True)``
holds a read server there as a write server is held (ADR-0025, D-a; ADR-0026).

Requires the ``mcp`` extra: ``uv add "xippios-core[mcp]"``.
"""

try:
    import mcp.server.mcpserver  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError("xippios.core.mcp needs the 'mcp' extra: uv add 'xippios-core[mcp]'") from exc

from xippios.core.mcp.cli import LOOPBACK_HOSTS, build_parser, main, serve_tenants
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.server import (
    build_server,
    is_loopback_only,
    is_write_server,
    quiet_request_logging,
    register_tasks,
    tool_functions,
    tool_name,
)
from xippios.core.mcp.toolset import ToolSet
from xippios.core.models import ResultCap

__all__ = [
    "LOOPBACK_HOSTS",
    "ResultCap",
    "ToolSet",
    "build_parser",
    "build_server",
    "cap_result",
    "error_to_text",
    "is_loopback_only",
    "is_write_server",
    "main",
    "quiet_request_logging",
    "register_tasks",
    "serve_tenants",
    "tool_functions",
    "tool_name",
]
