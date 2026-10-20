from typing import Any

import pytest

from xippios.core.mcp import build_parser, build_server, main


def test_parser_defaults() -> None:
    args = build_parser("x").parse_args([])
    assert (args.http, args.host, args.port) == (False, "127.0.0.1", 8000)


def test_main_dispatches_to_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_server("example", [])
    calls: list[tuple[Any, ...]] = []

    def fake_run(transport: str = "stdio", **kwargs: Any) -> None:
        calls.append((transport, kwargs))

    monkeypatch.setattr(server, "run", fake_run)
    main(server, [])
    main(server, ["--http", "--host", "0.0.0.0", "--port", "9000"])
    assert calls == [
        ("stdio", {}),
        ("streamable-http", {"host": "0.0.0.0", "port": 9000}),
    ]
