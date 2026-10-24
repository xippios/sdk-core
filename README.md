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
  Two hooks, `before_request` and `observe`, see each call and each response;
  `QuotaPolicy` uses them to wait out or refuse a request into a spent quota.
  `auth=None` sends one call without the client's key.
- **Auth helpers** that read the key from the environment on the first request:
  query parameter, header, bearer token or basic auth. A source's documented error
  shapes go into `ClientConfig.classify`, consulted on every response.
- **Error taxonomy**: `ConfigError`, `AuthError`, `RateLimitError`, `NotFoundError`,
  `ValidationError`, `UpstreamError`, `TransportError` and `InvalidRequestError` (the
  request as given cannot be served: a bad argument, or a refusal the source documents,
  detected before the call or mapped from upstream's own refusal), all under
  `XippiosError`.
- **Result envelope**: every task function returns `Result[T]` with `ResultMeta`
  (source, endpoint, retrieved_at, published_at, vintage, request, total: upstream's
  count of the matching records when the source reports one, and tenant: the tenant the
  data came from, by name, for a multi-tenant source). `Decimal` fields
  of upstream models arrive as JSON numbers in both adapters; `UpstreamModel.project`
  builds a projection of a record under upstream names, `parse_decimal` reads a
  published figure.
- **Tenants** for a source that serves several tenants from the environment: declared
  names, per-tenant variables, one client per tenant (`Tenants`).
- **Reference data**: loaders for code lists shipped inside a package, and the
  renderers that generate their `StrEnum` and `IntEnum` modules.
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

## Quotas, hooks and keyless calls

An upstream that reports a longer-window quota in its headers (api.data.gov:
`x-ratelimit-limit`, `x-ratelimit-remaining`) gets a `QuotaPolicy`, installed on the
client's configuration:

```python
from xippios.core import AsyncClient, ClientConfig, HeaderKeyAuth, QuotaPolicy

quota = QuotaPolicy(window=3600.0, source="example")  # spent for an hour unless told otherwise
config = quota.install(
    ClientConfig(source="example", version="0.1.0", base_url="https://api.example.org")
)
client = AsyncClient(config, auth=HeaderKeyAuth("X-Api-Key", "EXAMPLE_API_KEY"))
quota.snapshot()  # None: no response observed yet


async def get_series_async(series_id: str) -> object:
    rows = await client.get_json("/v1/series", params={"id": series_id})
    quota.snapshot()  # QuotaSnapshot(limit=1000, remaining=999, observed_at=..., resumes_at=None)
    return rows


async def list_countries_async() -> object:
    return await client.get_json("/files/countries.json", auth=None)  # public: no key sent
```

The policy reads the quota headers of every response from the wire through
`ClientConfig.observe`. Once a 429, or a response that leaves nothing, shows the quota
spent, `ClientConfig.before_request` makes the next request wait until it is back if
that is within `RetryPolicy.backoff_max` (30 s by default), with one warning in the log,
and otherwise raises `RateLimitError` with `retry_after`, saying that nothing was sent.
An upstream that answers a spent limit with something other than a 429 gets
`QuotaPolicy(spent=...)`, a function that returns the seconds to wait for such an
answer, or `None`. A wait from upstream is never longer than `window`, and the reset
header may hold delay-seconds, epoch seconds or an HTTP-date. `install` refuses a config
that has hooks of its own, rather than replacing them.

A request the cache answers never waits: `before_request` runs after the cache lookup,
and a cache hit carries the time its entry was stored in
`response.extensions["xippios_cache_stored_at"]`, the hit's `retrieved_at`; a wrapper
that needs it calls `get()` and then `decode_json(response, source=...)` instead of
`get_json()`. The hooks are plain callables on `ClientConfig` (`before_request` may be
async) for anything else that has to see each call or each response.

`ClientConfig.classify` is asked before a 429 or 5xx is retried: a `RateLimitError`
with a `retry_after` beyond `backoff_max` is raised after one attempt instead of being
retried into a spent quota; an `UpstreamError` for a 5xx leaves the retries as they are;
any other error it returns, an `AuthError` say, ends them.

`auth=` on `request`, `get`, `get_json` and `record` overrides the client's credentials
for one call: `None` sends none, for a keyless endpoint on the same host, and another
`httpx.Auth` replaces them. `None` and the default share the cache; a call with an
`httpx.Auth` of its own bypasses it, neither looked up nor stored.

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

## Reference data and generated enums

A source ships its code lists under `reference/` and reads them with `load_csv`,
`load_json` or `load_table`. Its refresh script generates `enums.py` from them with
`xippios.core.reference`, and the module is committed as rendered:

```python
from xippios.core.reference import id_name_pairs, render_int_enums, render_str_enums

# Value lists: one StrEnum each, member names derived from the values.
enums = render_str_enums(
    {"state_alpha": ["AK", "AL"], "sector_desc": ["ANIMALS & PRODUCTS", "CROPS"]},
    class_names={"sector_desc": "Sector"},
    fetched="2026-10-24",
    generator="scripts/refresh_reference.py",
)

# Integer ids with names: one IntEnum each, values the ids, in upstream order.
records = [
    {"attributeId": 4, "attributeName": "Area Harvested"},
    {"attributeId": 126, "attributeName": "Total Disappearance"},
    {"attributeId": 173, "attributeName": "Total Disappearance"},
]
pairs = id_name_pairs(records, id_field="attributeId", name_field="attributeName")
ids = render_int_enums(
    {"attributeId": pairs},
    class_names={"attributeId": "AttributeId"},
    fetched="2026-10-24",
    generator="scripts/refresh_reference.py",
)
```

```python
class AttributeId(IntEnum):
    """Values of ``attributeId`` (fetched 2026-10-24)."""

    AREA_HARVESTED = 4
    TOTAL_DISAPPEARANCE_126 = 126
    TOTAL_DISAPPEARANCE_173 = 173
```

An upstream whose ids are integers gets `IntEnum` (conventions §3), so a member compares
equal to the id in upstream's data; a name several ids share gets `_<id>`. Values are
written as `ascii()` writes them, every character outside ASCII as an escape
(`"C\xf4te d\u2019Ivoire"`), a member too long for its line is wrapped as ruff wraps it,
and `__all__` is sorted as ruff sorts it, one name per line. The whole module is
ASCII-only, so no ruff version can find an ambiguous character in it, and it passes
`ruff check` and `ruff format --check` unchanged; a key, class name, fetch date or
generator text that is not printable ASCII is refused. A member name too long for any
line (over 92 columns), or a value with nothing to derive one from (an empty or a
non-Latin label), is refused with `ValueError`; the refresh script names that member by
hand, once:

```python
enums = render_str_enums(
    {"short_desc": values},
    member_names={"short_desc": {long_value: "CORN_GRAIN_IRRIGATED_ALL"}},
)
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
A reference tool whose whole list an agent needs gets a cap of its own, keyed by the
task function's name, with the rows and bytes the source judges it needs:
`build_server(..., caps={"list_commodities": ResultCap(max_rows=500,
max_bytes=100_000)})`; every other tool keeps 200 rows or 64 KB. The note says "narrow
the query to see the rest" and promises no filter; a tool with filters names them in
its cap, `ResultCap(note="filter by year to see the rest")`.
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
another tenant` before the tool runs, and a call that leaves the tenant out of a tool
that takes it with `...; the call did not name the tenant`; a task may not give the
tenant parameter a default. The server names the tenant in its instructions, and its
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
  it) and no `QuotaPolicy` pauses, refuses or stays spent from one test to the next
  (`rate_limited` keeps the pause too), and every `EnvKeyAuth` sends `PLACEHOLDER_KEY`
  while the variables named in `xippios_placeholder_key_envs` hold it (fixture
  `placeholder_api_key`), whatever the shell or an earlier live test left behind. The
  `httpx` and `httpcore` logger levels come back after every test. ADR-0013 states the
  edges of these guarantees.
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
| `xippios.core.client` | httpx client, retries, rate limit, cache, quota policy, request hooks, sync facade | alpha |
| `xippios.core.errors` | taxonomy and response classification | alpha |
| `xippios.core.models` | `UpstreamModel`, `Result`, `ResultMeta`, `parse` | alpha |
| `xippios.core.config` | `SourceSettings`, `resolve_api_key` | alpha |
| `xippios.core.reference` | packaged CSV/JSON loaders, generated `StrEnum`/`IntEnum` modules | alpha |
| `xippios.core.pagination` | offset, page and cursor iterators | alpha |
| `xippios.core.tenants` | `Tenants`, `list_task`: tenants from the environment, one client each | alpha |
| `xippios.core.mcp` | tool registration, result caps, error text, CLI, quiet request log | alpha |
| `xippios.core.http` | router factory, problem details | alpha |
| `xippios.core.testing` | live gate, offline run, record, replay, scrub, write checks | alpha |

Alpha: a new minor version may change the public surface, with no backward
compatibility across minors; patch releases stay compatible. A source depends on one
minor (`xippios-core~=0.2.0`) and adopts the next through conventions §15.

## Conventions

The rules this package implements live in [docs/conventions.md](docs/conventions.md)
and the decisions behind them in [docs/adr/](docs/adr/). Changes to a convention are
their own PR plus an ADR.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
