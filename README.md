# xippios-core

Shared foundation of the [xippios](https://github.com/xippios) Python SDK family. Every
`xippios-<source>` package depends on it; nothing in it knows about any particular
upstream API.

It gives a source package the things that should be identical across the family:

- **HTTP client** on `httpx` with retries, a per-source rate limiter, an optional
  response cache (off by default; the in-memory one is bounded by TTL and size),
  explicit timeouts and one `User-Agent`. Async at the core, a sync facade on top.
- **Auth helpers** that read the key from the environment on the first request:
  query parameter, header, bearer token or basic auth.
- **Error taxonomy**: `ConfigError`, `AuthError`, `RateLimitError`, `NotFoundError`,
  `ValidationError`, `UpstreamError`, `TransportError`, all under `XippiosError`.
- **Result envelope**: every task function returns `Result[T]` with `ResultMeta`
  (source, endpoint, retrieved_at, published_at, vintage, request).
- **Reference-data loader** for code lists shipped inside a package.
- **Adapters** that turn task functions into MCP tools (`xippios.core.mcp`) and FastAPI
  routes (`xippios.core.http`) without any logic of their own.
- **Test support**: a live-test gate, fixture recording with secrets scrubbed, and
  replay through `respx` (`xippios.core.testing`).

## Install

```bash
uv add xippios-core                 # client, models, errors, reference, pagination
uv add "xippios-core[mcp]"          # + MCP server helpers (official mcp SDK 2.x)
uv add "xippios-core[http]"         # + FastAPI router helpers
uv add "xippios-core[testing]"      # + pytest plugin, respx replay, fixture recording
```

Python 3.12 or later.

## 30-second example

A source package writes its task function once, async, and derives the sync one:

```python
from pydantic import Field

from xippios.core import (
    AsyncClient,
    ClientConfig,
    QueryKeyAuth,
    RateLimit,
    Result,
    ResultMeta,
    UpstreamModel,
    parse,
    sync,
)

client = AsyncClient(
    ClientConfig(
        source="example",
        version="0.1.0",
        base_url="https://api.example.org",
        rate_limit=RateLimit(per_minute=60),
    ),
    auth=QueryKeyAuth("key", "EXAMPLE_API_KEY", source="example"),  # read on first request
)


class Series(UpstreamModel):
    series_id: str = Field(alias="seriesId")
    value: float


async def get_series_async(series_id: str, year: int = 2024) -> Result[list[Series]]:
    """Fetch one series for a year.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN_YIELD"``.
        year: Four-digit year, e.g. ``2024``.
    """
    params = {"id": series_id, "year": year}
    raw = await client.get_json("/v1/series", params=params)
    rows = parse(list[Series], raw["data"], source="example", endpoint="series")
    meta = ResultMeta(source="example", endpoint="series", request=params)
    return Result(data=rows, meta=meta)


get_series = sync(get_series_async)  # same signature, same docstring, blocks until done
```

```python
>>> result = get_series("CORN_YIELD", year=2024)
>>> result.data[0].value, result.meta.retrieved_at
(177.3, datetime.datetime(2026, 10, 20, 12, 0, tzinfo=datetime.timezone.utc))
```

`meta.request` is provenance, not a copy of the call: `ResultMeta` redacts any key that
looks like a credential (`key`, `token`, `secret`, ...) so an envelope is safe to hand
to an agent or return over HTTP.

Upstream failures arrive as taxonomy errors, never as raw `httpx` exceptions:

```python
from xippios.core import NotFoundError, RateLimitError

try:
    get_series("NOPE")
except NotFoundError as exc:
    print(exc)  # 404 from GET api.example.org/v1/series: ...
except RateLimitError as exc:
    print(exc.retry_after)
```

## MCP server in five lines

```python
# xippios/example/mcp.py
from xippios.core.mcp import build_server, main
from xippios.example import tasks

server = build_server("example", [tasks.get_series, tasks.list_commodities])


def run() -> None:  # entry point: xippios-example-mcp = "xippios.example.mcp:run"
    main(server)
```

Tool names are `<source>_<function>` (`example_get_series`), the docstring is the tool
description, the signature is the input schema. Results are capped at 200 rows or
64 KB with a note on how to narrow the query; errors come back as
`error: <Class>: <message>`. `--http` serves streamable HTTP instead of stdio.

Client configuration, for Claude Desktop or any MCP client:

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": ["--from", "xippios-example[mcp]", "xippios-example-mcp"],
      "env": { "EXAMPLE_API_KEY": "..." }
    }
  }
}
```

## HTTP routes in two lines

```python
from xippios.core.http import router_from_tasks

router = router_from_tasks("example", [tasks.get_series])  # GET /example/get_series?series_id=...
```

Mount it on your FastAPI app. Responses are the `Result[T]` envelope; errors are
RFC 9457 problem details (`application/problem+json`).

## Testing a source package

```python
# tests/conftest.py
pytest_plugins = ["xippios.core.testing.plugin"]
```

- `@pytest.mark.live` tests are skipped unless `XIPPIOS_LIVE_TESTS=1`.
- `replay_fixture("api_GET", "corn_2024")` mounts `tests/fixtures/api_GET/corn_2024.json`.
- `record(client, "/v1/series", fixture_path(...), params=...)` records a live response
  with credentials scrubbed. Never hand-write a fixture.

## Status

| Module | What | Status |
| --- | --- | --- |
| `xippios.core.client` | httpx client, retries, rate limit, cache, sync facade | alpha |
| `xippios.core.errors` | taxonomy and response classification | alpha |
| `xippios.core.models` | `UpstreamModel`, `Result`, `ResultMeta`, `parse` | alpha |
| `xippios.core.config` | `SourceSettings`, `resolve_api_key` | alpha |
| `xippios.core.reference` | packaged CSV/JSON loaders | alpha |
| `xippios.core.pagination` | offset, page and cursor iterators | alpha |
| `xippios.core.mcp` | tool registration, result caps, error text, CLI | alpha |
| `xippios.core.http` | router factory, problem details | alpha |
| `xippios.core.testing` | live gate, record, replay, scrub | alpha |

Alpha: the public surface may change in a minor version until the first source
package, `sdk-usda-nass`, has exercised it.

## Conventions

The rules this package implements live in [docs/conventions.md](docs/conventions.md)
and the decisions behind them in [docs/adr/](docs/adr/). Changes to a convention are
their own PR plus an ADR.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
