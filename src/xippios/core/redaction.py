"""The one credential rule: what is redacted wherever a request is kept or shown.

The result envelope (``ResultMeta.request``, ADR-0030), the fixture recorder's scrub and
the replay helpers (``sent_urls``, ``sent_query``, ``recorded_query``, ``mount_fixture``)
all ask this module, so a name is a credential in all of them or in none.

A parameter name is a credential when one of these words stands in it as a whole word,
between ``_``, ``-`` or the ends of the name, in any letter case: ``api_key`` (also
``apikey``, ``api-key``), ``token``, ``secret``, ``password``, ``passwd``, ``pwd``,
``auth``, ``authorization``, ``sig``, ``signature``, ``credential``, ``credentials``.
``x-api-key``, ``access_token``, ``client_secret`` and the ``sig`` of a pre-signed
storage URL (Azure SAS) are credentials; ``keyword``, ``author``, ``tokens_used``,
``design`` and ``sort_key`` are data. A bare ``key`` is not on the list: Eurostat's
SDMX series ``key`` is data (ADR-0040, decision 6).

A name a ``QueryKeyAuth`` sends its key under is registered when that auth object is
built, and is a credential from then on for the whole process, matched exactly in any
letter case: USDA NASS's ``QueryKeyAuth("key", ...)`` makes ``key`` one wherever NASS's
package is imported, and a process that imports a keyless source alone keeps ``key`` as
data. Nothing unregisters a name.

A source declares a parameter whose name holds ``token`` as a whole word, and no other
credential word, as data with ``register_data_name``: X's ``next_token`` and
``pagination_token``, which a caller reads to page on. It is data from then on for the
whole process, matched exactly in any letter case, and every name nobody declared keeps
the rule; a name a ``QueryKeyAuth`` registered stays a credential though declared.

``redact_credentials`` also reads each text value that is an ``http`` or ``https`` link:
a credential in its query or its userinfo reads ``REDACTED``, as ``scrub_url`` writes it,
so a signed file link (an Azure SAS ``sig``, an S3 ``X-Amz-Signature``) keeps its path
and its other parameters and loses its signature. A link without one is kept as given.

This module sits at the bottom of the package with ``errors`` and imports nothing from
``xippios.core``.
"""

import re
import threading
from collections.abc import Iterable, Mapping
from typing import Any, Final

import httpx

__all__ = [
    "REDACTED",
    "is_credential_name",
    "redact_credentials",
    "register_credential_name",
    "register_data_name",
    "scrub_headers",
    "scrub_params",
    "scrub_url",
]

REDACTED: Final = "REDACTED"
"""What a credential's value is replaced with, in an envelope and in a fixture."""

_CREDENTIAL_WORDS: Final = (
    r"api[_-]?key",
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
    "auth",
    "authorization",
    "sig",
    "signature",
    "credentials?",
)
"""The credential words, as patterns: the rule and ``register_data_name`` read these alone."""


def _whole_word(words: Iterable[str]) -> re.Pattern[str]:
    """One of ``words`` between ``_``, ``-`` or the ends of a name, in any letter case."""
    return re.compile(r"(?i)(?:^|[_-])(?:" + "|".join(words) + r")(?:[_-]|$)")


_CREDENTIAL_WORD = _whole_word(_CREDENTIAL_WORDS)
_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "x-auth-token",
    }
)

_TOKEN_WORD = _whole_word(["token"])
_OTHER_CREDENTIAL_WORD = _whole_word(word for word in _CREDENTIAL_WORDS if word != "token")
_NEVER_DATA = frozenset({"token", "access_token", "refresh_token", "id_token"})
"""The token names of OAuth 2.0 (RFC 6749) and OpenID Connect, and the word alone."""
_LINK = re.compile(r"(?i)https?://")

_registered: frozenset[str] = frozenset()
"""Names registered by ``register_credential_name``, lower-cased; replaced, never changed."""
_data_names: frozenset[str] = frozenset()
"""Names declared by ``register_data_name``, lower-cased; replaced, never changed."""
_lock = threading.Lock()


def register_credential_name(name: str) -> None:
    """Make ``name`` a credential for the rest of the process, in any letter case.

    ``QueryKeyAuth`` calls it with its ``param`` when it is built (ADR-0040, decision 6).
    Registering a name again changes nothing.

    Args:
        name: A query parameter name a key is sent under, e.g. ``"key"``.
    """
    global _registered
    with _lock:
        _registered = _registered | {name.lower()}


def register_data_name(name: str) -> None:
    """Keep the value of a parameter called ``name`` for the rest of the process.

    For a parameter whose name holds the whole word ``token`` but is data, a paging
    cursor such as X's ``next_token``: a source calls it in its ``_client.py``, and the
    value stays as sent in ``ResultMeta.request``, in a recorded fixture and in the
    replay helpers. Matched exactly, in any letter case; every other name with a
    whole-word ``token`` stays a credential, and so does a name a ``QueryKeyAuth``
    registers. Declaring a name again changes nothing.

    Args:
        name: The parameter name as upstream writes it, e.g. ``"next_token"``.

    Raises:
        ValueError: ``name`` holds no whole-word ``token``, or holds another credential
            word (``auth``, ``secret``, ``api_key``, ...), or is ``token`` alone or a token
            name of OAuth 2.0 or OpenID Connect (``access_token``, ``refresh_token``,
            ``id_token``), which name credentials wherever they appear.
    """
    lowered = name.lower()
    if (
        _TOKEN_WORD.search(name) is None
        or _OTHER_CREDENTIAL_WORD.search(name) is not None
        or lowered in _NEVER_DATA
    ):
        raise ValueError(
            f"{name!r} cannot be declared data: only a name that holds the whole word "
            "'token' and no other credential word can, and never token, access_token, "
            "refresh_token or id_token"
        )
    global _data_names
    with _lock:
        _data_names = _data_names | {lowered}


def is_credential_name(name: str) -> bool:
    """True when the value of a parameter called ``name`` must never be kept or shown.

    A whole word of the module's list (``api_key``, ``token``, ``secret``, ``sig``, ...),
    unless a source declared the name data (``register_data_name``), or a name a
    ``QueryKeyAuth`` registered (``key`` for USDA NASS), which nothing makes data.

    Args:
        name: A parameter or mapping key name, e.g. ``"access_token"``.
    """
    lowered = name.lower()
    if lowered in _registered:
        return True
    return lowered not in _data_names and _CREDENTIAL_WORD.search(name) is not None


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_credentials(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str) and _LINK.match(value):
        return _redact_link(value)
    return value


def _redact_link(link: str) -> str:
    """``link`` as ``scrub_url`` writes it when it carries a credential, else as given.

    A link httpx cannot read is ``REDACTED`` whole: its credentials cannot be told apart.
    """
    try:
        url = httpx.URL(link)
    except httpx.InvalidURL:
        return REDACTED
    if url.userinfo or any(is_credential_name(name) for name, _ in url.params.multi_items()):
        return scrub_url(url)
    return link


def redact_credentials(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of ``mapping`` with every credential's value ``REDACTED``, at any depth.

    Nested mappings and lists are copied too; ``mapping`` itself is not changed. A text
    value that is an ``http`` or ``https`` link loses the credentials of its query and its
    userinfo, as ``scrub_url`` writes them, and is kept as given when it carries none.

    Args:
        mapping: Request parameters, e.g. ``{"key": "...", "year": 2024}``.
    """
    return {
        key: REDACTED if isinstance(key, str) and is_credential_name(key) else _redact_value(value)
        for key, value in mapping.items()
    }


def scrub_params(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The query parameters ``items`` with every credential's value ``REDACTED``, in order.

    Args:
        items: ``(name, value)`` pairs, e.g. ``url.params.multi_items()``.
    """
    return [(name, REDACTED if is_credential_name(name) else value) for name, value in items]


def scrub_url(url: httpx.URL | str) -> str:
    """The URL as text, every credential's query value and the userinfo ``REDACTED``.

    Args:
        url: A URL, e.g. ``"https://api.example.test/v1/x?api_key=...&year=2024"``.
    """
    parsed = httpx.URL(url)
    params = httpx.QueryParams(tuple(scrub_params(parsed.params.multi_items())))
    cleaned = parsed.copy_with(params=params)
    if parsed.userinfo:
        cleaned = cleaned.copy_with(username=REDACTED, password=REDACTED)
    return str(cleaned)


def scrub_headers(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The headers ``items`` with the value of each that may carry a credential ``REDACTED``.

    ``Authorization``, ``Proxy-Authorization``, ``Cookie``, ``Set-Cookie``,
    ``X-Api-Key``, ``Api-Key`` and ``X-Auth-Token``, in any letter case.

    Args:
        items: ``(name, value)`` pairs, e.g. ``response.headers.multi_items()``.
    """
    return [
        (name, REDACTED if name.lower() in _SENSITIVE_HEADERS else value) for name, value in items
    ]
