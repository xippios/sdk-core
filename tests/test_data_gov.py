"""xippios.core.data_gov: the api.data.gov gateway's key, answers and one shared quota.

The answers are built with ``httpx.MockTransport`` in the shape sdk-usda-psd recorded on
2026-10-23, its ``tests/fixtures/PSDData_GetCommodities/invalid_key.json`` (403
``API_KEY_INVALID``) and ``over_rate_limit.json`` (429, ``retry-after: 3151``,
``x-ratelimit-limit: 1000``, ``x-ratelimit-remaining: 0``, no reset header): the body
``{"error": {"code": ..., "message": ...}}`` and the headers. Core keeps no fixture of a
source. ``Gateway.policy`` runs on the real clock, so a wait read through it is
bracketed with ``CLOCK_SLACK``.
"""

import json
import re
from collections.abc import Callable

import httpx
import pytest

from xippios.core.client import AsyncClient, ClientConfig
from xippios.core.data_gov import API_KEY_ENV, WINDOW, Gateway, NoDataForYear
from xippios.core.errors import AuthError, NotFoundError, RateLimitError
from xippios.core.testing import CLOCK_SLACK

BASE = "https://api.fas.usda.gov"
HOST = "api.fas.usda.gov"
INVALID_KEY = {
    "error": {
        "code": "API_KEY_INVALID",
        "message": f"An invalid api_key was supplied. Get one at {BASE}:443",
    }
}
OVER_RATE_LIMIT = {
    "error": {
        "code": "OVER_RATE_LIMIT",
        "message": "You have exceeded your rate limit. Try again later or contact us for "
        f"assistance: {BASE}:443",
    }
}
RECORDED_429 = {"retry-after": "3151", "x-ratelimit-limit": "1000", "x-ratelimit-remaining": "0"}
QUOTA = {"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "999"}


def answer(
    status: int, body: object, headers: dict[str, str] | None = None, path: str = "/api/psd/x"
) -> httpx.Response:
    """An answer to ``GET <path>``; ``body=None`` is an empty body, as psd's empty 404."""
    content = b"" if body is None else json.dumps(body).encode()
    return httpx.Response(
        status, content=content, headers=headers or {}, request=httpx.Request("GET", BASE + path)
    )


class Upstream:
    """A ``MockTransport`` handler: one answer for every request, and what was sent."""

    def __init__(self, status: int, body: object, headers: dict[str, str] | None = None) -> None:
        self.status, self.body, self.headers = status, body, headers or {}
        self.sent: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(f"{request.method} {request.url.path}")
        return httpx.Response(self.status, json=self.body, headers=self.headers)


def client_for(
    gateway: Gateway, upstream: Callable[[httpx.Request], httpx.Response]
) -> AsyncClient:
    config = ClientConfig(
        source=gateway.source, version="1", base_url=BASE, classify=gateway.classify
    )
    return AsyncClient(
        gateway.install(config), auth=gateway.auth, transport=httpx.MockTransport(upstream)
    )


def test_the_gateway_wires_its_key_and_the_one_policy(placeholder_api_key: str) -> None:
    gateway = Gateway("usda-psd")
    config = gateway.install(ClientConfig(source="usda-psd", version="1", base_url=BASE))
    assert config.observe == Gateway.policy.observe
    assert config.before_request == Gateway.policy.before_request
    assert (gateway.auth.location, gateway.auth.name) == ("header", "X-Api-Key")
    assert gateway.auth.env_var == API_KEY_ENV == "DATA_GOV_API_KEY"  # pragma: allowlist secret
    assert gateway.auth.source == "usda-psd"
    assert gateway.auth.key() == placeholder_api_key
    policy = Gateway.policy
    assert (policy.limit_header, policy.remaining_header) == (
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
    )
    assert (policy.window, policy.source) == (WINDOW, "api.data.gov") == (3600.0, "api.data.gov")
    assert Gateway("usda-esr").policy is policy, "one policy per process for the key"


def test_a_refused_key_is_an_auth_error_naming_the_variable_and_the_code() -> None:
    error = Gateway("usda-psd").classify(answer(403, INVALID_KEY))
    assert isinstance(error, AuthError)
    assert error.status == 403
    assert "HTTP 403 API_KEY_INVALID: An invalid api_key was supplied" in error.message
    assert API_KEY_ENV in error.message
    assert HOST not in error.message, "host-free (ADR-0030)"
    assert error.source == "usda-psd"


@pytest.mark.anyio
async def test_a_429_waits_until_the_snapshot_says_the_quota_is_back() -> None:
    upstream = Upstream(429, OVER_RATE_LIMIT, RECORDED_429)
    client = client_for(Gateway("usda-psd"), upstream)
    with pytest.raises(RateLimitError) as info:
        await client.get_json("/api/psd/commodities")
    assert upstream.sent == ["GET /api/psd/commodities"], "3151 s is beyond backoff_max"
    snapshot = Gateway.policy.snapshot()
    assert snapshot is not None
    assert snapshot.resumes_at is not None
    assert (snapshot.resumes_at - snapshot.observed_at).total_seconds() == 3151
    slack = CLOCK_SLACK.total_seconds()
    assert info.value.retry_after is not None
    assert 3151 - slack <= info.value.retry_after <= 3151 + slack
    message = info.value.message
    assert "(HTTP 429 OVER_RATE_LIMIT: You have exceeded your rate limit." in message
    assert "1000 requests per rolling hour per key" in message
    assert f"Quota: {snapshot.describe()}." in message
    assert "expected back in" not in message, "the snapshot's time, not the seconds again"
    assert API_KEY_ENV in message
    assert HOST not in message
    assert info.value.source == "usda-psd"


@pytest.mark.anyio
async def test_a_429_without_retry_after_waits_the_window() -> None:
    client = client_for(Gateway("usda-gats"), Upstream(429, OVER_RATE_LIMIT))
    with pytest.raises(RateLimitError) as info:
        await client.get_json("/api/gats/x")
    assert info.value.retry_after is not None
    slack = CLOCK_SLACK.total_seconds()
    assert WINDOW - slack <= info.value.retry_after <= WINDOW + slack
    assert "an hourly quota per key" in info.value.message, "no limit known, none invented"


def test_a_429_classified_on_its_own_waits_what_the_policy_would_set() -> None:
    # No client observed the answer, so no snapshot holds it.
    error = Gateway("usda-psd").classify(answer(429, OVER_RATE_LIMIT, RECORDED_429))
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 3151.0
    assert "Quota:" not in error.message
    assert "The quota is expected back in 3151 s." in error.message
    assert Gateway.policy.snapshot() is None, "classify reads the policy, never writes it"


def test_the_gateway_s_not_found_is_a_not_found_error_naming_the_path() -> None:
    body = {"error": {"code": "NOT_FOUND", "message": "The requested URL was not found."}}
    error = Gateway("usda-esr").classify(answer(404, body, path="/api/esr/nowhere"))
    assert isinstance(error, NotFoundError)
    assert "api.data.gov has no route for /api/esr/nowhere (HTTP 404 NOT_FOUND" in error.message
    assert error.source == "usda-esr"


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (403, {"Message": "Access denied"}),
        (404, None),  # psd's empty 404 for a year without data stays psd's
        (500, {"Message": "An error has occurred."}),
        (200, []),
    ],
)
def test_every_other_answer_is_left_to_the_source(status: int, body: object) -> None:
    assert Gateway("usda-psd").classify(answer(status, body)) is None


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_two_sources_draw_on_one_quota() -> None:
    psd = client_for(Gateway("usda-psd"), Upstream(429, OVER_RATE_LIMIT, RECORDED_429))
    esr_upstream = Upstream(200, [], QUOTA)
    esr = client_for(Gateway("usda-esr"), esr_upstream)
    with pytest.raises(RateLimitError):
        await psd.get_json("/api/psd/commodities")
    with pytest.raises(RateLimitError, match="nothing was sent for GET /api/esr/regions") as info:
        await esr.get_json("/api/esr/regions", params={"key": "not-sent"})
    assert esr_upstream.sent == []
    assert info.value.source == "api.data.gov"
    assert info.value.message.startswith(f"api.data.gov quota of the key in {API_KEY_ENV} spent")
    assert info.value.retry_after is not None
    slack = CLOCK_SLACK.total_seconds()
    assert 3151 - slack <= info.value.retry_after <= 3151 + slack
    assert HOST not in info.value.message
    assert "not-sent" not in info.value.message


# -- FAS's empty 404 on a data path (https://github.com/xippios/sdk-core/issues/106) -------

# sdk-usda-psd's and sdk-usda-esr's data paths, as their _client.py write them.
PSD_DATA = re.compile(r"/api/psd/commodity/[^/]+/(?:country/[^/]+|world)/year/[^/]+")
ESR_DATA = re.compile(
    r"/api/esr/exports/commodityCode/[^/]+/(?:allCountries|countryCode/[^/]+)/marketYear/[^/]+"
)
YEAR_1900 = "/api/psd/commodity/0410000/country/US/year/1900"
TEXT = {"content-type": "text/plain; charset=utf-8"}


def test_an_empty_text_404_on_a_data_path_says_the_year_holds_no_data() -> None:
    # Both sources recorded it for market year 1900 on every data form.
    error = Gateway("usda-psd", data_path=PSD_DATA).classify(
        answer(404, None, TEXT, path=YEAR_1900)
    )
    assert isinstance(error, NoDataForYear)
    assert isinstance(error, NotFoundError), "in the taxonomy, conventions §5"
    assert error.path == YEAR_1900
    assert error.source == "usda-psd"
    assert error.message == (
        f"no data for {YEAR_1900} (HTTP 404 with an empty body): the year it names holds no "
        "data upstream"
    )
    assert HOST not in error.message
    path = "/api/esr/exports/commodityCode/104/allCountries/marketYear/1900"
    esr = Gateway("usda-esr", data_path=ESR_DATA)
    upper = {"Content-Type": "TEXT/PLAIN; charset=utf-8"}  # media types ignore case (RFC 9110)
    assert isinstance(esr.classify(answer(404, None, upper, path=path)), NoDataForYear)


@pytest.mark.parametrize(
    ("headers", "path", "body"),
    [
        (TEXT, "/api/psd/commodity/0410000/dataReleaseDates", None),  # off a data path
        ({"content-type": "application/json"}, YEAR_1900, None),  # not text
        ({}, YEAR_1900, None),  # no content type
        (TEXT, YEAR_1900, "no such year"),  # a body
    ],
)
def test_any_other_404_is_left_to_the_source(
    headers: dict[str, str], path: str, body: object
) -> None:
    gateway = Gateway("usda-psd", data_path=PSD_DATA)
    assert gateway.classify(answer(404, body, headers, path=path)) is None


def test_a_gateway_without_data_paths_maps_no_empty_404() -> None:
    # sdk-usda-gats: its data paths answer [], never the empty 404.
    assert Gateway("usda-gats").classify(answer(404, None, TEXT, path=YEAR_1900)) is None


def test_no_data_for_year_takes_a_message_of_the_source_s_own() -> None:
    # A task raises it again naming commodity, country and market year.
    error = NoDataForYear(YEAR_1900, "PSD has no data for wheat, US, 1900", source="usda-psd")
    assert (error.path, error.message, error.source) == (
        YEAR_1900,
        "PSD has no data for wheat, US, 1900",
        "usda-psd",
    )


# -- the gateway's own answers alone (https://github.com/xippios/sdk-core/issues/163) -----


@pytest.mark.parametrize(
    ("status", "body"), [(429, OVER_RATE_LIMIT), (403, INVALID_KEY), (404, None)]
)
def test_an_answer_from_another_origin_is_not_the_gateway_s(status: int, body: object) -> None:
    request = httpx.Request(
        "GET", "https://files.example.test" + YEAR_1900, extensions={"xippios_origin": "other"}
    )
    content = b"" if body is None else json.dumps(body).encode()
    response = httpx.Response(status, content=content, headers=TEXT, request=request)
    assert Gateway("usda-psd", data_path=PSD_DATA).classify(response) is None


@pytest.mark.anyio
@pytest.mark.rate_limited
async def test_a_429_from_another_host_spends_no_gateway_quota() -> None:
    # A keyless bulk download through the source's one client (sdk-usda-psd's plan).
    upstream = Upstream(429, OVER_RATE_LIMIT, RECORDED_429)
    client = client_for(Gateway("usda-psd"), upstream)
    with pytest.raises(RateLimitError) as info:
        await client.get_json("https://files.example.test/psd_alldata.zip")
    assert not info.value.message.startswith("api.data.gov"), "core's mapping, not the gateway's"
    assert Gateway.policy.snapshot() is None
    sent = len(upstream.sent)
    with pytest.raises(RateLimitError):
        await client.get_json("https://files.example.test/psd_alldata.zip")
    assert len(upstream.sent) > sent, "sent again: no gateway quota holds it back"


# -- a response built without a request (findings of https://github.com/xippios/sdk-core/pull/275)


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        (b'{"Message": "No HTTP resource was found"}', {"content-type": "application/json"}),
        (b"", TEXT),  # an empty text 404 whose path cannot be read
    ],
)
@pytest.mark.parametrize("data_path", [None, PSD_DATA])
def test_a_404_built_without_a_request_is_left_to_the_source(
    body: bytes, headers: dict[str, str], data_path: re.Pattern[str] | None
) -> None:
    # As on main: only the gateway's own NOT_FOUND names the path it reads.
    response = httpx.Response(404, content=body, headers=headers)
    assert Gateway("usda-psd", data_path=data_path).classify(response) is None
