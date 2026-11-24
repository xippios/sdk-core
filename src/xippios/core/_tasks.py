"""What core reads from a source's ``tasks.py``: its tool functions, their names, its bulk tasks.

``tool_functions`` and ``tool_name`` are public through ``xippios.core``, since neither
needs the ``mcp`` extra, and through ``xippios.core.mcp`` (ADR-0063, decision 2).
``is_bulk_task`` is not public API: a ``ToolSet`` leaves a task named in ``BULK_TASKS``
out, and the HTTP router (``router_from_tasks``) skips it. What a tasks module declares for
the MCP server alone, ``MCP_CAPS``, ``MCP_INSTRUCTIONS``, ``MCP_BOUND_INSTRUCTIONS``, the
two option hooks and ``MCP_LOOPBACK_ONLY``, is read by ``ToolSet.from_tasks`` of
``xippios.core.mcp`` (ADR-0063, decision 7).
"""

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

__all__ = ["is_bulk_task", "tool_functions", "tool_name"]

_MISSING = object()


def tool_functions(tasks: ModuleType) -> list[Callable[..., Any]]:
    """The functions of ``tasks.__all__`` that become tools and routes, in its order.

    A task the module names in ``BULK_TASKS`` is left out: it returns a file, or a list
    read from one, and is Python-only (ADR-0040, decision 4). ``BULK_TASKS`` is read from
    ``tasks`` itself, so a function whose ``__module__`` names another module, a tenant
    lock's wrapper say, is judged by the module it is listed in. So a source's ``mcp.py``
    passes ``tool_functions(tasks)`` to its ``ToolSet``, and a host checks a tool list
    against the names of what it returns.

    A task's name is its entry in ``__all__``: a tool's name, a key of ``MCP_CAPS`` and an
    entry of ``BULK_TASKS`` read it as the function's ``__name__``, so the two must match
    for every entry, a bulk task's included.

    Args:
        tasks: A source's tasks module, e.g. ``xippios.example.tasks``, or its
            ``tasks_write`` for the write server.

    Raises:
        ValueError: ``tasks`` has no ``__all__``, or an entry of it names nothing in the
            module, no function, or a function whose ``__name__`` differs; the message
            names every such entry.
    """
    names = getattr(tasks, "__all__", None)
    if names is None:
        raise ValueError(f"{tasks.__name__} has no __all__, the names of its tasks")
    bulk = frozenset(getattr(tasks, "BULK_TASKS", ()))
    problems: list[str] = []
    functions: list[Callable[..., Any]] = []
    for name in names:
        fn = getattr(tasks, name, _MISSING)
        if fn is _MISSING:
            problems.append(f"{name} is not in the module")
        elif not callable(fn):
            problems.append(f"{name} is no function")
        elif getattr(fn, "__name__", None) != name:
            problems.append(f"{name} is the function {getattr(fn, '__name__', '?')}")
        elif name not in bulk:
            functions.append(fn)
    if problems:
        raise ValueError(
            f"{tasks.__name__}.__all__: {', '.join(problems)}; a task's name is its entry in "
            "__all__, which tool names, MCP_CAPS and BULK_TASKS read as the function's __name__"
        )
    return functions


def tool_name(source: str, task: Callable[..., Any] | str) -> str:
    """A task's tool name, ``<source>_<task>``, the slug underscored and never doubled.

    ``task`` is the task function, read by its ``__name__``, or its name as text, so a
    refusal that names a tool needs no function: ``tool_name("example", "get_series")``
    is ``example_get_series``, and so is ``tool_name("example", "example_get_series")``.
    A host names a source's tools with it, ``tool_name(tool_set.source, fn)`` for each
    ``fn`` of ``tool_set.tasks`` (ADR-0063, decision 4).

    Args:
        source: Source slug, e.g. ``"example"``; each ``-`` becomes ``_``.
        task: The task function, e.g. ``tasks.get_series``, or its name, ``"get_series"``.
    """
    prefix = source.replace("-", "_")
    name = task if isinstance(task, str) else task.__name__
    return name if name.startswith(f"{prefix}_") else f"{prefix}_{name}"


def is_bulk_task(fn: Callable[..., Any]) -> bool:
    """True when ``fn``, or a function it wraps, is named in its module's ``BULK_TASKS``.

    A bulk task returns a file or a list read from one and is Python-only:
    a ``ToolSet`` leaves it out and ``router_from_tasks`` skips it (ADR-0040, decision 4). The
    module of each layer is ``sys.modules[layer.__module__]``, the source's ``tasks.py``
    for the task itself; a sync facade made by ``sync`` keeps its async twin's module
    and its name minus ``_async``, the name ``tasks.__all__`` and ``BULK_TASKS`` use. The
    layers are ``fn`` and each ``__wrapped__`` below it, which ``functools.wraps`` sets,
    so a wrapper whose own ``__module__`` names another module, a tenant lock's, still
    leads to the task. A wrapper that keeps neither is judged by its own name and
    module: such a wrapper wraps ``tool_functions(tasks)``, which has left the bulk tasks
    out already.
    """
    return _declared(fn, "BULK_TASKS")


def _declared(fn: Callable[..., Any], declaration: str) -> bool:
    """Whether a layer of ``fn`` is named in its module's ``declaration``; see ``is_bulk_task``."""
    seen: set[int] = set()
    layer: Any = fn
    while layer is not None and id(layer) not in seen:
        seen.add(id(layer))
        module = sys.modules.get(getattr(layer, "__module__", None) or "")
        if getattr(layer, "__name__", None) in getattr(module, declaration, ()):
            return True
        layer = getattr(layer, "__wrapped__", None)
    return False
