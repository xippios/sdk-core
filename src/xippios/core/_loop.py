"""A background event loop so synchronous callers can run the async core (ADR-0002).

One daemon thread owns one event loop for the whole process. Sync facades submit
coroutines to it and block until they finish, which works from plain scripts, from
Jupyter, and from inside another running loop. Nothing here is public API except
through ``xippios.core.sync``.
"""

import asyncio
import functools
import inspect
import threading
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Protocol, cast

__all__ = ["SyncFunction", "as_async", "run", "sync"]

_LOOP_THREAD_NAME = "xippios-core-loop"


class SyncFunction[**P, T](Protocol):
    """A synchronous function derived by ``sync`` from an async one."""

    __name__: str
    __qualname__: str
    __doc__: str | None
    __wrapped__: Callable[P, Coroutine[Any, Any, T]]
    async_fn: Callable[P, Coroutine[Any, Any, T]]

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T: ...


class _Runner:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None or self._loop.is_closed():
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name=_LOOP_THREAD_NAME, daemon=True
                )
                thread.start()
                self._loop, self._thread = loop, thread
            return self._loop

    def run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        loop = self.loop()
        if threading.current_thread() is self._thread:
            coro.close()
            raise RuntimeError(
                "a sync facade was called from inside the xippios event loop; "
                "await the async function instead"
            )
        return asyncio.run_coroutine_threadsafe(coro, loop).result()


_runner = _Runner()


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` to completion on the background loop and return its result."""
    return _runner.run(coro)


def sync[**P, T](fn: Callable[P, Coroutine[Any, Any, T]]) -> SyncFunction[P, T]:
    """Derive a synchronous function from an async one.

    The result has the same signature and docstring, runs the coroutine on the
    background loop, and exposes the original as ``.async_fn`` so adapters can
    await it natively instead of blocking their own loop.

    Args:
        fn: An ``async def`` function.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return run(fn(*args, **kwargs))

    wrapper.async_fn = fn  # type: ignore[attr-defined]
    return cast(SyncFunction[P, T], wrapper)


def as_async(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
    """Return an awaitable form of ``fn`` for use inside an adapter's event loop.

    Prefers the ``async_fn`` twin set by ``sync``; returns ``fn`` itself when it is
    already a coroutine function; otherwise wraps a plain function in a worker thread.
    """
    twin = getattr(fn, "async_fn", None)
    if twin is not None and inspect.iscoroutinefunction(twin):
        return cast(Callable[..., Awaitable[Any]], twin)
    if inspect.iscoroutinefunction(fn):
        return cast(Callable[..., Awaitable[Any]], fn)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)

    return wrapper
