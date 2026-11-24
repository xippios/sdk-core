"""Response cache hooks: a backend protocol and an in-memory LRU with a lifetime per path (§6)."""

import hashlib
import math
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Protocol

import httpx

__all__ = [
    "WIRE_HEADERS",
    "CacheBackend",
    "CachedResponse",
    "MemoryCache",
    "cache_key",
    "strip_wire_headers",
]

WIRE_HEADERS = frozenset({"content-length", "content-encoding", "transfer-encoding", "connection"})
"""Headers that describe how a body travelled, not the body itself.

``httpx`` hands out the decoded body, so a stored copy (a cache entry, a fixture) that
kept them would claim an encoding and a length the stored bytes no longer have.
"""


def strip_wire_headers(items: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The ``(name, value)`` pairs of ``items`` minus ``WIRE_HEADERS``, in any letter case."""
    return [(name, value) for name, value in items if name.lower() not in WIRE_HEADERS]


@dataclass(frozen=True, slots=True)
class CachedResponse:
    """What a backend stores: enough to rebuild an ``httpx.Response``.

    Attributes:
        status: HTTP status code.
        headers: Response headers as ``(name, value)`` pairs, without ``WIRE_HEADERS``.
        content: Body bytes as decoded by ``httpx`` (gzip and the like already undone).
        stored_at: Epoch seconds when the entry was stored.
    """

    status: int
    headers: tuple[tuple[str, str], ...]
    content: bytes
    stored_at: float


class CacheBackend(Protocol):
    """Pluggable storage for GET responses, keyed by ``cache_key``.

    The key is a digest that names no path, so the client hands ``set`` the request's
    path, from which the backend takes how long it keeps the answer, if at all.
    Implementations must be safe to call from several threads and event loops.
    """

    def get(self, key: str) -> CachedResponse | None:
        """Return the entry for ``key`` or ``None`` when absent or expired."""
        ...

    def set(self, key: str, value: CachedResponse, *, path: str) -> None:
        """Store ``value`` under ``key`` for as long as the backend keeps ``path``."""
        ...


def cache_key(method: str, url: httpx.URL) -> str:
    """A stable key for method, URL and sorted query parameters.

    The key is a SHA-256 hex digest so that query strings carrying an API key never
    appear verbatim in a backend such as a file or a shared store.
    """
    query = "&".join(f"{name}={value}" for name, value in sorted(url.params.multi_items()))
    text = f"{method.upper()} {url.copy_with(query=None)} {query}"
    return hashlib.sha256(text.encode()).hexdigest()


_CACHES: "weakref.WeakSet[MemoryCache]" = weakref.WeakSet()
"""Every live ``MemoryCache``, for the testing plugin's clearing between tests (ADR-0035)."""
_CACHES_LOCK = threading.Lock()


def _clear_every_cache() -> None:
    """Drop every live ``MemoryCache``'s entries; the testing plugin calls it around each test."""
    with _CACHES_LOCK:
        caches = list(_CACHES)
    for cache in caches:
        cache.clear()


_DEFAULT_LIFETIMES: Final[Mapping[str, float | None]] = MappingProxyType({"/": 300.0})
"""Every path for 300 seconds: what ``MemoryCache()`` keeps without a mapping of its own."""


@dataclass(frozen=True, slots=True)
class _Entry:
    """A stored answer and when it expires, in epoch seconds; ``None`` never."""

    value: CachedResponse
    expires_at: float | None


class MemoryCache:
    """In-memory LRU cache with a lifetime per path prefix, shareable across threads and loops.

    ``lifetimes`` maps a path prefix to the seconds an answer under it is kept. A prefix is
    matched against the path of the request's URL, the base URL's own path included, and
    the longest prefix that the path starts with wins: ``None`` keeps an answer for the
    life of the process, ``0`` stores nothing, and a path that no prefix matches is not
    stored at all, so no GET to it is answered from the cache::

        MemoryCache(lifetimes={"/v1/regions": 86400.0, "/v1/files/": None})

    keeps the regions of ``example`` for a day and its files for as long as the process
    runs, and caches no other path. An entry is dropped once its lifetime, counted from
    its ``stored_at``, has passed, at the next ``get`` or ``set`` of any key. The cache
    holds at most ``maxsize`` entries and ``max_bytes`` bytes of bodies in all and evicts
    the least recently used entry first; a body larger than ``max_bytes`` is not stored.

    The testing plugin clears every instance before and after each test not marked
    ``live`` (ADR-0035).

    Args:
        lifetimes: Seconds an answer is kept, by path prefix, e.g. ``{"/v1/regions":
            3600.0}``; each prefix starts with ``/``. By default every path for 300
            seconds, ``{"/": 300.0}``.
        maxsize: Maximum number of entries.
        max_bytes: Maximum bytes of the bodies held in all; 64 MiB by default, eight
            answers at the default of ``ClientConfig.cache_max_bytes``.
        clock: Time source in epoch seconds, replaceable in tests.

    Attributes:
        lifetimes: As given, read-only.
        maxsize: As given.
        max_bytes: As given.

    Raises:
        ValueError: A prefix that does not start with ``/``, a lifetime that is negative,
            infinite or NaN, or a ``maxsize`` or ``max_bytes`` below 1.
    """

    def __init__(
        self,
        *,
        lifetimes: Mapping[str, float | None] = _DEFAULT_LIFETIMES,
        maxsize: int = 256,
        max_bytes: int = 64 * 1024 * 1024,
        clock: Callable[[], float] = time.time,
    ) -> None:
        for prefix, lifetime in lifetimes.items():
            if not prefix.startswith("/"):
                raise ValueError(f"a path prefix starts with /, not {prefix!r}")
            if lifetime is not None and not (math.isfinite(lifetime) and lifetime >= 0):
                raise ValueError(
                    f"the lifetime of {prefix!r} is a number of seconds, 0 or more, or None "
                    f"for the life of the process, not {lifetime!r}"
                )
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        if max_bytes < 1:
            raise ValueError("max_bytes must be at least 1")
        self.lifetimes: Mapping[str, float | None] = MappingProxyType(dict(lifetimes))
        self.maxsize = maxsize
        self.max_bytes = max_bytes
        self._longest_first = sorted(self.lifetimes, key=len, reverse=True)
        self._clock = clock
        self._items: OrderedDict[str, _Entry] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        with _CACHES_LOCK:
            _CACHES.add(self)

    def _lifetime(self, path: str) -> float | None:
        """The lifetime of the longest prefix that ``path`` starts with; ``0`` for none.

        Args:
            path: A request URL's path, e.g. ``"/v1/regions"``.
        """
        for prefix in self._longest_first:
            if path.startswith(prefix):
                return self.lifetimes[prefix]
        return 0.0

    def get(self, key: str) -> CachedResponse | None:
        """Return a live entry for ``key``, once every expired entry is dropped."""
        with self._lock:
            self._drop_expired()
            entry = self._items.get(key)
            if entry is None:
                return None
            self._items.move_to_end(key)
            return entry.value

    def set(self, key: str, value: CachedResponse, *, path: str) -> None:
        """Store ``value`` for the lifetime of ``path``, evicting beyond either bound.

        The least recently used entries go first, until at most ``maxsize`` entries and
        ``max_bytes`` bytes are held. A path of lifetime ``0``, or a body larger than
        ``max_bytes``, stores nothing and drops an earlier entry under ``key``.

        Args:
            key: The request's ``cache_key``.
            value: The answer to keep.
            path: The path of the request's URL, e.g. ``"/v1/regions"``.
        """
        lifetime = self._lifetime(path)
        with self._lock:
            self._drop(key)
            self._drop_expired()
            size = len(value.content)
            if lifetime == 0 or size > self.max_bytes:
                return
            expires_at = None if lifetime is None else value.stored_at + lifetime
            self._items[key] = _Entry(value, expires_at)
            self._bytes += size
            while len(self._items) > self.maxsize or self._bytes > self.max_bytes:
                _, evicted = self._items.popitem(last=False)
                self._bytes -= len(evicted.value.content)

    def clear(self) -> None:
        """Drop every entry."""
        with self._lock:
            self._items.clear()
            self._bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def _drop(self, key: str) -> None:
        """Drop the entry under ``key``, if there is one; the caller holds the lock."""
        entry = self._items.pop(key, None)
        if entry is not None:
            self._bytes -= len(entry.value.content)

    def _drop_expired(self) -> None:
        """Drop every entry whose lifetime has passed; the caller holds the lock."""
        now = self._clock()
        expired = [
            key
            for key, entry in self._items.items()
            if entry.expires_at is not None and now > entry.expires_at
        ]
        for key in expired:
            self._drop(key)
