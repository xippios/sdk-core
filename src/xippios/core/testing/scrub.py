"""Remove credentials and tenant traces from what gets written into a fixture.

The matching is deliberately broad: a redacted ``keyword`` parameter costs nothing,
a leaked API key costs a rotation. Credential-like query parameters, userinfo and
credential headers are always redacted; a ``Scrub`` adds what only the source knows: a
placeholder for a tenant's host, the secret values themselves, and a rewrite for
pre-authenticated URLs.
"""

import base64
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import httpx

__all__ = ["REDACTED", "Scrub", "scrub_headers", "scrub_params", "scrub_url"]

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
_HOST_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")
_BINARY_BODY = "binary body cannot be scrubbed; pass allow_binary=True to store it base64, flagged"


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Scrub:
    r"""What a recording must not keep besides credentials, removed before anything is written.

    ``write_fixture`` and ``record`` apply it in memory to the whole fixture (request
    URL, request body, response headers, response body) and write the file once,
    already scrubbed, so the file never holds what was removed, not even briefly
    (conventions §10). The credential scrubbing of ``scrub_url`` and ``scrub_headers``
    always applies as well. No scrub reads a binary body: a request or response body
    that is not UTF-8 text is refused with ``ValueError`` unless ``allow_binary`` is
    set, and is then stored base64, unscrubbed, flagged with ``body_base64``.

    Attributes:
        host: Placeholder for the request's host, e.g. ``"demo.example.test"``, for an
            upstream that serves each tenant from a host of its own. The request URL
            gets it, and every occurrence of the original host in URL, headers and
            bodies becomes it: in any letter case, in its IDNA form too where that
            differs, plain or percent-encoded. ``None`` keeps the host, for a public
            upstream.
        secrets: Values that must never be written, e.g. a key or a tenant name. Each
            becomes ``REDACTED`` wherever it appears in URL, headers and bodies, plain
            or percent-encoded (either hex case, ``+`` for a space; ``/`` also as JSON's
            ``\/``), the longest value first, in the letter case given. An empty
            value is refused with ``ValueError``.
        rewrite: A text hook applied after ``host`` and ``secrets`` to the request body,
            the response body and every response header value (``Location`` and
            ``Content-Location`` included), for pre-authenticated URLs the source knows
            how to neutralise, such as a signed storage URL. Not applied to the request
            URL.
        allow_binary: Store a body that is not UTF-8 text base64 and flagged instead of
            raising ``ValueError``. Nothing in it is scrubbed.
    """

    host: str | None = None
    secrets: Sequence[str] = ()
    rewrite: Callable[[str], str] | None = None
    allow_binary: bool = False

    def __post_init__(self) -> None:
        if self.host is not None and not _HOST_NAME.fullmatch(self.host):
            raise ValueError("host must be a plain host name such as 'demo.example.test'")
        if isinstance(self.secrets, str):
            raise TypeError("secrets is a sequence of values, e.g. [value], not one string")
        secrets = tuple(self.secrets)
        if any(not value for value in secrets):
            raise ValueError("secrets must not contain an empty string")
        object.__setattr__(self, "secrets", secrets)


def _plain_or_encoded(value: str) -> str:
    r"""A pattern for ``value`` with each character plain or percent-encoded.

    Covers any mix: what a URL encoder leaves alone and what it encodes, in either hex
    case, ``+`` for a space as in a form body or a query, and ``\/`` for ``/`` as some
    JSON encoders write it.
    """
    parts = []
    for char in value:
        encoded = "".join(
            "%" + "".join(f"[{c}{c.lower()}]" if c.isalpha() else c for c in f"{byte:02X}")
            for byte in char.encode("utf-8")
        )
        options = [re.escape(char), encoded]
        if char == " ":
            options.append(r"\+")
        elif char == "/":
            options.append(r"\\/")
        parts.append("(?:" + "|".join(options) + ")")
    return "".join(parts)


class _Scrubber:
    """A ``Scrub`` bound to the request it scrubs: the original host's patterns compiled."""

    def __init__(self, scrub: Scrub, url: httpx.URL) -> None:
        self._scrub = scrub
        self._host: re.Pattern[str] | None = None
        if scrub.host is not None:
            forms = {form for form in (url.host, url.raw_host.decode("ascii")) if form}
            if forms:
                longest_first = sorted(forms, key=len, reverse=True)
                self._host = re.compile(
                    "|".join(_plain_or_encoded(form) for form in longest_first), re.IGNORECASE
                )
        self._secrets = [
            re.compile(_plain_or_encoded(value))
            for value in sorted(scrub.secrets, key=len, reverse=True)
        ]

    def text(self, text: str) -> str:
        """``text`` with the original host made the placeholder, then secrets redacted."""
        if self._host is not None and self._scrub.host is not None:
            placeholder = self._scrub.host
            text = self._host.sub(lambda _: placeholder, text)
        for pattern in self._secrets:
            text = pattern.sub(lambda _: REDACTED, text)
        return text

    def rewritten(self, text: str) -> str:
        """``text`` scrubbed, then passed through the source's ``rewrite`` hook."""
        text = self.text(text)
        return self._scrub.rewrite(text) if self._scrub.rewrite is not None else text

    def url(self, url: httpx.URL) -> str:
        """The URL with credentials redacted, the placeholder host, secrets redacted."""
        cleaned = httpx.URL(scrub_url(url))
        if self._scrub.host is not None:
            cleaned = cleaned.copy_with(host=self._scrub.host)
        return self.text(str(cleaned))

    def headers(self, items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        """Headers with credentials redacted, names scrubbed, values scrubbed and rewritten."""
        return [(self.text(name), self.rewritten(value)) for name, value in scrub_headers(items)]

    def body(self, content: bytes) -> tuple[str, bool]:
        """``(text, False)`` scrubbed and rewritten, or ``(base64, True)`` when allowed.

        Raises:
            ValueError: ``content`` is not UTF-8 text and ``allow_binary`` is not set.
        """
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            if not self._scrub.allow_binary:
                raise ValueError(_BINARY_BODY) from None
            return base64.b64encode(content).decode("ascii"), True
        return self.rewritten(text), False
