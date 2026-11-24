"""Authentication helpers: a key read from the environment, or a bearer that a token renews.

Every upstream sends its key in one of four places: a query parameter, a header, a bearer
or the HTTP basic user name. ``KeyAuth``, the one key class (ADR-0059, decision 7), takes
the place and reads the key lazily from the environment (conventions §7), an explicit key
winning, so a package imports without credentials and fails with ``ConfigError`` on the
first request instead of at import time. An upstream that exchanges a long-lived
credential for a short-lived bearer, by a login or by a refresh token, gets a
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
from typing import ClassVar, Final, Literal, get_args

import httpx
from pydantic import SecretStr

from xippios.core.errors import (
    IDEMPOTENT_METHODS,
    AuthError,
    ConfigError,
    NotFoundError,
    RateLimitError,
    UpstreamError,
    XippiosError,
    parse_retry_after,
    request_description,
)
from xippios.core.redaction import register_credential_name

__all__ = [
    "RENEWAL_MARGIN",
    "BearerToken",
    "EnvKeyAuth",
    "KeyAuth",
    "KeyLocation",
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

    ``KeyAuth`` is the one subclass core ships. ``apply`` reads the key through
    ``self.key()`` where it attaches it, and keeps it in no local variable, so no traceback
    frame holds the key as an argument or a local.

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


KeyLocation = Literal["query", "header", "bearer", "basic"]
"""Where ``KeyAuth`` sends the key: a query parameter, a header, a bearer or basic auth."""

_LOCATIONS: Final[tuple[KeyLocation, ...]] = get_args(KeyLocation)
_NAMED: Final = {"query": "query parameter", "header": "header"}


class KeyAuth(EnvKeyAuth):
    """Send the key where upstream documents it: a query parameter, a header, a bearer, basic auth.

    The family's one key class (ADR-0059, decision 7), which a source builds in its
    ``_client.py``. ``location`` names where the key travels, and ``name`` the query
    parameter or the header that carries it, as upstream's documentation names it:

    - ``"query"``: the key goes as the query parameter ``name`` of every request,
      ``?key=<key>`` for ``name="key"``. Building one registers ``name`` as a credential
      name of its ``source`` (``xippios.core.redaction``), which it then takes: the value
      is ``REDACTED`` in every ``ResultMeta.request`` of that source, every recorded
      fixture and every URL ``sent_urls`` gives, also where the name is no credential by
      itself, as ``key`` is not, while another source's ``key`` stays data (ADR-0040,
      decision 6, amendment 2026-11-24).
    - ``"header"``: the key goes as the value of the header ``name``,
      ``X-Api-Key: <key>`` for ``name="X-Api-Key"``.
    - ``"bearer"``: the key goes as ``Authorization: Bearer <key>``; no ``name``.
    - ``"basic"``: the key goes as the HTTP basic user name with an empty password,
      ``Authorization: Basic`` and the two in base64; no ``name``.

    The key is read from ``env_var`` on the first request, an explicit ``key`` winning, as
    ``EnvKeyAuth`` reads it.

    Args:
        env_var: Variable that holds the key, e.g. ``"EXAMPLE_API_KEY"``.
        location: Where the key travels: ``"query"``, ``"header"``, ``"bearer"`` or
            ``"basic"``.
        name: The query parameter or the header that carries the key, e.g. ``"key"`` or
            ``"X-Api-Key"``; given for ``"query"`` and ``"header"`` and only for them.
        key: Explicit key; wins over the environment.
        source: Source slug for error messages, e.g. ``"example"``, and for ``"query"`` the
            source whose answers read ``name`` as a credential, given then.

    Raises:
        ValueError: ``location`` is none of the four, or ``name`` is missing or empty for
            ``"query"`` or ``"header"``, or given for ``"bearer"`` or ``"basic"``, or
            ``source`` is missing for ``"query"``; nothing is registered.
    """

    def __init__(
        self,
        env_var: str,
        *,
        location: KeyLocation,
        name: str | None = None,
        key: str | SecretStr | None = None,
        source: str | None = None,
    ) -> None:
        if location not in _LOCATIONS:
            raise ValueError(
                f"location is one of {', '.join(_LOCATIONS[:-1])} or {_LOCATIONS[-1]}, "
                f"not {location!r}"
            )
        carrier = _NAMED.get(location)
        if carrier is not None and not name:
            raise ValueError(
                f'location="{location}" takes name=, the {carrier} that carries the key'
            )
        if carrier is None and name is not None:
            raise ValueError(
                f'location="{location}" takes no name=: the key goes in the Authorization header'
            )
        if location == "query" and not source:
            raise ValueError(
                'location="query" takes source=, the source whose answers read name= as a '
                "credential"
            )
        super().__init__(env_var, key=key, source=source)
        self.location = location
        self.name = name
        if location == "query" and name and source:
            register_credential_name(name, source=source)

    def apply(self, request: httpx.Request) -> None:
        """Attach the key where ``location`` sends it."""
        name = self.name or ""  # given for query and header, as the constructor checked
        if self.location == "query":
            request.url = request.url.copy_merge_params({name: self.key()})
        elif self.location == "header":
            request.headers[name] = self.key()
        elif self.location == "bearer":
            request.headers["Authorization"] = f"Bearer {self.key()}"
        else:  # basic: the key as the user name, the password empty
            request.headers["Authorization"] = "Basic " + base64.b64encode(
                f"{self.key()}:".encode()
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
    - ``token_refused(response)`` makes the error for any other status: the status's
      taxonomy error by default, quoting nothing of the answer. A source maps its
      upstream's refusals first and names what the user does next, the variables to check
      for a refused login, the consent to run again and its scope set for a revoked grant.

    For a request while no bearer is held, or the one held runs out within
    ``RENEWAL_MARGIN``, 60 seconds, the flow sends the token request first, with the
    request's ``User-Agent`` where the token request sets none, and keeps the bearer and
    when it lapses; then it sends the request with ``Authorization: Bearer <token>``. An
    answer to a read whose status is in ``renew_on``, 401 by default, makes one more
    exchange and sends the read again, once, and that answer goes back to the client as it
    is. A write, a request of any method but ``GET``, ``HEAD`` and ``OPTIONS``, is sent
    once (ADR-0011, amendment 2026-11-24): its refusal goes back to the client, which
    raises it, and the refused bearer is dropped, so that the next request exchanges
    first. A request that finds an exchange running on its event loop waits for it and
    sends the bearer it brought: two first requests exchange once, and two requests
    refused with one bearer renew it once.

    The exchange runs inside httpx's auth flow, below the client's limiter, hooks, cache and
    ``classify``: it is not paced, ``observe`` sees its token answer only in the ``history``
    of the answer that follows it, and a token answer that ``token_refused`` or
    ``read_token`` refuses raises an error that ends the call, so no hook sees that answer. A
    transport failure of the exchange counts as one of the request it precedes, so the
    client's retry policy sends that request again, exchange included, where it would for
    the request alone (ADR-0011). The flow reads the token answer and no other, so a
    download through it streams to its file (ADR-0040, decision 1). httpx keeps the token
    answer, its body read, and the refused answer before a resend in the final response's
    ``history`` for as long as that response lives: a caller that keeps a response of
    ``request`` or ``get`` keeps the bearer with it, while ``get_answer``, ``post_json`` and
    the cache keep no response, and the recorder's ``send_once`` and a download's refusal
    keep that history as statuses alone. The two refresh frames count one request for each
    answer in it, so a run's count holds each exchange and resend, and not a token request
    whose answer the flow refused (ADR-0062, decisions 4 and 14). The client sends its auth
    to the base URL's origin only (ADR-0037, decision 4).

    The bearer is kept as a ``SecretStr``, and a credential is read when the token request
    is built and kept nowhere, unless it is given to the constructor. It runs on an async
    client only, as core's ``AsyncClient`` is.

    Args:
        source: Source slug for the errors, e.g. ``"example"``.
        credentials: Credentials by variable name, which win over the environment
            (conventions §7), e.g. ``{"EXAMPLE_DEMO_REFRESH_TOKEN": token}``.
        clock: Monotonic seconds, replaceable in tests.

    Attributes:
        renew_on: The statuses of an answer that make one more exchange for a read and
            drop the bearer after a write, ``{401}``; a source whose upstream refuses a
            bearer with another status too sets its own on the class.
        source: As given.
        margin: Seconds before the bearer's ``expires_in`` runs out that it is renewed,
            ``RENEWAL_MARGIN``, which no constructor argument changes; two sources' tests
            read it (ADR-0059, decision 2).
    """

    renew_on: ClassVar[frozenset[int]] = frozenset({401})
    # The flow reads the token answer itself: the answer of the request it signs, a
    # streamed download's among them, is never buffered (ADR-0040, decision 1).
    requires_request_body = False
    requires_response_body = False

    def __init__(
        self,
        *,
        source: str | None = None,
        credentials: Mapping[str, str | SecretStr] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.source = source
        self.margin = RENEWAL_MARGIN
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
        testing plugin pins it to the placeholder, the check below kept (ADR-0035,
        decision 3), so a source never overrides it.

        Args:
            name: The variable, named as upstream's documents name the credential, e.g.
                ``"EXAMPLE_USERNAME"``.

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
        e.g. ``"example needs an account: export EXAMPLE_USERNAME (the account's e-mail)
        and EXAMPLE_PASSWORD"``.
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

        Raised by the flow, it ends the call. By default the error that core's status
        mapping gives the status, its message the status, the request as
        ``request_description`` names it and the reason phrase, or ``no reason phrase``,
        ``503 from POST /token: Service Unavailable``, and nothing of the answer, which a
        token endpoint may write from the credentials it was sent: ``AuthError`` for a 401
        or 403, ``RateLimitError`` for a 429 with ``Retry-After``'s wait, ``NotFoundError``
        for a 404 and ``UpstreamError`` with no ``body`` for any other 4xx or 5xx. Another
        status below 400 is an ``UpstreamError`` that says the answer is not the documented
        200. A source that knows its endpoint's error answers reads them in its override, as
        it reads the 200 in ``read_token``.
        """
        status = response.status_code
        where = request_description(response)
        if status < 400:
            return UpstreamError(
                f"{where} answered HTTP {status}, not the documented 200; nothing of it is shown",
                status=status,
                body="",
                source=self.source,
            )
        message = f"{status} from {where}: {response.reason_phrase or 'no reason phrase'}"
        if status in (401, 403):
            return AuthError(message, status=status, source=self.source)
        if status == 429:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            return RateLimitError(message, retry_after=retry_after, source=self.source)
        if status == 404:
            return NotFoundError(message, source=self.source)
        return UpstreamError(message, status=status, body="", source=self.source)

    def reset(self) -> None:
        """Forget the bearer, so that the next request exchanges the credential again."""
        with self._bearer_lock:
            self._bearer = None
            self._lapses_at = 0.0

    def _forget(self, refused: SecretStr) -> None:
        """Drop ``refused`` while it is the bearer held, so that the next request exchanges.

        A bearer that another request renewed meanwhile stays.
        """
        with self._bearer_lock:
            if self._bearer is refused:
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
        the client unread, its status alone looked at. A read refused with a status of
        ``renew_on`` is renewed and sent again; a write is sent once (ADR-0011, amendment
        2026-11-24), so its refusal goes back and the next request exchanges first, since
        an exchange here would hand the token answer back as the write's.
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
            if request.method not in IDEMPOTENT_METHODS:
                self._forget(token)
                return
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
