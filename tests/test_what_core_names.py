"""The shapes of a name that core may use, and every other refused in what binds (ADR-0065).

What binds is the package, its tests and its scripts, the conventions, the README, `CLAUDE.md`,
the review checklist, the definition of done and the handover (ADR-0065, decision 5). It names
no real source or publisher, and its examples use the invented source `example` (ADR-0065,
decision 4). This module lists the shapes in which a name of the family can stand, a repository,
a distribution, an import path, a credential's variable and a host, with what core may name in
each, and fails on any other: it never changes when a source joins (ADR-0065, decision 6). It
reads no record under `docs/adr/`, no dated report and no changelog, which tell history and may
name a source.

A citation is the whole URL of a public record of the organization: an issue, a pull request,
or a record or a report under `docs/`. Each is taken out before the shapes are matched, so the
name in a citation passes, while the same name as a word, in a code span, a link's text or the
URL of a repository or of a file stands as a name and fails. The words that only the
organization's conventions check can see, a source's name without its shape, are its step
(https://github.com/xippios/.github/issues/169).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TREES = ("src", "tests", "scripts")
"""The package, its tests and its scripts, every file under them."""
DOCUMENTS = (
    "README.md",
    "CLAUDE.md",
    "docs/conventions.md",
    "docs/review-checklist.md",
    "docs/definition-of-done.md",
    "docs/handover.md",
)
"""The documents that bind, by their path in the repository."""
SKIPPED = ("__pycache__",)
"""The folders that a run leaves in the trees and git ignores."""

CITATION = re.compile(
    r"https://github\.com/xippios/[\w.-]+/"
    r"(?:(?:issues|pull)/\d+|blob/[\w.-]+/docs/(?:adr|reports)/[\w.-]+\.md)"
    r"(?:#[\w-]+)?"
)
"""A citation of a public record: an issue, a pull request, a record or a dated report."""

HOST_ENDINGS = "com|org|net|gov|edu|int|io|eu|dev|ai|us|uk|ch|de|fr"
"""The endings of a host that a publisher's documents and APIs stand under, matched in lower case,
since a host is written so and a member's name or an encoded value is not."""


@dataclass(frozen=True)
class Shape:
    """One shape of a name: how it stands in a text, and what core may name in it."""

    name: str
    pattern: re.Pattern[str]
    allowed: re.Pattern[str]


SHAPES = (
    Shape(
        "repository",
        re.compile(r"(?<![\w.-])sdk-[a-z0-9]+(?:-[a-z0-9]+)*"),
        # Core's own, the template's and the invented source's.
        re.compile(r"sdk-(?:core|template|example(?:-[a-z0-9]+)*)"),
    ),
    Shape(
        "distribution",
        re.compile(r"(?<![\w.-])xippios-[a-z0-9]+(?:-[a-z0-9]+)*"),
        # Core's and its names, the host's, the family's topic, the invented source's and the
        # second package that core's tests install beside it, and two names core gives itself:
        # the prefix of the reference frame's folder and the census's plugin.
        re.compile(
            r"xippios-(?:core|mcp|sdk|example|other)(?:-[a-z0-9]+)*"
            r"|xippios-refresh|xippios-replay-census"
        ),
    ),
    Shape(
        "import path",
        re.compile(r"(?<![\w.-])xippios\.[a-z_][a-z0-9_]*"),
        # Core's, the host's, the invented source's with its test modules, and the second package.
        re.compile(r"xippios\.(?:core|mcp|example\w*|other)"),
    ),
    Shape(
        "credential's variable",
        # A part in angle or curly brackets is a placeholder, `EXAMPLE_<NAME>_API_KEY`.
        re.compile(
            r"(?<![\w<>{}])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_(?:KEY|TOKEN|SECRET|PASSWORD)(?![\w<>{}])"
        ),
        # The invented source's and core's own, and the words that say what a value is and
        # whose it is not: a field's name, a placeholder, a hidden value, a refreshing or a
        # page's token, a tenant of a test, and the second package.
        re.compile(r"(?:EXAMPLE|XIPPIOS|OTHER|API|PLACEHOLDER|HIDDEN|REFRESH|NEXT|TENANT)_\w+"),
    ),
    Shape(
        "host",
        re.compile(
            rf"(?<![\w.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{HOST_ENDINGS})(?![\w-]|\.\w)"
        ),
        # The names that RFC 2606 reserves for examples, the organization's host, and the two
        # storage services whose signed links core's redaction reads.
        re.compile(
            r"(?:[\w-]+\.)*(?:example\.(?:org|com|net)|github\.com"
            r"|blob\.core\.windows\.net|s3\.amazonaws\.com)"
        ),
    ),
)


@dataclass(frozen=True)
class Finding:
    """A name that core may not use, where it stands."""

    path: str
    line: int
    shape: str
    name: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.shape} {self.name}"


def binding_files(root: Path) -> list[Path]:
    """Every file of what binds under `root`, the trees' files and the documents that exist."""
    files = [
        path
        for tree in TREES
        for path in sorted((root / tree).rglob("*"))
        if path.is_file() and not set(path.relative_to(root).parts) & set(SKIPPED)
    ]
    return files + [root / name for name in DOCUMENTS if (root / name).is_file()]


def names_in(text: str) -> list[tuple[int, str, str]]:
    """Each name outside the shapes core may use, with its line and its shape's name."""
    found = []
    # A citation leaves its place to spaces, so the lines after it keep their numbers.
    bare = CITATION.sub(lambda match: " " * len(match.group(0)), text)
    for shape in SHAPES:
        for match in shape.pattern.finditer(bare):
            name = match.group(0)
            if not shape.allowed.fullmatch(name):
                found.append((bare.count("\n", 0, match.start()) + 1, shape.name, name))
    return found


def findings(root: Path) -> list[Finding]:
    """The names that core may not use in the files of what binds under `root`."""
    return [
        Finding(path.relative_to(root).as_posix(), line, shape, name)
        for path in binding_files(root)
        for line, shape, name in names_in(path.read_text(encoding="utf-8", errors="replace"))
    ]


def test_what_binds_names_no_source() -> None:
    found = findings(ROOT)
    assert not found, "core names what it may not:\n" + "\n".join(map(str, found))


def test_what_binds_is_read() -> None:
    # The scan reads every document that binds and each tree, so a moved file cannot pass it.
    files = {path.relative_to(ROOT).as_posix() for path in binding_files(ROOT)}
    assert set(DOCUMENTS) <= files
    for tree in TREES:
        assert any(name.startswith(f"{tree}/") for name in files), tree
    assert "tests/test_what_core_names.py" in files


# Each planted name is joined from two parts, so that this module names none of them itself.
PLANTED = {
    "repository": "sdk" + "-planted",
    "distribution": "xippios" + "-planted",
    "import path": "xippios" + ".planted",
    "credential's variable": "PLANTED" + "_API_KEY",
    "host": "api.planted" + ".gov",
}


@pytest.mark.parametrize("shape", [shape.name for shape in SHAPES])
@pytest.mark.parametrize("where", [*TREES, *DOCUMENTS])
def test_a_planted_name_of_each_shape_fails_in_each_place(
    tmp_path: Path, shape: str, where: str
) -> None:
    name = PLANTED[shape]
    path = tmp_path / where / "planted.py" if where in TREES else tmp_path / where
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"A first line.\nA case of `{name}` stands here.\n", encoding="utf-8")
    assert findings(tmp_path) == [Finding(path.relative_to(tmp_path).as_posix(), 2, shape, name)]


def test_every_shape_has_a_planted_name() -> None:
    assert set(PLANTED) == {shape.name for shape in SHAPES}


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("sdk-core, sdk-template and sdk-example", id="repositories"),
        pytest.param("xippios-core[mcp]~=0.5.0, xippios-mcp, xippios-example", id="distributions"),
        pytest.param("xippios-example-mcp-read and the topic xippios-sdk", id="names"),
        pytest.param(
            "from xippios.core import KeyAuth; import xippios.example.tasks", id="imports"
        ),
        pytest.param("EXAMPLE_API_KEY, EXAMPLE_ACME_REFRESH_TOKEN and PLACEHOLDER_KEY", id="keys"),
        pytest.param("https://api.example.org/v1 and https://github.com/xippios", id="hosts"),
        pytest.param("a host on example.test or localhost", id="reserved"),
        pytest.param("xippios-<source> and EXAMPLE_<NAME>_API_KEY", id="placeholders"),
    ],
)
def test_what_core_may_name_passes(text: str) -> None:
    assert names_in(text) == []


def test_a_name_in_a_citation_passes_and_the_same_name_outside_it_fails() -> None:
    repository = "sdk" + "-planted"
    cited = (
        f"https://github.com/xippios/{repository}/issues/60, part 1, "
        f"https://github.com/xippios/{repository}/pull/7#issuecomment-1, "
        f"https://github.com/xippios/{repository}/blob/main/docs/adr/0001-a-record.md and "
        f"https://github.com/xippios/{repository}/blob/main/docs/reports/2026-11-24-a-report.md"
    )
    assert names_in(cited) == []
    for named in (
        f"{repository}'s first record, https://github.com/xippios/{repository}/issues/60",
        f"the repository https://github.com/xippios/{repository}",
        f"https://github.com/xippios/{repository}/blob/main/src/xippios/tasks.py",
        f"[the record of `{repository}`](https://github.com/xippios/{repository}/issues/60)",
    ):
        assert names_in(named) == [(1, "repository", repository)], named


def test_a_name_on_a_later_line_than_a_citation_keeps_its_line() -> None:
    repository = "sdk" + "-planted"
    text = f"https://github.com/xippios/{repository}/issues/1\n\n{repository}\n"
    assert names_in(text) == [(3, "repository", repository)]


@pytest.mark.parametrize(
    "where",
    [
        "docs/adr/0001-a-record.md",
        "docs/reports/2026-11-24-a-report.md",
        "CHANGELOG.md",
        "changelog/added-a-change.md",
        "docs/adr.md",
    ],
)
def test_the_records_the_reports_and_the_changelog_are_not_read(tmp_path: Path, where: str) -> None:
    path = tmp_path / where
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{PLANTED['repository']} and {PLANTED['host']}\n", encoding="utf-8")
    assert findings(tmp_path) == []


@pytest.mark.parametrize(
    "planted",
    [
        # Each begins with a word that a name of the tree begins with, and is another name
        # (finding 2 of the review of https://github.com/xippios/sdk-core/pull/556).
        "TENANT" + "_PLANTED_API_KEY",
        "API" + "_PLANTED_KEY",
        "NEXT" + "_PLANTED_TOKEN",
        "OTHER" + "_PLANTED_SECRET",
        "PLACEHOLDER" + "_PLANTED_KEY",
        "HIDDEN" + "_PLANTED_PASSWORD",
        "REFRESH" + "_PLANTED_TOKEN",
    ],
)
def test_a_variable_that_only_begins_like_an_allowed_one_fails(planted: str) -> None:
    assert names_in(f"`{planted}` is read") == [(1, "credential's variable", planted)]


def test_a_host_outside_the_list_fails_however_it_starts() -> None:
    # A host that begins like an allowed one is another host.
    planted = "api.example.org.elsewhere" + ".gov"
    assert names_in(f"https://{planted}/v1") == [(1, "host", planted)]
