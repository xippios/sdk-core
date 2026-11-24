"""``RenewingBearerAuth``: the exchange, its reuse, the margin, the refusal, single-flight.

ADR-0025, amendment 2026-11-18, point c; https://github.com/xippios/sdk-core/issues/156.
Every exchange is a test double behind ``httpx.MockTransport``: a token endpoint on an
origin of its own, as a provider's is, that answers a made-up bearer numbered by the exchange,
and the API on the base URL. The shell holds made-up values for the two variables the
login reads; the plugin pins the placeholder on both (ADR-0035, decision 3), so a
token request carries the placeholder and no shell value.
"""

import asyncio
import inspect
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from xippios.core import BearerToken, RenewingBearerAuth
from xippios.core.client import AsyncClient, ClientConfig, RetryPolicy
from xippios.core.client.auth import RENEWAL_MARGIN
from xippios.core.errors import (
    AuthError,
    ConfigError,
    NotFoundError,
    RateLimitError,
    TransportError,
    UpstreamError,
    ValidationError,
    XippiosError,
)
from xippios.core.testing import send_once
from xippios.core.testing.plugin import PLACEHOLDER_KEY

BASE = "https://api.example.test/v1"
TOKEN_URL = "https://login.example.test/token"
TOKEN_HOST = "login.example.test"
FILES = "https://files.example.test/bulk/data.csv"
USER = "EXAMPLE_TEST_USERNAME"
PASSWORD = "EXAMPLE_TEST_PASSWORD"  # pragma: allowlist secret
SHELL = {
    USER: "shell-user-never-sent",
    PASSWORD: "shell-password-never-sent",  # pragma: allowlist secret
}
EXPIRES_IN = 3600.0


@pytest.fixture(autouse=True)
def shell_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a shell would hold: values that an offline token request never sends."""
    for name, value in SHELL.items():
        monkeypatch.setenv(name, value)


async def no_sleep(_: float) -> None:
    return None


class Clock:
    """Monotonic seconds that a test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class LoginAuth(RenewingBearerAuth):
    """A login of two variables posted as a form, with a JSON answer."""

    def token_request(self, request: httpx.Request) -> httpx.Request:
        return httpx.Request(
            "POST",
            TOKEN_URL,
            data={"username": self.credential(USER), "password": self.credential(PASSWORD)},
        )

    def read_token(self, response: httpx.Response) -> BearerToken:
        answer = response.json()
        return BearerToken(SecretStr(answer["access_token"]), answer["expires_in"])


class Upstream:
    """The token endpoint and the API behind one transport, keeping what each received.

    The token endpoint answers ``made-up-bearer-<n>`` for its n-th exchange, after
    ``hold`` is set when one is given. The API answers ``refusals`` in turn, then 200;
    ``api`` replaces it.
    """

    def __init__(self, *, expires_in: float = EXPIRES_IN) -> None:
        self.expires_in = expires_in
        self.exchanges: list[httpx.Request] = []
        self.calls: list[httpx.Request] = []
        self.signed: list[str | None] = []
        self.refusals: list[int] = []
        self.hold: asyncio.Event | None = None
        self.token_answer: Callable[[int], httpx.Response] | None = None
        self.api: Callable[[httpx.Request], httpx.Response] | None = None

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == TOKEN_HOST:
            self.exchanges.append(request)
            count = len(self.exchanges)
            if self.hold is not None:
                await self.hold.wait()
            if self.token_answer is not None:
                return self.token_answer(count)
            return httpx.Response(
                200,
                json={"access_token": f"made-up-bearer-{count}", "expires_in": self.expires_in},
            )
        self.calls.append(request)
        self.signed.append(request.headers.get("authorization"))
        if self.api is not None:
            return self.api(request)
        if self.refusals:
            return httpx.Response(self.refusals.pop(0), text="refused")
        return httpx.Response(200, json={"ok": True})

    def bearers(self) -> list[str | None]:
        """The ``Authorization`` header of each API request as it arrived, oldest first.

        A resend is the same request object, signed again, so the header is kept on arrival.
        """
        return list(self.signed)


def make_client(
    upstream: Upstream, auth: RenewingBearerAuth | None = None, **changes: object
) -> tuple[AsyncClient, RenewingBearerAuth]:
    """A client on ``BASE`` that signs with ``auth``, a ``LoginAuth`` by default."""
    signer = LoginAuth(source="example") if auth is None else auth
    arguments: dict[str, object] = {"source": "example", "version": "1", "base_url": BASE}
    arguments.update(changes)
    config = ClientConfig(**arguments)  # type: ignore[arg-type]
    client = AsyncClient(
        config, auth=signer, transport=httpx.MockTransport(upstream), sleep=no_sleep
    )
    return client, signer


@pytest.mark.anyio
async def test_one_exchange_serves_every_request_and_sends_the_placeholder() -> None:
    upstream = Upstream()
    client, _ = make_client(upstream)
    await client.get("/data")
    await client.get("/data")
    assert len(upstream.exchanges) == 1, "one exchange while the bearer lives"
    assert upstream.bearers() == ["Bearer made-up-bearer-1"] * 2
    token = upstream.exchanges[0]
    form = parse_qs(token.content.decode())
    assert form == {"username": [PLACEHOLDER_KEY], "password": [PLACEHOLDER_KEY]}
    assert token.headers["user-agent"] == client.config.user_agent, "the request's own"
    assert "authorization" not in token.headers, "the token request carries no bearer"
    sent = [*upstream.exchanges, *upstream.calls]
    assert {request.url.host for request in sent} == {"login.example.test", "api.example.test"}
    assert not any(
        value in request.content.decode() for request in sent for value in SHELL.values()
    )
    await client.aclose()


@pytest.mark.anyio
async def test_two_concurrent_first_requests_exchange_once() -> None:
    upstream = Upstream()
    upstream.hold = asyncio.Event()
    client, _ = make_client(upstream)
    calls = [asyncio.create_task(client.get("/data")) for _ in range(3)]
    for _ in range(50):  # every call reaches the token endpoint or waits for the exchange
        await asyncio.sleep(0)
    assert len(upstream.exchanges) == 1, "the others wait for the exchange running"
    upstream.hold.set()
    await asyncio.gather(*calls)
    assert len(upstream.exchanges) == 1
    assert upstream.bearers() == ["Bearer made-up-bearer-1"] * 3
    await client.aclose()


@pytest.mark.anyio
async def test_the_bearer_is_renewed_within_the_margin_of_its_expiry() -> None:
    # The margin is the family's, 60 s: no source gave another
    # (https://github.com/xippios/sdk-core/issues/475). The attribute stays, since two
    # sources' tests read it (ADR-0059, decisions 1 and 2).
    assert RENEWAL_MARGIN == 60.0
    assert "margin" not in inspect.signature(RenewingBearerAuth).parameters
    clock = Clock()
    auth = LoginAuth(source="example", clock=clock)
    assert auth.margin == RENEWAL_MARGIN
    upstream = Upstream()
    client, _ = make_client(upstream, auth)
    await client.get("/data")
    clock.now += EXPIRES_IN - auth.margin - 1
    await client.get("/data")
    assert len(upstream.exchanges) == 1, "outside the margin the bearer is kept"
    clock.now += 1
    await client.get("/data")
    assert len(upstream.exchanges) == 2, "within the margin of its expiry it is renewed"
    assert upstream.bearers() == [
        "Bearer made-up-bearer-1",
        "Bearer made-up-bearer-1",
        "Bearer made-up-bearer-2",
    ]
    await client.aclose()


@pytest.mark.anyio
async def test_a_bearer_shorter_than_the_margin_signs_its_request_and_no_other() -> None:
    upstream = Upstream(expires_in=30.0)
    client, _ = make_client(upstream, LoginAuth(source="example", clock=Clock()))
    await client.get("/data")
    await client.get("/data")
    assert upstream.bearers() == ["Bearer made-up-bearer-1", "Bearer made-up-bearer-2"]
    await client.aclose()


@pytest.mark.anyio
async def test_a_401_exchanges_once_more_and_sends_the_request_again() -> None:
    upstream = Upstream()
    upstream.refusals = [401]
    client, _ = make_client(upstream)
    response = await client.get("/data")
    assert response.status_code == 200
    assert len(upstream.exchanges) == 2
    assert upstream.bearers() == ["Bearer made-up-bearer-1", "Bearer made-up-bearer-2"]
    await client.aclose()


@pytest.mark.anyio
async def test_a_second_401_is_the_client_s_auth_error() -> None:
    upstream = Upstream()
    upstream.refusals = [401, 401]
    client, _ = make_client(upstream)
    with pytest.raises(AuthError) as raised:
        await client.get("/data")
    assert raised.value.status == 401
    assert str(raised.value).startswith("401 from GET /v1/data: ")
    assert (len(upstream.exchanges), len(upstream.calls)) == (2, 2), "one renewal, one resend"
    await client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_a_write_refused_with_a_401_goes_out_once_and_the_next_call_renews(
    method: str,
) -> None:
    # A write is sent once (ADR-0011, amendment 2026-11-24): its refusal reaches the caller,
    # who knows the write was not applied, and the refused bearer is dropped, so that the
    # next request exchanges for a new one first.
    upstream = Upstream()
    upstream.refusals = [401]
    client, _ = make_client(upstream)
    with pytest.raises(AuthError) as raised:
        await client.request(method, "/data", json={"a": 1})
    assert raised.value.status == 401
    assert str(raised.value) == f"401 from {method} /v1/data: refused"
    assert (len(upstream.exchanges), len(upstream.calls)) == (1, 1), "one write, no resend"
    response = await client.request(method, "/data", json={"a": 1})
    assert response.status_code == 200
    assert len(upstream.exchanges) == 2, "the next call renews the bearer"
    assert upstream.bearers() == ["Bearer made-up-bearer-1", "Bearer made-up-bearer-2"]
    await client.aclose()


@pytest.mark.anyio
async def test_a_write_s_refusal_keeps_the_bearer_that_a_read_renewed_meanwhile() -> None:
    """A read and a write refused with one bearer: the read renews it, and the write, refused
    after that, drops the refused bearer alone, so the next call needs no exchange."""
    upstream = Upstream()
    written, resent = asyncio.Event(), asyncio.Event()

    def api(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] == "Bearer made-up-bearer-1":
            return httpx.Response(401, text="refused")
        resent.set()
        return httpx.Response(200, json={"ok": True})

    async def hold_the_write(request: httpx.Request) -> httpx.Response:
        if request.url.host != TOKEN_HOST:
            if request.method == "POST":
                written.set()
                await resent.wait()  # refused once the read has renewed and gone out again
            elif request.headers["authorization"] == "Bearer made-up-bearer-1":
                await written.wait()  # refused once the write went out with the same bearer
        return await upstream(request)

    upstream.api = api
    client = AsyncClient(
        ClientConfig(source="example", version="1", base_url=BASE),
        auth=LoginAuth(source="example"),
        transport=httpx.MockTransport(hold_the_write),
        sleep=no_sleep,
    )
    read, write = await asyncio.gather(
        client.get("/data"), client.request("POST", "/data", json={"a": 1}), return_exceptions=True
    )
    assert isinstance(read, httpx.Response)
    assert read.status_code == 200
    assert isinstance(write, AuthError)
    assert write.status == 401
    assert len(upstream.exchanges) == 2, "the first exchange and the read's renewal"
    await client.get("/data")
    assert len(upstream.exchanges) == 2, "the write's refusal kept the renewed bearer"
    await client.aclose()


class LoginAuthRenewingOn403(LoginAuth):
    """A source whose upstream refuses a bearer with 403 too."""

    renew_on: ClassVar[frozenset[int]] = frozenset({401, 403})


@pytest.mark.anyio
async def test_renew_on_names_the_statuses_that_renew() -> None:
    upstream = Upstream()
    upstream.refusals = [403]
    client, _ = make_client(upstream)
    with pytest.raises(AuthError) as raised:
        await client.get("/data")
    assert raised.value.status == 403, "401 alone renews by default"
    assert (len(upstream.exchanges), len(upstream.calls)) == (1, 1)
    upstream = Upstream()
    upstream.refusals = [403]
    client, _ = make_client(upstream, LoginAuthRenewingOn403(source="example"))
    response = await client.get("/data")
    assert response.status_code == 200
    assert (len(upstream.exchanges), len(upstream.calls)) == (2, 2)
    await client.aclose()


@pytest.mark.anyio
async def test_two_refusals_of_one_bearer_renew_it_once() -> None:
    """The renewal is single-flight too: the second refused call takes the renewed bearer."""
    upstream = Upstream()
    refused = asyncio.Event()

    def api(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"] == "Bearer made-up-bearer-1":
            if upstream.bearers().count("Bearer made-up-bearer-1") == 2:
                refused.set()
            return httpx.Response(401, text="refused")
        return httpx.Response(200, json={"ok": True})

    def token_answer(count: int) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": f"made-up-bearer-{count}", "expires_in": EXPIRES_IN}
        )

    async def hold_the_renewal(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL and upstream.exchanges:
            await refused.wait()  # renew once both calls were refused
        return await upstream(request)

    upstream.api = api
    upstream.token_answer = token_answer
    client = AsyncClient(
        ClientConfig(source="example", version="1", base_url=BASE),
        auth=LoginAuth(source="example"),
        transport=httpx.MockTransport(hold_the_renewal),
        sleep=no_sleep,
    )
    first, second = await asyncio.gather(client.get("/data"), client.get("/data"))
    assert (first.status_code, second.status_code) == (200, 200)
    assert len(upstream.exchanges) == 2, "the first exchange and one renewal"
    assert sorted(bearer or "" for bearer in upstream.bearers()) == [
        "Bearer made-up-bearer-1",
        "Bearer made-up-bearer-1",
        "Bearer made-up-bearer-2",
        "Bearer made-up-bearer-2",
    ]
    await client.aclose()


@pytest.mark.anyio
async def test_the_bearer_goes_to_the_base_url_s_origin_only(tmp_path: Path) -> None:
    upstream = Upstream()
    client, _ = make_client(upstream)
    await client.get(FILES)
    await client.download(FILES, tmp_path / "data.csv")
    await client.get("/public", auth=None)
    assert upstream.exchanges == [], "no exchange for a request that carries no bearer"
    assert upstream.bearers() == [None, None, None]
    await client.aclose()


class Chunks(httpx.AsyncByteStream):
    """A body sent in 1 KiB chunks, counting the chunks read."""

    def __init__(self, count: int) -> None:
        self.count = count
        self.read = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self.count):
            self.read += 1
            yield b"x" * 1024


@pytest.mark.anyio
async def test_a_download_through_the_bearer_streams_its_body_to_the_file(
    tmp_path: Path,
) -> None:
    """``observe`` sees the success before a chunk of it is read: the flow buffers nothing."""
    upstream = Upstream()
    body = Chunks(4)
    upstream.api = lambda request: httpx.Response(200, stream=body)
    unread_at_observe: list[int] = []
    client, _ = make_client(upstream, observe=lambda response: unread_at_observe.append(body.read))
    got = await client.download("/files/data.csv", tmp_path / "data.csv")
    assert unread_at_observe == [0]
    assert got.bytes == 4096
    assert (tmp_path / "data.csv").read_bytes() == b"x" * 4096
    assert upstream.bearers() == ["Bearer made-up-bearer-1"]
    assert len(upstream.exchanges) == 1
    await client.aclose()


class Unread(httpx.AsyncByteStream):
    """A body that is read only when someone iterates it; ``read`` says whether one did."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.read = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        self.read = True
        yield self.body


@pytest.mark.anyio
async def test_the_flow_reads_the_token_answer_and_hands_the_signed_answer_back_unread() -> None:
    flow = LoginAuth(source="example").async_auth_flow(
        httpx.Request("GET", f"{BASE}/data", headers={"User-Agent": "test"})
    )
    token_request = await anext(flow)
    assert str(token_request.url) == TOKEN_URL
    assert token_request.headers["user-agent"] == "test"
    token_body = Unread(b'{"access_token": "made-up-bearer-1", "expires_in": 3600}')
    signed = await flow.asend(httpx.Response(200, stream=token_body, request=token_request))
    assert token_body.read, "the token answer is read"
    assert signed.headers["authorization"] == "Bearer made-up-bearer-1"
    data_body = Unread(b'{"ok": true}')
    answer = httpx.Response(200, stream=data_body, request=signed)
    with pytest.raises(StopAsyncIteration):
        await flow.asend(answer)
    assert not data_body.read, "the signed request's answer goes back unread"


@pytest.mark.anyio
async def test_the_token_answer_stays_in_the_response_s_history() -> None:
    upstream = Upstream()
    client, _ = make_client(upstream)
    response = await client.get("/data")
    assert [str(earlier.request.url) for earlier in response.history] == [TOKEN_URL]
    await client.aclose()


def assert_statuses_alone(history: list[httpx.Response]) -> None:
    """Each earlier answer is its status alone: no body, no header and no request, so neither
    a bearer nor a credential of the token request stays with the answer."""
    for earlier in history:
        assert earlier.content == b""
        assert not earlier.headers
        with pytest.raises(RuntimeError):
            earlier.request  # noqa: B018 - httpx raises for an answer without its request


@pytest.mark.anyio
async def test_the_one_send_keeps_the_history_as_statuses_alone() -> None:
    """https://github.com/xippios/sdk-core/issues/579: the recorder's one send rebuilds its
    answer, and keeps the answers before it, the two token answers and the refused one, as
    their statuses, so the refresh frames count each request the call sent, and nothing else
    of them; ``observe`` sees that answer."""
    upstream = Upstream()
    upstream.refusals = [401]
    seen: list[httpx.Response] = []
    client, _ = make_client(upstream, observe=seen.append)
    response = await send_once.async_fn(client, "/data")
    assert response.status_code == 200
    assert [earlier.status_code for earlier in response.history] == [200, 401, 200]
    assert_statuses_alone(response.history)
    assert seen == [response]
    await client.aclose()


@pytest.mark.anyio
async def test_a_download_s_refusal_keeps_the_history_as_statuses_alone(tmp_path: Path) -> None:
    """https://github.com/xippios/sdk-core/issues/579: a download's refusal is rebuilt from
    its first bytes, and ``observe`` sees it with the token answer before it, as its status
    alone, so a refresh frame that downloads counts the login too."""
    upstream = Upstream()
    upstream.api = lambda request: httpx.Response(404, text="gone")
    seen: list[httpx.Response] = []
    client, _ = make_client(upstream, observe=seen.append)
    with pytest.raises(NotFoundError):
        await client.download("/files/data.csv", tmp_path / "data.csv")
    (refusal,) = seen
    assert refusal.status_code == 404
    assert [earlier.status_code for earlier in refusal.history] == [200]
    assert_statuses_alone(refusal.history)
    await client.aclose()


ECHOED = "an-echoed-value-never-shown"
"""What a token endpoint's error answer might repeat of the request: never quoted."""


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error", "text"),
    [
        (400, UpstreamError, "400 from POST /token: Bad Request"),
        (401, AuthError, "401 from POST /token: Unauthorized"),
        (403, AuthError, "403 from POST /token: Forbidden"),
        (404, NotFoundError, "404 from POST /token: Not Found"),
        (429, RateLimitError, "429 from POST /token: Too Many Requests"),
        (503, UpstreamError, "503 from POST /token: Service Unavailable"),
        (599, UpstreamError, "599 from POST /token: no reason phrase"),
        (
            204,
            UpstreamError,
            "POST /token answered HTTP 204, not the documented 200; nothing of it is shown",
        ),
    ],
    ids=["400", "401", "403", "404", "429", "503", "599", "204"],
)
async def test_a_refused_exchange_is_mapped_by_its_status_and_quotes_nothing(
    status: int, error: type[XippiosError], text: str
) -> None:
    """The taxonomy error of the status, its reason phrase in place of the answer."""
    upstream = Upstream()
    upstream.token_answer = lambda _: httpx.Response(
        status,
        json={"error": "invalid_grant", "error_description": ECHOED},
        headers={"Retry-After": "7"},
    )
    client, _ = make_client(upstream)
    with pytest.raises(error) as raised:
        await client.get("/data")
    assert str(raised.value) == text
    assert ECHOED not in repr(vars(raised.value))
    assert raised.value.source == "example"
    assert (len(upstream.exchanges), len(upstream.calls)) == (1, 0), "never retried"
    if isinstance(raised.value, UpstreamError):
        assert (raised.value.status, raised.value.body) == (status, "")
    if isinstance(raised.value, RateLimitError):
        assert raised.value.retry_after == 7
    await client.aclose()


class TenantLoginAuth(LoginAuth):
    """A token request with a query and a ``User-Agent`` of its own."""

    def token_request(self, request: httpx.Request) -> httpx.Request:
        login = super().token_request(request)
        return httpx.Request(
            "POST",
            f"{TOKEN_URL}?tenant=never-named",
            content=login.content,
            headers={**login.headers, "User-Agent": "its-own-agent"},
        )


@pytest.mark.anyio
async def test_a_refused_exchange_names_the_method_and_path_alone() -> None:
    """``request_description``'s words: no host, no query (conventions §5)."""
    upstream = Upstream()
    upstream.token_answer = lambda _: httpx.Response(503, text="busy")
    client, _ = make_client(upstream, TenantLoginAuth(source="example"))
    with pytest.raises(UpstreamError) as raised:
        await client.get("/data")
    assert str(raised.value) == "503 from POST /token: Service Unavailable"
    await client.aclose()


@pytest.mark.anyio
async def test_a_token_request_keeps_a_user_agent_of_its_own() -> None:
    upstream = Upstream()
    client, _ = make_client(upstream, TenantLoginAuth(source="example"))
    await client.get("/data")
    assert upstream.exchanges[0].headers["user-agent"] == "its-own-agent"
    await client.aclose()


@pytest.mark.anyio
async def test_a_transport_failure_of_the_exchange_is_retried_with_its_request() -> None:
    """The client's retry policy (ADR-0011) sends a GET again, its exchange included."""
    upstream = Upstream()
    failures = [httpx.ConnectError("connection refused")]

    async def failing_once(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL and failures:
            raise failures.pop()
        return await upstream(request)

    auth = LoginAuth(source="example")
    client = AsyncClient(
        ClientConfig(
            source="example",
            version="1",
            base_url=BASE,
            retry=RetryPolicy(max_attempts=2, jitter=False),
        ),
        auth=auth,
        transport=httpx.MockTransport(failing_once),
        sleep=no_sleep,
    )
    response = await client.get("/data")
    assert response.status_code == 200
    assert upstream.bearers() == ["Bearer made-up-bearer-1"]
    auth.reset()
    failures.append(httpx.ConnectError("connection refused"))
    with pytest.raises(TransportError):
        await client.request("POST", "/data", json={"a": 1})
    assert len(upstream.calls) == 1, "a POST is not sent again, so neither is its exchange"
    await client.aclose()


class RefreshAuth(LoginAuth):
    """A refresh whose revoked grant names the consent to run again."""

    def token_refused(self, response: httpx.Response) -> XippiosError:
        if response.status_code == 400 and response.json().get("error") == "invalid_grant":
            return AuthError(
                "account demo: refresh token revoked or expired; re-run example-auth "
                "--account demo --scopes read",
                status=400,
                source=self.source,
            )
        return super().token_refused(response)


@pytest.mark.anyio
async def test_token_refused_is_the_source_s_to_write() -> None:
    upstream = Upstream()
    upstream.token_answer = lambda _: httpx.Response(400, json={"error": "invalid_grant"})
    client, _ = make_client(upstream, RefreshAuth(source="example"))
    with pytest.raises(AuthError) as raised:
        await client.get("/data")
    assert str(raised.value).endswith("re-run example-auth --account demo --scopes read")
    assert (len(upstream.exchanges), len(upstream.calls)) == (1, 0)
    upstream.token_answer = lambda _: httpx.Response(503, text=ECHOED)
    with pytest.raises(UpstreamError) as other:
        await client.get("/data")
    assert str(other.value) == "503 from POST /token: Service Unavailable", "the default's"
    await client.aclose()


class ShapelessAuth(LoginAuth):
    """A ``read_token`` that refuses an answer, quoting none of it."""

    def read_token(self, response: httpx.Response) -> BearerToken:
        raise ValidationError(
            "POST /token answered HTTP 200, but not the documented answer", raw="", source="example"
        )


@pytest.mark.anyio
async def test_an_error_of_read_token_ends_the_call() -> None:
    upstream = Upstream()
    client, _ = make_client(upstream, ShapelessAuth(source="example"))
    with pytest.raises(ValidationError, match="not the documented answer"):
        await client.get("/data")
    assert (len(upstream.exchanges), len(upstream.calls)) == (1, 0)
    await client.aclose()


@pytest.mark.anyio
@pytest.mark.parametrize("name", [USER, PASSWORD])
@pytest.mark.parametrize("unset", ["deleted", "empty"])
async def test_an_unset_credential_is_a_config_error_and_nothing_is_sent(
    monkeypatch: pytest.MonkeyPatch, name: str, unset: str
) -> None:
    if unset == "deleted":
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, "")
    upstream = Upstream()
    client, _ = make_client(upstream)
    with pytest.raises(ConfigError) as raised:
        await client.get("/data")
    assert str(raised.value) == f"{name} is not set; export it or pass it in credentials="
    assert raised.value.source == "example"
    assert (upstream.exchanges, upstream.calls) == ([], [])
    await client.aclose()


class AccountLoginAuth(LoginAuth):
    """A source that says what its unset variables need."""

    def credential_help(self, name: str) -> str:
        return f"the example account needs {USER} and {PASSWORD}"


@pytest.mark.anyio
async def test_credential_help_says_what_an_unset_credential_needs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(PASSWORD)
    upstream = Upstream()
    client, _ = make_client(upstream, AccountLoginAuth(source="example"))
    with pytest.raises(ConfigError) as raised:
        await client.get("/data")
    assert str(raised.value) == (
        f"{PASSWORD} is not set; the example account needs {USER} and {PASSWORD}"
    )
    await client.aclose()


class TestCredentialResolution:
    """How a credential is read where the plugin's pin is lifted, as in a live run."""

    @pytest.fixture
    def placeholder_api_key(self) -> None:
        """These tests read the variables: the plugin's pins stay off."""

    @pytest.mark.anyio
    async def test_each_exchange_reads_the_variables_anew(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        upstream = Upstream()
        client, auth = make_client(upstream)
        await client.get("/data")
        monkeypatch.setenv(USER, "changed-user")
        auth.reset()
        await client.get("/data")
        users = [parse_qs(request.content.decode())["username"] for request in upstream.exchanges]
        assert users == [[SHELL[USER]], ["changed-user"]]
        await client.aclose()

    @pytest.mark.anyio
    async def test_a_given_credential_wins_over_the_variable_and_is_kept_masked(self) -> None:
        upstream = Upstream()
        auth = LoginAuth(source="example", credentials={USER: "given-user"})
        client, _ = make_client(upstream, auth)
        await client.get("/data")
        form = parse_qs(upstream.exchanges[0].content.decode())
        assert form == {"username": ["given-user"], "password": [SHELL[PASSWORD]]}
        assert "given-user" not in repr(vars(auth))
        await client.aclose()


@pytest.mark.anyio
async def test_the_bearer_is_kept_masked() -> None:
    upstream = Upstream()
    client, auth = make_client(upstream)
    await client.get("/data")
    assert "made-up-bearer-1" not in repr(vars(auth))
    await client.aclose()


@pytest.mark.anyio
async def test_reset_forgets_the_bearer() -> None:
    upstream = Upstream()
    client, auth = make_client(upstream)
    await client.get("/data")
    auth.reset()
    await client.get("/data")
    assert upstream.bearers() == ["Bearer made-up-bearer-1", "Bearer made-up-bearer-2"]
    await client.aclose()


def test_the_sync_flow_is_not_served() -> None:
    with pytest.raises(NotImplementedError, match="async client only"):
        next(LoginAuth(source="example").sync_auth_flow(httpx.Request("GET", BASE)))


def test_the_base_leaves_the_token_request_and_its_reading_to_the_source() -> None:
    base = RenewingBearerAuth(source="example")
    with pytest.raises(NotImplementedError, match="token_request"):
        base.token_request(httpx.Request("GET", BASE))
    with pytest.raises(NotImplementedError, match="read_token"):
        base.read_token(httpx.Response(200))
