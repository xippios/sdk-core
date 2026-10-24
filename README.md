# xippios-core

Shared foundation of the [xippios](https://github.com/xippios) Python SDK family. Every
`xippios-<source>` package depends on it; nothing in it knows about any particular
upstream API.

It gives a source package the things that should be identical across the family:

- **HTTP client** on `httpx` with retries, a per-source rate limiter, an optional
  response cache (off by default; the in-memory one is bounded by TTL and size),
  explicit timeouts and one `User-Agent`. Async at the core, a sync facade on top.
  A 429 is retried for every method, a 5xx or a transport failure only for GET, HEAD
  and OPTIONS unless `RetryPolicy.retry_non_idempotent` is set, because upstream makes a
  repeated write safe, or because the source only reads through POST.
  `ClientConfig.cache_filter` narrows the cache to chosen requests; clients built with
  the same `limiter` share one pace. A body goes as JSON (`json=`) or form-encoded
  (`data=`); `AsyncClient.derive` gives a client with another retry policy or other
  timeouts that shares auth, pace, cache and transport, and never closes the transport.
- **Auth helpers** that read the key from the environment on the first request:
  query parameter, header, bearer token or basic auth. A source's documented error
  shapes go into `ClientConfig.classify`, consulted on every response.
- **Error taxonomy**: `ConfigError`, `AuthError`, `RateLimitError`, `NotFoundError`,
  `ValidationError`, `UpstreamError`, `TransportError` and `InvalidRequestError` (a
  request refused before it is sent), all under `XippiosError`.
- **Result envelope**: every task function returns `Result[T]` with `ResultMeta`
  (source, endpoint, retrieved_at, published_at, vintage, request, total: upstream's
  count of the matching records when the source reports one, and tenant: the tenant the
  data came from, by name, for a multi-tenant source). `Decimal` fields
  of upstream models arrive as JSON numbers in both adapters; `UpstreamModel.project`
  builds a projection of a record under upstream names, `parse_decimal` reads a
  published figure.
- **Tenants** for a source that serves several tenants from the environment: declared
  names, per-tenant variables, one client per tenant (`Tenants`).
- **Reference-data loader** for code lists shipped inside a package.
- **Adapters** that turn task functions into MCP tools (`xippios.core.mcp`) and FastAPI
  routes (`xippios.core.http`) without any logic of their own.
- **Test support**: a live-test gate, offline guarantees for every other test (no
  network, no rate-limit wait, a placeholder key), fixture recording with secrets
  scrubbed, replay through `respx`, and a check for write servers
  (`xippios.core.testing`).

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
    print(exc)  # 404 from GET /v1/series: ...
except RateLimitError as exc:
    print(exc.retry_after)
```

A message names the method and path of the request, never its host or query string:
the host can name a tenant and the query can carry a key.

## Multi-tenant sources

An upstream that serves each tenant from a host or under a key of its own gets its
tenants from the environment through `Tenants`: one variable lists the names, each
tenant's values sit in `<SOURCE>_<NAME>_<FIELD>`, and a reserved test tenant exists when
its own variables are set and is never listed. Every tenant gets one client, built on
first use and rebuilt when one of its values changes. Errors name tenants and variables,
never a value.

```python
import re

from xippios.core import AsyncClient, BasicKeyAuth, ClientConfig, Tenants
from xippios.core.tenants import list_task


def check_subdomain(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
        raise ValueError("not a subdomain")  # never the value: it names the tenant
    return value


# EXAMPLE_TENANTS=acme,acme_test
# EXAMPLE_ACME_SUBDOMAIN=acme-books   EXAMPLE_ACME_API_KEY=...
# EXAMPLE_DEMO_SUBDOMAIN=demo         EXAMPLE_DEMO_API_KEY=...   (reserved, never listed)
tenants = Tenants(
    "example",
    list_var="EXAMPLE_TENANTS",
    fields=("SUBDOMAIN", "API_KEY"),
    reserved=("demo",),
    validate={"SUBDOMAIN": check_subdomain},
)


def build(name: str) -> AsyncClient:
    subdomain = tenants.field(name, "SUBDOMAIN")
    config = ClientConfig(
        source="example", version="0.1.0", base_url=f"https://{subdomain}.example.org/api"
    )
    return AsyncClient(config, auth=BasicKeyAuth(tenants.var(name, "API_KEY")))


tenants.names()  # ("acme", "acme_test", "demo")
client = tenants.client_for("acme", build)  # the same client until a value changes
list_tenants = list_task(tenants, name="list_tenants")  # a reference tool: names only
```

A task takes the tenant's name and sets `ResultMeta(tenant=name, ...)`. The key is read
on the first request, so a declared tenant without one fails then, with `ConfigError`.

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
A write server (`build_server(..., read_only=False)`) refuses, with `ValueError`, a task
that does not take `confirm: bool = False`, and `--http` serves it on a loopback
`--host` only (`127.0.0.1`, `localhost`, `::1`): it carries no authentication.
`--allow-remote` serves it beyond loopback, behind a gateway that adds it.
Request URLs are not logged: `build_server` and `main` set the `httpx` and `httpcore`
loggers to `WARNING` (`quiet_request_logging`), because a URL can carry an API key or a
tenant host.

A multi-tenant source locks a server to one tenant with an option of its own, added
through `main`'s hooks so the command line is parsed once:

```python
import argparse

from mcp.server.mcpserver import MCPServer
from xippios.core.mcp import TenantLock, build_server, main
from xippios.core.tenants import list_task
from xippios.example import tasks
from xippios.example._client import tenants

TASKS = [tasks.get_account, list_task(tenants, name="list_tenants")]
server = build_server("example", TASKS)


def lock(args: argparse.Namespace, server: MCPServer) -> MCPServer:
    if args.tenant is None:
        return server
    tenant = tenants.require(args.tenant)  # an undeclared name: exit status 2
    tenants.field(tenant, "SUBDOMAIN")  # a missing or malformed subdomain: exit status 2
    return build_server("example", TASKS, tenant_lock=TenantLock("tenant", tenant))


def run() -> None:  # xippios-example-mcp --tenant acme
    main(
        server,
        add_options=lambda parser: parser.add_argument("--tenant", help="serve one tenant"),
        apply_options=lock,
    )
```

A locked server answers a call naming another tenant with
`error: InvalidRequestError: this server is locked to tenant=acme; the call named
another tenant` before the tool runs, names the tenant in its instructions, and its
`example_list_tenants` tool lists that tenant alone.

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

Mount it on your FastAPI app. A task whose parameters are all scalars is a `GET` with
query parameters; a task with a mapping, list or model parameter is a `POST` whose JSON
body is keyed by parameter name. Responses are the `Result[T]` envelope; errors are
RFC 9457 problem details (`application/problem+json`), `InvalidRequestError` as 422.

## Testing a source package

```python
# tests/conftest.py
pytest_plugins = ["xippios.core.testing.plugin"]
```

```toml
# pyproject.toml: the variables that hold the placeholder key in offline tests
[tool.pytest.ini_options]
xippios_placeholder_key_envs = ["EXAMPLE_API_KEY"]
```

- `@pytest.mark.live` tests are skipped unless `XIPPIOS_LIVE_TESTS=1`.
- The whole run is offline (ADR-0013). From `pytest_configure` on, during collection, in
  fixtures and in tests, a request through httpx's default transports raises
  `RuntimeError` naming its method and path unless `respx` answers it, a `respx` route
  that passes through included; mark a test `network` to let it through. In every test
  not marked `live`, the rate limiter never waits (mark a test `rate_limited` to keep
  it), and every `EnvKeyAuth` sends `PLACEHOLDER_KEY` while the variables named in
  `xippios_placeholder_key_envs` hold it (fixture `placeholder_api_key`), whatever the
  shell or an earlier live test left behind. The `httpx` and `httpcore` logger levels
  come back after every test. ADR-0013 states the edges of these guarantees.
- `replay_fixture("api_GET", "corn_2024")` mounts `tests/fixtures/api_GET/corn_2024.json`
  on its method, host and path; `match_params=["countOnly"]` makes the route match those
  recorded query parameters too. A parameter's absence cannot be matched: where two
  fixtures share a path, mount the one with `match_params` first, since `respx` tries
  routes in order. The request body is never matched: assert it from the route's calls
  against `fixture.request.body`. `sent_urls(route)` gives the URLs the route received
  as scrubbed strings, so no request has to sit in the test's frame. Annotate the
  fixture as `ReplayFixture`.
- `record(client, "/v1/series", fixture_path(...), params=...)` records a live response
  with credentials scrubbed. Never hand-write a fixture. `json=` or `data=` (a form) send
  a body, recorded with its content type; `retry=` and `timeouts=` override the
  client's for the recording.

`mcp_call(server, "example_get_series", {...})` calls a tool through an in-process MCP
client, so the server's middleware, a tenant lock included, runs as for a real client;
it returns the decoded JSON and fails the test on `error:` text. `mcp_call_text` returns
the text, to assert a refusal.

A source with a write server checks it against its write tasks: exactly those tools,
each taking `confirm: bool = False`, none of them on the read server or the HTTP router.

```python
from xippios.core.testing import assert_write_tools

assert_write_tools(
    write_server, [tasks.create_account], source="example", read_server=server, router=router
)
```

A multi-tenant source tells the recorder what else must never be written:

```python
from xippios.core.testing import Scrub, fixture_path, record_sync

record_sync(
    client,
    "/account/list.json",
    fixture_path(FIXTURES, "account_list", "one"),
    scrub=Scrub(
        host="demo.example.test",  # placeholder for the tenant's host, used everywhere it appeared
        secrets=[tenant_name],  # REDACTED wherever it appears, plain or percent-encoded
        rewrite=strip_signatures,  # text hook for bodies and header values (Location)
    ),
)
```

The fixture is scrubbed in memory, verified and written once: if the tenant's host or a
named value is still anywhere, a JSON body decoded included, nothing is written and the
error says where, never what. A body that is not UTF-8 text cannot be scrubbed and is
refused unless `Scrub(allow_binary=True)` stores it base64, flagged.

## Status

| Module | What | Status |
| --- | --- | --- |
| `xippios.core.client` | httpx client, retries, rate limit, cache, sync facade | alpha |
| `xippios.core.errors` | taxonomy and response classification | alpha |
| `xippios.core.models` | `UpstreamModel`, `Result`, `ResultMeta`, `parse` | alpha |
| `xippios.core.config` | `SourceSettings`, `resolve_api_key` | alpha |
| `xippios.core.reference` | packaged CSV/JSON loaders | alpha |
| `xippios.core.pagination` | offset, page and cursor iterators | alpha |
| `xippios.core.tenants` | `Tenants`, `list_task`: tenants from the environment, one client each | alpha |
| `xippios.core.mcp` | tool registration, result caps, error text, CLI, quiet request log | alpha |
| `xippios.core.http` | router factory, problem details | alpha |
| `xippios.core.testing` | live gate, offline run, record, replay, scrub, write checks | alpha |

Alpha: the public surface may change in a minor version until the first source
package, `sdk-usda-nass`, has exercised it.

## Conventions

The rules this package implements live in [docs/conventions.md](docs/conventions.md)
and the decisions behind them in [docs/adr/](docs/adr/). Changes to a convention are
their own PR plus an ADR.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
