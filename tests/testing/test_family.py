"""The family check, run by pytester against a source package laid out as the template does."""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from xippios.core.http import router_from_tasks
from xippios.core.mcp import build_server
from xippios.core.testing import family
from xippios.core.testing.family import FamilySource, _cell_tasks, _status_table_tasks

# What building the adapters imports is loaded here, before pytester's in-process runs: a
# module first imported inside one is dropped after it, and imported again by the next,
# cryptography's hash classes (behind the MCP server) no longer match its compiled half.
build_server("warmup", [], read_only=False)
router_from_tasks("warmup", [])

TASKS = '''
from xippios.core import Result, ResultMeta, sync

META = ResultMeta(source="example", endpoint="series")


async def get_series_async(series_id: str, year: int = 2024) -> Result[list[int]]:
    """Fetch one series for a year.

    Args:
        series_id: Upstream identifier, e.g. ``"CORN"``.
        year: Four-digit year, e.g. ``2024``.
    """
    return Result[list[int]](data=[year], meta=META)


async def find_series_async(filters: dict[str, str]) -> Result[list[int]]:
    """Find series by upstream filters.

    Args:
        filters: Upstream filters, e.g. ``{"state": "IA"}``.
    """
    return Result[list[int]](data=[], meta=META)


async def list_regions_async() -> Result[list[str]]:
    """List the regions a series can be asked for."""
    return Result[list[str]](data=[], meta=META)


get_series = sync(get_series_async)
find_series = sync(find_series_async)
list_regions = sync(list_regions_async)

__all__ = ["find_series", "get_series", "list_regions"]
'''

SERVED = "[getattr(tasks, n) for n in tasks.__all__ if n not in getattr(tasks, 'BULK_TASKS', ())]"

README = """# xippios-example

## Install

| Not | the | status |
| --- | --- | --- |
| `not_a_task` | | |

## Status

| Upstream operation | Task function | MCP tool | Status |
| --- | --- | --- | --- |
| `series` | `get_series(series_id, year=2024)` | `example_get_series` | alpha |
| `series`, filtered | `tasks.find_series(filters)`; a `POST` route | `example_find_series` | |
| `regions` | `list_regions()`, packaged as `reference/regions.json`, checks `region` | | |

The tasks above; nothing else in this section is a table.

## Licence

Apache-2.0.
"""

PYPROJECT = """[project]
name = "xippios-example"
version = "0.1.0"
dependencies = ["httpx>=0.28", "xippios-core~=0.2.1"]

[project.optional-dependencies]
mcp = ["xippios-core[mcp]~=0.2.1"]
http = ["xippios-core[http]~=0.2.1"]
testing = ["xippios-core[testing]~=0.2.1", "pytest>=8"]

[tool.pytest.ini_options]
addopts = "-p no:cacheprovider"
"""

SOURCE: dict[str, str] = {
    "src/xippios/example/__init__.py": '__version__ = "0.1.0"\n',
    "src/xippios/example/py.typed": "",
    "src/xippios/example/_client.py": 'SOURCE = "example"\n',
    "src/xippios/example/tasks.py": TASKS,
    "src/xippios/example/mcp.py": (
        "from xippios.core.mcp import build_server\n"
        "from xippios.example import tasks\n"
        "from xippios.example._client import SOURCE\n\n"
        f"server = build_server(SOURCE, {SERVED})\n"
    ),
    "src/xippios/example/http.py": (
        "from xippios.core.http import router_from_tasks\n"
        "from xippios.example import tasks\n"
        "from xippios.example._client import SOURCE\n\n"
        f"router = router_from_tasks(SOURCE, {SERVED})\n"
    ),
    "README.md": README,
    ".copier-answers.yml": (
        "# Changes here will be overwritten by Copier; NEVER EDIT MANUALLY\n"
        "_commit: v0.2.1\n"
        "_src_path: https://github.com/xippios/sdk-template.git\n"
        "core_version: 0.2.1\n"
    ),
    "pyproject.toml": PYPROJECT,
    "tests/conftest.py": 'pytest_plugins = ["xippios.core.testing.plugin"]\n',
    "tests/test_family.py": "from xippios.core.testing.family import *  # noqa: F403\n",
}

FAMILY_TESTS = 11


def run_family(
    pytester: pytest.Pytester, changes: dict[str, str | None] | None = None
) -> pytest.RunResult:
    """Write the source with ``changes`` (path to content; ``None`` deletes) and run it."""
    files = {**SOURCE, **(changes or {})}
    for path, content in files.items():
        if content is None:
            continue
        target = pytester.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    pytester.syspathinsert(pytester.path / "src")
    for name in [m for m in sys.modules if m.split(".")[:2] == ["xippios", "example"]]:
        del sys.modules[name]  # a second run in one test imports the changed files
    importlib.invalidate_caches()
    return pytester.runpytest("tests", "-ra")


def test_a_conforming_source_passes_every_family_check(pytester: pytest.Pytester) -> None:
    result = run_family(pytester)
    result.assert_outcomes(passed=FAMILY_TESTS)


def test_the_package_is_named_by_the_ini_option_when_src_holds_two(
    pytester: pytest.Pytester,
) -> None:
    second: dict[str, str | None] = {"src/xippios/other/tasks.py": "__all__: list[str] = []\n"}
    result = run_family(pytester, second)
    result.assert_outcomes(errors=FAMILY_TESTS)
    result.stdout.fnmatch_lines(
        ["*one package with a tasks.py under src/xippios/, found*example/tasks.py*other/tasks.py*"]
    )
    named = PYPROJECT + 'xippios_package = "xippios.example"\n'
    result = run_family(pytester, {**second, "pyproject.toml": named})
    result.assert_outcomes(passed=FAMILY_TESTS)


def test_an_adapter_that_drops_a_task_fails_naming_it(pytester: pytest.Pytester) -> None:
    dropped = SOURCE["src/xippios/example/mcp.py"].replace(
        SERVED, "[tasks.get_series, tasks.find_series]"
    )
    extra = SOURCE["src/xippios/example/http.py"].replace(
        SERVED, f"{SERVED} + [tasks.get_series_async]"
    )
    result = run_family(
        pytester, {"src/xippios/example/mcp.py": dropped, "src/xippios/example/http.py": extra}
    )
    result.assert_outcomes(passed=FAMILY_TESTS - 2, failed=2)
    result.stdout.fnmatch_lines(
        [
            "*mcp.py must register exactly tasks.__all__ minus BULK_TASKS:*",
            "*- missing tool example_list_regions*",
        ]
    )
    result.stdout.fnmatch_lines(
        [
            "*http.py must route exactly tasks.__all__ minus BULK_TASKS:*",
            "*- route /example/get_series_async serves no task of tasks.__all__ minus BULK_TASKS*",
        ]
    )


def test_a_stale_status_table_fails_naming_both_sides(pytester: pytest.Pytester) -> None:
    stale = README.replace("`list_regions()`", "`list_old_regions()`")
    result = run_family(pytester, {"README.md": stale})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*README.md's status table ('Task function' column) lists exactly the tasks:*",
            "*- list_regions is not in the table*",
            "*- list_old_regions is in the table but is no task*",
        ]
    )
    result = run_family(pytester, {"README.md": "# xippios-example\n\n## Status\n\nSoon.\n"})
    result.stdout.fnmatch_lines(["*README.md has no table with a 'Task function' column*"])


def test_bulk_tasks_stay_off_the_adapters_and_in_the_table(pytester: pytest.Pytester) -> None:
    bulk = TASKS.replace(
        '__all__ = ["find_series", "get_series", "list_regions"]',
        "async def download_series_async(series_id: str) -> Result[list[int]]:\n"
        '    """Download every year of one series.\n\n    Args:\n'
        '        series_id: Upstream identifier, e.g. ``"CORN"``.\n    """\n'
        "    return Result[list[int]](data=[], meta=META)\n\n\n"
        "download_series = sync(download_series_async)\n"
        'BULK_TASKS = frozenset({"download_series"})\n'
        '__all__ = ["download_series", "find_series", "get_series", "list_regions"]',
    )
    table = README.replace(
        "| `regions` |",
        "| `bulk` | `download_series(series_id)` | none: Python only | alpha |\n| `regions` |",
    )
    changes: dict[str, str | None] = {"src/xippios/example/tasks.py": bulk, "README.md": table}
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS)
    # register_tasks and router_from_tasks skip it themselves (ADR-0040, decision 4).
    every = "[getattr(tasks, n) for n in tasks.__all__]"
    adapters = {
        path: SOURCE[path].replace(SERVED, every)
        for path in ("src/xippios/example/mcp.py", "src/xippios/example/http.py")
    }
    result = run_family(pytester, {**changes, **adapters})
    result.assert_outcomes(passed=FAMILY_TESTS)


def test_a_task_without_the_envelope_or_the_docstring_fails(pytester: pytest.Pytester) -> None:
    bad = (
        TASKS.replace(
            "async def list_regions_async() -> Result[list[str]]:\n"
            '    """List the regions a series can be asked for."""\n'
            "    return Result[list[str]](data=[], meta=META)",
            "def list_regions(year: int) -> dict[str, int]:\n"
            '    """List the regions"""\n'
            "    return {}",
        )
        .replace("list_regions = sync(list_regions_async)\n", "")
        .replace("find_series = sync(find_series_async)", "find_series = find_series_async")
    )
    result = run_family(pytester, {"src/xippios/example/tasks.py": bad})
    result.stdout.fnmatch_lines(
        [
            "*task docstrings are written for agents:*",
            "*- tasks.list_regions: the first line is one sentence ending with a full stop*",
            "*- tasks.list_regions: explain every parameter under Args: with valid values*",
        ]
    )
    result.stdout.fnmatch_lines(
        [
            "*every task returns Result[[]T[]]:*",
            "*- tasks.find_series is async; list the sync function sync() derives from it*",
            "*- tasks.list_regions returns dict[[]str, int[]], not Result[[]T[]]*",
        ]
    )


def test_the_answers_tag_and_the_core_bound(pytester: pytest.Pytester) -> None:
    answers = SOURCE[".copier-answers.yml"].replace("v0.2.1", "v0.2.1-3-g1a2b3c4")
    loose = PYPROJECT.replace('"xippios-core~=0.2.1"]', '"xippios-core>=0.2.0"]').replace(
        "xippios-core[http]~=0.2.1", "xippios-core[http]~=0.2.0"
    )
    result = run_family(pytester, {".copier-answers.yml": answers, "pyproject.toml": loose})
    result.assert_outcomes(passed=FAMILY_TESTS - 2, failed=2)
    result.stdout.fnmatch_lines(
        [
            "*_commit is 'v0.2.1-3-g1a2b3c4', not a template tag vX.Y.Z*",
            "*- dependencies: 'xippios-core>=0.2.0' is not bound to one minor with ~=X.Y.Z*",
            "*- core and its extras name different bounds: [[]'0.2.0', '0.2.1'[]]*",
        ]
    )


def _family_at(package_dir: Path) -> FamilySource:
    package = ModuleType("xippios.usda.example")
    package.__file__ = str(package_dir / "__init__.py")
    return FamilySource(
        root=package_dir,
        import_path="xippios.usda.example",
        package=package,
        source="usda-example",
        tasks=ModuleType("xippios.usda.example.tasks"),
        tasks_write=None,
    )


def test_a_filled_namespace_level_fails_naming_it(tmp_path: Path) -> None:
    # A nested source (ADR-0006): an __init__.py in xippios/usda/ would shadow the others.
    package_dir = tmp_path / "src" / "xippios" / "usda" / "example"
    package_dir.mkdir(parents=True)
    family.test_family_namespace_levels_are_empty(_family_at(package_dir))
    (package_dir.parent / "__init__.py").write_text("")
    with pytest.raises(pytest.fail.Exception, match=r"(?s)must stay empty.*usda/__init__\.py"):
        family.test_family_namespace_levels_are_empty(_family_at(package_dir))


def test_a_missing_typing_marker_fails(tmp_path: Path) -> None:
    package_dir = tmp_path / "src" / "xippios" / "usda" / "example"
    package_dir.mkdir(parents=True)
    with pytest.raises(pytest.fail.Exception, match=r"py\.typed is missing"):
        family.test_family_package_ships_py_typed(_family_at(package_dir))
    (package_dir / "py.typed").write_text("")
    family.test_family_package_ships_py_typed(_family_at(package_dir))


WRITE_TASKS = '''
from xippios.core import Result, ResultMeta, sync


async def create_series_async(name: str, confirm: bool = False) -> Result[str]:
    """Create a series, or preview it unless confirmed.

    Args:
        name: The series name, e.g. ``"corn"``.
        confirm: ``True`` writes; ``False`` previews.
    """
    return Result[str](data=name, meta=ResultMeta(source="example", endpoint="create"))


create_series = sync(create_series_async)

__all__ = ["create_series"]
'''


def test_write_tasks_are_checked_and_listed_and_the_write_server_is_not(
    pytester: pytest.Pytester,
) -> None:
    # The write server is its source's to test (ADR-0042); none is written here.
    write: dict[str, str | None] = {"src/xippios/example/tasks_write.py": WRITE_TASKS}
    table = README.replace(
        "| `regions` |",
        "| `create` | `create_series(name, confirm)` | write server | alpha |\n| `regions` |",
    )
    result = run_family(pytester, {**write, "README.md": table})
    result.assert_outcomes(passed=FAMILY_TESTS)
    result = run_family(pytester, write)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(["*- create_series is not in the table*"])


@pytest.mark.parametrize(
    ("cell", "names"),
    [
        ("`get_data(commodity_code, market_year)`", ["get_data"]),
        ("`tasks.get_counts(filters)`", ["get_counts"]),
        ("`list_organisations`", ["list_organisations"]),
        (
            "`create_journal_entry`, `update_journal_entry`, `delete_journal_entry`",
            ["create_journal_entry", "update_journal_entry", "delete_journal_entry"],
        ),
        (
            '`get_census_release_dates("X")`; read by the exports tasks too',
            ["get_census_release_dates"],
        ),
        (
            "`list_countries(region_code=None)`, packaged as `reference/c.json`, checks `code`",
            ["list_countries"],
        ),
        ("", []),
        ("(none yet)", []),
        ("`reference/x.json`", []),
    ],
)
def test_a_task_function_cell_yields_the_names_it_starts_with(cell: str, names: list[str]) -> None:
    # The cells of usda-psd, usda-nass, cashctrl and usda-gats on 2026-10-26.
    assert _cell_tasks(cell) == names


def test_the_status_tables_are_read_under_the_status_heading_only() -> None:
    assert _status_table_tasks(README) == ["get_series", "find_series", "list_regions"]
    template = (
        "## Status\n\n| Upstream operation | Task function | MCP tool | Status |\n"
        "| --- | --- | --- | --- |\n| (none yet) | | | |\n"
    )
    assert _status_table_tasks(template) == []
    assert _status_table_tasks("## Status\n\n| a | b |\n| - | - |\n| `x` | `y` |\n") is None
    assert _status_table_tasks("# Title\n") is None


# One tenant per call (conventions §7; https://github.com/xippios/sdk-core/issues/299) -----

TENANT_CLIENT = """from xippios.core import Tenants

SOURCE = "example"
TENANTS = Tenants(SOURCE, list_var="EXAMPLE_ORGS", fields=("API_KEY",), reserved=("demo",))
"""

TENANT_TASKS = '''
from xippios.core import Result, ResultMeta, list_task, sync
from xippios.example._client import TENANTS


async def get_series_async(org: str, series_id: str, year: int = 2024) -> Result[list[int]]:
    """Fetch one series of an organisation for a year.

    Args:
        org: A declared organisation, e.g. ``demo``.
        series_id: Upstream identifier, e.g. ``"CORN"``.
        year: Four-digit year, e.g. ``2024``.
    """
    meta = ResultMeta(source="example", endpoint="series", tenant=org)
    return Result[list[int]](data=[year], meta=meta)


async def list_regions_async() -> Result[list[str]]:
    """List the regions a series can be asked for, the same for every organisation."""
    return Result[list[str]](data=[], meta=ResultMeta(source="example", endpoint="regions"))


get_series = sync(get_series_async)
list_regions = sync(list_regions_async)
list_organisations = list_task(TENANTS, name="list_organisations")

NO_TENANT_TASKS = frozenset({"list_regions"})
__all__ = ["get_series", "list_organisations", "list_regions"]
'''

TENANT_WRITE_TASKS = '''
from xippios.core import Result, ResultMeta, sync


async def create_series_async(org: str, name: str, confirm: bool = False) -> Result[str]:
    """Create a series, or preview it unless confirmed.

    Args:
        org: A declared organisation, e.g. ``demo``.
        name: The series name, e.g. ``"corn"``.
        confirm: ``True`` writes; ``False`` previews.
    """
    meta = ResultMeta(source="example", endpoint="create", tenant=org)
    return Result[str](data=name, meta=meta)


async def rename_series_async(name: str, confirm: bool = False) -> Result[str]:
    """Rename a series, or preview it unless confirmed.

    Args:
        name: The series name, e.g. ``"corn"``.
        confirm: ``True`` writes; ``False`` previews.
    """
    return Result[str](data=name, meta=ResultMeta(source="example", endpoint="rename"))


create_series = sync(create_series_async)
rename_series = sync(rename_series_async)

__all__ = ["create_series", "rename_series"]
'''

TENANT_README = """# xippios-example

## Status

| Upstream operation | Task function | MCP tool | Status |
| --- | --- | --- | --- |
| `series` | `get_series(org, series_id, year=2024)` | `example_get_series` | alpha |
| none | `list_organisations()` | `example_list_organisations` | alpha |
| `regions` | `list_regions()` | `example_list_regions` | alpha |
| `create`, `rename` | `create_series`, `rename_series` | write server | alpha |
"""

TENANT_SOURCE: dict[str, str | None] = {
    "src/xippios/example/_client.py": TENANT_CLIENT,
    "src/xippios/example/tasks.py": TENANT_TASKS,
    "README.md": TENANT_README,
}


def test_a_multi_tenant_source_passes_with_its_tenant_list_and_a_declared_task(
    pytester: pytest.Pytester,
) -> None:
    """Every task takes ``org`` but the tenant list and ``list_regions``, which is declared."""
    write = TENANT_WRITE_TASKS.replace(
        '__all__ = ["create_series", "rename_series"]',
        'NO_TENANT_TASKS = frozenset({"rename_series"})\n'
        '__all__ = ["create_series", "rename_series"]',
    )
    result = run_family(pytester, {**TENANT_SOURCE, "src/xippios/example/tasks_write.py": write})
    result.assert_outcomes(passed=FAMILY_TESTS)


def test_a_task_of_a_multi_tenant_source_that_takes_no_tenant_fails_naming_it(
    pytester: pytest.Pytester,
) -> None:
    """The source opts into nothing: a ``Tenants`` registry makes it multi-tenant."""
    undeclared = TENANT_TASKS.replace('NO_TENANT_TASKS = frozenset({"list_regions"})\n', "")
    changes = {
        **TENANT_SOURCE,
        "src/xippios/example/tasks.py": undeclared,
        "src/xippios/example/tasks_write.py": TENANT_WRITE_TASKS,
    }
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*every task of a multi-tenant source takes exactly one tenant, required, its "
            "parameter read as org*NO_TENANT_TASKS*",
            "*- tasks.list_regions takes no org*",
            "*- tasks_write.rename_series takes no org*",
        ]
    )
    # A registry its tasks module holds, imported or its own, makes it multi-tenant too.
    own = undeclared.replace(
        "from xippios.example._client import TENANTS\n",
        "from xippios.core import Tenants\n\n"
        'TENANTS = Tenants("example", list_var="EXAMPLE_ORGS", fields=("API_KEY",))\n',
    )
    moved = {
        "src/xippios/example/_client.py": SOURCE["src/xippios/example/_client.py"],
        "src/xippios/example/tasks.py": own,
    }
    result = run_family(pytester, {**changes, **moved})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(["*- tasks.list_regions takes no org*"])


TENANT_FORMS = '''
from typing import Annotated

from pydantic import Field

from xippios.core import Result, ResultMeta, list_task, sync
from xippios.core.tenants import Tenants

META = ResultMeta(source="example", endpoint="e")
TENANTS = Tenants("example", list_var="EXAMPLE_ORGS", fields=("API_KEY",))
ORG = Annotated[str, Field(description="A declared organisation, e.g. demo.")]


def get_one(org: ORG, limit: int = 10) -> Result[int]:
    """Get one."""
    return Result[int](data=limit, meta=META)


def get_two(limit: int, org: str) -> Result[int]:
    """Get two."""
    return Result[int](data=limit, meta=META)


def get_defaulted(org: str = "demo") -> Result[int]:
    """Get with a default."""
    return Result[int](data=0, meta=META)


def get_several(org: list[str]) -> Result[int]:
    """Get for several."""
    return Result[int](data=0, meta=META)


def get_maybe(org: str | None) -> Result[int]:
    """Get for one or none."""
    return Result[int](data=0, meta=META)


def get_each(*org: str) -> Result[int]:
    """Get for each."""
    return Result[int](data=0, meta=META)


def get_unresolved(org: "Missing") -> Result[int]:
    """Get with an annotation that does not resolve."""
    return Result[int](data=0, meta=META)


async def list_regions_async() -> Result[list[str]]:
    """List regions."""
    return Result[list[str]](data=[], meta=META)


list_regions = sync(list_regions_async)
list_orgs = list_task(TENANTS, name="list_orgs")
NO_TENANT_TASKS = frozenset({"list_regions"})
'''


@pytest.fixture
def tenant_forms(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """A tasks module of every form a tenant's parameter takes; its ``__all__`` set per test."""
    module = ModuleType("xippios.example_forms.tasks")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    exec(TENANT_FORMS, module.__dict__)  # its functions' __module__ is the module
    return module


def _tenant_family(tasks: ModuleType, names: list[str], *, multi_tenant: bool = True) -> None:
    tasks.__all__ = names  # type: ignore[attr-defined]
    package = ModuleType("xippios.example_forms")
    package.__file__ = "/nowhere/__init__.py"
    source = FamilySource(
        root=Path("/nowhere"),
        import_path="xippios.example_forms",
        package=package,
        source="example",
        tasks=tasks,
        tasks_write=None,
        tenants=tasks.TENANTS if multi_tenant else None,
    )
    family.test_family_tasks_take_one_tenant(source)


def test_the_tenant_list_a_declared_task_and_an_annotated_tenant_pass(
    tenant_forms: ModuleType,
) -> None:
    # get_one and get_two take org and limit alike: org fits the rule, so org is the tenant's.
    _tenant_family(tenant_forms, ["get_one", "get_two", "list_regions", "list_orgs"])


@pytest.mark.parametrize(
    ("task", "problem"),
    [
        (
            "get_defaulted",
            "tasks.get_defaulted gives org the default 'demo'; the tenant is required",
        ),
        ("get_several", "tasks.get_several takes org as list[str], not one tenant's name, a str"),
        ("get_maybe", "tasks.get_maybe takes org as str | None, not one tenant's name, a str"),
        ("get_each", "tasks.get_each takes *org, several tenants"),
        ("get_unresolved", "tasks.get_unresolved has annotations that do not resolve"),
    ],
)
def test_a_tenant_parameter_with_a_default_or_of_several_tenants_fails(
    tenant_forms: ModuleType, task: str, problem: str
) -> None:
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_one", "list_regions", task])
    assert str(failed.value).splitlines()[1:] == [f"- {problem}"]


def test_a_declared_name_outside_all_fails_and_one_tenant_checks_nothing(
    tenant_forms: ModuleType,
) -> None:
    declared = frozenset({"list_regions", "list_old_regions"})
    tenant_forms.NO_TENANT_TASKS = declared  # type: ignore[attr-defined]
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_one", "list_regions"])
    assert str(failed.value).splitlines()[1:] == [
        "- NO_TENANT_TASKS of xippios.example_forms.tasks names ['list_old_regions'], not in its "
        "__all__"
    ]
    _tenant_family(tenant_forms, ["get_one", "get_each", "list_regions"], multi_tenant=False)
