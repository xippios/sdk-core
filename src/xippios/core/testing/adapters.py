"""Helpers for tests that go through the adapters, check projections or a write server."""

import inspect
import json
import re
import types
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Literal

import httpx
import respx
from pydantic import BaseModel

from xippios.core.client.retry import IDEMPOTENT_METHODS
from xippios.core.models import Result

__all__ = ["assert_projection", "assert_write_tools", "mcp_call", "mcp_call_text"]

type DryRun = Mapping[str, Mapping[str, Any] | Sequence[Mapping[str, Any]]]
"""The arguments of the dry run: a write task's name to one call's arguments, or a list."""


def assert_projection(projected: BaseModel, source: BaseModel, **overrides: Any) -> None:
    """Check that ``projected`` is a faithful projection of ``source`` (ADR-0031).

    Every field of ``projected`` must exist on ``source`` and carry the same value,
    except the fields named in ``overrides``, which must carry the given values.
    """
    fields = set(type(projected).model_fields)
    unknown = sorted(name for name in overrides if name not in fields)
    assert not unknown, f"overrides for fields {type(projected).__name__} does not have: {unknown}"
    foreign = sorted(name for name in fields if name not in overrides and not hasattr(source, name))
    assert not foreign, (
        f"{type(projected).__name__} fields missing on {type(source).__name__}: {foreign}"
    )
    for name in fields:
        expected = overrides[name] if name in overrides else getattr(source, name)
        actual = getattr(projected, name)
        assert actual == expected, f"{name}: {actual!r} != {expected!r}"


_ERROR_TEXT = re.compile(r"error: [A-Za-z_][A-Za-z0-9_]*: ")
"""The start of the family's error text, ``error: <ErrorClass>: `` (conventions §8)."""


async def mcp_call_text(server: Any, name: str, arguments: dict[str, Any]) -> str:
    """Call a tool on an ``MCPServer`` through an in-process client and return its text.

    The call goes through ``mcp.Client(server)``, as a real client's would, so the
    server's middleware runs: an argument the tool does not declare and arguments its
    schema refuses come back here as the family's ``error: InvalidRequestError: ...``
    text, which a test can assert. An error answer is flagged ``is_error`` beside that
    text (conventions §8; ADR-0026, decision 6), and its text is returned as well. Fails
    the test when the server reports an MCP error of another kind, flagged with any other
    text (e.g. an unknown tool or a task that crashed), or answers with anything but text.

    Args:
        server: The ``MCPServer`` under test, e.g. from ``build_server``.
        name: The tool name, e.g. ``"example_get_series"``.
        arguments: The tool arguments, e.g. ``{"series_id": "CORN"}``.
    """
    from mcp.client import Client
    from mcp.types import TextContent

    async with Client(server) as client:
        result = await client.call_tool(name, arguments)
    assert result.content, "tool returned no content"
    content = result.content[0]
    assert isinstance(content, TextContent), content
    if result.is_error:
        assert _ERROR_TEXT.match(content.text), result.content
    return content.text


async def mcp_call(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool on an ``MCPServer`` through an in-process client; its JSON, decoded.

    Like ``mcp_call_text``, so the server's middleware runs, and fails the test as well
    when the tool answered with the family's ``error: <Class>: <message>`` text instead
    of JSON.
    """
    text = await mcp_call_text(server, name, arguments)
    if text.startswith("error:"):
        raise AssertionError(text)
    return json.loads(text)


async def assert_write_tools(
    write_server: Any,
    write_tasks: Iterable[Callable[..., Any]],
    *,
    source: str,
    read_server: Any = None,
    router: Any = None,
    preview_reads: bool = False,
    dry_run: DryRun | None = None,
    sent: respx.Router | None = None,
    is_read: Callable[[httpx.Request], bool] | None = None,
) -> None:
    """Check a write server against its write tasks, and their previews (conventions §8).

    Fails the test, naming the offending tool, unless all of these hold:

    - the write server was registered with ``read_only=False`` (``is_write_server``),
      which ``main``'s loopback rule for ``--http`` depends on;
    - the write server's tools are exactly ``tool_name(source, fn)`` for the write
      tasks, no more and no fewer;
    - every write task takes ``confirm: bool = False`` as its last parameter, so a call
      without it is a dry run;
    - no write tool is on ``read_server``, and no route of ``router`` serves a write
      task (matched by the route name and path ``router_from_tasks`` gives it), when
      given.

    A write server exposes write tools only: reference tools, the tenant list of
    ``list_task`` among them, stay on the read server. A server a ``TenantLock`` binds is
    checked against its bound tasks, ``bind_tasks(tasks, lock)``, whose names and
    ``confirm`` stay. Async: the tools are listed on the test's own loop, so a test calls
    it as ``await assert_write_tools(...)`` under ``@pytest.mark.anyio``.

    The preview is held in two parts, each off by default (ADR-0050). With
    ``preview_reads=True`` every write task's return annotation is a ``Result`` whose
    data has exactly one member tagged ``performed: Literal[False]``, the preview, a
    union's member or a ``type`` alias's, and that member declares ``reads: list[str]``,
    the operations the preview read. With ``dry_run`` each write tool is called on the
    write server without ``confirm``, as an agent calls it, once for each set of
    arguments, and its answer must be the preview, ``performed`` false, that sent no
    request but a read, with ``reads`` empty exactly when it sent no request at all. The
    dry run holds ``preview_reads`` too, and every argument set is checked before the
    first tool is called. A request the router does not answer fails its call with
    ``respx``'s error.

    Args:
        write_server: The ``MCPServer`` behind ``xippios-<source>-mcp-write``, built
            with ``read_only=False``.
        write_tasks: The task functions it must expose, e.g.
            ``[getattr(tasks_write, name) for name in tasks_write.__all__]``.
        source: Source slug, e.g. ``"cashctrl"``.
        read_server: The source's read server, ``xippios-<source>-mcp-read``, if any.
        router: The source's FastAPI router from ``router_from_tasks``, if any.
        preview_reads: Hold each write task's annotations to one preview that declares
            ``reads``.
        dry_run: The arguments of a call of each write task, without ``confirm``, keyed
            by the task function's ``__name__``, one mapping or a list of them, e.g.
            ``{"create_entry": {"org": "demo", "amount": "1.00"}, "update_entry":
            [{"org": "demo", "id": 52}]}``. Every write task needs one at least.
        sent: The ``respx`` router the test's routes are mounted on, usually the
            ``respx_mock`` fixture, whose calls tell what each call of the dry run sent.
            Required with ``dry_run``.
        is_read: Whether a request the dry run saw is a read, for an upstream that reads
            through ``POST`` or a read that sends a token request first; by default a
            request whose method is ``GET``, ``HEAD`` or ``OPTIONS``, the methods core's
            retry rule repeats (``IDEMPOTENT_METHODS``, ADR-0011).

    Raises:
        TypeError: ``dry_run`` without ``sent``, or ``sent`` or ``is_read`` without
            ``dry_run``.
    """
    from xippios.core.mcp.server import _confirm_problem, is_write_server, tool_name

    if dry_run is not None and sent is None:
        raise TypeError(
            "dry_run needs sent=, the respx router the test's routes are mounted on, "
            "e.g. the respx_mock fixture"
        )
    if dry_run is None and (sent is not None or is_read is not None):
        raise TypeError("sent= and is_read= serve the dry run; pass dry_run= with them")
    assert is_write_server(write_server), (
        "the write server was not registered with read_only=False; the loopback rule depends on it"
    )
    expected = {tool_name(source, fn): fn for fn in write_tasks}
    listed = await _tool_names(write_server)
    unexpected = sorted(listed - expected.keys())
    assert not unexpected, f"write server tools that are not write tasks: {unexpected}"
    missing = sorted(expected.keys() - listed)
    assert not missing, f"write tasks missing from the write server: {missing}"
    for name, fn in expected.items():
        problem = _confirm_problem(fn)
        if problem is None and list(inspect.signature(fn).parameters)[-1] != "confirm":
            problem = "confirm is not the last parameter"
        assert problem is None, f"{name}: {problem}; a write tool takes confirm: bool = False last"
    if read_server is not None:
        on_read = sorted(expected.keys() & await _tool_names(read_server))
        assert not on_read, f"write tools on the read server: {on_read}"
    if router is not None:
        for name, fn in expected.items():
            for route in router.routes:
                path = str(getattr(route, "path", ""))
                methods = " ".join(sorted(getattr(route, "methods", None) or ()))
                served = _serves(route, source, fn)
                assert not served, f"{name}: a write task has an HTTP route, {methods} {path}"
    if preview_reads or dry_run is not None:
        for name, fn in expected.items():
            problem = _preview_problem(fn)
            assert problem is None, f"{name}: {problem}"
    if dry_run is not None and sent is not None:
        calls = _dry_run_calls(expected, dry_run)
        for name, arguments in calls:
            start = len(sent.calls)
            text = await mcp_call_text(write_server, name, arguments)
            requests = [call.request for call in sent.calls[start:]]
            _judge_preview(name, text, requests, is_read or _by_method)


def _by_method(request: httpx.Request) -> bool:
    """The dry run's default read: a method core's retry rule repeats (ADR-0011, decision 2)."""
    return request.method in IDEMPOTENT_METHODS


def _members(data: Any) -> tuple[Any, ...]:
    """The members of a ``Result``'s data: a union's, through a ``type`` alias, or itself."""
    if isinstance(data, typing.TypeAliasType):
        return _members(data.__value__)
    if typing.get_origin(data) in (typing.Union, types.UnionType):
        return typing.get_args(data)
    return (data,)


def _is_preview(member: Any) -> bool:
    """True when ``member`` is a model whose ``performed`` is annotated ``Literal[False]``."""
    if not (isinstance(member, type) and issubclass(member, BaseModel)):
        return False
    field = member.model_fields.get("performed")
    if field is None or typing.get_origin(field.annotation) is not Literal:
        return False
    tags = typing.get_args(field.annotation)
    return len(tags) == 1 and tags[0] is False


def _preview_problem(fn: Callable[..., Any]) -> str | None:
    """Why ``fn``'s answer holds no preview that declares ``reads``; ``None`` when it does.

    The return annotation is resolved with ``typing.get_type_hints``, through a sync
    facade's or a bound task's wrapper, and must be a ``Result`` whose data holds exactly
    one member tagged ``performed: Literal[False]``, which declares ``reads: list[str]``
    (ADR-0050, decision 4).
    """
    returned = typing.get_type_hints(fn).get("return", inspect.signature(fn).return_annotation)
    if returned is inspect.Signature.empty:
        return "its return is not annotated; a write task returns a Result that holds its preview"
    metadata = getattr(returned, "__pydantic_generic_metadata__", None) or {}
    if metadata.get("origin") is not Result:
        shown = returned.__name__ if isinstance(returned, type) else repr(returned)
        return f"returns {shown}, not a Result whose data holds the preview"
    previews = [member for member in _members(metadata["args"][0]) if _is_preview(member)]
    if not previews:
        return "no member of its Result's data is tagged performed: Literal[False], the preview"
    if len(previews) > 1:
        names = ", ".join(member.__name__ for member in previews)
        return (
            f"{len(previews)} members of its Result's data are tagged performed: "
            f"Literal[False]: {names}; one is the preview"
        )
    (preview,) = previews
    field = preview.model_fields.get("reads")
    if field is None or field.annotation != list[str]:
        return (
            f"the preview {preview.__name__} declares no reads: list[str], the operations it read"
        )
    return None


def _dry_run_calls(
    tools: Mapping[str, Callable[..., Any]], dry_run: DryRun
) -> list[tuple[str, dict[str, Any]]]:
    """Each call of the dry run, its tool's name and arguments, in the write tasks' order.

    Every argument set is checked before any tool is called: each write task has one at
    least, each key names a write task by its ``__name__``, and none passes ``confirm``.
    """
    by_task = {fn.__name__: name for name, fn in tools.items()}
    unknown = sorted(dry_run.keys() - by_task.keys())
    assert not unknown, (
        f"dry_run names no write task: {unknown}; a key is the task function's __name__"
    )
    missing = sorted(by_task.keys() - dry_run.keys())
    assert not missing, (
        f"dry_run gives no arguments for the write tasks {missing}; "
        "the dry run calls each write tool"
    )
    calls: list[tuple[str, dict[str, Any]]] = []
    for task, name in by_task.items():
        given = dry_run[task]
        sets = [given] if isinstance(given, Mapping) else list(given)
        assert sets, f"{name}: dry_run gives it no arguments"
        for arguments in sets:
            assert "confirm" not in arguments, (
                f"{name}: a dry run calls without confirm; drop it from dry_run"
            )
            calls.append((name, dict(arguments)))
    return calls


def _described(requests: Sequence[httpx.Request]) -> str:
    """The requests as messages name one, method and path: never the host nor the query."""
    return ", ".join(f"{request.method} {request.url.path}" for request in requests)


def _judge_preview(
    name: str,
    text: str,
    requests: Sequence[httpx.Request],
    is_read: Callable[[httpx.Request], bool],
) -> None:
    """Fail the dry run's call of ``name`` unless it answered a preview true to its reads."""
    writes = [request for request in requests if not is_read(request)]
    assert not writes, (
        f"{name}: the preview sent a request that is no read, {_described(writes)}; "
        "a preview sends no write"
    )
    assert not text.startswith("error:"), f"{name}: the dry run answered {text}"
    try:
        data = json.loads(text).get("data")
    except ValueError:
        raise AssertionError(f"{name}: the dry run's answer is no JSON, the cap cut it") from None
    performed = data.get("performed") if isinstance(data, dict) else None
    assert performed is False, (
        f"{name}: the dry run's answer is no preview, performed is {performed}"
    )
    reads = data.get("reads")
    listed = isinstance(reads, list) and all(isinstance(read, str) for read in reads)
    assert listed, f"{name}: the preview carries no reads, the list of the operations it read"
    if requests:
        assert reads, f"{name}: the preview sent {_described(requests)} and its reads is empty"
    else:
        assert not reads, f"{name}: the preview's reads names {reads} and it sent no request"


async def _tool_names(server: Any) -> set[str]:
    return {tool.name for tool in await server.list_tools()}


def _serves(route: Any, source: str, fn: Callable[..., Any]) -> bool:
    """True when ``route`` is the one ``router_from_tasks`` builds for ``fn``.

    ``router_from_tasks`` names it ``<source>_<function>`` and puts it at
    ``<prefix>/<function>``; either is enough, so a custom prefix is caught too.
    """
    named = getattr(route, "name", None) == f"{source}_{fn.__name__}"
    return named or str(getattr(route, "path", "")).endswith(f"/{fn.__name__}")
