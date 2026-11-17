"""What core reads from a source's ``tasks.py``: its tool functions and its bulk tasks.

The adapters ask ``is_bulk_task`` before they register a task (``register_tasks``,
``router_from_tasks``). ``tool_functions`` is public through ``xippios.core.mcp``;
``is_bulk_task`` is not public API.
"""

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

__all__ = ["is_bulk_task", "tool_functions"]

_MISSING = object()


def tool_functions(tasks: ModuleType) -> list[Callable[..., Any]]:
    """The functions of ``tasks.__all__`` that become tools and routes, in its order.

    A task the module names in ``BULK_TASKS`` is left out: it returns a file, or a list
    read from one, and is Python-only (ADR-0019, decision 4). ``BULK_TASKS`` is read from
    ``tasks`` itself, so a function whose ``__module__`` names another module, a tenant
    lock's wrapper say, is judged by the module it is listed in. So a source's ``mcp.py``
    passes ``tool_functions(tasks)`` to ``build_server``, and a host checks a tool list
    against the names of what it returns.

    A task's name is its entry in ``__all__``: a tool's name, a key of ``MCP_CAPS`` and an
    entry of ``BULK_TASKS`` read it as the function's ``__name__``, so the two must match
    for every entry, a bulk task's included.

    Args:
        tasks: A source's tasks module, e.g. ``xippios.usda.nass.tasks``, or its
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


def is_bulk_task(fn: Callable[..., Any]) -> bool:
    """True when ``fn``, or a function it wraps, is named in its module's ``BULK_TASKS``.

    A bulk task returns a file or a list read from one and is Python-only:
    ``register_tasks`` and ``router_from_tasks`` skip it (ADR-0019, decision 4). The
    module of each layer is ``sys.modules[layer.__module__]``, the source's ``tasks.py``
    for the task itself; a sync facade made by ``sync`` keeps its async twin's module
    and its name minus ``_async``, the name ``tasks.__all__`` and ``BULK_TASKS`` use. The
    layers are ``fn`` and each ``__wrapped__`` below it, which ``functools.wraps`` sets,
    so a wrapper whose own ``__module__`` names another module, a tenant lock's, still
    leads to the task. A wrapper that keeps neither is judged by its own name and
    module: such a wrapper wraps ``tool_functions(tasks)``, which has left the bulk tasks
    out already.
    """
    seen: set[int] = set()
    layer: Any = fn
    while layer is not None and id(layer) not in seen:
        seen.add(id(layer))
        module = sys.modules.get(getattr(layer, "__module__", None) or "")
        if getattr(layer, "__name__", None) in getattr(module, "BULK_TASKS", ()):
            return True
        layer = getattr(layer, "__wrapped__", None)
    return False
