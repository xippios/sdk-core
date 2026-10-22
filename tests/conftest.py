import pytest

pytest_plugins = ["pytester", "xippios.core.testing.plugin"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
