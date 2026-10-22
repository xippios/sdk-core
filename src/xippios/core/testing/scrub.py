"""Remove credentials from what gets written into a fixture.

The matching is deliberately broad: a redacted ``keyword`` parameter costs nothing,
a leaked API key costs a rotation.
"""

import re
from collections.abc import Iterable

import httpx

__all__ = ["REDACTED", "scrub_headers", "scrub_params", "scrub_url"]

REDACTED = "REDACTED"

_SENSITIVE_PARAM = re.compile(r"key|token|secret|pass|auth|sig|cred", re.IGNORECASE)
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


def scrub_params(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Redact the value of every query parameter whose name looks like a credential."""
    return [(name, REDACTED if _SENSITIVE_PARAM.search(name) else value) for name, value in items]


def scrub_url(url: httpx.URL | str) -> str:
    """The URL as text with credential-like query values and userinfo redacted."""
    parsed = httpx.URL(url)
    params = httpx.QueryParams(tuple(scrub_params(parsed.params.multi_items())))
    cleaned = parsed.copy_with(params=params)
    if parsed.userinfo:
        cleaned = cleaned.copy_with(username=REDACTED, password=REDACTED)
    return str(cleaned)


def scrub_headers(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Redact the value of every header that may carry a credential."""
    return [
        (name, REDACTED if name.lower() in _SENSITIVE_HEADERS else value) for name, value in items
    ]
