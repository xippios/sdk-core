"""Register task functions as MCP tools.

Each tool keeps the task's signature and docstring, so the SDK derives the input
schema and the description from them. The body awaits the task's async twin, turns
taxonomy errors into text and applies the result cap.

A server can be locked to one tenant (``TenantLock``): a middleware refuses every tool
call naming another before the tool runs. A server whose tasks were registered with
``read_only=False`` is a write server (``is_write_server``), which ``main`` keeps on
loopback unless told otherwise.

Building a server also quiets httpx's request log (``quiet_request_logging``).
"""

import functools
import inspect
import logging
import typing
import weakref
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from xippios.core._loop import as_async
from xippios.core.errors import InvalidRequestError, XippiosError
from xippios.core.mcp.errors import error_to_text
from xippios.core.mcp.results import ResultCap, cap_result
from xippios.core.models import Result
from xippios.core.tenants import _LISTS_TENANTS

__all__ = [
    "TenantLock",
    "build_server",
    "is_write_server",
    "quiet_request_logging",
    "register_tasks",
    "tool_name",
]

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


@dataclass(frozen=True, slots=True)
class TenantLock:
    """Lock a server to one tenant: a tool call naming another never reaches the tool.

    Given to ``build_server`` or ``register_tasks`` (conventions §8, ADR-0014). A
    ``tools/call`` whose arguments carry ``param`` with a value other than ``value`` is
    answered with ``error: InvalidRequestError: this server is locked to
    <param>=<value>; the call named another tenant`` and the tool does not run; a call
    without ``param`` is left to the tool's own argument validation; listing tools and
    every other request are untouched. A tool built by ``xippios.core.tenants.list_task``
    lists the locked tenant only.

    Attributes:
        param: The tool parameter that names the tenant, e.g. ``"org"``.
        value: The tenant the server serves, e.g. ``"acme"``.

    Raises:
        ValueError: ``param`` is not a parameter name or ``value`` is empty.
    """

    param: str
    value: str

    def __post_init__(self) -> None:
        if not self.param.isidentifier():
            raise ValueError("param must be a parameter name such as 'org'")
        if not self.value:
            raise ValueError("value must name the tenant the server serves")


_LOCKS: weakref.WeakKeyDictionary[MCPServer, TenantLock] = weakref.WeakKeyDictionary()
_WRITE_SERVERS: weakref.WeakSet[MCPServer] = weakref.WeakSet()


def is_write_server(server: MCPServer) -> bool:
    """True when tasks were registered on ``server`` with ``read_only=False``."""
    return server in _WRITE_SERVERS


def _lock_sentence(lock: TenantLock) -> str:
    return (
        f"This server is locked to {lock.param} {lock.value}; "
        f"every tool call must pass {lock.param}={lock.value}."
    )


def _lock_middleware(lock: TenantLock) -> ServerMiddleware[Any]:
    """The pre-call middleware ``TenantLock`` describes.

    The ``mcp`` middleware API is provisional in 2.x; the in-process ``mcp.Client``
    tests in ``tests/mcp/test_lock.py`` guard it.
    """
    refusal = error_to_text(
        InvalidRequestError(
            f"this server is locked to {lock.param}={lock.value}; the call named another tenant"
        )
    )

    async def tenant_lock(
        ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        if ctx.method == "tools/call":
            arguments = (ctx.params or {}).get("arguments")
            if (
                isinstance(arguments, Mapping)
                and lock.param in arguments
                and arguments[lock.param] != lock.value
            ):
                # Text, like every family error: a refusal is not an MCP protocol error.
                return CallToolResult(content=[TextContent(type="text", text=refusal)])
        return await call_next(ctx)

    return tenant_lock


def _install_lock(server: MCPServer, lock: TenantLock) -> None:
    """Install the lock's middleware on ``server`` once; another lock is refused."""
    current = _LOCKS.get(server)
    if current == lock:
        return
    if current is not None:
        raise ValueError(
            f"the server is locked to {current.param}={current.value} already; "
            "a locked server serves one tenant"
        )
    _LOCKS[server] = lock
    server.middleware.append(_lock_middleware(lock))


def _only_the_locked_tenant(server: MCPServer, result: Any) -> Any:
    """A tenant list narrowed to the tenant ``server`` is locked to; unchanged unlocked."""
    lock = _LOCKS.get(server)
    if lock is None or not isinstance(result, Result) or not isinstance(result.data, list):
        return result
    return result.model_copy(update={"data": [name for name in result.data if name == lock.value]})


def tool_name(source: str, fn: Callable[..., Any]) -> str:
    """``<source>_<function name>`` with the source slug underscored, never doubled."""
    prefix = source.replace("-", "_")
    name = fn.__name__
    return name if name.startswith(f"{prefix}_") else f"{prefix}_{name}"


def _confirm_problem(fn: Callable[..., Any]) -> str | None:
    """Why ``fn`` does not take ``confirm: bool = False``, or ``None`` when it does.

    The annotation is resolved with ``typing.get_type_hints``, so a string annotation
    and ``Annotated[bool, ...]`` count as ``bool``; ``bool | None`` does not.
    """
    parameter = inspect.signature(fn).parameters.get("confirm")
    if parameter is None:
        return "no parameter confirm"
    annotation = typing.get_type_hints(fn).get("confirm", parameter.annotation)
    if annotation is inspect.Parameter.empty:
        return "confirm is not annotated"
    if annotation is not bool:
        return f"confirm is annotated {annotation!r}, not bool"
    if parameter.default is inspect.Parameter.empty:
        return "confirm has no default"
    if parameter.default is not False:
        return f"confirm defaults to {parameter.default!r}, not False"
    return None


def _as_tool(
    fn: Callable[..., Any], cap: ResultCap, narrow: Callable[[Any], Any] | None = None
) -> Callable[..., Awaitable[str]]:
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
        if narrow is not None:
            result = narrow(result)
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
    tenant_lock: TenantLock | None = None,
) -> list[str]:
    """Add each task function to ``server`` as a tool and return the tool names.

    With ``read_only=False`` every task must take ``confirm: bool = False`` and return a
    dry-run preview unless it is true (conventions §8); the tasks are checked before any
    is registered, so a task without it registers nothing. The server is then a write
    server (``is_write_server``), which ``main`` serves over HTTP on loopback only unless
    ``--allow-remote`` is passed.

    Args:
        server: The server to register on.
        source: Source slug, e.g. ``"usda-nass"``; prefixes every tool name.
        tasks: Task functions (sync facades, async functions, or plain functions).
        cap: Result cap; defaults to 200 rows or 64 KB.
        read_only: Mark the tools read-only. Write tools belong in a separate server.
        tenant_lock: Lock the whole server to one tenant, e.g.
            ``TenantLock("org", "acme")``; installed once per server, the same lock
            again is a no-op. The instructions are not changed here; ``build_server``
            adds the sentence naming the tenant.

    Raises:
        ValueError: ``read_only`` is ``False`` and a task has no parameter ``confirm``
            annotated ``bool`` with the default ``False``; the message names the tool.
            Or ``tenant_lock`` differs from the lock the server already has.
    """
    cap = cap or ResultCap()
    tasks = list(tasks)
    if not read_only:
        for fn in tasks:
            problem = _confirm_problem(fn)
            if problem is not None:
                raise ValueError(
                    f"{tool_name(source, fn)}: {problem}; every task of a write server takes "
                    "confirm: bool = False and previews unless it is true (conventions §8)"
                )
    if tenant_lock is not None:
        _install_lock(server, tenant_lock)
    if not read_only:
        _WRITE_SERVERS.add(server)
    annotations = ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=not read_only,
        idempotent_hint=read_only,
        open_world_hint=True,
    )
    names: list[str] = []
    for fn in tasks:
        name = tool_name(source, fn)
        lists_tenants = getattr(fn, _LISTS_TENANTS, False) is True
        narrow = functools.partial(_only_the_locked_tenant, server) if lists_tenants else None
        server.add_tool(
            _as_tool(fn, cap, narrow),
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
    tenant_lock: TenantLock | None = None,
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
        read_only: Whether the tools are read-only; ``False`` for a write server, whose
            every task takes ``confirm: bool = False`` (see ``register_tasks``).
        tenant_lock: Lock the server to one tenant, e.g. ``TenantLock("org", "acme")``
            (see ``TenantLock``). The instructions gain one sentence: "This server is
            locked to org acme; every tool call must pass org=acme."

    Raises:
        ValueError: ``read_only`` is ``False`` and a task does not take
            ``confirm: bool = False``.
    """
    if tenant_lock is not None:
        instructions = " ".join(filter(None, [instructions, _lock_sentence(tenant_lock)]))
    server = MCPServer(name or f"xippios-{source}", version=version, instructions=instructions)
    quiet_request_logging()
    register_tasks(server, source, tasks, cap=cap, read_only=read_only, tenant_lock=tenant_lock)
    return server
