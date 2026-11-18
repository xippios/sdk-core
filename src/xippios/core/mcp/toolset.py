"""The tool set of the package contract: what a package's ``build(**options)`` returns.

The package contract is how a host serves a source (ADR-0026, decision 8, and its
amendment of 2026-11-18, (c) and (d)): the variables the package needs, as
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
"""

import argparse
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, NoReturn

from mcp.server.mcpserver import MCPServer

from xippios.core.models import ResultCap

__all__ = ["ToolSet"]


@dataclass(frozen=True, slots=True, eq=False, init=False)
class ToolSet:
    """What a package serves over MCP: its tasks, caps, text, version, hooks and holds.

    ``build_server(tool_set)`` builds the package's server from it, and a host registers
    several tool sets on one server with ``register_tasks(server, tool_set)``; both take
    every field but the hooks from the tool set, so a server a host builds keeps a
    package's caps, its write rule and its hold to loopback. ``serve_tenants`` builds a
    multi-tenant source's bound server from the tool set its ``build(lock)`` returns. The
    fields are ``build_server``'s parameters, less the server's ``name`` and the default
    ``cap``, and ``main``'s two hooks. A server built from a tool set checks it as
    ``register_tasks`` checks its arguments. ``dataclasses.replace`` gives a narrowed copy,
    and checks it as a new tool set.

    Args:
        source: Source slug, e.g. ``"usda-nass"``; prefixes every tool name.
        tasks: The task functions as the package's lock binds them, e.g.
            ``bind_tasks(tool_functions(tasks), lock)``, kept as a tuple; one in its
            module's ``BULK_TASKS`` becomes no tool.
        caps: A tool's own result cap, keyed by the task function's ``__name__``, a
            source's ``MCP_CAPS``, kept as a read-only copy; ``None``, as
            ``getattr(tasks, "MCP_CAPS", None)`` gives for a source without them, is no
            cap of a tool's own. Every other tool takes the family default.
        instructions: Server-level guidance for agents; ``None`` for none.
        version: The package's version, shown to clients.
        add_options: Adds the package's options to core's parser, ``main``'s hook;
            ``None`` for none.
        apply_options: Applies the parsed options and returns the server to run,
            ``main``'s hook; ``None`` for none.
        read_only: ``False`` for a write server, whose every task takes
            ``confirm: bool = False``.
        loopback_only: ``True`` for a read server held to loopback
            (``is_loopback_only``).

    Raises:
        ValueError: ``source`` is empty.
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
            raise ValueError("source must name the source, e.g. 'usda-nass'")
        functions = tuple(tasks)
        for position, fn in enumerate(functions, start=1):
            if not callable(fn):
                raise TypeError(
                    f"entry {position} of tasks is no function; a tool set takes the task "
                    "functions, e.g. tool_functions(tasks)"
                )
        given: dict[str, object] = {
            "source": source,
            "tasks": functions,
            "caps": MappingProxyType(dict(caps or {})),
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
