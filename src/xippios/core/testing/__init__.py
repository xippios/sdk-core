"""Test support shared by every source repo (conventions §10).

Five things live here: the pytest plugin, which gates live tests and keeps the run
offline (no network for the session; no rate-limit wait and a placeholder key in every
test not marked live; ADR-0013); fixture recording with secrets scrubbed in memory and
verified before the write (``Scrub``); fixture replay through ``respx``, with what was
sent and recorded as plain values (``sent_urls``, ``sent_query``, ``recorded_query``,
``response_from_fixture``); checks for adapters (``mcp_call``, ``mcp_call_text``,
``assert_write_tools``) and for times read around a call (``assert_time_between``); and
the family conformance check, ``xippios.core.testing.family``, which a source collects
by importing it into ``tests/test_family.py`` and which is not imported here.
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

from xippios.core.testing.adapters import (
    assert_projection,
    assert_write_tools,
    mcp_call,
    mcp_call_text,
)
from xippios.core.testing.clock import CLOCK_SLACK, assert_time_between
from xippios.core.testing.fixtures import (
    Fixture,
    FixtureRequest,
    FixtureResponse,
    fixture_from_response,
    fixture_path,
    load_fixture,
    recorded_query,
    response_from_fixture,
    write_fixture,
)
from xippios.core.testing.plugin import LIVE_ENV, PLACEHOLDER_KEY, live_enabled
from xippios.core.testing.record import record, record_sync
from xippios.core.testing.replay import (
    ReplayFixture,
    mount_fixture,
    replay,
    sent_query,
    sent_urls,
)
from xippios.core.testing.scrub import REDACTED, Scrub, scrub_headers, scrub_params, scrub_url

__all__ = [
    "CLOCK_SLACK",
    "LIVE_ENV",
    "PLACEHOLDER_KEY",
    "REDACTED",
    "Fixture",
    "FixtureRequest",
    "FixtureResponse",
    "ReplayFixture",
    "Scrub",
    "assert_projection",
    "assert_time_between",
    "assert_write_tools",
    "fixture_from_response",
    "fixture_path",
    "live_enabled",
    "load_fixture",
    "mcp_call",
    "mcp_call_text",
    "mount_fixture",
    "record",
    "record_sync",
    "recorded_query",
    "replay",
    "response_from_fixture",
    "scrub_headers",
    "scrub_params",
    "scrub_url",
    "sent_query",
    "sent_urls",
    "write_fixture",
]
