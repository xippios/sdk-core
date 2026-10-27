"""QuotaPolicy: the quota snapshot and the pause before a request into a spent quota.

The behaviours are the ones sdk-usda-psd proved in its own client (``Quota``,
``observe_quota``, ``quota_pause``, ``QuotaAwareClient``; its tests/test_client.py),
on a fictitious upstream. Headers and statuses follow api.data.gov's documented answers.
A test that exercises the pause or the refusal is marked ``rate_limited``: otherwise the
plugin turns both off (ADR-0013).
"""

import dataclasses
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from xippios.core.client import (
    AsyncClient,
    ClientConfig,
    MemoryCache,
    QuotaPolicy,
    QuotaSnapshot,
    RetryPolicy,
)
from xippios.core.errors import RateLimitError
from xippios.core.mcp.errors import error_to_text

BASE = "https://api.example.test"
NOW = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)
QUOTA = {"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "999"}
SPENT = {"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "0"}
HIDDEN_KEY = "xa-hidden-key-value"  # pragma: allowlist secret


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class Sleeper:
    def __init__(self, events: list[str], clock: Clock | None = None) -> None:
        self.events = events
        self.clock = clock

    async def __call__(self, seconds: float) -> None:
        self.events.append(f"sleep {seconds:.0f}")
        if self.clock is not None:
            self.clock.now += timedelta(seconds=seconds)


class Upstream(httpx.AsyncBaseTransport):
    """Answers from a list in order and counts what was sent."""

    def __init__(self, events: list[str], *answers: httpx.Response) -> None:
        self.events = events
        self.answers = list(answers)
        self.sent = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.sent += 1
        self.events.append(f"sent {request.url.path}")
        reply = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return httpx.Response(reply.status_code, headers=reply.headers, content=reply.content)


def answer(status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    """An answer as it arrives: header values as UTF-8 bytes, which httpx decodes."""
    request = httpx.Request("GET", f"{BASE}/v1/x?key={HIDDEN_KEY}")
    raw = [(name.encode(), value.encode()) for name, value in (headers or {}).items()]
    return httpx.Response(status, headers=raw, json=[], request=request)


def make_config(**changes: object) -> ClientConfig:
    arguments: dict[str, object] = {"source": "example", "version": "1", "base_url": BASE}
    arguments.update(changes)
    return ClientConfig(**arguments)  # type: ignore[arg-type]


# -- the snapshot -------------------------------------------------------------------------


def test_quota_headers_land_in_the_snapshot() -> None:
    policy = QuotaPolicy(clock=Clock())
    assert policy.snapshot() is None
    policy.observe(answer(headers=QUOTA))
    assert policy.snapshot() == QuotaSnapshot(
        limit=1000, remaining=999, observed_at=NOW, resumes_at=None
    )
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.describe() == "999 of 1000 requests left as of 2026-10-23T08:00:00Z"


def test_the_snapshot_is_frozen() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(headers=QUOTA))
    snapshot = policy.snapshot()
    assert snapshot is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.remaining = 5  # type: ignore[misc]


def test_an_answer_without_quota_headers_leaves_the_snapshot() -> None:
    clock = Clock()
    policy = QuotaPolicy(clock=clock)
    policy.observe(answer(headers=QUOTA))
    clock.now += timedelta(minutes=5)
    policy.observe(answer(403))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.remaining, snapshot.observed_at) == (999, NOW)


def test_a_missing_limit_keeps_the_last_one() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(headers=QUOTA))
    policy.observe(answer(headers={"x-ratelimit-remaining": "998"}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (1000, 998)


def test_the_header_names_are_the_policy_s() -> None:
    policy = QuotaPolicy(
        limit_header="x-quota-limit", remaining_header="x-quota-left", clock=Clock()
    )
    policy.observe(answer(headers=QUOTA))
    assert policy.snapshot() is None
    policy.observe(answer(headers={"X-Quota-Limit": "500", "X-Quota-Left": "12"}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (500, 12)


def test_header_reading_can_be_turned_off() -> None:
    # UN Comtrade's x-ratelimit-* headers describe its per-second pace, not its daily quota.
    policy = QuotaPolicy(limit_header=None, remaining_header=None, clock=Clock())
    policy.observe(answer(headers=SPENT))
    assert policy.snapshot() is None, "a 200 leaving remaining 0 is not read"
    policy.observe(answer(429, {**QUOTA, "Retry-After": "60"}))
    assert policy.snapshot() == QuotaSnapshot(
        limit=None, remaining=0, observed_at=NOW, resumes_at=NOW + timedelta(minutes=1)
    )
    policy.reset()
    remaining_only = QuotaPolicy(limit_header=None, clock=Clock())
    remaining_only.observe(answer(headers=QUOTA))
    assert remaining_only.snapshot() == QuotaSnapshot(
        limit=None, remaining=999, observed_at=NOW, resumes_at=None
    )


def test_without_headers_spent_and_mark_spent_still_mark_the_quota() -> None:
    policy = QuotaPolicy(
        limit_header=None, remaining_header=None, spent=comtrade_spent, window=86_400.0,
        clock=Clock(),
    )  # fmt: skip
    policy.observe(quota_403("02:00:00"))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(hours=2)
    policy.reset()
    policy.mark_spent(30.0)
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(seconds=30)


@pytest.mark.parametrize("value", ["", "many", "-1", "1.5", "²", "٣", "1²", "9" * 19, "9" * 5000])
def test_a_header_that_is_no_count_is_ignored(value: str) -> None:
    # "²" and "٣" pass str.isdigit(), and int("²") raised; int() refuses 5,000 digits.
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(headers={"x-ratelimit-limit": value, "x-ratelimit-remaining": value}))
    assert policy.snapshot() is None


def test_a_count_that_is_no_number_leaves_the_snapshot() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(headers=QUOTA))
    before = policy.snapshot()
    policy.observe(answer(headers={"x-ratelimit-limit": "²", "x-ratelimit-remaining": "²"}))
    assert policy.snapshot() is before


@pytest.mark.parametrize("value", ["²", "9" * 400])
def test_a_retry_after_that_is_no_number_falls_back_to_the_window(value: str) -> None:
    policy = QuotaPolicy(window=600.0, clock=Clock())
    policy.observe(answer(429, {"Retry-After": value}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(minutes=10)


@pytest.mark.parametrize(
    "header", ["Retry-After", "x-ratelimit-reset"], ids=["retry-after", "reset"]
)
def test_a_date_that_overflows_falls_back_to_the_window(header: str) -> None:
    # parsedate_to_datetime raised OverflowError for a huge zone offset, out of observe.
    value = "Fri, 23 Oct 2026 08:00:00 +9999999999999999999999999"
    policy = QuotaPolicy(reset_header="x-ratelimit-reset", window=600.0, clock=Clock())
    policy.observe(answer(429, {header: value}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(minutes=10)


@pytest.mark.anyio
async def test_a_503_with_an_overflowing_retry_after_is_retried(
    respx_mock: respx.MockRouter,
) -> None:
    events: list[str] = []
    value = "Fri, 23 Oct 2026 08:00:00 +9999999999999999999999999"
    route = respx_mock.get(f"{BASE}/v1/x").mock(
        side_effect=[httpx.Response(503, headers={"Retry-After": value}), httpx.Response(200)]
    )
    config = make_config(retry=RetryPolicy(max_attempts=2, jitter=False))
    await AsyncClient(config, sleep=Sleeper(events)).get("/v1/x")
    assert route.call_count == 2
    assert events == ["sleep 0"]


def test_a_huge_retry_after_is_cut_to_the_window() -> None:
    policy = QuotaPolicy(window=3600.0, clock=Clock())
    policy.observe(answer(429, {"Retry-After": str(10**12)}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(hours=1)


@pytest.mark.parametrize(
    ("offset", "resumes_after"),
    [(timedelta(minutes=15), timedelta(minutes=15)), (-timedelta(minutes=1), timedelta(0))],
)
def test_an_epoch_reset_is_read_as_a_time(offset: timedelta, resumes_after: timedelta) -> None:
    # GitHub's x-ratelimit-reset is epoch seconds; read as a delay it would be 56 years.
    epoch = str(int((NOW + offset).timestamp()))
    policy = QuotaPolicy(reset_header="x-ratelimit-reset", window=3600.0, clock=Clock())
    policy.observe(answer(headers={**SPENT, "x-ratelimit-reset": epoch}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + resumes_after


def test_ten_years_of_seconds_is_still_a_delay() -> None:
    policy = QuotaPolicy(reset_header="x-ratelimit-reset", window=315_360_000.0, clock=Clock())
    policy.observe(answer(headers={**SPENT, "x-ratelimit-reset": "315360000"}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(seconds=315_360_000)


@pytest.mark.parametrize("value", [str(10**12), "9" * 400, "²", "Fri, 31 Dec 9999 23:59:59 GMT"])
def test_a_huge_or_unreadable_reset_is_cut_to_the_window(value: str) -> None:
    policy = QuotaPolicy(reset_header="x-ratelimit-reset", window=3600.0, clock=Clock())
    policy.observe(answer(headers={**SPENT, "x-ratelimit-reset": value}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(hours=1)


def test_a_429_marks_the_quota_spent_with_its_retry_after() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(headers=QUOTA))
    policy.observe(answer(429, {"Retry-After": "3151", "x-ratelimit-remaining": "0"}))
    assert policy.snapshot() == QuotaSnapshot(
        limit=1000, remaining=0, observed_at=NOW, resumes_at=NOW + timedelta(seconds=3151)
    )


def test_a_429_without_retry_after_falls_back_to_the_window() -> None:
    policy = QuotaPolicy(window=3600.0, clock=Clock())
    policy.observe(answer(429))  # no quota header at all: still spent
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (None, 0)
    assert snapshot.resumes_at == NOW + timedelta(hours=1)
    assert snapshot.describe() == (
        "0 of ? requests left as of 2026-10-23T08:00:00Z, expected back at 2026-10-23T09:00:00Z"
    )


def test_a_429_marks_the_quota_spent_whatever_remaining_says() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(429, {**QUOTA, "Retry-After": "1"}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.remaining == 0
    assert snapshot.resumes_at == NOW + timedelta(seconds=1)


def test_a_200_that_leaves_nothing_counts_the_window() -> None:
    policy = QuotaPolicy(window=600.0, clock=Clock())
    policy.observe(answer(headers=SPENT))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(minutes=10)
    policy.observe(answer(headers={**SPENT, "Retry-After": "5"}))  # read on a 429 only
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(minutes=10)


@pytest.mark.parametrize(
    ("value", "seconds"), [("120", 120), ("Fri, 23 Oct 2026 08:30:00 GMT", 1800)]
)
def test_the_reset_header_names_the_time_when_given(value: str, seconds: int) -> None:
    policy = QuotaPolicy(reset_header="x-ratelimit-reset", window=3600.0, clock=Clock())
    policy.observe(answer(headers={**SPENT, "x-ratelimit-reset": value}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(seconds=seconds)
    policy.observe(answer(429, {"Retry-After": "7", "x-ratelimit-reset": value}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == NOW + timedelta(seconds=7), "Retry-After wins on a 429"


def test_requests_left_again_clear_the_pause() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(429))
    policy.observe(answer(headers=QUOTA))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.remaining, snapshot.resumes_at) == (999, None)


def test_a_cache_hit_is_never_observed() -> None:
    policy = QuotaPolicy(clock=Clock())
    hit = answer(headers=SPENT)
    hit.extensions["xippios_cache"] = "hit"
    policy.observe(hit)
    assert policy.snapshot() is None


def test_reset_forgets_the_snapshot() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(answer(429))
    policy.reset()
    assert policy.snapshot() is None


def test_describe_names_numbers_and_times_only() -> None:
    policy = QuotaPolicy(clock=Clock())
    policy.observe(
        answer(429, {**SPENT, "Retry-After": "60", "x-api-key": HIDDEN_KEY, "x-note": "text"})
    )
    snapshot = policy.snapshot()
    assert snapshot is not None
    text = snapshot.describe()
    assert text == (
        "0 of 1000 requests left as of 2026-10-23T08:00:00Z, expected back at 2026-10-23T08:01:00Z"
    )
    assert HIDDEN_KEY not in text
    assert "api.example.test" not in text


# -- spent and mark_spent -----------------------------------------------------------------

_REPLENISHED = re.compile(r"replenished in (\d+):(\d{2}):(\d{2})")


def comtrade_spent(response: httpx.Response) -> float | None:
    """sdk-comtrade's daily quota: a 403 whose body names the time left (APIM's text)."""
    match = _REPLENISHED.search(response.text) if response.status_code == 403 else None
    if match is None:
        return None
    hours, minutes, seconds = (int(part) for part in match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def quota_403(left: str) -> httpx.Response:
    request = httpx.Request("GET", f"{BASE}/data/v1/get")
    text = f"Out of call volume quota. Quota will be replenished in {left}."
    return httpx.Response(403, text=text, request=request)


def test_spent_marks_a_documented_refusal_as_a_spent_quota() -> None:
    policy = QuotaPolicy(spent=comtrade_spent, window=86_400.0, clock=Clock())
    policy.observe(quota_403("05:04:03"))
    assert policy.snapshot() == QuotaSnapshot(
        limit=None,
        remaining=0,
        observed_at=NOW,
        resumes_at=NOW + timedelta(hours=5, minutes=4, seconds=3),
    )


def test_spent_is_asked_about_every_observed_response() -> None:
    seen: list[int] = []

    def spent(response: httpx.Response) -> float | None:
        seen.append(response.status_code)
        return None

    policy = QuotaPolicy(spent=spent, clock=Clock())
    policy.observe(answer(headers=QUOTA))
    policy.observe(answer(403))
    hit = answer(headers=QUOTA)
    hit.extensions["xippios_cache"] = "hit"
    policy.observe(hit)
    assert seen == [200, 403]  # a cache hit is not observed at all
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.remaining, snapshot.resumes_at) == (999, None), "None tells nothing"


def test_spent_wins_over_the_headers_and_is_cut_to_the_window() -> None:
    policy = QuotaPolicy(spent=lambda response: 90_000.0, window=3600.0, clock=Clock())
    policy.observe(answer(429, {**QUOTA, "Retry-After": "60"}))
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (1000, 0)
    assert snapshot.resumes_at == NOW + timedelta(hours=1)


def test_spent_returning_nan_is_a_programming_error() -> None:
    policy = QuotaPolicy(spent=lambda response: float("nan"), clock=Clock())
    with pytest.raises(ValueError, match="not NaN"):
        policy.observe(answer())


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_after_a_documented_refusal_the_next_request_is_not_sent() -> None:
    # ADR-0010 decision 4 for a source whose spent limit is not a 429 (sdk-comtrade).
    events: list[str] = []
    policy = QuotaPolicy(spent=comtrade_spent, window=86_400.0, clock=Clock(), source="example")
    upstream = Upstream(events, quota_403("20:00:00"))
    client = AsyncClient(policy.install(make_config()), transport=upstream)
    response = await client.request("GET", "/data/v1/get", raise_on_error=False)
    assert response.status_code == 403
    with pytest.raises(RateLimitError, match="nothing was sent for GET /data/v1/get") as info:
        await client.get("/data/v1/get")
    assert info.value.retry_after == 72_000.0
    assert upstream.sent == 1


def test_mark_spent_keeps_the_limit_and_cuts_the_wait() -> None:
    clock = Clock()
    policy = QuotaPolicy(window=3600.0, clock=clock)
    policy.mark_spent(120.0)
    assert policy.snapshot() == QuotaSnapshot(
        limit=None, remaining=0, observed_at=NOW, resumes_at=NOW + timedelta(minutes=2)
    )
    policy.observe(answer(headers=QUOTA))
    clock.now += timedelta(minutes=1)
    policy.mark_spent(10**12)
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (1000, 0)
    assert snapshot.resumes_at == clock.now + timedelta(hours=1)
    policy.mark_spent(-5.0)
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at == clock.now
    with pytest.raises(ValueError, match="not NaN"):
        policy.mark_spent(float("nan"))


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_mark_spent_pauses_the_next_request() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(clock=clock, sleep=Sleeper(events, clock))
    policy.mark_spent(12.0)
    await policy.before_request(httpx.Request("GET", f"{BASE}/v1/x"))
    assert events == ["sleep 12"]


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        ({"window": -1.0}, "window must be between 0 and ten years"),
        ({"window": 315_360_001.0}, "window must be between 0 and ten years"),
        ({"window": float("nan")}, "window must be between 0 and ten years"),
        ({"pause_cap": -1.0}, "pause_cap must be non-negative, not NaN"),
        ({"pause_cap": float("nan")}, "pause_cap must be non-negative, not NaN"),
    ],
)
def test_impossible_waits_are_refused(arguments: dict[str, float], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        QuotaPolicy(**arguments)  # type: ignore[arg-type]


# -- install ------------------------------------------------------------------------------


def test_install_sets_both_hooks_on_a_copy() -> None:
    config = make_config(retry=RetryPolicy(backoff_max=12.0))
    policy = QuotaPolicy()
    installed = policy.install(config)
    assert installed.before_request is not None
    assert installed.observe == policy.observe
    assert dataclasses.replace(installed, before_request=None, observe=None) == config
    assert config.before_request is None
    assert config.observe is None
    assert policy.pause_cap is None, "the cap is bound to the config, not written back"


def test_installing_the_same_policy_again_is_allowed() -> None:
    policy = QuotaPolicy()
    once = policy.install(make_config())
    assert policy.install(once) == once
    by_hand = make_config(before_request=policy.before_request, observe=policy.observe)
    assert policy.install(by_hand).observe == policy.observe


@pytest.mark.parametrize(
    ("hooks", "named"),
    [
        ({"observe": lambda response: None}, "(observe)"),
        ({"before_request": lambda request: None}, "(before_request)"),
        (
            {"before_request": lambda request: None, "observe": lambda response: None},
            "(before_request, observe)",
        ),
    ],
)
def test_install_refuses_a_config_with_hooks_of_its_own(
    hooks: dict[str, object], named: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(f"hooks of its own {named}")):
        QuotaPolicy().install(make_config(**hooks))


def test_another_policy_s_hooks_are_foreign_too() -> None:
    installed = QuotaPolicy().install(make_config())
    with pytest.raises(ValueError, match="hooks of its own"):
        QuotaPolicy().install(installed)


async def pause(config: ClientConfig) -> None:
    """Run the installed ``before_request`` hook as the client would."""
    assert config.before_request is not None
    outcome = config.before_request(httpx.Request("GET", f"{BASE}/v1/x"))
    assert outcome is not None
    await outcome


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_each_installed_config_pauses_within_its_own_backoff_max() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(window=20.0, clock=clock, sleep=Sleeper(events))
    policy.observe(answer(headers=SPENT))
    short = policy.install(make_config(retry=RetryPolicy(backoff_max=12.0)))
    patient = policy.install(make_config(retry=RetryPolicy(backoff_max=60.0)))
    with pytest.raises(RateLimitError, match=r"\(12 s\)"):
        await pause(short)
    await pause(patient)
    assert events == ["sleep 20"]
    explicit = QuotaPolicy(window=20.0, pause_cap=5.0, clock=clock)
    explicit.observe(answer(headers=SPENT))
    with pytest.raises(RateLimitError, match=r"\(5 s\)"):
        await pause(explicit.install(make_config(retry=RetryPolicy(backoff_max=60.0))))


# -- the pause, through the client --------------------------------------------------------


def quota_client(
    events: list[str], *answers: httpx.Response, window: float = 3600.0
) -> tuple[AsyncClient, QuotaPolicy, Upstream, Clock]:
    """A client with a policy on a fake clock, whose pause advances the clock."""
    clock = Clock()
    quota = QuotaPolicy(window=window, clock=clock, sleep=Sleeper(events, clock), source="example")
    upstream = Upstream(events, *answers)
    config = quota.install(make_config(retry=RetryPolicy(max_attempts=1)))
    return AsyncClient(config, transport=upstream), quota, upstream, clock


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_spent_quota_within_the_cap_is_waited_out() -> None:
    events: list[str] = []
    client, policy, upstream, _ = quota_client(
        events, answer(429, {"Retry-After": "20"}), answer(headers=QUOTA)
    )
    with pytest.raises(RateLimitError):
        await client.get("/v1/x")
    assert await client.get_json("/v1/x") == []
    assert events == ["sent /v1/x", "sleep 20", "sent /v1/x"]
    assert upstream.sent == 2
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.remaining, snapshot.resumes_at) == (999, None)


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_spent_quota_beyond_the_cap_is_refused_without_sending(
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    client, _, upstream, clock = quota_client(events, answer(headers=SPENT), window=3600.0)
    assert await client.get_json("/v1/x", params={"key": HIDDEN_KEY}) == []
    clock.now += timedelta(seconds=10)
    with pytest.raises(RateLimitError) as info:
        await client.get_json("/v1/x", params={"key": HIDDEN_KEY})
    assert upstream.sent == 1
    assert events == ["sent /v1/x"], "nothing sent, nothing slept"
    assert info.value.retry_after == 3590.0
    assert info.value.source == "example"
    message = info.value.message
    assert message == (
        "quota spent (0 of 1000 requests left as of 2026-10-23T08:00:00Z, expected back at "
        "2026-10-23T09:00:00Z); nothing was sent for GET /v1/x: the quota is expected back "
        "at 2026-10-23T09:00:00Z, later than a call waits (30 s)"
    )
    assert HIDDEN_KEY not in message
    assert "api.example.test" not in message
    assert "retry after" not in message, "core's adapters append the retry hint"
    assert error_to_text(info.value).endswith("(retry after 3590 s)")
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_the_pause_logs_one_warning_with_method_and_path_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    client, _, _, _ = quota_client(
        events, answer(headers=SPENT), answer(headers=QUOTA), window=20.0
    )
    await client.get("/v1/x", params={"key": HIDDEN_KEY})
    with caplog.at_level(logging.WARNING, logger="xippios.core.client"):
        await client.get("/v1/x", params={"key": HIDDEN_KEY})
    (record,) = caplog.records
    assert record.getMessage() == (
        "example: quota spent (0 of 1000 requests left as of 2026-10-23T08:00:00Z, expected "
        "back at 2026-10-23T08:00:20Z); waiting 20 s before GET /v1/x"
    )
    assert HIDDEN_KEY not in caplog.text
    assert "api.example.test" not in caplog.text


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_the_cap_is_the_config_s_backoff_max() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(clock=clock, sleep=Sleeper(events, clock))
    upstream = Upstream(events, answer(headers=SPENT), answer(headers=QUOTA))
    patient = policy.install(make_config(retry=RetryPolicy(max_attempts=1, backoff_max=7200.0)))
    client = AsyncClient(patient, transport=upstream)
    await client.get("/v1/x")
    await client.get("/v1/x")
    assert events == ["sent /v1/x", "sleep 3600", "sent /v1/x"]


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_cache_hit_never_waits_and_never_updates_the_snapshot() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(clock=clock, sleep=Sleeper(events, clock))
    upstream = Upstream(events, answer(headers=SPENT))
    cached = make_config(retry=RetryPolicy(max_attempts=1), cache=MemoryCache(ttl=None))
    client = AsyncClient(policy.install(cached), transport=upstream)
    first = await client.get_json("/v1/reference")
    spent = policy.snapshot()
    assert spent is not None
    assert spent.remaining == 0
    clock.now += timedelta(minutes=1)
    assert await client.get_json("/v1/reference") == first
    raw = await client.request("GET", "/v1/reference", raise_on_error=False)
    assert raw.extensions["xippios_cache"] == "hit"
    assert upstream.sent == 1
    assert events == ["sent /v1/reference"]
    assert policy.snapshot() is spent
    with pytest.raises(RateLimitError, match="nothing was sent for GET /v1/data"):
        await client.get_json("/v1/data")
    assert upstream.sent == 1


@pytest.mark.anyio
async def test_raw_answers_and_retried_attempts_update_the_snapshot() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(clock=clock, sleep=Sleeper(events, clock))
    upstream = Upstream(
        events,
        answer(429, {"Retry-After": "1", "x-ratelimit-limit": "1000"}),
        answer(500, {"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "42"}),
    )
    config = policy.install(make_config(retry=RetryPolicy(max_attempts=2, jitter=False)))
    client = AsyncClient(config, transport=upstream, sleep=Sleeper(events))
    response = await client.request("GET", "/v1/x", raise_on_error=False)
    assert response.status_code == 500
    assert events == ["sent /v1/x", "sleep 1", "sent /v1/x"]
    snapshot = policy.snapshot()
    assert snapshot is not None
    assert (snapshot.limit, snapshot.remaining) == (1000, 42)


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_recorded_style_429_is_raised_once_and_the_next_request_refused() -> None:
    # sdk-usda-psd's over_rate_limit.json: Retry-After 3151 s, beyond backoff_max.
    events: list[str] = []
    client, _, upstream, _ = quota_client(events, answer(429, {**SPENT, "Retry-After": "3151"}))
    client = AsyncClient(
        dataclasses.replace(client.config, retry=RetryPolicy()), transport=upstream
    )
    with pytest.raises(RateLimitError) as raised:
        await client.get("/v1/x")
    assert raised.value.retry_after == 3151.0
    assert upstream.sent == 1
    with pytest.raises(RateLimitError, match="nothing was sent") as refused:
        await client.get("/v2/y")
    assert refused.value.retry_after == 3151.0
    assert upstream.sent == 1


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_before_request_alone_uses_a_30_s_cap() -> None:
    events: list[str] = []
    clock = Clock()
    policy = QuotaPolicy(window=31.0, clock=clock, sleep=Sleeper(events, clock))
    policy.observe(answer(headers=SPENT))
    with pytest.raises(RateLimitError, match=r"\(30 s\)"):
        await policy.before_request(httpx.Request("GET", f"{BASE}/v1/x"))
    clock.now += timedelta(seconds=2)
    await policy.before_request(httpx.Request("GET", f"{BASE}/v1/x"))
    assert events == ["sleep 29"]
    await policy.before_request(httpx.Request("GET", f"{BASE}/v1/x"))
    assert events == ["sleep 29"], "the quota is expected back by now"
