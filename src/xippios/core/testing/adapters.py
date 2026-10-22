"""Helpers for tests that go through the adapters or check projections."""

import json
from typing import Any

from pydantic import BaseModel

__all__ = ["assert_projection", "mcp_call"]


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


async def mcp_call(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    """Call a tool on an ``MCPServer`` in-process and return its JSON result, decoded.

    Fails the test when the server reports an error, or when the tool answered with the
    family's ``error: <Class>: <message>`` text instead of JSON.
    """
    from mcp.types import CallToolResult, TextContent

    result = await server.call_tool(name, arguments)
    assert isinstance(result, CallToolResult), result
    assert not result.is_error, result.content
    assert result.content, "tool returned no content"
    content = result.content[0]
    assert isinstance(content, TextContent), content
    if content.text.startswith("error:"):
        raise AssertionError(content.text)
    return json.loads(content.text)
