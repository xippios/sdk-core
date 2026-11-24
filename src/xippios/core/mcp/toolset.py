"""The tool set of the package contract: what a package's ``build(**options)`` returns.

The package contract is how a host serves a source (ADR-0026, decision 8, and
amendment 2026-11-18, points c and d): the variables the package needs, as
``xippios.core.EnvVar`` entries, and the tool set here. A source's ``mcp.py`` builds its
tool set in ``build(**options)``, whose options are keyword arguments with defaults, and
its server from it::

    from xippios.core.mcp import ToolSet, build_server, main, tool_functions
    from xippios.example import tasks


    def build() -> ToolSet:
        return ToolSet(
            "example",
            tool_functions(tasks),
            caps=tasks.MCP_CAPS,
            instructions="Example via xippios. Call the list tools first.",
            version="1.2.0",
            add_options=tasks.mcp_add_options,
            apply_options=tasks.mcp_apply_options,
        )


    TOOLS = build()
    server = build_server(TOOLS)


    def run() -> None:
        main(server, add_options=TOOLS.add_options, apply_options=TOOLS.apply_options)

A multi-tenant source's ``build`` takes ``lock: TenantLock | None = None`` and passes its
tasks through ``bind_tasks`` and its instructions through ``tenant_instructions``. A host
builds one server from several tool sets with ``register_tasks(server, tool_set)``, and
applies each one's hooks with ``option_defaults()``.

A tool set is checked when it is built, so a source's own tests fail on a declaration that
no server could serve, before any server is built (ADR-0063, decision 3).
"""

import argparse
import inspect
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NoReturn

from mcp.server.mcpserver import MCPServer

from xippios.core._tasks import is_bulk_task, tool_name
from xippios.core.models import ResultCap

__all__ = ["ToolSet"]

_OFFSET = "offset"
"""The adapter's own argument of a paged tool: the rows of the answer already shown."""

_START = "start"
"""A task's own offset into upstream's rows, which the note of its cut answer resumes."""


@dataclass(frozen=True, slots=True, eq=False, init=False)
class ToolSet:
    """What a package serves over MCP: its tools, caps, text, version, hooks and holds.

    ``build_server(tool_set)`` builds the package's server from it, and a host registers
    several tool sets on one server with ``register_tasks(server, tool_set)``; both take
    every field but the hooks from the tool set, so a server a host builds keeps a
    package's caps, its write rule and its hold to loopback (ADR-0063, decision 1).
    ``serve_tenants`` builds a multi-tenant source's bound server from the tool set its
    ``build(lock)`` returns.

    A tool set holds tools alone: a task its module names in ``BULK_TASKS`` is left out,
    a wrapper whose ``__wrapped__`` leads to one included, so the names of its tools are
    ``tool_name(tool_set.source, fn)`` for each ``fn`` of ``tool_set.tasks``. It is
    checked when it is built, before any server is: a write tool set's every task takes
    ``confirm: bool = False``, every key of ``caps`` names one of its tasks, and a paged
    cap fits its task (ADR-0063, decision 3). ``dataclasses.replace`` gives a narrowed
    copy, a host's list of tools say, and checks it as a new tool set, so a copy that
    drops a task drops its cap too.

    Args:
        source: Source slug, e.g. ``"example"``; prefixes every tool name.
        tasks: The task functions as the package's lock binds them, e.g.
            ``bind_tasks(tool_functions(tasks), lock)``, kept as a tuple without the
            tasks of ``BULK_TASKS``.
        caps: A tool's own result cap, keyed by the task function's ``__name__``, a
            source's ``MCP_CAPS``, kept as a read-only copy; ``None``, as
            ``getattr(tasks, "MCP_CAPS", None)`` gives for a source without them, is no
            cap of a tool's own. Every other tool takes the family default, 200 rows or
            64 KB (ADR-0038).
        instructions: Server-level guidance for agents; ``None`` for none.
        version: The package's version, shown to clients.
        add_options: Adds the package's options to core's parser, ``main``'s hook;
            ``None`` for none.
        apply_options: Applies the parsed options and returns the server to run,
            ``main``'s hook; ``None`` for none.
        read_only: ``False`` for a write tool set, whose every task takes
            ``confirm: bool = False`` and whose server is held to loopback.
        loopback_only: ``True`` for a read tool set whose server is held to loopback as
            a write server is (ADR-0025, D-a).

    Raises:
        ValueError: ``source`` is empty. Or ``read_only`` is ``False`` and a task does
            not take ``confirm: bool = False``; or a key of ``caps`` names no task of the
            tool set, a task of ``BULK_TASKS`` included; or a paged cap is given to a
            task of a write tool set, which a continuation would run again, to a task
            that takes ``offset``, which the adapter's argument would shadow, or to a
            task that takes ``start``, which pages upstream itself (ADR-0047, ADR-0061,
            decision 9). Each message names the tool and says why.
        TypeError: An entry of ``tasks`` is no function; the message names its position.
    """

    source: str
    tasks: Sequence[Callable[..., Any]]  # kept a tuple; a Sequence, so replace() takes a list
    caps: Mapping[str, ResultCap]
    instructions: str | None
    version: str
    add_options: Callable[[argparse.ArgumentParser], None] | None
    apply_options: Callable[[argparse.Namespace, MCPServer], MCPServer] | None
    read_only: bool
    loopback_only: bool

    def __init__(
        self,
        source: str,
        tasks: Iterable[Callable[..., Any]],
        *,
        caps: Mapping[str, ResultCap] | None = None,
        instructions: str | None = None,
        version: str = "",
        add_options: Callable[[argparse.ArgumentParser], None] | None = None,
        apply_options: Callable[[argparse.Namespace, MCPServer], MCPServer] | None = None,
        read_only: bool = True,
        loopback_only: bool = False,
    ) -> None:
        if not source:
            raise ValueError("source must name the source, e.g. 'example'")
        functions = tuple(tasks)
        for position, fn in enumerate(functions, start=1):
            if not callable(fn):
                raise TypeError(
                    f"entry {position} of tasks is no function; a tool set takes the task "
                    "functions, e.g. tool_functions(tasks)"
                )
        functions = tuple(fn for fn in functions if not is_bulk_task(fn))
        own = dict(caps or {})
        _check(source, functions, own, read_only=read_only)
        given: dict[str, object] = {
            "source": source,
            "tasks": functions,
            "caps": MappingProxyType(own),
            "instructions": instructions,
            "version": version,
            "add_options": add_options,
            "apply_options": apply_options,
            "read_only": read_only,
            "loopback_only": loopback_only,
        }
        for name, value in given.items():
            object.__setattr__(self, name, value)  # frozen: the dataclass refuses setattr

    def option_defaults(self) -> argparse.Namespace:
        """The options ``main`` hands ``apply_options`` when the command line names none.

        Core's options and those ``add_options`` adds, each at its default, as ``main``
        parses an empty command line; core's alone without ``add_options``. A host that
        serves the tool set without its entry point applies the hooks with them,
        ``tool_set.apply_options(tool_set.option_defaults(), server)``, so the server holds
        what the entry point holds when it runs without options.

        Raises:
            ValueError: An option of ``add_options`` takes no value from an empty command
                line, a required one or one whose default its type refuses; the message
                names the source and gives argparse's. Nothing is printed and the process
                goes on, where argparse would print its usage and exit, which would end a
                host that serves other packages too.
        """
        # Imported here: cli imports server, which imports this module.
        from xippios.core.mcp.cli import build_parser

        parser = build_parser(add_options=self.add_options)

        def refuse(message: str) -> NoReturn:
            raise ValueError(
                f"{self.source}: add_options needs a default for each of its options, since a "
                f"host applies the hooks without a command line: {message}"
            )

        parser.error = refuse  # type: ignore[method-assign]
        return parser.parse_args([])


def _check(
    source: str,
    tasks: Sequence[Callable[..., Any]],
    caps: Mapping[str, ResultCap],
    *,
    read_only: bool,
) -> None:
    """Refuse a declaration that no server could serve: the three checks of a tool set.

    In this order: a key of ``caps`` that names none of ``tasks``, a task of a write tool
    set without ``confirm: bool = False``, and a paged cap its task does not fit.

    Raises:
        ValueError: Naming every unknown key, sorted, or else the first tool that fails.
    """
    unknown = sorted(set(caps) - {fn.__name__ for fn in tasks})
    if unknown:
        raise ValueError(
            f"caps names no task among the tasks: {', '.join(unknown)}; a key is the task "
            "function's __name__, not the tool name with the source prefix, and a task in "
            "BULK_TASKS is no tool"
        )
    if not read_only:
        for fn in tasks:
            problem = _confirm_problem(fn)
            if problem is not None:
                raise ValueError(
                    f"{tool_name(source, fn)}: {problem}; every task of a write server takes "
                    "confirm: bool = False and previews unless it is true (conventions §8)"
                )
    for fn in tasks:
        cap = caps.get(fn.__name__)
        problem = None if cap is None else _paged_problem(fn, cap, read_only=read_only)
        if problem is not None:
            raise ValueError(f"{tool_name(source, fn)}: {problem}")


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


def _paged_problem(fn: Callable[..., Any], cap: ResultCap, *, read_only: bool) -> str | None:
    """Why ``fn`` cannot have the paged ``cap``, or ``None`` when it can.

    A continuation runs the task again, so a write task, every task of a write tool set,
    is never paged: following its note would repeat a confirmed write. ``keep="last"``
    alone runs it once and names no call, so a write task may keep the last rows. A task
    that takes ``offset`` itself would have the adapter's argument shadow its own, and
    one that takes ``start`` pages upstream itself, so its cut answer resumes with its
    own ``start`` and a continuation would send upstream a request (ADR-0061, decision 9).
    """
    if not cap.paged:
        return None
    if not read_only:
        return (
            "a paged cap runs the task again for the next rows, so a write task is never "
            "paged: following its note would repeat a confirmed write; leave the tool unpaged"
        )
    parameters = inspect.signature(fn).parameters
    if _OFFSET in parameters:
        return (
            "the task takes a parameter offset, which a paged cap adds as the adapter's own "
            "argument for the rest of a cut answer; rename the task's parameter or leave the "
            "tool unpaged"
        )
    if _START in parameters:
        return (
            "the task takes a parameter start and pages upstream itself, so its cut answer "
            "resumes with start and a continuation would send upstream a request; leave the "
            "tool unpaged"
        )
    return None
