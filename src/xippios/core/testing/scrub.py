"""Remove credentials and tenant traces from what gets written into a fixture.

Credentials are always redacted by the one rule of ``xippios.core.redaction``, the rule
``ResultMeta.request`` applies (ADR-0005, ADR-0019): a query parameter that names a
credential (``api_key``, ``token``, ``secret``, ..., and a name a ``QueryKeyAuth``
registered, such as USDA NASS's ``key``), the userinfo and the credential headers.
``scrub_params``, ``scrub_url`` and ``scrub_headers`` are that module's, importable from
here as well. A ``Scrub`` adds what only the source knows: a placeholder for a tenant's
host, the secret values themselves, and a rewrite for pre-authenticated URLs.
"""

import base64
import json
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from xippios.core.redaction import REDACTED, scrub_headers, scrub_params, scrub_url

__all__ = ["REDACTED", "Scrub", "scrub_headers", "scrub_params", "scrub_url"]

_HOST_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")
_BINARY_BODY = "binary body cannot be scrubbed; pass allow_binary=True to store it base64, flagged"


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
            differs, plain or percent-encoded. A placeholder that is the request's own
            host is refused with ``ValueError`` when the exchange is scrubbed; one that
            ends with it (``demo.example.test`` for ``example.test``) is allowed.
            ``None`` keeps the host, for a public upstream.
        secrets: Values that must never be written, e.g. a key or a tenant name. Each
            becomes ``REDACTED`` wherever it appears in URL, headers and bodies, plain
            or percent-encoded (either hex case, ``+`` for a space; ``/`` also as JSON's
            ``\/``), the longest value first, in the letter case given. An empty
            value is refused with ``ValueError``, and so is a ``host`` that contains
            one of them in any letter case: the placeholder would write it into every
            URL. Left out of the ``repr``.
        rewrite: A text hook applied after ``host`` and ``secrets`` to the request body,
            the response body and every response header value (``Location`` and
            ``Content-Location`` included), for pre-authenticated URLs the source knows
            how to neutralise, such as a signed storage URL. Not applied to the request
            URL.
        allow_binary: Store a body that is not UTF-8 text base64 and flagged instead of
            raising ``ValueError``. Nothing in it is scrubbed.
    """

    host: str | None = None
    secrets: Sequence[str] = field(default=(), repr=False)
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
        if self.host is not None and any(value.lower() in self.host.lower() for value in secrets):
            # Neither the value nor the host is named: the host holds the value.
            raise ValueError(
                "host contains one of the secrets, and the placeholder would write it into "
                "every recorded URL; choose a placeholder without it"
            )
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
        forms: set[str] = set()
        if scrub.host is not None:
            forms = {form for form in (url.host, url.raw_host.decode("ascii")) if form}
            if scrub.host.lower() in {form.lower() for form in forms}:
                raise ValueError(
                    "Scrub.host is the request's own host, which would be written as it is; "
                    "give a placeholder that differs from it"
                )
            if forms:
                longest_first = sorted(forms, key=len, reverse=True)
                self._host = re.compile(
                    "|".join(_plain_or_encoded(form) for form in longest_first), re.IGNORECASE
                )
        self._secrets = [
            re.compile(_plain_or_encoded(value))
            for value in sorted(scrub.secrets, key=len, reverse=True)
        ]
        # The longest text one of the patterns can match: each character percent-encoded
        # as up to four bytes, %XX each.
        values = [*scrub.secrets, *(forms if self._host is not None else ())]
        self._reach = 12 * max((len(value) for value in values), default=0)

    def spared_end(self, text: str, end: int) -> int:
        """``end`` moved back to the start of a host or secret occurrence it would split.

        A cut keeping ``text[:end]`` would otherwise keep the first part of one, which
        neither the scrub nor the verify recognises (``max_bytes=``). Occurrences are
        those the scrub replaces: the original host, in any letter case, and each secret
        value, plain or percent-encoded.
        """
        patterns = [pattern for pattern in (self._host, *self._secrets) if pattern is not None]
        split = True
        while split and end > 0:
            split = False
            window = max(0, end - self._reach), end + self._reach
            for pattern in patterns:
                for match in pattern.finditer(text, *window):
                    if match.start() < end < match.end():
                        end, split = match.start(), True
                        break
                if split:
                    break
        return end

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
        """The URL with credentials redacted, the placeholder host, secrets redacted.

        The text is scrubbed in one pass first and the placeholder set as the host
        after it, so a placeholder that contains the original host is not replaced again.
        """
        text = self.text(scrub_url(url))
        if self._scrub.host is None:
            return text
        return str(httpx.URL(text).copy_with(host=self._scrub.host))

    def headers(self, items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        """Headers with credentials redacted, names scrubbed, values scrubbed and rewritten."""
        return [(self.text(name), self.rewritten(value)) for name, value in scrub_headers(items)]

    def verify(
        self,
        url: str,
        request_headers: Iterable[tuple[str, str]],
        request_body: str | None,
        response_headers: Iterable[tuple[str, str]],
        response_body: str | None,
    ) -> None:
        r"""Refuse a scrubbed exchange that still holds the original host or a secret value.

        Runs on what the scrub produced, before anything is kept or written, when the
        ``Scrub`` sets ``host`` or ``secrets``. The URL, every header name and value and
        both bodies are searched raw with the scrub's own patterns (the host in any letter
        case, each value plain or percent-encoded); a body that is JSON is searched
        decoded as well, every key and string in it, so a value the scrub could not see
        behind a ``\uXXXX`` escape is found. The placeholder host and ``REDACTED`` are
        masked first and never count. A body stored base64 (``allow_binary``) is not
        searched: it is kept unscrubbed by design.

        Args:
            url: The scrubbed request URL.
            request_headers: The request headers kept, e.g. ``[("content-type", ...)]``.
            request_body: The scrubbed request body; ``None`` without one or when base64.
            response_headers: The scrubbed response headers.
            response_body: The scrubbed response body; ``None`` when base64.

        Raises:
            ValueError: The original host ("request host") or a secret value ("secret
                value") is still present; the message names the kind and the location
                (``url``, a header by name, ``request body``, ``response body``), never
                the value.
        """
        __tracebackhide__ = True  # pytest would print the arguments: the refused text
        if self._host is None and not self._secrets:
            return
        places: list[tuple[str, list[str]]] = [("url", [url])]
        for side, headers in (("request", request_headers), ("response", response_headers)):
            for name, value in headers:
                # The name is checked before it appears in a location of its own.
                places.append((f"name of a {side} header", [name]))
                places.append((f"{side} header {name!r}", [value]))
        for location, body in (("request body", request_body), ("response body", response_body)):
            if body is not None:
                places.append((location, [body, *_json_strings(body)]))
        for location, texts in places:
            kind = self._left_in(texts)
            if kind is not None:
                raise ValueError(
                    f"the scrubbed fixture still holds the {kind} in the {location}; "
                    "it is refused before anything is written"
                )

    def _left_in(self, texts: Iterable[str]) -> str | None:
        """``"request host"`` or ``"secret value"`` when one survives in ``texts``."""
        __tracebackhide__ = True
        for text in texts:
            masked = text.replace(REDACTED, "\0")
            if self._scrub.host is not None:
                masked = re.sub(re.escape(self._scrub.host), "\0", masked, flags=re.IGNORECASE)
            if self._host is not None and self._host.search(masked):
                return "request host"
            if any(pattern.search(masked) for pattern in self._secrets):
                return "secret value"
        return None

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


def _json_strings(body: str) -> Iterator[str]:
    """Every key and string of ``body`` decoded as JSON; nothing when it is not JSON."""
    try:
        decoded = json.loads(body)
    except ValueError:
        return iter(())
    return _strings(decoded)


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for name, value in node.items():
            yield str(name)
            yield from _strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _strings(item)
