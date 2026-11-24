"""The workflows carry no comment, and the README says what each one does.

A workflow file carries no comment but the version after a pinned action, and the README says of
each workflow in one short paragraph what it checks, when it runs, what the calling file hands
over and what switches it (https://github.com/xippios/.github/issues/111, decided for core's
files in https://github.com/xippios/sdk-core/issues/494).
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = sorted(
    path for suffix in ("*.yml", "*.yaml") for path in (ROOT / ".github" / "workflows").glob(suffix)
)
"""Every workflow GitHub runs: a file of `.github/workflows/` named `*.yml` or `*.yaml`."""
PINNED = re.compile(r"^\s*(?:- )?uses: [\w./-]+@[0-9a-f]{40} # v\d+(?:\.\d+)*$")
"""A pinned action with its version: the one line of a workflow that may hold a comment."""


def _readme_section(heading: str) -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    found = text.find(f"\n{heading}\n")
    assert found >= 0, f"the README has no {heading!r}"
    start = found + len(heading) + 2
    end = text.find("\n## ", start)
    return text[start:] if end < 0 else text[start:end]


def test_the_repository_has_its_four_workflows() -> None:
    names = [path.name for path in WORKFLOWS]
    assert names == ["adr-index.yml", "ci.yml", "conventions.yml", "publish.yml"], names


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_a_workflow_carries_no_comment_but_a_pinned_action_s_version(path: pathlib.Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    comments = [
        f"{path.name}:{number}: {line.strip()}"
        for number, line in enumerate(lines, 1)
        if re.search(r"(?:^|\s)#", line) and not PINNED.match(line)
    ]
    assert comments == [], "\n".join(comments)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_the_readme_gives_a_workflow_one_paragraph(path: pathlib.Path) -> None:
    section = _readme_section("## Workflows")
    paragraphs = [p for p in section.strip().split("\n\n") if p.startswith(f"`{path.name}`")]
    assert len(paragraphs) == 1, f"## Workflows opens {len(paragraphs)} paragraphs with {path.name}"
