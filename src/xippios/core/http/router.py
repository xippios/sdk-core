"""Build a FastAPI router from task functions.

Each task becomes ``GET /<source>/<function>``: its parameters are query parameters,
its return annotation is the response model, and its docstring is the description.
Errors never leak as tracebacks; they come back as problem details.
"""

import functools
import inspect
import typing
from collections.abc import Awaitable, Callable, Iterable, Sequence
from enum import Enum
from typing import Any

from fastapi import APIRouter

from xippios.core._loop import as_async
from xippios.core.errors import XippiosError
from xippios.core.http.problems import problem_response

__all__ = ["router_from_tasks"]


def _endpoint(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    target = as_async(fn)
    hints = typing.get_type_hints(fn)
    signature = inspect.signature(fn)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation)) for p in signature.parameters.values()
    ]
    returns = hints.get("return", signature.return_annotation)

    async def endpoint(*args: Any, **kwargs: Any) -> Any:
        try:
            return await target(*args, **kwargs)
        except XippiosError as exc:
            return problem_response(exc)

    functools.update_wrapper(endpoint, fn)
    endpoint.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=parameters, return_annotation=returns
    )
    endpoint.__annotations__ = {p.name: p.annotation for p in parameters} | {"return": returns}
    return endpoint


def router_from_tasks(
    source: str,
    tasks: Iterable[Callable[..., Any]],
    *,
    prefix: str | None = None,
    tags: Sequence[str | Enum] | None = None,
) -> APIRouter:
    """One ``GET`` route per task function, under ``/<source>`` and tagged with the source.

    Args:
        source: Source slug, e.g. ``"usda-nass"``; becomes the path prefix and the tag.
        tasks: Task functions. Parameters must be scalars so they map to query parameters.
        prefix: Path prefix; defaults to ``/<source>``.
        tags: OpenAPI tags; default to ``[source]``.
    """
    router = APIRouter(
        prefix=prefix if prefix is not None else f"/{source}",
        tags=list(tags) if tags else [source],
    )
    for fn in tasks:
        doc = inspect.getdoc(fn) or ""
        hints = typing.get_type_hints(fn)
        router.add_api_route(
            f"/{fn.__name__}",
            _endpoint(fn),
            methods=["GET"],
            name=f"{source}_{fn.__name__}",
            summary=doc.splitlines()[0] if doc else None,
            description=doc,
            response_model=hints.get("return"),
        )
    return router
