"""Authentication helpers: a key read from the environment, or a bearer that a token renews.

Every upstream sends its key differently: USDA NASS as a query parameter, UN Comtrade
in a header, CashCtrl as the HTTP basic user name. The ``EnvKeyAuth`` classes cover
those shapes and read the key lazily from the environment (conventions §7), an explicit
key winning, so a package imports without credentials and fails with ``ConfigError`` on
the first request instead of at import time. An upstream that exchanges a long-lived
credential for a short-lived bearer, FAOSTAT's login or Google's refresh token, gets a
subclass of ``RenewingBearerAuth`` (ADR-0025, amendment 2026-11-18, point c).
"""

import asyncio
import base64
import os
import threading
import time
import weakref
from collections.abc import AsyncGenerator, Callable, Generator, Mapping
from dataclasses import dataclass
from typing import ClassVar, Final

import httpx
from pydantic import SecretStr

from xippios.core.errors import ConfigError, UpstreamError, XippiosError, error_from_response
from xippios.core.redaction import register_credential_name

__all__ = [
    "RENEWAL_MARGIN",
    "BasicKeyAuth",
    "BearerAuth",
    "BearerToken",
    "EnvKeyAuth",
    "HeaderKeyAuth",
    "QueryKeyAuth",
    "RenewingBearerAuth",
]

RENEWAL_MARGIN: Final = 60.0
"""Seconds before a bearer's ``expires_in`` runs out that ``RenewingBearerAuth`` renews it."""


def _resolve_api_key(
    env_var: str, override: str | SecretStr | None = None, *, source: str | None = None
) -> SecretStr:
    """The key from ``override``, else from ``env_var``; an empty variable counts as unset.

    Raises:
        ConfigError: Neither gives a key; the message names the variable, never a value.
    """
    if override is not None:
        return override if isinstance(override, SecretStr) else SecretStr(override)
    value = os.environ.get(env_var)
    if value:
        return SecretStr(value)
    raise ConfigError(f"{env_var} is not set; export it or pass the key explicitly", source=source)


class EnvKeyAuth(httpx.Auth):
    """Base class: resolve the key once, then let a subclass attach it to each request.

    Subclass and implement ``apply`` for a shape not covered below. ``apply`` reads the
    key through ``self.key()`` where it attaches it, and keeps it in no local variable,
    so no traceback frame holds the key as an argument or a local.

    Args:
        env_var: Variable that holds the key, named as the upstream documents it.
        key: Explicit key; wins over the environment (conventions §7).
        source: Source slug for the ``ConfigError`` message.
    """

    requires_request_body = False

    def __init__(
        self, env_var: str, *, key: str | SecretStr | None = None, source: str | None = None
    ) -> None:
        self.env_var = env_var
        self.source = source
        self._override = key
        self._key: str | None = None
        self._lock = threading.Lock()

    def key(self) -> str:
        """The key, resolved on first use and cached for the life of the object."""
        if self._key is None:
            with self._lock:
                if self._key is None:
                    secret = _resolve_api_key(self.env_var, self._override, source=self.source)
                    self._key = secret.get_secret_value()
        return self._key

    def apply(self, request: httpx.Request) -> None:
        """Attach the key, read with ``self.key()``, to ``request``; implemented by subclasses."""
        raise NotImplementedError

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """The httpx hook: one request, the key attached."""
        self.apply(request)
        yield request


class QueryKeyAuth(EnvKeyAuth):
    """Send the key as a query parameter, e.g. ``?key=...`` for USDA NASS.

    Building one registers ``param`` as a credential name for the whole process
    (``xippios.core.redaction``): its value is ``REDACTED`` in every ``ResultMeta.request``,
    every recorded fixture and every URL ``sent_urls`` gives, also where the name is no
    credential by itself, as ``key`` is not (ADR-0019, decision 6).

    Args:
        param: Query parameter name, e.g. ``"key"``.
        env_var: Variable that holds the key.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        param: str,
        env_var: str,
        *,
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.param = param
        register_credential_name(param)

    def apply(self, request: httpx.Request) -> None:
        """Merge the key into the query string."""
        request.url = request.url.copy_merge_params({self.param: self.key()})


class HeaderKeyAuth(EnvKeyAuth):
    """Send the key in a header, e.g. ``Ocp-Apim-Subscription-Key`` for UN Comtrade.

    Args:
        header: Header name.
        env_var: Variable that holds the key.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        header: str,
        env_var: str,
        *,
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.header = header

    def apply(self, request: httpx.Request) -> None:
        """Set the header."""
        request.headers[self.header] = self.key()


class BearerAuth(EnvKeyAuth):
    """Send the key as ``Authorization: Bearer <key>``."""

    def apply(self, request: httpx.Request) -> None:
        """Set the Authorization header."""
        request.headers["Authorization"] = f"Bearer {self.key()}"


class BasicKeyAuth(EnvKeyAuth):
    """Send the key as the HTTP basic user name, as CashCtrl expects.

    Args:
        env_var: Variable that holds the key.
        password: Basic-auth password; empty for key-as-user-name schemes.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages.
    """

    def __init__(
        self,
        env_var: str,
        *,
        password: str = "",
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(env_var, key=key, source=source)
        self.password = password

    def apply(self, request: httpx.Request) -> None:
        """Set the Authorization header."""
        request.headers["Authorization"] = "Basic " + base64.b64encode(
            f"{self.key()}:{self.password}".encode()
        ).decode("ascii")


@dataclass(frozen=True, slots=True)
class BearerToken:
    """What a token answer gives: the bearer and how long it lives.

    ``RenewingBearerAuth.read_token`` returns it.

    Attributes:
        token: The short-lived bearer, e.g. an OAuth access token; masked in ``repr``.
        expires_in: Its lifetime in seconds from the answer, e.g. ``3599``.
    """

    token: SecretStr
    expires_in: float


class RenewingBearerAuth(httpx.Auth):
    """Exchange a long-lived credential for a short-lived bearer, and renew it in time.

    The base of the ``httpx.Auth`` of an upstream that issues a bearer for a login or a
    refresh token (ADR-0025, amendment 2026-11-18, point c). A source subclasses it and
    writes the token request and the reading of its answer:

    - ``token_request(request)`` builds the request that exchanges the credential, and
      reads each credential through ``credential(name)``;
    - ``read_token(response)`` reads the token answer's HTTP 200 into a ``BearerToken``;
    - ``token_refused(response)`` makes the error for any other status: core's status
      mapping by default. A source maps its upstream's refusals first and names what the
      user does next, the variables to check for a refused login, the consent to run
      again and its scope set for a revoked grant.

    For a request while no bearer is held, or the one held runs out within ``margin``
    seconds, the flow sends the token request first, with the request's ``User-Agent``
    where the token request sets none, and keeps the bearer and when it lapses; then it
    sends the request with ``Authorization: Bearer <token>``. An answer whose status is in
    ``renew_on``, 401 by default, makes one more exchange and sends the request again,
    once, and that answer goes back to the client as it is. A request that finds an
    exchange running on its event loop waits for it and sends the bearer it brought: two
    first requests exchange once, and two requests refused with one bearer renew it once.

    The exchange runs inside httpx's auth flow, below the client's limiter, hooks, cache,
    ``classify`` and retries: it is not paced, observed or retried, and an error it raises
    ends the call. The flow reads the token answer and no other, so a download through it
    streams to its file (ADR-0019, decision 1). httpx keeps the token answer, its body
    read, in the final response's ``history`` for as long as that response lives: a
    caller that keeps a response of ``request`` or ``get`` keeps the bearer with it,
    while ``get_json``, ``get_answer`` and the cache keep no response. The client sends
    its auth to the base URL's origin only (ADR-0015, amendment 2026-11-18, point d).

    The bearer is kept as a ``SecretStr``, and a credential is read when the token request
    is built and kept nowhere, unless it is given to the constructor. It runs on an async
    client only, as core's ``AsyncClient`` is.

    Args:
        source: Source slug for the errors, e.g. ``"faostat"``.
        credentials: Credentials by variable name, which win over the environment
            (conventions §7), e.g. ``{"GOOGLE_DEMO_REFRESH_TOKEN": token}``.
        margin: Seconds before the bearer's ``expires_in`` runs out that it is renewed;
            ``RENEWAL_MARGIN``, 60, by default.
        clock: Monotonic seconds, replaceable in tests.

    Attributes:
        renew_on: The statuses of an answer that make one more exchange, ``{401}``; a
            source whose upstream refuses a bearer with another status too sets its own on
            the class.
        source: As given.
        margin: As given.
    """

    renew_on: ClassVar[frozenset[int]] = frozenset({401})
    # The flow reads the token answer itself: the answer of the request it signs, a
    # streamed download's among them, is never buffered (ADR-0019, decision 1).
    requires_request_body = False
    requires_response_body = False

    def __init__(
        self,
        *,
        source: str | None = None,
        credentials: Mapping[str, str | SecretStr] | None = None,
        margin: float = RENEWAL_MARGIN,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source
        self.margin = margin
        self._clock = clock
        self._given = {
            name: value if isinstance(value, SecretStr) else SecretStr(value)
            for name, value in (credentials or {}).items()
        }
        self._bearer_lock = threading.Lock()
        self._bearer: SecretStr | None = None
        self._lapses_at = 0.0
        self._exchanges: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
            weakref.WeakKeyDictionary()
        )

    def credential(self, name: str) -> str:
        """The credential ``name`` at this moment: given to the constructor, else the variable.

        ``token_request`` reads each credential here, where it builds the request, and
        keeps it in no attribute and in no local that outlives the call. Offline, the
        testing plugin pins it to the placeholder, the check below kept (ADR-0013,
        amendment 2026-11-18, point c), so a source never overrides it.

        Args:
            name: The variable, named as upstream's documents name the credential, e.g.
                ``"FAOSTAT_USERNAME"``.

        Raises:
            ConfigError: Neither holds it, an empty variable counting as unset; the
                message names the variable and says what ``credential_help`` says, never
                a value.
        """
        given = self._given.get(name)
        if given is not None:
            return given.get_secret_value()
        value = os.environ.get(name)
        if value:
            return value
        raise self._unset(name)

    def credential_help(self, name: str) -> str:
        """What ``credential``'s ``ConfigError`` for an unset ``name`` tells the user to do.

        The text after ``"<name> is not set; "``. A source names what its credentials are,
        e.g. ``"FAOSTAT needs a FAO account: export FAOSTAT_USERNAME (the account's e-mail)
        and FAOSTAT_PASSWORD"``.
        """
        return "export it or pass it in credentials="

    def token_request(self, request: httpx.Request) -> httpx.Request:
        """The request that exchanges the credential for a bearer, sent ahead of ``request``.

        Written by the source: a login's form, a refresh token's grant, each credential
        read through ``credential``. The flow sends it with ``request``'s ``User-Agent``
        unless it sets one.

        Raises:
            NotImplementedError: Here; a subclass writes it.
        """
        raise NotImplementedError(f"{type(self).__name__} must write token_request")

    def read_token(self, response: httpx.Response) -> BearerToken:
        """The bearer and its lifetime from the token answer's HTTP 200, read in full.

        Written by the source. An answer that is not the documented one raises
        ``ValidationError`` and quotes nothing of it, since its text holds the bearer;
        a source keeps whatever else the answer grants, a scope set say, here.

        Raises:
            NotImplementedError: Here; a subclass writes it.
        """
        raise NotImplementedError(f"{type(self).__name__} must write read_token")

    def token_refused(self, response: httpx.Response) -> XippiosError:
        """The error for a token answer of another status than HTTP 200, read in full.

        Raised by the flow, it ends the call. Core's status mapping by default
        (``error_from_response``): ``AuthError`` for a 401 or 403, ``RateLimitError`` for
        a 429, ``UpstreamError`` for a 5xx; another status is an ``UpstreamError`` that
        names the method, the path and the status and quotes nothing.
        """
        error = error_from_response(response, source=self.source)
        if error is not None:
            return error
        request = response.request
        return UpstreamError(
            f"{request.method} {request.url.path} answered HTTP {response.status_code}, not "
            "the documented 200; nothing of it is shown",
            status=response.status_code,
            body="",
            source=self.source,
        )

    def reset(self) -> None:
        """Forget the bearer, so that the next request exchanges the credential again."""
        with self._bearer_lock:
            self._bearer = None
            self._lapses_at = 0.0

    def _holds(self, name: str) -> bool:
        """Whether ``credential`` finds ``name``; the testing plugin's pin asks it."""
        return name in self._given or bool(os.environ.get(name))

    def _unset(self, name: str) -> ConfigError:
        return ConfigError(f"{name} is not set; {self.credential_help(name)}", source=self.source)

    def _current(self) -> SecretStr | None:
        """The bearer while it runs out beyond the margin, else ``None``."""
        with self._bearer_lock:
            if self._bearer is not None and self._clock() < self._lapses_at:
                return self._bearer
            return None

    def _exchange_lock(self) -> asyncio.Lock:
        """The lock that makes the exchanges on the running event loop single-flight."""
        loop = asyncio.get_running_loop()
        with self._bearer_lock:
            lock = self._exchanges.get(loop)
            if lock is None:
                lock = self._exchanges[loop] = asyncio.Lock()
            return lock

    def _ask(self, request: httpx.Request) -> httpx.Request:
        """``token_request``, with ``request``'s ``User-Agent`` where it sets none."""
        asked = self.token_request(request)
        agent = request.headers.get("user-agent")
        if agent is not None and "user-agent" not in asked.headers:
            asked.headers["User-Agent"] = agent
        return asked

    async def _keep(self, response: httpx.Response) -> SecretStr:
        """Read the token answer, keep its bearer and when it lapses; return the bearer."""
        await response.aread()
        if response.status_code != 200:
            raise self.token_refused(response)
        bearer = self.read_token(response)
        lapses_at = self._clock() + max(0.0, bearer.expires_in - self.margin)
        with self._bearer_lock:
            self._bearer = bearer.token
            self._lapses_at = lapses_at
        return bearer.token

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """The httpx hook: exchange without a current bearer, sign, renew once on refusal.

        A token answer is read here; the answer of the signed request is handed back to
        the client unread, its status alone looked at.
        """
        token = self._current()
        if token is None:
            async with self._exchange_lock():
                token = self._current()  # another request's exchange may have brought one
                if token is None:
                    answer = yield self._ask(request)
                    token = await self._keep(answer)
        _sign(request, token)
        response = yield request
        if response.status_code in self.renew_on:
            refused = token
            async with self._exchange_lock():
                token = self._current()
                if token is None or token is refused:  # nobody renewed it meanwhile
                    answer = yield self._ask(request)
                    token = await self._keep(answer)
            _sign(request, token)
            yield request

    def sync_auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        """Not served: the bearer runs on an async client, as core's ``AsyncClient`` is.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            f"{type(self).__name__} runs on an async client only (async_auth_flow), as "
            "xippios.core's AsyncClient is"
        )


def _sign(request: httpx.Request, token: SecretStr) -> None:
    """Attach ``token`` to ``request`` as a bearer."""
    request.headers["Authorization"] = f"Bearer {token.get_secret_value()}"
