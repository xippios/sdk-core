"""Remove credentials and named secret values from what gets written into a fixture.

Credentials are always redacted by the one rule of ``xippios.core.redaction``, the rule
``ResultMeta.request`` applies (ADR-0030, ADR-0040): a query parameter that names a
credential (``api_key``, ``token``, ``secret``, ..., and a name a ``QueryKeyAuth``
registered, such as USDA NASS's ``key``), the userinfo and the credential headers. A
``token`` name the source declared data with ``register_data_name``, X's ``next_token``
say, is written as sent, and replay can match it.
``scrub_params``, ``scrub_url`` and ``scrub_headers`` are that module's, importable from
here as well. A ``Scrub`` adds what only the source knows: the secret values themselves,
named before the request or read from its answer, such as a login's tokens. What a
source rewrites beyond them, a tenant's host or a field by key, it rewrites in its own
step on the ``Fixture``, which the recorder runs after the scrub and checks before the
write (``rewrite=``; ADR-0048, decisions 1 and 2).
"""

import base64
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from xippios.core.redaction import REDACTED, scrub_headers, scrub_params, scrub_url

__all__ = ["REDACTED", "Scrub", "scrub_headers", "scrub_params", "scrub_url"]

_BINARY_BODY = (
    "a binary body cannot be scrubbed; the recording is refused unless "
    "Scrub(allow_binary=True) stores it base64, flagged"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Scrub:
    """What a recording must not keep besides credentials, removed before anything is written.

    ``fixture_from_response`` and ``record`` apply it in memory to the whole fixture
    (request URL, request body, response headers, response body), and the file is written
    once, already scrubbed, so the file never holds what was removed, not even briefly
    (conventions §10). The credential scrubbing of ``scrub_url`` and ``scrub_headers``
    always applies as well. No scrub reads a binary body: a request or response body
    that is not UTF-8 text is refused with ``ValueError`` unless ``allow_binary`` is
    set, and is then stored base64, unscrubbed, flagged with ``body_base64``.

    Attributes:
        secrets: Values that must never be written, e.g. a key or a tenant name. Each
            becomes ``REDACTED`` wherever it appears as given, in the URL, the headers
            and the bodies, the longest value first, in the letter case given; an
            encoded form (percent-encoded, behind a JSON escape) is not looked for. An
            empty value is refused with ``ValueError``. Left out of the ``repr``.
        response_secrets: A function that reads the values that must never be written
            from the answer, for a value known only once upstream sends it, such as a
            login's or a refresh's tokens, which name no credential (``AccessToken``),
            e.g. ``lambda response: [response.json()["AccessToken"]]``. It is called
            once per recording with the whole response, an error answer included, before
            any cut, and each value it returns is scrubbed and verified as ``secrets``
            are (ADR-0042, decision 3). An answer that carries none gives
            ``[]``. ``None`` reads nothing.
        allow_binary: Store a body that is not UTF-8 text base64 and flagged instead of
            raising ``ValueError``. Nothing in it is scrubbed.

    Raises:
        TypeError: ``secrets`` is one string, or ``response_secrets`` cannot be called.
        ValueError: ``secrets`` holds an empty value.
    """

    secrets: Sequence[str] = field(default=(), repr=False)
    response_secrets: Callable[[httpx.Response], Iterable[str]] | None = None
    allow_binary: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.secrets, str):
            raise TypeError("secrets is a sequence of values, e.g. [value], not one string")
        secrets = tuple(self.secrets)
        if any(not value for value in secrets):
            raise ValueError("secrets must not contain an empty string")
        object.__setattr__(self, "secrets", secrets)
        if self.response_secrets is not None and not callable(self.response_secrets):
            raise TypeError(
                "response_secrets is a function of the response that returns the values, "
                "e.g. lambda response: [response.json()['token']]"
            )


def _read_secrets(scrub: Scrub, response: httpx.Response) -> tuple[str, ...]:
    """``scrub.secrets`` and the values ``scrub.response_secrets`` reads from ``response``.

    Raises:
        TypeError: The function returned one string, or a value that is no string.
        ValueError: It returned an empty value. No message names a value.
    """
    named = tuple(scrub.secrets)  # a tuple already: __post_init__ made it one
    if scrub.response_secrets is None:
        return named
    read: Any = scrub.response_secrets(response)  # checked below, whatever it returned
    if isinstance(read, str):
        raise TypeError(
            "response_secrets returns a sequence of values, e.g. [token], not one string"
        )
    values: tuple[str, ...] = tuple(read)
    if any(not isinstance(value, str) for value in values):
        raise TypeError("response_secrets returns text values; one it returned is no string")
    if any(not value for value in values):
        raise ValueError("response_secrets returned an empty value, which cannot be scrubbed")
    return named + values


class _Scrubber:
    """A ``Scrub`` applied to one exchange: the secret values as patterns, longest first.

    The values are the ``Scrub``'s own and those its ``response_secrets`` reads from
    ``response``.
    """

    def __init__(self, scrub: Scrub, response: httpx.Response) -> None:
        self._scrub = scrub
        secrets = _read_secrets(scrub, response)
        longest_first = sorted(secrets, key=len, reverse=True)
        self._secrets = [re.compile(re.escape(value)) for value in longest_first]
        self._reach = max((len(value) for value in secrets), default=0)

    def spared_end(self, text: str, end: int) -> int:
        """``end`` moved back to the start of a secret value it would split.

        A cut keeping ``text[:end]`` would otherwise keep the first part of one, which
        neither the scrub nor the verify recognises (``max_bytes=``).
        """
        split = True
        while split and end > 0:
            split = False
            window = max(0, end - self._reach), end + self._reach
            for pattern in self._secrets:
                for match in pattern.finditer(text, *window):
                    if match.start() < end < match.end():
                        end, split = match.start(), True
                        break
                if split:
                    break
        return end

    def text(self, text: str) -> str:
        """``text`` with every secret value, as given, made ``REDACTED``, the longest first."""
        for pattern in self._secrets:
            text = pattern.sub(lambda _: REDACTED, text)
        return text

    def url(self, url: httpx.URL) -> str:
        """The URL with credentials redacted, then secret values."""
        return self.text(scrub_url(url))

    def headers(self, items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        """Headers with credentials redacted, then secret values in names and values."""
        return [(self.text(name), self.text(value)) for name, value in scrub_headers(items)]

    def verify(
        self,
        url: str,
        request_headers: Iterable[tuple[str, str]],
        request_body: str | None,
        response_headers: Iterable[tuple[str, str]],
        response_body: str | None,
    ) -> None:
        """Refuse a scrubbed exchange that still holds a secret value.

        Runs on what the scrub produced, before anything is kept or written, when the
        ``Scrub`` names secrets: the URL, every header value and both bodies are
        searched for each value as given, a plain substring in the letter case given;
        ``REDACTED`` is masked first and never counts. A backstop (ADR-0030): an encoded
        form is not looked for, and a body stored base64 (``allow_binary``) is not
        searched, since it is kept unscrubbed by design.

        Args:
            url: The scrubbed request URL.
            request_headers: The request headers kept, e.g. ``[("content-type", ...)]``.
            request_body: The scrubbed request body; ``None`` without one or when base64.
            response_headers: The scrubbed response headers.
            response_body: The scrubbed response body; ``None`` when base64.

        Raises:
            ValueError: A secret value is still present; the message names the location
                (``request URL``, a header by name, ``request body``, ``response body``),
                never the value.
        """
        __tracebackhide__ = True  # pytest would print the arguments: the refused text
        if not self._secrets:
            return
        places = [("request URL", url)]
        for side, headers in (("request", request_headers), ("response", response_headers)):
            places += [(f"{side} header {name!r}", value) for name, value in headers]
        for location, body in (("request body", request_body), ("response body", response_body)):
            if body is not None:
                places.append((location, body))
        for location, text in places:
            masked = text.replace(REDACTED, "\0")
            if any(pattern.search(masked) for pattern in self._secrets):
                raise ValueError(
                    f"the scrubbed fixture still holds a secret value in the {location}; "
                    "it is refused before anything is written"
                )

    def body(self, content: bytes) -> tuple[str, bool]:
        """``(text, False)`` scrubbed, or ``(base64, True)`` when allowed.

        Raises:
            ValueError: ``content`` is not UTF-8 text and ``allow_binary`` is not set.
        """
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            if not self._scrub.allow_binary:
                raise ValueError(_BINARY_BODY) from None
            return base64.b64encode(content).decode("ascii"), True
        return self.text(text), False
