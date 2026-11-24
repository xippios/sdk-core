"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` builds its ``ToolSet`` and its server from it::

    from xippios.core.mcp import ToolSet, build_server, main, tool_functions
    from xippios.example import tasks

    def build() -> ToolSet:
        return ToolSet("example", tool_functions(tasks), caps=tasks.MCP_CAPS)

    server = build_server(build())

    def run() -> None:
        main(server)

``tool_functions(tasks)`` is ``tasks.__all__`` minus ``BULK_TASKS``, read from the module
it is given, each name its function's ``__name__``; it and ``tool_name`` come from
``xippios.core`` too, since neither needs this extra.

A source's own command-line options reach ``main`` through two hooks, parsed once with
core's: ``add_options`` puts them on the parser, ``apply_options`` returns the server to
run, and a ``XippiosError`` it raises stops the process with exit status 2 (ADR-0036).
A multi-tenant source runs ``serve_tenants`` instead, whose ``--org acme`` serves the
server bound to one tenant (``xippios.core.TenantLock``).

The package contract's tool set, ``ToolSet``, is what a source's ``build(**options)``
returns: its tools as its lock binds them, its caps, instructions and version, its option
hooks, and whether it writes and is held to loopback, all checked when it is built.
``build_server(tool_set)`` builds the source's server from it, and a host builds one
server from several with ``register_tasks(server, tool_set)`` and applies each one's hooks
with ``option_defaults()`` (ADR-0063, decisions 1 and 3).

``ResultCap`` is defined in ``xippios.core.models`` and exported from ``xippios.core``
too, so a source's ``tasks.py`` declares its caps without this extra; it is re-exported
here for the sources that import it from this package. A host such as xippios-mcp
imports ``ToolSet``, ``build_server``, ``register_tasks``, ``LOOPBACK_HOSTS`` and
``quiet_request_logging`` from here, and reads whether a tool set writes or is held to
loopback from its ``read_only`` and ``loopback_only`` (ADR-0063, decision 4).

Requires the ``mcp`` extra: ``uv add "xippios-core[mcp]"``.
"""

try:
    import mcp.server.mcpserver  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError("xippios.core.mcp needs the 'mcp' extra: uv add 'xippios-core[mcp]'") from exc

from xippios.core._tasks import tool_functions, tool_name
from xippios.core.mcp.cli import LOOPBACK_HOSTS, build_parser, main, serve_tenants
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.server import build_server, quiet_request_logging, register_tasks
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
    "main",
    "quiet_request_logging",
    "register_tasks",
    "serve_tenants",
    "tool_functions",
    "tool_name",
]
