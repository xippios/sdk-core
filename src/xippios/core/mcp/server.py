"""Register task functions as MCP tools.

Each tool keeps the task's signature and docstring, so the SDK derives the input
schema and the description from them. The body awaits the task's async twin, turns
taxonomy errors into text and applies the result cap.

Building a server also quiets httpx's request log (``quiet_request_logging``).
"""

import functools
import inspect
import logging
import typing
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from xippios.core._loop import as_async
from xippios.core.errors import XippiosError
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import ResultCap, cap_result

__all__ = ["build_server", "quiet_request_logging", "register_tasks", "tool_name"]

_REQUEST_LOGGERS = ("httpx", "httpcore")


def quiet_request_logging() -> None:
    """Keep httpx and httpcore from logging request URLs: set both loggers to ``WARNING``.

    Constructing an ``MCPServer`` (``mcp`` SDK 2.x) calls the SDK's
    ``configure_logging`` with the default level ``INFO``: ``logging.basicConfig`` sets
    the root logger to ``INFO`` with a stderr handler, unless the process configured
    root logging before. httpx logs every request at
    ``INFO`` as ``HTTP Request: GET <full URL> "HTTP/1.1 200 OK"``, and MCP clients
    capture a server's stderr into their own logs. The full URL carries the API key for
    a source that sends it as a query parameter (``QueryKeyAuth``) and names the tenant
    for a source with one host per tenant; neither belongs in a log (ADR-0005).
    httpcore's ``DEBUG`` traces name the host as well, so httpcore is quieted with it.

    ``build_server`` calls this right after constructing the server, and ``main`` calls
    it again before running one. It only sets the two logger levels: no handler is added
    and no other logger is touched, so calling it again changes nothing.

    A consumer who wants the request log on purpose, knowing that it writes keys and
    tenant hosts wherever the log goes, raises the level after building the server and
    runs the server itself, since ``main`` quiets the loggers again::

        server = build_server("usda-nass", tasks)
        logging.getLogger("httpx").setLevel(logging.INFO)
        server.run(transport="stdio")
    """
    for name in _REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def tool_name(source: str, fn: Callable[..., Any]) -> str:
    """``<source>_<function name>`` with the source slug underscored, never doubled."""
    prefix = source.replace("-", "_")
    name = fn.__name__
    return name if name.startswith(f"{prefix}_") else f"{prefix}_{name}"


def _as_tool(fn: Callable[..., Any], cap: ResultCap) -> Callable[..., Awaitable[str]]:
    target = as_async(fn)
    hints = typing.get_type_hints(fn)
    signature = inspect.signature(fn)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation)) for p in signature.parameters.values()
    ]

    async def tool(*args: Any, **kwargs: Any) -> str:
        try:
            result = await target(*args, **kwargs)
        except XippiosError as exc:
            return error_to_text(exc)
        return cap_result(result, cap)

    functools.update_wrapper(tool, fn)
    tool.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters, return_annotation=str
    )
    tool.__annotations__ = {p.name: p.annotation for p in parameters} | {"return": str}
    return tool


def register_tasks(
    server: MCPServer,
    source: str,
    tasks: Iterable[Callable[..., Any]],
    *,
    cap: ResultCap | None = None,
    read_only: bool = True,
) -> list[str]:
    """Add each task function to ``server`` as a tool and return the tool names.

    Args:
        server: The server to register on.
        source: Source slug, e.g. ``"usda-nass"``; prefixes every tool name.
        tasks: Task functions (sync facades, async functions, or plain functions).
        cap: Result cap; defaults to 200 rows or 64 KB.
        read_only: Mark the tools read-only. Write tools belong in a separate server.
    """
    cap = cap or ResultCap()
    annotations = ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=not read_only,
        idempotent_hint=read_only,
        open_world_hint=True,
    )
    names: list[str] = []
    for fn in tasks:
        name = tool_name(source, fn)
        server.add_tool(
            _as_tool(fn, cap),
            name=name,
            description=inspect.getdoc(fn) or "",
            annotations=annotations,
            structured_output=False,
        )
        names.append(name)
    return names


def build_server(
    source: str,
    tasks: Iterable[Callable[..., Any]],
    *,
    name: str | None = None,
    version: str = "",
    instructions: str | None = None,
    cap: ResultCap | None = None,
    read_only: bool = True,
) -> MCPServer:
    """Create an ``MCPServer`` named ``xippios-<source>`` with the tasks registered.

    The ``mcp`` SDK configures root logging at ``INFO`` while the server is constructed
    (unless it was configured before); the httpx and httpcore loggers are set to
    ``WARNING`` right after, so request URLs, which may carry a key or a tenant host,
    stay out of the log. See ``quiet_request_logging``.

    Args:
        source: Source slug.
        tasks: Task functions to expose.
        name: Server name; defaults to ``xippios-<source>``.
        version: Source package version, shown to clients.
        instructions: Server-level guidance for agents, e.g. which tool to call first.
        cap: Result cap for every tool.
        read_only: Whether the tools are read-only; ``False`` for a write server.
    """
    server = MCPServer(name or f"xippios-{source}", version=version, instructions=instructions)
    quiet_request_logging()
    register_tasks(server, source, tasks, cap=cap, read_only=read_only)
    return server
