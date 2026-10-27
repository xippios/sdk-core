"""Build a FastAPI router from task functions.

A task whose parameters are all scalars becomes ``GET /<source>/<function>`` with query
parameters. A task with any non-scalar parameter (a mapping, a list, a model) becomes
``POST /<source>/<function>`` whose JSON body is an object keyed by parameter name
(ADR-0007). Either way the return annotation is the response model and the docstring the
description, and errors come back as problem details, never as tracebacks. A task its
``tasks.py`` names in ``BULK_TASKS`` gets no route (ADR-0019).
"""

import functools
import inspect
import types
import typing
from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, create_model

from xippios.core._loop import as_async, is_bulk_task
from xippios.core.errors import XippiosError
from xippios.core.http.problems import problem_response

__all__ = ["is_scalar", "router_from_tasks"]

_SCALARS: tuple[type, ...] = (str, int, float, bool, Decimal, date, datetime, Enum)


def is_scalar(annotation: Any) -> bool:
    """True when a parameter annotation maps onto one query parameter.

    Scalars are ``str``, numbers, ``bool``, ``Decimal``, dates, enums, literals, and
    optionals, unions and ``Annotated`` forms of those. Anything else (mappings, lists,
    models) needs a JSON body.
    """
    if annotation is inspect.Parameter.empty or annotation is Any:
        return True
    origin = typing.get_origin(annotation)
    if origin is typing.Annotated:
        return is_scalar(typing.get_args(annotation)[0])
    if origin is typing.Literal:
        return True
    if origin is types.UnionType or origin is typing.Union:
        return all(is_scalar(arg) for arg in typing.get_args(annotation))
    if isinstance(annotation, type):
        return annotation is type(None) or issubclass(annotation, _SCALARS)
    return False


def _resolved(fn: Callable[..., Any]) -> tuple[inspect.Signature, list[inspect.Parameter], Any]:
    hints = typing.get_type_hints(fn)
    signature = inspect.signature(fn)
    parameters = [
        p.replace(annotation=hints.get(p.name, p.annotation)) for p in signature.parameters.values()
    ]
    return signature, parameters, hints.get("return", signature.return_annotation)


def _query_endpoint(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    target = as_async(fn)
    signature, parameters, returns = _resolved(fn)

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


def _body_endpoint(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    target = as_async(fn)
    _, parameters, returns = _resolved(fn)
    fields: dict[str, Any] = {
        p.name: (
            Any if p.annotation is inspect.Parameter.empty else p.annotation,
            ... if p.default is inspect.Parameter.empty else p.default,
        )
        for p in parameters
    }
    args_model: type[BaseModel] = create_model(f"{fn.__name__}_args", **fields)

    async def endpoint(payload: BaseModel) -> Any:
        try:
            return await target(**{name: getattr(payload, name) for name in fields})
        except XippiosError as exc:
            return problem_response(exc)

    functools.update_wrapper(endpoint, fn)
    payload = inspect.Parameter(
        "payload", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=args_model
    )
    endpoint.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=[payload], return_annotation=returns
    )
    endpoint.__annotations__ = {"payload": args_model, "return": returns}
    return endpoint


def router_from_tasks(
    source: str,
    tasks: Iterable[Callable[..., Any]],
    *,
    prefix: str | None = None,
    tags: Sequence[str | Enum] | None = None,
) -> APIRouter:
    """One route per task function under ``/<source>``, tagged with the source.

    Scalar-only signatures become ``GET`` with query parameters; any non-scalar
    parameter makes the route a ``POST`` with a JSON body keyed by parameter name. A
    task the module that defines it names in ``BULK_TASKS`` gets no route: a bulk task
    returns a file, or a list read from one, and is Python-only; no route returns a file
    path (conventions §9, ADR-0019). So an adapter may pass every name of
    ``tasks.__all__``.

    Args:
        source: Source slug, e.g. ``"usda-nass"``; becomes the path prefix and the tag.
        tasks: Task functions, e.g. ``[getattr(tasks, n) for n in tasks.__all__]``; one
            in its module's ``BULK_TASKS`` is skipped.
        prefix: Path prefix; defaults to ``/<source>``.
        tags: OpenAPI tags; default to ``[source]``.
    """
    router = APIRouter(
        prefix=prefix if prefix is not None else f"/{source}",
        tags=list(tags) if tags else [source],
    )
    for fn in tasks:
        if is_bulk_task(fn):
            continue
        doc = inspect.getdoc(fn) or ""
        _, parameters, returns = _resolved(fn)
        scalar_only = all(is_scalar(p.annotation) for p in parameters)
        router.add_api_route(
            f"/{fn.__name__}",
            _query_endpoint(fn) if scalar_only else _body_endpoint(fn),
            methods=["GET" if scalar_only else "POST"],
            name=f"{source}_{fn.__name__}",
            summary=doc.splitlines()[0] if doc else None,
            description=doc,
            response_model=returns if returns is not inspect.Signature.empty else None,
        )
    return router
