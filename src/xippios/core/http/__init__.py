"""HTTP adapter helpers (conventions §9): a FastAPI router generated from task functions.

A source's ``http.py`` is a handful of lines::

    from xippios.core.http import router_from_tasks
    from xippios.usda.nass import tasks

    router = router_from_tasks("usda-nass", [tasks.get_series, tasks.list_commodities])

The consumer mounts the router and, optionally, calls
``xippios.core.http.problems.install_error_handlers`` on its app so errors raised
outside endpoints become problem details too; that module also holds
``problem_response``, ``PROBLEM_MEDIA_TYPE`` and ``STATUS_BY_ERROR``.

Requires the ``http`` extra: ``uv add "xippios-core[http]"``.
"""

try:
    import fastapi  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "xippios.core.http needs the 'http' extra: uv add 'xippios-core[http]'"
    ) from exc

from xippios.core.http.problems import status_for
from xippios.core.http.router import is_scalar, router_from_tasks

__all__ = ["is_scalar", "router_from_tasks", "status_for"]
