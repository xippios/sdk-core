"""The api.data.gov gateway: its key, its documented answers and one quota per key.

api.data.gov (API Umbrella) fronts the APIs of every agency that takes part in it, USDA
FAS's PSD, ESR and GATS at ``api.fas.usda.gov`` among them. One key serves them all, and
one hourly quota counts every request made with it (ADR-0009). ``Gateway`` holds what
every source behind it shares, once (ADR-0023: sdk-usda-psd, sdk-usda-esr and
sdk-usda-gats each carried a copy)::

    from xippios.core.data_gov import Gateway

    gateway = Gateway("usda-psd")


    def classify(response: httpx.Response) -> XippiosError | None:
        error = gateway.classify(response)
        if error is not None:
            return error
        ...  # the source's own documented answers, then None


    config = gateway.install(ClientConfig(..., classify=classify))
    client = AsyncClient(config, auth=gateway.auth)

What the gateway sends, as sdk-usda-psd recorded it on 2026-10-23 (its
``tests/fixtures/PSDData_GetCommodities/``):

- Every answer to a valid key carries ``x-ratelimit-limit: 1000`` and
  ``x-ratelimit-remaining``, the requests left in the key's rolling hour; no reset
  header.
- A spent quota answers 429 ``{"error": {"code": "OVER_RATE_LIMIT", "message": ...}}``
  with ``x-ratelimit-remaining: 0`` and ``Retry-After: 3151`` (``over_rate_limit.json``).
  The developer manual (https://api.data.gov/docs/developer-manual/, read 2026-10-23)
  documents no ``Retry-After``, only that "the block will automatically be lifted by
  waiting an hour", which ADR-0010's context records; so the wait is ``Retry-After``
  when the gateway sends one and ``WINDOW``, the hour, when it does not.
- A key the gateway refuses answers 401 or 403 with an ``API_KEY_*`` code in the same
  body and no quota headers (``invalid_key.json``: 403 ``API_KEY_INVALID``); a path it
  does not route answers 404 ``NOT_FOUND`` (documented, not recorded).

The gateway ends its messages with its URL (``"... https://api.fas.usda.gov:443"``);
every error here writes it ``<host>`` (ADR-0005).
"""

import re
from typing import ClassVar

import httpx

from xippios.core.client.auth import HeaderKeyAuth
from xippios.core.client.config import ClientConfig
from xippios.core.client.quota import QuotaPolicy
from xippios.core.errors import AuthError, NotFoundError, RateLimitError, XippiosError

__all__ = [
    "API_KEY_ENV",
    "KEY_HEADER",
    "LIMIT_HEADER",
    "REMAINING_HEADER",
    "WINDOW",
    "Gateway",
]

API_KEY_ENV = "DATA_GOV_API_KEY"  # pragma: allowlist secret (a variable name, not a key)
"""The variable every source behind api.data.gov reads its key from (ADR-0009)."""
KEY_HEADER = "X-Api-Key"
"""The header the key is sent in."""
WINDOW = 3600.0
"""The quota's window in seconds: a rolling hour per key, and the wait without ``Retry-After``."""
LIMIT_HEADER = "x-ratelimit-limit"
"""The header with the quota's size, 1,000 requests by default."""
REMAINING_HEADER = "x-ratelimit-remaining"
"""The header with the requests left in the key's rolling hour."""

_GATEWAY = "api.data.gov"
_URL = re.compile(r"https?://[^/\s]+")


class _GatewayQuota(QuotaPolicy):
    """The gateway's quota policy: its refusal before sending names the key's variable."""

    _subject = f"{_GATEWAY} quota of the key in {API_KEY_ENV}"


def _gateway_error(response: httpx.Response) -> tuple[str | None, str]:
    """The gateway's ``{"error": {"code": ..., "message": ...}}``, or ``(None, "")``.

    The message comes back host-free: the gateway's URL is written ``<host>``.
    """
    try:
        payload = response.json()
    except ValueError:
        return None, ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict) or not isinstance(error.get("code"), str):
        return None, ""
    message = error.get("message")
    return error["code"], _URL.sub("<host>", message) if isinstance(message, str) else ""


class Gateway:
    """api.data.gov for one source behind it: the key, the gateway's answers, the quota.

    Every instance shares ``Gateway.policy``, one ``QuotaPolicy`` per process for the key
    in ``DATA_GOV_API_KEY``: what one source spends, another source's next request sees,
    and it waits that out within the policy's cap or is refused without being sent
    (ADR-0009; ADR-0010, decision 4). ``classify``'s errors carry the source's slug; the
    policy's refusal before sending speaks for the gateway, ``source="api.data.gov"``,
    and names the variable, the method and the path.

    Args:
        source: The calling source's slug, e.g. ``"usda-psd"``, for its errors and for the
            ``ConfigError`` when ``DATA_GOV_API_KEY`` is unset.

    Attributes:
        source: As given.
        auth: The key from ``DATA_GOV_API_KEY`` in the ``X-Api-Key`` header, read on the
            first request (conventions §7); the client's ``auth``.
        policy: The process's one policy for the key: ``x-ratelimit-limit`` and
            ``x-ratelimit-remaining`` read from every answer from the wire, a window of
            one hour, created when this module is imported.
    """

    policy: ClassVar[QuotaPolicy] = _GatewayQuota(
        limit_header=LIMIT_HEADER,
        remaining_header=REMAINING_HEADER,
        window=WINDOW,
        source=_GATEWAY,
    )

    def __init__(self, source: str) -> None:
        self.source = source
        self.auth = HeaderKeyAuth(KEY_HEADER, API_KEY_ENV, source=source)

    def install(self, config: ClientConfig) -> ClientConfig:
        """``config`` with the shared policy's ``before_request`` and ``observe`` hooks.

        ``Gateway.policy.install(config)``: ``config`` itself is unchanged, hooks it had
        are replaced, and installing again changes nothing.

        Args:
            config: The source's client configuration, whose ``classify`` asks this
                gateway's ``classify`` first.
        """
        return self.policy.install(config)

    def classify(self, response: httpx.Response) -> XippiosError | None:
        """The gateway's documented answers as taxonomy errors in the source's name.

        - 401 or 403 with an ``error.code`` starting ``API_KEY_`` (the developer manual
          names ``API_KEY_MISSING``, ``API_KEY_INVALID``, ``API_KEY_DISABLED``,
          ``API_KEY_UNAUTHORIZED`` and ``API_KEY_UNVERIFIED``) is an ``AuthError`` naming
          the code and the variable, never the key.
        - 429 (``OVER_RATE_LIMIT``) is a ``RateLimitError`` whose ``retry_after`` is the
          wait ``Gateway.policy`` keeps the quota spent for: ``observe`` has read this
          answer before ``classify`` runs (ADR-0015, decision 1), so the wait counts to
          the snapshot's ``resumes_at``, from ``Retry-After`` or one ``WINDOW``. The
          message names the gateway's allowance, that every package using the key
          shares it, and the quota as the snapshot reports it. Whether the client
          retries is the retry loop's: a wait beyond its ``backoff_max`` ends the
          retries after one request. When the shared snapshot shows no spent quota
          still ahead, because no client observed this answer, another answer has
          replaced the snapshot since, or the quota is back already, the wait is the
          one the policy would set from this answer, and the message says it in
          seconds. Called on its own while the shared quota is spent, it reads the
          snapshot like any other call.
        - 404 with ``error.code`` ``NOT_FOUND`` is a ``NotFoundError`` naming the path.

        Everything else is ``None``: the source's own ``classify`` goes on with its
        documented answers, and core's status mapping follows. Messages name the path,
        never the host.

        Args:
            response: A response from the wire, any status.
        """
        status = response.status_code
        if status in (401, 403):
            code, message = _gateway_error(response)
            if code is not None and code.startswith("API_KEY_"):
                return AuthError(
                    f"api.data.gov refused the key in {API_KEY_ENV} (HTTP {status} {code}: "
                    f"{message}). Check that the variable holds a valid, active api.data.gov "
                    "key.",
                    status=status,
                    source=self.source,
                )
            return None
        if status == 429:
            return self._over_rate_limit(response)
        if status == 404:
            code, message = _gateway_error(response)
            if code == "NOT_FOUND":
                return NotFoundError(
                    f"api.data.gov has no route for {response.request.url.path} "
                    f"(HTTP 404 NOT_FOUND: {message})",
                    source=self.source,
                )
        return None

    def _over_rate_limit(self, response: httpx.Response) -> RateLimitError:
        """The gateway's 429, ``retry_after`` as long as the shared policy keeps it spent."""
        code, message = _gateway_error(response)
        upstream = ": ".join(part for part in (code, message) if part)
        policy = self.policy
        snapshot = policy.snapshot()
        wait = policy._wait_left(snapshot)
        if wait is None:  # the snapshot shows no spent quota still ahead: read this answer
            snapshot, wait = None, policy._wait(response, policy._clock())
        allowance = (
            f"{snapshot.limit} requests per rolling hour per key"
            if snapshot is not None and snapshot.limit is not None
            else "an hourly quota per key"
        )
        state = (
            f"Quota: {snapshot.describe()}."
            if snapshot is not None
            else f"The quota is expected back in {wait:.0f} s."
        )
        return RateLimitError(
            f"api.data.gov rate limit reached for the key in {API_KEY_ENV} "
            f"(HTTP 429{' ' + upstream if upstream else ''}). The gateway allows {allowance}, "
            f"shared by every package using that key. {state}",
            retry_after=wait,
            source=self.source,
        )
