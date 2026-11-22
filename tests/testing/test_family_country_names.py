"""The family check of the names of a task's country codes (ADR-0056, conventions §4).

A task with a parameter whose name holds ``country``, ``area``, ``reporter`` or ``partner`` is
named by ``names_codes`` for it, or stands in ``UNNAMED_CODES`` of its tasks module with the
reason, and the check fails at once a task that is neither, and an entry that is stale
(https://github.com/xippios/sdk-core/issues/359, part 4). The tasks below take every form the
six sources' parameters take; the check reads the module that a test sets up, as the tenant
check's tests do.
"""

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from xippios.core.testing import family
from xippios.core.testing.family import FamilySource

FORMS = '''
from collections.abc import Sequence

from xippios.core import PackagedList, Result, ResultMeta, names_codes, sync

COUNTRIES = PackagedList.model_validate(
    {
        "param": "countries",
        "endpoint": "lists",
        "fetched": "2026-10-23T09:00:00Z",
        "records": [{"countryCode": "CN", "countryName": "Comoros"}],
    }
).codes("countryCode", "countryName")
META = ResultMeta(source="example", endpoint="e")


@names_codes(country_code=COUNTRIES)
async def get_data_async(country_code: str | None = None, year: int = 2024) -> Result[int]:
    """Get data, the async function named."""
    return Result[int](data=year, meta=META)


async def get_flows_async(reporter: str, partner: str) -> Result[int]:
    """Get flows, the sync facade named."""
    return Result[int](data=0, meta=META)


async def get_series_async(area: str, area_cs: str | None = None) -> Result[int]:
    """Get a series under a coding system that no packaged list names."""
    return Result[int](data=0, meta=META)


@names_codes(reporter_code=COUNTRIES, separator=",")
@names_codes(partner2_code=COUNTRIES)
def get_stacked(reporter_code: str, partner2_code: str) -> Result[int]:
    """Get data, named by two decorators."""
    return Result[int](data=0, meta=META)


def get_trade(reporters: Sequence[str], partner2_code: str | None = None) -> Result[int]:
    """Get trade, named by nothing."""
    return Result[int](data=0, meta=META)


def get_plain(
    year: int,
    region_code: str | None = None,
    state: str | None = None,
    market_year: int = 2024,
    geo_level: str | None = None,
    statement_id: int = 0,
    county: str | None = None,
) -> Result[int]:
    """Get data by parameters that hold none of the words."""
    return Result[int](data=0, meta=META)


def download_trade(partners: Sequence[str]) -> Result[int]:
    """Download trade, a bulk task named by nothing."""
    return Result[int](data=0, meta=META)


get_data = sync(get_data_async)
get_flows = names_codes(reporter=COUNTRIES, partner=COUNTRIES)(sync(get_flows_async))
get_series = sync(get_series_async)
BULK_TASKS = frozenset({"download_trade"})
UNNAMED_CODES = {
    "get_series": {
        "area": "Under area_cs it is an ISO3 or M49 code, which no packaged list names.",
        "area_cs": "The coding system of area, no code.",
    }
}
'''

WRITE_FORMS = '''
from xippios.core import Result, ResultMeta

META = ResultMeta(source="example", endpoint="e")


def create_order(partner_code: str, confirm: bool = False) -> Result[int]:
    """Create an order for a partner."""
    return Result[int](data=0, meta=META)


def delete_order(order_id: int, confirm: bool = False) -> Result[int]:
    """Delete an order."""
    return Result[int](data=0, meta=META)
'''

NAMED = ["get_data", "get_flows", "get_series", "get_stacked", "get_plain"]
"""The tasks that pass: named, exempt, or holding none of the words."""

INTRO = (
    "every task parameter whose name holds country, area, reporter or partner is named in the "
    "answer's meta by names_codes, or stands in UNNAMED_CODES of its tasks module with the "
    "reason it is not (conventions §4, ADR-0056):"
)


def module(name: str, text: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A tasks module made from ``text``, its functions' ``__module__`` its own name."""
    made = ModuleType(name)
    monkeypatch.setitem(sys.modules, made.__name__, made)
    exec(text, made.__dict__)
    return made


@pytest.fixture
def forms(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The tasks module of every form, its ``__all__`` set per test."""
    return module("xippios.example_names.tasks", FORMS, monkeypatch)


def check(tasks: ModuleType, names: list[str], tasks_write: ModuleType | None = None) -> None:
    """Run the check on ``tasks`` with ``__all__`` set to ``names``."""
    tasks.__all__ = names  # type: ignore[attr-defined]
    package = ModuleType("xippios.example_names")
    package.__file__ = "/nowhere/__init__.py"
    source = FamilySource(
        root=Path("/nowhere"),
        import_path="xippios.example_names",
        package=package,
        source="example",
        tasks=tasks,
        tasks_write=tasks_write,
    )
    family.test_family_country_codes_are_named_in_the_answer(source)


def problems(
    tasks: ModuleType, names: list[str], tasks_write: ModuleType | None = None
) -> list[str]:
    """The lines the check fails with, after its introduction."""
    with pytest.raises(pytest.fail.Exception) as failed:
        check(tasks, names, tasks_write)
    lines = str(failed.value).splitlines()
    assert lines[0] == INTRO
    return lines[1:]


def test_a_task_named_exempt_or_taking_no_country_passes(forms: ModuleType) -> None:
    check(forms, NAMED)


def test_a_parameter_neither_named_nor_exempt_fails_naming_the_task_and_each_parameter(
    forms: ModuleType,
) -> None:
    assert problems(forms, [*NAMED, "get_trade"]) == [
        "- tasks.get_trade takes reporters, which names_codes does not name and UNNAMED_CODES "
        "does not exempt",
        "- tasks.get_trade takes partner2_code, which names_codes does not name and "
        "UNNAMED_CODES does not exempt",
    ]


def test_a_bulk_task_is_held_as_every_task_is(forms: ModuleType) -> None:
    assert problems(forms, [*NAMED, "download_trade"]) == [
        "- tasks.download_trade takes partners, which names_codes does not name and "
        "UNNAMED_CODES does not exempt",
    ]


@pytest.mark.parametrize(
    "parameter",
    [
        "country_code",
        "countries",
        "area",
        "areas",
        "area_cs",
        "reporter",
        "reporters",
        "reporter_code",
        "reporterCode",
        "partner",
        "partners",
        "partner_code",
        "partner2_code",
        "COUNTRY",
    ],
)
def test_the_words_catch_every_form_the_sources_name_a_country_by(
    forms: ModuleType, parameter: str
) -> None:
    exec(
        f"def get_one({parameter}: str) -> Result[int]:\n"
        '    """Get one."""\n'
        "    return Result[int](data=0, meta=META)\n",
        forms.__dict__,
    )
    assert problems(forms, ["get_one", "get_series"]) == [
        f"- tasks.get_one takes {parameter}, which names_codes does not name and UNNAMED_CODES "
        "does not exempt"
    ]


def test_a_parameter_both_named_and_exempt_fails(forms: ModuleType) -> None:
    forms.UNNAMED_CODES = {  # type: ignore[attr-defined]
        **forms.UNNAMED_CODES,
        "get_data": {"country_code": "A reason that the decoration contradicts."},
    }
    assert problems(forms, NAMED) == [
        "- tasks.get_data: country_code is named by names_codes and exempt in UNNAMED_CODES; "
        "keep one"
    ]


@pytest.mark.parametrize(
    ("unnamed", "problem"),
    [
        (
            {"get_old": {"area": "Gone."}},
            "UNNAMED_CODES of xippios.example_names.tasks names get_old, not in its __all__",
        ),
        (
            {"get_plain": {"area": "No such parameter."}},
            "UNNAMED_CODES of xippios.example_names.tasks: get_plain takes no area",
        ),
        (
            {"get_plain": {"region_code": "A group of countries."}},
            "UNNAMED_CODES of xippios.example_names.tasks: get_plain's region_code holds none of "
            "the words, so the check holds it to nothing",
        ),
        (
            {"get_plain": "Every parameter."},
            "UNNAMED_CODES of xippios.example_names.tasks: get_plain is a str, not a mapping of "
            "its parameters to their reasons",
        ),
        (
            {"get_trade": {"reporters": " ", "partner2_code": None}},
            "UNNAMED_CODES of xippios.example_names.tasks: get_trade's reporters gives no reason, "
            "a text that says why its codes are not named",
        ),
    ],
)
def test_a_stale_entry_or_one_without_its_reason_fails_naming_it(
    forms: ModuleType, unnamed: dict[str, Any], problem: str
) -> None:
    forms.UNNAMED_CODES = {**forms.UNNAMED_CODES, **unnamed}  # type: ignore[attr-defined]
    found = problems(forms, [*NAMED, "get_trade"] if "get_trade" in unnamed else NAMED)
    assert f"- {problem}" in found
    assert all("get_series" not in line for line in found), "the rest of the entry stands"


def test_a_declaration_that_is_no_mapping_fails(forms: ModuleType) -> None:
    forms.UNNAMED_CODES = ["get_series"]  # type: ignore[attr-defined]
    assert problems(forms, ["get_data", "get_plain"]) == [
        "- UNNAMED_CODES of xippios.example_names.tasks is a list, not a mapping of tasks to "
        "their parameters and reasons"
    ]


def test_a_write_task_is_held_with_the_declaration_of_its_own_module(
    forms: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    write = module("xippios.example_names.tasks_write", WRITE_FORMS, monkeypatch)
    write.__all__ = ["create_order", "delete_order"]  # type: ignore[attr-defined]
    assert problems(forms, NAMED, write) == [
        "- tasks_write.create_order takes partner_code, which names_codes does not name and "
        "UNNAMED_CODES does not exempt"
    ]
    write.UNNAMED_CODES = {  # type: ignore[attr-defined]
        "create_order": {"partner_code": "A trading partner of the ledger, no country."}
    }
    check(forms, NAMED, write)
