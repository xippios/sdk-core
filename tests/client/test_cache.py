import httpx

from xippios.core.client import (
    WIRE_HEADERS,
    CachedResponse,
    MemoryCache,
    cache_key,
    strip_wire_headers,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def entry(clock: Clock, body: bytes = b"x") -> CachedResponse:
    return CachedResponse(status=200, headers=(), content=body, stored_at=clock())


def test_key_ignores_parameter_order_and_hides_values() -> None:
    a = cache_key("GET", httpx.URL("https://h.test/p?b=2&key=SECRET&a=1"))
    b = cache_key("get", httpx.URL("https://h.test/p?a=1&key=SECRET&b=2"))
    assert a == b
    assert "SECRET" not in a
    assert len(a) == 64
    assert cache_key("GET", httpx.URL("https://h.test/p?a=1")) != a
    assert cache_key("POST", httpx.URL("https://h.test/p?b=2&key=SECRET&a=1")) != a


def test_ttl_expiry() -> None:
    clock = Clock()
    cache = MemoryCache(ttl=60, clock=clock)
    cache.set("k", entry(clock))
    clock.now += 59
    assert cache.get("k") is not None
    clock.now += 2
    assert cache.get("k") is None
    assert len(cache) == 0


def test_no_ttl_keeps_entries() -> None:
    clock = Clock()
    cache = MemoryCache(ttl=None, clock=clock)
    cache.set("k", entry(clock))
    clock.now += 10_000_000
    assert cache.get("k") is not None


def test_lru_eviction_prefers_recently_used() -> None:
    clock = Clock()
    cache = MemoryCache(maxsize=2, clock=clock)
    cache.set("a", entry(clock, b"a"))
    cache.set("b", entry(clock, b"b"))
    assert cache.get("a") is not None  # touch a, so b is the oldest
    cache.set("c", entry(clock, b"c"))
    assert cache.get("b") is None
    assert cache.get("a") is not None
    assert cache.get("c") is not None


def test_clear() -> None:
    clock = Clock()
    cache = MemoryCache(clock=clock)
    cache.set("k", entry(clock))
    cache.clear()
    assert len(cache) == 0


def test_strip_wire_headers_ignores_case_and_keeps_order() -> None:
    wire = {"content-length", "content-encoding", "transfer-encoding", "connection"}
    assert wire == WIRE_HEADERS
    items = [
        ("Content-Type", "application/json"),
        ("Content-Encoding", "gzip"),
        ("x-ratelimit-remaining", "9"),
        ("CONTENT-LENGTH", "42"),
        ("Transfer-Encoding", "chunked"),
        ("Connection", "keep-alive"),
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
    ]
    assert strip_wire_headers(items) == [
        ("Content-Type", "application/json"),
        ("x-ratelimit-remaining", "9"),
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
    ]
    assert strip_wire_headers(iter(())) == []
