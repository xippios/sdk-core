"""The family check of the names of a record's codes (ADR-0067, decision 8; conventions §4).

The check reads the model's declaration and no word of a parameter's name: each field that
``NamedBy`` marks holds codes and is marked once, and the field it names as the one in which
upstream sends the name stands in the same model and holds text, so a code and its label stand
side by side (ADR-0060, decision 7). The tasks below return the invented source's records in
the forms a task returns them; the check reads the module that a test sets up, as the tenant
check's tests do.
"""

import sys
from pathlib import Path
from types import ModuleType

import pytest

from xippios.core.testing import family
from xippios.core.testing.family import FamilySource

FORMS = '''
from collections.abc import Sequence
from typing import Annotated

from pydantic import BaseModel, Field

from xippios.core import NamedBy, PackagedList, Result, ResultMeta, UpstreamModel, sync

REGIONS = PackagedList.model_validate(
    {
        "param": "regions",
        "endpoint": "lists",
        "fetched": "2026-10-23T09:00:00Z",
        "records": [{"regionCode": "R1", "regionName": "North"}],
    }
).codes("regionCode", "regionName")
META = ResultMeta(source="example", endpoint="e")


class Row(UpstreamModel):
    region_code: Annotated[str | None, NamedBy(REGIONS)] = Field(validation_alias="regionCode")
    item_code: Annotated[int, NamedBy("item")] = Field(validation_alias="itemCode")
    item: str
    unit_ids: Annotated[list[int], NamedBy("unit")] = []
    unit: str | None = None


class Report(BaseModel):
    rows: list[Row]


async def get_rows_async(area: str, area_cs: str | None = None) -> Result[list[Row]]:
    """Get rows under a coding system: no word of a parameter's name is read."""
    return Result[list[Row]](data=[], meta=META)


def get_report(country_code: str) -> Result[Report]:
    """Get a report that holds the rows."""
    return Result[Report](data=Report(rows=[]), meta=META)


def download_rows(partners: Sequence[str]) -> Result[list[Row]]:
    """Download the rows, a bulk task."""
    return Result[list[Row]](data=[], meta=META)


get_rows = sync(get_rows_async)
BULK_TASKS = frozenset({"download_rows"})
'''

WRONG = '''

class Wrong(UpstreamModel):
    region_code: Annotated[str, NamedBy(REGIONS), NamedBy("region")]
    item_code: Annotated[int, NamedBy("label")]
    unit_code: Annotated[int, NamedBy("unit")]
    unit: int
    row: Annotated[Row, NamedBy(REGIONS)]
    region: str


def get_wrong() -> Result[Wrong]:
    """Get a record whose marks cannot name."""
    raise NotImplementedError
'''

WRITE = '''
from typing import Annotated

from xippios.core import NamedBy, Result, ResultMeta, UpstreamModel


class Order(UpstreamModel):
    partner_code: Annotated[str, NamedBy("partner")]
    partner: int


def create_order(partner_code: str, confirm: bool = False) -> Result[Order]:
    """Create an order for a partner."""
    raise NotImplementedError
'''

PASSING = ["get_rows", "get_report", "download_rows"]
"""The tasks whose records are marked as the check holds."""

INTRO = (
    "a field that NamedBy marks holds codes and is marked once, and the field it names as the "
    "one that holds the name stands in the same model and holds text (conventions §4, "
    "ADR-0067, decision 8):"
)


def module(name: str, text: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A tasks module made from ``text``, its functions' ``__module__`` its own name."""
    made = ModuleType(name)
    monkeypatch.setitem(sys.modules, made.__name__, made)
    exec(text, made.__dict__)
    return made


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
    family.test_family_code_names_are_declared_on_the_model(source)


def problems(
    tasks: ModuleType, names: list[str], tasks_write: ModuleType | None = None
) -> list[str]:
    """The lines the check fails with, after its introduction."""
    with pytest.raises(pytest.fail.Exception) as failed:
        check(tasks, names, tasks_write)
    lines = str(failed.value).splitlines()
    assert lines[0] == INTRO
    return lines[1:]


def test_marked_records_pass_whatever_the_parameters_are_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # area, area_cs, country_code and partners took the five words of the check that this one
    # replaces; it reads none of them (ADR-0067, decision 8).
    check(module("xippios.example_names.tasks", FORMS, monkeypatch), PASSING)


def test_each_mark_that_cannot_name_fails_naming_its_model_and_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = module("xippios.example_names.tasks", FORMS + WRONG, monkeypatch)
    assert problems(tasks, [*PASSING, "get_wrong"]) == [
        "- Wrong.region_code is marked by NamedBy twice; keep one",
        "- Wrong.item_code is named by label, which is no other field of the model",
        "- Wrong.unit_code is named by unit, which holds int, not text",
        "- Wrong.row holds Row, no code: NamedBy marks a field of text or integer codes, one or a "
        "list of them",
    ]


def test_a_write_task_s_record_is_held_too(monkeypatch: pytest.MonkeyPatch) -> None:
    tasks = module("xippios.example_names.tasks", FORMS, monkeypatch)
    write = module("xippios.example_names.tasks_write", WRITE, monkeypatch)
    write.__all__ = ["create_order"]  # type: ignore[attr-defined]
    assert problems(tasks, PASSING, write) == [
        "- Order.partner_code is named by partner, which holds int, not text"
    ]
