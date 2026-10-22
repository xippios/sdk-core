"""Record a live upstream response into a fixture file.

This is what a source repo's ``record-fixture`` command calls. It goes through the
real client, so retries, rate limits and authentication behave as in production, and
error responses are recorded too rather than raised.
"""

from pathlib import Path
from typing import Any

from xippios.core._loop import sync
from xippios.core.client import AsyncClient, Params
from xippios.core.testing.fixtures import Fixture, write_fixture

__all__ = ["record", "record_sync"]


async def record(
    client: AsyncClient,
    path: str,
    fixture: Path,
    *,
    method: str = "GET",
    params: Params = None,
    json: Any = None,
) -> Fixture:
    """Perform one live request and write the scrubbed exchange to ``fixture``.

    Args:
        client: The source's configured client.
        path: Request path, e.g. ``"/api/api_GET"``.
        fixture: Destination file, usually from ``fixture_path``.
        method: HTTP method.
        params: Query parameters.
        json: JSON body for write methods.
    """
    response = await client.request(method, path, params=params, json=json, raise_on_error=False)
    return write_fixture(response, fixture)


record_sync = sync(record)
