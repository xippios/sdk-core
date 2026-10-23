"""Test support shared by every source repo (conventions §10).

Four things live here: the pytest plugin, which gates live tests and keeps the run
offline (no network for the session; no rate-limit wait and a placeholder key in every
test not marked live; ADR-0013), fixture recording with secrets scrubbed in memory and
verified before the write (``Scrub``), fixture replay through ``respx``, and checks for
adapters (``mcp_call``, ``assert_write_tools``).
Enable the plugin in a repo's ``tests/conftest.py``::

    pytest_plugins = ["xippios.core.testing.plugin"]

Requires the ``testing`` extra: ``uv add "xippios-core[testing]"``.
"""

try:
    import pytest  # noqa: F401
    import respx  # noqa: F401
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "xippios.core.testing needs the 'testing' extra: uv add 'xippios-core[testing]'"
    ) from exc

from xippios.core.testing.adapters import assert_projection, assert_write_tools, mcp_call
from xippios.core.testing.fixtures import (
    Fixture,
    FixtureRequest,
    FixtureResponse,
    fixture_from_response,
    fixture_path,
    load_fixture,
    write_fixture,
)
from xippios.core.testing.plugin import LIVE_ENV, PLACEHOLDER_KEY, live_enabled
from xippios.core.testing.record import record, record_sync
from xippios.core.testing.replay import ReplayFixture, mount_fixture, replay, sent_urls
from xippios.core.testing.scrub import REDACTED, Scrub, scrub_headers, scrub_params, scrub_url

__all__ = [
    "LIVE_ENV",
    "PLACEHOLDER_KEY",
    "REDACTED",
    "Fixture",
    "FixtureRequest",
    "FixtureResponse",
    "ReplayFixture",
    "Scrub",
    "assert_projection",
    "assert_write_tools",
    "fixture_from_response",
    "fixture_path",
    "live_enabled",
    "load_fixture",
    "mcp_call",
    "mount_fixture",
    "record",
    "record_sync",
    "replay",
    "scrub_headers",
    "scrub_params",
    "scrub_url",
    "sent_urls",
    "write_fixture",
]
