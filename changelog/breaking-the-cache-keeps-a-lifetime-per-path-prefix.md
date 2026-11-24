- `MemoryCache(lifetimes=...)` keeps an answer for the seconds of the longest path prefix
  that its request's URL path starts with, `None` for the life of the process and `0` for
  nothing stored, and a path that no prefix matches is never stored. It takes the place of
  `ttl=` and of `ClientConfig.cache_filter`, which leave, and `MemoryCache()` keeps every
  path for 300 s. The cache drops an entry once its lifetime has passed and holds at most
  `max_bytes=` of bodies in all, 64 MiB by default, and a backend's `set` takes the request's
  `path=`, from which it reads the lifetime.
  (ADR-0040, §6, https://github.com/xippios/sdk-core/issues/479)
  - Hand-apply: `src/xippios/comtrade/_client.py` (sdk-comtrade) — at `:191-214`,
    `_reference_file` and `cache_filter=_reference_file` leave, and `MemoryCache(ttl=None,
    maxsize=64)` becomes `MemoryCache(lifetimes={_REFERENCE_FILES: None}, maxsize=64)`,
    the docstring at `:6` with it — `ClientConfig` takes no `cache_filter`, and until it
    stands every test fails at the import of `_client.py`.
    `tests/test_tasks.py` (sdk-comtrade) — at `:1505-1509`, the test asserts
    `config.cache.lifetimes == {"/files/v1/app/reference/": None}` in place of calling
    `config.cache_filter` — it fails at `cache_filter`.
    `src/xippios/usda/gats/_client.py` (sdk-usda-gats) — at `:125-144` and `:166-256`,
    `PathCaches`, its three `MemoryCache`s and `cache_filter` leave for one
    `MemoryCache(lifetimes=...)` that gives the four release-date paths and
    `COMMODITIES_PATH` their lifetimes, `RELEASE_DATES_TTL`, `UN_RELEASE_DATES_TTL` and
    `COMMODITIES_TTL`, and `ClientConfig` loses `cache_filter=` at `:275-287`, while
    `__all__` loses `PathCaches` and `cache_filter` at `:307` and `:310` — the cache of a
    path is the cache's own now, and until it stands every test fails at the import of
    `_client.py`.
    `tests/test_client.py` (sdk-usda-gats) — at `:54-64`, `:354-445`, `:447-466` and
    `:546-576`, the tests of `PathCaches`, `by_path`, `cache_filter`, `.ttl`, `.maxsize` and
    the three caches assert `config.cache.lifetimes` for the five named paths and that the
    data paths are never stored, and read the one `cache` where they read a cache of their
    own — they fail at the import of `PathCaches`.
    `tests/test_lists.py` (sdk-usda-gats) — at `:35`, the import of `commodities_cache`
    leaves with the three caches, and `cache` stays — the module fails at the import.
    `src/xippios/usda/nass/_client.py` (sdk-usda-nass) — at `:39-42` and `:78-95`,
    `_list_lookup` and `cache_filter=_list_lookup` leave, and `MemoryCache(ttl=_LIST_TTL)`
    becomes `MemoryCache(lifetimes={_LIST_PATH: _LIST_TTL})` — `ClientConfig` takes no
    `cache_filter`, and until it stands every test fails at the import of `_client.py`.
    `tests/test_tasks.py` (sdk-usda-nass) — at `:458`, `config.cache.ttl == 24 * 60 * 60`
    becomes `config.cache.lifetimes == {"/api/get_param_values/": 24 * 60 * 60}` — the
    test fails at `ttl`.
