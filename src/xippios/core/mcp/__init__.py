"""MCP adapter helpers (conventions §8): task functions become tools, nothing else.

A source's ``mcp.py`` is a handful of lines::

    from xippios.core.mcp import build_server, main
    from xippios.usda.nass import tasks

    server = build_server("usda-nass", [tasks.get_series, tasks.list_commodities])

    def run() -> None:
        main(server)

A source's own command-line options reach ``main`` through two hooks, parsed once with
core's: ``add_options`` puts them on the parser, ``apply_options`` returns the server to
run, and a ``XippiosError`` it raises stops the process with exit status 2 (ADR-0014).

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
from xippios.core.mcp.server import build_server, tool_name
from xippios.core.models import ResultCap

__all__ = [
    "ResultCap",
    "build_parser",
    "build_server",
    "cap_result",
    "error_to_text",
    "main",
    "tool_name",
]
