import logging
from collections.abc import Iterator

import pytest

pytest_plugins = ["pytester", "xippios.core.testing.plugin"]

REQUEST_LOGGERS = ("httpx", "httpcore")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _restore_request_logger_levels() -> Iterator[None]:
    """Building an MCP server sets the httpx and httpcore levels; undo that after each test."""
    saved = {name: logging.getLogger(name).level for name in REQUEST_LOGGERS}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)
