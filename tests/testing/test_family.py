"""The family check, run by pytester against a source package laid out as the template does."""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any

import pytest

from xippios.core.http import router_from_tasks
from xippios.core.mcp import ToolSet, build_server
from xippios.core.testing import family
from xippios.core.testing.family import FamilySource, _cell_tasks, _status_table_tasks

# What building the adapters imports is loaded here, before pytester's in-process runs: a
# module first imported inside one is dropped after it, and imported again by the next,
# cryptography's hash classes (behind the MCP server) no longer match its compiled half.
build_server(ToolSet("warmup", [], read_only=False))
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


async def search_series_async(filters: dict[str, str]) -> Result[list[int]]:
    """Search series by upstream filters.

    Args:
        filters: Upstream filters, e.g. ``{"state": "IA"}``.
    """
    return Result[list[int]](data=[], meta=META)


async def list_regions_async() -> Result[list[str]]:
    """List the regions a series can be asked for."""
    return Result[list[str]](data=[], meta=META)


get_series = sync(get_series_async)
search_series = sync(search_series_async)
list_regions = sync(list_regions_async)

__all__ = ["search_series", "get_series", "list_regions"]
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
| `series`, filtered | `tasks.search_series(filters)`; a `POST` route | `example_search_series` | |
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

[project.scripts]
xippios-example-mcp = "xippios.example.mcp:run"
example-refresh = "xippios.example.refresh:main"

[tool.pytest.ini_options]
addopts = "-p no:cacheprovider"
"""

INIT = '''"""The example package: its version and its tasks, re-exported (ADR-0063, decision 8)."""

from xippios.example.tasks import *  # noqa: F403

try:
    from xippios.example.tasks_write import *  # noqa: F403
except ModuleNotFoundError:  # a read-only source
    pass

__version__ = "0.1.0"
'''
"""The package's ``__init__.py``: its star imports re-export each variant's tasks."""

READ_SCRIPT = 'xippios-example-mcp = "xippios.example.mcp:run"\n'
"""The entry point of a source without a write server (conventions §8)."""

SOURCE: dict[str, str] = {
    "src/xippios/example/__init__.py": INIT,
    "src/xippios/example/py.typed": "",
    "src/xippios/example/_client.py": 'SOURCE = "example"\nENV_VARS = ()\n',
    "src/xippios/example/tasks.py": TASKS,
    "src/xippios/example/mcp.py": (
        "from xippios.core.mcp import ToolSet, build_server, main\n"
        "from xippios.example import tasks\n"
        "from xippios.example._client import ENV_VARS, SOURCE\n\n"
        '__all__ = ["ENV_VARS", "SOURCE", "build", "run", "server"]\n\n\n'
        "def build() -> ToolSet:\n"
        f"    return ToolSet(SOURCE, {SERVED})\n\n\n"
        "server = build_server(build())\n\n\n"
        "def run() -> None:\n"
        "    main(build)\n"
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

FAMILY_TESTS = 23

WRITE_MCP = """from xippios.core.mcp import ToolSet, build_server, main
from xippios.example import tasks_write
from xippios.example._client import SOURCE


def build() -> ToolSet:
    return ToolSet.from_tasks(SOURCE, tasks_write, read_only=False)


server = build_server(build())


def run() -> None:
    main(build)
"""
"""A write server's ``mcp_write.py``, built from ``tasks_write`` (conventions §8)."""

WRITE_SCRIPTS = (
    'xippios-example-mcp-read = "xippios.example.mcp:run"\n'
    'xippios-example-mcp-write = "xippios.example.mcp_write:run"\n'
)
"""The entry points of a source with a write server, read and write (conventions §8)."""

WRITE_SERVER: dict[str, str | None] = {
    "src/xippios/example/mcp_write.py": WRITE_MCP,
    "pyproject.toml": PYPROJECT.replace(READ_SCRIPT, WRITE_SCRIPTS),
}
"""What a source with ``tasks_write.py`` adds: its write server and its two entry points."""


def run_family(
    pytester: pytest.Pytester, changes: dict[str, str | None] | None = None
) -> pytest.RunResult:
    """Write the source with ``changes`` (path to content; ``None`` deletes) and run it."""
    files = {**SOURCE, **(changes or {})}
    for path, content in files.items():
        target = pytester.path / path
        if content is None:
            target.unlink(missing_ok=True)
            continue
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


# The package contract, the entry points, the re-export and a description's bound, which
# every source tested again for itself (ADR-0063, decisions 8 and 9) ---------------------

CONTRACT_INTRO = (
    "*mcp.py and mcp_write.py hold the package contract (conventions §8, ADR-0063, decision 8):*"
)


def test_a_server_or_env_vars_that_the_tool_set_does_not_give_fail_the_contract(
    pytester: pytest.Pytester,
) -> None:
    # A paged cap that build() lacks lists the tool with an offset, so the server serves
    # another tool than a host that serves build() would; a copy of ENV_VARS can drift.
    mcp = SOURCE["src/xippios/example/mcp.py"]
    key = 'EnvVar("EXAMPLE_API_KEY", secret=True, required=True)'
    client = f'from xippios.core import EnvVar\n\nSOURCE = "example"\nENV_VARS = ({key},)\n'
    paged = f"ToolSet(SOURCE, {SERVED}, caps={{'get_series': ResultCap(paged=True)}})"
    drifted = (
        mcp.replace(
            "from xippios.example._client import ENV_VARS, SOURCE",
            "from xippios.core import EnvVar, ResultCap\n"
            "from xippios.example._client import SOURCE",
        )
        .replace("__all__ = [", f"ENV_VARS = ({key},)\n__all__ = [")
        .replace("server = build_server(build())", f"server = build_server({paged})")
    )
    changes: dict[str, str | None] = {
        "src/xippios/example/_client.py": client,
        "src/xippios/example/mcp.py": drifted,
    }
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*test_family_mcp_build_holds_the_package_contract*",
            CONTRACT_INTRO,
            "*- mcp.server lists other tools than build_server(mcp.build()): example_get_series*",
            "*- mcp.ENV_VARS is not _client.ENV_VARS: import it from _client*",
        ]
    )
    # A tool set of another source names its tools after that source.
    other = mcp.replace("ToolSet(SOURCE, ", 'ToolSet("example-v2", ')
    result = run_family(pytester, {"src/xippios/example/mcp.py": other})
    result.assert_outcomes(passed=FAMILY_TESTS - 2, failed=2)
    result.stdout.fnmatch_lines(
        ["*- mcp.build() returns the tool set of 'example-v2', not of _client.SOURCE, 'example'*"]
    )
    bare = mcp.replace("server = build_server(build())", "").replace(
        "import ENV_VARS, SOURCE", "import SOURCE"
    )
    result = run_family(pytester, {"src/xippios/example/mcp.py": bare})
    result.stdout.fnmatch_lines(
        ["*- mcp.py has no server: server = build_server(build())*", "*- mcp.py has no ENV_VARS*"]
    )


def test_a_write_source_without_its_write_tool_set_fails_the_contract(
    pytester: pytest.Pytester,
) -> None:
    table = README.replace(
        "| `regions` |",
        "| `create` | `create_series(name, confirm)` | write server | alpha |\n| `regions` |",
    )
    write: dict[str, str | None] = {
        "src/xippios/example/tasks_write.py": WRITE_TASKS,
        "README.md": table,
    }
    result = run_family(pytester, write)
    result.assert_outcomes(passed=FAMILY_TESTS - 2, failed=2)
    result.stdout.fnmatch_lines(
        [CONTRACT_INTRO, "*- tasks_write.py has no write server: mcp_write.py is missing*"]
    )
    read_only = WRITE_MCP.replace(", read_only=False", "")
    changes = {**write, **WRITE_SERVER, "src/xippios/example/mcp_write.py": read_only}
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(["*- mcp_write.build() returns a tool set that does not write*"])


SCRIPTS_INTRO = (
    "*[[]project.scripts[]] names the entry points of conventions §8, each at its module's run "
    "(ADR-0063, decision 8):*"
)


def test_the_entry_points_are_the_conventions_at_each_module_s_run(
    pytester: pytest.Pytester,
) -> None:
    # A script of the package's own, example-refresh, stands beside them (SOURCE's pyproject).
    moved = PYPROJECT.replace(READ_SCRIPT, 'xippios-example-mcp = "xippios.example.server:main"\n')
    result = run_family(pytester, {"pyproject.toml": moved})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            SCRIPTS_INTRO,
            "*- xippios-example-mcp runs xippios.example.server:main, not xippios.example.mcp:run*",
        ]
    )
    result = run_family(pytester, {"pyproject.toml": PYPROJECT.replace(READ_SCRIPT, "")})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(['*- no xippios-example-mcp = "xippios.example.mcp:run"*'])
    # A read-only source names no write server's entry points.
    split = PYPROJECT.replace(READ_SCRIPT, WRITE_SCRIPTS)
    result = run_family(pytester, {"pyproject.toml": split})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            '*- no xippios-example-mcp = "xippios.example.mcp:run"*',
            "*- xippios-example-mcp-read is no entry point of a source without a write server*",
            "*- xippios-example-mcp-write is no entry point of a source without a write server*",
        ]
    )
    # A source with a write server names the two and keeps no alias of the old name.
    aliased = WRITE_SERVER["pyproject.toml"] or ""
    aliased = aliased.replace(WRITE_SCRIPTS, WRITE_SCRIPTS + READ_SCRIPT)
    table = README.replace(
        "| `regions` |",
        "| `create` | `create_series(name, confirm)` | write server | alpha |\n| `regions` |",
    )
    changes: dict[str, str | None] = {
        "src/xippios/example/tasks_write.py": WRITE_TASKS,
        **WRITE_SERVER,
        "README.md": table,
        "pyproject.toml": aliased,
    }
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        ["*- xippios-example-mcp is no entry point of a source with a write server*"]
    )
    result = run_family(pytester, {**changes, "pyproject.toml": PYPROJECT})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            '*- no xippios-example-mcp-read = "xippios.example.mcp:run"*',
            '*- no xippios-example-mcp-write = "xippios.example.mcp_write:run"*',
            "*- xippios-example-mcp is no entry point of a source with a write server*",
        ]
    )


def test_a_task_that_the_package_does_not_re_export_fails_naming_it(
    pytester: pytest.Pytester,
) -> None:
    init = (
        "from xippios.example.tasks import get_series, search_series\n\n"
        "list_regions = search_series\n"
        '__version__ = "0.1.0"\n'
    )
    write: dict[str, str | None] = {
        "src/xippios/example/tasks_write.py": WRITE_TASKS,
        **WRITE_SERVER,
        "README.md": README.replace(
            "| `regions` |",
            "| `create` | `create_series(name, confirm)` | write server | alpha |\n| `regions` |",
        ),
    }
    result = run_family(pytester, {**write, "src/xippios/example/__init__.py": init})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*the package re-exports every task of tasks.__all__ and tasks_write.__all__*",
            "*- tasks.list_regions: xippios.example.list_regions is another object*",
            "*- tasks_write.create_series: xippios.example has no create_series*",
        ]
    )
    assert "- tasks.get_series" not in result.stdout.str()


DESCRIPTION_INTRO = (
    "*every tool's description, the text of its task's docstring before Args:, is under 1,000 "
    "characters (conventions §8, ADR-0063, decision 9):*"
)


def _described(text: str, first: str, length: int) -> str:
    """``text`` with the task whose docstring opens with ``first`` described in ``length``.

    The description is the docstring's text before ``Args:``: its first line, a blank line and
    a paragraph that brings it to ``length`` characters.
    """
    rest = "x" * (length - len(first) - 2)
    return text.replace(f'"""{first}\n', f'"""{first}\n\n    {rest}\n', 1)


def test_a_description_of_1000_characters_fails_naming_its_tool(
    pytester: pytest.Pytester,
) -> None:
    # The text under Args: is no part of the description: it goes to the input schema.
    first = "Fetch one series for a year."
    long_args = TASKS.replace('e.g. ``"CORN"``.', 'e.g. ``"CORN"``. ' + "y" * 2000, 1)
    under = _described(long_args, first, 999)
    result = run_family(pytester, {"src/xippios/example/tasks.py": under})
    result.assert_outcomes(passed=FAMILY_TESTS)
    at = _described(TASKS, first, 1000)
    write = _described(WRITE_TASKS, "Create a series, or preview it unless confirmed.", 1204)
    changes: dict[str, str | None] = {
        "src/xippios/example/tasks.py": at,
        "src/xippios/example/tasks_write.py": write,
        **WRITE_SERVER,
        "README.md": README.replace(
            "| `regions` |",
            "| `create` | `create_series(name, confirm)` | write server | alpha |\n| `regions` |",
        ),
    }
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*test_family_tool_descriptions_stay_under_the_bound*",
            DESCRIPTION_INTRO,
            "*- example_create_series: 1,204 characters*",
            "*- example_get_series: 1,000 characters*",
        ]
    )


KEYED_CLIENT = """from xippios.core import EnvVar
from xippios.core.client import AsyncClient, ClientConfig, KeyAuth

SOURCE = "example"
BASE_URL = "https://api.example.org/v1"
ENV_VARS = (EnvVar("EXAMPLE_API_KEY", secret=True, required=True),)


class Shared:
    # Builds the key class with the slug it is given, as a publisher's gateway does.

    def __init__(self, source: str) -> None:
        self.auth = KeyAuth("EXAMPLE_SHARED", location="header", name="X-Api-Key", source=source)


auth = KeyAuth("EXAMPLE_API_KEY", location="query", name="key", source=SOURCE)
shared = Shared(SOURCE)
config = ClientConfig(source=SOURCE, version="0.1.0", base_url=BASE_URL)
client = AsyncClient(config, auth=shared.auth)
"""

ANOTHER_SLUG = """
other = Shared("example-v2")
elsewhere = AsyncClient(config, auth=KeyAuth("EXAMPLE_KEY", location="bearer", source="sibling"))
stray = KeyAuth("EXAMPLE_STRAY_KEY", location="query", name="key", source="sibling-two")
"""


def test_a_key_class_that_names_another_slug_than_the_package_s_fails(
    pytester: pytest.Pytester,
) -> None:
    # A key registered under one slug stays as sent in an envelope of another, so the check
    # holds the key class a source's client uses to the package's own slug
    # (https://github.com/xippios/sdk-core/issues/526).
    no_key = run_family(pytester)
    no_key.assert_outcomes(passed=FAMILY_TESTS)
    own = run_family(pytester, {"src/xippios/example/_client.py": KEYED_CLIENT})
    own.assert_outcomes(passed=FAMILY_TESTS)
    mismatched = KEYED_CLIENT + ANOTHER_SLUG
    result = run_family(pytester, {"src/xippios/example/_client.py": mismatched})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*test_family_key_class_names_the_package_s_own_slug*",
            "*_client.py's key class must name the package's slug, 'example':*",
            "*- elsewhere's auth names 'sibling'*",
            "*- other.auth names 'example-v2'*",
            "*- stray names 'sibling-two'*",
        ]
    )
    for passing in ("- auth ", "- shared.auth", "- client's auth"):
        assert passing not in result.stdout.str(), passing


COUNTRIES = """
from xippios.core import PackagedList, names_codes

COUNTRIES = PackagedList.model_validate(
    {
        "param": "countries",
        "endpoint": "lists",
        "fetched": "2026-10-23T09:00:00Z",
        "records": [{"countryCode": "CN", "countryName": "Comoros"}],
    }
).codes("countryCode", "countryName")
"""

WITH_A_COUNTRY = TASKS.replace(
    "async def get_series_async(series_id: str, year",
    'async def get_series_async(series_id: str, country_code: str = "CN", year',
)


def test_a_task_that_takes_a_country_fails_at_once_until_its_answer_names_it(
    pytester: pytest.Pytester,
) -> None:
    # ADR-0056: no release warns first (https://github.com/xippios/sdk-core/issues/359, part 4).
    unnamed = run_family(pytester, {"src/xippios/example/tasks.py": COUNTRIES + WITH_A_COUNTRY})
    unnamed.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    unnamed.stdout.fnmatch_lines(
        [
            "*test_family_country_codes_are_named_in_the_answer*",
            "*- tasks.get_series takes country_code, which names_codes does not name and "
            "UNNAMED_CODES does not exempt*",
        ]
    )
    named = COUNTRIES + WITH_A_COUNTRY.replace(
        "async def get_series_async",
        "@names_codes(country_code=COUNTRIES)\nasync def get_series_async",
    )
    run_family(pytester, {"src/xippios/example/tasks.py": named}).assert_outcomes(
        passed=FAMILY_TESTS
    )


def test_two_packages_with_a_tasks_py_fail_every_check_naming_both(
    pytester: pytest.Pytester,
) -> None:
    # The ini option xippios_package, which named one of them, left in 0.5.0: no source set
    # it (https://github.com/xippios/sdk-core/issues/475, part 7).
    second: dict[str, str | None] = {"src/xippios/other/tasks.py": "__all__: list[str] = []\n"}
    result = run_family(pytester, second)
    result.assert_outcomes(errors=FAMILY_TESTS)
    result.stdout.fnmatch_lines(
        ["*one package with a tasks.py under src/xippios/, found*example/tasks.py*other/tasks.py*"]
    )
    assert "ini option" not in result.stdout.str()


def test_an_adapter_that_drops_a_task_fails_naming_it(pytester: pytest.Pytester) -> None:
    dropped = SOURCE["src/xippios/example/mcp.py"].replace(
        SERVED, "[tasks.get_series, tasks.search_series]"
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
    # A task that takes offset itself cannot be paged: the tool set refuses it as it is built,
    # so mcp.py does not import, which the tools' test and the package contract's both meet.
    own = TASKS.replace("(series_id: str, year: int = 2024)", "(series_id: str, offset: int = 0)")
    result = run_family(
        pytester, {"src/xippios/example/mcp.py": paged, "src/xippios/example/tasks.py": own}
    )
    result.assert_outcomes(passed=FAMILY_TESTS - 2, failed=2)
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
        '__all__ = ["search_series", "get_series", "list_regions"]',
        "async def download_series_async(series_id: str) -> Result[list[int]]:\n"
        '    """Download every year of one series.\n\n    Args:\n'
        '        series_id: Upstream identifier, e.g. ``"CORN"``.\n    """\n'
        "    return Result[list[int]](data=[], meta=META)\n\n\n"
        "download_series = sync(download_series_async)\n"
        'BULK_TASKS = frozenset({"download_series"})\n'
        '__all__ = ["download_series", "search_series", "get_series", "list_regions"]',
    )
    table = README.replace(
        "| `regions` |",
        "| `bulk` | `download_series(series_id)` | none: Python only | alpha |\n| `regions` |",
    )
    changes: dict[str, str | None] = {"src/xippios/example/tasks.py": bulk, "README.md": table}
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS)
    # A tool set leaves it out and router_from_tasks skips it (ADR-0040, decision 4).
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
        .replace("search_series = sync(search_series_async)", "search_series = search_series_async")
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
            "*- tasks.search_series is async; list the sync function sync() derives from it*",
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


def test_a_read_task_without_a_read_verb_fails_naming_it(pytester: pytest.Pytester) -> None:
    # ADR-0061, decision 3: a read task is list_, get_, search_, count_ or download_.
    found = TASKS.replace("search_series", "find_series")
    table = README.replace("search_series", "find_series")
    result = run_family(pytester, {"src/xippios/example/tasks.py": found, "README.md": table})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*every read task's name starts with list_, get_, search_, count_ or download_ "
            "(conventions §1, ADR-0061, decision 3):*",
            "*- tasks.find_series starts with none of them*",
        ]
    )
    # A verb alone is no name, and a verb that runs into its noun is no verb.
    bare = TASKS.replace("search_series", "get_").replace("list_regions", "listregions")
    rows = README.replace("search_series", "get_").replace("list_regions", "listregions")
    result = run_family(pytester, {"src/xippios/example/tasks.py": bare, "README.md": rows})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*- tasks.get_ starts with none of them*",
            "*- tasks.listregions starts with none of them*",
        ]
    )


READINGS = '''
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, computed_field


class Region(BaseModel):
    """The region of an observation: its code with its label, and its printed level."""

    code: int
    code_label: str
    level: float
    level_number: Decimal | None = None


class Observation(BaseModel):
    """One observation: upstream's printed value, and the number read from it beside it."""

    value: Annotated[str, Field(validation_alias="Value")]
    value_number: Decimal | None = None
    street_number: str | None = None
    region: Region

    @computed_field  # type: ignore[prop-decorator]
    @property
    def period_number(self) -> int:
        """Upstream's own name: the model holds no field period."""
        return 2024
'''

WITH_READINGS = READINGS + TASKS.replace(
    "async def get_series_async(series_id: str, year: int = 2024) -> Result[list[int]]:",
    "async def get_series_async(series_id: str, year: int = 2024) -> Result[list[Observation]]:",
)


def test_a_reading_beside_a_stem_that_holds_no_text_fails_naming_it(
    pytester: pytest.Pytester,
) -> None:
    # ADR-0060, decision 9: the check reaches Region through Observation's field, fails both
    # suffixes beside a stem that holds no text (https://github.com/xippios/sdk-core/issues/474,
    # part 10), and passes street_number and period_number, whose part before the suffix names
    # no field.
    result = run_family(pytester, {"src/xippios/example/tasks.py": WITH_READINGS})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*a reading <stem>_number or <stem>_label stands beside a text field <stem> of its "
            "model; a name whose part before the suffix names no field is upstream's own and "
            "passes (conventions §3, ADR-0060, decisions 7 and 9):*",
            "*- Region.code_label stands beside code, which holds int*",
            "*- Region.level_number stands beside level, which holds float*",
        ]
    )
    text = WITH_READINGS.replace("    code: int\n", "    code: str | None\n").replace(
        "    level: float\n", "    level: str | None\n"
    )
    result = run_family(pytester, {"src/xippios/example/tasks.py": text})
    result.assert_outcomes(passed=FAMILY_TESTS)


class Kind(str):
    """A text of its own kind, as a value set's members are texts."""


@pytest.mark.parametrize(
    ("annotation", "text"),
    [
        (str, True),
        (str | None, True),
        (Annotated[str | None, "a note"], True),
        (Kind, True),
        (Kind | None, True),
        (int, False),
        (float | None, False),
        (str | int, False),
        (list[str], False),
        (None, False),
    ],
)
def test_text_is_a_str_or_a_subclass_none_allowed_beside_it(annotation: Any, text: bool) -> None:
    assert family._holds_text(annotation) is text


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


def test_write_tasks_are_checked_and_listed_and_the_write_server_built(
    pytester: pytest.Pytester,
) -> None:
    # The tools of the write server are its source's to test with assert_write_tools
    # (ADR-0042, decision 1); the family check holds mcp_write.build() and the entry points
    # alone (ADR-0063, decision 8).
    write: dict[str, str | None] = {
        "src/xippios/example/tasks_write.py": WRITE_TASKS,
        **WRITE_SERVER,
    }
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
    assert _status_table_tasks(README) == ["get_series", "search_series", "list_regions"]
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
ENV_VARS = ()
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


async def list_regions_async(org: str) -> Result[list[str]]:
    """List the regions a series can be asked for, the same for every organisation.

    Args:
        org: A declared organisation, e.g. ``demo``.
    """
    meta = ResultMeta(source="example", endpoint="regions", tenant=org)
    return Result[list[str]](data=[], meta=meta)


get_series = sync(get_series_async)
list_regions = sync(list_regions_async)
list_organisations = list_task(TENANTS, name="list_organisations")

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


async def rename_series_async(org: str, name: str, confirm: bool = False) -> Result[str]:
    """Rename a series, or preview it unless confirmed.

    Args:
        org: A declared organisation, e.g. ``demo``.
        name: The series name, e.g. ``"corn"``.
        confirm: ``True`` writes; ``False`` previews.
    """
    meta = ResultMeta(source="example", endpoint="rename", tenant=org)
    return Result[str](data=name, meta=meta)


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
| `regions` | `list_regions(org)` | `example_list_regions` | alpha |
| `create`, `rename` | `create_series`, `rename_series` | write server | alpha |
"""

TENANT_SOURCE: dict[str, str | None] = {
    "src/xippios/example/_client.py": TENANT_CLIENT,
    "src/xippios/example/tasks.py": TENANT_TASKS,
    "README.md": TENANT_README,
}


def test_a_multi_tenant_source_passes_with_its_tenant_list(pytester: pytest.Pytester) -> None:
    """Every task takes ``org`` but the tenant list, read and write alike."""
    write = {"src/xippios/example/tasks_write.py": TENANT_WRITE_TASKS, **WRITE_SERVER}
    result = run_family(pytester, {**TENANT_SOURCE, **write})
    result.assert_outcomes(passed=FAMILY_TESTS)


def _untenanted(text: str, task: str, endpoint: str) -> str:
    """``text`` with ``task`` taking no ``org``, as a task that touches no tenant would."""
    for given, taken in (
        (f"{task}_async(org: str, ", f"{task}_async("),
        (f"{task}_async(org: str)", f"{task}_async()"),
        (f'endpoint="{endpoint}", tenant=org', f'endpoint="{endpoint}"'),
    ):
        text = text.replace(given, taken)
    return text


def test_a_task_of_a_multi_tenant_source_that_takes_no_tenant_fails_naming_it(
    pytester: pytest.Pytester,
) -> None:
    """The source opts into nothing: a ``Tenants`` registry makes it multi-tenant.

    A task its module names in ``NO_TENANT_TASKS`` fails as any other: the declaration left
    core in 0.5.0 (ADR-0036, amendment 2026-11-24).
    """
    regions = _untenanted(TENANT_TASKS, "list_regions", "regions")
    declared = regions + 'NO_TENANT_TASKS = frozenset({"list_regions"})\n'
    rename = _untenanted(TENANT_WRITE_TASKS, "rename_series", "rename")
    changes = {
        **TENANT_SOURCE,
        **WRITE_SERVER,
        "src/xippios/example/tasks.py": declared,
        "src/xippios/example/tasks_write.py": rename,
    }
    result = run_family(pytester, changes)
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*every task of a multi-tenant source takes exactly one tenant, org, the parameter "
            "its Tenants registry declares, required, the tenant list excepted (conventions §7):",
            "*- tasks.list_regions takes no org*",
            "*- tasks_write.rename_series takes no org*",
        ]
    )
    # A registry its tasks module holds, imported or its own, makes it multi-tenant too.
    own = regions.replace(
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


def test_the_tenant_list_and_an_annotated_tenant_pass(tenant_forms: ModuleType) -> None:
    # get_one takes org first, get_two last: the registry names it, not its place.
    _tenant_family(tenant_forms, ["get_one", "get_two", "list_orgs"])


def test_the_tenant_parameter_is_the_one_the_registry_declares(tenant_forms: ModuleType) -> None:
    """The review's probe: the tasks share invoice_id, yet the registry declares org."""
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_invoice", "get_journal", "list_orgs"])
    assert str(failed.value).splitlines()[1:] == ["- tasks.get_journal takes no org"]
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_one", "list_orgs"], registry="ACCOUNTS")
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
        _tenant_family(tenant_forms, ["get_one", "list_orgs", task])
    assert str(failed.value).splitlines()[1:] == [f"- {problem}"]


def test_a_declaration_beside_the_tasks_excepts_nothing_and_one_tenant_checks_nothing(
    tenant_forms: ModuleType,
) -> None:
    """``NO_TENANT_TASKS`` is read no more: neither its tasks nor its stale names count."""
    declared = frozenset({"list_regions", "list_old_regions"})
    tenant_forms.NO_TENANT_TASKS = declared  # type: ignore[attr-defined]
    with pytest.raises(pytest.fail.Exception) as failed:
        _tenant_family(tenant_forms, ["get_one", "list_regions"])
    assert str(failed.value).splitlines()[1:] == ["- tasks.list_regions takes no org"]
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


COLLECTING = "from xippios.core.testing.live import *  # noqa: F403\n"
UNREAD = "so the family check cannot read its LIVE_LISTS and NO_LIVE_LIST"
IMPORT_OFFLINE = "make it import offline, as pytest's collection imports it"
SKIP_INSIDE = (
    "skip in the tests or the fixtures that need what is missing, pytest.importorskip among "
    "them, and keep the module's top level importable offline"
)


def broken_at_import(statement: str) -> str:
    """The declaration with ``statement`` run at the module's top level, after its imports."""
    module = DECLARATION.format(live=COMPARED, no_live=EXCUSED)
    return module.replace(COLLECTING, f"{COLLECTING}\nimport pytest\n\n{statement}\n")


@pytest.mark.parametrize(
    ("statement", "problem"),
    [
        (
            "MISSING_NAME",
            f"tests/test_live.py does not import, {UNREAD} (NameError: name 'MISSING_NAME' is not "
            f"defined): {IMPORT_OFFLINE}",
        ),
        # pytest's outcomes are no Exception: a skip once let the check report skipped.
        (
            'pytest.skip("no key in this shell", allow_module_level=True)',
            f"tests/test_live.py skips at its import, {UNREAD} (Skipped: no key in this shell): "
            f"{SKIP_INSIDE}",
        ),
        (
            'pytest.importorskip("xippios_no_such_module")',
            f"tests/test_live.py skips at its import, {UNREAD} (Skipped: could not import "
            f"'xippios_no_such_module': No module named 'xippios_no_such_module'): {SKIP_INSIDE}",
        ),
        (
            'pytest.fail("not here", pytrace=False)',
            f"tests/test_live.py does not import, {UNREAD} (Failed: not here): {IMPORT_OFFLINE}",
        ),
        (
            'pytest.xfail("not yet")',
            f"tests/test_live.py does not import, {UNREAD} (XFailed: not yet): {IMPORT_OFFLINE}",
        ),
        (
            'pytest.exit("stop", returncode=3)',
            f"tests/test_live.py does not import, {UNREAD} (Exit: stop): {IMPORT_OFFLINE}",
        ),
        (
            "import sys\nsys.exit(2)",
            f"tests/test_live.py exits at its import, {UNREAD} (SystemExit: 2): remove the exit "
            "from its top level",
        ),
    ],
    ids=["error", "skip", "importorskip", "fail", "xfail", "pytest-exit", "sys-exit"],
)
def test_a_live_test_module_that_does_not_load_fails_saying_why_and_what_to_do(
    tmp_path: Path, statement: str, problem: str
) -> None:
    """Whatever ends the module's import, the check fails: it is never skipped (sdk-core#359)."""
    files = {**LISTS_TREE, "tests/test_live.py": broken_at_import(statement)}
    assert live_problems(tmp_path, files) == [f"- {problem}"]


def test_an_interrupt_while_the_live_module_loads_stops_the_run(tmp_path: Path) -> None:
    """A keyboard interrupt is the person's, not the module's: it is not read as a problem."""
    _write(
        tmp_path, {**LISTS_TREE, "tests/test_live.py": broken_at_import("raise KeyboardInterrupt")}
    )
    with pytest.raises(KeyboardInterrupt):
        family.test_family_every_packaged_list_is_declared_for_the_live_run(_rooted(tmp_path))


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
    # A live module that skips at its import skips its own tests, and the family check fails,
    # so CI goes red where it stayed green (https://github.com/xippios/sdk-core/issues/359).
    skipping = broken_at_import('pytest.skip("no key in this shell", allow_module_level=True)')
    result = run_family(pytester, {**tree, "tests/test_live.py": skipping})
    result.assert_outcomes(passed=FAMILY_TESTS - 1, failed=1, skipped=1)
    result.stdout.fnmatch_lines([f"*- tests/test_live.py skips at its import, {UNREAD}*"])
