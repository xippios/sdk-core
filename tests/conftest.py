import pytest

from xippios.core import redaction

# The plugin under test is the one every source enables; anyio_backend comes from it.
pytest_plugins = ["pytester", "xippios.core.testing.plugin"]


@pytest.fixture(autouse=True)
def _no_registered_credential_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no name a query key registered.

    The registry is the process's, by source (ADR-0040, decision 6): a ``KeyAuth(...,
    location="query", name="key", source="example")`` built by one test would make ``key`` a
    credential of ``example`` in every test after it.
    """
    monkeypatch.setattr(redaction, "_registered", {})


@pytest.fixture(autouse=True)
def _no_declared_data_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with no name a source declared as data.

    The declarations are the process's too: ``register_data_name("next_token",
    source="example")`` in one test would keep ``next_token`` as data of ``example`` in every
    test after it.
    """
    monkeypatch.setattr(redaction, "_data_names", {})
