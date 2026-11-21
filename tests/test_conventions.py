"""The sentences of `docs/conventions.md` that the cases of ADR-0043 stand on.

The organization's release check quotes the conventions from sdk-core's `main`, and a finding
blocks only where it quotes the sentence that a change breaks
(https://github.com/xippios/.github/issues/119). Each rule below is therefore one sentence that
can be quoted alone, citing its record, and the review checklist's item that judges it cites
the record too. A later edit that splits a rule or drops its citation fails here.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONVENTIONS = ROOT / "docs" / "conventions.md"
CHECKLIST = ROOT / "docs" / "review-checklist.md"
RECORD = "ADR-0043"


def flat(text: str) -> str:
    """The text on one line, so that a phrase matches across the file's line breaks."""
    return " ".join(text.split())


def section(number: int) -> str:
    """Section `## <number>.` of the conventions, up to the next heading."""
    text = CONVENTIONS.read_text(encoding="utf-8")
    found = re.search(rf"^## {number}\. .*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert found, f"the conventions have no section {number}"
    return flat(found.group(0))


def checklist_item(number: int) -> str:
    """Item `<number>.` of the review checklist's list, up to the next item or heading."""
    text = CHECKLIST.read_text(encoding="utf-8")
    pattern = rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|^## |\Z)"
    found = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    assert found, f"the review checklist has no item {number}"
    return flat(found.group(0))


def sentence(text: str, phrase: str) -> str:
    """The sentence of `text` that holds `phrase`, from the end of the one before to its own."""
    start = text.find(phrase)
    assert start >= 0, f"no sentence holds {phrase!r}"
    begin = text.rfind(". ", 0, start)
    end = text.find(". ", start)
    return text[begin + 2 if begin >= 0 else 0 : end + 1 if end >= 0 else len(text)]


RULES = [
    # §5: which of a source's own messages name their request (sdk-core#346).
    pytest.param(
        5,
        "The messages that name their request are those about an answer",
        ("ADR-0030, decision 4",),
        id="s5-the-messages-that-name-their-request",
    ),
    pytest.param(
        5,
        "names no request: it names the argument, the record or the tool that it refuses and "
        "says that nothing was sent",
        ("ADR-0030, decision 4", "sdk-cashctrl"),
        id="s5-a-refusal-of-the-call-as-given",
    ),
    pytest.param(
        5,
        "The subject of a decoder that reads a body without its response names no request",
        ("ADR-0030, decision 4", "`parse`"),
        id="s5-a-decoder-s-subject",
    ),
    # §10: the three cases between the kinds of a built answer, each with its sources
    # (sdk-core#345).
    pytest.param(
        10,
        "changed in its status, its content type and its body at once is a new answer composed "
        "in a recorded shape, the second kind",
        ("the fourth", "sdk-usda-esr", "sdk-cashctrl"),
        id="s10-a-recording-changed-three-ways",
    ),
    pytest.param(
        10,
        "is an input of the test and takes no kind",
        ("no route serves", "sdk-google-mail", "sdk-cashctrl"),
        id="s10-an-input-of-the-test",
    ),
    pytest.param(
        10,
        "A recording replayed at its own path for other parameters is the third kind",
        ("names the condition under which upstream answers", "sdk-google-mail", "sdk-cashctrl"),
        id="s10-a-recording-at-its-own-path",
    ),
    # §12: the release's pull request and its entries (sdk-core#355), its live run (sdk-core#351).
    pytest.param(
        12,
        "assembles each entry as its fragment reads",
        ("rewords or regroups none", "https://github.com/xippios/sdk-core/issues/355"),
        id="s12-a-release-rewords-no-entry",
    ),
    pytest.param(
        12,
        "cites a green run of `live.yml` on the commit of `main` that it starts from",
        ("the nightly run or one dispatch", "https://github.com/xippios/sdk-core/issues/351"),
        id="s12-the-live-run-a-release-cites",
    ),
    pytest.param(
        12,
        "A run on an earlier commit of `main` is no such run, whatever the merges after it changed",
        ("https://github.com/xippios/sdk-core/issues/351",),
        id="s12-an-older-live-run",
    ),
    # §15, item 9: the versions an adoption's entry names (sdk-core#355) and its group
    # (sdk-core#342).
    pytest.param(
        15,
        "names the core bound, the template's tag and the conventions' version as they stand "
        "after the adoption, changed or not",
        ("template-only", "https://github.com/xippios/sdk-core/issues/355"),
        id="s15-the-versions-of-an-adoption-s-entry",
    ),
    pytest.param(
        15,
        "is `breaking` where the adoption brings a core minor",
        ("`changed` where it brings none", "https://github.com/xippios/sdk-core/issues/342"),
        id="s15-the-group-of-an-adoption-s-fragment",
    ),
]


@pytest.mark.parametrize(("number", "phrase", "names"), RULES)
def test_each_rule_is_one_sentence_that_cites_its_record(
    number: int, phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(number), phrase)
    for name in (RECORD, *names):
        assert name in rule, f"§{number}: {rule!r} does not name {name!r}"


@pytest.mark.parametrize(
    ("number", "phrase"),
    [
        pytest.param(3, "a refusal the package makes of the call as given", id="errors"),
        pytest.param(4, "the three cases that §10 settles", id="fixtures"),
        pytest.param(12, "`breaking` where it brings a core minor", id="adoption"),
        pytest.param(13, "a green run of `live.yml`", id="release"),
    ],
)
def test_the_review_checklist_judges_each_rule_by_its_record(number: int, phrase: str) -> None:
    item = checklist_item(number)
    assert phrase in item, f"item {number} does not say {phrase!r}"
    assert RECORD in item, f"item {number} does not cite {RECORD}"
