"""Helpers for tests that go through the adapters or check projections."""

import json
from typing import Any

from pydantic import BaseModel

__all__ = ["assert_projection", "mcp_call", "mcp_call_text"]


def assert_projection(projected: BaseModel, source: BaseModel, **overrides: Any) -> None:
    """Check that ``projected`` is a faithful projection of ``source`` (ADR-0008).

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


async def mcp_call_text(server: Any, name: str, arguments: dict[str, Any]) -> str:
    """Call a tool on an ``MCPServer`` through an in-process client and return its text.

    The call goes through ``mcp.Client(server)``, as a real client's would, so the
    server's middleware runs: arguments the tool's schema refuses come back here as the
    family's ``error: InvalidRequestError: ...`` text, which a test can assert. Fails the
    test when the server reports an MCP error (``is_error``, e.g. an unknown tool or a
    task that crashed) or answers with anything but text.

    Args:
        server: The ``MCPServer`` under test, e.g. from ``build_server``.
        name: The tool name, e.g. ``"example_get_series"``.
        arguments: The tool arguments, e.g. ``{"series_id": "CORN"}``.
    """
    from mcp.client import Client
    from mcp.types import TextContent

    async with Client(server) as client:
        result = await client.call_tool(name, arguments)
    assert not result.is_error, result.content
    assert result.content, "tool returned no content"
    content = result.content[0]
    assert isinstance(content, TextContent), content
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
