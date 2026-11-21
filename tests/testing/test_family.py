"""The family check, run by pytester against a source package laid out as the template does."""

import importlib
import json
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

FAMILY_TESTS = 15


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


def test_a_paged_tool_takes_its_tasks_parameters_and_the_adapters_offset(
    pytester: pytest.Pytester,
) -> None:
    # sdk-core#362: offset is the adapter's argument, which the task never takes.
    paged = SOURCE["src/xippios/example/mcp.py"].replace(
        f"{SERVED})", f"{SERVED}, caps={{'get_series': ResultCap(paged=True)}})"
    )
    paged = "from xippios.core import ResultCap\n" + paged
    result = run_family(pytester, {"src/xippios/example/mcp.py": paged})
    result.assert_outcomes(passed=FAMILY_TESTS)
    # A task that takes offset itself cannot be paged: the server refuses it as it is built.
    own = TASKS.replace("(series_id: str, year: int = 2024)", "(series_id: str, offset: int = 0)")
    result = run_family(
        pytester, {"src/xippios/example/mcp.py": paged, "src/xippios/example/tasks.py": own}
    )
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        ["*example_get_series: the task takes a parameter offset, which a paged cap adds*"]
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
TENANTS = Tenants(
    SOURCE, list_var="EXAMPLE_ORGS", param="org", fields=("API_KEY",), reserved=("demo",)
)
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
            "*every task of a multi-tenant source takes exactly one tenant, org, the parameter "
            "its Tenants registry declares, required*NO_TENANT_TASKS*",
            "*- tasks.list_regions takes no org*",
            "*- tasks_write.rename_series takes no org*",
        ]
    )
    # A registry its tasks module holds, imported or its own, makes it multi-tenant too.
    own = undeclared.replace(
        "from xippios.example._client import TENANTS\n",
        "from xippios.core import Tenants\n\n"
        'TENANTS = Tenants("example", list_var="EXAMPLE_ORGS", param="org", fields=("K",))\n',
    )
    moved = {
        "src/xippios/example/_client.py": SOURCE["src/xippios/example/_client.py"],
        "src/xippios/example/tasks.py": own,
    }
    result = run_family(pytester, {**changes, **moved})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(["*- tasks.list_regions takes no org*"])


def test_a_multi_tenant_source_that_declares_no_tenant_parameter_fails(
    pytester: pytest.Pytester,
) -> None:
    """``Tenants`` takes ``param``, the one declaration the check and the lock read."""
    client = TENANT_CLIENT.replace(' param="org",', "")
    result = run_family(pytester, {**TENANT_SOURCE, "src/xippios/example/_client.py": client})
    result.assert_outcomes(errors=FAMILY_TESTS)
    result.stdout.fnmatch_lines(["*missing 1 required keyword-only argument: 'param'*"])


TENANT_FORMS = '''
from typing import Annotated

from pydantic import Field

from xippios.core import Result, ResultMeta, list_task, sync
from xippios.core.tenants import Tenants

META = ResultMeta(source="example", endpoint="e")
TENANTS = Tenants("example", list_var="EXAMPLE_ORGS", param="org", fields=("API_KEY",))
ACCOUNTS = Tenants("example", list_var="EXAMPLE_ACCOUNTS", param="account", fields=("API_KEY",))
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


def get_invoice(invoice_id: str, org: str) -> Result[int]:
    """Get an invoice of an organisation."""
    return Result[int](data=0, meta=META)


def get_journal(invoice_id: str) -> Result[int]:
    """Get the journal of an invoice; it takes no tenant and is not declared."""
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


def _tenant_family(
    tasks: ModuleType, names: list[str], *, multi_tenant: bool = True, registry: str = "TENANTS"
) -> None:
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
        tenants=getattr(tasks, registry) if multi_tenant else None,
    )
    family.test_family_tasks_take_one_tenant(source)


def test_the_tenant_list_a_declared_task_and_an_annotated_tenant_pass(
    tenant_forms: ModuleType,
) -> None:
    # get_one takes org first, get_two last: the registry names it, not its place.
    _tenant_family(tenant_forms, ["get_one", "get_two", "list_regions", "list_orgs"])


def test_the_tenant_parameter_is_the_one_the_registry_declares(tenant_forms: ModuleType) -> None:
    """The review's probe: the tasks share invoice_id, yet the registry declares org."""
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_invoice", "get_journal", "list_regions"])
    assert str(failed.value).splitlines()[1:] == ["- tasks.get_journal takes no org"]
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_one", "list_regions"], registry="ACCOUNTS")
    assert str(failed.value).splitlines()[1:] == ["- tasks.get_one takes no account"]


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


# The notes of observed behavior (conventions §3, ADR-0044). OBSERVED_MD meets the three
# rules once the files it cites exist: its notes are the three ### sections, the fenced
# "## ..." line and the #### heading stay inside the second, the same heading under two
# groups is two notes, and the last note ends with its probe once its link reference
# definition, which renders as nothing, is dropped. Its preamble's other spans cite no file.
OBSERVED_MD = """# What Example does but never documents

Notes, written by hand, on what the Example API does that no page of the snapshot states
(conventions §3). A sample is named by its path, ``tests/fixtures/get_series/corn.json``,
and the seed script, `scripts/seed.py --discovery`, the folder `tests/fixtures/` and the
request `GET /v1/series.json` cite no file.

## Series

### A year without data answers HTTP 404

The series endpoint answers a year without data with HTTP 404 and an empty body.

Probe: 2026-11-20, `GET /v1/series`; sample `tests/fixtures/get_series/empty.json`.

### The layout of the yearly file

The file is laid out as the release's `series2026.xml` shows, against the snapshot's
`openapi/spec.json`:

```text
## a line of the file, not a heading
```

#### Columns

The columns are named as upstream prints them.

Observed: 2026-10-28, in `docs/upstream/samples/series.json`.

## Refusals

### A year without data answers HTTP 404

The same heading under another group is a note of its own.

Probe: 2026-11-21, `GET /v1/series` with a year of letters, its answer not kept; see the
[record][1].

[1]: https://example.org/record
"""

HAND = "written by hand: what upstream does but never documents; not fetched or checked"

FETCHED_MD = """# Fetched

| File | URL | Fetched | Note |
| --- | --- | --- | --- |
| index.md | https://example.org/docs/ | 2026-11-20T09:00:00Z | the guide |
{row}
"""

OBSERVED_TREE: dict[str, str | None] = {
    "docs/upstream/OBSERVED.md": OBSERVED_MD,
    "docs/upstream/FETCHED.md": FETCHED_MD.format(row=f"| OBSERVED.md | - | - | {HAND} |"),
    "tests/fixtures/get_series/corn.json": "{}\n",
    "tests/fixtures/get_series/empty.json": "{}\n",
    "docs/upstream/samples/series.json": "{}\n",
}

OBSERVED_INTRO = (
    "docs/upstream/OBSERVED.md: every note, a ### section, ends with a paragraph that opens "
    "with 'Probe: <date>' or 'Observed: <date>', the date as YYYY-MM-DD (conventions §3, "
    "ADR-0044):"
)


def _rooted(root: Path) -> FamilySource:
    """A source at ``root``, for the checks that read the repository's files alone."""
    package = ModuleType("xippios.example")
    package.__file__ = str(root / "src" / "xippios" / "example" / "__init__.py")
    return FamilySource(
        root=root,
        import_path="xippios.example",
        package=package,
        source="example",
        tasks=ModuleType("xippios.example.tasks"),
        tasks_write=None,
    )


def _write(root: Path, files: dict[str, str | None]) -> None:
    for path, content in files.items():
        if content is not None:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(content, encoding="utf-8")


def test_a_source_without_observed_md_passes_the_three_rules(tmp_path: Path) -> None:
    source = _rooted(tmp_path)
    family.test_family_fetched_md_lists_observed_md_in_a_row_of_its_own(source)
    family.test_family_observed_notes_end_with_their_probe_and_date(source)
    family.test_family_observed_md_cites_files_that_exist(source)


def test_a_source_that_keeps_observed_md_passes_the_three_rules_it_meets(tmp_path: Path) -> None:
    _write(tmp_path, OBSERVED_TREE)
    source = _rooted(tmp_path)
    family.test_family_fetched_md_lists_observed_md_in_a_row_of_its_own(source)
    family.test_family_observed_notes_end_with_their_probe_and_date(source)
    family.test_family_observed_md_cites_files_that_exist(source)


@pytest.mark.parametrize(
    "row",
    [
        f"| OBSERVED.md | - | - | {HAND} |",  # sdk-cashctrl's four cells
        f"| OBSERVED.md | - | - | - | - | {HAND} |",  # the six of sdk-eurostat's script
        f"| OBSERVED.md | - | - | - | - | - | - | - | {HAND} |",  # the nine of four sources
        "| OBSERVED.md | Written by hand, never fetched |",
    ],
)
def test_the_row_of_observed_md_is_told_by_its_cells_at_any_width(row: str) -> None:
    assert family._lists_observed(FETCHED_MD.format(row=row))


@pytest.mark.parametrize(
    "row",
    [
        "",  # sdk-eurostat's FETCHED.md on 2026-11-21: the file kept, its row not written
        f"| OBSERVED.md | https://example.org/observed | - | {HAND} |",
        "| OBSERVED.md | - | - | the notes on what upstream does but never documents |",
        f"| docs/upstream/OBSERVED.md | - | - | {HAND} |",
        f"| OBSERVED.md, index.md | - | - | {HAND} |",
        f"Nothing here is edited by hand but `OBSERVED.md`, {HAND}.",
    ],
)
def test_a_row_that_was_fetched_names_another_file_or_no_hand_is_none(row: str) -> None:
    assert not family._lists_observed(FETCHED_MD.format(row=row))


def test_a_fetched_md_without_the_row_fails_naming_the_row(tmp_path: Path) -> None:
    _write(tmp_path, {**OBSERVED_TREE, "docs/upstream/FETCHED.md": FETCHED_MD.format(row="")})
    with pytest.raises(pytest.fail.Exception) as failed:
        family.test_family_fetched_md_lists_observed_md_in_a_row_of_its_own(_rooted(tmp_path))
    assert str(failed.value) == (
        "docs/upstream/FETCHED.md lists OBSERVED.md in no row of its own: write a row of its "
        "table whose first cell is OBSERVED.md, whose last cell says that it is written by "
        "hand and whose cells between are - (conventions §3, ADR-0044)"
    )
    (tmp_path / "docs" / "upstream" / "FETCHED.md").unlink()
    with pytest.raises(pytest.fail.Exception, match=r"^docs/upstream/FETCHED\.md is missing"):
        family.test_family_fetched_md_lists_observed_md_in_a_row_of_its_own(_rooted(tmp_path))


def test_the_notes_are_the_h3_sections_each_judged_by_its_last_paragraph() -> None:
    notes = family._observed_notes(OBSERVED_MD)
    assert [heading for heading, _ in notes] == [
        "A year without data answers HTTP 404",
        "The layout of the yearly file",
        "A year without data answers HTTP 404",
    ]
    assert [paragraphs[-1].split(",")[0] for _, paragraphs in notes] == [
        "Probe: 2026-11-20",
        "Observed: 2026-10-28",
        "Probe: 2026-11-21",
    ]
    assert notes[1][1][1:4] == [
        "```text ## a line of the file, not a heading ```",
        "#### Columns",
        "The columns are named as upstream prints them.",
    ]
    assert family._probe_problems(OBSERVED_MD) == []


NOTE = "# Notes\n\n## Group\n\n### A note\n\nWhat upstream does.\n\n{last}\n"


@pytest.mark.parametrize(
    ("last", "problem"),
    [
        (
            "Probe: 2026-11-20.\n\nThe package reads it as None.",
            "A note: its last paragraph opens 'The package reads it as None.'",
        ),
        (
            "Probe: on 2026-11-20, `GET /v1/series`.",
            "A note: its last paragraph opens 'Probe: on 2026-11-20, `GET /v1/series`.'",
        ),
        (
            "Probe: `GET /v1/series`, sample\n`tests/fixtures/get_series/empty.json`.",
            "A note: its last paragraph opens 'Probe: `GET /v1/series`, sample `tests/f...'",
        ),
        ("Seen: 2026-11-20.", "A note: its last paragraph opens 'Seen: 2026-11-20.'"),
        ("probe: 2026-11-20.", "A note: its last paragraph opens 'probe: 2026-11-20.'"),
        ("Probe: 20261120.", "A note: its last paragraph opens 'Probe: 20261120.'"),
        ("Probe: 2026-13-01, `GET /v1/series`.", "A note: 2026-13-01 is no date"),
    ],
)
def test_a_note_whose_last_paragraph_is_no_dated_probe_fails(last: str, problem: str) -> None:
    assert family._probe_problems(NOTE.format(last=last)) == [problem]


def test_a_file_without_notes_or_with_an_empty_note_fails() -> None:
    ungrouped = "# Notes\n\n## Series\n\nProbe: 2026-11-20, a probe under no note.\n"
    assert family._probe_problems(ungrouped) == ["the file holds no note"]
    empty = "### A note\n\n### Another\n\nProbe: 2026-11-20.\n"
    assert family._probe_problems(empty) == ["A note: no paragraph"]


def test_a_failing_note_fails_beside_one_of_the_same_heading(tmp_path: Path) -> None:
    """The first of two notes of one heading fails: a note keyed by its heading would pass."""
    broken = OBSERVED_MD.replace("Probe: 2026-11-20, ", "Seen on 2026-11-20, ")
    _write(tmp_path, {**OBSERVED_TREE, "docs/upstream/OBSERVED.md": broken})
    with pytest.raises(pytest.fail.Exception) as failed:
        family.test_family_observed_notes_end_with_their_probe_and_date(_rooted(tmp_path))
    assert str(failed.value).splitlines() == [
        OBSERVED_INTRO,
        "- A year without data answers HTTP 404: its last paragraph opens 'Seen on "
        "2026-11-20, `GET /v1/series`; sa...'",
    ]


def test_every_path_a_code_span_cites_is_a_file_from_the_root(tmp_path: Path) -> None:
    assert family._missing_citations(OBSERVED_MD, tmp_path) == [
        "line 4: tests/fixtures/get_series/corn.json",
        "line 14: tests/fixtures/get_series/empty.json",
        "line 29: docs/upstream/samples/series.json",
    ]
    _write(tmp_path, OBSERVED_TREE)
    assert family._missing_citations(OBSERVED_MD, tmp_path) == []
    (tmp_path / "tests" / "fixtures" / "get_series" / "empty.json").unlink()
    with pytest.raises(pytest.fail.Exception) as failed:
        family.test_family_observed_md_cites_files_that_exist(_rooted(tmp_path))
    assert str(failed.value).splitlines() == [
        "docs/upstream/OBSERVED.md cites files that do not exist, from the repository's root "
        "(conventions §3, ADR-0044):",
        "- line 14: tests/fixtures/get_series/empty.json",
    ]


WRAPPED = """### A query with no filter is refused

A data query with no filter is refused with HTTP 500 and the plain text body `Please add
at least one filter.`, as the sample `tests/fixtures/get_data/no_filter.json` holds.

```text
`tests/fixtures/in_a_fence.json` is text in a fenced block, no code span
```

Probe: 2026-10-29, `get_data`; sample `tests/fixtures/get_data/no_filter_500.json`.
"""


def test_a_span_that_wraps_onto_the_next_line_hides_no_citation_after_it(tmp_path: Path) -> None:
    """A span may wrap onto the next line of its paragraph, as two of sdk-faostat's do.

    Read line by line, its closing backtick would pair with the opening one of the next span,
    and the path after it would go unread. A fenced block holds no code span.
    """
    assert family._missing_citations(WRAPPED, tmp_path) == [
        "line 4: tests/fixtures/get_data/no_filter.json",
        "line 10: tests/fixtures/get_data/no_filter_500.json",
    ]


def test_the_family_check_holds_a_sources_observed_md(pytester: pytest.Pytester) -> None:
    result = run_family(pytester, OBSERVED_TREE)
    result.assert_outcomes(passed=FAMILY_TESTS)
    cited = "tests/fixtures/get_series/empty.json"
    (pytester.path / cited).unlink()
    broken: dict[str, str | None] = {
        "docs/upstream/FETCHED.md": FETCHED_MD.format(row=""),
        "docs/upstream/OBSERVED.md": OBSERVED_MD.replace("Observed: 2026-10-28, in", "From"),
        cited: None,
    }
    result = run_family(pytester, {**OBSERVED_TREE, **broken})
    result.assert_outcomes(passed=FAMILY_TESTS - 3, failed=3)
    result.stdout.fnmatch_lines(["*docs/upstream/FETCHED.md lists OBSERVED.md in no row of its*"])
    result.stdout.fnmatch_lines(
        ["*- The layout of the yearly file: its last paragraph opens 'From*"]
    )
    result.stdout.fnmatch_lines([f"*- line 14: {cited}*"])


# The declaration of the packaged lists for the live run (ADR-0055, sdk-core#319).

REFERENCE = "src/xippios/example/reference"


def packaged(param: str, code: str, *codes: str) -> str:
    """A packaged list's file: ``codes`` as records of the one field ``code``."""
    records = [{code: value} for value in codes]
    return json.dumps(
        {
            "param": param,
            "endpoint": f"get_{param}",
            "fetched": "2026-11-20T09:00:00Z",
            "records": records,
        }
    )


LISTS_TREE: dict[str, str | None] = {
    f"{REFERENCE}/countries.json": packaged("countries", "countryCode", "US", "BR"),
    f"{REFERENCE}/regions.json": packaged("regions", "regionCode", "R01"),
    # sdk-eurostat's index of its lists holds no records: no packaged list
    f"{REFERENCE}/lists.json": json.dumps({"fetched": "2026-11-20T09:00:00Z", "lists": []}),
    f"{REFERENCE}/README.md": "# Reference data\n",
}

DECLARATION = '''"""Live tests: the packaged lists of xippios.example."""

from pathlib import Path

from xippios.core import PackagedList
from xippios.core.testing.live import *  # noqa: F403

REFERENCE = Path(__file__).parents[1] / "src" / "xippios" / "example" / "reference"


def codes(name, code):
    text = (REFERENCE / f"{{name}}.json").read_text(encoding="utf-8")
    return PackagedList.model_validate_json(text).codes(code)


def fetch():
    raise AssertionError("the family check fetches nothing")


LIVE_LISTS = {{{live}}}
NO_LIVE_LIST = {{{no_live}}}
'''

COMPARED = '"countries": (codes("countries", "countryCode"), fetch)'
EXCUSED = '"regions": "Upstream serves no list of regions; its specification gives them."'


def declared(live: str = COMPARED, no_live: str = EXCUSED) -> dict[str, str | None]:
    return {"tests/test_live.py": DECLARATION.format(live=live, no_live=no_live)}


LIVE_INTRO = (
    "every packaged list under reference/ stands in LIVE_LISTS of tests/test_live.py, compared "
    "with the list upstream serves now, or in its NO_LIVE_LIST with the reason it is not "
    "(conventions §10, ADR-0055):"
)


def live_problems(root: Path, files: dict[str, str | None]) -> list[str]:
    """The lines the check fails with for a source of ``files`` at ``root``, none on a pass."""
    _write(root, files)
    try:
        family.test_family_every_packaged_list_is_declared_for_the_live_run(_rooted(root))
    except pytest.fail.Exception as failed:
        lines, pytrace = str(failed).splitlines(), failed.pytrace
    else:
        return []
    assert not pytrace, "the failure shows no frame"
    assert lines[0] == LIVE_INTRO
    return lines[1:]


def test_a_source_without_packaged_lists_or_a_declaration_passes(tmp_path: Path) -> None:
    assert live_problems(tmp_path, {f"{REFERENCE}/README.md": "# Reference data\n"}) == []


def test_a_source_that_declares_every_packaged_list_passes(tmp_path: Path) -> None:
    assert live_problems(tmp_path, {**LISTS_TREE, **declared()}) == []


def test_a_packaged_list_in_neither_declaration_fails_naming_it_and_both(tmp_path: Path) -> None:
    assert live_problems(tmp_path, {**LISTS_TREE, **declared(no_live="")}) == [
        "- regions: reference/regions.json stands in neither LIVE_LISTS nor NO_LIVE_LIST"
    ]


@pytest.mark.parametrize(
    ("live", "no_live", "problems"),
    [
        (
            f'{COMPARED}, "partners": (codes("countries", "countryCode"), fetch)',
            EXCUSED,
            ["- partners: LIVE_LISTS names no packaged list, no reference/partners.json"],
        ),
        (
            COMPARED,
            f'{EXCUSED}, "units": "No endpoint."',
            ["- units: NO_LIVE_LIST names no packaged list, no reference/units.json"],
        ),
        (
            f'{COMPARED}, "regions": (codes("regions", "regionCode"), fetch)',
            EXCUSED,
            ["- regions: stands in both LIVE_LISTS and NO_LIVE_LIST"],
        ),
        (
            COMPARED,
            '"regions": " "',
            ["- regions: NO_LIVE_LIST gives no reason, a text that says why it is not compared"],
        ),
        (
            COMPARED,
            '"regions": None',
            ["- regions: NO_LIVE_LIST gives no reason, a text that says why it is not compared"],
        ),
        (
            '"countries": (fetch, codes("countries", "countryCode"))',
            EXCUSED,
            [
                "- countries: LIVE_LISTS holds no pair of its PackagedCodes and the function that "
                "fetches it now"
            ],
        ),
        (
            '"countries": codes("countries", "countryCode")',
            EXCUSED,
            [
                "- countries: LIVE_LISTS holds no pair of its PackagedCodes and the function that "
                "fetches it now"
            ],
        ),
        (
            '"countries": (codes("regions", "regionCode"), fetch)',
            EXCUSED,
            [
                "- countries: LIVE_LISTS holds the codes of another list than "
                "reference/countries.json"
            ],
        ),
    ],
    ids=[
        "stale-live",
        "stale-no-live",
        "in-both",
        "blank-reason",
        "no-reason",
        "pair-reversed",
        "no-pair",
        "another-list",
    ],
)
def test_a_declaration_that_the_files_do_not_bear_out_fails_naming_the_entry(
    tmp_path: Path, live: str, no_live: str, problems: list[str]
) -> None:
    """A stale entry fails as an undeclared list does: no declaration passes silently."""
    assert live_problems(tmp_path, {**LISTS_TREE, **declared(live, no_live)}) == problems


def test_declarations_that_are_no_mappings_fail_naming_them(tmp_path: Path) -> None:
    broken = DECLARATION.format(live=COMPARED, no_live=EXCUSED).replace(
        "NO_LIVE_LIST = {" + EXCUSED + "}", 'NO_LIVE_LIST = ["regions"]'
    )
    assert live_problems(tmp_path, {**LISTS_TREE, "tests/test_live.py": broken}) == [
        "- NO_LIVE_LIST is a list, not a mapping by the lists' names",
        "- regions: reference/regions.json stands in neither LIVE_LISTS nor NO_LIVE_LIST",
    ]


def test_packaged_lists_without_a_live_test_module_fail_naming_it(tmp_path: Path) -> None:
    assert live_problems(tmp_path, LISTS_TREE) == [
        "- tests/test_live.py, which declares LIVE_LISTS and NO_LIVE_LIST, is missing",
        "- countries: reference/countries.json stands in neither LIVE_LISTS nor NO_LIVE_LIST",
        "- regions: reference/regions.json stands in neither LIVE_LISTS nor NO_LIVE_LIST",
    ]


def test_a_live_test_module_that_does_not_import_fails_naming_its_error(tmp_path: Path) -> None:
    broken = DECLARATION.format(live=COMPARED, no_live=EXCUSED) + "\nMISSING_NAME\n"
    assert live_problems(tmp_path, {**LISTS_TREE, "tests/test_live.py": broken}) == [
        "- tests/test_live.py does not import: NameError: name 'MISSING_NAME' is not defined"
    ]


def test_a_stale_declaration_fails_where_no_list_is_packaged(tmp_path: Path) -> None:
    assert live_problems(tmp_path, declared(live="", no_live=EXCUSED)) == [
        "- regions: NO_LIVE_LIST names no packaged list, no reference/regions.json"
    ]


def test_the_family_check_and_the_live_test_read_one_declaration(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under --import-mode=importlib, as the sources run, the two modules reach one declaration."""
    monkeypatch.delenv("XIPPIOS_LIVE_TESTS", raising=False)
    importlib_mode = PYPROJECT.replace(
        '"-p no:cacheprovider"', '"-p no:cacheprovider --import-mode=importlib"'
    )
    tree: dict[str, str | None] = {**LISTS_TREE, **declared(), "pyproject.toml": importlib_mode}
    result = run_family(pytester, tree)
    result.assert_outcomes(passed=FAMILY_TESTS, skipped=1)  # the gate is closed
    result = run_family(pytester, {**tree, **declared(no_live="")})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1, skipped=1)
    result.stdout.fnmatch_lines(
        [
            f"*{LIVE_INTRO}*",
            "*- regions: reference/regions.json stands in neither LIVE_LISTS nor NO_LIVE_LIST*",
        ]
    )
