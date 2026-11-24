from typing import Any

import httpx
import pytest

from xippios.core.client import CachedResponse, ClientConfig, MemoryCache, cache_key
from xippios.core.client.cache import DEFAULT_LIFETIMES, WIRE_HEADERS, strip_wire_headers


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


def test_an_entry_expires_once_its_lifetime_has_passed() -> None:
    clock = Clock()
    cache = MemoryCache(lifetimes={"/v1/": 60}, clock=clock)
    cache.set("k", entry(clock), lifetime=60)
    clock.now += 59
    assert cache.get("k") is not None
    clock.now += 2
    assert cache.get("k") is None
    assert len(cache) == 0


def test_no_lifetime_keeps_an_entry_for_the_life_of_the_process() -> None:
    clock = Clock()
    cache = MemoryCache(lifetimes={"/v1/files/": None}, clock=clock)
    cache.set("k", entry(clock), lifetime=None)
    clock.now += 10_000_000
    assert cache.get("k") is not None


def test_lru_eviction_prefers_recently_used() -> None:
    clock = Clock()
    cache = MemoryCache(maxsize=2, clock=clock)
    cache.set("a", entry(clock, b"a"), lifetime=300)
    cache.set("b", entry(clock, b"b"), lifetime=300)
    assert cache.get("a") is not None  # touch a, so b is the oldest
    cache.set("c", entry(clock, b"c"), lifetime=300)
    assert cache.get("b") is None
    assert cache.get("a") is not None
    assert cache.get("c") is not None


def test_clear() -> None:
    clock = Clock()
    cache = MemoryCache(clock=clock)
    cache.set("k", entry(clock), lifetime=300)
    cache.clear()
    assert len(cache) == 0
    assert cache.size == 0


# -- a lifetime per path prefix (https://github.com/xippios/sdk-core/issues/479, part 1) ----


def test_the_longest_prefix_gives_a_path_its_lifetime() -> None:
    cache = MemoryCache(
        lifetimes={"/v1/": 300.0, "/v1/regions": 86400.0, "/v1/files/": None, "/v1/live/": 0}
    )
    assert cache.lifetime("/v1/regions") == 86400.0
    assert cache.lifetime("/v1/regions/7") == 86400.0, "a prefix, not a whole path"
    assert cache.lifetime("/v1/series") == 300.0
    assert cache.lifetime("/v1/files/a.csv") is None
    assert cache.lifetime("/v1/live/now") == 0
    assert cache.lifetime("/v2/regions") == 0, "a path no prefix matches is not cached"


def test_the_default_keeps_every_path_for_300_seconds() -> None:
    cache = MemoryCache()
    assert dict(cache.lifetimes) == dict(DEFAULT_LIFETIMES) == {"/": 300.0}
    assert cache.lifetime("/v1/anything") == 300.0
    with pytest.raises(TypeError):
        cache.lifetimes["/v1/"] = 1.0  # type: ignore[index]


def test_a_lifetime_of_zero_stores_nothing_and_drops_the_entry_it_replaces() -> None:
    clock = Clock()
    cache = MemoryCache(clock=clock)
    cache.set("k", entry(clock), lifetime=300)
    cache.set("k", entry(clock), lifetime=0)
    assert cache.get("k") is None
    assert (len(cache), cache.size) == (0, 0)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"lifetimes": {"v1/": 60.0}}, "^a path prefix starts with /, not 'v1/'$"),
        ({"lifetimes": {"/v1/": -1.0}}, "^the lifetime of '/v1/' is a number of seconds"),
        ({"lifetimes": {"/v1/": float("nan")}}, "^the lifetime of '/v1/' is a number"),
        ({"lifetimes": {"/v1/": float("inf")}}, "^the lifetime of '/v1/' is a number"),
        ({"maxsize": 0}, "^maxsize must be at least 1$"),
        ({"max_bytes": 0}, "^max_bytes must be at least 1$"),
    ],
    ids=["relative-prefix", "negative", "nan", "infinite", "no-entries", "no-bytes"],
)
def test_a_bad_lifetime_or_bound_is_refused(arguments: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MemoryCache(**arguments)


# -- expired entries leave and the bytes are bounded (the same answer, part 4) -------------


def test_an_expired_entry_is_dropped_at_the_next_call_whatever_its_key() -> None:
    # Before, an expired entry stayed until its own key was asked for again.
    clock = Clock()
    cache = MemoryCache(clock=clock)
    cache.set("old", entry(clock, b"o" * 10), lifetime=60)
    cache.set("kept", entry(clock, b"k" * 5), lifetime=None)
    clock.now += 61
    cache.set("new", entry(clock, b"n" * 3), lifetime=60)
    assert (len(cache), cache.size) == (2, 8)
    clock.now += 61
    assert cache.get("kept") is not None
    assert (len(cache), cache.size) == (1, 5)


def test_the_bytes_held_in_all_are_bounded_and_the_oldest_used_leave_first() -> None:
    clock = Clock()
    cache = MemoryCache(max_bytes=10, clock=clock)
    cache.set("a", entry(clock, b"a" * 4), lifetime=300)
    cache.set("b", entry(clock, b"b" * 4), lifetime=300)
    assert cache.get("a") is not None  # touch a, so b is the oldest used
    cache.set("c", entry(clock, b"c" * 4), lifetime=300)
    assert cache.get("b") is None
    assert cache.get("a") is not None
    assert cache.get("c") is not None
    assert cache.size == 8
    cache.set("a", entry(clock, b"a" * 6), lifetime=300)  # replaced: its old bytes leave
    assert cache.size == 10


def test_a_body_over_the_byte_bound_is_not_stored() -> None:
    clock = Clock()
    cache = MemoryCache(max_bytes=10, clock=clock)
    cache.set("a", entry(clock, b"a" * 4), lifetime=300)
    cache.set("big", entry(clock, b"x" * 11), lifetime=300)
    assert cache.get("big") is None
    assert (len(cache), cache.size) == (1, 4), "nothing was evicted for it"


def test_the_bound_by_default_holds_eight_answers_at_the_client_s_bound() -> None:
    cache = MemoryCache()
    config = ClientConfig(source="example", version="1", base_url="https://api.example.org")
    assert cache.max_bytes == 64 * 1024 * 1024 == 8 * config.cache_max_bytes
    assert cache.maxsize == 256


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
