# xippios-core

Shared foundation of the [xippios](https://github.com/xippios) Python SDK family. Every
`xippios-<source>` package depends on it; nothing in it knows about any particular
upstream API.

The sections below show each part of it as a source package uses it, and the conventions,
under Documents, hold the rules that a source is held to.

## Install

```bash
uv add "xippios-core~=0.4.1"            # client, models, errors, reference, pagination
uv add "xippios-core[mcp]~=0.4.1"       # + MCP server helpers (official mcp SDK 2.x)
uv add "xippios-core[http]~=0.4.1"      # + FastAPI router helpers
uv add "xippios-core[testing]~=0.4.1"   # + pytest plugin, respx replay, fixture recording
```

Python 3.12 or later. A source package depends on one core minor, `~=0.4.1` from the patch
that ships what it uses, and each extra likewise (conventions §12).
[CHANGELOG.md](https://github.com/xippios/sdk-core/blob/main/CHANGELOG.md) lists what
changed in each release, and a change's entry waits under
[changelog/](https://github.com/xippios/sdk-core/blob/main/changelog/README.md) as a
fragment until the release assembles it.

## 30-second example

A source package writes its task function once, async, and derives the sync one:

```python
from pydantic import Field

from xippios.core import (
    AsyncClient,
    ClientConfig,
    KeyAuth,
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
    # the key as ?key=..., read on the first request
    auth=KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source="example"),
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
    answer = await client.get_answer("/v1/series", params=params)
    rows = parse(list[Series], answer.payload["data"], source="example", endpoint="series")
    meta = ResultMeta(
        source="example", endpoint="series", request=params, retrieved_at=answer.retrieved_at
    )
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
only where a `KeyAuth` sends the key under that name, as above, which registers it
for its source; in every other source it is data, also in a host that loads both, and so
is a `sort_key`. The family check holds a source's key class to the package's own slug,
so that its envelopes read its key's name as a credential. A link keeps its path and its other parameters and loses the credentials of
its query, a signed file link's `sig` or `X-Amz-Signature` say, as `scrub_url` writes
them. The fixture recorder and the replay helpers redact by the same rule
(`xippios.core.redaction`). A parameter the caller left `None` was not sent and is left
out of `meta.request`, so a task passes its parameters as they are.

A paging cursor whose name holds `token` as a whole word is data, and its source declares
it so once, in `_client.py`, for itself; every name it does not declare keeps the rule:

```python
from xippios.core.redaction import register_data_name

register_data_name("next_token", source="example")  # kept in meta.request, fixtures, replay
```

Only a name with the whole word `token` and no other credential word can be declared,
never `token` alone nor `access_token`, `refresh_token` or `id_token`, and a name a
query `KeyAuth` registers stays a credential.

A release time upstream prints without a zone (`2026-10-06T08:00:00`) goes into
`published_at` as printed, with `published_at_naive=True`, and `vintage` keeps the
release identifier as upstream names it; `ResultMeta` refuses a naive time without the
flag, the flag without a naive time, and any field it does not define.

A parameter that takes back the `meta.vintage` of an earlier call, to return only what
changed since, filters with `newer_than`: the source hands its own reader of the vintage
text, since core ships none, and the task sets `meta` from the whole answer, so an answer
with nothing newer still names the newest release (ADR-0052; ADR-0059, decision 4):

```python
from datetime import datetime

from xippios.core import InvalidRequestError, Result, ResultMeta, newer_than


def read_since(text: str) -> datetime:
    """A release time printed without a zone; a zone and an unreadable text are refused."""
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(text)  # a date alone is its midnight
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is not None:  # comparing the two would invent a zone
        raise InvalidRequestError(
            f"since must be a release time without a zone, got {text!r}. Nothing was sent.",
            source="example",
        )
    return parsed


def released(release: Release) -> datetime:
    return release.released_at  # naive, as upstream printed it


async def get_release_dates_async(since: str | None = None) -> Result[list[Release]]:
    if since is not None:
        read_since(since)  # refused before the request, never after it
    releases = await api.get_release_info()  # the whole answer
    newest = max(releases, key=released, default=None)
    meta = ResultMeta(
        source="example",
        endpoint="GetReleaseInfo",
        published_at=None if newest is None else newest.released_at,
        published_at_naive=newest is not None,
        vintage=None if newest is None else newest.released_at_text,  # the text as printed
        request={"since": since},
    )
    kept = newer_than(since, releases, released=released, read=read_since)
    return Result(data=kept, meta=meta)
```

`newer_than(since, items, *, released, read)` keeps the items whose release is strictly later
than `read(since)`, in upstream's order, an equal release being no newer, and every item for
`since=None`; an item whose `released` gives `None` is kept, since it cannot be shown to be no
newer. It reads `since` once, before the first item, and the reader's `InvalidRequestError`
passes as raised. A release that does not compare with what the reader gave, a month against
a time or a time with a zone against one without, raises `TypeError` naming both values and
their types: a fault of the source's code, which mypy does not catch. A source whose vintage
is no time hands a reader of its own form, a release month `"2026-09"` read into `(2026, 9)`
and compared with each record's
`(release_year, release_month)`. A `since` that bounds dates or periods beside an `until`,
both included, is another rule, and this helper does not serve it (conventions §4).

A task that assembles a period series from one upstream call per period, a market year or a
month, declares its ceiling once as a `Ceiling`, checks the range against it before the first
request, and sends the requests with `fetch_periods`, which returns each period with its
answer (conventions §4, ADR-0054):

```python
from xippios.core import Ceiling, InvalidRequestError, Result, ResultMeta, fetch_periods
from xippios.example.errors import NoDataForYear  # a NotFoundError of the source's own

SERIES = Ceiling(10, unit="market years", source="example")  # the same over MCP


async def get_weekly_series_async(code: int, start_year: int, end_year: int) -> Result[list[Week]]:
    if start_year > end_year:  # the order of a range stays the source's own refusal
        raise InvalidRequestError(f"start_year {start_year} is after end_year {end_year}.")
    SERIES.check(end_year - start_year + 1, asked=f"{start_year} to {end_year}")
    fetched = await fetch_periods(
        range(start_year, end_year + 1),
        lambda year: api.get_weeks(code, year),  # one request per market year
        skip=(NoDataForYear,),  # upstream's empty 404: a year without data
    )
    weeks = sorted((week for _, answer in fetched for week in answer), key=week_ending)
    newest = max(weeks, key=week_ending, default=None)  # the vintage stays the task's
    meta = ResultMeta(
        source="example",
        endpoint="GetWeeks",
        vintage=None if newest is None else newest.week_ending.isoformat(),
        request={"code": code, "start_year": start_year, "end_year": end_year},
    )
    return Result(data=weeks, meta=meta)
```

`check(count, *, asked=None, advice=None)` refuses more periods than the ceiling in force with
`InvalidRequestError`, `2010 to 2021 is 12 market years; one call fetches at most 10 market
years. Nothing was sent. Ask for fewer market years.`, which says before its advice that
nothing was sent, as conventions §5 ask of a refusal of the call as given, and `advice` takes
the place of the last sentence where the source names its own parameters. A task calls `check`
before any request of the call, which makes that sentence true, and a task that can check a
range only after a request words that refusal itself and says what was sent (ADR-0054,
amendment 2026-11-22). The two stay apart, so a task sends a release list or a count between
them and still refuses a range before any request. `fetch_periods(periods, fetch, *, skip=())`
awaits each request before the next, in the order given, passes over a period whose fetch
raises one of `skip`, and returns the other periods with their answers: the task derives its
vintage itself, from the rows or from a release list. When a fetch after the first raises, the
helper returns nothing and raises that error again, the same instance with its class, its
attributes, its cause and its traceback, and its message ends with the periods answered before
it, those passed over included, by their count, the first and the last, each by its `str`:
`503 from GET /v1/weeks/2023: Service Unavailable. The series stopped at 2023 after 2 periods
answered, 2021 to 2022, and returns nothing.` Answered holds for a loop over counts too, which a
task may run before the loop over its data (ADR-0054, amendment 2026-11-22). An error that is
no `XippiosError` keeps its arguments and gets that sentence as a note, and a failure in the
first period passes as raised.

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

A task whose upstream counts a query's records on request and serves at most a limit of
them per call counts first with `fetch_counted`: a count of 0 answers the task's empty
answer and sends no data request, and a count over the limit raises `QueryTooLarge` before
the data request (ADR-0053):

```python
from xippios.core import Result, ResultMeta, fetch_counted

RECORD_LIMIT = 100_000  # the most records upstream serves per call
NARROW = "Split by period, then by reporter, and count each part with get_counts."


async def get_data_async(period: str, reporter: str | None = None) -> Result[list[Record]]:
    request = {"period": period, "reporter": reporter}

    async def count() -> int:
        return (await api.get_count(**request)).count  # upstream's count, read as an int

    async def fetch() -> list[Record]:
        return (await api.get(**request)).data

    rows, total = await fetch_counted(
        count, fetch, limit=RECORD_LIMIT, empty=[], narrow=NARROW, source="example"
    )
    meta = ResultMeta(source="example", endpoint="get", request=request, total=total)
    return Result(data=rows, meta=meta)
```

`fetch_counted(count, fetch, *, limit, empty, narrow, source=None)` returns the data with
the count, `(empty, 0)` for a count of 0, so the task sets `meta.total` from the count it
already paid for, and `empty=[]` beside a fetch of `list[Record]` types as `list[Record]`
under mypy. A count equal to the limit fetches, and an error that either request
raises passes as raised. `count` gives an `int`: a float, a whole one such as `1234.0`
included, or a `bool` raises `TypeError`, and a negative count `ValueError`, before the data
request, since a source reads upstream's count into an `int` where it parses the answer, as
a pydantic `int` field reads `1234.0` and refuses `1234.5`. `QueryTooLarge(count, *, limit,
narrow, request=None, source=None)` carries the fields, and core words its message from them,
`narrow` last: `query would return 5,006,385 records; upstream serves at most 100,000 per
call. Split by period, ...`; and with a count of `None`, for upstream's own refusal of the
query that a source's `classify` maps, `upstream refused the query as too large; it serves at
most 50,000 records per call. ...`. A size that a source reads from the arguments, with nothing
counted, is the source's own refusal, which says that nothing was sent (ADR-0053, amendment
2026-11-24). That `classify` passes `request=request_description(response)`, since a
message about an answer names its request, and the message names it in place of the query:
`upstream refused GET /v1/data as too large; ...`. A refusal before the data request names
none. A source subclasses it only for an attribute of its own, worded in `narrow`, such
as the `year` that alone is over the limit.

A task that collects every page of an offset-paged list walks them with `fetch_pages`, under
the bound of pages that its docstring states as the most requests one call spends (ADR-0061,
decision 8). Its `fetch` answers a page's items with upstream's count, and the walk sends no
request at or past that count (ADR-0034, amendment 2026-11-24):

```python
from xippios.core import Result, ResultMeta, fetch_pages

PAGE_SIZE = 100  # upstream's page size, sent explicitly
MOST_PAGES = 24  # the most requests one call spends, 96 with the client's retries


async def list_regions_async(*, page: int | None = None) -> Result[list[Region]]:
    async def fetch(offset: int) -> tuple[list[Region], int | None]:
        answer = await api.list_regions(page=offset // PAGE_SIZE, per_page=PAGE_SIZE)
        return answer.data, answer.total  # the page's items and upstream's count

    if page is not None:
        regions, total = await fetch(page * PAGE_SIZE)
    else:
        regions, total = await fetch_pages(
            fetch, page_size=PAGE_SIZE, most=MOST_PAGES, paging="page", source="example"
        )
    meta = ResultMeta(source="example", endpoint="regions", request={"page": page}, total=total)
    return Result(data=list(regions), meta=meta)
```

`fetch_pages(fetch, *, page_size, most, paging, start=0, stop=None, key=None, source=None)`
returns the items in upstream's order with the count of the last page fetched, `meta.total`'s.
A page shorter than `page_size` ends the walk, and so does the offset that reaches upstream's
count, with no request for an empty page. Without `stop`, the walk refuses after its first page
where upstream's count shows more pages from `start` than `most`; with `stop`, or where upstream
sends no count, it refuses where it has fetched `most` pages and needs another. Either way it
raises `InvalidRequestError` and returns nothing, and its message names what a caller needs to
page on purpose: `the walk needs more than the 24 pages that one call fetches: upstream counts
703 records on 29 pages of 25, and the walk reached page 1 of 29 after 1 request. It returns
nothing; pass page to fetch one page at a time.` The client tries each request up to
`RetryPolicy.max_attempts` times, 4 by default, so a call spends at most `most` times that
with its retries. `stop` takes each page's items and answers `True` for the last page that a
task wants, a page that reaches back before its `since` say, and the page it marks is kept
whole; one source uses it, the one that ADR-0034's amendment of 2026-11-24 names. `key` takes
an item and answers what tells it apart, and an item whose key an earlier item had is dropped,
as a list that changes between two requests repeats one; no source uses it yet. Both enter
with fewer than two consumers, since a maintainer's answer decided them (ADR-0059, amendment
2026-11-24). A cursor-paged task keeps its
own loop (ADR-0034, decision 2).

## Quotas, hooks and keyless calls

An upstream that reports a longer-window quota in its headers (`x-ratelimit-limit` and
`x-ratelimit-remaining`, say) gets a `QuotaPolicy`, installed on the
client's configuration:

```python
from xippios.core import AsyncClient, ClientConfig, KeyAuth, QuotaPolicy

quota = QuotaPolicy(
    limit_header="x-ratelimit-limit",  # no header is read unless the source names it
    remaining_header="x-ratelimit-remaining",
    window=3600.0,  # spent for an hour unless told otherwise
    source="example",
)
config = quota.install(
    ClientConfig(source="example", version="0.1.0", base_url="https://api.example.org")
)
client = AsyncClient(config, auth=KeyAuth("EXAMPLE_API_KEY", location="header", name="X-Api-Key"))
quota.snapshot()  # None: no response observed yet


async def get_series_async(series_id: str) -> object:
    answer = await client.get_answer("/v1/series", params={"id": series_id})
    quota.snapshot()  # QuotaSnapshot(limit=1000, remaining=999, observed_at=..., resumes_at=None)
    return answer.payload


async def list_countries_async() -> object:
    answer = await client.get_answer("/files/countries.json", auth=None)  # public: no key
    return answer.payload
```

The policy reads the quota headers of every response from the wire through
`ClientConfig.observe`. Once a 429, or a response that leaves nothing, shows the quota
spent, `ClientConfig.before_request` makes the next request wait until it is back if
that is within 30 s, the default `backoff_max`, with one warning in the log,
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

Clients that draw on one quota share one policy, as the sources that one key serves do in
one process: the code that they share for that key, its reading, its issuer's documented
answers and the one policy, stands in their publisher's shared package, which they depend on,
and never in core (ADR-0065). A `classify` that words the refusal of a 429 reads `snapshot()`,
which `observe` has updated from that answer before `classify` runs (ADR-0037, decision 1).

A request the cache answers never waits: `before_request` runs after the cache lookup,
and a cache hit carries the time its entry was stored in
`response.extensions["xippios_cache_stored_at"]`, the hit's `retrieved_at`. A wrapper
reads JSON through `get_answer()`, the one reader and the one call that stores an answer:
a 200 once its body decoded and, with `parse=`, its payload parsed, so a body that fails
is requested again on the next call. `get` and `request` read the cache and store
nothing. The `Answer` carries the
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

The cache keeps the paths its lifetimes name, by the prefix of the request's URL path,
the base URL's own path included, and the longest prefix wins:

```python
from xippios.core import MemoryCache

cache = MemoryCache(
    lifetimes={
        "/v1/regions": 86400.0,  # a day
        "/v1/files/": None,  # for the life of the process
        "/v1/files/live/": 0,  # never stored
    }
)  # any other path is never stored
```

`MemoryCache()` keeps every path for 300 s. An entry is dropped once its lifetime has
passed, and the cache holds at most 256 entries and 64 MiB of bodies in all
(`maxsize=`, `max_bytes=`), the least recently used leaving first.

The hooks are plain callables on `ClientConfig` (`before_request` may be async) for
anything else that has to see each call or each response. `before_request` runs once per
call, after the cache lookup and before the rate limiter, and may wait or raise an error of
the taxonomy, and then nothing is sent; `observe` sees every response from the wire, a
retried attempt's and a raw one's included and a cache hit's never, before `classify`
(ADR-0037).

`ClientConfig.classify` is asked before a 429 or 5xx is retried: a `RateLimitError`
with a `retry_after` beyond `backoff_max` is raised after one attempt instead of being
retried into a spent quota; an `UpstreamError` for a 5xx leaves the retries as they are;
any other error it returns, an `AuthError` say, ends them.

`auth=` on `request`, `get`, `post_json`, `get_answer`, `download` and `record`
overrides the client's credentials for one call: `None` sends none, for a keyless
endpoint on the same host, and another `httpx.Auth` replaces them. `None` and the default
share the cache; a call with an `httpx.Auth` of its own bypasses it, neither looked up nor
stored.

A write wrapper sends through `post_json`, which applies `classify`, the hooks and the
retry rule for a write as `request` does, never touches the cache, and decodes the answer,
`None` for one with no body, and a DELETE goes through `request`:

```python
draft = await client.post_json("/drafts", json={"message": {"raw": raw}})  # decoded JSON
await client.request("DELETE", f"/drafts/{draft['id']}")  # a 204, raised if an error
```

A write, a `POST`, `PUT`, `PATCH` or `DELETE`, is sent once, after a 429 or a 5xx too,
whatever the client's `RetryPolicy` says, since a repeat can apply it twice (ADR-0011). The
error of a write that met a 5xx or failed in transit says what became of it, so the caller
reads before it sends again, and the write task's docstring names that read:

```text
503 from POST /v1/things: busy. The request was sent once and its outcome is unknown.
ConnectError: [Errno 111] Connection refused. Nothing was sent.
```

A 4xx, a 429 among them, keeps upstream's words, since upstream refused the write before acting
on it. A client whose reads upstream bills takes `RetryPolicy(max_attempts=1)`, so that it
sends a read once too.

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
bearer, kept as a `SecretStr`, goes out as `Authorization: Bearer` until 60 seconds before
its `expires_in` runs out, when the next request exchanges again. An answer whose status is in `renew_on`, `{401}` by default,
makes one more exchange and sends a read again, once, while a write's refusal goes back to
its caller, the write sent once, and the next request exchanges first; a source whose upstream
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
while that response lives; `get_answer`, `post_json` and the cache keep no response.
A login and the exchange of a refresh token are the two token requests it serves (ADR-0025).

## Files: download and decode

An upstream that publishes files (a bulk dataset, a release's CSV or XLS) is read with
`download`, which streams the body to disk under a temporary name, renames it when it
is complete and removes it on a failure; it takes `params=`, `headers=` and `auth=` as `get()` does, the limiter,
the hooks, `classify` and the retries apply as for `get()`, a retry restarting the file,
and the response cache is never touched. The hooks see a
success's status and headers only, since its body goes to the file unread, and a 1xx or
a 3xx, a redirect among them, raises `UpstreamError`, since no redirect is followed:

```python
from pathlib import Path

from xippios.core import Downloaded, Result, ResultMeta
from xippios.core.client import decode_csv

BULK_TASKS = frozenset({"download_crops"})  # in tasks.py beside MCP_CAPS: Python only


async def download_crops_async(dest: Path) -> Result[Downloaded]:
    """Download the crops file of the current release.

    Args:
        dest: The file to write, e.g. ``Path("crops.csv")``.
    """
    url = "https://files.example.org/bulk/crops.csv"  # a link from the catalog
    got = await client.download(url, dest)  # another host: the client's key stays off it
    # endpoint: the file's name as upstream names it, never its kind (conventions §4)
    # a signed link's signature reads REDACTED in meta.request
    meta = ResultMeta(source="example", endpoint="crops.csv", request={"url": url})
    return Result(data=got, meta=meta)


for row in decode_csv(Path("crops.csv")):  # row by row, never whole
    print(row["COMMODITY_DESC"], row["VALUE"])  # headers as upstream prints them
```

`Downloaded` carries the path, the size, the content type, the file name from
`Content-Disposition`, the `ETag`, the `Last-Modified` text and when the file was
complete. `decode_csv` takes a downloaded file or an open text stream of comma-separated
values, a byte order mark stripped. A gzip or zip file is opened with the stdlib, and its
member read through `decode_csv` row by row:

```python
import gzip
import io

with (
    gzip.open("crops.csv.gz") as raw,
    io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text,
):
    for row in decode_csv(text):  # left open: the with closes it
        print(row["COMMODITY_DESC"])
```

Core ships no XML, spreadsheet or PDF parser. A `dest` that is a directory, or whose
directory does not exist, is refused with `InvalidRequestError` before anything is sent,
`dest is a directory; name the file to write. Nothing was sent.`, and the file is written
with mode `0600`, its owner's alone. `check_dest(dest, *, source=None)` is that check alone,
which returns `dest` as a `Path`: a task that sends a request of its own before its download,
a listing that finds the file say, calls it before that first request, so a bad `dest` sends
nothing (ADR-0045, amendment 2026-11-24):

```python
from xippios.core import check_dest


async def download_report_async(report_id: int, dest: Path) -> Result[Downloaded]:
    target = check_dest(dest, source="example")  # before the listing's request
    listing = await client.get_answer(f"/reports/{report_id}")
    got = await client.download(listing.payload["file"], target)
    meta = ResultMeta(source="example", endpoint="reports", request={"report_id": report_id})
    return Result(data=got, meta=meta)
```

`register_tasks` and
`router_from_tasks` skip a task its `tasks.py` names in `BULK_TASKS`, so no tool or route
returns a file path. A body over `ClientConfig.cache_max_bytes` (8 MiB by default) is
returned and not cached.

## Multi-tenant sources

An upstream that serves each tenant from a host or under a key of its own (an accounting
service's organisations, a mail service's mailboxes) is served by a source that declares its
tenants in the environment with `Tenants`, one client each, and names them with `list_task`
(`xippios.core.tenants`; ADR-0036, ADR-0042):

```python
from xippios.core import AsyncClient, ClientConfig, KeyAuth, Tenants, list_task

TENANTS = Tenants(
    "example",
    list_var="EXAMPLE_TENANTS",  # EXAMPLE_TENANTS=acme,acme_test
    param="org",  # every task takes org, the tenant's name
    fields=("SUBDOMAIN", "API_KEY"),  # EXAMPLE_ACME_SUBDOMAIN, EXAMPLE_ACME_API_KEY
    reserved=("demo",),  # declared by EXAMPLE_DEMO_SUBDOMAIN and _API_KEY alone
    noun="organisation",  # the word for one tenant in --org's help and a bound server's text
)


def build(name: str) -> AsyncClient:
    subdomain = TENANTS.field(name, "SUBDOMAIN")  # EXAMPLE_<NAME>_SUBDOMAIN, stripped
    config = ClientConfig(..., base_url=f"https://{subdomain}.example.org/api")
    return AsyncClient(config, auth=KeyAuth(TENANTS.var(name, "API_KEY"), location="basic"))


client = TENANTS.client_for("acme", build)  # acme's own client, built on first use
list_tenants = list_task(TENANTS, name="list_tenants")  # the tool example_list_tenants
```

The environment is read on every call. `client_for` keeps one client per tenant until
`TENANTS.reset()`, the one way to a new client, which a process calls when it changes a
tenant's variables. A name that is not declared is the caller's `InvalidRequestError`,
which lists the declared ones; a malformed list, or a missing value of a declared tenant,
is the operator's `ConfigError`, which names the variable. `field` returns a value
stripped, and a source that knows its shape checks it in `build` and raises a
`ConfigError` that names the variable, `TENANTS.var(name, "SUBDOMAIN")`, and never the
value. A source whose variables carry a prefix other than its slug names it:
`Tenants("example", var_prefix="EXAMPLE_MAIL", param="account", ...)` reads
`EXAMPLE_MAIL_ACME_REFRESH_TOKEN`, and its errors name `example`. The list task takes no
argument and returns names only, `meta.source` the registry's and `meta.tenant` `None`, on
the read server.

Every other task takes the tenant's name as the registry's `param`, `org` here, and sets
`ResultMeta(tenant=name, ...)`; its messages and results name tenants and variables, never
a value, and core's error messages leave the host out, since it names the tenant. One
tenant per call (ADR-0036, decisions 11 and 13): each task takes exactly one tenant,
required, the tenant list returns names only, nothing is shared between tenants, and
nothing in core works across them.

A server bound to one tenant serves that tenant alone, and none of its tools takes the
tenant's name. `bind_tasks(tasks, lock)` binds them to a `TenantLock(TENANTS, "acme")`,
whose parameter and noun are the registry's, and `tenant_instructions` ends the server's
instructions with a sentence that names the tenant. `main(build, tenants=TENANTS)` puts
`--org`, the registry's `param`, on the command line and builds the bound server from
`build(TenantLock(TENANTS, "acme"))` (ADR-0036; ADR-0063, decision 7). The source's
`build(lock)` returns its tool set, which core builds from the tasks module, the bound
server's text included:

```python
# xippios/example/tasks.py
MCP_INSTRUCTIONS = "Example via xippios. Every tool but example_list_tenants takes org."
MCP_BOUND_INSTRUCTIONS = "Example via xippios."  # the bound server's text: no tool takes org
```

```python
# xippios/example/mcp.py
from xippios.core import TenantLock
from xippios.core.mcp import ToolSet, build_server, main
from xippios.example import tasks
from xippios.example._client import TENANTS


def build(lock: TenantLock | None = None) -> ToolSet:
    return ToolSet.from_tasks("example", tasks, version="1.2.0", lock=lock)


server = build_server(build())  # every declared tenant


def run() -> None:  # xippios-example-mcp --org acme serves acme alone
    main(build, tenants=TENANTS, check=lambda org: TENANTS.field(org, "SUBDOMAIN"))
```

A bound tool keeps its name and its other parameters' `Annotated` constraints, and its
docstring and signature lose `org`, so a call that still names a tenant is refused like
any argument the tool does not declare; the tenant list lists the bound tenant alone.
`bind_tasks` refuses with `ValueError`, naming the task and `org`, a task that takes no
`org` and is not the tenant list, so a bound server serves the tenant's tasks and the
tenant list, and no task unbound.
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

from xippios.core import PackagedList, Result, matches

# scripts/refresh_reference.py: the records as upstream named them, the time of the fetch
records = [record.dump_upstream() for record in commodities]  # from the api/ wrapper
PackagedList(
    param="commodities", endpoint="GetCommodities", fetched=datetime.now(UTC), records=records
).write(REFERENCE / "commodities.json")  # fetched written to the second


# tasks.py
COMMODITIES = PackagedList.load("xippios.example", "commodities").codes(
    "commodityCode", "commodityName", source="example"
)  # declared once: the index of the codes is built here and kept for the process


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


def validate_commodity_code(commodity_code: str) -> str:
    return COMMODITIES.check(  # the value as given, or UnknownCode
        "commodity_code",
        commodity_code,  # "wheat": "... Did you mean 0410000 (Wheat)? Example answers ..."
        reason="Example answers unknown codes with an empty result, so the package refuses them.",
    )
```

The answer's `meta` follows ADR-0041, decision 1: `endpoint` is the upstream operation the list came
from, `retrieved_at` the time it was fetched, `vintage` an upstream release identifier
only when one is passed (a fetch date is not a vintage), `total` `None`. A file whose
`fetched` is a bare date, as refresh scripts wrote it before template v0.3.0, reads as
00:00 UTC of that day; `write` writes `fetched` to the second. A list of values is
records of one field named by the upstream parameter (`[{"state_alpha": "AK"}, ...]`).
`UnknownCode` names the value, the list and its fetch date, says that nothing was sent,
then names the closest codes (or a `hint=`), an optional `reason=`, and that the list is
out of date if upstream added the code since, which `outdated=False` leaves out for a value
that is no code at all (ADR-0041, decision 8, amended 2026-11-22; ADR-0045, amendment
2026-11-24). `closest` matches a code by its text and its name at `difflib`'s similarity of
0.6, and `nearest(value, codes)` names the integer codes nearest by number.

`PackagedList.codes(code, name=None, *, fold_case=False, list_name=None, source=None)`
declares once which field holds a list's code, which its name and whether upstream compares
it without case, and the `PackagedCodes` it returns checks an argument in one call, conventions
§5's refusal of an unknown code (ADR-0045). `check` takes one code or a list of codes, several
values of one filter, and returns the value itself, so the task sends it, and records it in
`meta.request`, as the caller gave it: under `fold_case=True` the caller's spelling, which
upstream compares without case. A list is checked in its order and refused for its first code
that the check refuses, and an empty list is refused, naming the codes the parameter takes. A
task calls `check` before any request of the call, and each refusal says `Nothing was sent.`
after its first sentence (ADR-0045, amendment 2026-11-24). A list's codes are text or integers,
as its records hold them, and a value of the other type is refused with `InvalidRequestError`,
never compared by its text: `"104"` for integer codes reads `Pass it as the integer 104.`, and
another text names the codes that the source's `closest=` strategy names for it, such as
`842 (USA)` for `"US"`, else the codes by name (ADR-0045, decision 4, amended 2026-11-22). So
a strategy of integer codes takes a text as well, and returns no pair for one it does not read.
The refusal ends with the `reason=`, as `UnknownCode` does.

```python
STATES = PackagedList.load("xippios.example", "state_alpha").codes(
    "state_alpha", fold_case=True, source="example"
)  # a list of values: each value its own name
STATES.check("state_alpha", "va")  # "va", as given: upstream compares without case
STATES.check("state_alpha", ["va", "IA"])  # several values of one filter, in one call
COUNTRIES.check(
    "country_code",
    country_code,
    hints={"all": "Omit country_code for every country."},  # in place of the closest codes
    otherwise="list_countries lists them.",  # the text when no code is close
    closest=iso_codes_first,  # the source's own strategy: (value, names) -> [(code, name)]
    reason="Example answers unknown codes with an empty result, so the package refuses them.",
)
```

A hint is read with the value stripped and without case, and before the list's type, so
`"all"` given for integer codes reads its hint. Such a value is no code, so its refusal
leaves out that the list is out of date, which the refusal with `otherwise=` keeps (ADR-0045,
decision 3, amended 2026-11-22). By default the closest codes are `closest`'s for text codes
and `nearest`'s for integer codes, and a strategy reads each name with its runs of white space
collapsed, as the refusal shows it. `list_name="element_QCL"`
names the list where its file says more than its `param`. The declaration builds its index
once and loads its file where the source makes it, so a large list is declared behind
`functools.cache`, and a record without the code or the name field, codes of both types, or
codes that differ in case alone in a folded list are refused there with `ValueError`.
`name_of(value)` gives the name of a code, compared as the check compares it, and `code`,
`list_name`, `integer` and `packaged` give the code's field, the list's name, its type and the
list, which the live comparison, `names_codes` and `NamedBy` read.

Other code lists are read with `load_json`, and a source that packages a CSV file reads
it itself (ADR-0059, decision 2). `enums.py` is generated from the packaged lists by the
reference refresh script's frame, which holds the renderer, as its section below has it
(ADR-0062, decision 13).

### The names of codes in an answer

A country argument takes upstream's own code and no second one, and every answer names the
country it stands for, since a known code can be another country than the caller meant: in a
list where `CN` is Comoros, China is `CH`. `meta.names` maps a code parameter of the request,
or a code field of the answer's records, to its codes and the names that its packaged list
holds (conventions §4, ADR-0067). A task declares the list of each code parameter with
`names_codes`, and a record's model declares the list of each code field with `NamedBy`, so
that every task that returns the model is named:

```python
from typing import Annotated

from pydantic import Field

from xippios.core import NamedBy, PackagedList, Result, UpstreamModel, names_codes, sync

REGIONS = PackagedList.load("xippios.example", "regions").codes(
    "regionCode", "regionName", source="example"
)  # R1 North, R2 South, ...


class Row(UpstreamModel):
    region_code: Annotated[str, NamedBy(REGIONS)] = Field(validation_alias="regionCode")
    item_code: Annotated[int, NamedBy("item")] = Field(validation_alias="itemCode")
    item: str  # upstream sends the item's name beside its code


@names_codes(region_code=REGIONS)
async def get_series_async(region_code: list[str] | None = None) -> Result[list[Row]]: ...


get_series = sync(get_series_async)
```

```python
>>> get_series(["R1"]).meta.names  # the request's code and the rows' under one entry
{'region_code': {'R1': 'North'}}
>>> every = get_series()  # every region: each code of the rows
>>> every.meta.names
{'region_code': {'R1': 'North', 'R2': 'South'}}
>>> every.meta.notes  # a row's code that upstream added after the list was fetched
['The packaged regions list (fetched 2026-10-23) holds no name for region_code R9 of this answer, so meta.names leaves it out.']
```

The decorator reads the call's arguments, defaults applied, once the task returned: a text is
one code, and a list, a tuple or a set holds several, since several values of one filter are a
list (ADR-0061, decision 1); a code stands once, under its text as the caller gave it, so an
integer by its digits, with the name its list holds, white space collapsed. A text of digits is
read as the integer for a list of integer codes, and an integer as its text for a list of text
codes. It wraps an `async def`, a plain function or a `sync` facade, whose async twin it wraps
too, so the MCP tool, the HTTP route and a server bound by `bind_tasks` answer with the names,
and the tool's schema, the docstring and the signature stay the task's. A name that is no
parameter of the task, a value that is no `PackagedCodes` and a parameter named twice are
refused with `TypeError` when the module is imported, and a decorated task that returns
anything but a `Result` raises `TypeError`. Names the answer carries already, its records' or
a composed answer's, are kept beside the decorator's own, and two decorators stack.

The task checks its codes before the call, with its hints and its reason, so a code the list
lacks never reaches the decorator. One that does, a code sent unchecked, is refused after the
call with the list's own refusal, `UnknownCode`, whose reason says that upstream was asked
and that the answer is withheld, without the `Nothing was sent.` of a refusal before the call
(ADR-0045, amendment 2026-11-24). The name is the one the source's own list holds for the code,
so nothing is mapped between sources (ADR-0028).

A `Result`, built or validated, names the codes of the records its data holds, in a list, a
tuple, a set or a mapping's values and in a record's fields whose annotation names a model, in
`meta.names` under the field's name. A record's code that its list lacks is no fault of the
call, since upstream returned it: the answer stands, the code is left out of the map, and one
note per field says which codes are left out. A field marked `NamedBy("item")` names its code by
the field of the same record in which upstream sends the name, so the name stands on the record
beside its code and `meta.names` takes nothing for it. A mark reads on the field and on an
optional code, `Annotated[str, NamedBy(REGIONS)] | None`. A mark that cannot name, a field
marked twice, a mark on a list's items or in a union of codes, which no answer reads, a marked
field that holds no code, text or integers, one or a list of them, or a named field that is no
other field of the model or holds no text, raises `TypeError` when an answer holds the record,
and the family check names it first. Where two models of one answer mark fields of one name
with two lists, each list's note says its own gaps and no code that the other names.

`meta.notes` holds one sentence per fact that a task says about its answer and that neither a
record nor another field states, such as the periods that a series passed over or the rule that
ended a walk of pages; it is empty by default and left out of a dump while it is empty.

## The snapshot script's frame

A source's `scripts/refresh_upstream.py`, which snapshots its upstream documentation into
`docs/upstream/` (conventions §3), declares a `Snapshot` and runs it; `xippios.core.refresh`
does the rest, sending each request through core's client (ADR-0062). sdk-template renders
this script for a new source, which fills the declaration:

```python
"""Refresh the upstream documentation snapshot in ``docs/upstream/`` (``/refresh-upstream``).

The source fills the declaration below and says here what it captures; core's frame,
``xippios.core.refresh``, fetches, checks the attribution, writes ``FETCHED.md`` and the
files, and compares with ``--check``. Run from the repository's root::

    uv run scripts/refresh_upstream.py            # fetch, then write the snapshot
    uv run scripts/refresh_upstream.py --check    # fetch and compare; write nothing
"""

from pathlib import Path

from xippios.core.refresh import NotFetched, Page, Response, Snapshot, Statement, run

ROOT = Path(__file__).resolve().parents[1]
DOCS_URL = "https://docs.example.org/api"
SPEC_URL = "https://api.example.org/openapi.json"
"""The machine-readable API document the documentation names, kept verbatim."""
TERMS_URL = "https://example.org/legal/terms"


def reduce(page: Page, response: Response) -> bytes:
    """The content a page's file is written with: the body as fetched by default.

    An HTML page becomes Markdown through the source's converter, its own dependency,
    such as markdownify in its dev group, a table with merged cells kept as HTML.
    """
    return response.body


SNAPSHOT = Snapshot(
    name="Example",
    slug="example",
    pages=(
        Page(DOCS_URL, "pages/api.md", note="converted to Markdown"),
        Page(SPEC_URL, "openapi/openapi.json", note="SPEC_URL, verbatim"),
        Page(TERMS_URL, "pages/terms.md", terms=True, note="converted to Markdown"),
        Page(f"{DOCS_URL}/v1/items?limit=2", "samples/items.json", sample=True),
        Page(f"{DOCS_URL}/admin", status=302, note="a login on another host"),
    ),
    attribution=(
        Statement("\N{COPYRIGHT SIGN} 2026 Example Ltd.", DOCS_URL, "the footer"),
        Statement("Terms of Use", TERMS_URL, "the terms page's title"),
    ),
    not_fetched=(NotFetched("https://example.org/feed.xml", "a feed, no documentation"),),
    vocabulary=(),
    capture="The API page is server-rendered HTML, converted to Markdown.",
    out=ROOT / "docs/upstream",
    reduce=reduce,
)

if __name__ == "__main__":
    raise SystemExit(run(SNAPSHOT))
```

The script carries no `# /// script` block: it runs in the project's environment, where
`xippios-core`, the source's own package and the converter of the source's dev group are
installed. `run` fetches every page before it writes one, one request at a time, `pause`
seconds apart (2 by default), each retried once after a network error or a 5xx, and once
after a 429 where the client's retry policy gives it a wait, the retry no sooner than 10 s or
the pause, whichever is longer, and follows no redirect to
another host: such a page stops the run unless it is recorded by that status, and then
`FETCHED.md` lists it under `Not fetched` with the host.

Every request goes through core's `AsyncClient` on core's loop (ADR-0062, decision 4). The
frame builds one from the slug, without credentials, which names itself as every client of
the source does, `xippios-example/<version>`, the version that of the installed distribution
`xippios-example`; a source hands its own as `Snapshot(client=...)` for its credentials, its
pace, its headers or the wait its retry policy gives a 429, which its `classify` may read from
a header of upstream's own. The client follows no redirect, so the frame follows one on the
page's host itself, up to ten, and notes each hop in the page's row: a 301, 302, 303, 307 or
308 that names a `Location`, while any other 3xx is the page's own answer. The command line takes
`--check`, and `--keyless` where the snapshot names the variables of its client's
credentials; the declaration's `out` names where the snapshot stands. The run stops, before writing,
when a page states a copyright, a licence or terms of use that `attribution` does not
record, or no longer prints one it records; `vocabulary` names words that state none.
The check reads an HTML page's visible text, an image's alternative text included where
the image stands, and searches the same text without the alternative text too, so the words
an image stands between are searched as before, and it reads any other page's text whole. A
statement recorded with a link,
`Statement("Terms of Service", DOCS_URL, "the footer", "https://example.org/tos")`, passes
only as the text of a link to that target, on any page that prints the link, so the same
words in prose, linked elsewhere or on a page that is no HTML stop the run, while a
statement without a link and the words of `vocabulary` pass wherever they stand (ADR-0062,
decision 10). An API document's `info` names a licence, terms or a contact only as a
statement recorded from the document quotes it (ADR-0062, decision 10).
`FETCHED.md` is written whole, in one form for every source: the time of the run, the
attribution, one row per file with the size and sha256 of the body as fetched, each ETag
in a code span on a row that ends in the secret scan's allowlist mark, a row for
`OBSERVED.md` where it exists, and the table `Not fetched` under its heading, empty or not,
each row on one line, a line feed in a note or a reason written as a space.
`--check` exits 1 when a file differs from what upstream serves, compared after
`canonical`, or when `FETCHED.md` would change in more than its rows' measures.

The last line of `FETCHED.md` names the file's form, `<!-- form 2 of the FETCHED.md that
xippios.core.refresh writes -->`, and every change of core that rewords what the frame writes
raises it (`FORM`), so a file that the frame wrote tells itself from a copy's (ADR-0062,
decision 8). Form 2 names the client's User-Agent, its version written `<version>`, so that a
release of the source moves no line of the file, and a source's first refresh on it rewrites
the file whole (ADR-0062, decision 6). No check reads a committed `FETCHED.md` without a request: `--check` at a refresh
is the one comparison, and each refresh writes the file whole (ADR-0062, decision 9). The
script names its declaration `SNAPSHOT` at its top level, which imports and declares alone,
sends no request and writes no file, its run under `if __name__ == "__main__":`, the form that
sdk-template renders (conventions §3).

Beside `reduce`, `canonical` and `linked`, a snapshot declares the hooks for what some
sources do beyond that, each source named in ADR-0062, and every hook stops the run with
`changed(url, what)` on a page it does not recognise:

| The source does | The declaration takes |
| --- | --- |
| sends credentials on a sample whose operation needs them | `client=` its own client with its auth, `variables=(name, ...)` and `Page(..., sample=True, keyed=True)`; `--keyless` fetches the rest |
| keeps a file as recorded where only its order moved | `reduce` returns the recorded file's content where `canonical` finds it the answer's |
| makes several files from one page | `Page(url, split=True)` and `split=lambda page, response: {name: content}` |
| keeps a page from the publisher's second origin after a 403 | two pages, `Page(url, status=403, note=...)` and `Page(second_url, file)` |
| waits out a 429 as upstream names the wait | `client=` its own client, whose `RetryPolicy` bounds the wait and whose `classify` may read it |
| writes a section of its own in `FETCHED.md` | `sections=lambda rows: [Section(heading, text)]` |
| makes a row's note from its answer | `note=lambda row: f"{row.note}; {count} operations"` |

A keyed sample alone is sent with the credentials of the snapshot's `client`, which reads
them itself, a login's included; it follows no redirect, is never retried, and the frame
prints nothing of it. It lies on the origin of the client's base URL, its scheme, host and
port, where alone the client sends its credentials (ADR-0037, decision 4), so
`https://api.example.org/v2/items` is a keyed sample of a client on
`https://api.example.org/v1` and `https://api.example.org.elsewhere.example.net/v1/items` none.
`variables` names the environment variables that the credentials are read from: `FETCHED.md`
names them and never a value, and each must be set before anything is fetched. A shared
document is cut to the source's part in `reduce` with `read_json`, which refuses a document
that `dump_json` does not write again as fetched or that holds a key twice, and `dump_json`,
both indenting by two (ADR-0062, decision 4). A `Last-Modified` stands in UTC, a date without
a zone read as GMT as HTTP has it, and one that is no HTTP date as sent, in a code span.

## The reference refresh script's frame

A source's `scripts/refresh_reference.py`, which packages its lists under `reference/` and
renders `enums.py` from them (conventions §3), declares its lists in one `Lists`, one `Listed`
per list, and hands that declaration to `run`; `xippios.core.refresh` does the rest
(ADR-0062). sdk-template renders this script for a new source, which fills the declarations:

```python
"""Refresh the packaged reference data from upstream (``/refresh-reference-data``).

The source declares its lists below, one ``Listed`` each, with the wrapper in ``api/`` that
fetches it, never a task that answers from the package; core's frame,
``xippios.core.refresh``, fetches every list before it writes one, sends each request once
and counts it, and writes ``reference/<name>.json``, the rows of ``reference/README.md`` and
``enums.py``. Run from the repository's root, with what the lists' endpoints need in the
environment::

    uv run python scripts/refresh_reference.py                     # fetch every list
    uv run python scripts/refresh_reference.py --only commodities  # one list, the rest kept
    uv run python scripts/refresh_reference.py --render-only       # no request, no key
"""

from xippios.core.refresh import Enumeration, Listed, Lists, run

from xippios.example import api
from xippios.example._client import client
from xippios.example.params import PACKAGED_LISTS


async def state_alpha() -> list[dict[str, str]]:
    """The values of ``state_alpha``, as records of one field named by the list."""
    answer = await api.get_param_values("state_alpha")
    return [{"state_alpha": value} for value in answer.payload]


LISTS = Lists(
    package="xippios.example",
    lists=(
        # A list of values, packaged as records of one field named by the list: a StrEnum.
        Listed(
            "state_alpha",
            state_alpha,
            endpoint="get_param_values",
            enum=Enumeration(),
            origin="`GET /api/get_param_values?param=state_alpha`",
        ),
        # A list of integer ids and names, packaged as upstream's records: an IntEnum.
        Listed(
            "unitsOfMeasure",
            api.get_units_of_measure,
            endpoint="GetUnitsOfMeasure",
            enum=Enumeration(ids="unitId", names="unitDescription"),
        ),
        # A table, packaged as upstream's records, with no enum.
        Listed("commodities", api.get_commodities, endpoint="GetCommodities"),
    ),
    packaged=PACKAGED_LISTS,
    client=client,
    quota_header="x-ratelimit-remaining",
)
"""The declaration: the lists, in the order of their enums in ``enums.py``."""

if __name__ == "__main__":
    raise SystemExit(run(LISTS))
```

`run(declaration, argv=None)` is the one entry of both frames: given a `Snapshot` it is the
snapshot frame's, as the section above has it, and given a `Lists` the reference frame's
(ADR-0062, decision 2). `Lists(package, lists, packaged, client, quota_header=None,
before=None, after=None)` is a frozen dataclass beside `Snapshot`: the package's import path,
whose directory the frame writes into and which must lie in the directory the script runs
in, the lists, the names of the lists the package declares it ships, the client the fetches
go through, the header of upstream's quota and the two hooks below. A script that hands `run`
anything else, the lists alone among it, is stopped before anything is read. The lists
declared must be those of `packaged`, the package's `params.PACKAGED_LISTS` in the template's
shape, or the run stops before a request and names the lists declared on one side alone; a
source that declares its lists in two parts hands both, as
`[*PACKAGED_LISTS, *PACKAGED_TABLES]`. It fetches every list before it writes one, through that
client with one attempt per request for the run, so a 5xx or a 429 spends no second call of
upstream's quota, and prints the requests it sent and the quota left in `quota_header`, a
failed run's too, a request that ended in a transport error counted as sent. A fetch answers
records, a model's by `dump_upstream` and a mapping as it is, kept under the list's `param`,
its name by default, or a finished `PackagedList`, written as built. An `api/` wrapper's
`Answer` whose `payload` is those records is read by its payload, so a wrapper that takes no
argument is a fetch as it stands, as `api.get_commodities` above is, and an `Answer` of
anything else, the body that holds the records say, stops the run before the first write. A
list of values is records of one field named by its `param`, which the fetch makes, as
`state_alpha` above does, and a fetch that answers a plain value stops the run before the
first write, naming the list and the item's position (ADR-0062, decision 11). Records, an
`Answer`'s too, are stamped `fetched` when their fetch returned; a finished list carries its
own moment, the wrapper's `retrieved_at`, its first request or the time its file was
complete, and must name the `param` and `endpoint` its `Listed` declares, where it declares
them.

Each list is written to `reference/<name>.json` by `PackagedList.write`. The provenance
table of `reference/README.md` stands under the one header that sdk-template renders,
`| File | Origin | Fetched |`, so no row counts its file's records, and a README under
another header stops a run, and a render alone, before a request (ADR-0062, decision 13).
Each list's row is rewritten where it stands, its Origin the `origin` text, the text a
function of the written list returns, or the endpoint in a code span; a row of a file no list
declares, such as one a hook writes, is kept, the template's `(none yet)` is dropped, and a
new list's row follows the others. `enums.py` is rendered by the frame, which holds the
renderer, in the order the lists are declared: a `StrEnum` of the values of the field that
its file's `param` names, keyed by the list's name, or an `IntEnum` of
`Enumeration(ids=..., names=...)`, keyed by `ids`, each with its `class_name` and
`member_names`, which a function of the values may make. It is then formatted with
`ruff format` and `ruff check --fix`, which read it from standard input under the
configuration the repository gives `enums.py`; where no list declares an enum, `enums.py` is
left alone. Every file is made, the module formatted, before the first is written, and the
files are written as one: a write that fails halfway puts back each file the run replaced and
removes each it made. So a run that fails, on a fetch, a render, ruff or a write, writes
nothing. `--only LIST [LIST ...]` fetches those lists alone and keeps every other list's
file, and `--render-only` writes the rows and `enums.py` from the packaged files alone,
without a request or a key, as an adoption does after a core release changes the renderer.

An upstream whose ids are integers gets `IntEnum` (conventions §3), so a member compares
equal to the id in upstream's data; a name several ids share gets `_<id>`:

```python
class AttributeId(IntEnum):
    """Values of ``attributeId`` (fetched 2026-10-24)."""

    AREA_HARVESTED = 4
    TOTAL_DISAPPEARANCE_126 = 126
    TOTAL_DISAPPEARANCE_173 = 173
```

Each class's docstring is one line naming the list and its fetch date, which an MCP tool's
input schema shows the agent (conventions §8). The output is plain and ASCII-only: values are
written as `ascii()` writes them, every character outside ASCII as an escape
(`'C\xf4te d\u2019Ivoire'`), one member per line, `__all__` in the order of the lists, and a
line over 100 columns carries `# noqa: E501`; ruff chooses the quotes, wraps what fits and
sorts `__all__`. A key, class name or fetch date that is not printable ASCII is refused, and
so is an empty list, a repeated id, and a value with nothing to derive a member name from (an
empty or a non-Latin label) or whose name collides; the script names that member by hand,
once, in its list's `Enumeration`:

```python
Listed(
    "short_desc",
    short_desc,
    endpoint="get_param_values",
    enum=Enumeration(member_names={"\u5317\u4eac": "BEIJING"}),
)
```

What a script writes beside its lists goes in the two hooks of `Lists`, which
`--render-only` calls neither of: `before`, called once the command line and the declaration
are checked and before the first request, for what can stop the run before it spends one,
such as the parse of a snapshot's table that a file beside the lists is rebuilt from; and
`after`, called after the last write with the lists the run fetched by name, for what a
script writes beside them, an index, test samples or a manifest. An `after` that raises
leaves the frame's files written, whole, and the run says so before the error ends it: what
the hook writes is the source's to make before it writes. The frame takes no option of a
source's own: a script that keeps one, a `--samples` say, reads it before the call and passes
the rest as `argv`.

## MCP server in five lines

```python
# xippios/example/mcp.py
from xippios.core.mcp import ToolSet, build_server, main
from xippios.example import tasks


def build() -> ToolSet:
    return ToolSet.from_tasks("example", tasks)  # __all__ minus BULK_TASKS, its MCP_CAPS


server = build_server(build())


def run() -> None:  # entry point: xippios-example-mcp = "xippios.example.mcp:run"
    main(build)
```

Tool names are `<source>_<function>` (`example_get_series`), the signature is the input
schema, and the docstring's text before `Args:` is the tool's description, under 1,000
characters, which the family check holds. Each argument's text under `Args:` describes it
in the input schema, unless the parameter's `Annotated` metadata declares a description of
its own (ADR-0063, decision 9): the description of the example's `get_series` is "Fetch
one series for a year.", and its input schema describes `series_id` and `year` by their
lines under `Args:`. Results are capped at 200 rows or
64 KB with a note on how to narrow the query, and a capped list whose `meta.request`
records an integer `start` says where to resume (`; resume with start=200`), unless not
even its first row fits, which the note then says instead. A model that holds one list of
rows keeps its other fields whole past 64 KB and has its rows cut the same way; any other
result past it is the note and a preview of its first 64 KB. Errors come
back as `error: <Class>: <message>`, arguments the tool's schema refuses too
(`error: InvalidRequestError: year: Input should be a valid integer, ... Nothing was
sent.`), before the tool runs and never with pydantic's rendered error (its URL, input type
or input value), and so does an argument the tool does not declare (`error:
InvalidRequestError: yaer: Not an argument of this tool; it takes series_id, year. Nothing
was sent.`): the tool did not run (ADR-0063, decision 6). An error answer sets `isError`
on the tool's result beside its text. A constraint that an `Annotated` parameter declares,
`Annotated[int, Field(ge=1)]` say, reaches the input schema and the check.
`--http` serves streamable HTTP instead of stdio.
A reference tool whose whole list an agent needs gets a cap of its own, keyed by the
task function's name, with the rows and bytes the source judges it needs:
`ToolSet(..., caps={"list_commodities": ResultCap(max_rows=500,
max_bytes=100_000)})`. So does a tool whose result is one upstream page that must return
whole, a cursor-paged page with its `next_token` or a bounded lookup, with a byte bound
of its own and the row bound unchanged (ADR-0038, decision 4), and so does a
tool whose result is one upstream document or table that an agent reads whole, a report
or a table's page, with the rows and bytes it needs and a note that says how to read a
part of it (ADR-0038, decision 4); every other tool keeps 200 rows or
64 KB. The note says "narrow the query to see the rest" and
promises no filter; a tool with filters names them in its cap, `ResultCap(note="filter
by year to see the rest")`. `ResultCap` comes from `xippios.core` alone, so the `MCP_CAPS`
in a source's `tasks.py` need no `mcp` extra. A write tool set (`ToolSet(...,
read_only=False)`) refuses, with `ValueError` when it is built, a task that does not take
`confirm: bool = False`, and `--http` serves its server on a loopback `--host` only
(`LOOPBACK_HOSTS`: `127.0.0.1`, `localhost`, `::1`): it carries no authentication.
`--allow-remote` serves it beyond loopback, behind a gateway that adds it. A read server
that reaches what no deployment may serve without authentication, a mailbox say, is held
the same way, its `tasks.py` declaring `MCP_LOOPBACK_ONLY = True`, which its tool set reads
as `loopback_only` (ADR-0025, D-a; ADR-0063, decision 7); the tool set's `read_only` and
`loopback_only` tell either kind, and `main` reads them from the tool set it builds the
server from. The usage line names the entry point that runs, and the refusal names the
server's kind; the help of `--allow-remote` is one sentence for every server. A source's
read and write servers are both named `xippios-<source>`.

A tool whose cut answer a caller continues takes a paged cap, `ResultCap(paged=True)`
(ADR-0047): the adapter gives it its own argument `offset: int = 0`, the rows of the answer
already shown, runs the task again without it and cuts the task's rows from there. A cut
answer of 500 rows shows 200 and its note ends with the call for the next ones, `showing 200
of 500 rows (cap: 200 rows or 65536 bytes); narrow the query to see the rest; continue with
offset=200`. The call with `offset=200` answers `showing rows 201 to 400 of 500`, the cap
and its note, and `continue with offset=400`, and the last page is its count alone,
`showing rows 401 to 500 of 500`. A page cut short by the byte bound names the right next
offset, a row that alone passes the bound is passed with `continue past it with
offset=<offset + 1>`, and an offset past the end answers no row and says so. `offset`
reaches neither the task nor `meta.request`, and every page carries its note, so an answer
without one is whole. `ResultCap(keep="last")` keeps the newest rows of a series ordered
oldest first, in the task's order, and its `offset` counts from the last row, so the
continuation walks to older rows; without `paged` it answers the newest rows and the note
alone.

```python
MCP_CAPS: Mapping[str, ResultCap] = {
    "list_regions": ResultCap(paged=True),  # a packaged table: a second run is free
    # A series of 500 periods, oldest first, whose path the client's MemoryCache keeps, so
    # that a second run is free, answers its newest 200 with the note "showing rows 301 to
    # 500 of 500 (cap: 200 rows or 65536 bytes); narrow the query to see the rest; continue
    # with offset=200", and offset=200 answers rows 101 to 300.
    "get_series": ResultCap(paged=True, keep="last"),
}
```

A continuation runs the task again, so a source pages a read tool only where that second
run costs upstream nothing (ADR-0061, decision 9): a packaged table, as `list_regions` reads
it, or an answer the response cache holds, for 300 seconds say. It leaves a tool unpaged where
a second run sends upstream a request, one request or many: a `get_series` split by year
spends a keyed call for each year of the quota its key shares, and an upstream that bills
each record it returns bills each page again. Such a series can still keep its newest rows
unpaged. The second run draws on the same quota as the
first: on a multi-tenant source the tenant's own, on a key that several packages share the
key's, and on a metered upstream the bill, so a source counts a continuation there as one
more call at that price. Rows can change between two runs, so a continuation of a live list
can repeat or skip a row. A tool set refuses a paged cap when it is built, with
`ValueError` naming the tool, for a task that takes `start`, which pages upstream itself and
keeps its `resume with start=` note, for a task that takes a parameter `offset` itself and
for every task of a write tool set, since a continuation would run a confirmed write again
(ADR-0063, decision 3); a write task may keep its last rows, `ResultCap(keep="last")` alone,
which runs it once. A tool without `paged=True` declares no `offset`, and its notes read as
before.

`tool_functions(tasks)` gives the functions of `tasks.__all__` that become tools, those in
its `BULK_TASKS` left out, read from the module it is given; it refuses an entry whose
function carries another `__name__`, since a task's name is its entry in `__all__` for its
tool name, its `MCP_CAPS` key and its `BULK_TASKS` entry alike. It and `tool_name(source,
task)`, which takes a task or its name, come from `xippios.core` without the `mcp` extra. A
task named in `BULK_TASKS` is left out of a tool set too, a wrapper whose `__wrapped__`
leads to it included, so `mcp.py` may pass every name of `tasks.__all__`; a cap named for it
is refused. Request URLs are not logged: `build_server` and `main` set the `httpx`,
`httpcore`, `httpx2` and `httpcore2` loggers to `WARNING` (`quiet_request_logging`),
because a URL can carry an API key or a tenant host; httpx2 is the `mcp` SDK's own HTTP
client.

A write tool's preview, its answer while `confirm` is false, sends no write and shows the
action as the confirmed call would send it, by upstream's names (ADR-0050). Whether it
reads first, the record an update would change say, is the write task's choice, and its
docstring says whether its preview reads and what that read costs. The preview's model
carries `reads`, the operations the preview read, each named as `meta.endpoint` names an
operation, `[]` when it read nothing, beside the tag that tells it from the confirmed
answer:

```python
class WritePreview(UpstreamModel):
    performed: Literal[False] = False  # the tag: nothing was written
    endpoint: str  # the write the confirmed call sends, "thing/update.json"
    payload: dict[str, str]  # what it would send, as upstream would receive it
    reads: list[str]  # ["thing/read.json"] for the update, [] for a create
```

A host that builds its servers itself, such as xippios-mcp, reads a source's tool set
(ADR-0063, decision 4). It takes `ToolSet`, `build_server`, `register_tasks`,
`LOOPBACK_HOSTS` and `quiet_request_logging`, after each `MCPServer` it constructs, from
`xippios.core.mcp`, and `tool_name`, `tool_functions`, `ResultCap` and `ConfigError` from
`xippios.core`. A tool set holds tools alone, so a source's tools are named
`tool_name(tool_set.source, fn)` for each `fn` of `tool_set.tasks`; a host's list of tools
is `dataclasses.replace(tool_set, tasks=..., caps=...)`, checked as a new tool set; and the
tool set's `read_only` and `loopback_only` say whether to hold its server to loopback as
`main` does (ADR-0026, decision 5).

A source's own options go through `main`'s hooks, which its `tasks.py` declares as
`mcp_add_options` and `mcp_apply_options`, so the command line is parsed once: `add_options`
puts them on core's parser, so `--help` lists them; `apply_options(namespace)` takes the
parsed options alone and returns nothing; and a `XippiosError` it raises, a missing variable
say, stops the process with exit status 2 and the message, before anything is served.

A period series whose MCP tool fetches fewer periods than its Python API declares the
server's ceiling and the option that sets another on its `Ceiling`, whose two methods are the
hooks, so core's `main` gains no option and the source keeps its option's name (ADR-0054):

```python
# tasks.py
SERIES = Ceiling(
    60,
    unit="months",
    mcp=24,  # the MCP server starts with 24
    option="--series-months",  # which sets another, 1 to 60
    help="one request per month, so 60 months take about a minute of calls",
    source="example",
)
mcp_add_options = SERIES.add_options  # the tool set's two hooks
mcp_apply_options = SERIES.apply_options
```

The entry point, and a host that applies the tool set's `option_defaults()`, set the ceiling
in force, `SERIES.value`, to 24 for the whole process, its Python and HTTP calls and every
endpoint that a host serves from one process included, and `--series-months 36` sets 36; a
value outside 1 to 60 stops the entry point with exit status 2.
Below 60 the refusal says so: `2024-08 to 2026-08 is 25 months; one call fetches at most 24
months, the ceiling set for this process (the MCP server starts with 24 by default;
--series-months raises it, up to 60). Nothing was sent. Ask for fewer months.` The option's
help is core's range and default, `most months one tool call fetches, 1 to 60 (default 24)`,
then `help`. `SERIES.set(36)` sets the ceiling from Python, and a test that sets it sets
`SERIES.most` again after it.

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
loopback (`loopback_only=True`), and its server from it. Core builds the tool set from the
tasks module, `ToolSet.from_tasks`, which reads what the module declares beside its tasks,
each where it is declared, so `mcp.py` holds no line that a source edits (ADR-0063,
decision 7):

```python
# xippios/example/tasks.py
MCP_CAPS: Mapping[str, ResultCap] = {"list_areas": ResultCap(max_rows=400)}
MCP_INSTRUCTIONS = "Example via xippios. Call example_list_areas first."
mcp_add_options = SPLIT.add_options  # main's hooks, a --split-years say
mcp_apply_options = SPLIT.apply_options
MCP_LOOPBACK_ONLY = True  # a read server held to loopback; absent, it is not
```

```python
# xippios/example/mcp.py
from xippios.core.mcp import ToolSet, build_server, main
from xippios.example import tasks
from xippios.example._version import __version__


def build() -> ToolSet:
    return ToolSet.from_tasks("example", tasks, version=__version__)


server = build_server(build())  # xippios-example, with the tool set's version and instructions


def run() -> None:
    main(build)
```

A write server's `mcp_write.py` reads `tasks_write` with `read_only=False`, and a
multi-tenant source's `build(lock=None)` passes its lock on, so the tasks are bound and the
instructions are `MCP_BOUND_INSTRUCTIONS` and the lock's sentence (see Multi-tenant sources).
A declaration of another type, `MCP_LOOPBACK_ONLY = "yes"` say, is refused with `TypeError`
naming it. `build_server` takes a tool set and `name` alone, and `register_tasks` a server
and a tool set, which was checked when it was built. A host builds one server from the tool
sets of several packages, each tool with its own package's caps, holds it to loopback where
a tool set writes or is `loopback_only`, as `main` does, and applies each package's hooks
as its entry point does when it runs without options:

```python
server = MCPServer("xippios-mcp")
quiet_request_logging()
for tools in (example_mcp.build(), other_mcp.build()):
    register_tasks(server, tools)
    if tools.apply_options is not None:
        tools.apply_options(tools.option_defaults())  # --split-years at its default
```

`option_defaults()` raises `ValueError`, naming the source, for an option of `add_options`
that has no default, where argparse would print its usage and end the host. It holds core's
options and the package's own, and not the tenant's `--<param>` that `main` adds where it is
given `tenants`, since a host binds no tenant: a hook that read it would find no such
attribute under a host. A `XippiosError` that `apply_options` raises, a missing variable say,
reaches the host, which catches it itself and stops as `main` does, with the message and exit
status 2. A hook takes no server, so what it sets is the process's, as a `Ceiling`'s value is,
and every endpoint that a host serves from one process holds a package's options at the same
values.

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
tag; `pyproject.toml` bounds `xippios-core` with `~=`; and every task, read and write, of a
source whose `_client`, `tasks` or `tasks_write` module holds a `Tenants` registry takes
exactly one tenant, the parameter its registry declares, `Tenants(..., param="org")`, once,
required, a `str`, the tenant list excepted, with no opt-in. The check reads signatures
only, so a task that takes one tenant and opens another's client is the review's to find.

It holds the package contract as a host reads it too (ADR-0063, decision 8): `mcp.build()`
returns a `ToolSet` of `_client.SOURCE`, `mcp.server` lists the tools of
`build_server(mcp.build())`, and `mcp.ENV_VARS` is `_client.ENV_VARS` itself; a source with
`tasks_write.py` has `mcp_write.py`, whose `build()` returns a tool set that writes.
`[project.scripts]` names `xippios-example-mcp = "xippios.example.mcp:run"`, or, for a
source with a write server, `xippios-example-mcp-read` at `mcp:run` and
`xippios-example-mcp-write` at `mcp_write:run`, a script of the package's own beside them.
The package re-exports every task of `tasks.__all__` and `tasks_write.__all__` from its
`__init__.py`, and every tool's description, the text of its docstring before `Args:`, is
under 1,000 characters (ADR-0063, decision 9). So a source keeps no test of its own of
these, nor of what core's adapters answer for every source, an undeclared or refused
argument, the flag of an error answer and a route's problem details, and keeps the test of
a refusal of its own (conventions §10). Its live suite is one smoke test per task, with no
probe of upstream's base URL beside them.

A write
server's tools are its source's to test, with `await assert_write_tools(mcp_write.build(),
write_tasks, read_server=read_server, router=router)`: a write tool set, its tools exactly
the write tasks, each taking `confirm: bool = False` last, and none of them on the read
server or the router. A source whose adapters drop a task, or whose README table is stale,
fails CI before a reviewer looks. The package under test is the one `tasks.py` under
`src/xippios/`.

`assert_write_tools` holds the preview of each write task too, in two parts (ADR-0050):

- Every call reads the annotations: each write task returns a `Result` whose data has
  exactly one member tagged `performed: Literal[False]`, the preview, and that member
  declares `reads: list[str]`.
- `dry_run=`, off by default, the arguments of a call of each write task keyed by the task's
  name, one mapping or a list of them, with `sent=`, the `respx` router the test's routes are
  mounted on, calls each tool of the write server without `confirm`, as an agent does. It fails a
  call unless the answer is the preview, no request but a read was sent and `reads` is empty
  exactly when no request was, and names the tool and each request by its method and path. A
  read is a `GET`, `HEAD` or `OPTIONS` request, the methods core's retry rule repeats, unless
  `is_read=`, a function of the `httpx.Request`, says otherwise, for an upstream that reads
  through `POST` or a read that sends a token request first.

A source declares `reads` on its preview from its adoption of core 0.5.0, and runs the dry run
where its tests serve what its previews read:

```python
@pytest.mark.anyio
async def test_the_write_server(
    respx_mock: respx.MockRouter, replay_fixture: ReplayFixture
) -> None:
    replay_fixture("thing_read", "ok")  # what update_thing's preview reads
    await assert_write_tools(
        mcp_write.build(),
        write_tasks,
        read_server=read_server,
        router=router,
        dry_run={
            "create_thing": {"name": "Corn"},  # reads nothing: reads == []
            "update_thing": {"thing_id": 4, "name": "Wheat"},  # reads == ["thing/read.json"]
        },
        sent=respx_mock,
    )
```

Two tests hold the names that the boundary and the ways give (ADR-0060, ADR-0061). Every read
task, of `tasks.__all__`, bulk or not, is named with one of the five read verbs, `list_`, `get_`,
`search_`, `count_` or `download_`, so `find_series` fails where `search_series` passes; a write
task of `tasks_write` takes a write's verb and is not read. In every model that a task's
`Result[T]` reaches, through its fields, a reading `<stem>_number` or `<stem>_label` stands
beside the text field of its stem: `value: str`, `"1,204 (P)"`, beside `value_number: Decimal |
None`, `1204`, passes, and `level: float` beside `level_number` or `code: int` beside
`code_label` fails. A name whose part before the suffix names no field of its model, an
address's `street_number`, is upstream's own and passes, so the check holds a reading's form,
and the review whether a reading that can lose something keeps its text. A time is read into the
type that keeps all of it, with no text and no suffix, so the check reads no time.

In every model that a task's `Result[T]` reaches, read and write, bulk or not, a field that
`NamedBy` marks holds codes and is marked once, and a field that it names as the one in which
upstream sends the name stands in the same model and holds text, so that a code and its label
stand side by side (see The names of codes in an answer; ADR-0067, decision 8). The check reads
the model's declaration and no word of a parameter's name, so whether a code is owed a name is
the review's.

A source that keeps `docs/upstream/OBSERVED.md`, its notes of what upstream does but never
documents, is held to three rules of conventions §3, one test each (ADR-0044):

- `FETCHED.md` lists the file in a row of its own: a table row whose first cell is
  `OBSERVED.md`, whose last cell says that it is written by hand and whose cells between
  are `-`, at any width.
- Every note is a `###` section whose last paragraph opens with `Probe: <date>` or
  `Observed: <date>`, an ISO date right after the label, and the file holds one note at
  least. A `##` heading groups notes, and a link reference definition at a note's end is
  dropped before its last paragraph is judged.
- Every file that a code span of the file cites exists, from the repository's root: a span
  whose text starts with `tests/`, `docs/`, `src/` or `scripts/`, holds no space and ends
  in an extension, so `docs/upstream/samples/series.json` is held and `openapi/spec.json`
  or `GET /v1/series.json` is not.

```markdown
## Series

### A year without data answers HTTP 404

The series endpoint answers a year without data with HTTP 404 and an empty body.

Probe: 2026-11-20, `GET /v1/series`; sample `tests/fixtures/get_series/empty.json`.
```

```markdown
| OBSERVED.md | - | - | written by hand: what upstream does but never documents; not fetched or checked |
```

A source without the file passes all three. The rules fail at once from core 0.4.1 on.
That no dated note of what upstream answered stands outside the file stays the source's
own test and the review's.

The nightly run compares each packaged list with the list upstream serves now, in core's
test, which `tests/test_live.py` collects with one line beside its declaration of the lists
(conventions §10, ADR-0055):

```python
# tests/test_live.py
from functools import partial

from xippios.core.testing.live import *  # noqa: F403

from xippios.example import api
from xippios.example.params import COMMODITIES, COUNTRIES, PARTNERS  # PackagedList.codes(...)

LIVE_LISTS = {  # each packaged list compared, by its file reference/<name>.json
    "commodities": (COMMODITIES, api.get_commodities),  # an Answer of UpstreamModel records
    "countries": (COUNTRIES, api.get_countries),
    "partnerAreas": (PARTNERS, partial(api.reference_rows, "partnerAreas.json")),  # mappings
}
NO_LIVE_LIST = {  # each packaged list not compared, with the reason
    "progress_stages": "Derived from a year of weekly rows: no endpoint serves the list.",
}
```

`test_packaged_list_is_current[commodities]` runs once per entry of `LIVE_LISTS`, marked
`live`, so an offline run sends nothing. An entry is the list's `PackagedCodes`
(`PackagedList.codes`, above), whose `code` is the field the records are compared by, and
the function that fetches the list now. It takes no argument and returns, or awaits, the
records under upstream's field names, mappings or `UpstreamModel` instances, or the bare
codes, text or integers, which are compared by code alone, either of them as they stand or
as the `payload` of an `api/` wrapper's `Answer`, so a wrapper is a fetch as it stands. A
mapping, or an `Answer` of anything else, the body that holds the records say, fails the test
naming its type, never read as codes of its keys. A code
gone from upstream's list,
a code new in it and a code whose record changed fail the run, in any order of the list, and
the failure names the codes, the first 20 of each kind, and never a record:

```text
packaged list countries (fetched 2026-10-23) differs from the list upstream serves now: 1 gone, 1 new, 1 changed of 3 packaged codes, 3 served; refresh it (conventions §10, ADR-0055):
- gone: 'BR'
- new: 'AR'
- changed: 'US'
```

The family check fails at once a packaged list, a `reference/<name>.json` that holds
`param`, `endpoint`, `fetched` and `records`, that stands in neither declaration, an entry
that names no packaged list, a list in both, an entry of `NO_LIVE_LIST` without its reason
and an entry of `LIVE_LISTS` that is no pair of a `PackagedCodes` declared from its file and
a function. It reads `tests/test_live.py` by its path from the root, and a source with no
packaged list and no declaration passes. A `tests/test_live.py` that does not import, or that
skips, fails or exits at its import, fails the check, which is never skipped: a live test
that needs an optional dependency or a key skips in itself or in its fixture,
`pytest.importorskip` among them, so that the module's top level, where the declarations
stand, imports offline. A source whose fetch is a fixture of its own calls
the assertion underneath in its own test, `assert_list_current(codes, current)` from
`xippios.core.testing.live`, with
`packaged=` the packaged records read as it reads the current ones where its records name
the release they came from, and gives that test as the list's reason in `NO_LIVE_LIST`.

The check of a built answer's mark is collected by a line of its own, in a file that holds
nothing else (conventions §10, ADR-0064):

```python
# tests/test_built_answers.py
from xippios.core.testing.built_answers import *  # noqa: F403
```

It reads every module under `tests/`, `tests/fixtures/` left out, and fails, naming the file
and the line, on each place that no mark covers: a `Response` that a test builds, a route's
`.respond(...)`, a body written in the test and handed to `classify`, to a model's
`model_validate` or `model_validate_json` or to a scrub, and a recording replayed with `url=`.
A mark names `§10` and its kind, `kind 1` to `kind 5`, in one docstring or block of comments,
`NOT RECORDED: an empty page (conventions §10, kind 2)`, or says that the value `is an input
of the test, not an answer from <upstream>.`, and covers the places of the function or class
whose docstring holds it, of the statement it stands on or above, and of every call of a
helper whose docstring holds it; a module's docstring covers nothing. Either mark covers any
place: the check follows no body to where it is served, so that a served answer takes a kind
is the review's (ADR-0064, decision 9). A helper that serves each recording where and as it
was recorded builds its answer with `response_from_fixture(load_fixture(path))`, which is no
place.

The census, the second test, runs after every other test of the run. The plugin compares each
request that a replay answered with the recorded one, through the recording's redaction, so
a key the recording holds `REDACTED` matches the placeholder sent, and the census fails each
test whose replay answered another host, path, query or body without `kind 3` beside `§10`.
A partial run judges only the tests that ran. A source meets the check once it adds the line,
and the module's docstring lists what it cannot see.

```python
# src/xippios/example/_client.py: each secret variable holds the placeholder key offline
ENV_VARS = (
    EnvVar("EXAMPLE_TENANTS", secret=False, required=False),
    EnvVar("EXAMPLE_<NAME>_API_KEY", secret=True, required=True),  # EXAMPLE_DEMO_API_KEY
)
TENANTS = Tenants(
    "example", list_var="EXAMPLE_TENANTS", param="org", fields=("API_KEY",), reserved=("demo",)
)
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
  sends `PLACEHOLDER_KEY` while each secret variable of `_client.ENV_VARS` holds it, a
  pattern once for each reserved tenant of the `Tenants` that `_client.py` holds (fixture
  `placeholder_api_key`), whatever the shell or an earlier live test left behind. The
  plugin reads the one package with a `_client.py` under the repository's own
  `src/xippios/`, a source or a publisher's shared package that holds a key, and a
  repository with none, a package with a `tasks.py` and no `_client.py` say, or with several
  sets no variable and raises no error. A
  fixture of the source's own that sets one of them, a reserved tenant's recorded host
  say, runs after it. Every credential that a `RenewingBearerAuth` reads is the
  placeholder too, and a variable unset or empty is still its `ConfigError`, so
  `ENV_VARS` declares each variable a token request reads secret. The `httpx`,
  `httpcore`, `httpx2` and `httpcore2` logger levels come back after every test.
  After a live run the summary prints each quota policy's last reading, `quota after the
  live run: example: 986 of 1000 requests left as of ...`. ADR-0035 states the edges of
  these guarantees.
- After a live run the summary prints, above the quota lines, the requests that its live
  tests sent, by host, `requests sent by the live run: 15 (api.example.org: 12,
  files.example.org: 3)`, so a release PR reads its count of live calls from the log of
  each run and adds up the runs. Every request that a live test hands to httpcore's pools,
  from its setup to its teardown, counts once, answered or not, each hop of a redirect and
  each attempt of a retry included; one that `respx` or a transport of the test's own
  answers was never sent and does not count. A run that built a `Tenants` registry names no
  host, `requests sent by the live run: 42 (hosts not named: tenants declared)`, since a
  tenant's host names the tenant (ADR-0030, decision 4). The line follows every run in which
  a live test was set up with the gate open, one that skips at its setup included, so a
  nightly whose live tests all skip, their key unset say, prints `requests sent by the live
  run: 0`. A run in which no live test was set up with the gate open prints no such line.
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
  so a 429 or a 5xx is recorded as it came and spends no second request. An answer of a
  1xx or a 3xx status is no final answer of its operation and is refused, nothing written,
  the message naming the status and what to record instead, the URL a redirect's
  `Location` names (ADR-0066, decision 4). It reads at
  most `max_read_bytes` of the body (32 MiB by default, `None` for no bound): past it,
  the reading stops and the recording raises, naming the method, the path and the bound,
  and nothing is written. `max_bytes=80_000`
  cuts a large answer that is a JSON array after its first whole elements, in upstream's
  own text, and the fixture is marked `truncated` with the whole body's size, sha256 and
  the array's length; `keep="last"` keeps its last elements, for a list ordered oldest
  first. A JSON object, a text that is not JSON, XML, ZIP, XLSX, gzip, XLS or a body that
  is not UTF-8 text is refused: record a small real answer or sample instead (ADR-0066,
  decision 12). It bounds the body, not the file, which escapes the body as a JSON string,
  text outside ASCII up to three times as long: 80,000 bytes keep a file under the
  256 KiB cap.
- `record` and `send_once` are sync functions, as a task's sync form is: a script or a
  test on an event loop awaits `record.async_fn(...)` or `send_once.async_fn(...)` with the
  same arguments (ADR-0066, decision 8).

`mcp_call(server, "example_get_series", {...})` calls a tool through an in-process MCP
client, so the server's middleware, the argument check included, runs as for a real client;
it returns the decoded JSON and fails the test on `error:` text. `mcp_call_text` returns
the text, an error answer's flagged `isError` included, to assert a refusal; an unknown tool
or a task that crashed fails both.

A recording names the values that must never be written:

```python
from xippios.core.testing import Scrub, fixture_path, record

record(
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


record(
    client,
    "/auth/login",
    fixture_path(FIXTURES, "auth_login", "login"),
    method="POST",
    data={"username": username, "password": password},
    auth=None,
    scrub=Scrub(secrets=[username, password], response_secrets=tokens),
)
```

Each value is replaced in its every form, not as given alone: each character as given,
percent-encoded in either hex case, a space also as `+`, or behind a JSON escape,
`\u00e9` or `\/`, in any mix and in the letter case given. A tenant named `acme corp/eu`
reads `REDACTED` in a query that sent `acme+corp%2Feu` and in a JSON body that echoes
`acme corp\/eu`, so a recording names the value once (ADR-0066, decision 11).

The fixture is scrubbed in memory, verified and written once: if a named value or one
`response_secrets` read is still in the URL, a header value or a text body, in any of its
forms, nothing is written and the error says where, never what. A body that is not UTF-8
text cannot be scrubbed and is refused unless `Scrub(allow_binary=True)` stores it base64,
flagged.

What a source replaces beyond those values, a field by key or a tenant's host, its own
rewrite step replaces, and the recorder runs it: a function of the scrubbed `Fixture` that
returns it rewritten with the values it replaced, and raises `ValueError` to refuse
(ADR-0066):

```python
import json

from xippios.core.testing import Fixture, Scrub, fixture_path, record


def rewrite(fixture: Fixture) -> tuple[Fixture, list[str]]:
    """Every user's description replaced by key; the values replaced returned."""
    body = json.loads(fixture.response.body)
    replaced = []
    for user in body.get("data", []):
        if isinstance(user.get("description"), str):
            replaced.append(user["description"])
            user["description"] = "[description rewritten]"
    response = fixture.response.model_copy(update={"body": json.dumps(body)})
    return fixture.model_copy(update={"response": response}), replaced


record(
    client,
    "/users/by",
    fixture_path(FIXTURES, "get_users_by_usernames", "two"),
    params={"usernames": "acme,example"},
    scrub=Scrub(secrets=[key]),
    rewrite=rewrite,
)
```

The order is fixed: the scrub, the step, the check, the one write. The check searches the
URL, every header value, both bodies and every key and string of a body that is JSON for
each value the step returned, as given, `REDACTED` masked first, and for the scrub's values
again; a value left anywhere refuses the write, the error naming the place (`response body`,
`request URL`, `response header 'x-echo'`), never the value. An empty value is passed over.
An encoded form of a value the step replaced is the step's to return, or to look for
itself: core searches each such value as given. `fixture_from_response(response, scrub=..., rewrite=...)` runs the same refusal,
scrub, step and check on one exchange and writes nothing, so a source that records several
exchanges checks them all before it writes one with `write_fixture(fixture, path)`, laid out
as `record` writes it; `fixture_text(fixture)` gives that text.

The step's type is `Rewrite`, which `xippios.core.testing` exports. A field of a request that
the recorder must not keep, such as a whole message sent in a write's body, the step writes as
`REDACTED` in place of its value and never drops, so that the census of built answers compares
a replay with its recording key by key (ADR-0066, decision 7).

A source that needs the answer itself, the bytes it cuts a sample from or a write's answer
it reports, sends the recording's one request with `send_once`: sent
as `record` sends it, once, never from the cache, through the source's own client, and
returned as it came, a 4xx or a 5xx included, nothing written. A 1xx or a 3xx is refused
there too. No recorder of one exchange builds a client for one attempt:

```python
from xippios.core.testing import Scrub, fixture_from_response, send_once, write_fixture

response = send_once(client, "/thing/create.json", method="POST", data=form)
print(response.json().get("insertId"))  # the record to delete after the recording
write_fixture(fixture_from_response(response, scrub=Scrub(secrets=[key])), path)
```

A task that makes several calls, a search that lists series and then reads each one, is
recorded by its source's own capture, which core does not hold (ADR-0066, decision 9): the
task's client built for one attempt, its `observe` keeping each answer, each exchange
built with `fixture_from_response`, its scrub and its step, and every one written with
`write_fixture` once all passed. The fixtures stand under the task's name, numbered from
the second, `search_series/ok.json`, then `ok_2.json` and `ok_3.json`, and
`replay_fixture("search_series", "ok_2")` replays each on its path (ADR-0066, decision 10).

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

## Counting the surface and its consumers

`scripts/count_surface.py` counts core's surface in two parts and, given the trees of its
consumers, reports who consumes each piece (https://github.com/xippios/sdk-core/issues/485).
It is a report: it fails nothing, it exits 0 on any tree it can read, and no name and no
parameter leaves core by its count alone. It reads by `ast` and imports nothing, so the
standard library runs it:

```bash
python3 -I scripts/count_surface.py                                # the surface alone
python3 -I scripts/count_surface.py example=../sdk-example host=../example-host
python3 -I scripts/count_surface.py --json example=../sdk-example  # the report as JSON
```

The surface is the six pinned lists, counted in two parts while the package stays one. The
workbench is `xippios.core.testing` and `xippios.core.refresh` with the modules under
`testing/` and `refresh/`, and the run-time part is the rest. Each part counts its names, a
name that two of its lists pin once, and the lines of its modules: one line per list, one per
part, and one for the package, which names what both parts pin.

A consumer is the tree of a source or of the host, named as `name=<path>`. Its code is of four
kinds, as the answer on https://github.com/xippios/sdk-core/issues/473 counts it: `package`
under `src/`, `scripts`, `tests`, and `commands`, the code blocks of `.claude/commands/*.md`.
A `fixtures` folder is recorded data and is not read. The report gives one line per item:

```text
name xippios.core:closest: 2 consumers: example (package; by xippios.core.models), host (package)
parameter xippios.core:closest(n=): 1 consumer: example (package)
outside xippios.core.testing.plugin: 1 consumer: example (tests)
```

A `name` line is each pinned name, with the module's path where a consumer imports its object
from outside the lists. An object that two lists pin, such as a class of `xippios.core.client`
that `xippios.core` pins too, is one: a consumer of either entry counts for both, by the other
list's path, and the second entry's line names the first, which it repeats. A `parameter` line is each keyword-only parameter of a pinned function
or constructor: a dataclass's with `kw_only=True`, a pydantic model's fields, and the keywords
that a subclass passes by `super().__init__` count too. An `outside` line is each import from
core outside the lists, a module that `pytest_plugins` names among them. A method's keywords,
such as `client.get(params=...)`, are not counted, since `ast` does not know an object's class,
nor is a keyword passed through `**options`, nor a field of a dataclass that a caller may pass
by position. The last lines tally the names and the parameters with no consumer, one, and two
or more, each object once, and count the entries that repeat one.

## Workflows

`ci.yml` runs ruff, its format check, mypy and pytest on Python 3.12, 3.13 and 3.14, then
pre-commit, secret detection among its hooks, whose ruff hooks run the version that `uv.lock`
pins, kept in step by hand, so a hook that would change a file fails. Its job `ci` passes once
the whole matrix passed and is the check that the organization's ruleset requires on `main`.
It runs on every pull request and, called by `publish.yml`, once for a release, with no push
trigger of its own, since the ruleset's up-to-date policy tests every tree before it merges.
It is handed no secret, and no variable switches it off.

`publish.yml` is the release train (conventions §12; ADR-0039, decision 6). Every push to
`main` and a dispatch start it. Its job `release-check` reads a push that changed
`pyproject.toml` or `CHANGELOG.md`, a first release's change of `CHANGELOG.md` alone included,
counts a dispatch or a push whose range it cannot read as a changed `pyproject.toml`, and lets
it through when the version that `pyproject.toml` names has no tag yet and `CHANGELOG.md` holds
its `## [X.Y.Z] - ` heading; any other push ends there quietly, with a notice where
`pyproject.toml` names a version without that heading. The run then calls `ci.yml`, tags the
merge commit `vX.Y.Z` with the version's section as the tag's message, builds the package and,
once a maintainer approves the run at the environment `pypi`, uploads it by trusted
publishing. It is one workflow, since a tag pushed with the job's token starts no other, and
PyPI's trusted publisher names its file. It is handed no secret, and each job takes the token
it needs: `release-check` reads the tags with the job's token, the job `tag` pushes the tag
with that token from the one checkout that keeps its credentials (conventions §13), and PyPI
trusts the workflow itself. No variable switches it off.

`conventions.yml` calls the organization's review of a pull request against the documents
listed under Documents below, the check `conventions / conventions`, when a pull request
opens, is pushed to, reopens or is edited, and on a push to `main` or a dispatch the review of
the range of commits, `range / range`. It hands each the two secrets of the organization that
the review reads, the model's key and a token that reads the documents, by name. A variable
`WORKFLOW_CONVENTIONS` of `off`, the repository's over the organization's, switches both off.

`adr-index.yml` calls the organization's check of the ADR index, `adr-index / adr-index`,
which runs `scripts/adr_index.py --check`, when a pull request opens, is pushed to or
reopens. It hands over nothing, and the called workflow reads its switch itself: a variable
`WORKFLOW_ADR_INDEX` of `off`, the repository's over the organization's, skips the check.

## Documents

- sdk-core: [docs/conventions.md](https://github.com/xippios/sdk-core/blob/main/docs/conventions.md) — the rules of the family, which this package implements and every `sdk-*` repository follows; a change to one comes with an ADR.
- sdk-core: [docs/definition-of-done.md](https://github.com/xippios/sdk-core/blob/main/docs/definition-of-done.md) — what a change satisfies before its pull request is opened.
- sdk-core: [docs/review-checklist.md](https://github.com/xippios/sdk-core/blob/main/docs/review-checklist.md) — the checklist every `sdk-*` pull request is reviewed against.
- sdk-core: [docs/handover.md](https://github.com/xippios/sdk-core/blob/main/docs/handover.md) — what a source's adoption of a core release does, in one part for the coming release that names no source.
- sdk-core: [docs/adr.md](https://github.com/xippios/sdk-core/blob/main/docs/adr.md) — the index of the architecture decision records under `docs/adr/`, the decisions behind the rules.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
