"""The nightly comparison of a source's packaged lists with the lists upstream serves now.

A source collects it in ``tests/test_live.py`` with one line, beside the declaration of its
packaged lists, as ``tests/test_family.py`` collects the family check (ADR-0055)::

    from xippios.core.testing.live import *  # noqa: F403

    LIVE_LISTS = {  # each packaged list compared, by its file reference/<name>.json
        "regions": (REGIONS, api.get_regions),
    }
    NO_LIVE_LIST = {  # each packaged list not compared, with the reason
        "series": "A fetch takes 101 requests; test_list_series_live counts it.",
    }

The star import puts ``test_packaged_list_is_current`` and this module's
``pytest_generate_tests`` into that module, which runs the test once per entry of its
``LIVE_LISTS``, ``test_packaged_list_is_current[regions]``, at collection, wherever the
module declares it. The test is marked ``live``, so an offline run collects it and sends
nothing. The family check (``xippios.core.testing.family``) reads the same declaration
from the file and fails a source whose package holds a packaged list in neither, or an
entry that names no packaged list.

**An entry of** ``LIVE_LISTS`` is a pair: the ``PackagedCodes`` that the list is declared as
(``PackagedList.codes``, ADR-0045), whose ``code`` is the field the records are compared by,
and the function that fetches the list now. The function takes no argument and returns the
list, or an awaitable of it, which the test runs on core's loop as ``sync`` runs a task:
records under upstream's field names, as mappings or ``UpstreamModel`` instances, compared
whole by their code, or bare codes, text or integers, compared by code alone. It may return
the list in an ``api/`` wrapper's ``Answer``, read by its ``payload``, so a wrapper that takes
no argument is a fetch as it stands.

**An entry of** ``NO_LIVE_LIST`` is the reason the list is not compared: a list that no
endpoint serves, say, or one that a test of the source's own compares through
``assert_list_current``, the assertion underneath.

A code gone from upstream's list, a code new in it and a code whose record changed fail the
run, and the failure names the codes and never a record, since the log of a public
repository is public (conventions §10).
"""

import inspect
import json
from collections.abc import Awaitable, Callable, Iterable, Mapping
from enum import Enum
from typing import Any, TypeGuard, cast

import pytest
from pydantic_core import to_jsonable_python

from xippios.core._loop import run
from xippios.core.client import Answer
from xippios.core.models import UpstreamModel
from xippios.core.reference import PackagedCodes

__all__ = ["pytest_generate_tests", "test_packaged_list_is_current"]

_LIVE = "LIVE_LISTS"
"""The declaration of the lists compared, by its name in ``tests/test_live.py``."""
_NO_LIVE = "NO_LIVE_LIST"
"""The declaration of the lists not compared, each with its reason."""
_NO_PAIR = f"{_LIVE} holds no pair of its PackagedCodes and the function that fetches it now"
_SHOWN = 20
"""How many codes of each kind a failure names, in the list's order, before it counts the rest."""

type _Code = str | int
type _Item = Mapping[str, Any] | UpstreamModel | str | int


def _is_entry(entry: object) -> TypeGuard[tuple[PackagedCodes, Callable[[], Any]]]:
    """Whether ``entry`` is an entry of ``LIVE_LISTS``: a ``PackagedCodes`` and a function."""
    return (
        isinstance(entry, tuple)
        and len(entry) == 2
        and isinstance(entry[0], PackagedCodes)
        and callable(entry[1])
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Run ``test_packaged_list_is_current`` once per entry of its module's ``LIVE_LISTS``.

    pytest calls the hook for every test of the module that star-imports it, at collection;
    it parametrizes this module's test alone, by the names the declaration gives its lists.
    A module whose ``LIVE_LISTS`` names none, or that has none, gets an empty set, which
    pytest skips.
    """
    if metafunc.function is not test_packaged_list_is_current:
        return
    declared = getattr(metafunc.module, _LIVE, {})
    names = [str(name) for name in declared] if isinstance(declared, Mapping) else []
    metafunc.parametrize("live_list", names)


async def _awaited(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


@pytest.mark.live
def test_packaged_list_is_current(live_list: str, request: pytest.FixtureRequest) -> None:
    """The packaged list ``live_list`` is the list upstream serves now (conventions §10).

    Its entry of ``LIVE_LISTS`` fetches the list, or a wrapper's ``Answer`` of it, and
    ``assert_list_current`` compares it with the packaged records by the declared code: a
    code gone, new or changed fails the test,
    naming the codes and never a record (ADR-0055).
    """
    entry = getattr(request.module, _LIVE)[live_list]
    if not _is_entry(entry):
        pytest.fail(f"{live_list}: {_NO_PAIR}", pytrace=False)
    codes, fetch = entry
    current = fetch()
    if inspect.isawaitable(current):
        current = run(_awaited(current))
    assert_list_current(codes, current)


class _Unreadable(Exception):
    """A side of the comparison that holds neither records nor codes, as ``_read`` says."""


def _listed(current: Iterable[_Item] | Answer[Iterable[_Item]]) -> Iterable[object]:
    """The list ``current`` holds: an ``Answer``'s ``payload``, else ``current`` itself.

    Raises:
        _Unreadable: An ``Answer`` whose payload is no list, the body that holds the records
            say; the message names the payload's type, never a value.
    """
    if not isinstance(current, Answer):
        return current
    payload = cast(object, current.payload)  # a wrapper's answer that mypy does not check
    if isinstance(payload, str | bytes | Mapping) or not isinstance(payload, Iterable):
        raise _Unreadable(
            f"the list upstream serves now is an Answer of {_a(type(payload).__name__)}: an "
            "Answer's payload is the list, so hand the records, not the body that holds them"
        )
    return payload


def _is_code(value: object) -> TypeGuard[_Code]:
    return isinstance(value, str | int) and not isinstance(value, bool)


def _a(kind: str) -> str:
    return f"{'an' if kind[:1] in 'aeiou' else 'a'} {kind}"


def _read(items: Iterable[object], field: str, side: str) -> tuple[dict[_Code, list[str]], bool]:
    """Each code of ``items`` to its records as JSON texts, and whether they are bare codes.

    The codes stand in the list's order. A record is a mapping under upstream's field names,
    or an ``UpstreamModel`` read through ``dump_upstream``; it is read as the JSON that a
    packaged file holds, its fields sorted, and keyed by its field ``field``. A bare code is
    text or an integer, an enum member read by its value, and has no record.

    Raises:
        _Unreadable: An item is neither, a record lacks ``field`` or holds no code there, or
            the list holds both; the message names the side and the position, never a value.
    """
    by_code: dict[_Code, list[str]] = {}
    bare: set[bool] = set()
    for position, item in enumerate(items):
        value = item.value if isinstance(item, Enum) else item
        if isinstance(value, UpstreamModel):
            value = value.dump_upstream()
        if isinstance(value, Mapping):
            record = to_jsonable_python(dict(value))
            if field not in record:
                raise _Unreadable(f"{side}: record {position} has no field {field!r}")
            code = record[field]
            if not _is_code(code):
                raise _Unreadable(
                    f"{side}: record {position}: field {field!r} is neither text nor an integer"
                )
            text = json.dumps(record, sort_keys=True, ensure_ascii=False)
            by_code.setdefault(code, []).append(text)
            bare.add(False)
        elif _is_code(value):
            by_code.setdefault(value, [])
            bare.add(True)
        else:
            kind = _a(type(value).__name__)
            raise _Unreadable(f"{side}: item {position} is {kind}, neither a record nor a code")
    if len(bare) > 1:
        raise _Unreadable(f"{side} mixes records and bare codes")
    return by_code, bare == {True}


def _shown(codes: list[_Code]) -> str:
    """The first ``_SHOWN`` codes, each as ``repr`` writes it, and how many more."""
    shown = ", ".join(repr(code) for code in codes[:_SHOWN])
    return f"{shown} and {len(codes) - _SHOWN} more" if len(codes) > _SHOWN else shown


def assert_list_current(
    codes: PackagedCodes,
    current: Iterable[_Item] | Answer[Iterable[_Item]],
    *,
    packaged: Iterable[_Item] | None = None,
) -> None:
    """Fail the test unless ``current`` is the packaged list that ``codes`` declares.

    The nightly comparison of a packaged list with the list upstream serves now (conventions
    §10, ADR-0055), which ``test_packaged_list_is_current`` runs for each entry of a source's
    ``LIVE_LISTS``, and a source whose fetch is its own, a session's fixture say, calls
    itself. The records are compared by the declared code, ``codes.code``, each as the JSON
    that the packaged file holds, in any order of the list and of its fields; a code listed
    twice compares its records together, and a side of bare codes compares codes alone.

    A code gone from ``current``, a code new in it and a code whose record changed fail the
    test. The failure names the list, its fetch date, the counts and the codes of each kind,
    the first 20 in the list's order and how many more, as ``repr`` writes them, so ``'104'``
    reads apart from ``104``, and never a record's other fields. It shows no frame and no
    local value of the test, whatever ``--tb`` or ``--showlocals`` the run takes, since the
    log of a public repository is public.

    Args:
        codes: The list's declaration, ``PackagedList.codes(...)``: its ``code`` is the field
            the records are compared by, and its list's records the packaged side.
        current: The list upstream serves now: its records under upstream's field names, as
            mappings or ``UpstreamModel`` instances, read through ``dump_upstream``, or its
            bare codes, text or integers; or an ``api/`` wrapper's ``Answer`` whose
            ``payload`` is that list, read as the list is. An ``Answer`` of anything else,
            the body that holds the records say, fails the test naming the payload's type.
        packaged: The packaged side, read as ``current`` is read, for a list whose records
            name the release they came from, as records that carry a ``report_month`` do:
            ``codes.packaged.records`` as the source views them; those records by default.

    Raises:
        TypeError: ``codes`` is no ``PackagedCodes``.
    """
    if not isinstance(codes, PackagedCodes):
        raise TypeError(
            f"codes is {_a(type(codes).__name__)}; pass the list's PackagedList.codes(...)"
        )
    side = codes.packaged.records if packaged is None else packaged
    try:
        before, packaged_bare = _read(side, codes.code, "the packaged list")
        served = _listed(current)
        after, current_bare = _read(served, codes.code, "the list upstream serves now")
    except _Unreadable as unreadable:
        pytest.fail(f"packaged list {codes.list_name}: {unreadable} (ADR-0055)", pytrace=False)
    by_code_alone = packaged_bare or current_bare
    gone = [code for code in before if code not in after]
    new = [code for code in after if code not in before]
    changed = [
        code
        for code in before
        if code in after and not by_code_alone and sorted(before[code]) != sorted(after[code])
    ]
    if not (gone or new or changed):
        return
    lines = [
        f"packaged list {codes.list_name} (fetched {codes.packaged.fetched:%Y-%m-%d}) differs "
        f"from the list upstream serves now: {len(gone)} gone, {len(new)} new, {len(changed)} "
        f"changed of {len(before)} packaged codes, {len(after)} served; refresh it "
        "(conventions §10, ADR-0055):"
    ]
    kinds = (("gone", gone), ("new", new), ("changed", changed))
    lines += [f"- {kind}: {_shown(found)}" for kind, found in kinds if found]
    pytest.fail("\n".join(lines), pytrace=False)
