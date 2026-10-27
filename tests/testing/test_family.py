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

FAMILY_TESTS = 10


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
    # register_tasks and router_from_tasks skip it themselves (ADR-0019, decision 4).
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
    # The write server is its source's to test (ADR-0024); none is written here.
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
