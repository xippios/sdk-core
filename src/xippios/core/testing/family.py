"""The family conformance check: what every source package shares, tested once, in core.

A source collects these tests with one line, in the ``tests/test_family.py`` that
sdk-template renders::

    from xippios.core.testing.family import *  # noqa: F403

The star import puts the ``test_family_*`` functions and their ``family_source`` fixture
into that module, where pytest collects them; a check added in a later core release
reaches every source with the core update and no change to the file. The plugin
(``pytest_plugins = ["xippios.core.testing.plugin"]``) is enabled, as it is in every
source, so the checks run offline.

**The package under test** is the one package with a ``tasks.py`` under
``<rootdir>/src/xippios/``, the layout every source has (``src/xippios/example/tasks.py``
gives ``xippios.example``); none or more than one fails every test here, naming what it
found. The repository's files (``README.md``, ``.copier-answers.yml``, ``pyproject.toml``)
are read from pytest's rootdir.

**What is checked**, one test each:

- the namespace levels above the package (``xippios/`` and any between it and the package) hold no
  ``__init__.py``, and the package ships ``py.typed`` and a ``__version__`` (ADR-0006);
- ``mcp.py``'s ``server`` registers exactly ``tasks.__all__`` minus
  ``getattr(tasks, "BULK_TASKS", frozenset())``, each tool taking its task's parameters,
  a paged tool the adapter's ``offset`` beside them (ADR-0047), and described by the text
  of its docstring before ``Args:`` (conventions §8, ADR-0040);
- the package contract (conventions §8, ADR-0063, decision 8): ``mcp.build()`` returns a
  ``ToolSet`` of ``_client.SOURCE``, ``mcp.server`` lists the tools of
  ``build_server(mcp.build())``, and ``mcp.ENV_VARS`` is ``_client.ENV_VARS``, imported
  rather than copied; a source with ``tasks_write.py`` has ``mcp_write.py``, whose
  ``build()`` returns a tool set of the source that writes, while the tools of its write
  server are its own to test with ``assert_write_tools`` (ADR-0042, decision 1);
- ``pyproject.toml``'s ``[project.scripts]`` names the entry points of conventions §8,
  each at its module's ``run``: ``xippios-<source>-mcp = "<import path>.mcp:run"``, or for a
  source with ``tasks_write.py`` ``xippios-<source>-mcp-read`` at ``mcp:run`` and
  ``xippios-<source>-mcp-write`` at ``mcp_write:run``, with no alias of the other form; a
  script of the package's own stands beside them (ADR-0063, decision 8);
- the package re-exports every task of ``tasks.__all__`` and ``tasks_write.__all__``, the
  same object, from its ``__init__.py`` (ADR-0063, decision 8);
- every tool's description, the text of its task's docstring before ``Args:``, is under
  1,000 characters, read and write tools alike, since each argument's text reaches the
  tool's input schema instead (conventions §8, ADR-0063, decision 9);
- ``http.py``'s ``router`` routes the same tasks at ``/<source>/<task>``, ``GET`` when
  every parameter is a scalar and ``POST`` otherwise (conventions §9, ADR-0007);
- every task, read and write, is a synchronous function returning ``Result[T]``
  (conventions §2, §6) whose docstring is a one-sentence first line and, when it takes
  parameters, an ``Args:`` block (conventions §8); no ``async_fn`` is required, since
  conventions §6 makes the async variant optional;
- every read task, of ``tasks.__all__``, bulk or not, is named with one of the five read
  verbs, ``list_``, ``get_``, ``search_``, ``count_`` or ``download_``, and a noun after it
  (conventions §1, ADR-0061, decision 3); a write task of ``tasks_write`` takes a write's
  verb, ``create_``, ``update_``, ``delete_`` or upstream's own, and is not read here;
- in every pydantic model that a task's ``Result[T]`` reaches, read or write, through its
  fields, a field or computed field ``<stem>_number`` or ``<stem>_label`` whose stem names a
  field of the same model stands beside text: that field holds ``str`` or a subclass, ``None``
  allowed beside it (conventions §3 and §10, ADR-0060, decisions 7 and 9). A name whose part
  before the suffix names no field of its model is upstream's own and no reading, an address's
  ``street_number`` say, and passes; so does a reading that keeps no text beside it, since
  whether a reading can lose something is the review's. A time has no suffix, since the type
  that keeps all that upstream sends reads it;
- ``README.md``'s status table lists exactly ``tasks.__all__`` plus
  ``tasks_write.__all__``, a source's write tasks included (conventions §13), in the format
  of sdk-template's ``README.md.jinja``: the tables under the ``## Status`` heading whose
  header row has a ``Task function`` column; that cell starts with the task's name in
  backticks, alone, with its call (``get_series(region_code, year)``) or as
  ``tasks.get_series(...)``, several tasks of one row as backticked names separated by
  commas; whatever follows the first non-backticked text is prose;
- ``.copier-answers.yml`` names a template tag, ``_commit: vX.Y.Z`` (conventions §15);
- ``pyproject.toml`` bounds ``xippios-core`` and each of its extras to one minor,
  ``~=X.Y.Z``, all alike (conventions §12, ADR-0039);
- every task, read and write, of a multi-tenant source, one whose ``_client``, ``tasks``
  or ``tasks_write`` module holds a ``Tenants`` registry, takes exactly one tenant: the
  parameter the registry declares, ``Tenants(..., param="org")``, with no default,
  annotated ``str`` or ``Annotated[str, ...]``, neither ``*`` nor ``**``; the tenant list
  of ``list_task`` is excepted (conventions §7; ADR-0036, decision 13). A source with no
  ``Tenants`` registry passes. The check reads
  signatures: what a task reaches inside is the review's
  (https://github.com/xippios/sdk-core/issues/302);
- every key class that ``_client.py`` holds by a name names the package's own slug,
  ``_client.SOURCE``: a ``KeyAuth`` of the module, the ``auth`` of its ``AsyncClient`` and
  the ``auth`` of another object of it, the gateway that a publisher's shared package
  builds with the slug it is given, ``Gateway(SOURCE)`` say. A key that a ``KeyAuth``
  registers under one slug stays as sent in an envelope of another, since the registries are
  kept for each source (conventions §10, ADR-0040, decision 6, amendment 2026-11-24;
  https://github.com/xippios/sdk-core/issues/526). A ``KeyAuth`` that names no source, a
  ``QuotaPolicy`` whose ``source`` speaks for a publisher, and a source with no key class
  pass;
- a source that keeps ``docs/upstream/OBSERVED.md``, the notes of what it observed of
  upstream, is held to three rules of it, one test each, and a source without the file
  passes all three (conventions §3, ADR-0044). ``FETCHED.md`` lists the file in a row of
  its own: a table row whose first cell is ``OBSERVED.md``, whose last cell says that it is
  written by hand and whose cells between, at any width, are ``-``. The file holds one note
  at least, a ``###`` section, and the last paragraph of every note, its link reference
  definitions dropped, opens with ``Probe: <date>`` or ``Observed: <date>``, an ISO date
  (``Probe: 2026-11-20, ...``). Every code span of the file whose text starts with
  ``tests/``, ``docs/``, ``src/`` or ``scripts/``, holds no space and ends in an extension
  names a file that exists, from the repository's root;
- every packaged list of the package, a ``reference/<name>.json`` that holds ``param``,
  ``endpoint``, ``fetched`` and ``records``, stands in ``LIVE_LISTS`` of
  ``tests/test_live.py``, which the nightly run compares with the list upstream serves now,
  or in its ``NO_LIVE_LIST`` with the reason it is not (conventions §10, ADR-0055;
  ``xippios.core.testing.live``). An entry that names no packaged list fails, so a stale
  declaration does not pass, and so do a list in both, an entry of ``NO_LIVE_LIST`` without
  its reason and an entry of ``LIVE_LISTS`` that is no pair of a ``PackagedCodes`` declared
  from its file and a function. The check loads ``tests/test_live.py`` by its path from the
  root, since under ``--import-mode=importlib`` no test module stands on an import path, and
  a source with no packaged list and no declaration passes. A module that does not import,
  or skips, fails or exits at its import, fails the check, which is never skipped: a test
  that needs an optional dependency or a key skips in itself or in its fixture;
- in every pydantic model that a task's ``Result[T]`` reaches, read or write, through its
  fields, each field that ``NamedBy`` marks holds codes, text or integers, one or a list of
  them, and is marked once, on the field or on an optional code, and a field that it names as
  the one in which upstream sends the name stands in the same model and holds text: a code and
  its label stand side by side
  (conventions §4, ADR-0067, decision 8; ADR-0060, decision 7). The check reads the model's
  declaration and no word of a parameter's name: whether a code is owed a name is the
  review's.

A write server's tools are its source's to test: the family check reads ``tasks_write`` for
the task checks, the status table, the package contract and the entry points (ADR-0042,
decision 1; ADR-0063, decision 8). A source tests again neither what these tests hold nor
what core's adapters answer for every source (conventions §10).

**Two family checks are CI steps, not tests**, since they read the pull request rather
than the package; sdk-template's ``ci.yml`` carries them, on ``pull_request`` with the
whole history checked out (``fetch-depth: 0``, for ``git diff origin/<base>...HEAD``):
every pull request but Dependabot's (``dependabot/``, which writes no entry) brings its
changelog entry, a fragment it adds or changes under ``changelog/`` or a change of
``CHANGELOG.md``, a release's and an adoption's included (conventions §12, §15, the
definition of done); and the fixture files it adds or changes under ``tests/fixtures/``
stay under 256 KiB, a fixture it only moves being neither, one moved and changed judged
under its new path (ADR-0040).
"""

import importlib
import importlib.util
import inspect
import json
import re
import sys
import tomllib
import typing
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pydantic
import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from xippios.core.client import AsyncClient, KeyAuth
from xippios.core.models import Result, _bare, _holds_text, _named_by
from xippios.core.reference import PackagedCodes, PackagedList
from xippios.core.tenants import Tenants, _lists_tenants
from xippios.core.testing.live import _LIVE, _NO_LIVE, _NO_PAIR, _a, _is_entry
from xippios.core.testing.plugin import _source_packages

__all__ = [
    "family_source",
    "test_family_code_names_are_declared_on_the_model",
    "test_family_copier_answers_name_a_template_tag",
    "test_family_core_is_bound_to_one_minor",
    "test_family_every_packaged_list_is_declared_for_the_live_run",
    "test_family_fetched_md_lists_observed_md_in_a_row_of_its_own",
    "test_family_http_router_routes_the_tasks",
    "test_family_key_class_names_the_package_s_own_slug",
    "test_family_mcp_build_holds_the_package_contract",
    "test_family_mcp_server_registers_the_tasks",
    "test_family_namespace_levels_are_empty",
    "test_family_observed_md_cites_files_that_exist",
    "test_family_observed_notes_end_with_their_probe_and_date",
    "test_family_package_has_a_version",
    "test_family_package_re_exports_its_tasks",
    "test_family_package_ships_py_typed",
    "test_family_project_scripts_name_the_entry_points",
    "test_family_read_tasks_start_with_a_read_verb",
    "test_family_readings_stand_beside_their_text",
    "test_family_readme_status_table_lists_the_tasks",
    "test_family_tasks_carry_agent_docstrings",
    "test_family_tasks_return_results",
    "test_family_tasks_take_one_tenant",
    "test_family_tool_descriptions_stay_under_the_bound",
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
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
"""A code span: a run of backticks, its text, which may hold a line break, and a run as long."""
_CITED = re.compile(r"(?:tests|docs|src|scripts)/[^\s`]+\.[A-Za-z][A-Za-z0-9]*")
"""A path a code span of ``OBSERVED.md`` cites a file by, from the repository's root."""


@dataclass(frozen=True)
class FamilySource:
    """The source package under test and the repository around it.

    Attributes:
        root: pytest's rootdir, the repository root.
        import_path: The package's import path, e.g. ``"xippios.example"``.
        package: The package module.
        source: The source slug, ``_client.SOURCE``, e.g. ``"example"``.
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
    found = _source_packages(config.rootpath)
    if len(found) != 1:
        where = [str((path / "tasks.py").relative_to(config.rootpath)) for path in found]
        pytest.fail(
            f"the family check needs one package with a tasks.py under src/xippios/, found "
            f"{where or 'none'}",
            pytrace=False,
        )
    return ".".join(found[0].relative_to(config.rootpath / "src").parts)


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

    Each tool takes its task's parameters, and a paged tool the adapter's ``offset`` beside
    them (ADR-0047), and carries the text of its docstring before ``Args:`` (conventions §8,
    ADR-0040, ADR-0063, decision 9).
    """
    from xippios.core._loop import run
    from xippios.core.mcp import tool_name
    from xippios.core.mcp.server import _adapter_arguments

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
        added = _adapter_arguments(server, tool)
        if listed != set(_parameters(fn)) | set(added):
            besides = f" and its paged cap adds {', '.join(added)}" if added else ""
            problems.append(
                f"{tool} takes {sorted(listed)}, {name} takes {sorted(_parameters(fn))}{besides}"
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


_CONTRACT_INTRO = (
    "mcp.py and mcp_write.py hold the package contract (conventions §8, ADR-0063, decision 8):"
)


def _tool_set(module: ModuleType, name: str, source: str, problems: list[str]) -> Any:
    """What ``<name>.build()`` returns where it is a ``ToolSet`` of ``source``, else ``None``.

    Each way it fails adds its problem: no ``build``, a ``build`` that raises, a value that
    is no ``ToolSet`` and a tool set of another source.

    Args:
        module: The source's ``mcp`` or ``mcp_write`` module.
        name: Its name in the package, ``"mcp"`` or ``"mcp_write"``.
        source: The source's slug, ``_client.SOURCE``.
        problems: The check's problems, which this adds to.
    """
    from xippios.core.mcp import ToolSet

    build = getattr(module, "build", None)
    if not callable(build):
        problems.append(f"{name}.py has no build(): def build() -> ToolSet")
        return None
    try:
        tool_set = build()
    except Exception as exc:  # the source's own error, named as the check meets it
        problems.append(f"{name}.build() raises {type(exc).__name__}: {exc}")
        return None
    if not isinstance(tool_set, ToolSet):
        problems.append(f"{name}.build() returns {_a(type(tool_set).__name__)}, not a ToolSet")
        return None
    if tool_set.source != source:
        problems.append(
            f"{name}.build() returns the tool set of {tool_set.source!r}, not of _client.SOURCE, "
            f"{source!r}"
        )
        return None
    return tool_set


def _listing(server: Any) -> dict[str, dict[str, Any]]:
    """The tools that ``server`` lists, each by its name as a client reads it."""
    from xippios.core._loop import run

    return {tool.name: tool.model_dump() for tool in run(server.list_tools())}


def test_family_mcp_build_holds_the_package_contract(family_source: FamilySource) -> None:
    """``mcp.build()``, ``mcp.server`` and ``mcp.ENV_VARS`` hold the package contract (§8).

    A host serves a source by its ``build()``, so ``mcp.build()`` returns a ``ToolSet`` of
    ``_client.SOURCE``, the entry point's ``mcp.server`` lists the tools that
    ``build_server(mcp.build())`` lists, name, description and input schema alike, and
    ``mcp.ENV_VARS`` is ``_client.ENV_VARS`` itself, imported rather than copied. A source
    with ``tasks_write.py`` serves it from ``mcp_write.py``, whose ``build()`` returns a tool
    set of the source that writes, ``read_only=False``; the write server's tools are the
    source's to test with ``assert_write_tools`` (conventions §8, ADR-0042, decision 1,
    ADR-0063, decision 8).
    """
    from xippios.core.mcp import build_server

    path = family_source.import_path
    client = importlib.import_module(f"{path}._client")
    mcp = importlib.import_module(f"{path}.mcp")
    problems: list[str] = []
    tool_set = _tool_set(mcp, "mcp", family_source.source, problems)
    server = getattr(mcp, "server", None)
    if server is None:
        problems.append("mcp.py has no server: server = build_server(build())")
    elif tool_set is not None:
        served, built = _listing(server), _listing(build_server(tool_set))
        differ = sorted(
            name for name in served.keys() | built.keys() if served.get(name) != built.get(name)
        )
        if differ:
            problems.append(
                f"mcp.server lists other tools than build_server(mcp.build()): {', '.join(differ)}"
            )
    if not hasattr(mcp, "ENV_VARS"):
        problems.append("mcp.py has no ENV_VARS: import it from _client")
    elif mcp.ENV_VARS is not getattr(client, "ENV_VARS", None):
        problems.append("mcp.ENV_VARS is not _client.ENV_VARS: import it from _client")
    if family_source.tasks_write is not None:
        if importlib.util.find_spec(f"{path}.mcp_write") is None:
            problems.append("tasks_write.py has no write server: mcp_write.py is missing")
        else:
            write = importlib.import_module(f"{path}.mcp_write")
            writes = _tool_set(write, "mcp_write", family_source.source, problems)
            if writes is not None and writes.read_only:
                problems.append(
                    "mcp_write.build() returns a tool set that does not write: build it with "
                    "read_only=False"
                )
    _fail(problems, _CONTRACT_INTRO)


_SCRIPTS_INTRO = (
    "[project.scripts] names the entry points of conventions §8, each at its module's run "
    "(ADR-0063, decision 8):"
)


def _entry_points(family: FamilySource) -> tuple[dict[str, str], tuple[str, ...]]:
    """The entry points that conventions §8 name for the source, and those it names not.

    ``xippios-<source>-mcp`` at ``mcp:run``, or for a source with ``tasks_write.py``
    ``xippios-<source>-mcp-read`` at ``mcp:run`` and ``xippios-<source>-mcp-write`` at
    ``mcp_write:run``, with no alias of the other form (ADR-0026).
    """
    stem, path = f"xippios-{family.source}-mcp", family.import_path
    if family.tasks_write is None:
        return {stem: f"{path}.mcp:run"}, (f"{stem}-read", f"{stem}-write")
    return {f"{stem}-read": f"{path}.mcp:run", f"{stem}-write": f"{path}.mcp_write:run"}, (stem,)


def test_family_project_scripts_name_the_entry_points(family_source: FamilySource) -> None:
    """``[project.scripts]`` names the servers' entry points of conventions §8.

    Each at its module's ``run``: ``xippios-<source>-mcp = "<import path>.mcp:run"``, or for
    a source with ``tasks_write.py`` ``xippios-<source>-mcp-read`` at ``mcp:run`` and
    ``xippios-<source>-mcp-write`` at ``mcp_write:run``, with no alias of the other form. A
    script of the package's own stands beside them (ADR-0063, decision 8).
    """
    pyproject = tomllib.loads((family_source.root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject.get("project", {}).get("scripts", {})
    expected, refused = _entry_points(family_source)
    problems: list[str] = []
    for name, target in expected.items():
        given = scripts.get(name)
        if given is None:
            problems.append(f'no {name} = "{target}"')
        elif str(given).strip() != target:
            problems.append(f"{name} runs {given}, not {target}")
    kind = "without" if family_source.tasks_write is None else "with"
    problems += [
        f"{name} is no entry point of a source {kind} a write server"
        for name in refused
        if name in scripts
    ]
    _fail(problems, _SCRIPTS_INTRO)


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

    Agents read the docstring, its text before ``Args:`` as the tool's description and each
    argument's text in the input schema: a first line that ends with a full stop, and an
    ``Args:`` block when the task takes parameters (conventions §8, ADR-0063, decision 9).
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


_RE_EXPORT_INTRO = (
    "the package re-exports every task of tasks.__all__ and tasks_write.__all__, the same "
    "object, from its __init__.py (ADR-0063, decision 8):"
)


def test_family_package_re_exports_its_tasks(family_source: FamilySource) -> None:
    """Every task of ``tasks.__all__`` and ``tasks_write.__all__`` is the package's own.

    ``xippios.example.get_series`` is ``xippios.example.tasks.get_series``, the object
    itself, as the package's ``__init__.py`` imports it (ADR-0063, decision 8).
    """
    package, path = family_source.package, family_source.import_path
    problems: list[str] = []
    for name, fn in sorted(_every_task(family_source).items()):
        attribute = name.partition(".")[2]
        if not hasattr(package, attribute):
            problems.append(f"{name}: {path} has no {attribute}")
        elif getattr(package, attribute) is not fn:
            problems.append(f"{name}: {path}.{attribute} is another object")
    _fail(problems, _RE_EXPORT_INTRO)


_DESCRIPTION_BOUND = 1_000
"""The characters a tool's description stays under (ADR-0063, decision 9)."""
_DESCRIPTION_INTRO = (
    "every tool's description, the text of its task's docstring before Args:, is under "
    f"{_DESCRIPTION_BOUND:,} characters (conventions §8, ADR-0063, decision 9):"
)


def test_family_tool_descriptions_stay_under_the_bound(family_source: FamilySource) -> None:
    """Every tool's description is under 1,000 characters (conventions §8).

    The description is the text of the task's docstring before ``Args:``, as the MCP adapter
    gives it, and each argument's text under ``Args:`` reaches the tool's input schema
    instead, so what one argument needs goes to its line there. The test holds the tools of
    the read server, ``tasks.__all__`` minus ``BULK_TASKS``, and of the write server,
    ``tasks_write.__all__`` (ADR-0063, decision 9).
    """
    from xippios.core.mcp import tool_name
    from xippios.core.mcp.server import _description

    tools = [*_served(family_source).values(), *family_source.write_tasks().values()]
    over = sorted(
        (tool_name(family_source.source, fn), len(_description(fn)))
        for fn in tools
        if len(_description(fn)) >= _DESCRIPTION_BOUND
    )
    _fail(
        [
            f"{tool}: {length:,} characters; move what one argument needs to its line under Args:"
            for tool, length in over
        ],
        _DESCRIPTION_INTRO,
    )


_READ_VERBS = ("list", "get", "search", "count", "download")
"""The five verbs a read task's name starts with, each followed by ``_`` (ADR-0061, decision 3).

Conventions §1 name them in this order, which ``tests/test_conventions.py`` holds.
"""
_VERBS_INTRO = (
    "every read task's name starts with "
    + ", ".join(f"{verb}_" for verb in _READ_VERBS[:-1])
    + f" or {_READ_VERBS[-1]}_ (conventions §1, ADR-0061, decision 3):"
)


def _starts_with_a_read_verb(name: str) -> bool:
    """Whether ``name`` is a read verb, its ``_`` and a noun after it."""
    return any(name.startswith(f"{verb}_") and len(name) > len(verb) + 1 for verb in _READ_VERBS)


def test_family_read_tasks_start_with_a_read_verb(family_source: FamilySource) -> None:
    """Every read task's name starts with one of the five read verbs (conventions §1).

    A task of ``tasks.__all__``, bulk or not, is ``list_``, ``get_``, ``search_``, ``count_``
    or ``download_`` and what it lists, gets, searches, counts or downloads, as the invented
    source ``example`` names ``list_regions`` and ``get_series``. Each verb has one meaning in
    the family, so an agent that knows one source reads the next one's tools by their names. A
    write task of ``tasks_write`` takes a write's verb, ``create_``, ``update_``, ``delete_`` or
    upstream's own, and is not read here (ADR-0061, decision 3).
    """
    problems = [
        f"tasks.{name} starts with none of them"
        for name in family_source.read_tasks()
        if not _starts_with_a_read_verb(name)
    ]
    _fail(problems, _VERBS_INTRO)


_SUFFIXES = ("_number", "_label")
"""The suffixes of a reading, which stands beside the text field of its stem (ADR-0060).

A time has none: it is read into the type that keeps all that upstream sends, with no text
beside it (ADR-0060, decision 8).
"""
_READINGS_INTRO = (
    "a reading <stem>_number or <stem>_label stands beside a text field <stem> of its model; a "
    "name whose part before the suffix names no field is upstream's own and passes "
    "(conventions §3, ADR-0060, decisions 7 and 9):"
)


def _model_fields(model: type[pydantic.BaseModel]) -> dict[str, Any]:
    """The model's fields and computed fields by name, each with its annotation."""
    fields: dict[str, Any] = {name: info.annotation for name, info in model.model_fields.items()}
    for name, computed in model.model_computed_fields.items():
        fields[name] = computed.return_type
    return fields


def _models(
    annotation: Any, seen: set[type[pydantic.BaseModel]]
) -> Iterator[type[pydantic.BaseModel]]:
    """Each model that ``annotation`` reaches and ``seen`` lacks, added to ``seen`` as it is.

    A model is reached through a union, a container's arguments and the fields of a model that
    is reached itself.
    """
    annotation = _bare(annotation)
    if isinstance(annotation, type) and issubclass(annotation, pydantic.BaseModel):
        if annotation not in seen:
            seen.add(annotation)
            yield annotation
            for field in _model_fields(annotation).values():
                yield from _models(field, seen)
        return
    for argument in typing.get_args(annotation):
        yield from _models(argument, seen)


def _stem(name: str) -> str | None:
    """The part of ``name`` before a reading's suffix, or ``None`` for a name without one."""
    for suffix in _SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return None


def test_family_readings_stand_beside_their_text(family_source: FamilySource) -> None:
    """A reading ``<stem>_number`` or ``<stem>_label`` stands beside its text (conventions §3).

    A package that reads a printed text as a number or a label keeps the text under upstream's
    name and the reading beside it under a fixed suffix (ADR-0060, decision 7), as the invented
    source ``example`` keeps ``value``, ``"1,204 (P)"``, beside ``value_number``, ``1204``. The
    check reads every pydantic model that a task's ``Result[T]`` reaches, read and write tasks
    alike, through its fields and computed fields, and fails a field or computed field with
    either suffix whose stem names a field of the same model that holds no text. The stem is
    the name before the suffix where the model holds a field of that name: a name whose part
    before the suffix names no field is upstream's own and no reading, an address's
    ``street_number`` say, and passes. A time has no suffix: the type that keeps all that
    upstream sends reads it, with no text beside it. The check holds a reading's form, not that
    a reading which can lose something has one, which is the review's (ADR-0060, decision 9).
    """
    problems: list[str] = []
    seen: set[type[pydantic.BaseModel]] = set()
    for fn in _every_task(family_source).values():
        try:
            returned = typing.get_type_hints(fn, include_extras=True).get("return")
        except Exception:  # an annotation that does not resolve: the test of results names it
            continue
        for model in _models(returned, seen):
            fields = _model_fields(model)
            for name in fields:
                stem = _stem(name)
                if stem is None or stem not in fields or _holds_text(fields[stem]):
                    continue
                held = _bare(fields[stem])
                shown = held.__name__ if isinstance(held, type) else repr(held)
                problems.append(
                    f"{model.__name__}.{name} stands beside {stem}, which holds {shown}"
                )
    _fail(problems, _READINGS_INTRO)


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
    list (ADR-0036, decision 13).
    """
    if family_source.tenants is None:
        return
    problems: list[str] = []
    param = family_source.tenants.param
    for name, fn in _every_task(family_source).items():
        if _lists_tenants(fn):
            continue
        problem = _one_tenant_problem(fn, param)
        if problem is not None:
            problems.append(f"{name} {problem}")
    _fail(
        problems,
        f"every task of a multi-tenant source takes exactly one tenant, {param}, the parameter "
        "its Tenants registry declares, required, the tenant list excepted (conventions §7):",
    )


def _key_classes(client: ModuleType) -> list[tuple[str, KeyAuth]]:
    """Every key class ``client`` holds by a name, each once, under the first name that holds it.

    A module-level ``KeyAuth``, the ``auth`` of a module-level ``AsyncClient``, and the ``auth``
    of any other module-level object, a publisher's gateway say, in the order of the names.
    """
    found: dict[int, tuple[str, KeyAuth]] = {}
    for name, value in sorted(vars(client).items()):
        if isinstance(value, KeyAuth):
            held: object = value
            label = name
        elif isinstance(value, AsyncClient):
            held, label = value._auth, f"{name}'s auth"
        elif isinstance(value, type | ModuleType):
            continue
        else:
            held, label = getattr(value, "auth", None), f"{name}.auth"
        if isinstance(held, KeyAuth):
            found.setdefault(id(held), (label, held))
    return list(found.values())


def test_family_key_class_names_the_package_s_own_slug(family_source: FamilySource) -> None:
    """The key class a source's client uses names the package's slug (conventions §10).

    A ``KeyAuth`` registers its query parameter as a credential of the slug it names, and an
    envelope reads the names of its own slug alone (ADR-0040, decision 6, amendment
    2026-11-24), so a key class that names another slug would leave the key as sent in the
    source's envelopes. The check reads what ``_client.py`` holds by a name: a ``KeyAuth``,
    the ``auth`` of an ``AsyncClient`` and the ``auth`` of a shared object such as a
    publisher's gateway, which builds its key class with the slug it is given
    (https://github.com/xippios/sdk-core/issues/526). A ``KeyAuth`` that names no source
    passes, and so does a source with none.
    """
    client = importlib.import_module(f"{family_source.import_path}._client")
    slug = family_source.source
    problems = [
        f"{label} names {auth.source!r}"
        for label, auth in _key_classes(client)
        if auth.source is not None and auth.source != slug
    ]
    _fail(
        problems,
        "so that no envelope of the package keeps its key as sent (conventions §10, ADR-0040, "
        f"decision 6), _client.py's key class must name the package's slug, {slug!r}:",
    )


_NAMES_INTRO = (
    "a field that NamedBy marks holds codes and is marked once, and the field it names as the "
    "one that holds the name stands in the same model and holds text (conventions §4, "
    "ADR-0067, decision 8):"
)


def test_family_code_names_are_declared_on_the_model(family_source: FamilySource) -> None:
    """Each mark of a record's code field is one that a ``Result`` can read (conventions §4).

    A record's model marks a code field with the packaged list that names its codes,
    ``NamedBy(REGIONS)``, or with the field beside it in which upstream sends the name,
    ``NamedBy("item")`` (ADR-0067, decision 6). The check reads every pydantic model that a
    task's ``Result[T]`` reaches, read and write tasks alike, bulk or not, through its fields
    and computed fields, and fails a field marked twice, a mark inside the field's type that no
    answer reads, on a list's items or in a union of codes, a marked field that holds no code,
    text or integers, one or a list of them, and a named field that is no other field of the
    model or holds no text, so a code and its label stand side by side (ADR-0060, decision 7).
    A mark reads on the field and on an optional code, ``Annotated[str, NamedBy(...)] | None``.
    It reads
    the declaration and no word of a parameter's name: whether a code is owed a name, a
    country's say, is the review's (ADR-0067, decision 8).
    """
    problems: list[str] = []
    seen: set[type[pydantic.BaseModel]] = set()
    for fn in _every_task(family_source).values():
        try:
            returned = typing.get_type_hints(fn, include_extras=True).get("return")
        except Exception:  # an annotation that does not resolve: the test of results names it
            continue
        for model in _models(returned, seen):
            problems += _named_by(model)[1]
    _fail(problems, _NAMES_INTRO)


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


def _lines(text: str) -> Iterator[tuple[int, str, bool]]:
    """Each line of a Markdown text: its number, its text and whether a fenced block holds it.

    A fence's own lines belong to its block, and a fence closes on a run of its own
    character as long as its opening, or longer, with nothing after it.

    Args:
        text: A Markdown text, ``docs/upstream/OBSERVED.md`` say.
    """
    fence = ""
    for number, line in enumerate(text.splitlines(), start=1):
        marker = _FENCE.match(line)
        if fence:
            if marker and marker.group(1).startswith(fence) and not line[marker.end() :].strip():
                fence = ""
            yield number, line, True
        else:
            fence = marker.group(1) if marker is not None else ""
            yield number, line, marker is not None


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
    for _, line, fenced in _lines(text):
        heading = None if fenced else _HEADING.match(line)
        if heading is not None and len(heading.group(1)) <= 3:
            body = [] if len(heading.group(1)) == 3 else None
            if body is not None:
                notes.append(((heading.group(2) or "").strip(), body))
            continue
        if body is not None and (fenced or not _REFERENCE.match(line)):
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


def _blocks(text: str) -> list[list[tuple[int, str]]]:
    """The blocks of a Markdown text that can hold a code span, each line with its number.

    A blank line, a fenced code block and a heading end a paragraph, a heading is a block
    of its own, and a fenced block holds no code span, so it is none.

    Args:
        text: A Markdown text, ``docs/upstream/OBSERVED.md`` say.
    """
    blocks: list[list[tuple[int, str]]] = [[]]
    for number, line, fenced in _lines(text):
        if fenced or not line.strip():
            blocks.append([])
        elif _HEADING.match(line):
            blocks += [[(number, line)], []]
        else:
            blocks[-1].append((number, line))
    return [block for block in blocks if block]


def _citations(text: str) -> list[tuple[int, str]]:
    """Each file a code span of an ``OBSERVED.md`` cites, with the line the span starts on.

    A span cites a file when its text starts with ``tests/``, ``docs/``, ``src/`` or
    ``scripts/``, holds no space and ends in an extension, a path from the repository's
    root. Spans are read paragraph by paragraph, since a span may wrap onto the next line
    of its paragraph (conventions §3, ADR-0044, decision 1).

    Args:
        text: The text of ``docs/upstream/OBSERVED.md``.
    """
    cited: list[tuple[int, str]] = []
    for block in _blocks(text):
        joined = "\n".join(line for _, line in block)
        for span in _CODE_SPAN.finditer(joined):
            path = span.group(2).strip()
            if _CITED.fullmatch(path):
                cited.append((block[joined.count("\n", 0, span.start())][0], path))
    return cited


def _missing_citations(text: str, root: Path) -> list[str]:
    """The files that the code spans of an ``OBSERVED.md`` cite and ``root`` lacks.

    Each is named by the line its span starts on, as ``_citations`` reads them.

    Args:
        text: The text of ``docs/upstream/OBSERVED.md``.
        root: The repository's root.
    """
    return [
        f"line {number}: {path}" for number, path in _citations(text) if not (root / path).is_file()
    ]


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


_LIVE_TESTS = "tests/test_live.py"
"""The module that collects the live comparison and declares the packaged lists (ADR-0055)."""
_LIST_KEYS = frozenset({"param", "endpoint", "fetched", "records"})
"""The keys a packaged list's file holds, which ``PackagedList`` requires."""
_LIVE_INTRO = (
    f"every packaged list under reference/ stands in {_LIVE} of {_LIVE_TESTS}, compared with the "
    f"list upstream serves now, or in its {_NO_LIVE} with the reason it is not (conventions §10, "
    "ADR-0055):"
)


def _packaged_lists(package_dir: Path) -> dict[str, Path]:
    """The package's packaged lists by name, each ``reference/<name>.json`` that holds one.

    A file is a packaged list when it holds a JSON object with the keys ``PackagedList``
    requires, ``param``, ``endpoint``, ``fetched`` and ``records``; any other file under
    ``reference/``, a table's CSV or an index of the lists such as a
    ``lists.json``, is none.

    Args:
        package_dir: The package's directory, ``FamilySource.package_dir``.
    """
    found: dict[str, Path] = {}
    for path in sorted((package_dir / "reference").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.keys() >= _LIST_KEYS:
            found[path.stem] = path
    return found


def _live_tests(root: Path) -> ModuleType | None:
    """The repository's ``tests/test_live.py``, run as a module of its own; ``None`` without it.

    Loaded by its path from the root, as the check reads ``README.md`` there, since under
    ``--import-mode=importlib``, which the sources use, no test module stands on an import
    path (ADR-0055, decision 2). It runs offline, as pytest's collection runs it.

    Args:
        root: The repository's root, ``FamilySource.root``.

    Raises:
        BaseException: What ends the module's run: an error, pytest's skip, fail or exit, or a
            ``SystemExit``; ``_unloaded`` says which.
    """
    path = root / _LIVE_TESTS
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_xippios_family_test_live", path)
    if spec is None or spec.loader is None:  # pragma: no cover - a .py path always has both
        raise ImportError(f"{_LIVE_TESTS} cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass or a model of the module looks itself up
    spec.loader.exec_module(module)
    return module


def _unloaded(exc: BaseException) -> str:
    """Why ``tests/test_live.py`` gave the check no declaration, and what the source does.

    pytest's skip and fail are no ``Exception``, and neither is an exit: each ends the
    module's run before its declarations stand, so each fails the check, which is never
    skipped (https://github.com/xippios/sdk-core/issues/359, part 4). A module that skips
    for a reason of its own, a missing optional dependency or key, skips in the tests or the
    fixtures that need it, and its top level, where the declarations stand, imports offline.

    Args:
        exc: What ended the module's run.
    """
    unread = f"so the family check cannot read its {_LIVE} and {_NO_LIVE}"
    what = f"({type(exc).__name__}: {exc})"
    if isinstance(exc, pytest.skip.Exception):
        return (
            f"{_LIVE_TESTS} skips at its import, {unread} {what}: skip in the tests or the "
            "fixtures that need what is missing, pytest.importorskip among them, and keep the "
            "module's top level importable offline"
        )
    if isinstance(exc, SystemExit):
        return (
            f"{_LIVE_TESTS} exits at its import, {unread} {what}: remove the exit from its top "
            "level"
        )
    return (
        f"{_LIVE_TESTS} does not import, {unread} {what}: make it import offline, as pytest's "
        "collection imports it"
    )


def _declaration(module: ModuleType, name: str, problems: list[str]) -> dict[str, object]:
    """The module's declaration ``name`` by list name; one that is no mapping adds its problem."""
    declared = getattr(module, name, {})
    if not isinstance(declared, Mapping):
        kind = _a(type(declared).__name__)
        problems.append(f"{name} is {kind}, not a mapping by the lists' names")
        return {}
    return {str(key): entry for key, entry in declared.items()}


def _declared_from(codes: PackagedCodes, path: Path) -> bool:
    """Whether ``codes`` was declared from the packaged list that the file ``path`` holds."""
    try:
        return codes.packaged == PackagedList.model_validate_json(path.read_text(encoding="utf-8"))
    except pydantic.ValidationError:
        return False


def _list_problems(
    name: str, path: Path | None, live: dict[str, object], excused: dict[str, object]
) -> list[str]:
    """What fails the declaration of the list ``name``, whose file is ``path`` or none."""
    held = {_LIVE: name in live, _NO_LIVE: name in excused}
    problems: list[str] = []
    if path is None:
        problems += [
            f"{where} names no packaged list, no reference/{name}.json"
            for where, holds in held.items()
            if holds
        ]
    elif not any(held.values()):
        problems.append(f"reference/{name}.json stands in neither {_LIVE} nor {_NO_LIVE}")
    if all(held.values()):
        problems.append(f"stands in both {_LIVE} and {_NO_LIVE}")
    reason = excused.get(name)
    if held[_NO_LIVE] and not (isinstance(reason, str) and reason.strip()):
        problems.append(f"{_NO_LIVE} gives no reason, a text that says why it is not compared")
    entry = live.get(name)
    if held[_LIVE] and not _is_entry(entry):
        problems.append(_NO_PAIR)
    elif _is_entry(entry) and path is not None and not _declared_from(entry[0], path):
        problems.append(f"{_LIVE} holds the codes of another list than reference/{name}.json")
    return problems


def _live_declaration_problems(family: FamilySource) -> list[str]:
    """What fails the rule that every packaged list stands in one declaration (ADR-0055)."""
    packaged = _packaged_lists(family.package_dir)
    try:
        module = _live_tests(family.root)
    except KeyboardInterrupt:  # the person's, not the module's
        raise
    except BaseException as exc:  # an error, a skip, a fail or an exit: none skips the check
        return [_unloaded(exc)]
    problems: list[str] = []
    live: dict[str, object] = {}
    excused: dict[str, object] = {}
    if module is not None:
        live = _declaration(module, _LIVE, problems)
        excused = _declaration(module, _NO_LIVE, problems)
    elif packaged:
        problems.append(f"{_LIVE_TESTS}, which declares {_LIVE} and {_NO_LIVE}, is missing")
    for name in sorted(packaged.keys() | live.keys() | excused.keys()):
        problems += [
            f"{name}: {problem}"
            for problem in _list_problems(name, packaged.get(name), live, excused)
        ]
    return problems


def test_family_every_packaged_list_is_declared_for_the_live_run(
    family_source: FamilySource,
) -> None:
    """Every packaged list stands in ``LIVE_LISTS`` or ``NO_LIVE_LIST`` (conventions §10).

    ``tests/test_live.py`` declares in ``LIVE_LISTS`` each packaged list that the nightly run
    compares with the list upstream serves now, with its ``PackagedCodes`` and the function
    that fetches it, and in ``NO_LIVE_LIST`` each one it does not compare, with the reason
    (ADR-0055). An entry that names no packaged list fails too, so a stale declaration does
    not pass, and so do a list in both, an entry without its reason and one that is no pair
    of a ``PackagedCodes`` declared from its file and a function. A source with no packaged
    list and no declaration passes. A ``tests/test_live.py`` that skips, fails or exits at its
    import fails the check as one that does not import does, naming why and what to do, since
    no new family check of core 0.4.1 is skipped or warns first
    (https://github.com/xippios/sdk-core/issues/359, part 4).
    """
    _fail(_live_declaration_problems(family_source), _LIVE_INTRO)
