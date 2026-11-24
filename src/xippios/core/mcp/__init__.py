"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` builds its ``ToolSet`` from its tasks module, its server from the
tool set, and runs the server through the one entry::

    from xippios.core.mcp import ToolSet, build_server, main
    from xippios.example import tasks

    def build() -> ToolSet:
        return ToolSet.from_tasks("example", tasks, version="1.2.0")

    server = build_server(build())

    def run() -> None:
        main(build)

``ToolSet.from_tasks`` reads the tasks module: ``tool_functions(tasks)``, which is
``tasks.__all__`` minus ``BULK_TASKS``, and what the module declares for the server,
``MCP_CAPS``, ``MCP_INSTRUCTIONS``, the two option hooks ``mcp_add_options`` and
``mcp_apply_options``, and ``MCP_LOOPBACK_ONLY`` (ADR-0063, decision 7). ``tool_functions``
and ``tool_name`` come from ``xippios.core`` too, since neither needs this extra.

``main(build)`` reads the option hooks from the tool set, so a source's options are parsed
once with core's, and a ``XippiosError`` that ``apply_options`` raises stops the process
with exit status 2 (ADR-0036). A multi-tenant source passes its registry,
``main(build, tenants=TENANTS)``, whose ``--org acme`` serves the server bound to one
tenant (``xippios.core.TenantLock``).

The package contract's tool set, ``ToolSet``, is what a source's ``build(**options)``
returns: its tools as its lock binds them, its caps, instructions and version, its option
hooks, and whether it writes and is held to loopback, all checked when it is built.
``build_server(tool_set)`` builds the source's server from it, and a host builds one
server from several with ``register_tasks(server, tool_set)`` and applies each one's hooks
with ``option_defaults()`` (ADR-0063, decisions 1 and 3).

``ResultCap`` is defined in ``xippios.core.models`` and exported from ``xippios.core``
alone, so a source's ``tasks.py`` declares its caps without this extra; this package does
not export it (https://github.com/xippios/sdk-core/issues/475). A host such as xippios-mcp
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
from xippios.core.mcp.cli import LOOPBACK_HOSTS, build_parser, main
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.server import build_server, quiet_request_logging, register_tasks
from xippios.core.mcp.toolset import ToolSet

__all__ = [
    "LOOPBACK_HOSTS",
    "ToolSet",
    "build_parser",
    "build_server",
    "cap_result",
    "error_to_text",
    "main",
    "quiet_request_logging",
    "register_tasks",
    "tool_functions",
    "tool_name",
]
