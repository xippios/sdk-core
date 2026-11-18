"""A background event loop so synchronous callers can run the async core (ADR-0002).

One daemon thread owns one event loop for the whole process. Sync facades submit
coroutines to it and block until they finish, which works from plain scripts, from
Jupyter, and from inside another running loop. Nothing here is public API except
through ``xippios.core.sync``.

Not fork-safe: a process forked after the loop thread started (``multiprocessing`` with
the ``fork`` start method) inherits a loop whose thread does not exist. Use the
``spawn`` start method, or fork before the first sync call.
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


def _serve(loop: asyncio.AbstractEventLoop) -> None:
    """Run ``loop`` until it is stopped, whatever a task raises.

    asyncio lets a ``SystemExit`` or a ``KeyboardInterrupt`` that a task raises out of
    ``run_forever``, its task already done with it. Ending the thread there would leave
    the callback that hands the result to the waiting caller unrun, and every later call
    waiting on a loop no thread runs (https://github.com/xippios/sdk-core/issues/77).
    Running the loop again runs that callback: the caller gets the exception, and the
    loop serves the next call.
    """
    while True:
        try:
            loop.run_forever()
        except (SystemExit, KeyboardInterrupt):
            continue
        return


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
                    target=_serve, args=(loop,), name=_LOOP_THREAD_NAME, daemon=True
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
    """Run ``coro`` to completion on the background loop and return its result.

    What ``coro`` raises is raised here, ``SystemExit`` and ``KeyboardInterrupt``
    included, and the loop serves the next call.
    """
    return _runner.run(coro)


def sync[**P, T](fn: Callable[P, Coroutine[Any, Any, T]]) -> SyncFunction[P, T]:
    """Derive a synchronous function from an async one.

    The result has the same signature and docstring, runs the coroutine on the
    background loop, and exposes the original as ``.async_fn`` so adapters can
    await it natively instead of blocking their own loop. A trailing ``_async`` is
    dropped from the name, so ``get_series = sync(get_series_async)`` is named
    ``get_series`` wherever the name is shown, such as in MCP tool names. What the
    coroutine raises reaches the caller, a ``SystemExit`` too, so a script may exit
    from inside a task with its status. The loop is not fork-safe; see the module
    docstring.

    Args:
        fn: An ``async def`` function, or a callable that returns a coroutine and has
            a ``__name__``: a ``functools.partial`` has none until
            ``functools.update_wrapper(partial, function)`` gives it the function's.

    Raises:
        TypeError: ``fn`` has no ``__name__``, which the derived function is named
            after.
    """
    name = getattr(fn, "__name__", None)
    if not isinstance(name, str):
        raise TypeError(
            f"sync() names the function it derives after fn, and {fn!r} has no __name__: "
            "name it with functools.update_wrapper(partial, function) or wrap it in an "
            "async def"
        )
    qualname = getattr(fn, "__qualname__", None)
    if not isinstance(qualname, str):
        qualname = name

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return run(fn(*args, **kwargs))

    wrapper.__name__ = name.removesuffix("_async")
    wrapper.__qualname__ = qualname.removesuffix("_async")
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
