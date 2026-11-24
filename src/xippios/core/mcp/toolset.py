"""The tool set of the package contract: what a package's ``build(**options)`` returns.

The package contract is how a host serves a source (ADR-0063, decisions 2 and 4): the
variables the package needs, as ``xippios.core.EnvVar`` entries, and the tool set here.
Core builds a source's tool set from its tasks module, ``ToolSet.from_tasks``, so a
rendered ``mcp.py`` holds no line that a source edits (ADR-0063, decision 7)::

    from xippios.core.mcp import ToolSet, build_server, main
    from xippios.example import tasks
    from xippios.example._version import __version__


    def build() -> ToolSet:
        return ToolSet.from_tasks("example", tasks, version=__version__)


    server = build_server(build())


    def run() -> None:
        main(build)

The tasks module declares what the source serves beside its tasks: ``MCP_CAPS``,
``MCP_INSTRUCTIONS``, the two option hooks ``mcp_add_options`` and ``mcp_apply_options``,
and, for a read server held to loopback, ``MCP_LOOPBACK_ONLY = True``. A multi-tenant
source's ``build`` takes ``lock: TenantLock | None = None`` and passes it on, and its
module adds ``MCP_BOUND_INSTRUCTIONS``, the text of a server bound to one tenant. A host
builds one server from several tool sets with ``register_tasks(server, tool_set)``, and
applies each one's hooks with ``option_defaults()``.

A tool set is checked when it is built, so a source's own tests fail on a declaration that
no server could serve, before any server is built (ADR-0063, decision 3). It imports
nothing of the MCP SDK: its hooks take the parsed options alone.
"""

import argparse
import inspect
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any, NoReturn, Self

from xippios.core._tasks import is_bulk_task, tool_functions, tool_name
from xippios.core.models import ResultCap
from xippios.core.tenants import TenantLock, bind_tasks, tenant_instructions

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
    every field but the hooks and the hold from the tool set, so a server a host builds
    keeps a package's caps and its write rule (ADR-0063, decision 1). ``main(build)`` reads
    the hooks and the hold from the tool set that ``build`` returns, and a host reads them
    as it serves it (ADR-0063, decisions 4, 5 and 7). Core builds a source's tool set from
    its tasks module with ``from_tasks``.

    A tool set holds tools alone: a task its module names in ``BULK_TASKS`` is left out,
    a wrapper whose ``__wrapped__`` leads to one included, so the names of its tools are
    ``tool_name(tool_set.source, fn)`` for each ``fn`` of ``tool_set.tasks``. It is
    checked when it is built, before any server is: a write tool set's every task takes
    ``confirm: bool = False``, every key of ``caps`` names one of its tasks, and a paged
    cap fits its task (ADR-0063, decision 3). ``dataclasses.replace`` gives a narrowed
    copy, a host's list of tools say, and checks it as a new tool set, so the caller drops
    the cap of each task it drops, with ``caps=`` beside ``tasks=`` in the same
    ``replace``, else the check of a key of ``caps`` refuses the copy with a
    ``ValueError`` naming the key (ADR-0063, decision 4).

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
        apply_options: Applies the parsed options and returns nothing, ``main``'s hook;
            ``None`` for none. It takes no server, since no hook uses one
            (https://github.com/xippios/sdk-core/issues/485, part 1). A ``XippiosError``
            that it raises, an option value the source refuses or a missing variable,
            ``main`` turns into the message on stderr and exit status 2, and a host that
            applies it without ``main`` catches it itself and stops the same way.
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
            decision 9). Each message says why: the refusal of a key of ``caps`` names
            the key, each such key sorted, and the refusals of the other two checks
            name the tool.
        TypeError: An entry of ``tasks`` is no function; the message names its position.
    """

    source: str
    tasks: Sequence[Callable[..., Any]]  # kept a tuple; a Sequence, so replace() takes a list
    caps: Mapping[str, ResultCap]
    instructions: str | None
    version: str
    add_options: Callable[[argparse.ArgumentParser], None] | None
    apply_options: Callable[[argparse.Namespace], None] | None
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
        apply_options: Callable[[argparse.Namespace], None] | None = None,
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

    @classmethod
    def from_tasks(
        cls,
        source: str,
        tasks: ModuleType,
        *,
        version: str = "",
        lock: TenantLock | None = None,
        read_only: bool = True,
    ) -> Self:
        """The tool set of a source's tasks module, as its ``mcp.py`` serves it.

        Core reads the module as ``tool_functions`` reads its ``BULK_TASKS``: its tools,
        ``tool_functions(tasks)``, and what it declares for the server, each optional
        (ADR-0063, decision 7):

        - ``MCP_CAPS``, a tool's own result cap by its task's name;
        - ``MCP_INSTRUCTIONS``, the server's instructions;
        - ``mcp_add_options`` and ``mcp_apply_options``, the two option hooks of ``main``;
        - ``MCP_LOOPBACK_ONLY = True``, a read server held to loopback as a write server
          is (ADR-0025, D-a);
        - ``MCP_BOUND_INSTRUCTIONS``, the text of a server bound to one tenant, without the
          clause that every tool takes the tenant's argument (``tenant_instructions``).

        Given ``lock``, the tasks are bound to its tenant with ``bind_tasks`` and the
        instructions end with the lock's sentence, ``tenant_instructions(MCP_INSTRUCTIONS,
        lock, bound=MCP_BOUND_INSTRUCTIONS)``. The tool set is checked as any is.

        Args:
            source: Source slug, e.g. ``"example"``, a source's ``_client.SOURCE``.
            tasks: The source's ``tasks`` module, or its ``tasks_write`` for the write
                server.
            version: The package's version, e.g. its ``__version__``.
            lock: The tenant a multi-tenant source's server is bound to, e.g.
                ``TenantLock(TENANTS, "acme")``; ``None`` for every declared tenant, and
                for a source without tenants.
            read_only: ``False`` for the write server's module, whose every task takes
                ``confirm: bool = False``.

        Raises:
            TypeError: A declaration holds another type: ``MCP_CAPS`` no mapping, an
                instructions text no ``str``, ``MCP_LOOPBACK_ONLY`` no ``bool``, a hook no
                function; the message names the module's declaration. And as ``ToolSet``
                and ``tool_functions`` raise.
            ValueError: As ``ToolSet``, ``tool_functions`` and ``bind_tasks`` raise.
        """
        caps = _declared(tasks, "MCP_CAPS", Mapping, "a mapping", None)
        text = _declared(tasks, "MCP_INSTRUCTIONS", str, "text or None", None)
        bound = _declared(tasks, "MCP_BOUND_INSTRUCTIONS", str, "text or None", None)
        held = _declared(tasks, "MCP_LOOPBACK_ONLY", bool, "True or False", False)
        add_options = _hook(tasks, "mcp_add_options")
        apply_options = _hook(tasks, "mcp_apply_options")
        return cls(
            source,
            bind_tasks(tool_functions(tasks), lock),
            caps=caps,
            instructions=tenant_instructions(text, lock, bound=bound),
            version=version,
            add_options=add_options,
            apply_options=apply_options,
            read_only=read_only,
            loopback_only=held,
        )

    def option_defaults(self) -> argparse.Namespace:
        """The options ``main`` hands ``apply_options`` when the command line names none.

        Core's options and those ``add_options`` adds, each at its default, as ``main``
        parses an empty command line; core's alone without ``add_options``. A host that
        serves the tool set without its entry point applies the hooks with them,
        ``tool_set.apply_options(tool_set.option_defaults())``, so its server holds what
        the entry point holds when it runs without options. They hold no tenant's option,
        the ``--<param>`` that ``main`` adds where it is given ``tenants``, since a host
        binds no tenant (ADR-0063, decision 4): a hook that read it would find no such
        attribute under a host.

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


def _declared(tasks: ModuleType, name: str, kind: type[Any], what: str, default: object) -> Any:
    """The declaration ``name`` of ``tasks``, ``default`` where it is absent or ``None``.

    Raises:
        TypeError: It is not of ``kind``; the message names the module's declaration.
    """
    value = getattr(tasks, name, None)
    if value is None:
        return default
    if not isinstance(value, kind):
        raise TypeError(f"{tasks.__name__}.{name} is {what}, got {type(value).__name__}")
    return value


def _hook(tasks: ModuleType, name: str) -> Any:
    """The option hook ``name`` of ``tasks``, or ``None`` where it declares none.

    Raises:
        TypeError: It is no function; the message names the module's declaration.
    """
    value = getattr(tasks, name, None)
    if value is not None and not callable(value):
        raise TypeError(
            f"{tasks.__name__}.{name} is a function or None, got {type(value).__name__}"
        )
    return value


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
