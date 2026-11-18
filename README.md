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
  (`json=`) or form-encoded (`data=`), and `post_json` and `delete_json` decode a write's
  answer as `get_json` decodes a read's, `None` for one with no body. Two hooks,
  `before_request` and `observe`, see each call and each response; `QuotaPolicy` uses
  them to wait out or refuse a request into a spent quota.
  `auth=None` sends one call without the client's key. `get_answer` returns the payload,
  parsed into the type it names, with its `retrieved_at`, a cache hit's stored time, and
  it alone stores an answer in the cache, once the answer decoded. A file is streamed
  to disk with `download`, never held in memory; `decode_text` and `decode_csv` read
  text and CSV next to `decode_json`; the cache stores no body over `cache_max_bytes`
  (8 MiB).
- **Auth helpers** that read the key from the environment on the first request:
  query parameter, header, bearer token or basic auth; and `RenewingBearerAuth`, the base
  for an upstream that exchanges a login or a refresh token for a short-lived bearer. A
  source's documented error shapes go into `ClientConfig.classify`, consulted on every
  response.
- **The api.data.gov gateway** (`xippios.core.data_gov`) for every source behind it:
  the key from `DATA_GOV_API_KEY`, the gateway's error answers, and one quota policy per
  process for that key.
- **Tenants** (`xippios.core.tenants`) for a source whose upstream serves each tenant from
  a host or under a key of its own: `Tenants` declares them in the environment, one
  client each, `list_task` gives the tool that names them, and `TenantLock` binds a
  server to one of them, which `xippios.core.mcp.serve_tenants` starts from `--org`.
- **The package contract** by which a host serves a source (ADR-0026, decision 8): `EnvVar`,
  a variable the package needs, and `xippios.core.mcp.ToolSet`, what its `build(**options)`
  returns, from which `build_server` builds its server and a host one server from several.
- **Error taxonomy**: `ConfigError`, `AuthError`, `RateLimitError`, `NotFoundError`,
  `ValidationError`, `UpstreamError`, `TransportError` and `InvalidRequestError` (the
  request as given cannot be served: a bad argument, or a refusal the source documents,
  detected before the call, mapped from upstream's own refusal or made from an answer the
  task cannot serve as asked), all under
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
- **Reference data**: loaders for code lists shipped inside a package, `PackagedList`
  for a list fetched from one upstream operation (its file, the meta of an answer from
  it, its writer), `matches`, `closest` and `nearest` for the list tasks and their
  refusals, and `render_enums`, which generates one module of `StrEnum` and `IntEnum`
  classes.
- **Adapters** that turn task functions into MCP tools (`xippios.core.mcp`) and FastAPI
  routes (`xippios.core.http`) without any logic of their own.
- **Test support**: a live-test gate, offline guarantees for every other test (no
  network, no rate-limit wait, a placeholder key), fixture recording with secrets
  scrubbed, replay through `respx`, and the family conformance check every source runs
  (`xippios.core.testing`).

## Install

```bash
uv add "xippios-core~=0.3.0"            # client, models, errors, reference, pagination
uv add "xippios-core[mcp]~=0.3.0"       # + MCP server helpers (official mcp SDK 2.x)
uv add "xippios-core[http]~=0.3.0"      # + FastAPI router helpers
uv add "xippios-core[testing]~=0.3.0"   # + pytest plugin, respx replay, fixture recording
```

Python 3.12 or later. A source package depends on one core minor, `~=0.3.0`, and each
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
`sort_key`. A link keeps its path and its other parameters and loses the credentials of
its query, a signed file link's `sig` or `X-Amz-Signature` say, as `scrub_url` writes
them. The fixture recorder and the replay helpers redact by the same rule
(`xippios.core.redaction`). A parameter the caller left `None` was not sent and is left
out of `meta.request`, so a task passes its parameters as they are.

A paging cursor whose name holds `token` as a whole word is data, and its source declares
it so once, in `_client.py`; every name it does not declare keeps the rule:

```python
from xippios.core.redaction import register_data_name

register_data_name("next_token")  # X's cursor: kept in meta.request, fixtures and replay
```

Only a name with the whole word `token` and no other credential word can be declared,
never `token` alone nor `access_token`, `refresh_token` or `id_token`, and a name a
`QueryKeyAuth` registers stays a credential.

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
the host can name a tenant and the query can carry a key. `request_description(response)`
gives that description, `GET /v1/series`, for the errors a source's `classify` maps:

```python
from xippios.core import NotFoundError, request_description

NotFoundError(f"no data for {request_description(response)}", source="example")
```

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
A request sent with `auth=None`, as `list_countries_async` sends one, or to another origin
than the base URL's spends no quota: the policy neither holds it back nor reads its
answer, and the limiter still paces it.
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
import re

import httpx

from xippios.core import AsyncClient, ClientConfig, NotFoundError, XippiosError
from xippios.core.data_gov import Gateway

DATA_PATH = re.compile(r"/api/psd/commodity/[^/]+/(?:country/[^/]+|world)/year/[^/]+")
gateway = Gateway("usda-psd", data_path=DATA_PATH)


def classify(response: httpx.Response) -> XippiosError | None:
    error = gateway.classify(response)  # API_KEY_*, the 429, NOT_FOUND, NoDataForYear
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
`api.data.gov`. FAS's answer for a market year it holds no data for, HTTP 404 with an
empty `text/plain` body, is `NoDataForYear` of `xippios.core.data_gov`, a `NotFoundError`
with the request's `path`, on the paths `data_path` matches and nowhere else. The gateway
reads the answers of the base URL's origin alone: a file host's 429 is core's plain
`RateLimitError`, not the gateway's.

A request the cache answers never waits: `before_request` runs after the cache lookup,
and a cache hit carries the time its entry was stored in
`response.extensions["xippios_cache_stored_at"]`, the hit's `retrieved_at`. A wrapper
whose answer may come from the cache calls `get_answer()` instead of `get_json()`, the
one call that stores an answer: a 200 once its body decoded and, with `parse=`, its
payload parsed, so a body that fails is requested again on the next call. `get`,
`get_json` and `request` read the cache and store nothing. The `Answer` carries the
payload and `retrieved_at`, the stored time on a hit and on the miss that stored it,
which reads the clock once for both.

```python
answer = await client.get_answer(
    "/api/regions", auth=None, parse=list[Region], endpoint="regions"
)  # Answer[list[Region]]; a payload that is not a list[Region] raises ValidationError
meta = ResultMeta(source="example", endpoint="regions", retrieved_at=answer.retrieved_at)
```

A wrapper that returns a value it derives from the payload keeps the time with it as an
`Answer` of that value's type, `Answer(codes, answer.retrieved_at)`, not as a pair of
its own.

The hooks are plain callables on `ClientConfig` (`before_request` may be async) for
anything else that has to see each call or each response.

`ClientConfig.classify` is asked before a 429 or 5xx is retried: a `RateLimitError`
with a `retry_after` beyond `backoff_max` is raised after one attempt instead of being
retried into a spent quota; an `UpstreamError` for a 5xx leaves the retries as they are;
any other error it returns, an `AuthError` say, ends them.

`auth=` on `request`, `get`, `get_json`, `post_json`, `delete_json`, `get_answer` and
`record` overrides the client's credentials for one call: `None` sends none, for a keyless
endpoint on the same host, and another `httpx.Auth` replaces them. `None` and the default
share the cache; a call with an `httpx.Auth` of its own bypasses it, neither looked up nor
stored.

A write wrapper sends through `post_json` or `delete_json`, which apply `classify`, the
hooks and the retry rule for a write as `request` does, never touch the cache, and decode
the answer, `None` for one with no body:

```python
draft = await client.post_json("/drafts", json={"message": {"raw": raw}})  # decoded JSON
await client.delete_json(f"/drafts/{draft['id']}")  # None: the answer is a 204
```

The client's own credentials go to the base URL's origin only, its scheme, host and port:
a request to an absolute URL on another origin is sent without them, and a call that must
send credentials there passes an `httpx.Auth` of its own. Every request the client builds
says where they go, for the hooks, in its extensions: `xippios_auth` is `"client"`,
`"none"` or `"own"`, and `xippios_origin` is `"base"` or `"other"`.

## A login or a refresh token: the renewing bearer

An upstream that issues a short-lived bearer for a long-lived credential, a login or an
OAuth refresh token, gets a subclass of `RenewingBearerAuth`. The source writes the token
request and reads its answer; core sends it, keeps the bearer and renews it:

```python
import httpx
from pydantic import SecretStr

from xippios.core import (
    AsyncClient,
    BearerToken,
    ClientConfig,
    RenewingBearerAuth,
    ValidationError,
)


class LoginAuth(RenewingBearerAuth):
    """The account's login, EXAMPLE_USERNAME and EXAMPLE_PASSWORD, for a bearer."""

    def token_request(self, request: httpx.Request) -> httpx.Request:
        form = {
            "username": self.credential("EXAMPLE_USERNAME"),  # read now, kept nowhere
            "password": self.credential("EXAMPLE_PASSWORD"),
        }
        return httpx.Request("POST", "https://api.example.org/auth/login", data=form)

    def read_token(self, response: httpx.Response) -> BearerToken:
        try:
            answer = response.json()  # {"access_token": "...", "expires_in": 3600}
            return BearerToken(SecretStr(answer["access_token"]), answer["expires_in"])
        except (ValueError, TypeError, KeyError):
            raise ValidationError(  # never quoting the answer, which holds the bearer
                "POST /auth/login answered HTTP 200, but not the documented answer",
                raw="",
                source="example",
            ) from None


client = AsyncClient(
    ClientConfig(source="example", version="0.1.0", base_url="https://api.example.org"),
    auth=LoginAuth(source="example"),  # logs in on the first request, not at import
)
```

The first request sends the token request ahead of it, with its `User-Agent`, and the
bearer, kept as a `SecretStr`, goes out as `Authorization: Bearer` until `margin` seconds
before its `expires_in` runs out (`RENEWAL_MARGIN`, 60 s, by default), when the next
request exchanges again. An answer whose status is in `renew_on`, `{401}` by default,
makes one more exchange and sends the request again, once; a source whose upstream
refuses a bearer with a 403 too sets `renew_on = frozenset({401, 403})` on its class. A
request that finds an exchange running on its event loop waits for it, so two first
requests exchange once, and two requests refused with one bearer renew it once.

A token answer other than HTTP 200 raises `token_refused(response)`: the taxonomy error
of its status, `503 from POST /auth/login: Service Unavailable`, with the reason phrase and
nothing of the answer, which a token endpoint may write from the credentials it was sent,
unless the source maps its upstream's refusals first and names what to run again, the
variables to check or the consent and its scope set. `read_token` raises
`ValidationError` for an answer that is not the documented one, quoting nothing of it.
`credential(name)` reads a credential from `credentials=`, given to the constructor, or
else from the variable, and an unset one raises `ConfigError` with the text of
`credential_help(name)`. The exchange runs inside httpx's auth flow, where it is not
paced, observed or cached, and its refusal ends the call; a transport failure of the
exchange is the request's own, which the retry policy sends again where it would without
the exchange, a GET say. It reads the token answer
and no other, so a `download` streams to its file, and the client sends its auth to the
base URL's origin only. httpx keeps the token answer in the final response's `history`
while that response lives; `get_json`, `get_answer` and the cache keep no response.
sdk-faostat's login and sdk-google-mail's refresh are its two token requests (ADR-0025).

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
    got = await client.download(url, dest)  # another host: the client's key stays off it
    # endpoint: the file's name as upstream names it, never its kind (conventions §4)
    # a signed link's signature reads REDACTED in meta.request
    meta = ResultMeta(source="example", endpoint="qs.crops.txt", request={"url": url})
    return Result(data=got, meta=meta)


for row in decode_csv(Path("qs.crops.txt"), delimiter="\t"):  # row by row, never whole
    print(row["COMMODITY_DESC"], row["VALUE"])  # headers as upstream prints them
```

`Downloaded` carries the path, the size, the content type, the file name from
`Content-Disposition`, the `ETag`, the `Last-Modified` text and when the file was
complete. `decode_text(response)` reads a text answer in the charset of its
`Content-Type` (UTF-8 by default, a byte order mark stripped), and `decode_csv` takes a
downloaded file, a response or an open text stream. A gzip or zip file is opened with the
stdlib, and its member read through `decode_csv` row by row:

```python
import gzip
import io

with (
    gzip.open("qs.crops.txt.gz") as raw,
    io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
):
    for row in decode_csv(text, delimiter="\t"):  # left open: the with closes it
        print(row["COMMODITY_DESC"])
```

Core ships no XML, spreadsheet or PDF parser. A `dest` that is a directory, or whose
directory does not exist, is refused with `InvalidRequestError` before anything is sent,
and the file is written with mode `0600`, its owner's alone. `register_tasks` and
`router_from_tasks` skip a task its `tasks.py` names in `BULK_TASKS`, so no tool or route
returns a file path. A body over `ClientConfig.cache_max_bytes` (8 MiB by default) is
returned and not cached.

## Multi-tenant sources

An upstream that serves each tenant from a host or under a key of its own (CashCtrl's
organisations, Gmail's mailboxes) is served by a source that declares its tenants in the
environment with `Tenants`, one client each, and names them with `list_task`
(`xippios.core.tenants`; ADR-0036, ADR-0042):

```python
from xippios.core import AsyncClient, BasicKeyAuth, ClientConfig, Tenants, list_task

TENANTS = Tenants(
    "example",
    list_var="EXAMPLE_TENANTS",  # EXAMPLE_TENANTS=acme,acme_test
    fields=("SUBDOMAIN", "API_KEY"),  # EXAMPLE_ACME_SUBDOMAIN, EXAMPLE_ACME_API_KEY
    reserved=("demo",),  # declared by EXAMPLE_DEMO_SUBDOMAIN and _API_KEY alone
)


def build(name: str) -> AsyncClient:
    subdomain = TENANTS.field(name, "SUBDOMAIN")  # EXAMPLE_<NAME>_SUBDOMAIN, stripped
    config = ClientConfig(..., base_url=f"https://{subdomain}.example.org/api")
    return AsyncClient(config, auth=BasicKeyAuth(TENANTS.var(name, "API_KEY")))


client = TENANTS.client_for("acme", build)  # acme's own client, built on first use
list_tenants = list_task(TENANTS, name="list_tenants")  # the tool example_list_tenants
```

The environment is read on every call. `client_for` keeps one client per tenant under a
digest of its variables, never their values, so a changed variable builds a new client
and closes the one it replaces. A name that is not declared is the caller's
`InvalidRequestError`, which lists the declared ones; a malformed list, or a missing or
refused value of a declared tenant, is the operator's `ConfigError`, which names the
variable. A source whose variables carry a prefix other than its slug names it:
`Tenants("google-mail", var_prefix="GOOGLE", ...)` reads `GOOGLE_WORK_REFRESH_TOKEN`, and
its errors name `google-mail`. The list task takes no argument and returns names only,
`meta.tenant` `None`, on the read server; `list_task(..., source=...)` names another
source than the registry's, for a registry that several sources share.

Every other task takes the tenant's name and sets `ResultMeta(tenant=name, ...)`; its
messages and results name tenants and variables, never a value, and core's error messages
leave the host out, since it names the tenant.

A server bound to one tenant serves that tenant alone, and none of its tools takes the
tenant's name. `bind_tasks(tasks, lock)` binds them to a `TenantLock`, and
`tenant_instructions` ends the server's instructions with a sentence that names the
tenant; `serve_tenants` builds the bound server from `--org` and runs it through `main`
(ADR-0036, ADR-0042). The source's `build(lock)` returns its tool set, as the package
contract has it, and `serve_tenants` builds the bound server from the tool set, named as
`server` is (ADR-0026):

```python
# xippios/example/mcp.py
from xippios.core import TenantLock, bind_tasks, tenant_instructions
from xippios.core.mcp import ToolSet, build_server, serve_tenants, tool_functions
from xippios.example import tasks
from xippios.example._client import TENANTS

INSTRUCTIONS = "Example via xippios. Every tool but example_list_tenants takes org."
BOUND = "Example via xippios."  # the bound server's text: no tool takes org


def build(lock: TenantLock | None = None) -> ToolSet:
    return ToolSet(
        "example",
        bind_tasks(tool_functions(tasks), lock),
        instructions=tenant_instructions(INSTRUCTIONS, lock, bound=BOUND),
    )


server = build_server(build())  # every declared tenant


def run() -> None:  # xippios-example-mcp --org acme serves acme alone
    serve_tenants(
        server,
        build,
        TENANTS,
        param="org",
        noun="organisation",
        check=lambda org: TENANTS.field(org, "SUBDOMAIN"),
    )
```

A bound tool keeps its name and its other parameters' `Annotated` constraints, and its
docstring and signature lose `org`, so a call that still names a tenant is refused like
any argument the tool does not declare; the tenant list lists the bound tenant alone.
The bound server's instructions end "This server is bound to org acme; every tool acts on
that organisation and takes no org." `--org acme` stops the process with exit status 2
before anything is served when `acme` is not declared or `check` raises, a missing
subdomain here; without `--org` the server serves every declared tenant. `main` holds the
bound server to loopback as it holds the unbound one. The HTTP router takes no lock: a
deployment that needs one declares only that tenant.

A source's `tests/conftest.py` calls `keep_reserved_tenants(TENANTS)` when pytest
imports it, so its tests see the reserved tenant, `demo`, and no other: it removes the
list variable and every other tenant's variables, by the registry's scheme, and keeps
the rest of the prefix (`xippios.core.testing`).

## Reference data and generated enums

A list a source fetches from one upstream operation and ships, so that its `list_*`
tasks and its argument checks need no call, is a `PackagedList`: `reference/<name>.json`
with `{"param", "endpoint", "fetched", "records"}` and an optional free-text `"note"`,
upstream's records under upstream's field names; any other key is refused. `<name>` is
the parameter, or a name of the list's own where two lists derive from one parameter.
The refresh script writes it; the tasks read it:

```python
from datetime import UTC, datetime

from xippios.core import PackagedList, Result, UnknownCode, closest, matches

# scripts/refresh_reference.py: the records as upstream named them, the time of the fetch
records = [record.dump_upstream() for record in commodities]  # from the api/ wrapper
PackagedList(
    param="commodities", endpoint="GetCommodities", fetched=datetime.now(UTC), records=records
).write(REFERENCE / "commodities.json")  # fetched written to the second


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

The answer's `meta` follows ADR-0041, decision 1: `endpoint` is the upstream operation the list came
from, `retrieved_at` the time it was fetched, `vintage` an upstream release identifier
only when one is passed (a fetch date is not a vintage), `total` `None`. A file whose
`fetched` is a bare date, as refresh scripts wrote it before template v0.3.0, reads as
00:00 UTC of that day; `write` writes `fetched` to the second. A list of values is
records of one field named by the upstream parameter (`[{"state_alpha": "AK"}, ...]`).
`UnknownCode` names the value, the list and its fetch date, the closest codes (or a
`hint=`), an optional `reason=`, and that the list is out of date if upstream added the
code since. `closest` matches a code by its text and its name, with a `cutoff=` below
0.6 for short codes, and `nearest(value, codes)` names the integer codes nearest by
number.

Other code lists are read with `load_json` or `load_table` (`load_csv`, which
`load_table` calls for a CSV file, stays in `xippios.core.reference`). The refresh
script generates `enums.py` from the lists with one `render_enums` call, then runs
`ruff format` and `ruff check --fix` on it, and the module is committed as formatted:

```python
from xippios.core.reference import id_name_pairs, render_enums

records = [
    {"attributeId": 4, "attributeName": "Area Harvested"},
    {"attributeId": 126, "attributeName": "Total Disappearance"},
    {"attributeId": 173, "attributeName": "Total Disappearance"},
]
source = render_enums(
    {
        # Strings: a StrEnum, member names derived from the values.
        "sector_desc": ["ANIMALS & PRODUCTS", "CROPS"],
        # (id, name) pairs: an IntEnum, values the ids, in upstream order.
        "attributeId": id_name_pairs(records, id_field="attributeId", name_field="attributeName"),
    },
    fetched={"sector_desc": "2026-10-27", "attributeId": "2026-10-24"},  # or one date
    class_names={"sector_desc": "Sector"},  # attributeId gives AttributeId by default
    generator="scripts/refresh_reference.py",
)
ENUMS.write_text(source, encoding="utf-8")
# then: uv run ruff format src/xippios/example/enums.py
#       uv run ruff check --fix src/xippios/example/enums.py
```

```python
class AttributeId(IntEnum):
    """Values of ``attributeId`` (fetched 2026-10-24)."""

    AREA_HARVESTED = 4
    TOTAL_DISAPPEARANCE_126 = 126
    TOTAL_DISAPPEARANCE_173 = 173
```

An upstream whose ids are integers gets `IntEnum` (conventions §3), so a member compares
equal to the id in upstream's data; a name several ids share gets `_<id>`. Each class's
docstring is one line naming the list and its fetch date, which an MCP tool's input
schema shows the agent (conventions §8). The output is plain and ASCII-only: values are
written as `ascii()` writes them, every character outside ASCII as an escape
(`'C\xf4te d\u2019Ivoire'`), one member per line, `__all__` in the order of the lists, and
a line over 100 columns carries `# noqa: E501`; ruff chooses the quotes, wraps what fits
and sorts `__all__`. A key, class name, fetch date or generator text that is not
printable ASCII is refused, and so is an empty list, a repeated id, and a value with
nothing to derive a member name from (an empty or a non-Latin label) or whose name
collides; the refresh script names that member by hand, once:

```python
source = render_enums(
    {"short_desc": values},
    fetched="2026-10-27",
    member_names={"short_desc": {"\u5317\u4eac": "BEIJING"}},
)
```

## MCP server in five lines

```python
# xippios/example/mcp.py
from xippios.core.mcp import build_server, main, tool_functions
from xippios.example import tasks

server = build_server("example", tool_functions(tasks))  # tasks.__all__ minus BULK_TASKS


def run() -> None:  # entry point: xippios-example-mcp = "xippios.example.mcp:run"
    main(server)
```

Tool names are `<source>_<function>` (`example_get_series`), the docstring is the tool
description, the signature is the input schema. Results are capped at 200 rows or
64 KB with a note on how to narrow the query, and a capped list whose `meta.request`
records an integer `start` says where to resume (`; resume with start=200`), unless not
even its first row fits, which the note then says instead. A model that holds one list of
rows keeps its other fields whole past 64 KB and has its rows cut the same way; any other
result past it is the note and a preview of its first 64 KB. Errors come
back as `error: <Class>: <message>`, arguments the tool's schema refuses too
(`error: InvalidRequestError: year: Input should be a valid integer, ...`), before the
tool runs and never with pydantic's rendered error (its URL, input type or input value),
and so does an argument the tool does not declare (`error: InvalidRequestError: yaer:
Not an argument of this tool; it takes series_id, year`). An error answer sets `isError`
on the tool's result beside its text. A constraint that an `Annotated` parameter declares,
`Annotated[int, Field(ge=1)]` say, reaches the input schema and the check.
`--http` serves streamable HTTP instead of stdio.
A reference tool whose whole list an agent needs gets a cap of its own, keyed by the
task function's name, with the rows and bytes the source judges it needs:
`build_server(..., caps={"list_commodities": ResultCap(max_rows=500,
max_bytes=100_000)})`. So does a tool whose result is one upstream page that must return
whole, a cursor-paged page with its `next_token` or a bounded lookup, with a byte bound
of its own and the row bound unchanged (ADR-0038, decision 4), and so does a
tool whose result is one upstream document or table that an agent reads whole, a report
or a table's page, with the rows and bytes it needs and a note that says how to read a
part of it (ADR-0038, decision 4); every other tool keeps 200 rows or
64 KB. The note says "narrow the query to see the rest" and
promises no filter; a tool with filters names them in its cap, `ResultCap(note="filter
by year to see the rest")`. `ResultCap` comes from `xippios.core`, so the `MCP_CAPS` in
a source's `tasks.py` need no `mcp` extra. A write server (`build_server(...,
read_only=False)`) refuses, with `ValueError`, a task that does not take `confirm: bool
= False`, and `--http` serves it on a loopback `--host` only (`LOOPBACK_HOSTS`:
`127.0.0.1`, `localhost`, `::1`): it carries no authentication. `--allow-remote` serves
it beyond loopback, behind a gateway that adds it. A read server that reaches what no
deployment may serve without authentication, a mailbox say, is held the same way with
`build_server(..., loopback_only=True)` (ADR-0025, D-a); `is_loopback_only(server)`
answers for both kinds. The usage line names the entry point that runs, and the help of
`--allow-remote` and the refusal name the server's kind.

`tool_functions(tasks)` gives the functions of `tasks.__all__` that become tools, those in
its `BULK_TASKS` left out, read from the module it is given; it refuses an entry whose
function carries another `__name__`, since a task's name is its entry in `__all__` for its
tool name, its `MCP_CAPS` key and its `BULK_TASKS` entry alike. A task named in
`BULK_TASKS` is skipped by `register_tasks` too, a wrapper whose `__wrapped__` leads to it
included, so `mcp.py` may pass every name of `tasks.__all__`; a cap named for it is
refused. Request URLs are not logged: `build_server` and `main` set the `httpx`,
`httpcore`, `httpx2` and `httpcore2` loggers to `WARNING` (`quiet_request_logging`),
because a URL can carry an API key or a tenant host; httpx2 is the `mcp` SDK's own HTTP
client.

A host that builds its servers itself, such as xippios-mcp, imports what `build_server`
and `main` use from `xippios.core.mcp`: `register_tasks` with `read_only` and
`loopback_only`, `tool_functions`, `quiet_request_logging` after each `MCPServer` it
constructs, and `is_write_server`, `is_loopback_only` and `LOOPBACK_HOSTS` to hold a
server to loopback as `main` does (ADR-0026, decision 5).

A source's own options go through `main`'s hooks, so the command line is parsed once:
`add_options` puts them on core's parser, so `--help` lists them; `apply_options(namespace,
server)` returns the server to run; and a `XippiosError` it raises, a missing variable
say, stops the process with exit status 2 and the message, before anything is served.

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

## The package contract

A host such as xippios-mcp serves a source through its package contract (ADR-0026,
decision 8): the variables the package needs and the tool set its `build(**options)`
returns. A source's `_client.py` declares its variables, by name or, for one per tenant,
by a pattern such as `EXAMPLE_<NAME>_API_KEY`, each with whether it is a secret and whether
it is required, both stated since neither has a default. An `EnvVar` names a variable and
never reads one, and it needs no `mcp` extra:

```python
from xippios.core import EnvVar

ENV_VARS = (EnvVar("EXAMPLE_API_KEY", secret=True, required=True),)
```

Its `mcp.py` builds its `ToolSet`, its tasks as its lock binds them, its caps, instructions
and version, its option hooks, and whether it writes (`read_only=False`) and is held to
loopback (`loopback_only=True`), and its server from it:

```python
# xippios/example/mcp.py
from xippios.core.mcp import ToolSet, build_server, main, tool_functions
from xippios.example import tasks


def build() -> ToolSet:
    return ToolSet(
        "example",
        tool_functions(tasks),
        caps=tasks.MCP_CAPS,
        instructions="Example via xippios. Call example_list_areas first.",
        version="1.2.0",
        add_options=tasks.mcp_add_options,  # main's hooks, a --split-years say
        apply_options=tasks.mcp_apply_options,
    )


TOOLS = build()
server = build_server(TOOLS)  # xippios-example, with the tool set's version and instructions


def run() -> None:
    main(server, add_options=TOOLS.add_options, apply_options=TOOLS.apply_options)
```

Beside a tool set `build_server` takes `name` alone. A multi-tenant source's
`build(lock=None)` passes its tasks through `bind_tasks` and its instructions through
`tenant_instructions`, and `serve_tenants(server, build, ...)` builds the bound server from
the tool set it returns (see Multi-tenant sources). A host builds one server from the tool
sets of several packages, each tool with its own package's caps, a write tool set making it
a write server and a held one holding it to loopback, and applies each package's hooks as
its entry point does when it runs without options:

```python
server = MCPServer("xippios-group")
quiet_request_logging()
for tools in (example_mcp.build(), other_mcp.build()):
    register_tasks(server, tools)
    if tools.apply_options is not None:
        tools.apply_options(tools.option_defaults(), server)  # --split-years at its default
```

`option_defaults()` raises `ValueError`, naming the source, for an option of `add_options`
that has no default, where argparse would print its usage and end the host.

## HTTP routes in two lines

```python
from xippios.core.http import router_from_tasks

router = router_from_tasks("example", [tasks.get_series])  # GET /example/get_series?series_id=...
```

Mount it on your FastAPI app. A task whose parameters are all scalars is a `GET` with
query parameters; a task with a mapping, list or model parameter is a `POST` whose JSON
body is keyed by parameter name. Responses are the `Result[T]` envelope; errors are
RFC 9457 problem details (`application/problem+json`), `InvalidRequestError` as 422. An
argument a typed parameter refuses is one too, answered before the task runs with the
detail `level: Input should be 'STATE' or 'COUNTY'` and never with the input; a parameter
keeps its `Annotated` constraints, as in the tool.

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
and `http.py` serve exactly `tasks.__all__` minus `BULK_TASKS`; every task, read and
write, is synchronous, returns `Result[T]` and has an agent docstring; the README's status
table lists exactly the read and the write tasks; `.copier-answers.yml` names a template
tag; `pyproject.toml` bounds `xippios-core` with `~=`. A write server is its source's to
test, with `await assert_write_tools(write_server, write_tasks, source="example",
read_server=read_server, router=router)`: a write server, its tools exactly the write
tasks, each taking `confirm: bool = False` last, and none of them on the read server or
the router. A source whose adapters drop a task, or whose README table is stale, fails CI
before a reviewer looks. The package under test is the one `tasks.py` under
`src/xippios/`, or the ini option `xippios_package`.

```toml
# pyproject.toml: the variables that hold the placeholder key in offline tests
[tool.pytest.ini_options]
xippios_placeholder_key_envs = ["EXAMPLE_API_KEY"]
```

- `@pytest.mark.live` tests are skipped unless `XIPPIOS_LIVE_TESTS=1`, and `anyio`
  tests run on asyncio (the plugin's `anyio_backend`).
- The whole run is offline (ADR-0035). From `pytest_configure` on, during collection, in
  fixtures and in tests, a request through httpx's default transports (the plugin
  patches httpcore's connection pools, which they all send through) raises
  `RuntimeError` naming its method and path unless `respx` answers it, a `respx` route
  that passes through included; mark a test `network` to let it through. In every test
  not marked `live`, the rate limiter never waits (mark a test `rate_limited` to keep
  it), no `QuotaPolicy` pauses, refuses or stays spent from one test to the next
  (`rate_limited` keeps the pause too), every `MemoryCache` starts and ends empty (a
  cache backend of the source's own is the source's to clear), and every `EnvKeyAuth`
  sends `PLACEHOLDER_KEY` while the variables named in `xippios_placeholder_key_envs`
  hold it (fixture `placeholder_api_key`), whatever the shell or an earlier live test
  left behind. Every credential that a `RenewingBearerAuth` reads is the placeholder too,
  and a variable unset or empty is still its `ConfigError`, so the ini option names each
  variable a token request reads. The `httpx`, `httpcore`, `httpx2` and `httpcore2` logger levels come back
  after every test.
  After a live run the summary prints each quota policy's last reading, `quota after the
  live run: usda-psd: 986 of 1000 requests left as of ...`. ADR-0035 states the edges of
  these guarantees.
- `replay_fixture("api_get", "corn_2024")` mounts `tests/fixtures/api_get/corn_2024.json`
  on its method, host and path, the directory named after the wrapper function (or the
  task, for an exchange recorded through a task); `match_params=["countOnly"]` makes the
  route match those recorded query parameters too. A parameter's absence cannot be
  matched: where two fixtures share a path, mount the one with `match_params` first,
  since `respx` tries routes in order. `sent_urls(route)` gives the URLs the route
  received as scrubbed strings, so no request has to sit in the test's frame, and
  `sent_query(route)` the last one's query as a mapping, to compare with
  `recorded_query(fixture)`. The request body is never matched: `sent_bodies(route)`
  gives each body the route received, oldest first, a JSON body decoded and a form as a
  mapping of its fields, credentials `REDACTED` by the same rule, `None` for a request
  without one, so a test asserts `sent_bodies(route)[-1] == {"name": "Corn", "n": "2"}`.
  `url=` serves a recorded answer at another URL, for a state upstream answers alike
  there, such as an empty 404 recorded for one year standing in for another, or for a
  test that asserts only what was sent, never for a state another operation was never
  seen in (conventions §10). Annotate the fixture as `ReplayFixture`.
- `response_from_fixture(load_fixture(path))` is a recorded answer as an
  `httpx.Response`, its request attached, for calling a source's `classify` directly.
- `assert_time_between(result.meta.retrieved_at, before, after)` brackets a time with
  two readings around the call and `CLOCK_SLACK` (five seconds) either side, for a host
  whose clock steps back.
- `record(client, "/v1/series", fixture_path(...), params=...)` records a live response
  with credentials scrubbed and without the response headers that only identify a
  request (`x-request-id`, `x-amz-cf-id`, `x-transaction-id` and the others of
  `xippios.core.testing.fixtures.REQUEST_ID_HEADERS`). Never hand-write a fixture.
  `json=` or `data=` (a form) send a body, recorded with its content type. The recording
  goes through the source's client, its base URL, auth, rate limit and hooks, and sends
  once: never retried, whatever its `RetryPolicy` says, and never answered from the cache,
  so a 429 or a 5xx is recorded as it came and spends no second request. It reads at
  most `max_read_bytes` of the body (32 MiB by default, `None` for no bound): past it,
  the reading stops and the recording raises, naming the method, the path and the bound,
  and nothing is written. `max_bytes=80_000`
  cuts a large answer's body: a JSON array after its first whole elements, in upstream's
  own text, a text after its first bytes, never inside a secret, and the fixture is
  marked `truncated` with the whole body's size and sha256 (and an array's length).
  `array_key="data"` cuts the array of that top-level key, `{"data": [...]}`, the rest
  of the object kept as upstream wrote it, and `keep="last"` keeps an array's last
  elements, for a list ordered oldest first. A JSON object without `array_key`, XML,
  ZIP, XLSX, gzip, XLS or a body that is not UTF-8 text is refused: record a small real
  answer or sample instead. It bounds the body, not the file, which escapes the body as
  a JSON string, text outside ASCII up to three times as long: 80,000 bytes keep a file
  under the 256 KiB cap.

`mcp_call(server, "example_get_series", {...})` calls a tool through an in-process MCP
client, so the server's middleware, the argument check included, runs as for a real client;
it returns the decoded JSON and fails the test on `error:` text. `mcp_call_text` returns
the text, an error answer's flagged `isError` included, to assert a refusal; an unknown tool
or a task that crashed fails both.

A recording names the values that must never be written:

```python
from xippios.core.testing import Scrub, fixture_path, record_sync

record_sync(
    client,
    "/account/list.json",
    fixture_path(FIXTURES, "account_list", "one"),
    scrub=Scrub(secrets=[tenant_name]),  # REDACTED wherever it appears as given
)
```

A value known only once upstream answers, such as a login's or a refresh's tokens, whose
names (`AccessToken`) are no credential's, is read from the answer by a function of it:

```python
def tokens(response: httpx.Response) -> list[str]:
    result = response.json().get("AuthenticationResult", {})  # none in an error answer
    return [result[name] for name in ("AccessToken", "IdToken", "RefreshToken") if name in result]


record_sync(
    client,
    "/auth/login",
    fixture_path(FIXTURES, "auth_login", "login"),
    method="POST",
    data={"username": username, "password": password},
    auth=None,
    scrub=Scrub(secrets=[username, password], response_secrets=tokens),
)
```

The fixture is scrubbed in memory, verified and written once: if a named value or one
`response_secrets` read is still in the URL, a header value or a text body, nothing is
written and the error says where, never what. A form a value takes that differs from it (percent-encoded, behind a JSON
escape), or a tenant's host, the source rewrites itself, on the `Fixture` that
`fixture_from_response` returns, and writes the file with `write_fixture(fixture, path)`,
laid out as `record` writes it; `fixture_text(fixture)` gives that text. A body that is
not UTF-8 text cannot be scrubbed and is refused unless `Scrub(allow_binary=True)` stores
it base64, flagged.

A download's replay fixture may carry as its body the sample its parser tests read, so
the download replays that file. It is marked `sample`, with the whole file's size and
sha256, and never `truncated`, which stays the recorder's cut:

```python
import hashlib

from xippios.core.testing import fixture_from_response, fixture_path, write_fixture

recorded = fixture_from_response(response)  # the download's exchange, its body whole
whole = response.content
body = recorded.response.model_copy(
    update={
        "body": sample.decode(),  # the sample under tests/fixtures/files/<file_kind>/
        "sample": True,
        "original_bytes": len(whole),
        "sha256": hashlib.sha256(whole).hexdigest(),
    }
)
write_fixture(recorded.model_copy(update={"response": body}), fixture_path(FIXTURES, ...))
```

`model_copy` checks nothing; `write_fixture` refuses a fixture that `load_fixture` would
not read back, such as a sample without its size and sha256, and writes nothing.

## Status

Release 0.3.2, alpha.
[CHANGELOG.md](https://github.com/xippios/sdk-core/blob/main/CHANGELOG.md) lists what
changed in each release, and a change's entry waits under
[changelog/](https://github.com/xippios/sdk-core/blob/main/changelog/README.md) as a
fragment until the release assembles it.

| Module | What | Status |
| --- | --- | --- |
| `xippios.core.client` | httpx client, retries, rate limit, cache with a byte bound, quota policy, request hooks, env-key auth, the renewing bearer, `get_answer`, `download`, `decode_text`, `decode_csv` | alpha |
| `xippios.core.errors` | taxonomy, `UnknownCode`, response classification, `request_description` | alpha |
| `xippios.core.data_gov` | `Gateway`: the api.data.gov key, the gateway's `classify` of its own answers with `NoDataForYear` on a data path, one quota policy per process | alpha |
| `xippios.core.redaction` | the one credential rule of the envelope, the recorder and replay, `register_data_name`, signed links | alpha |
| `xippios.core.models` | `UpstreamModel` with `dump_upstream`, `Result`, `ResultMeta` with `published_at_naive`, `ResultCap`, `parse` | alpha |
| `xippios.core.reference` | packaged CSV/JSON loaders, `PackagedList`, `matches`, `closest`, `nearest`, generated `StrEnum`/`IntEnum` modules | alpha |
| `xippios.core.pagination` | `paginate_offset` (a page-numbered endpoint maps the offset to its page), `collect` | alpha |
| `xippios.core.tenants` | `Tenants`, a multi-tenant source's tenants declared in the environment with one client each, `list_task`, the tool that names them, and `TenantLock` with `bind_tasks` and `tenant_instructions`, a server bound to one of them | alpha |
| `xippios.core.contract` | `EnvVar`, a variable of the package contract | alpha |
| `xippios.core.mcp` | tool registration with the argument check and the write server's `confirm` rule, `tool_functions`, result caps, error text, CLI with option hooks and the loopback rule for write and `loopback_only` servers, `serve_tenants`, quiet request log, `ToolSet`, the package contract's tool set, built by `build_server` and registered by `register_tasks` | alpha |
| `xippios.core.http` | router factory, problem details | alpha |
| `xippios.core.testing` | live gate, offline run, record (sent once, read up to `max_read_bytes`, with `max_bytes=`, `array_key=` and `keep=`), the fixture writer and the `sample` mark, replay with `sent_urls`, `sent_query` and `sent_bodies`, scrub of named secrets and of values read from the answer with a plain verify, `mcp_call`, `assert_write_tools`, `keep_reserved_tenants`, family check | alpha |

Alpha: while core is 0.x, a new minor version may change the public surface, with no
backward compatibility across minors; patch releases stay compatible. A source depends
on one minor (`xippios-core~=0.3.0`) and adopts the next through conventions §15
(ADR-0039).

## Documents

- sdk-core: [docs/conventions.md](https://github.com/xippios/sdk-core/blob/main/docs/conventions.md) — the rules of the family, which this package implements and every `sdk-*` repository follows; a change to one comes with an ADR.
- sdk-core: [docs/definition-of-done.md](https://github.com/xippios/sdk-core/blob/main/docs/definition-of-done.md) — what a change satisfies before its pull request is opened.
- sdk-core: [docs/review-checklist.md](https://github.com/xippios/sdk-core/blob/main/docs/review-checklist.md) — the checklist every `sdk-*` pull request is reviewed against.
- sdk-core: [docs/handover.md](https://github.com/xippios/sdk-core/blob/main/docs/handover.md) — the record of each core release and how a source adopts it.
- sdk-core: [docs/roadmap.md](https://github.com/xippios/sdk-core/blob/main/docs/roadmap.md) — the order of the next core, template and source releases.
- sdk-core: [docs/adr.md](https://github.com/xippios/sdk-core/blob/main/docs/adr.md) — the index of the architecture decision records under `docs/adr/`, the decisions behind the rules.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
