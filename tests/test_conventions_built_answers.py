"""The sentences of `docs/conventions.md` §10 that the check of a built answer's mark stands on.

As `tests/test_conventions.py` holds the cases of ADR-0043, each rule here is one sentence that
can be quoted alone and cites ADR-0049, the review checklist's item on fixtures cites the record,
and the README's section on testing a source shows the line that collects the check.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONVENTIONS = ROOT / "docs" / "conventions.md"
CHECKLIST = ROOT / "docs" / "review-checklist.md"
README = ROOT / "README.md"
INDEX = ROOT / "docs" / "adr.json"
RECORD = "ADR-0049"
QUESTION = "https://github.com/xippios/sdk-core/issues/367"


def flat(text: str) -> str:
    """The text on one line, so that a phrase matches across the file's line breaks."""
    return " ".join(text.split())


def block(path: Path, heading: str) -> str:
    """The part of ``path`` from the line ``heading`` to the next heading of its level.

    A heading inside a fenced code block, an example's, is the block's text.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    assert heading in lines, f"{path.name} has no {heading!r}"
    level = heading.split(" ", 1)[0] + " "
    kept, fenced = [], False
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith(level):
            break
        kept.append(line)
    return "\n".join([heading, *kept])


def sentence(text: str, phrase: str) -> str:
    """The sentence of ``text`` that holds ``phrase``, from the end of the one before to its own."""
    start = text.find(phrase)
    assert start >= 0, f"no sentence holds {phrase!r}"
    begin = text.rfind(". ", 0, start)
    end = text.find(". ", start)
    return text[begin + 2 if begin >= 0 else 0 : end + 1 if end >= 0 else len(text)]


RULES = [
    pytest.param(
        "A test marks a body of these kinds where it builds it by naming `§10` and the body's kind",
        ("`kind 1` to `kind 5`", "one docstring or one block of comments", "`NOT RECORDED: "),
        id="the-form-of-the-mark",
    ),
    pytest.param(
        "A mark reaches the places of the function or class whose docstring holds it",
        (
            "of the statement that it stands on or above",
            "of every call of a helper whose docstring holds it",
            "a module's docstring reaches nothing",
        ),
        id="the-reach-of-a-mark",
    ),
    pytest.param(
        "is an input of the test, not an answer from <upstream>.`",
        ("in place of a kind", 'fixed up to the word "test"'),
        id="the-input-s-sentence",
    ),
    pytest.param(
        "A replay that answers another request than its recording",
        (
            "its host, its path, its query or its body",
            "the recording's redaction",
            "is the third kind",
            "`kind 3` beside `§10`",
        ),
        id="the-census",
    ),
    pytest.param(
        "`xippios.core.testing.built_answers`, which a source collects with one line",
        ("names its file and its line", "after every other test", "the tests that ran"),
        id="the-check",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), RULES)
def test_each_rule_of_the_mark_is_one_sentence_that_cites_its_record(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(flat(block(CONVENTIONS, "## 10. Testing")), phrase)
    for name in (RECORD, *names):
        assert name in rule, f"§10: {rule!r} does not name {name!r}"


def test_the_review_checklist_judges_a_served_body_by_its_mark() -> None:
    text = flat(CHECKLIST.read_text(encoding="utf-8"))
    item = re.search(r"4\. \*\*Fixtures\*\*.*?(?= 5\. \*\*)", text)
    assert item, "the review checklist has no item 4 on fixtures"
    for name in ("marked as §10 states the mark", "`xippios.core.testing.built_answers`", RECORD):
        assert name in item.group(0), f"item 4 does not say {name!r}"


def test_the_readme_shows_the_collecting_line_and_the_table() -> None:
    section = block(README, "## Testing a source package")
    for name in (
        "from xippios.core.testing.built_answers import *  # noqa: F403",
        "READERS = frozenset(",
        "ALLOWED = {",
        "A partial run judges only the tests that ran",
        "pytest-xdist",
    ):
        assert name in section, f"the README's testing section does not show {name!r}"


def test_the_record_keeps_its_question() -> None:
    records = json.loads(INDEX.read_text(encoding="utf-8"))["records"]
    found = next(record for record in records if record["id"] == RECORD)
    assert found["decided_by"] == QUESTION
