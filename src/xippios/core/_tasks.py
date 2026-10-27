"""What core reads from a source's ``tasks.py`` about one task function.

The adapters ask it before they register a task (``register_tasks``,
``router_from_tasks``). Nothing here is public API.
"""

import sys
from collections.abc import Callable
from typing import Any

__all__ = ["is_bulk_task"]


def is_bulk_task(fn: Callable[..., Any]) -> bool:
    """True when the module that defines ``fn`` names it in its ``BULK_TASKS``.

    A bulk task returns a file or a list read from one and is Python-only:
    ``register_tasks`` and ``router_from_tasks`` skip it (ADR-0019, decision 4). The
    module is ``sys.modules[fn.__module__]``, the source's ``tasks.py``; a sync facade
    made by ``sync`` keeps its async twin's module and its name minus ``_async``, the
    name ``tasks.__all__`` and ``BULK_TASKS`` use.
    """
    module = sys.modules.get(getattr(fn, "__module__", None) or "")
    return getattr(fn, "__name__", None) in getattr(module, "BULK_TASKS", ())
