"""Register task functions as MCP tools.

Each tool keeps the task's signature and docstring, so the SDK derives the input
schema and the description from them. The body awaits the task's async twin, turns
taxonomy errors into text and applies the result cap: the tool's own from ``caps``,
else the server's (ADR-0016).

A task its ``tasks.py`` names in ``BULK_TASKS`` is no tool and is skipped (ADR-0019).

Every server answers arguments a tool's schema refuses in conventions §8's form, through
one middleware ``register_tasks`` installs before the tool runs, instead of the SDK's
MCP error. A server can be locked to one tenant (``TenantLock``): a middleware refuses
every tool call naming another before the tool runs. A server whose tasks were registered with
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
from dataclasses import dataclass, field
from typing import Any

import pydantic
from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata, func_metadata
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from xippios.core._loop import as_async, is_bulk_task
from xippios.core.errors import InvalidRequestError, XippiosError
from xippios.core.mcp.errors import _refused_arguments, error_to_text
from xippios.core.mcp.results import cap_result
from xippios.core.models import Result, ResultCap
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

    Given to ``build_server`` or ``register_tasks`` (conventions §8, ADR-0014). A tool
    that takes the tenant parameter must receive it on a locked server, and a default is
    refused:

    - a ``tools/call`` whose arguments carry ``param`` with a value other than ``value``
      is answered with ``error: InvalidRequestError: this server is locked to
      <param>=<value>; the call named another tenant``, and one that leaves ``param``
      out while the tool's input schema declares it with ``...; the call did not name
      the tenant``; the tool does not run;
    - a task whose ``param`` has a default is refused with ``ValueError`` when it is
      registered on a locked server, and so is the lock on a server that has one;
    - a call to a tool that does not take ``param``, such as the tenant list, passes
      unless it names another tenant; listing tools and every other request are
      untouched. A tool built by ``xippios.core.tenants.list_task`` lists the locked
      tenant only.

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


@dataclass(slots=True)
class _ServerRecord:
    """What ``register_tasks`` knows about a server: its lock, its tools' arguments."""

    lock: TenantLock | None = None
    defaulted: dict[str, frozenset[str]] = field(default_factory=dict)
    """Per tool name, the task's parameters that have a default."""
    arguments: dict[str, FuncMetadata] = field(default_factory=dict)
    """Per tool name, the argument model the SDK validates a call against."""
    checking: ServerMiddleware[Any] | None = None
    """The argument middleware, installed once per server."""


_RECORDS: weakref.WeakKeyDictionary[MCPServer, _ServerRecord] = weakref.WeakKeyDictionary()
_WRITE_SERVERS: weakref.WeakSet[MCPServer] = weakref.WeakSet()


def is_write_server(server: MCPServer) -> bool:
    """True when tasks were registered on ``server`` with ``read_only=False``."""
    return server in _WRITE_SERVERS


def _lock_sentence(lock: TenantLock) -> str:
    return (
        f"This server is locked to {lock.param} {lock.value}; "
        f"every tool call that takes {lock.param} must pass {lock.param}={lock.value}."
    )


def _refusal(lock: TenantLock, reason: str) -> CallToolResult:
    """The family's error text for a call the lock refuses; not an MCP protocol error."""
    return _answer(
        InvalidRequestError(f"this server is locked to {lock.param}={lock.value}; {reason}")
    )


async def _declares(server: MCPServer, tool: object, param: str) -> bool:
    """True when ``tool``'s input schema on ``server`` declares ``param``."""
    for listed in await server.list_tools():
        if listed.name == tool:
            properties = listed.input_schema.get("properties")
            return isinstance(properties, Mapping) and param in properties
    return False


def _lock_middleware(server: MCPServer, lock: TenantLock) -> ServerMiddleware[Any]:
    """The pre-call middleware ``TenantLock`` describes.

    The ``mcp`` middleware API is provisional in 2.x; the in-process ``mcp.Client``
    tests in ``tests/mcp/test_lock.py`` guard it.
    """
    other = _refusal(lock, "the call named another tenant")
    missing = _refusal(lock, "the call did not name the tenant")

    async def tenant_lock(
        ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        if ctx.method == "tools/call":
            params = ctx.params or {}
            arguments = params.get("arguments")
            arguments = {} if arguments is None else arguments
            if isinstance(arguments, Mapping):
                if lock.param in arguments:
                    if arguments[lock.param] != lock.value:
                        return other
                else:
                    try:
                        declared = await _declares(server, params.get("name"), lock.param)
                    except Exception:
                        # Fail closed, as text: a lookup that fails must neither let the
                        # call through nor raise through the MCP boundary.
                        return missing
                    if declared:
                        return missing
        return await call_next(ctx)

    return tenant_lock


def _answer(error: XippiosError) -> CallToolResult:
    """The family's error text as a tool's answer, not an MCP error (conventions §8)."""
    return CallToolResult(content=[TextContent(type="text", text=error_to_text(error))])


def _arguments_middleware(record: _ServerRecord) -> ServerMiddleware[Any]:
    """The pre-call middleware that answers refused arguments as ``InvalidRequestError``.

    For a tool ``register_tasks`` registered, the call's arguments are validated against
    the argument model the SDK builds for it (``func_metadata``), before the SDK does; a
    refusal is answered as ``error: InvalidRequestError: <argument>: <message>``, where
    the SDK would answer an MCP error quoting pydantic's text, the input value included
    (queue row 41 a). Every other call, request and failure reaches the SDK unchanged.
    """

    async def check_arguments(
        ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        if ctx.method == "tools/call":
            params = ctx.params or {}
            name = params.get("name")
            metadata = record.arguments.get(name) if isinstance(name, str) else None
            arguments = params.get("arguments")
            arguments = {} if arguments is None else arguments
            if metadata is not None and isinstance(arguments, Mapping):
                refused = _refusal_of(metadata, dict(arguments))
                if refused is not None:
                    return refused
        return await call_next(ctx)

    return check_arguments


def _refusal_of(metadata: FuncMetadata, arguments: dict[str, Any]) -> CallToolResult | None:
    """The answer to ``arguments`` the argument model refuses, or ``None`` to go on."""
    try:
        metadata.validate_arguments(arguments)
    except pydantic.ValidationError as exc:
        return _answer(_refused_arguments(exc))
    except Exception:
        return None  # a validator that crashes: the SDK answers it as it does
    return None


def _defaulted(fn: Callable[..., Any]) -> frozenset[str]:
    """The parameters of ``fn`` that have a default."""
    parameters = inspect.signature(fn).parameters.values()
    return frozenset(p.name for p in parameters if p.default is not inspect.Parameter.empty)


def _check_lock(
    server: MCPServer, source: str, tasks: list[Callable[..., Any]], lock: TenantLock | None
) -> TenantLock | None:
    """The lock ``server`` will have once ``tasks`` are registered; refusals before any.

    Raises:
        ValueError: ``lock`` differs from the lock the server has; or, on a locked
            server, a task already registered or one of ``tasks`` takes the tenant
            parameter with a default.
    """
    record = _RECORDS.get(server, _ServerRecord())
    if lock is not None and record.lock is not None and lock != record.lock:
        raise ValueError(
            f"the server is locked to {record.lock.param}={record.lock.value} already; "
            "a locked server serves one tenant"
        )
    lock = lock or record.lock
    if lock is None:
        return None
    defaults = record.defaulted | {tool_name(source, fn): _defaulted(fn) for fn in tasks}
    offending = sorted(name for name, params in defaults.items() if lock.param in params)
    if offending:
        raise ValueError(
            f"{', '.join(offending)}: {lock.param} has a default; a tool that takes the "
            f"tenant parameter must receive it on a locked server ({lock.param}="
            f"{lock.value}), and a default is refused (ADR-0014)"
        )
    return lock


def _only_the_locked_tenant(server: MCPServer, result: Any) -> Any:
    """A tenant list narrowed to the tenant ``server`` is locked to; unchanged unlocked."""
    record = _RECORDS.get(server)
    lock = None if record is None else record.lock
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


def _check_caps(tasks: list[Callable[..., Any]], caps: Mapping[str, ResultCap]) -> None:
    """Refuse a key of ``caps`` that is not the ``__name__`` of one of ``tasks``.

    ``tasks`` are the tools to be, a task in ``BULK_TASKS`` left out: a cap for it is
    refused as unknown.

    Raises:
        ValueError: Naming every such key, sorted.
    """
    unknown = sorted(set(caps) - {fn.__name__ for fn in tasks})
    if unknown:
        raise ValueError(
            f"caps names no task among the tasks: {', '.join(unknown)}; a key is the task "
            "function's __name__, not the tool name with the source prefix, and a task in "
            "BULK_TASKS is no tool"
        )


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
    caps: Mapping[str, ResultCap] | None = None,
    read_only: bool = True,
    tenant_lock: TenantLock | None = None,
) -> list[str]:
    """Add each task function to ``server`` as a tool and return the tool names.

    Arguments a tool's schema refuses are answered as ``error: InvalidRequestError:
    <argument>: <message>`` before the tool runs, by a middleware installed once per
    server (conventions §8), never with pydantic's text and the input value.

    A task the module that defines it names in ``BULK_TASKS`` (``tasks.py``, beside
    ``MCP_CAPS``) is skipped: a bulk task returns a file, or a list read from one, and is
    Python-only; no tool returns a file path to an agent (conventions §8, ADR-0019). So
    an adapter may pass every name of ``tasks.__all__``.

    With ``read_only=False`` every task must take ``confirm: bool = False`` and return a
    dry-run preview unless it is true (conventions §8); the tasks are checked before any
    is registered, so a task without it registers nothing. The server is then a write
    server (``is_write_server``), which ``main`` serves over HTTP on loopback only unless
    ``--allow-remote`` is passed.

    Args:
        server: The server to register on.
        source: Source slug, e.g. ``"usda-nass"``; prefixes every tool name.
        tasks: Task functions (sync facades, async functions, or plain functions); one
            named in its module's ``BULK_TASKS`` is skipped.
        cap: Result cap of every tool without an entry in ``caps``; defaults to 200 rows
            or 64 KB.
        caps: A tool's own result cap, replacing ``cap`` for it, keyed by the task
            function's ``__name__``, e.g. ``{"list_partners": ResultCap(max_rows=400,
            max_bytes=100_000)}`` for the tool ``comtrade_list_partners``: for a
            reference tool whose whole list an agent needs (conventions §8, ADR-0016).
            It sets ``max_rows`` and ``max_bytes`` as the source judges; a byte bound
            above the default 64 KB is a deliberate choice for that tool, so that an
            agent gets the list whole. Its ``note`` says how to see the rest when the
            cap still cuts. A field the per-tool cap leaves unset takes the family
            default (200 rows, 65,536 bytes, the default note), not ``cap``'s.
        read_only: Mark the tools read-only. Write tools belong in a separate server.
        tenant_lock: Lock the whole server to one tenant, e.g.
            ``TenantLock("org", "acme")``; installed once per server, the same lock
            again is a no-op. The instructions are not changed here; ``build_server``
            adds the sentence naming the tenant.

    Raises:
        ValueError: ``read_only`` is ``False`` and a task has no parameter ``confirm``
            annotated ``bool`` with the default ``False``; the message names the tool.
            Or a key of ``caps`` is not the ``__name__`` of one of ``tasks`` that becomes a
            tool, a task in ``BULK_TASKS`` included; the message names it. Or
            ``tenant_lock`` differs from the lock the server already has. Or the server
            is locked, by ``tenant_lock`` or before, and a task, registered now or
            earlier, gives the tenant parameter a default. Nothing is registered or
            installed then.
    """
    cap = cap or ResultCap()
    caps = caps or {}
    tasks = [fn for fn in tasks if not is_bulk_task(fn)]
    _check_caps(tasks, caps)
    if not read_only:
        for fn in tasks:
            problem = _confirm_problem(fn)
            if problem is not None:
                raise ValueError(
                    f"{tool_name(source, fn)}: {problem}; every task of a write server takes "
                    "confirm: bool = False and previews unless it is true (conventions §8)"
                )
    lock = _check_lock(server, source, tasks, tenant_lock)
    record = _RECORDS.setdefault(server, _ServerRecord())
    if record.checking is None:
        record.checking = _arguments_middleware(record)
        server.middleware.append(record.checking)
    if lock is not None and record.lock is None:
        record.lock = lock
        # Outside the argument check: a call naming another tenant is the lock's to refuse.
        position = server.middleware.index(record.checking)
        server.middleware.insert(position, _lock_middleware(server, lock))
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
        tool = _as_tool(fn, caps.get(fn.__name__, cap), narrow)
        server.add_tool(
            tool,
            name=name,
            description=inspect.getdoc(fn) or "",
            annotations=annotations,
            structured_output=False,
        )
        record.defaulted[name] = _defaulted(fn)
        record.arguments[name] = func_metadata(tool, structured_output=False)
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
    caps: Mapping[str, ResultCap] | None = None,
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
        tasks: Task functions to expose, e.g. ``[getattr(tasks, n) for n in
            tasks.__all__]``; a task in its module's ``BULK_TASKS`` is skipped
            (ADR-0019), no tool returns a file path to an agent.
        name: Server name; defaults to ``xippios-<source>``.
        version: Source package version, shown to clients.
        instructions: Server-level guidance for agents, e.g. which tool to call first.
        cap: Result cap of every tool without an entry in ``caps``.
        caps: A tool's own result cap, keyed by the task function's ``__name__``, e.g.
            ``{"list_partners": ResultCap(max_rows=400, max_bytes=100_000)}`` for a
            reference list an agent needs whole; a field it leaves unset takes the
            family default, not ``cap``'s (see ``register_tasks``).
        read_only: Whether the tools are read-only; ``False`` for a write server, whose
            every task takes ``confirm: bool = False`` (see ``register_tasks``).
        tenant_lock: Lock the server to one tenant, e.g. ``TenantLock("org", "acme")``
            (see ``TenantLock``). The instructions gain one sentence: "This server is
            locked to org acme; every tool call that takes org must pass org=acme."

    Raises:
        ValueError: ``read_only`` is ``False`` and a task does not take
            ``confirm: bool = False``; or a key of ``caps`` names no task that becomes a
            tool, a bulk task included; or, on a locked server, a task gives the tenant
            parameter a default.
    """
    if tenant_lock is not None:
        instructions = " ".join(filter(None, [instructions, _lock_sentence(tenant_lock)]))
    server = MCPServer(name or f"xippios-{source}", version=version, instructions=instructions)
    quiet_request_logging()
    register_tasks(
        server,
        source,
        tasks,
        cap=cap,
        caps=caps,
        read_only=read_only,
        tenant_lock=tenant_lock,
    )
    return server
