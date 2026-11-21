"""The family conformance check: what every source package shares, tested once, in core.

A source collects these tests with one line, in the ``tests/test_family.py`` that
sdk-template renders::

    from xippios.core.testing.family import *  # noqa: F403

The star import puts the ``test_family_*`` functions and their ``family_source`` fixture
into that module, where pytest collects them; a check added in a later core release
reaches every source with the core update and no change to the file. The plugin
(``pytest_plugins = ["xippios.core.testing.plugin"]``) must be enabled, as it is in every
source, since it registers the ini option below.

**The package under test** is the ini option ``xippios_package``, its import path
(``xippios_package = "xippios.usda.psd"`` under ``[tool.pytest.ini_options]``). Unset, it
is the one package with a ``tasks.py`` under ``<rootdir>/src/xippios/``, the layout every
source has (``src/xippios/usda/psd/tasks.py`` gives ``xippios.usda.psd``); none or more
than one fails every test here, naming the option. The repository's files (``README.md``,
``.copier-answers.yml``, ``pyproject.toml``) are read from pytest's rootdir.

**What is checked**, one test each:

- the namespace levels above the package (``xippios/``, ``xippios/usda/``) hold no
  ``__init__.py``, and the package ships ``py.typed`` and a ``__version__`` (ADR-0006);
- ``mcp.py``'s ``server`` registers exactly ``tasks.__all__`` minus
  ``getattr(tasks, "BULK_TASKS", frozenset())``, each tool taking its task's parameters
  and described by its docstring (conventions §8, ADR-0040);
- ``http.py``'s ``router`` routes the same tasks at ``/<source>/<task>``, ``GET`` when
  every parameter is a scalar and ``POST`` otherwise (conventions §9, ADR-0007);
- every task, read and write, is a synchronous function returning ``Result[T]``
  (conventions §2, §6) whose docstring is a one-sentence first line and, when it takes
  parameters, an ``Args:`` block (conventions §8); no ``async_fn`` is required, since
  conventions §6 makes the async variant optional;
- ``README.md``'s status table lists exactly ``tasks.__all__`` plus
  ``tasks_write.__all__``, a source's write tasks included (conventions §13), in the format
  of sdk-template's ``README.md.jinja``: the tables under the ``## Status`` heading whose
  header row has a ``Task function`` column; that cell starts with the task's name in
  backticks, alone, with its call (``get_data(commodity_code, market_year)``) or as
  ``tasks.get_data(...)``, several tasks of one row as backticked names separated by
  commas; whatever follows the first non-backticked text is prose;
- ``.copier-answers.yml`` names a template tag, ``_commit: vX.Y.Z`` (conventions §15);
- ``pyproject.toml`` bounds ``xippios-core`` and each of its extras to one minor,
  ``~=X.Y.Z``, all alike (conventions §12, ADR-0039);
- every task, read and write, of a multi-tenant source, one whose ``_client``, ``tasks``
  or ``tasks_write`` module holds a ``Tenants`` registry, takes exactly one tenant: the
  parameter the registry declares, ``Tenants(..., param="org")``, with no default,
  annotated ``str`` or ``Annotated[str, ...]``, neither ``*`` nor ``**``; the tenant list
  of ``list_task`` and the tasks its module names in ``NO_TENANT_TASKS`` are excepted,
  and ``NO_TENANT_TASKS`` names tasks of that module's ``__all__`` alone (conventions §7;
  ADR-0036, decision 13). A source with no ``Tenants`` registry passes. The check reads
  signatures: what a task reaches inside is the review's
  (https://github.com/xippios/sdk-core/issues/302);
- a source that keeps ``docs/upstream/OBSERVED.md``, the notes of what it observed of
  upstream, is held to three rules of it, one test each, and a source without the file
  passes all three (conventions §3, ADR-0044). ``FETCHED.md`` lists the file in a row of
  its own: a table row whose first cell is ``OBSERVED.md``, whose last cell says that it is
  written by hand and whose cells between, at any width, are ``-``. The file holds one note
  at least, a ``###`` section, and the last paragraph of every note, its link reference
  definitions dropped, opens with ``Probe: <date>`` or ``Observed: <date>``, an ISO date
  (``Probe: 2026-11-20, ...``). Every code span of the file whose text starts with
  ``tests/``, ``docs/``, ``src/`` or ``scripts/``, holds no space and ends in an extension
  names a file that exists, from the repository's root.

A write server is its source's to test: the family check reads ``tasks_write`` for the
task checks and the status table only (ADR-0042).

**Two family checks are CI steps, not tests**, since they read the pull request rather
than the package; sdk-template's ``ci.yml`` carries them, on ``pull_request`` with the
whole history checked out (``fetch-depth: 0``, for ``git diff origin/<base>...HEAD``):
every pull request but Dependabot's (``dependabot/``, which writes no entry) brings its
changelog entry, a fragment it adds or changes under ``changelog/`` or a change of
``CHANGELOG.md``, a release's and an adoption's included (conventions §12, §15, the
definition of done); and the fixture files it adds or changes under ``tests/fixtures/``
stay under 256 KiB, a fixture it only moves being neither, one moved and changed judged
under its new path (ADR-0040). The cap binds a source from its 0.3.0 adoption
(conventions, header of 1.14), so the step warns in template v0.2.1 and fails from v0.3.0.
"""

import importlib
import importlib.util
import inspect
import re
import tomllib
import typing
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from xippios.core._tasks import touches_no_tenant
from xippios.core.models import Result
from xippios.core.tenants import Tenants, _lists_tenants
from xippios.core.testing.plugin import PACKAGE_INI

__all__ = [
    "family_source",
    "test_family_copier_answers_name_a_template_tag",
    "test_family_core_is_bound_to_one_minor",
    "test_family_fetched_md_lists_observed_md_in_a_row_of_its_own",
    "test_family_http_router_routes_the_tasks",
    "test_family_mcp_server_registers_the_tasks",
    "test_family_namespace_levels_are_empty",
    "test_family_observed_md_cites_files_that_exist",
    "test_family_observed_notes_end_with_their_probe_and_date",
    "test_family_package_has_a_version",
    "test_family_package_ships_py_typed",
    "test_family_readme_status_table_lists_the_tasks",
    "test_family_tasks_carry_agent_docstrings",
    "test_family_tasks_return_results",
    "test_family_tasks_take_one_tenant",
]

_TAG = re.compile(r"v\d+\.\d+\.\d+")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_SPAN = re.compile(r"`([^`]+)`")
_TASK_SPAN = re.compile(r"(?:tasks(?:_write)?\.)?([A-Za-z_]\w*)(?:\(.*\))?")
_OBSERVED = "docs/upstream/OBSERVED.md"
_FETCHED = "docs/upstream/FETCHED.md"
_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r" {0,3}(#{1,6})(?:[ \t]+(.*))?$")
_REFERENCE = re.compile(r" {0,3}\[[^\]]+\]:[ \t]*\S")
"""A link reference definition, which renders as nothing and is no paragraph of a note."""
_PROBE = re.compile(r"(?:Probe|Observed): (\d{4}-\d{2}-\d{2})(?!\d)")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_CITED = re.compile(r"(?:tests|docs|src|scripts)/[^\s`]+\.[A-Za-z][A-Za-z0-9]*")
"""A path a code span of ``OBSERVED.md`` cites a file by, from the repository's root."""


@dataclass(frozen=True)
class FamilySource:
    """The source package under test and the repository around it.

    Attributes:
        root: pytest's rootdir, the repository root.
        import_path: The package's import path, e.g. ``"xippios.usda.psd"``.
        package: The package module.
        source: The source slug, ``_client.SOURCE``, e.g. ``"usda-psd"``.
        tasks: The ``tasks`` module.
        tasks_write: The ``tasks_write`` module, or ``None`` for a read-only source.
        tenants: The ``Tenants`` registry of a multi-tenant source, which its ``_client``,
            ``tasks`` or ``tasks_write`` module holds, ``_client.TENANTS`` say; ``None``
            for a source with none.
    """

    root: Path
    import_path: str
    package: ModuleType
    source: str
    tasks: ModuleType
    tasks_write: ModuleType | None
    tenants: Tenants | None = None

    @property
    def package_dir(self) -> Path:
        """The package's directory, from its ``__init__.py``."""
        return Path(self.package.__file__ or "").parent

    def read_tasks(self) -> dict[str, Callable[..., Any]]:
        """``tasks.__all__`` by name; a listed name the module lacks fails the test."""
        return _named(self.tasks)

    def write_tasks(self) -> dict[str, Callable[..., Any]]:
        """``tasks_write.__all__`` by name, empty for a read-only source."""
        return {} if self.tasks_write is None else _named(self.tasks_write)

    def bulk_tasks(self) -> frozenset[str]:
        """``tasks.BULK_TASKS``, the tasks the adapters skip (ADR-0040); empty if absent."""
        return frozenset(getattr(self.tasks, "BULK_TASKS", frozenset()))


def _named(module: ModuleType) -> dict[str, Callable[..., Any]]:
    names = list(getattr(module, "__all__", []))
    missing = [name for name in names if not hasattr(module, name)]
    if missing:
        pytest.fail(f"{module.__name__}.__all__ names what it lacks: {missing}", pytrace=False)
    return {name: getattr(module, name) for name in names}


def _import_path(config: pytest.Config) -> str:
    try:
        configured = str(config.getini(PACKAGE_INI) or "").strip()
    except ValueError:  # the plugin is not enabled, so the option is unknown
        configured = ""
    if configured:
        return configured
    src = config.rootpath / "src"
    found = sorted(path.parent for path in (src / "xippios").rglob("tasks.py"))
    if len(found) != 1:
        where = [str((path / "tasks.py").relative_to(config.rootpath)) for path in found]
        pytest.fail(
            f"the family check needs one package with a tasks.py under src/xippios/, found "
            f"{where or 'none'}; name it with the ini option {PACKAGE_INI} "
            '(e.g. xippios_package = "xippios.usda.psd")',
            pytrace=False,
        )
    return ".".join(found[0].relative_to(src).parts)


@pytest.fixture(scope="module")
def family_source(request: pytest.FixtureRequest) -> FamilySource:
    """The source package the family check tests, found as the module docstring says."""
    import_path = _import_path(request.config)
    package = importlib.import_module(import_path)
    client = importlib.import_module(f"{import_path}._client")
    has_write = importlib.util.find_spec(f"{import_path}.tasks_write") is not None
    tasks = importlib.import_module(f"{import_path}.tasks")
    tasks_write = importlib.import_module(f"{import_path}.tasks_write") if has_write else None
    registries = [
        value
        for module in filter(None, [client, tasks, tasks_write])
        for value in vars(module).values()
        if isinstance(value, Tenants)
    ]
    return FamilySource(
        root=request.config.rootpath,
        import_path=import_path,
        package=package,
        source=client.SOURCE,
        tasks=tasks,
        tasks_write=tasks_write,
        tenants=registries[0] if registries else None,
    )


def _fail(problems: list[str], intro: str) -> None:
    if problems:
        pytest.fail("\n".join([intro, *(f"- {problem}" for problem in problems)]), pytrace=False)


def _parameters(fn: Callable[..., Any]) -> dict[str, Any]:
    hints = typing.get_type_hints(fn)
    parameters = inspect.signature(fn).parameters.values()
    return {p.name: hints.get(p.name, p.annotation) for p in parameters}


def _served(family: FamilySource) -> dict[str, Callable[..., Any]]:
    """The read tasks the adapters register: ``tasks.__all__`` minus ``BULK_TASKS``."""
    tasks = family.read_tasks()
    unknown = sorted(family.bulk_tasks() - tasks.keys())
    _fail([f"BULK_TASKS names {unknown}, not in tasks.__all__"] if unknown else [], "BULK_TASKS:")
    return {name: fn for name, fn in tasks.items() if name not in family.bulk_tasks()}


def test_family_namespace_levels_are_empty(family_source: FamilySource) -> None:
    """Every level from the package up to ``xippios/`` stays a namespace portion (ADR-0006)."""
    levels = list(family_source.package_dir.parents)
    names = [level.name for level in levels]
    if "xippios" not in names:
        pytest.fail(f"no xippios directory above {family_source.package_dir}", pytrace=False)
    filled = [
        str(level / "__init__.py")
        for level in levels[: names.index("xippios") + 1]
        if (level / "__init__.py").exists()
    ]
    _fail(filled, "namespace levels must stay empty; delete:")


def test_family_package_ships_py_typed(family_source: FamilySource) -> None:
    """The package ships its PEP 561 marker, or mypy --strict fails in its consumers."""
    marker = family_source.package_dir / "py.typed"
    if not marker.is_file():
        pytest.fail(f"{marker} is missing", pytrace=False)


def test_family_package_has_a_version(family_source: FamilySource) -> None:
    """``xippios.<source>.__version__`` is set, from the distribution's metadata."""
    if not getattr(family_source.package, "__version__", None):
        pytest.fail(f"{family_source.import_path}.__version__ is not set", pytrace=False)


def test_family_mcp_server_registers_the_tasks(family_source: FamilySource) -> None:
    """``mcp.server`` has exactly one tool per task in ``tasks.__all__`` minus ``BULK_TASKS``.

    Each tool takes its task's parameters and carries its docstring (conventions §8,
    ADR-0040).
    """
    from xippios.core._loop import run
    from xippios.core.mcp import tool_name

    server = importlib.import_module(f"{family_source.import_path}.mcp").server
    tools = {tool.name: tool for tool in run(server.list_tools())}
    expected = {
        tool_name(family_source.source, fn): (name, fn)
        for name, fn in _served(family_source).items()
    }
    problems = [f"missing tool {name}" for name in sorted(expected.keys() - tools.keys())]
    problems += [
        f"tool {name} serves no task of tasks.__all__ minus BULK_TASKS"
        for name in sorted(tools.keys() - expected.keys())
    ]
    for tool, (name, fn) in sorted(expected.items()):
        if tool not in tools:
            continue
        listed = set(tools[tool].input_schema.get("properties", {}))
        if listed != set(_parameters(fn)):
            problems.append(
                f"{tool} takes {sorted(listed)}, {name} takes {sorted(_parameters(fn))}"
            )
        if not tools[tool].description:
            problems.append(f"{tool} has no description: write {name}'s docstring")
    _fail(problems, "mcp.py must register exactly tasks.__all__ minus BULK_TASKS:")


def test_family_http_router_routes_the_tasks(family_source: FamilySource) -> None:
    """``http.router`` routes exactly the MCP server's tasks at ``/<source>/<task>``.

    ``GET`` with query parameters when every parameter is a scalar, ``POST`` with a JSON
    body otherwise (conventions §9, ADR-0007).
    """
    from fastapi.routing import APIRoute

    from xippios.core.http import is_scalar

    router = importlib.import_module(f"{family_source.import_path}.http").router
    routes = {route.path: route for route in router.routes if isinstance(route, APIRoute)}
    expected = {
        f"/{family_source.source}/{fn.__name__}": (name, fn)
        for name, fn in _served(family_source).items()
    }
    problems = [f"missing route {path}" for path in sorted(expected.keys() - routes.keys())]
    problems += [
        f"route {path} serves no task of tasks.__all__ minus BULK_TASKS"
        for path in sorted(routes.keys() - expected.keys())
    ]
    for path, (name, fn) in sorted(expected.items()):
        if path not in routes:
            continue
        scalar = all(is_scalar(annotation) for annotation in _parameters(fn).values())
        method = {"GET"} if scalar else {"POST"}
        answered = set(routes[path].methods or ())
        if answered != method:
            problems.append(f"{path} answers {sorted(answered)}, {name} needs {sorted(method)}")
    _fail(problems, "http.py must route exactly tasks.__all__ minus BULK_TASKS:")


def _every_task(family: FamilySource) -> dict[str, Callable[..., Any]]:
    tasks = {f"tasks.{name}": fn for name, fn in family.read_tasks().items()}
    tasks.update({f"tasks_write.{name}": fn for name, fn in family.write_tasks().items()})
    return tasks


def test_family_tasks_return_results(family_source: FamilySource) -> None:
    """Every task is a synchronous function annotated to return ``Result[T]``.

    Sources expose sync functions (conventions §6); every task returns the envelope with
    its metadata (conventions §2, §4). An ``async_fn`` is not required: conventions §6
    makes the async variant optional.
    """
    problems = []
    for name, fn in _every_task(family_source).items():
        if inspect.iscoroutinefunction(fn):
            problems.append(f"{name} is async; list the sync function sync() derives from it")
            continue
        try:
            returned = typing.get_type_hints(fn).get("return")
        except Exception as exc:  # an annotation that does not resolve
            problems.append(f"{name}: its annotations do not resolve ({type(exc).__name__}: {exc})")
            continue
        if not (
            isinstance(returned, type) and issubclass(returned, Result) and returned is not Result
        ):
            problems.append(f"{name} returns {returned!r}, not Result[T]")
    _fail(problems, "every task returns Result[T]:")


def test_family_tasks_carry_agent_docstrings(family_source: FamilySource) -> None:
    """Every task's docstring opens with one sentence and explains its parameters.

    The docstring is the tool description agents read: a first line that ends with a full
    stop, and an ``Args:`` block when the task takes parameters (conventions §8).
    """
    problems = []
    for name, fn in _every_task(family_source).items():
        doc = inspect.getdoc(fn) or ""
        if not doc:
            problems.append(f"{name} has no docstring")
            continue
        if not doc.splitlines()[0].rstrip().endswith("."):
            problems.append(f"{name}: the first line is one sentence ending with a full stop")
        if inspect.signature(fn).parameters and "Args:" not in doc:
            problems.append(f"{name}: explain every parameter under Args: with valid values")
    _fail(problems, "task docstrings are written for agents:")


def _one_tenant_problem(fn: Callable[..., Any], param: str) -> str | None:
    """Why ``fn`` does not take exactly one tenant as ``param``, or ``None`` when it does."""
    parameter = inspect.signature(fn).parameters.get(param)
    if parameter is None:
        return f"takes no {param}"
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        return f"takes *{param}, several tenants"
    if parameter.kind is inspect.Parameter.VAR_KEYWORD:
        return f"takes **{param}, several tenants"
    if parameter.default is not inspect.Parameter.empty:
        return f"gives {param} the default {parameter.default!r}; the tenant is required"
    try:
        annotation = typing.get_type_hints(fn, include_extras=True).get(param)
    except Exception:  # an annotation that does not resolve
        return "has annotations that do not resolve"
    if typing.get_origin(annotation) is typing.Annotated:
        annotation = typing.get_args(annotation)[0]
    if not (
        typing.get_origin(annotation) is None
        and isinstance(annotation, type)
        and issubclass(annotation, str)
    ):
        shown = annotation.__name__ if isinstance(annotation, type) else repr(annotation)
        return f"takes {param} as {shown}, not one tenant's name, a str"
    return None


def test_family_tasks_take_one_tenant(family_source: FamilySource) -> None:
    """Every task of a multi-tenant source takes exactly one tenant, required (conventions §7).

    A source whose ``_client``, ``tasks`` or ``tasks_write`` module holds a ``Tenants``
    registry is multi-tenant, with no opt-in: every task of ``tasks.__all__`` and
    ``tasks_write.__all__`` takes the parameter the registry declares, ``tenants.param``,
    once, with no default, of a type that names one tenant, a ``str``, except the tenant
    list and the tasks its module names in ``NO_TENANT_TASKS``, which touch no tenant
    (ADR-0036, decision 13).
    """
    if family_source.tenants is None:
        return
    problems: list[str] = []
    for module in filter(None, [family_source.tasks, family_source.tasks_write]):
        unknown = sorted(
            set(getattr(module, "NO_TENANT_TASKS", ())) - set(getattr(module, "__all__", ()))
        )
        if unknown:
            problems.append(
                f"NO_TENANT_TASKS of {module.__name__} names {unknown}, not in its __all__"
            )
    param = family_source.tenants.param
    for name, fn in _every_task(family_source).items():
        if _lists_tenants(fn) or touches_no_tenant(fn):
            continue
        problem = _one_tenant_problem(fn, param)
        if problem is not None:
            problems.append(f"{name} {problem}")
    _fail(
        problems,
        f"every task of a multi-tenant source takes exactly one tenant, {param}, the parameter "
        "its Tenants registry declares, required; the tenant list and the tasks named in "
        "NO_TENANT_TASKS of their module are excepted (conventions §7):",
    )


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in _CELL_SPLIT.split(line.strip().strip("|"))]


def _cell_tasks(cell: str) -> list[str]:
    """The task names a ``Task function`` cell starts with; see the module docstring."""
    names: list[str] = []
    rest = cell.strip()
    while (span := _SPAN.match(rest)) is not None:
        name = _TASK_SPAN.fullmatch(span.group(1).strip())
        if name is None:
            break
        names.append(name.group(1))
        rest = rest[span.end() :].lstrip()
        if not rest.startswith(","):
            break
        rest = rest[1:].lstrip()
    return names


def _status_table_tasks(readme: str) -> list[str] | None:
    """The task names the ``## Status`` tables of a README list, or ``None`` without one.

    Every table under the ``## Status`` heading, up to the next ``## `` heading, whose
    header row has a ``Task function`` column counts; the format is the module
    docstring's.

    Args:
        readme: The README's text.
    """
    lines = readme.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "## Status"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    names: list[str] = []
    found = False
    column: int | None = None
    previous = ""
    for line in lines[start + 1 : end]:
        if not line.lstrip().startswith("|"):
            column, previous = None, ""
            continue
        cells = _cells(line)
        if column is None:
            if previous and all(set(cell) <= set("-: ") and cell for cell in cells):
                header = _cells(previous)
                column = header.index("Task function") if "Task function" in header else -1
                found = found or column >= 0
            previous = line
            continue
        if column >= 0 and column < len(cells):
            names.extend(_cell_tasks(cells[column]))
    return names if found else None


def test_family_readme_status_table_lists_the_tasks(family_source: FamilySource) -> None:
    """``README.md``'s status table lists exactly ``tasks.__all__`` and ``tasks_write.__all__``.

    A source with write tasks lists them in its table too, so the read and the write
    tasks together are expected. The format is sdk-template's ``README.md.jinja``: the
    tables under ``## Status`` with a ``Task function`` column, the task's name first in
    that cell, in backticks (the module docstring has the details; conventions §13).
    """
    readme = family_source.root / "README.md"
    if not readme.is_file():
        pytest.fail(f"{readme} is missing", pytrace=False)
    listed = _status_table_tasks(readme.read_text(encoding="utf-8"))
    if listed is None:
        pytest.fail(
            "README.md has no table with a 'Task function' column under '## Status' "
            "(sdk-template's README.md.jinja)",
            pytrace=False,
        )
    tasks = set(family_source.read_tasks()) | set(family_source.write_tasks())
    problems = [f"{name} is not in the table" for name in sorted(tasks - set(listed))]
    problems += [f"{name} is in the table but is no task" for name in sorted(set(listed) - tasks)]
    _fail(problems, "README.md's status table ('Task function' column) lists exactly the tasks:")


def test_family_copier_answers_name_a_template_tag(family_source: FamilySource) -> None:
    """``.copier-answers.yml``'s ``_commit`` is a template tag, ``vX.Y.Z`` (conventions §15).

    A commit between tags (``v0.2.0-3-g1a2b3c4``) or a branch is not a release a source
    can adopt or a reviewer can read.
    """
    answers = family_source.root / ".copier-answers.yml"
    if not answers.is_file():
        pytest.fail(f"{answers} is missing", pytrace=False)
    commit = None
    for line in answers.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(":")
        if key == "_commit":
            commit = value.strip().strip("'\"")
    if commit is None or _TAG.fullmatch(commit) is None:
        pytest.fail(
            f".copier-answers.yml: _commit is {commit!r}, not a template tag vX.Y.Z", pytrace=False
        )


def test_family_core_is_bound_to_one_minor(family_source: FamilySource) -> None:
    """``pyproject.toml`` bounds ``xippios-core`` and its extras to one minor, alike.

    ``~=X.Y.Z`` (``~=0.2.0``, or ``~=0.2.1`` when patch 1 shipped what the source adopts)
    in ``[project] dependencies`` and in every extra that names core (conventions §12,
    ADR-0039).
    """
    pyproject = tomllib.loads((family_source.root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject.get("project", {})
    lists = {"dependencies": project.get("dependencies", [])}
    lists.update(
        {
            f"optional-dependencies.{k}": v
            for k, v in project.get("optional-dependencies", {}).items()
        }
    )
    problems: list[str] = []
    bounds: set[str] = set()
    in_dependencies = False
    for where, requirements in lists.items():
        for text in requirements:
            try:
                requirement = Requirement(text)
            except InvalidRequirement as exc:
                problems.append(f"{where}: {text!r} does not parse ({exc})")
                continue
            if canonicalize_name(requirement.name) != "xippios-core":
                continue
            in_dependencies = in_dependencies or where == "dependencies"
            specifiers = list(requirement.specifier)
            if (
                len(specifiers) != 1
                or specifiers[0].operator != "~="
                or len(Version(specifiers[0].version).release) != 3
            ):
                problems.append(f"{where}: {text!r} is not bound to one minor with ~=X.Y.Z")
                continue
            bounds.add(specifiers[0].version)
    if not in_dependencies:
        problems.append("[project] dependencies does not name xippios-core")
    if len(bounds) > 1:
        problems.append(f"core and its extras name different bounds: {sorted(bounds)}")
    _fail(problems, "pyproject.toml must bound xippios-core to one minor:")


def _observed_text(family: FamilySource) -> str | None:
    """The source's ``docs/upstream/OBSERVED.md``, or ``None`` for a source without one."""
    path = family.root / _OBSERVED
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _lists_observed(fetched: str) -> bool:
    """Whether a ``FETCHED.md`` lists ``OBSERVED.md`` in a row of its own that says so.

    The row is a table row whose first cell is ``OBSERVED.md``, whose last cell says that
    the file is written by hand and whose cells between, if any, are ``-``, since nothing
    fetched it. It is told by these three and never by its width: the sources' tables are
    four, six and nine cells wide (ADR-0044, decision 1).

    Args:
        fetched: The text of ``docs/upstream/FETCHED.md``.
    """
    for line in fetched.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if (
            len(cells) >= 2
            and cells[0] == "OBSERVED.md"
            and all(cell == "-" for cell in cells[1:-1])
            and "written by hand" in cells[-1].lower()
        ):
            return True
    return False


def _paragraphs(lines: list[str]) -> list[str]:
    """The blocks of ``lines`` between blank lines, each one's lines joined by a space."""
    blocks = re.split(r"\n[ \t]*\n", "\n".join(lines))
    return [" ".join(block.split()) for block in blocks if block.strip()]


def _observed_notes(text: str) -> list[tuple[str, list[str]]]:
    """The notes of an ``OBSERVED.md``, each ``###`` section's heading and its paragraphs.

    A note runs from its ``###`` heading to the next heading of level one to three outside
    a fenced code block: a ``##`` heading groups notes and is none itself, and a ``####``
    heading stays inside its note. Link reference definitions are dropped, since they
    render as nothing, and two notes of one heading are two notes (ADR-0044, decision 2).

    Args:
        text: The text of ``docs/upstream/OBSERVED.md``.
    """
    notes: list[tuple[str, list[str]]] = []
    body: list[str] | None = None
    fence = ""
    for line in text.splitlines():
        marker = _FENCE.match(line)
        heading = _HEADING.match(line)
        if fence:
            # A fence closes on a run of its own character as long as its opening, or longer.
            if marker and marker.group(1).startswith(fence) and not line[marker.end() :].strip():
                fence = ""
        elif marker is not None:
            fence = marker.group(1)
        elif heading is not None and len(heading.group(1)) <= 3:
            body = [] if len(heading.group(1)) == 3 else None
            if body is not None:
                notes.append(((heading.group(2) or "").strip(), body))
            continue
        elif _REFERENCE.match(line):
            continue
        if body is not None:
            body.append(line)
    return [(title, _paragraphs(lines)) for title, lines in notes]


def _probe_problems(text: str) -> list[str]:
    """What fails the rule that every note ends with its probe and its date.

    The last paragraph of each note opens with ``Probe: `` or ``Observed: `` and an ISO
    date, ``YYYY-MM-DD``, right after the label, and the file holds one note at least
    (conventions §3, ADR-0044).

    Args:
        text: The text of ``docs/upstream/OBSERVED.md``.
    """
    notes = _observed_notes(text)
    if not notes:
        return ["the file holds no note"]
    problems: list[str] = []
    for heading, paragraphs in notes:
        if not paragraphs:
            problems.append(f"{heading}: no paragraph")
            continue
        last = paragraphs[-1]
        label = _PROBE.match(last)
        if label is None:
            opening = last if len(last) <= 40 else f"{last[:40]}..."
            problems.append(f"{heading}: its last paragraph opens {opening!r}")
            continue
        try:
            date.fromisoformat(label.group(1))
        except ValueError:
            problems.append(f"{heading}: {label.group(1)} is no date")
    return problems


def _missing_citations(text: str, root: Path) -> list[str]:
    """The files that the code spans of an ``OBSERVED.md`` cite and ``root`` lacks.

    A span cites a file when its text starts with ``tests/``, ``docs/``, ``src/`` or
    ``scripts/``, holds no space and ends in an extension, a path from the repository's
    root; every line of the file is read (conventions §3, ADR-0044).

    Args:
        text: The text of ``docs/upstream/OBSERVED.md``.
        root: The repository's root.
    """
    missing: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for span in _CODE_SPAN.finditer(line):
            path = span.group(2).strip()
            if _CITED.fullmatch(path) and not (root / path).is_file():
                missing.append(f"line {number}: {path}")
    return missing


def test_family_fetched_md_lists_observed_md_in_a_row_of_its_own(
    family_source: FamilySource,
) -> None:
    """``FETCHED.md`` lists ``OBSERVED.md`` in a row of its own that says so (conventions §3).

    A table row whose first cell is ``OBSERVED.md``, whose last cell says that it is written
    by hand and whose cells between are ``-``, at any width (ADR-0044). A source without
    ``docs/upstream/OBSERVED.md`` passes.
    """
    if _observed_text(family_source) is None:
        return
    fetched = family_source.root / _FETCHED
    if not fetched.is_file():
        pytest.fail(
            f"{_FETCHED} is missing: it lists OBSERVED.md in a row of its own "
            "(conventions §3, ADR-0044)",
            pytrace=False,
        )
    if not _lists_observed(fetched.read_text(encoding="utf-8")):
        pytest.fail(
            f"{_FETCHED} lists OBSERVED.md in no row of its own: write a row of its table "
            "whose first cell is OBSERVED.md, whose last cell says that it is written by hand "
            "and whose cells between are - (conventions §3, ADR-0044)",
            pytrace=False,
        )


def test_family_observed_notes_end_with_their_probe_and_date(family_source: FamilySource) -> None:
    """Every note of ``OBSERVED.md`` ends with its probe and its date (conventions §3).

    A note is a ``###`` section, and its last paragraph opens with ``Probe: <date>`` or
    ``Observed: <date>``, an ISO date; the file holds one note at least (ADR-0044). A source
    without ``docs/upstream/OBSERVED.md`` passes.
    """
    text = _observed_text(family_source)
    if text is None:
        return
    _fail(
        _probe_problems(text),
        f"{_OBSERVED}: every note, a ### section, ends with a paragraph that opens with "
        "'Probe: <date>' or 'Observed: <date>', the date as YYYY-MM-DD (conventions §3, "
        "ADR-0044):",
    )


def test_family_observed_md_cites_files_that_exist(family_source: FamilySource) -> None:
    """Every file that ``OBSERVED.md`` cites exists (conventions §3).

    A code span whose text starts with ``tests/``, ``docs/``, ``src/`` or ``scripts/``,
    holds no space and ends in an extension cites a file from the repository's root
    (ADR-0044). A source without ``docs/upstream/OBSERVED.md`` passes.
    """
    text = _observed_text(family_source)
    if text is None:
        return
    _fail(
        _missing_citations(text, family_source.root),
        f"{_OBSERVED} cites files that do not exist, from the repository's root "
        "(conventions §3, ADR-0044):",
    )
