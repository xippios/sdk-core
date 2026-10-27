"""The one credential rule: what is redacted wherever a request is kept or shown.

The result envelope (``ResultMeta.request``, ADR-0005), the fixture recorder's scrub and
the replay helpers (``sent_urls``, ``sent_query``, ``recorded_query``, ``mount_fixture``)
all ask this module, so a name is a credential in all of them or in none.

A parameter name is a credential when one of these words stands in it as a whole word,
between ``_``, ``-`` or the ends of the name, in any letter case: ``api_key`` (also
``apikey``, ``api-key``), ``token``, ``secret``, ``password``, ``passwd``, ``auth``,
``authorization``, ``signature``, ``credential``, ``credentials``. ``x-api-key``,
``access_token`` and ``client_secret`` are credentials; ``keyword``, ``author``,
``tokens_used`` and ``sort_key`` are data. A bare ``key`` is not on the list: Eurostat's
SDMX series ``key`` is data (ADR-0019, decision 6).

A name a ``QueryKeyAuth`` sends its key under is registered when that auth object is
built, and is a credential from then on for the whole process, matched exactly in any
letter case: USDA NASS's ``QueryKeyAuth("key", ...)`` makes ``key`` one wherever NASS's
package is imported, and a process that imports a keyless source alone keeps ``key`` as
data. Nothing unregisters a name.

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
    "scrub_headers",
    "scrub_params",
    "scrub_url",
]

REDACTED: Final = "REDACTED"
"""What a credential's value is replaced with, in an envelope and in a fixture."""

_CREDENTIAL_WORD = re.compile(
    r"(?i)(?:^|[_-])"
    r"(?:api[_-]?key|token|secret|password|passwd|auth|authorization|signature|credentials?)"
    r"(?:[_-]|$)"
)
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

_registered: frozenset[str] = frozenset()
"""Names registered by ``register_credential_name``, lower-cased; replaced, never changed."""
_lock = threading.Lock()


def register_credential_name(name: str) -> None:
    """Make ``name`` a credential for the rest of the process, in any letter case.

    ``QueryKeyAuth`` calls it with its ``param`` when it is built (ADR-0019, decision 6).
    Registering a name again changes nothing.

    Args:
        name: A query parameter name a key is sent under, e.g. ``"key"``.
    """
    global _registered
    with _lock:
        _registered = _registered | {name.lower()}


def is_credential_name(name: str) -> bool:
    """True when the value of a parameter called ``name`` must never be kept or shown.

    A whole word of the module's list (``api_key``, ``token``, ``secret``, ...), or a name
    a ``QueryKeyAuth`` registered (``key`` for USDA NASS).
    """
    return name.lower() in _registered or _CREDENTIAL_WORD.search(name) is not None


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_credentials(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def redact_credentials(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of ``mapping`` with every credential's value ``REDACTED``, at any depth.

    Nested mappings and lists are copied too; ``mapping`` itself is not changed.
    """
    return {
        key: REDACTED if isinstance(key, str) and is_credential_name(key) else _redact_value(value)
        for key, value in mapping.items()
    }


def scrub_params(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The query parameters ``items`` with every credential's value ``REDACTED``, in order."""
    return [(name, REDACTED if is_credential_name(name) else value) for name, value in items]


def scrub_url(url: httpx.URL | str) -> str:
    """The URL as text, every credential's query value and the userinfo ``REDACTED``."""
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
    """
    return [
        (name, REDACTED if name.lower() in _SENSITIVE_HEADERS else value) for name, value in items
    ]
