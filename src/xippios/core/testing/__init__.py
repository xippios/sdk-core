"""Test support shared by every source repo (conventions §10).

Six things live here: the pytest plugin, which gates live tests and keeps the run
offline (no network for the session; no rate-limit wait and a placeholder key in every
test not marked live; ADR-0035); fixture recording, one request sent once and read up
to a bound, a final answer only, with secrets scrubbed in memory and verified before the
write (``Scrub``), a large answer cut on request (``max_bytes=``, ADR-0040), a source's
own rewrite step run and checked before the write (``rewrite=``, a ``Rewrite``), the one
send without the write (``send_once``) and the writer (``write_fixture``, ``fixture_text``;
ADR-0048), and the recording of every exchange of a task, all written or none
(``record_task``; ADR-0057); fixture replay through ``respx``, with what was sent and
recorded as plain values (``sent_urls``, ``sent_query``, ``sent_bodies``,
``recorded_query``, ``response_from_fixture``);
helpers for adapters (``mcp_call``, ``mcp_call_text``, ``assert_write_tools`` for a write
server), for times read around a call (``assert_time_between``) and for a multi-tenant
source's environment (``keep_reserved_tenants``); the family conformance check,
``xippios.core.testing.family``, which a source collects by importing it into
``tests/test_family.py``; and the check of a built answer's mark,
``xippios.core.testing.built_answers``, collected likewise into
``tests/test_built_answers.py`` (ADR-0064). Neither check is imported here. The nightly
comparison of a packaged list with the list upstream serves now,
``xippios.core.testing.live``, a source collects the same way into ``tests/test_live.py``,
beside its ``LIVE_LISTS`` and ``NO_LIVE_LIST``; its assertion, ``assert_list_current``,
stays in that module, which calls it, since no source imports it (ADR-0055; ADR-0059,
decision 3).
Enable the plugin in a repo's ``tests/conftest.py``::

    pytest_plugins = ["xippios.core.testing.plugin"]

This package exports what consumers import. The pieces the plugin and the recorder
are built from (``replay``, ``mount_fixture``, ``REQUEST_ID_HEADERS``, the ``scrub_*``
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
from xippios.core.testing.environment import keep_reserved_tenants
from xippios.core.testing.fixtures import (
    Fixture,
    FixtureResponse,
    Rewrite,
    fixture_from_response,
    fixture_path,
    fixture_text,
    load_fixture,
    recorded_query,
    response_from_fixture,
    write_fixture,
)
from xippios.core.testing.record import (
    record,
    record_sync,
    record_task,
    record_task_sync,
    send_once,
    send_once_sync,
)
from xippios.core.testing.replay import ReplayFixture, sent_bodies, sent_query, sent_urls
from xippios.core.testing.scrub import REDACTED, Scrub

__all__ = [
    "CLOCK_SLACK",
    "REDACTED",
    "Fixture",
    "FixtureResponse",
    "ReplayFixture",
    "Rewrite",
    "Scrub",
    "assert_projection",
    "assert_time_between",
    "assert_write_tools",
    "fixture_from_response",
    "fixture_path",
    "fixture_text",
    "keep_reserved_tenants",
    "load_fixture",
    "mcp_call",
    "mcp_call_text",
    "record",
    "record_sync",
    "record_task",
    "record_task_sync",
    "recorded_query",
    "response_from_fixture",
    "send_once",
    "send_once_sync",
    "sent_bodies",
    "sent_query",
    "sent_urls",
    "write_fixture",
]
