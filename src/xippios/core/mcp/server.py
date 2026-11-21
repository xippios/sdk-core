"""Register task functions as MCP tools.

Each tool keeps the task's signature and docstring, the metadata of an ``Annotated``
parameter included, so the SDK derives the input schema and the description from them.
The body awaits the task's async twin, turns taxonomy errors into text flagged
``is_error`` and applies the result cap: the tool's own from ``caps``, else the server's
(ADR-0038).

A task its ``tasks.py`` names in ``BULK_TASKS`` is no tool and is skipped (ADR-0040);
``tool_functions(tasks)`` gives the rest of ``tasks.__all__``.

Every server answers an argument a tool does not declare and arguments its schema
refuses in conventions §8's form, flagged ``is_error``, through one middleware
``register_tasks`` installs before the tool runs, instead of the SDK's MCP error. A
server whose tasks were registered with ``read_only=False`` is a write server
(``is_write_server``); it and a read server registered with ``loopback_only=True`` are
held to loopback (``is_loopback_only``), which ``main`` serves on a loopback ``--host``
only unless told otherwise.

``build_server`` builds a server from one ``ToolSet``, the package contract's, and
``register_tasks`` registers a tool set on a server a host builds from several
(ADR-0026, amendment 2026-11-18, point d).

Building a server also quiets the request log of httpx and httpx2
(``quiet_request_logging``).
"""

import functools
import inspect
import logging
import typing
import weakref
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, overload

import pydantic
from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata, func_metadata
from mcp.types import CallToolResult, ToolAnnotations

from xippios.core._loop import as_async
from xippios.core._tasks import is_bulk_task, tool_functions
from xippios.core.errors import XippiosError, _refused_arguments
from xippios.core.mcp.errors import _error_answer
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.toolset import ToolSet
from xippios.core.models import ResultCap

__all__ = [
    "build_server",
    "is_loopback_only",
    "is_write_server",
    "quiet_request_logging",
    "register_tasks",
    "tool_functions",
    "tool_name",
]

_REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")


def quiet_request_logging() -> None:
    """Keep httpx and httpx2 from logging request URLs: set their loggers to ``WARNING``.

    Constructing an ``MCPServer`` (``mcp`` SDK 2.x) calls the SDK's
    ``configure_logging`` with the default level ``INFO``: ``logging.basicConfig`` sets
    the root logger to ``INFO`` with a stderr handler, unless the process configured
    root logging before. httpx logs every request at
    ``INFO`` as ``HTTP Request: GET <full URL> "HTTP/1.1 200 OK"``, and MCP clients
    capture a server's stderr into their own logs. The full URL carries the API key for
    a source that sends it as a query parameter (``QueryKeyAuth``) and names the tenant
    for a source with one host per tenant; neither belongs in a log (ADR-0030).
    httpcore's ``DEBUG`` traces name the host as well, so httpcore is quieted with it.
    The ``mcp`` SDK 2.x builds its own HTTP client on httpx2 and httpcore2, which log
    the same way under the loggers ``httpx2`` and ``httpcore2``, so a process that also
    calls through the SDK's client, a proxy or a test harness, keeps its URLs out too.

    ``build_server`` calls this right after constructing the server, and ``main`` calls
    it again before running one. It only sets the four logger levels: no handler is
    added and no other logger is touched, so calling it again changes nothing.

    A consumer who wants the request log on purpose, knowing that it writes keys and
    tenant hosts wherever the log goes, raises the level after building the server and
    runs the server itself, since ``main`` quiets the loggers again::

        server = build_server("usda-nass", tool_functions(tasks))
        logging.getLogger("httpx").setLevel(logging.INFO)
        server.run(transport="stdio")
    """
    for name in _REQUEST_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


@dataclass(slots=True)
class _ServerRecord:
    """What ``register_tasks`` knows about a server: its tools' arguments."""

    arguments: dict[str, FuncMetadata] = field(default_factory=dict)
    """Per tool name, the argument model the SDK validates a call against."""
    added: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per tool name, the arguments the adapter adds to its task's: ``offset`` when paged."""
    checking: ServerMiddleware[Any] | None = None
    """The argument middleware, installed once per server."""


_RECORDS: weakref.WeakKeyDictionary[MCPServer, _ServerRecord] = weakref.WeakKeyDictionary()
_WRITE_SERVERS: weakref.WeakSet[MCPServer] = weakref.WeakSet()
_LOOPBACK_SERVERS: weakref.WeakSet[MCPServer] = weakref.WeakSet()


def _adapter_arguments(server: MCPServer, name: str) -> tuple[str, ...]:
    """The arguments the adapter adds to the task of the tool ``name``, for the family check.

    ``("offset",)`` for a tool registered with a paged cap (ADR-0047), else none.
    """
    record = _RECORDS.get(server)
    return () if record is None else record.added.get(name, ())


def is_write_server(server: MCPServer) -> bool:
    """True when tasks were registered on ``server`` with ``read_only=False``."""
    return server in _WRITE_SERVERS


def is_loopback_only(server: MCPServer) -> bool:
    """True when ``server`` is held to loopback: a write server, or one built ``loopback_only``.

    ``main`` serves such a server over ``--http`` on a loopback ``--host`` only
    (``LOOPBACK_HOSTS``) unless ``--allow-remote`` is passed, since it carries no
    authentication; a host that serves the server itself holds it the same way
    (ADR-0036, decision 9; ADR-0025, D-a; ADR-0026, decision 5). Tasks registered with
    ``loopback_only=True`` (``register_tasks``, ``build_server``) or ``read_only=False``
    hold the server from then on.
    """
    return server in _LOOPBACK_SERVERS or server in _WRITE_SERVERS


def _arguments_middleware(record: _ServerRecord) -> ServerMiddleware[Any]:
    """The pre-call middleware that answers refused arguments as ``InvalidRequestError``.

    For a tool ``register_tasks`` registered, the call's arguments are checked against
    the argument model the SDK builds for it (``func_metadata``), before the SDK does: an
    argument the model does not declare, which the SDK would drop, is refused naming the
    ones it declares (https://github.com/xippios/sdk-core/issues/84), and the others are
    validated. A refusal is answered as ``error: InvalidRequestError: <argument>:
    <message>``, flagged ``is_error``, where the SDK would answer an MCP error quoting
    pydantic's text, the input value included (queue row 41 a). Every other call, request
    and failure reaches the SDK unchanged.
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
    """The answer to ``arguments`` the argument model refuses, or ``None`` to go on.

    The errors are the arguments the model does not declare, in the call's order, then
    what its validation of the declared ones refuses; the answer names the first, with
    the count when there are several. A validator that crashes leaves the SDK to answer,
    unless an argument is undeclared.
    """
    declared = _declared(metadata)
    takes = ", ".join(declared) if declared else "no arguments"
    errors: list[Mapping[str, Any]] = [
        {"loc": (name,), "msg": f"Not an argument of this tool; it takes {takes}"}
        for name in arguments
        if name not in declared
    ]
    try:
        metadata.validate_arguments({k: v for k, v in arguments.items() if k in declared})
    except pydantic.ValidationError as exc:
        errors.extend(exc.errors(include_url=False, include_context=False, include_input=False))
    except Exception:
        pass  # a validator that crashes: the SDK answers it as it does
    return _error_answer(_refused_arguments(errors)) if errors else None


def _declared(metadata: FuncMetadata) -> list[str]:
    """The argument names a tool's model declares, in the signature's order.

    A field's alias where it has one: the SDK renames a parameter that shadows a
    ``BaseModel`` attribute and keeps its name as the alias, which the input schema shows.
    """
    fields = metadata.arg_model.model_fields
    return [field.alias or name for name, field in fields.items()]


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


_OFFSET = "offset"
"""The adapter's own argument of a paged tool: the rows of the answer already shown."""

_OFFSET_HELP = {
    "first": "Rows of the answer already shown, to skip: the note of a cut answer names the "
    "next offset. 0, the default, starts at the first row.",
    "last": "Rows of the answer already shown, counted from its last row: the note of a cut "
    "answer names the next offset, which reaches older rows. 0, the default, starts at the "
    "last row.",
}
"""The description of ``offset`` in a paged tool's input schema, by the cap's ``keep``."""


def _offset_problem(fn: Callable[..., Any], cap: ResultCap) -> str | None:
    """Why ``fn`` cannot have the paged ``cap``, or ``None`` when it can.

    A task that takes ``offset`` itself would have the adapter's argument shadow its own.
    """
    if cap.paged and _OFFSET in inspect.signature(fn).parameters:
        return (
            "the task takes a parameter offset, which a paged cap adds as the adapter's own "
            "argument for the rest of a cut answer; rename the task's parameter or leave the "
            "tool unpaged"
        )
    return None


def _with_offset(parameters: list[inspect.Parameter], cap: ResultCap) -> list[inspect.Parameter]:
    """``parameters`` with the adapter's ``offset`` after the task's, keyword-only.

    It goes before a ``**`` parameter, which must come last.
    """
    offset = inspect.Parameter(
        _OFFSET,
        inspect.Parameter.KEYWORD_ONLY,
        default=0,
        annotation=Annotated[int, pydantic.Field(ge=0, description=_OFFSET_HELP[cap.keep])],
    )
    if parameters and parameters[-1].kind is inspect.Parameter.VAR_KEYWORD:
        return [*parameters[:-1], offset, parameters[-1]]
    return [*parameters, offset]


def _as_tool(
    fn: Callable[..., Any], cap: ResultCap
) -> Callable[..., Awaitable[str | CallToolResult]]:
    """The tool for ``fn``: its signature, ``Annotated`` metadata kept, and its docstring.

    The hints are resolved with ``include_extras=True``, so a ``Field`` constraint, a
    description or a validator that an ``Annotated`` parameter declares reaches the
    argument model, the input schema and the argument check
    (https://github.com/xippios/sdk-core/issues/68). The tool returns the capped result
    as text, or a ``XippiosError`` as the family's text flagged ``is_error``.

    A paged cap adds ``offset: int = 0``, at least 0, after the task's parameters: the
    tool takes it off the call, runs the task without it and hands it to ``cap_result``,
    so it reaches neither the task nor ``meta.request`` (ADR-0047).
    """
    target = as_async(fn)
    hints = typing.get_type_hints(fn, include_extras=True)
    signature = inspect.signature(fn)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation)) for p in signature.parameters.values()
    ]
    if cap.paged:
        parameters = _with_offset(parameters, cap)

    async def tool(*args: Any, **kwargs: Any) -> str | CallToolResult:
        offset = kwargs.pop(_OFFSET, 0) if cap.paged else 0
        try:
            return cap_result(await target(*args, **kwargs), cap, offset=offset)
        except XippiosError as exc:
            return _error_answer(exc)

    functools.update_wrapper(tool, fn)
    tool.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters, return_annotation=str | CallToolResult
    )
    tool.__annotations__ = {p.name: p.annotation for p in parameters} | {
        "return": str | CallToolResult
    }
    return tool


def _alone(refusal: str, given: Mapping[str, bool]) -> None:
    """Refuse the arguments ``given`` marks as passed beside a tool set, naming each.

    Raises:
        TypeError: ``refusal``, then ``; drop`` and the names, in ``given``'s order.
    """
    passed = [name for name, is_passed in given.items() if is_passed]
    if passed:
        raise TypeError(f"{refusal}; drop {', '.join(passed)}")


@overload
def register_tasks(server: MCPServer, source: ToolSet, /) -> list[str]: ...


@overload
def register_tasks(
    server: MCPServer,
    source: str,
    tasks: Iterable[Callable[..., Any]],
    *,
    cap: ResultCap | None = None,
    caps: Mapping[str, ResultCap] | None = None,
    read_only: bool = True,
    loopback_only: bool = False,
) -> list[str]: ...


def register_tasks(
    server: MCPServer,
    source: str | ToolSet,
    tasks: Iterable[Callable[..., Any]] | None = None,
    *,
    cap: ResultCap | None = None,
    caps: Mapping[str, ResultCap] | None = None,
    read_only: bool = True,
    loopback_only: bool = False,
) -> list[str]:
    """Add each task function to ``server`` as a tool and return the tool names.

    ``register_tasks(server, tool_set)`` registers a ``ToolSet`` with its source, tasks,
    caps, ``read_only`` and ``loopback_only``, so a host builds one server from the tool
    sets of several packages, each tool with its own package's caps, and a held tool set
    holds the server. A tool set comes alone: ``tasks`` or a keyword given with a value
    other than its default is refused with ``TypeError`` before anything is registered.

    Arguments a tool's schema refuses are answered as ``error: InvalidRequestError:
    <argument>: <message>`` before the tool runs, by a middleware installed once per
    server (conventions §8), never with pydantic's rendered error (its URL, input type or
    input value). So is an argument the tool does not declare, which the answer names
    with the ones it declares: ``yaer: Not an argument of this tool; it takes series_id,
    year``. Every error answer, the task's own ``XippiosError`` included, sets
    ``is_error`` on its result beside the text (ADR-0026, decision 6). The middleware is
    appended to ``server.middleware`` at the first registration, and the SDK runs that
    list outermost-first, so a middleware appended later runs inside the check. A source
    that installs middleware of its own chooses its place in ``server.middleware``; index
    0 is ahead of the SDK's own OpenTelemetry and request-state middleware as well.

    A task the module that defines it names in ``BULK_TASKS`` (``tasks.py``, beside
    ``MCP_CAPS``) is skipped: a bulk task returns a file, or a list read from one, and is
    Python-only; no tool returns a file path to an agent (conventions §8, ADR-0040). So
    an adapter may pass every name of ``tasks.__all__``. A wrapper is skipped as the
    task it wraps when ``__wrapped__`` leads to it, whatever its own ``__module__``
    (``functools.wraps`` sets it); ``tool_functions(tasks)`` leaves the bulk tasks out
    before any wrapper is made.

    With ``read_only=False`` every task must take ``confirm: bool = False`` and return a
    dry-run preview unless it is true (conventions §8); the tasks are checked before any
    is registered, so a task without it registers nothing. The server is then a write
    server (``is_write_server``), which ``main`` serves over HTTP on loopback only unless
    ``--allow-remote`` is passed.

    With ``loopback_only=True`` a read server is held to loopback the same way
    (``is_loopback_only``): for one that reaches data no deployment may serve without
    authentication, a mailbox say (ADR-0025, D-a). A host that combines several
    packages' tasks on one server passes it when one of them is held.

    Args:
        server: The server to register on.
        source: Source slug, e.g. ``"usda-nass"``; prefixes every tool name. Or a
            ``ToolSet``, which carries every other argument.
        tasks: Task functions (sync facades, async functions, or plain functions); one
            named in its module's ``BULK_TASKS`` is skipped. Required with a slug.
        cap: Result cap of every tool without an entry in ``caps``; defaults to 200 rows
            or 64 KB.
        caps: A tool's own result cap, replacing ``cap`` for it, keyed by the task
            function's ``__name__``, e.g. ``{"list_partners": ResultCap(max_rows=400,
            max_bytes=100_000)}`` for the tool ``comtrade_list_partners``: for a
            reference tool whose whole list an agent needs (conventions §8, ADR-0038).
            It sets ``max_rows`` and ``max_bytes`` as the source judges; a byte bound
            above the default 64 KB is a deliberate choice for that tool, so that an
            agent gets the list whole. Its ``note`` says how to see the rest when the
            cap still cuts. A field the per-tool cap leaves unset takes the family
            default (200 rows, 65,536 bytes, the default note), not ``cap``'s. A paged
            cap, ``ResultCap(paged=True)``, gives the tool the adapter's own ``offset``
            for the rest of a cut answer, and ``keep="last"`` shows the last rows first
            (ADR-0047).
        read_only: Mark the tools read-only. Write tools belong in a separate server.
        loopback_only: Hold the server to loopback (``is_loopback_only``); a write
            server is held whatever this says.

    Raises:
        ValueError: ``read_only`` is ``False`` and a task has no parameter ``confirm``
            annotated ``bool`` with the default ``False``; the message names the tool.
            Or a key of ``caps`` is not the ``__name__`` of one of ``tasks`` that becomes a
            tool, a task in ``BULK_TASKS`` included; the message names it. Or a task with
            a paged cap takes a parameter ``offset`` itself, which the adapter's would
            shadow; the message names the tool and says so. Nothing is registered,
            installed or marked then.
        TypeError: A slug without ``tasks``, or a tool set with ``tasks`` or another
            argument; the message names each. Nothing is registered, installed or marked.
    """
    if isinstance(source, ToolSet):
        _alone(
            "register_tasks takes a tool set alone, which carries what it registers",
            {
                "tasks": tasks is not None,
                "cap": cap is not None,
                "caps": caps is not None,
                "read_only": not read_only,
                "loopback_only": loopback_only,
            },
        )
        return register_tasks(
            server,
            source.source,
            source.tasks,
            caps=source.caps,
            read_only=source.read_only,
            loopback_only=source.loopback_only,
        )
    if tasks is None:
        raise TypeError(
            "register_tasks takes the tasks beside a source slug, e.g. register_tasks(server, "
            "'usda-nass', tool_functions(tasks)), or a tool set alone"
        )
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
    for fn in tasks:
        problem = _offset_problem(fn, caps.get(fn.__name__, cap))
        if problem is not None:
            raise ValueError(f"{tool_name(source, fn)}: {problem}")
    record = _RECORDS.setdefault(server, _ServerRecord())
    if record.checking is None:
        record.checking = _arguments_middleware(record)
        server.middleware.append(record.checking)
    if not read_only:
        _WRITE_SERVERS.add(server)
    if loopback_only:
        _LOOPBACK_SERVERS.add(server)
    annotations = ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=not read_only,
        idempotent_hint=read_only,
        open_world_hint=True,
    )
    names: list[str] = []
    for fn in tasks:
        name = tool_name(source, fn)
        tool_cap = caps.get(fn.__name__, cap)
        tool = _as_tool(fn, tool_cap)
        server.add_tool(
            tool,
            name=name,
            description=inspect.getdoc(fn) or "",
            annotations=annotations,
            structured_output=False,
        )
        record.arguments[name] = func_metadata(tool, structured_output=False)
        record.added[name] = (_OFFSET,) if tool_cap.paged else ()
        names.append(name)
    return names


@overload
def build_server(source: ToolSet, /, *, name: str | None = None) -> MCPServer: ...


@overload
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
    loopback_only: bool = False,
) -> MCPServer: ...


def build_server(
    source: str | ToolSet,
    tasks: Iterable[Callable[..., Any]] | None = None,
    *,
    name: str | None = None,
    version: str = "",
    instructions: str | None = None,
    cap: ResultCap | None = None,
    caps: Mapping[str, ResultCap] | None = None,
    read_only: bool = True,
    loopback_only: bool = False,
) -> MCPServer:
    """Create an ``MCPServer`` named ``xippios-<source>`` with the tasks registered.

    ``build_server(tool_set)`` builds the server of a package's ``ToolSet``, what its
    ``build(**options)`` returns: named ``xippios-<source>`` unless ``name`` names it, with
    the tool set's version and instructions, and its tasks registered as
    ``register_tasks(server, tool_set)`` registers them. Beside a tool set ``name`` alone
    is taken: ``tasks`` or another keyword given with a value other than its default is
    refused with ``TypeError``, before the server is built.

    The ``mcp`` SDK configures root logging at ``INFO`` while the server is constructed
    (unless it was configured before); the httpx, httpcore, httpx2 and httpcore2 loggers
    are set to ``WARNING`` right after, so request URLs, which may carry a key or a
    tenant host, stay out of the log. See ``quiet_request_logging``.

    Args:
        source: Source slug, or a ``ToolSet``, which carries every argument but ``name``.
        tasks: Task functions to expose, e.g. ``tool_functions(tasks)``, which is
            ``tasks.__all__`` minus ``BULK_TASKS``; a task in its module's
            ``BULK_TASKS`` is skipped here too (ADR-0040), no tool returns a file path to
            an agent. Required with a slug.
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
        loopback_only: ``True`` for a read server that ``main`` serves over ``--http``
            on a loopback ``--host`` only unless ``--allow-remote`` is passed, as it
            serves a write server (``is_loopback_only``; ADR-0025, D-a).

    Raises:
        ValueError: ``read_only`` is ``False`` and a task does not take
            ``confirm: bool = False``; or a key of ``caps`` names no task that becomes a
            tool, a bulk task included.
        TypeError: A slug without ``tasks``, or a tool set with ``tasks`` or a keyword
            but ``name``; the message names each.
    """
    if isinstance(source, ToolSet):
        _alone(
            "build_server takes name alone beside a tool set, which carries the rest",
            {
                "tasks": tasks is not None,
                "version": version != "",
                "instructions": instructions is not None,
                "cap": cap is not None,
                "caps": caps is not None,
                "read_only": not read_only,
                "loopback_only": loopback_only,
            },
        )
        built = MCPServer(
            name or f"xippios-{source.source}",
            version=source.version,
            instructions=source.instructions,
        )
        quiet_request_logging()
        register_tasks(built, source)
        return built
    if tasks is None:
        raise TypeError(
            "build_server takes the tasks beside a source slug, e.g. build_server('usda-nass', "
            "tool_functions(tasks)), or a tool set alone"
        )
    server = MCPServer(name or f"xippios-{source}", version=version, instructions=instructions)
    quiet_request_logging()
    register_tasks(
        server,
        source,
        tasks,
        cap=cap,
        caps=caps,
        read_only=read_only,
        loopback_only=loopback_only,
    )
    return server
