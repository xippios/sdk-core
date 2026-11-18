"""Helpers for tests that go through the adapters, check projections or a write server."""

import inspect
import json
import re
from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel

__all__ = ["assert_projection", "assert_write_tools", "mcp_call", "mcp_call_text"]


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
) -> None:
    """Check a write server against its write tasks (conventions §8).

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

    Args:
        write_server: The ``MCPServer`` behind ``xippios-<source>-mcp-write``, built
            with ``read_only=False``.
        write_tasks: The task functions it must expose, e.g.
            ``[getattr(tasks_write, name) for name in tasks_write.__all__]``.
        source: Source slug, e.g. ``"cashctrl"``.
        read_server: The source's read server, ``xippios-<source>-mcp-read``, if any.
        router: The source's FastAPI router from ``router_from_tasks``, if any.
    """
    from xippios.core.mcp.server import _confirm_problem, is_write_server, tool_name

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


async def _tool_names(server: Any) -> set[str]:
    return {tool.name for tool in await server.list_tools()}


def _serves(route: Any, source: str, fn: Callable[..., Any]) -> bool:
    """True when ``route`` is the one ``router_from_tasks`` builds for ``fn``.

    ``router_from_tasks`` names it ``<source>_<function>`` and puts it at
    ``<prefix>/<function>``; either is enough, so a custom prefix is caught too.
    """
    named = getattr(route, "name", None) == f"{source}_{fn.__name__}"
    return named or str(getattr(route, "path", "")).endswith(f"/{fn.__name__}")
