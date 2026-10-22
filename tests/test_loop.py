import asyncio
import inspect
import threading

import pytest

from xippios.core._loop import as_async, run, sync


async def add(a: int, b: int = 1) -> int:
    """Add two numbers.

    Args:
        a: First.
        b: Second.
    """
    await asyncio.sleep(0)
    return a + b


add_sync = sync(add)


def test_sync_keeps_signature_and_docstring() -> None:
    assert add_sync(2, b=3) == 5
    assert inspect.signature(add_sync) == inspect.signature(add)
    assert add_sync.__doc__ == add.__doc__
    assert add_sync.__name__ == "add"
    assert add_sync.async_fn is add


def test_sync_strips_async_suffix_from_name() -> None:
    async def get_series_async() -> int:
        return 1

    facade = sync(get_series_async)
    assert facade.__name__ == "get_series"
    assert facade.__qualname__.endswith("get_series")
    assert facade.async_fn.__name__ == "get_series_async"


def test_sync_works_inside_a_running_loop() -> None:
    async def caller() -> int:
        return add_sync(40, 2)

    assert asyncio.run(caller()) == 42


def test_run_from_loop_thread_is_rejected() -> None:
    async def inner() -> None:
        add_sync(1)

    with pytest.raises(RuntimeError, match="inside the xippios event loop"):
        run(inner())


def test_exceptions_propagate() -> None:
    async def fail() -> None:
        raise KeyError("x")

    with pytest.raises(KeyError):
        run(fail())


def test_runs_on_one_background_thread() -> None:
    async def who() -> str:
        return threading.current_thread().name

    assert run(who()) == "xippios-core-loop"
    assert run(who()) == "xippios-core-loop"


@pytest.mark.anyio
async def test_as_async_prefers_twin_then_coroutine_then_thread() -> None:
    assert as_async(add_sync) is add
    assert as_async(add) is add

    def plain(x: int) -> int:
        return x * 2

    wrapped = as_async(plain)
    assert await wrapped(4) == 8
    assert wrapped.__name__ == "plain"
