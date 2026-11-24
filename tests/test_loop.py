import asyncio
import functools
import inspect
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable, Coroutine, Iterator
from typing import Any

import pytest

from xippios.core import _loop
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


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> Iterator[_loop._Runner]:
    """A background loop of this test's own, behind ``run`` and every ``sync`` facade.

    A test that takes the loop down takes this one, never the process's, which every
    other test shares.
    """
    fresh = _loop._Runner()
    monkeypatch.setattr(_loop, "_runner", fresh)
    yield fresh
    loop = fresh._loop
    if loop is not None:
        loop.call_soon_threadsafe(loop.stop)


def call_within(fn: Callable[[], object], seconds: float = 5.0) -> BaseException | object:
    """What ``fn()`` returned or raised, from a thread of its own, within ``seconds``.

    A call that hangs fails the test instead of the run: its thread is left waiting.
    """
    outcome: list[object] = []

    def target() -> None:
        try:
            outcome.append(fn())
        except BaseException as exc:
            outcome.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    assert not thread.is_alive(), f"no answer within {seconds} s: the call hangs"
    return outcome[0]


async def exits_async() -> None:
    raise SystemExit(3)


async def interrupts_async() -> None:
    raise KeyboardInterrupt


async def awaits_a_task_that_exits_async() -> None:
    await asyncio.gather(asyncio.sleep(0), exits_async())


@pytest.mark.parametrize(
    ("coroutine_function", "raised"),
    [
        (exits_async, SystemExit),
        (interrupts_async, KeyboardInterrupt),
        (awaits_a_task_that_exits_async, SystemExit),
    ],
    ids=["system-exit", "keyboard-interrupt", "system-exit-in-a-task-it-awaits"],
)
def test_a_sync_task_hands_system_exit_to_its_caller_and_the_loop_lives_on(
    runner: _loop._Runner,
    coroutine_function: Callable[[], Coroutine[Any, Any, None]],
    raised: type[BaseException],
) -> None:
    """https://github.com/xippios/sdk-core/issues/77: asyncio lets these two out of the
    loop, which ended its thread and left the caller waiting for ever."""
    facade = sync(coroutine_function)
    first = call_within(facade)
    assert type(first) is raised
    if isinstance(first, SystemExit):
        assert first.code == 3
    assert call_within(lambda: add_sync(2, b=3)) == 5  # the next call is answered
    assert call_within(lambda: add_sync(1)) == 2
    assert runner._thread is not None
    assert runner._thread.is_alive()


def test_a_script_that_exits_inside_a_sync_task_exits_with_its_status() -> None:
    """The case a source met: a script exits from inside a sync task."""
    script = textwrap.dedent(
        """
        from xippios.core import sync

        async def main_async() -> None:
            raise SystemExit(3)

        sync(main_async)()
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, timeout=30, check=False
    )
    assert finished.returncode == 3, finished.stderr.decode(errors="replace")


def test_sync_of_a_callable_without_a_name_says_how_to_name_it() -> None:
    """Part (b) of https://github.com/xippios/sdk-core/issues/46: a partial has no name."""
    unnamed = functools.partial(add, 2)
    with pytest.raises(TypeError) as info:
        sync(unnamed)
    assert str(info.value) == (
        "sync() names the function it derives after fn, and "
        f"{unnamed!r} has no __name__: name it with functools.update_wrapper(partial, "
        "function) or wrap it in an async def"
    )
    named = sync(functools.update_wrapper(functools.partial(add, 2), add))
    assert named.__name__ == "add"
    assert named(b=3) == 5
