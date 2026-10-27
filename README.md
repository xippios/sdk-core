# xippios-core

Shared foundation of the [xippios](https://github.com/xippios) Python SDK family. Every
`xippios-<source>` package depends on it; nothing in it knows about any particular
upstream API.

It gives a source package the things that should be identical across the family:

- **HTTP client** on `httpx` with retries, a per-source rate limiter, an optional
  response cache (off by default; the in-memory one is bounded by TTL and size),
  explicit timeouts and one `User-Agent`. Async at the core; `sync` derives the sync
  task functions from the async ones.
  A 429 is retried for every method, a 5xx or a transport failure only for GET, HEAD
  and OPTIONS unless `RetryPolicy.retry_non_idempotent` is set, because upstream makes a
  repeated write safe, or because the source only reads through POST.
  `ClientConfig.cache_filter` narrows the cache to chosen requests. A body goes as JSON
  (`json=`) or form-encoded (`data=`). Two hooks, `before_request` and `observe`, see
  each call and each response; `QuotaPolicy` uses them to wait out or refuse a request
  into a spent quota.
  `auth=None` sends one call without the client's key. `get_answer` returns the payload
  with its `retrieved_at`, a cache hit's stored time. A file is streamed to disk with
  `download`, never held in memory; `decode_text` and `decode_csv` read text and CSV
  next to `decode_json`; the cache stores no body over `cache_max_bytes` (8 MiB).
- **Auth helpers** that read the key from the environment on the first request:
  query parameter, header, bearer token or basic auth. A source's documented error
  shapes go into `ClientConfig.classify`, consulted on every response.
- **The api.data.gov gateway** (`xippios.core.data_gov`) for every source behind it:
  the key from `DATA_GOV_API_KEY`, the gateway's error answers, and one quota policy per
  process for that key.
- **Error taxonomy**: `ConfigError`, `AuthError`, `RateLimitError`, `NotFoundError`,
  `ValidationError`, `UpstreamError`, `TransportError` and `InvalidRequestError` (the
  request as given cannot be served: a bad argument, or a refusal the source documents,
  detected before the call or mapped from upstream's own refusal), all under
  `XippiosError`; `UnknownCode`, an `InvalidRequestError`, refuses a code a packaged
  list lacks and names the closest known ones.
- **Result envelope**: every task function returns `Result[T]` with `ResultMeta`
  (source, endpoint, retrieved_at, published_at with published_at_naive for a time
  upstream printed without a zone, vintage, request without the parameters left `None`,
  total: upstream's count of the matching records when the source reports one, and
  tenant: the tenant the data came from, by name, for a multi-tenant source); a field it
  does not define is refused. `Decimal` fields of upstream models arrive as JSON numbers
  in both adapters; `UpstreamModel.project` builds a projection of a record under
  upstream names, `dump_upstream` gives a record back under upstream's field names,
  `parse_decimal` reads a published figure.
- **Tenants** for a source that serves several tenants from the environment: declared
  names, per-tenant variables, one client per tenant (`Tenants`).
- **Reference data**: loaders for code lists shipped inside a package, `PackagedList`
  for a list fetched from one upstream operation (its file, the meta of an answer from
  it, its writer), `matches` and `closest` for the list tasks and their refusals, and the
  renderers that generate `StrEnum` and `IntEnum` modules.
- **Adapters** that turn task functions into MCP tools (`xippios.core.mcp`) and FastAPI
  routes (`xippios.core.http`) without any logic of their own.
- **Test support**: a live-test gate, offline guarantees for every other test (no
  network, no rate-limit wait, a placeholder key), fixture recording with secrets
  scrubbed, replay through `respx`, a check for write servers, and the family
  conformance check every source runs (`xippios.core.testing`).

## Install

```bash
uv add "xippios-core~=0.2.1"            # client, models, errors, reference, pagination
uv add "xippios-core[mcp]~=0.2.1"       # + MCP server helpers (official mcp SDK 2.x)
uv add "xippios-core[http]~=0.2.1"      # + FastAPI router helpers
uv add "xippios-core[testing]~=0.2.1"   # + pytest plugin, respx replay, fixture recording
```

Python 3.12 or later. A source package depends on one core minor, `~=0.2.1`, and each
extra likewise (conventions §12); see the Alpha note under Status.

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
names a credential (`api_key`, `token`, `secret`, `sig`, ... as whole words) so an
envelope is safe to hand to an agent or return over HTTP. A bare `key` is a credential
only where a `QueryKeyAuth` sends the key under that name, as above, which registers it
for the process; elsewhere it is data, as Eurostat's SDMX series `key` is, and so is a
`sort_key`. The fixture recorder and the replay helpers redact by the same rule
(`xippios.core.redaction`). A parameter the caller left `None` was not sent and is left
out of `meta.request`, so a task passes its parameters as they are.

A release time upstream prints without a zone (FAS: `2026-10-06T08:00:00`) goes into
`published_at` as printed, with `published_at_naive=True`, and `vintage` keeps the
release identifier as upstream names it; `ResultMeta` refuses a naive time without the
flag, the flag without a naive time, and any field it does not define.

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
that is within the policy's `pause_cap` (30 s by default), with one warning in the log,
and otherwise raises `RateLimitError` with `retry_after`, saying that nothing was sent.
A spent quota is back after a 429's `Retry-After`, else after `window`. An upstream that
answers a spent limit with something other than a 429 gets `QuotaPolicy(spent=...)`, a
function that returns the seconds to wait for such an answer, or `None`. A wait from
upstream is never longer than `window`. `install` sets the policy's two hooks on a copy
of the config and reads nothing else from it; a source that needs hooks of its own as
well composes them itself.

A source behind api.data.gov takes all of this from `xippios.core.data_gov`, together
with its key and the gateway's documented answers. Every `Gateway` in a process shares
one `QuotaPolicy`, `Gateway.policy`, since one key is one quota across every package that
uses it:

```python
import httpx

from xippios.core import AsyncClient, ClientConfig, NotFoundError, XippiosError
from xippios.core.data_gov import Gateway

gateway = Gateway("usda-psd")


def classify(response: httpx.Response) -> XippiosError | None:
    error = gateway.classify(response)  # API_KEY_*, the 429, NOT_FOUND; else None
    if error is None and response.status_code == 404 and not response.content:
        # the source's own documented answers follow the gateway's
        error = NotFoundError(f"no data for {response.request.url.path}", source="usda-psd")
    return error


config = gateway.install(
    ClientConfig(
        source="usda-psd",
        version="0.3.0",
        base_url="https://api.fas.usda.gov",
        classify=classify,
    )
)
client = AsyncClient(config, auth=gateway.auth)  # X-Api-Key from DATA_GOV_API_KEY
```

The gateway's 429 is a `RateLimitError` in the source's name whose `retry_after` is the
wait the shared policy keeps the quota spent for; once it is spent, the next request of
any source in the process waits within the policy's cap or is refused before sending, as
`api.data.gov`.

A request the cache answers never waits: `before_request` runs after the cache lookup,
and a cache hit carries the time its entry was stored in
`response.extensions["xippios_cache_stored_at"]`, the hit's `retrieved_at`. A wrapper
whose answer may come from the cache calls `get_answer()` instead of `get_json()`: its
`Answer` carries the payload and `retrieved_at`, the stored time on a hit and the time
the answer arrived otherwise.

```python
answer = await client.get_answer("/api/regions", auth=None)
meta = ResultMeta(source="example", endpoint="regions", retrieved_at=answer.retrieved_at)
```

The hooks are plain callables on `ClientConfig` (`before_request` may be async) for
anything else that has to see each call or each response.

`ClientConfig.classify` is asked before a 429 or 5xx is retried: a `RateLimitError`
with a `retry_after` beyond `backoff_max` is raised after one attempt instead of being
retried into a spent quota; an `UpstreamError` for a 5xx leaves the retries as they are;
any other error it returns, an `AuthError` say, ends them.

`auth=` on `request`, `get`, `get_json`, `get_answer` and `record` overrides the
client's credentials for one call: `None` sends none, for a keyless endpoint on the same
host, and another `httpx.Auth` replaces them. `None` and the default share the cache; a
call with an `httpx.Auth` of its own bypasses it, neither looked up nor stored.

## Files: download and decode

An upstream that publishes files (a bulk dataset, a release's CSV or XLS) is read with
`download`, which streams the body to disk under a temporary name and renames it when it
is complete; the limiter, the hooks, `classify` and the retries apply as for `get()`, a
retry restarting the file, and the response cache is never touched. The hooks see a
success's status and headers only, since its body goes to the file unread, and a
redirect raises `UpstreamError`:

```python
from pathlib import Path

from xippios.core import Downloaded, Result, ResultMeta
from xippios.core.client import decode_csv

BULK_TASKS = frozenset({"download_crops"})  # in tasks.py beside MCP_CAPS: Python only


async def download_crops_async(dest: Path) -> Result[Downloaded]:
    """Download the crops file of the current release.

    Args:
        dest: The file to write, e.g. ``Path("qs.crops.txt")``.
    """
    url = "https://files.example.org/bulk/qs.crops.txt"  # a link from the catalog
    got = await client.download(url, dest, auth=None)  # another host: no key sent there
    meta = ResultMeta(source="example", endpoint="qs.crops", request={"url": url})
    return Result(data=got, meta=meta)


for row in decode_csv(Path("qs.crops.txt"), delimiter="\t"):  # row by row, never whole
    print(row["COMMODITY_DESC"], row["VALUE"])  # headers as upstream prints them
```

`Downloaded` carries the path, the size, the content type, the file name from
`Content-Disposition`, the `ETag`, the `Last-Modified` text and when the file was
complete. `decode_text(response)` reads a text answer in the charset of its
`Content-Type` (UTF-8 by default, a byte order mark stripped), and `decode_csv` takes a
downloaded file or a response. A gzip or zip file is opened with the stdlib; core ships
no XML, spreadsheet or PDF parser. `register_tasks` and `router_from_tasks` skip a task
its `tasks.py` names in `BULK_TASKS`, so no tool or route returns a file path. A body
over `ClientConfig.cache_max_bytes` (8 MiB by default) is returned and not cached.

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

A list a source fetches from one upstream operation and ships, so that its `list_*`
tasks and its argument checks need no call, is a `PackagedList`: `reference/<param>.json`
with `{"param", "endpoint", "fetched", "records"}`, upstream's records under upstream's
field names. The refresh script writes it; the tasks read it:

```python
from datetime import UTC, datetime

from xippios.core import PackagedList, Result, UnknownCode, closest, matches

# scripts/refresh_reference.py: the records as upstream named them, the time of the fetch
fetched = datetime.now(UTC).replace(microsecond=0)
records = [record.dump_upstream() for record in commodities]  # from the api/ wrapper
PackagedList(
    param="commodities", endpoint="GetCommodities", fetched=fetched, records=records
).write(REFERENCE / "commodities.json")


# tasks.py
async def list_commodities_async(search: str | None = None) -> Result[list[Commodity]]:
    """List the commodities with their codes, the values commodity_code takes.

    Args:
        search: Keep the commodities whose code or name contains this text, ignoring
            case, e.g. ``"wheat"``. Omit (``None``) for all.
    """
    packaged = PackagedList.load("xippios.example", "commodities")
    rows = packaged.parse(Commodity, source="example")
    kept = [row for row in rows if matches(search, row.commodity_code, row.commodity_name)]
    return Result(data=kept, meta=packaged.meta("example", request={"search": search}))


def validate_commodity_code(code: str) -> str:
    packaged = PackagedList.load("xippios.example", "commodities")
    codes = {r["commodityCode"]: r["commodityName"] for r in packaged.records}
    if code not in codes:
        raise UnknownCode(
            "commodity_code",
            code,
            list_name="commodities",
            fetched=packaged.fetched,
            closest=closest(code, codes),  # "wheat" -> [("0410000", "Wheat")]
            source="example",
        )
    return code
```

The answer's `meta` follows ADR-0022: `endpoint` is the upstream operation the list came
from, `retrieved_at` the time it was fetched, `vintage` an upstream release identifier
only when one is passed (a fetch date is not a vintage), `total` `None`. A file whose
`fetched` is a bare date, as refresh scripts wrote it before template v0.3.0, reads as
00:00 UTC of that day. A list of values is records of one field named by the upstream
parameter (`[{"state_alpha": "AK"}, ...]`). `UnknownCode` names the value, the list and
its fetch date, the closest codes (or a `hint=`), an optional `reason=`, and that a code
upstream added since needs a refresh of the list.

Other code lists are read with `load_json` or `load_table` (`load_csv`, which
`load_table` calls for a CSV file, stays in `xippios.core.reference`). The refresh
script generates `enums.py` from them with `xippios.core.reference`, and the module is
committed as rendered:

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
its cap, `ResultCap(note="filter by year to see the rest")`. `ResultCap` comes from
`xippios.core`, so the `MCP_CAPS` in a source's `tasks.py` need no `mcp` extra.
A write server (`build_server(..., read_only=False)`) refuses, with `ValueError`, a task
that does not take `confirm: bool = False`, and `--http` serves it on a loopback
`--host` only (`127.0.0.1`, `localhost`, `::1`): it carries no authentication.
`--allow-remote` serves it beyond loopback, behind a gateway that adds it.
A task named in its `tasks.py`'s `BULK_TASKS` is skipped, so `mcp.py` may pass every name
of `tasks.__all__`; a cap named for it is refused.
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

```python
# tests/test_family.py, rendered by sdk-template
from xippios.core.testing.family import *  # noqa: F403
```

The second file collects the family conformance check: the tests of what every source
shares, kept once in core. The namespace levels stay empty and `py.typed` ships; `mcp.py`
and `http.py` serve exactly `tasks.__all__` minus `BULK_TASKS`, the write server exactly
`tasks_write.__all__`; every task is synchronous, returns `Result[T]` and has an agent
docstring; the README's status table lists exactly the read and the write tasks;
`.copier-answers.yml` names a template tag; `pyproject.toml` bounds `xippios-core` with
`~=`. A source whose adapters drop a task, or whose README table is stale, fails CI
before a reviewer looks. The package under test is the one `tasks.py` under
`src/xippios/`, or the ini option `xippios_package`.

```toml
# pyproject.toml: the variables that hold the placeholder key in offline tests
[tool.pytest.ini_options]
xippios_placeholder_key_envs = ["EXAMPLE_API_KEY"]
```

- `@pytest.mark.live` tests are skipped unless `XIPPIOS_LIVE_TESTS=1`, and `anyio`
  tests run on asyncio (the plugin's `anyio_backend`).
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
  as scrubbed strings, so no request has to sit in the test's frame, and
  `sent_query(route)` the last one's query as a mapping, to compare with
  `recorded_query(fixture)`. `url=` serves a recorded answer at another URL, such as an
  empty 404 recorded for one year standing in for another. Annotate the fixture as
  `ReplayFixture`.
- `response_from_fixture(load_fixture(path))` is a recorded answer as an
  `httpx.Response`, its request attached, for calling a source's `classify` directly.
- `assert_time_between(result.meta.retrieved_at, before, after)` brackets a time with
  two readings around the call and `CLOCK_SLACK` (five seconds) either side, for a host
  whose clock steps back.
- `record(client, "/v1/series", fixture_path(...), params=...)` records a live response
  with credentials scrubbed. Never hand-write a fixture. `json=` or `data=` (a form) send
  a body, recorded with its content type. The recording goes through the client as it
  is configured; one that must not retry a 5xx goes through a client whose config says
  `RetryPolicy(max_attempts=1)`. `max_bytes=80_000` cuts a large answer's body: a JSON
  array after its first whole elements, in upstream's own text, a text after its first
  bytes, never inside a secret or the host, and the fixture is marked `truncated` with
  the whole body's size and sha256 (and an array's length); a JSON object, XML, ZIP,
  XLSX, gzip, XLS or a body that is not UTF-8 text is refused: record a small real
  answer or sample instead. It bounds the body, not the file, which escapes the body as
  a JSON string, text outside ASCII up to three times as long: 80,000 bytes keep a file
  under the 256 KiB cap.

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

Release 0.2.1, alpha.
[CHANGELOG.md](https://github.com/xippios/sdk-core/blob/main/CHANGELOG.md) lists what
changed, breaking changes first.

| Module | What | Status |
| --- | --- | --- |
| `xippios.core.client` | httpx client, retries, rate limit, cache with a byte bound, quota policy, request hooks, env-key auth, `get_answer`, `download`, `decode_text`, `decode_csv` | alpha |
| `xippios.core.errors` | taxonomy, `UnknownCode`, response classification | alpha |
| `xippios.core.data_gov` | `Gateway`: the api.data.gov key, the gateway's `classify`, one quota policy per process | alpha |
| `xippios.core.redaction` | the one credential rule of the envelope, the recorder and replay | alpha |
| `xippios.core.models` | `UpstreamModel` with `dump_upstream`, `Result`, `ResultMeta` with `published_at_naive`, `ResultCap`, `parse` | alpha |
| `xippios.core.reference` | packaged CSV/JSON loaders, `PackagedList`, `matches`, `closest`, generated `StrEnum`/`IntEnum` modules | alpha |
| `xippios.core.pagination` | `paginate_offset` (a page-numbered endpoint maps the offset to its page), `collect` | alpha |
| `xippios.core.tenants` | `Tenants`, `list_task`: tenants from the environment, one client each | alpha |
| `xippios.core.mcp` | tool registration, result caps, error text, CLI, quiet request log | alpha |
| `xippios.core.http` | router factory, problem details | alpha |
| `xippios.core.testing` | live gate, offline run, record (with `max_bytes=`), replay, scrub, write checks, family check | alpha |

Alpha: while core is 0.x, a new minor version may change the public surface, with no
backward compatibility across minors; patch releases stay compatible. A source depends
on one minor (`xippios-core~=0.2.1`) and adopts the next through conventions §15
(ADR-0018).

## Conventions

The rules this package implements live in [docs/conventions.md](docs/conventions.md)
and the decisions behind them in [docs/adr/](docs/adr/). Changes to a convention are
their own PR plus an ADR. [docs/roadmap.md](docs/roadmap.md) gives the order of the next
core, template and source releases, and
[docs/review-checklist.md](docs/review-checklist.md) the checklist every `sdk-*` PR is
reviewed against.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
