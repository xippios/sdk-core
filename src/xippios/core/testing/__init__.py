"""Test support shared by every source repo (conventions §10).

Five things live here: the pytest plugin, which gates live tests and keeps the run
offline (no network for the session; no rate-limit wait and a placeholder key in every
test not marked live; ADR-0013); fixture recording with secrets scrubbed in memory and
verified before the write (``Scrub``), a large answer cut on request (``max_bytes=``,
ADR-0019); fixture replay through ``respx``, with what was sent and recorded as plain
values (``sent_urls``, ``sent_query``, ``recorded_query``, ``response_from_fixture``);
checks for adapters (``mcp_call``, ``mcp_call_text``,
``assert_write_tools``) and for times read around a call (``assert_time_between``); and
the family conformance check, ``xippios.core.testing.family``, which a source collects
by importing it into ``tests/test_family.py`` and which is not imported here.
Enable the plugin in a repo's ``tests/conftest.py``::

    pytest_plugins = ["xippios.core.testing.plugin"]

This package exports what consumers import. The pieces the plugin and the recorder
are built from (``replay``, ``mount_fixture``, ``write_fixture``, the ``scrub_*``
functions, ``LIVE_ENV``, ``PLACEHOLDER_KEY``, ...) are importable from their modules,
``xippios.core.testing.replay``, ``.fixtures``, ``.scrub`` and ``.plugin``.

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
    FixtureResponse,
    fixture_from_response,
    fixture_path,
    load_fixture,
    recorded_query,
    response_from_fixture,
)
from xippios.core.testing.record import record, record_sync
from xippios.core.testing.replay import ReplayFixture, sent_query, sent_urls
from xippios.core.testing.scrub import REDACTED, Scrub

__all__ = [
    "CLOCK_SLACK",
    "REDACTED",
    "Fixture",
    "FixtureResponse",
    "ReplayFixture",
    "Scrub",
    "assert_projection",
    "assert_time_between",
    "assert_write_tools",
    "fixture_from_response",
    "fixture_path",
    "load_fixture",
    "mcp_call",
    "mcp_call_text",
    "record",
    "record_sync",
    "recorded_query",
    "response_from_fixture",
    "sent_query",
    "sent_urls",
]
