"""Register a tool set's tasks as MCP tools.

Each tool keeps the task's signature, the metadata of an ``Annotated`` parameter
included, so the SDK derives the input schema from it. Its description is the text of the
task's docstring before ``Args:``, and each argument's text under ``Args:`` describes that
argument in the input schema, unless the parameter's ``Annotated`` metadata declares a
description of its own (ADR-0063, decision 9). The body awaits the task's async twin,
turns taxonomy errors into text flagged ``is_error`` and applies the result cap: the
tool's own from the tool set's ``caps``, else the family default (ADR-0038).

``build_server`` builds a server from one ``ToolSet``, the package contract's, and
``register_tasks`` registers a tool set on a server a host builds from several; both take
a tool set alone, which a source's ``build`` returns and which was checked when it was
built (ADR-0063, decisions 1 and 3).

Every server answers an argument a tool does not declare and arguments its schema
refuses in conventions §8's form, flagged ``is_error`` and saying that nothing was sent,
through one middleware ``register_tasks`` installs before the tool runs, instead of the
SDK's MCP error (ADR-0063, decision 6). Whether a server is held to loopback is its tool
set's to say, ``read_only`` and ``loopback_only``: ``main`` reads it from the tool set it
builds the server from, and a host from each tool set it registers (ADR-0063, decision 5).

Building a server also quiets the request log of httpx and httpx2
(``quiet_request_logging``).
"""

import functools
import inspect
import logging
import re
import typing
import weakref
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any

import pydantic
from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata, func_metadata
from mcp.types import CallToolResult, ToolAnnotations
from pydantic.fields import FieldInfo

from xippios.core._loop import as_async
from xippios.core._tasks import tool_name
from xippios.core.errors import InvalidRequestError, XippiosError, _refused_arguments
from xippios.core.mcp.errors import _error_answer
from xippios.core.mcp.results import cap_result
from xippios.core.mcp.toolset import _OFFSET, ToolSet
from xippios.core.models import ResultCap

__all__ = ["build_server", "quiet_request_logging", "register_tasks"]

_REQUEST_LOGGERS = ("httpx", "httpcore", "httpx2", "httpcore2")


def quiet_request_logging() -> None:
    """Keep httpx and httpx2 from logging request URLs: set their loggers to ``WARNING``.

    Constructing an ``MCPServer`` (``mcp`` SDK 2.x) calls the SDK's
    ``configure_logging`` with the default level ``INFO``: ``logging.basicConfig`` sets
    the root logger to ``INFO`` with a stderr handler, unless the process configured
    root logging before. httpx logs every request at
    ``INFO`` as ``HTTP Request: GET <full URL> "HTTP/1.1 200 OK"``, and MCP clients
    capture a server's stderr into their own logs. The full URL carries the API key for
    a source that sends it as a query parameter (a query ``KeyAuth``) and names the tenant
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

        server = build_server(tool_set)
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

_DEFAULT_CAP = ResultCap()
"""The cap of a tool without one of its own: the family default, 200 rows or 64 KB."""


def _adapter_arguments(server: MCPServer, name: str) -> tuple[str, ...]:
    """The arguments the adapter adds to the task of the tool ``name``, for the family check.

    ``("offset",)`` for a tool registered with a paged cap (ADR-0047), else none.
    """
    record = _RECORDS.get(server)
    return () if record is None else record.added.get(name, ())


_NOTHING_SENT = "Nothing was sent."
"""The sentence that closes the MCP adapter's refusal of an argument: the tool did not run."""


def _arguments_middleware(record: _ServerRecord) -> ServerMiddleware[Any]:
    """The pre-call middleware that answers refused arguments as ``InvalidRequestError``.

    For a tool ``register_tasks`` registered, the call's arguments are checked against
    the argument model the SDK builds for it (``func_metadata``), before the SDK does: an
    argument the model does not declare, which the SDK would drop, is refused naming the
    ones it declares (https://github.com/xippios/sdk-core/issues/84), and the others are
    validated. A refusal is answered as ``error: InvalidRequestError: <argument>:
    <message>. Nothing was sent.``, flagged ``is_error``, where the SDK would answer an MCP
    error quoting pydantic's text, the input value included (queue row 41 a). Every other
    call, request and failure reaches the SDK unchanged.
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
    the count when there are several, and says that nothing was sent, since the tool did
    not run (ADR-0063, decision 6). A validator that crashes leaves the SDK to answer,
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
    if not errors:
        return None
    refused = str(_refused_arguments(errors))
    return _error_answer(InvalidRequestError(f"{refused.removesuffix('.')}. {_NOTHING_SENT}"))


def _declared(metadata: FuncMetadata) -> list[str]:
    """The argument names a tool's model declares, in the signature's order.

    A field's alias where it has one: the SDK renames a parameter that shadows a
    ``BaseModel`` attribute and keeps its name as the alias, which the input schema shows.
    """
    fields = metadata.arg_model.model_fields
    return [field.alias or name for name, field in fields.items()]


_ARGS = "Args:"
"""The line that opens a docstring's arguments, at the docstring's own indentation (§8)."""

_ENTRY = re.compile(r"(?P<name>\*{0,2}[A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:(?:\s+(?P<text>.*))?$")
"""An argument's first line under ``Args:``: its name, its type in parentheses, its text."""


def _docstring_parts(fn: Callable[..., Any]) -> tuple[list[str], list[str]]:
    """The lines of ``fn``'s docstring before ``Args:``, and those of its ``Args:`` block.

    The block ends at the next line of the docstring's own indentation, the ``Returns:`` or
    ``Raises:`` that follows it say. A docstring without ``Args:`` is its first part whole.
    """
    lines = (inspect.getdoc(fn) or "").splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == _ARGS), None)
    if start is None:
        return lines, []
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and not line[0].isspace():
            break
        block.append(line)
    return lines[:start], block


def _description(fn: Callable[..., Any]) -> str:
    """A tool's description: the text of its task's docstring before ``Args:``.

    What follows ``Args:``, a ``Returns:`` or ``Raises:`` section after it included, is no
    part of it: each argument's text reaches the input schema instead, by
    ``_argument_texts`` (ADR-0063, decision 9). The family check holds it under 1,000
    characters.
    """
    return "\n".join(_docstring_parts(fn)[0]).strip()


def _argument_texts(fn: Callable[..., Any]) -> dict[str, str]:
    """Each argument's text under ``Args:`` of ``fn``'s docstring, by the argument's name.

    An entry is a line at the block's least indentation that opens with a name, its type in
    parentheses if any, and a colon; its text is the rest of that line and every line below
    it up to the next entry, as the docstring wraps it, the indentation they share removed.
    An entry without text gives none.
    """
    block = _docstring_parts(fn)[1]
    depths = [len(line) - len(line.lstrip()) for line in block if line.strip()]
    if not depths:
        return {}
    depth = min(depths)
    entries: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in block:
        at_depth = bool(line.strip()) and len(line) - len(line.lstrip()) == depth
        entry = _ENTRY.match(line[depth:]) if at_depth else None
        if entry is not None:
            current = entries.setdefault(entry["name"].lstrip("*"), [])
            current.append(entry["text"] or "")
        elif current is not None:
            current.append(line)
    texts = {name: inspect.cleandoc("\n".join(lines)) for name, lines in entries.items()}
    return {name: text for name, text in texts.items() if text}


def _declares_a_description(annotation: Any) -> bool:
    """Whether ``annotation`` is ``Annotated`` with a ``Field`` that holds a description."""
    if typing.get_origin(annotation) is not Annotated:
        return False
    return any(
        isinstance(meta, FieldInfo) and meta.description is not None
        for meta in typing.get_args(annotation)[1:]
    )


def _with_text(parameter: inspect.Parameter, text: str | None) -> inspect.Parameter:
    """``parameter`` described by ``text``, its argument's text under ``Args:``.

    A parameter whose ``Annotated`` metadata declares a description keeps it, since it is
    the parameter's own, and so does a parameter without an annotation or without text.
    """
    annotation = parameter.annotation
    if not text or annotation is inspect.Parameter.empty or _declares_a_description(annotation):
        return parameter
    return parameter.replace(annotation=Annotated[annotation, pydantic.Field(description=text)])


_OFFSET_HELP = {
    "first": "Rows of the answer already shown, to skip: the note of a cut answer names the "
    "next offset. 0, the default, starts at the first row.",
    "last": "Rows of the answer already shown, counted from its last row: the note of a cut "
    "answer names the next offset, which reaches older rows. 0, the default, starts at the "
    "last row.",
}
"""The description of ``offset`` in a paged tool's input schema, by the cap's ``keep``."""


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
    (https://github.com/xippios/sdk-core/issues/68). A parameter that declares no
    description takes its argument's text under ``Args:`` as one (ADR-0063, decision 9).
    The tool returns the capped result as text, or a ``XippiosError`` as the family's text
    flagged ``is_error``.

    A paged cap adds ``offset: int = 0``, at least 0, after the task's parameters: the
    tool takes it off the call, runs the task without it and hands it to ``cap_result``,
    so it reaches neither the task nor ``meta.request`` (ADR-0047).
    """
    target = as_async(fn)
    hints = typing.get_type_hints(fn, include_extras=True)
    signature = inspect.signature(fn)
    texts = _argument_texts(fn)
    parameters = [
        _with_text(p.replace(annotation=hints.get(p.name, p.annotation)), texts.get(p.name))
        for p in signature.parameters.values()
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


def register_tasks(server: MCPServer, tool_set: ToolSet) -> list[str]:
    """Add each task of ``tool_set`` to ``server`` as a tool and return the tool names.

    A host builds one server from the tool sets of several packages, each tool with its
    own package's caps; a tool without a cap of its own takes the family default, 200
    rows or 64 KB (ADR-0038). A tool's description is the text of its task's docstring
    before ``Args:``, and each argument's text under ``Args:`` describes it in the input
    schema (ADR-0063, decision 9). The tool set was checked when it was built, so nothing is
    refused here (ADR-0063, decision 3). A tool set that writes, ``read_only=False``,
    marks its tools read-only false and destructive. Whether ``server`` is then held to
    loopback is the host's to apply from the tool set's ``read_only`` and
    ``loopback_only``, as ``main`` does (ADR-0063, decision 5).

    Arguments a tool's schema refuses are answered as ``error: InvalidRequestError:
    <argument>: <message>. Nothing was sent.`` before the tool runs, by a middleware
    installed once per server (conventions §8), never with pydantic's rendered error (its
    URL, input type or input value). So is an argument the tool does not declare, which
    the answer names with the ones it declares: ``yaer: Not an argument of this tool; it
    takes series_id, year. Nothing was sent.`` Every error answer, the task's own
    ``XippiosError`` included, sets ``is_error`` on its result beside the text (ADR-0026,
    decision 6). The middleware is appended to ``server.middleware`` at the first
    registration, and the SDK runs that list outermost-first, so a middleware appended
    later runs inside the check. A source that installs middleware of its own chooses its
    place in ``server.middleware``; index 0 is ahead of the SDK's own OpenTelemetry and
    request-state middleware as well.

    Args:
        server: The server to register on.
        tool_set: What a package serves, e.g. ``mcp.build()``: its source prefixes every
            tool name, ``tool_name(tool_set.source, fn)``.
    """
    record = _RECORDS.setdefault(server, _ServerRecord())
    if record.checking is None:
        record.checking = _arguments_middleware(record)
        server.middleware.append(record.checking)
    annotations = ToolAnnotations(
        read_only_hint=tool_set.read_only,
        destructive_hint=not tool_set.read_only,
        idempotent_hint=tool_set.read_only,
        open_world_hint=True,
    )
    names: list[str] = []
    for fn in tool_set.tasks:
        name = tool_name(tool_set.source, fn)
        cap = tool_set.caps.get(fn.__name__, _DEFAULT_CAP)
        tool = _as_tool(fn, cap)
        server.add_tool(
            tool,
            name=name,
            description=_description(fn),
            annotations=annotations,
            structured_output=False,
        )
        record.arguments[name] = func_metadata(tool, structured_output=False)
        record.added[name] = (_OFFSET,) if cap.paged else ()
        names.append(name)
    return names


def build_server(tool_set: ToolSet, *, name: str | None = None) -> MCPServer:
    """Create an ``MCPServer`` for ``tool_set`` with its tasks registered.

    The server of a package's ``ToolSet``, what its ``build(**options)`` returns: named
    ``xippios-<source>`` unless ``name`` names it, with the tool set's version and
    instructions, and its tasks registered as ``register_tasks(server, tool_set)``
    registers them (ADR-0063, decision 1).

    The ``mcp`` SDK configures root logging at ``INFO`` while the server is constructed
    (unless it was configured before); the httpx, httpcore, httpx2 and httpcore2 loggers
    are set to ``WARNING`` right after, so request URLs, which may carry a key or a
    tenant host, stay out of the log. See ``quiet_request_logging``.

    Args:
        tool_set: What the package serves, e.g. ``build()``.
        name: Server name; defaults to ``xippios-<source>``.
    """
    server = MCPServer(
        name or f"xippios-{tool_set.source}",
        version=tool_set.version,
        instructions=tool_set.instructions,
    )
    quiet_request_logging()
    register_tasks(server, tool_set)
    return server
