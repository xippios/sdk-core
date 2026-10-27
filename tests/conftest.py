import pytest

from xippios.core import redaction

# The plugin under test is the one every source enables; anyio_backend comes from it.
pytest_plugins = ["pytester", "xippios.core.testing.plugin"]


@pytest.fixture(autouse=True)
def _no_registered_credential_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no name a ``QueryKeyAuth`` registered.

    The registry is the process's (ADR-0019, decision 6): a ``QueryKeyAuth("key", ...)``
    built by one test would make ``key`` a credential in every test after it.
    """
    monkeypatch.setattr(redaction, "_registered", frozenset())
