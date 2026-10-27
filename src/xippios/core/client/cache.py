"""Response cache hooks: a backend protocol and an in-memory LRU with TTL (conventions §6)."""

import hashlib
import threading
import time
import weakref
from collections import OrderedDict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

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

    Implementations must be safe to call from several threads and event loops.
    """

    def get(self, key: str) -> CachedResponse | None:
        """Return the entry for ``key`` or ``None`` when absent or expired."""
        ...

    def set(self, key: str, value: CachedResponse) -> None:
        """Store ``value`` under ``key``."""
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
"""Every live ``MemoryCache``, for the testing plugin's clearing between tests (ADR-0013)."""
_CACHES_LOCK = threading.Lock()


def _clear_every_cache() -> None:
    """Drop every live ``MemoryCache``'s entries; the testing plugin calls it around each test."""
    with _CACHES_LOCK:
        caches = list(_CACHES)
    for cache in caches:
        cache.clear()


class MemoryCache:
    """In-memory LRU cache with a TTL, shareable across threads and event loops.

    The testing plugin clears every instance before and after each test not marked
    ``live`` (ADR-0013).

    Args:
        ttl: Seconds an entry stays valid; ``None`` keeps entries until evicted.
        maxsize: Maximum number of entries; the least recently used is evicted first.
        clock: Time source in epoch seconds, replaceable in tests.
    """

    def __init__(
        self,
        *,
        ttl: float | None = 300.0,
        maxsize: int = 256,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.ttl = ttl
        self.maxsize = maxsize
        self._clock = clock
        self._items: OrderedDict[str, CachedResponse] = OrderedDict()
        self._lock = threading.Lock()
        with _CACHES_LOCK:
            _CACHES.add(self)

    def get(self, key: str) -> CachedResponse | None:
        """Return a live entry for ``key``, dropping it when its TTL has passed."""
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if self.ttl is not None and self._clock() - entry.stored_at > self.ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return entry

    def set(self, key: str, value: CachedResponse) -> None:
        """Store ``value``, evicting least recently used entries beyond ``maxsize``."""
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

    def clear(self) -> None:
        """Drop every entry."""
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
