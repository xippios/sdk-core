"""`scripts/count_surface.py`: core's surface in two counts, and who consumes each piece.

The script is a report: it fails nothing, and no name or parameter leaves core by its count
alone (https://github.com/xippios/sdk-core/issues/485). These tests pin its counting on a small
core and two consumers made here, the invented source `example` and a host, never on core's own
figures, which every release changes.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "count_surface.py"

# The sdist ships tests/ but no scripts/, so there is nothing to run there.
pytestmark = pytest.mark.skipif(
    not (ROOT / "scripts").is_dir(), reason="the sdist ships no scripts/"
)

# A core of six pinned lists. The workbench is testing/ and refresh/; the rest is the run-time
# part. Each file's line count is in its comment, and the sums are pinned below.
CORE = {
    # 8 lines
    "__init__.py": """
        from xippios.core._loop import sync
        from xippios.core.client import AsyncClient, ClientConfig
        from xippios.core.models import ResultMeta, closest
        from xippios.core.reference import load_json

        __all__ = [
            "AsyncClient", "ClientConfig", "ResultMeta", "closest", "load_json", "sync"
        ]
    """,
    # 6 lines
    "_loop.py": """
        def sync(fn):
            return fn


        def _private():
            return None
    """,
    # 4 lines
    "client/__init__.py": """
        from xippios.core.client._core import AsyncClient
        from xippios.core.client.config import ClientConfig, RetryPolicy

        __all__ = ["AsyncClient", "ClientConfig", "RetryPolicy"]
    """,
    # 6 lines
    "client/_core.py": """
        class AsyncClient:
            def __init__(self, base_url, *, config=None, cache=None):
                self.base_url = base_url

            def get(self, path, *, params=None):
                return path
    """,
    # 12 lines
    "client/config.py": """
        from dataclasses import dataclass, field


        @dataclass(frozen=True, kw_only=True)
        class RetryPolicy:
            max_attempts: int = 4


        @dataclass(frozen=True, kw_only=True)
        class ClientConfig:
            retry: RetryPolicy = field(default_factory=RetryPolicy)
            pause_cap: float = 30.0
    """,
    # 11 lines
    "models.py": """
        from pydantic import BaseModel


        class ResultMeta(BaseModel):
            source: str
            endpoint: str
            _private: int = 0


        def closest(value, codes, *, n=3, cutoff=0.6):
            return []
    """,
    # 2 lines
    "reference.py": """
        def load_json(package, name):
            return {}
    """,
    # 3 lines
    "mcp/__init__.py": """
        from xippios.core.mcp.cli import main

        __all__ = ["main"]
    """,
    # 2 lines
    "mcp/cli.py": """
        def main(server, argv=None, *, add_options=None, apply_options=None):
            return 0
    """,
    # 1 line
    "http/__init__.py": """
        __all__ = []
    """,
    # 6 lines
    "testing/__init__.py": """
        from xippios.core.testing.record import load_fixture, record, record_sync
        from xippios.core.testing.scrub import Scrub

        __all__ = [
            "Scrub", "load_fixture", "record", "record_sync"
        ]
    """,
    # 12 lines
    "testing/record.py": """
        from xippios.core import sync


        async def record(client, path, *, scrub=None, keep=None):
            return path


        record_sync = sync(record)


        def load_fixture(path):
            return path
    """,
    # 8 lines
    "testing/scrub.py": """
        from dataclasses import dataclass


        @dataclass(frozen=True)
        class Scrub:
            secrets: list
            response_secrets: list
            plain: bool = False
    """,
    # 5 lines
    "testing/family.py": """
        def test_namespace():
            pass

        def test_docstrings():
            pass
    """,
    # 4 lines
    "refresh/__init__.py": """
        from xippios.core.refresh.upstream import Snapshot, load_json

        __all__ = ["Snapshot", "load_json"]

    """,
    # 6 lines
    "refresh/upstream.py": """
        class Snapshot:
            def __init__(self, pages, *, slug, out=None):
                self.pages = pages

        def load_json(response, indent):
            return response
    """,
}

# The run-time part: 8 + 6 + 4 + 6 + 12 + 11 + 2 + 3 + 2 + 1 lines in 10 files; the
# workbench: 6 + 12 + 8 + 5 + 4 + 6 lines in 6 files.
RUN_TIME_LINES = 55
WORKBENCH_LINES = 41

# The invented source: its package, its scripts, its tests and one rendered command.
EXAMPLE = {
    "src/xippios/example/_client.py": """
        from xippios.core import AsyncClient, ClientConfig
        from xippios.core.client.config import RetryPolicy

        client = AsyncClient(
            "https://api.example.org/v1",
            config=ClientConfig(retry=RetryPolicy(max_attempts=1), pause_cap=5.0),
        )
    """,
    "src/xippios/example/tasks.py": """
        import xippios.core.models as models
        from xippios.core import ResultMeta, closest

        from xippios.example._client import client


        def list_regions(search):
            client.get("/regions", params={"q": search})
            models.closest(search, [], cutoff=0.9)
            return ResultMeta(source="example", endpoint="regions")
    """,
    "scripts/refresh_upstream.py": """
        from xippios.core.refresh import Snapshot
        from xippios.core.refresh.upstream import load_json

        SNAPSHOT = Snapshot([], slug="example")
    """,
    "tests/conftest.py": """
        pytest_plugins = ["xippios.core.testing.plugin"]
    """,
    "tests/test_family.py": """
        from xippios.core.testing.family import *  # noqa: F403
    """,
    "tests/test_tasks.py": """
        from xippios.core import testing
        from xippios.core.client import AsyncClient
        from xippios.core.testing import Scrub


        def test_record():
            testing.record_sync(AsyncClient("x"), "/regions", scrub=Scrub([], []))
    """,
    "tests/test_broken.py": """
        def broken(:
    """,
    "tests/fixtures/list_regions/ok.py": """
        from xippios.core import sync
    """,
    ".claude/commands/record-fixture.md": """
        # Record a fixture

        1. Record it:

           ```python
           from xippios.core.testing import record_sync

           record_sync(client, "/regions", keep=["id"])
           ```

        2. Then check it:

           ```bash
           uv run python -c "from xippios.core import load_json"
           ```
    """,
}

# A host: its package alone, with two subclasses of core's client.
HOST = {
    "src/example_host/server.py": """
        from xippios import core
        from xippios.core.mcp import main

        main(None, add_options=None)
        core.closest("x", [], n=1)
    """,
    "src/example_host/client.py": """
        from xippios.core.client import AsyncClient


        class HostClient(AsyncClient):
            def __init__(self, base_url):
                super().__init__(base_url, cache=None)


        class OtherClient(AsyncClient):
            def __init__(self, base_url):
                AsyncClient.__init__(self, base_url, config=None)
    """,
}


def write(base: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return base


@pytest.fixture
def trees(tmp_path: Path) -> dict[str, Path]:
    return {
        "core": write(tmp_path / "core" / "src" / "xippios" / "core", CORE).parents[2],
        "example": write(tmp_path / "example", EXAMPLE),
        "host": write(tmp_path / "host", HOST),
    }


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def report(trees: dict[str, Path], *consumers: str) -> Any:
    named = [f"{name}={trees[name]}" for name in consumers]
    done = run("--json", "--core", str(trees["core"]), *named)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_surface_counts_names_and_lines_in_two_parts(trees: dict[str, Path]) -> None:
    surface = report(trees)["surface"]

    assert surface["lists"] == {
        "xippios.core": {"part": "run time", "names": 6},
        "xippios.core.client": {"part": "run time", "names": 3},
        "xippios.core.mcp": {"part": "run time", "names": 1},
        "xippios.core.http": {"part": "run time", "names": 0},
        "xippios.core.testing": {"part": "workbench", "names": 4},
        "xippios.core.refresh": {"part": "workbench", "names": 2},
    }
    # A name in two lists of one part counts once in it; load_json, which both parts pin as
    # two different functions, counts once in each part and once in the package.
    assert surface["run_time"] == {"names": 8, "lines": RUN_TIME_LINES, "files": 10}
    assert surface["workbench"] == {"names": 6, "lines": WORKBENCH_LINES, "files": 6}
    assert surface["package"] == {
        "names": 13,
        "lines": RUN_TIME_LINES + WORKBENCH_LINES,
        "files": 16,
    }
    assert surface["in_both_parts"] == ["load_json"]


def test_each_pinned_name_names_its_consumers_by_kind_of_code(trees: dict[str, Path]) -> None:
    names = report(trees, "example", "host")["names"]

    # A class that two lists pin is one object: a consumer of either entry counts for both,
    # by the other list's path, and the second entry names the first, which it repeats.
    assert names["xippios.core:AsyncClient"] == {
        "count": 2,
        "consumers": {"example": ["package"]},
        "by_other_path": {"example": ["xippios.core.client"], "host": ["xippios.core.client"]},
        "repeats": None,
    }
    assert names["xippios.core.client:AsyncClient"] == {
        "count": 2,
        "consumers": {"example": ["tests"], "host": ["package"]},
        "by_other_path": {"example": ["xippios.core"]},
        "repeats": "xippios.core:AsyncClient",
    }
    assert names["xippios.core.client:ClientConfig"] == {
        "count": 1,
        "consumers": {},
        "by_other_path": {"example": ["xippios.core"]},
        "repeats": "xippios.core:ClientConfig",
    }
    # A module alias reaches a name too, from a pinned list or from the module that defines it.
    assert names["xippios.core:closest"] == {
        "count": 2,
        "consumers": {"example": ["package"], "host": ["package"]},
        "by_other_path": {"example": ["xippios.core.models"]},
        "repeats": None,
    }
    assert names["xippios.core.testing:record_sync"]["consumers"] == {
        "example": ["commands", "tests"]
    }
    assert names["xippios.core.client:RetryPolicy"] == {
        "count": 1,
        "consumers": {},
        "by_other_path": {"example": ["xippios.core.client.config"]},
        "repeats": None,
    }
    assert names["xippios.core:load_json"]["consumers"] == {"example": ["commands"]}
    assert names["xippios.core.refresh:load_json"]["by_other_path"] == {
        "example": ["xippios.core.refresh.upstream"]
    }
    # A fixture is recorded data, not code: its folder is not read.
    assert names["xippios.core:sync"]["count"] == 0
    assert names["xippios.core.testing:load_fixture"]["count"] == 0


def test_each_keyword_only_parameter_names_the_consumers_that_pass_it(
    trees: dict[str, Path],
) -> None:
    parameters = report(trees, "example", "host")["parameters"]

    # A function, a class's __init__, a dataclass with kw_only, a pydantic model's fields and
    # a function that sync derives: each keyword-only parameter, passed or not.
    assert parameters["xippios.core:closest"] == {
        "n": {"count": 1, "consumers": {"host": ["package"]}},
        "cutoff": {"count": 1, "consumers": {"example": ["package"]}},
    }
    # A subclass passes its base's keywords by super().__init__ or by Base.__init__.
    assert parameters["xippios.core:AsyncClient"] == {
        "config": {"count": 2, "consumers": {"example": ["package"], "host": ["package"]}},
        "cache": {"count": 1, "consumers": {"host": ["package"]}},
    }
    assert parameters["xippios.core:ClientConfig"] == {
        "retry": {"count": 1, "consumers": {"example": ["package"]}},
        "pause_cap": {"count": 1, "consumers": {"example": ["package"]}},
    }
    assert parameters["xippios.core.client:RetryPolicy"] == {
        "max_attempts": {"count": 1, "consumers": {"example": ["package"]}},
    }
    assert parameters["xippios.core:ResultMeta"] == {
        "source": {"count": 1, "consumers": {"example": ["package"]}},
        "endpoint": {"count": 1, "consumers": {"example": ["package"]}},
    }
    assert parameters["xippios.core.testing:record_sync"] == {
        "scrub": {"count": 1, "consumers": {"example": ["tests"]}},
        "keep": {"count": 1, "consumers": {"example": ["commands"]}},
    }
    assert parameters["xippios.core.mcp:main"] == {
        "add_options": {"count": 1, "consumers": {"host": ["package"]}},
        "apply_options": {"count": 0, "consumers": {}},
    }
    assert parameters["xippios.core.refresh:Snapshot"] == {
        "slug": {"count": 1, "consumers": {"example": ["scripts"]}},
        "out": {"count": 0, "consumers": {}},
    }
    # One class pinned in two lists has its parameters once, under the first list that pins
    # it. A dataclass without kw_only takes its fields by position as well, and a method's
    # keyword, client.get(params=...), is not its class's.
    assert "xippios.core.client:AsyncClient" not in parameters
    assert "xippios.core.client:ClientConfig" not in parameters
    assert "xippios.core.testing:Scrub" not in parameters
    assert "params" not in parameters["xippios.core:AsyncClient"]


def test_every_import_outside_the_pinned_lists_is_reported(trees: dict[str, Path]) -> None:
    outside = report(trees, "example", "host")["outside"]

    assert outside == {
        "xippios.core.client.config:RetryPolicy": {
            "count": 1,
            "consumers": {"example": ["package"]},
            "pinned_as": ["xippios.core.client:RetryPolicy"],
        },
        "xippios.core.models": {
            "count": 1,
            "consumers": {"example": ["package"]},
            "pinned_as": [],
        },
        "xippios.core.models:closest": {
            "count": 1,
            "consumers": {"example": ["package"]},
            "pinned_as": ["xippios.core:closest"],
        },
        "xippios.core.refresh.upstream:load_json": {
            "count": 1,
            "consumers": {"example": ["scripts"]},
            "pinned_as": ["xippios.core.refresh:load_json"],
        },
        "xippios.core.testing.family:*": {
            "count": 1,
            "consumers": {"example": ["tests"]},
            "pinned_as": [],
        },
        "xippios.core.testing.plugin": {
            "count": 1,
            "consumers": {"example": ["tests"]},
            "pinned_as": [],
        },
    }


def test_the_report_fails_nothing_and_names_what_it_could_not_read(
    trees: dict[str, Path],
) -> None:
    got = report(trees, "example", "host")

    assert got["consumers"] == {
        "example": {"files": 8, "unread": ["tests/test_broken.py"]},
        "host": {"files": 2, "unread": []},
    }
    assert got["summary"] == {
        "names": {"none": 3, "one": 9, "two_or_more": 2, "repeats": 2},
        "parameters": {"none": 4, "one": 12, "two_or_more": 1},
    }


def test_the_text_report_gives_one_line_per_item(trees: dict[str, Path]) -> None:
    done = run("--core", str(trees["core"]), f"example={trees['example']}", f"host={trees['host']}")

    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    for line in (
        "list xippios.core: 6 names, run time",
        "list xippios.core.testing: 4 names, workbench",
        f"run time: 8 names, {RUN_TIME_LINES} lines in 10 files",
        f"workbench: 6 names, {WORKBENCH_LINES} lines in 6 files",
        f"package: 13 names, {RUN_TIME_LINES + WORKBENCH_LINES} lines in 16 files;"
        " in both parts: load_json",
        "consumer example: 8 files, 1 unread",
        "consumer host: 2 files",
        "name xippios.core:closest: 2 consumers: example (package; by xippios.core.models),"
        " host (package)",
        "name xippios.core:sync: 0 consumers",
        "name xippios.core:AsyncClient: 2 consumers: example (package; by xippios.core.client),"
        " host (by xippios.core.client)",
        "name xippios.core.client:AsyncClient: 2 consumers; repeats xippios.core:AsyncClient",
        "parameter xippios.core:closest(cutoff=): 1 consumer: example (package)",
        "parameter xippios.core:AsyncClient(cache=): 1 consumer: host (package)",
        "parameter xippios.core.mcp:main(apply_options=): 0 consumers",
        "outside xippios.core.testing.plugin: 1 consumer: example (tests)",
        "outside xippios.core.client.config:RetryPolicy: 1 consumer: example (package);"
        " pinned as xippios.core.client:RetryPolicy",
        "unread example: tests/test_broken.py",
        "names by consumers: 3 with none, 9 with one, 2 with two or more,"
        " and 2 that repeat an entry of another list",
        "parameters by consumers: 4 with none, 12 with one, 1 with two or more",
    ):
        assert line in lines


def test_without_consumers_it_counts_the_surface_alone(trees: dict[str, Path]) -> None:
    got = report(trees)

    assert set(got) == {"surface"}


def test_a_consumer_is_named_as_name_and_path(trees: dict[str, Path]) -> None:
    for wrong in ("example", f"={trees['example']}", f"example={trees['example'] / 'missing'}"):
        done = run("--core", str(trees["core"]), wrong)
        assert done.returncode == 2
        assert "name=<path>" in done.stderr
    done = run(
        "--core", str(trees["core"]), f"example={trees['example']}", f"example={trees['host']}"
    )
    assert done.returncode == 2
    assert "example is named twice" in done.stderr


def test_a_tree_without_core_is_refused_in_one_line(tmp_path: Path) -> None:
    done = run("--core", str(tmp_path))

    assert done.returncode == 2
    assert "no package src/xippios/core" in done.stderr


def test_it_reads_this_repository_by_default() -> None:
    # Core's own figures change with every release, so this run pins none of them: it reads
    # the six lists of the repository that holds the script.
    done = run("--json")

    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout)
    assert len(got["surface"]["lists"]) == 6
    assert got["surface"]["package"]["names"] > 0
