"""Register task functions as MCP tools.

Each tool keeps the task's signature and docstring, so the SDK derives the input
schema and the description from them. The body awaits the task's async twin, turns
taxonomy errors into text and applies the result cap.
"""

import functools
import inspect
import typing
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from xippios.core._loop import as_async
from xippios.core.errors import XippiosError
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import ResultCap, cap_result

__all__ = ["build_server", "register_tasks", "tool_name"]


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
    register_tasks(server, source, tasks, cap=cap, read_only=read_only)
    return server
