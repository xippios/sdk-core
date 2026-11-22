"""The sentences of `docs/conventions.md` that the cases of ADR-0043 stand on, and ADR-0055's,
the preview rule of ADR-0050, the recording of a task's exchanges of ADR-0057, the names of a
request's country codes of ADR-0056, the check of the committed FETCHED.md of ADR-0046,
decision 6, the attribution check of its decision 7, the refusal of a hinted value of ADR-0041's
amendment of 2026-11-22, the two sentences of a period series that ADR-0054's amendment of
2026-11-22 words, a recorder's field of a request of ADR-0048, decision 7, the review
checklist's sentence that holds an adoption against the two lists of the handover's section for
the release, and ADR-0058's two: what a core patch keeps compatible, and the fourth reason for
code with one consumer, as the definition of done and the review checklist name it.

The organization's release check quotes the conventions from sdk-core's `main`, and a finding
blocks only where it quotes the sentence that a change breaks
(https://github.com/xippios/.github/issues/119). Each rule below is therefore one sentence that
can be quoted alone, citing its record, and the review checklist's item that judges it cites
the record too. A later edit that splits a rule or drops its citation fails here.
"""

import json
import re
from pathlib import Path

import pytest

from xippios.core.testing import family

ROOT = Path(__file__).resolve().parents[1]
CONVENTIONS = ROOT / "docs" / "conventions.md"
CHECKLIST = ROOT / "docs" / "review-checklist.md"
DONE = ROOT / "docs" / "definition-of-done.md"
INDEX = ROOT / "docs" / "adr.json"
RECORD = "ADR-0043"
QUESTIONS = (
    "https://github.com/xippios/sdk-core/issues/355",  # the versions of an entry, no rewording
    "https://github.com/xippios/sdk-core/issues/382",  # the live run on the release's base
)


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
        # sdk-usda-esr's example is the body it refused (decision 2 of sdk-usda-esr#55).
        ("the fourth", "serves no empty 404 off an exports path", "sdk-cashctrl"),
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
    # §12: the release's pull request and its entries (sdk-core#355), its live run (sdk-core#351,
    # decided by the human in sdk-core#382).
    pytest.param(
        12,
        "assembles each entry as its fragment reads",
        ("rewords or regroups none", "https://github.com/xippios/sdk-core/issues/355"),
        id="s12-a-release-rewords-no-entry",
    ),
    pytest.param(
        12,
        "cites a green run of `live.yml` on the commit of `main` that it starts from",
        (
            "the nightly run or one dispatch",
            "https://github.com/xippios/sdk-core/issues/351",
            "https://github.com/xippios/sdk-core/issues/382",
        ),
        id="s12-the-live-run-a-release-cites",
    ),
    pytest.param(
        12,
        "A run on an earlier commit of `main` is no such run, whatever the merges after it changed",
        (
            "https://github.com/xippios/sdk-core/issues/351",
            "https://github.com/xippios/sdk-core/issues/382",
        ),
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
    # §15, the host: item 9 read for a package that no template renders (sdk-core#355).
    pytest.param(
        15,
        "item 9's fragment names the core bound and the conventions' version as they stand after "
        "the adoption, changed or not",
        ("no template", "https://github.com/xippios/sdk-core/issues/355"),
        id="s15-the-versions-of-the-host-s-entry",
    ),
]


@pytest.mark.parametrize(("number", "phrase", "names"), RULES)
def test_each_rule_is_one_sentence_that_cites_its_record(
    number: int, phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(number), phrase)
    for name in (RECORD, *names):
        assert name in rule, f"§{number}: {rule!r} does not name {name!r}"


LIVE_LISTS_RULES = [
    # §10, the paragraph on live tests: the nightly comparison of a packaged list
    # (https://github.com/xippios/sdk-core/issues/374).
    pytest.param(
        "A live comparison of a public reference list may name in the log the codes",
        ("gone, new or changed", "never a record's other fields"),
        id="s10-codes-in-the-log",
    ),
    pytest.param(
        "A source declares in `tests/test_live.py`",
        ("`LIVE_LISTS`", "`NO_LIVE_LIST` with the reason", "stands in neither"),
        id="s10-the-declaration",
    ),
    pytest.param(
        "A code gone from upstream's list, a code new in it and a code whose record changed each "
        "fail the nightly run",
        ("the list's declared code in any order",),
        id="s10-what-fails-the-run",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), LIVE_LISTS_RULES)
def test_each_rule_of_the_live_comparison_is_one_sentence_that_cites_adr_0055(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(10), phrase)
    for name in ("ADR-0055", *names):
        assert name in rule, f"§10: {rule!r} does not name {name!r}"


EXEMPTION = "stands in `UNNAMED_CODES` of its tasks module with the reason"
"""The phrase of §4's sentence on the exemption and the family check (ADR-0056)."""

NAMES_RULES = [
    # §4, at the envelope's meta: the name of each country code of a request
    # (https://github.com/xippios/sdk-core/issues/375).
    pytest.param(
        "`meta.names` maps each country parameter of the request",
        ("`dict[str, dict[str, str]]`", "left out of a dumped answer while it is empty"),
        id="s4-the-field",
    ),
    pytest.param(
        "fills it with core's decorator `names_codes",
        ("one `PackagedCodes` per parameter", "withholds an answer for a code its list lacks"),
        id="s4-the-decorator",
    ),
    pytest.param(
        EXEMPTION,
        ("the family check fails", "and stands in neither"),
        id="s4-the-exemption",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), NAMES_RULES)
def test_each_rule_of_the_names_of_codes_is_one_sentence_that_cites_adr_0056(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(4), phrase)
    for name in ("ADR-0056", *names):
        assert name in rule, f"§4: {rule!r} does not name {name!r}"


def test_the_refusal_of_a_hinted_value_is_one_sentence_that_cites_its_amendment() -> None:
    # §5, beside the refusal of a code the packaged list lacks: a value of the check's hint
    # table is no code, so its refusal leaves out the list's age, as the question that amended
    # ADR-0041 decided (https://github.com/xippios/sdk-core/issues/440).
    rule = sentence(section(5), "A refusal of a value of the check's hint table")
    for name in (
        "ADR-0041, decision 8, amendment 2026-11-22",
        "leaves out that the packaged list is out of date",
    ):
        assert name in rule, f"§5: {rule!r} does not name {name!r}"


SERIES_RULES = [
    # §4, the period series: a task calls the ceiling's check before any request of the call,
    # so that its refusal's sentence that nothing was sent is true, as §5 asks of a refusal of
    # the call as given, and a task that checks only after a request words that refusal itself;
    # a later failure names the periods before it as answered, true of a pass that counts, as
    # the two questions that amended ADR-0054 decided
    # (https://github.com/xippios/sdk-core/issues/438,
    # https://github.com/xippios/sdk-core/issues/454).
    pytest.param(
        "A task calls the ceiling's `check` before any request of the call",
        (
            "says that nothing was sent",
            "before its advice",
            "§5",
            "only after a request",
            "words that refusal itself and says what was sent",
            "ADR-0054, decision 5, amendment 2026-11-22",
        ),
        id="s4-the-ceiling-s-refusal",
    ),
    pytest.param(
        "When a request of a period series after the first fails",
        ("the periods answered before it", "ADR-0054, decision 6, amendment 2026-11-22"),
        id="s4-a-later-failure",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), SERIES_RULES)
def test_each_rule_of_a_series_message_is_one_sentence_that_cites_its_amendment(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(4), phrase)
    for name in names:
        assert name in rule, f"§4: {rule!r} does not name {name!r}"


def test_the_exemption_s_sentence_names_the_words_of_the_family_check_in_their_order() -> None:
    # The organization's check quotes the sentence alone, so it lists exactly the words that
    # the check looks for (ADR-0056, decision 5), read here from the check itself.
    words = family._COUNTRY.pattern.split("|")
    assert all(word.isalpha() for word in words), f"{words!r}: a word, no pattern"
    listed = ", ".join(f"`{word}`" for word in words[:-1]) + f" or `{words[-1]}`"
    rule = sentence(section(4), EXEMPTION)
    assert listed in rule, f"§4: {rule!r} does not list {listed!r}"


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


HANDOVER_ROWS = (
    "https://github.com/xippios/sdk-core/issues/334",  # the changes that a source's callers see
    "https://github.com/xippios/sdk-core/issues/349",  # the conventions' rules that changed
)


def test_the_review_checklist_holds_an_adoption_against_the_handover_s_two_lists() -> None:
    # Item 12 reads §15's items 8 and 9 through the handover's section for the release, so
    # an adoption's review names the same rules and the same entries in every source.
    rule = sentence(checklist_item(12), "the two lists of the handover's section")
    for name in (
        "`Adopting core X.Y.Z`",
        "the conventions' rules changed since",
        "§15 item 8",
        "the changes that a source's callers see",
        "the adoption's fragments",
        *HANDOVER_ROWS,
    ):
        assert name in rule, f"item 12: {rule!r} does not name {name!r}"


def test_the_definition_of_done_words_an_adoption_s_fragment_as_item_9_does() -> None:
    # The line of the Adoption PR block, which "the versions adopted" made a second reading of
    # item 9 (https://github.com/xippios/sdk-core/issues/347).
    block = DONE.read_text(encoding="utf-8").split("## Adoption PR", 1)[1].split("\n## ", 1)[0]
    lines = [flat(line) for line in block.splitlines() if "changelog fragment" in line]
    assert len(lines) == 1, "the Adoption PR block has one line on the changelog fragment"
    for name in (
        "the core bound, the template's tag and the conventions' version as they stand after "
        "the adoption, changed or not",
        "`breaking` where the adoption brings a core minor",
        "`changed` where it brings none",
        "§15 item 9",
        RECORD,
    ):
        assert name in lines[0], f"{lines[0]!r} does not name {name!r}"


def test_the_definition_of_done_holds_an_adoption_against_the_handover_s_two_lists() -> None:
    # The opener's list names what item 12 of the review checklist holds the adoption to, so
    # an adoption meets before its review the two lists that its review reads.
    block = DONE.read_text(encoding="utf-8").split("## Adoption PR", 1)[1].split("\n## ", 1)[0]
    lines = [flat(line) for line in block.splitlines() if line.startswith("- [ ]")]
    version = [line for line in lines if "the current conventions version applied" in line]
    fragment = [line for line in lines if "changelog fragment" in line]
    assert len(version) == len(fragment) == 1, "one line on the version, one on the fragment"
    for line, names in (
        (version[0], ("the conventions' rules changed since", HANDOVER_ROWS[1])),
        (fragment[0], ("the changes that a source's callers see", HANDOVER_ROWS[0])),
    ):
        for name in ("`Adopting core X.Y.Z`", *names):
            assert name in line, f"{line!r} does not name {name!r}"


def test_both_questions_keep_the_record() -> None:
    # `coordinate decision show <question>` finds a record by its decider and its amendments.
    records = json.loads(INDEX.read_text(encoding="utf-8"))["records"]
    found = next(r for r in records if r["id"] == RECORD)
    kept = [found["decided_by"], *(entry["by"] for entry in found["amended"])]
    assert kept == list(QUESTIONS)


# §8: what a write tool's preview shows, and its check (sdk-core#182, decided by the human in
# https://github.com/xippios/sdk-core/issues/369). The confirm rule stays ADR-0036's, decision 9.

PREVIEW_RECORD = "ADR-0050"
PREVIEW_QUESTION = "https://github.com/xippios/sdk-core/issues/369"

PREVIEW_RULES = [
    pytest.param(
        "A write task's preview sends no write and shows the action as the confirmed call would "
        "send it",
        ("ADR-0036, decision 9", "ADR-0050, decision 1"),
        id="s8-what-a-preview-shows",
    ),
    pytest.param(
        "is the write task's choice, and its docstring says whether its preview reads and what "
        "that read costs",
        ("Whether a preview reads first", "ADR-0050, decision 2"),
        id="s8-whether-a-preview-reads",
    ),
    pytest.param(
        "The preview carries `reads: list[str]`",
        ("the operations it read", "`[]` when it read nothing", "ADR-0050, decision 3"),
        id="s8-the-preview-s-reads",
    ),
    pytest.param(
        "fails a write task unless its `Result`'s data has exactly one member tagged "
        "`performed: Literal[False]`",
        ("preview_reads=True)`", "declares `reads`", "ADR-0050, decision 4"),
        id="s8-the-check-of-the-annotations",
    ),
    pytest.param(
        "calls each write tool without `confirm`",
        (
            "dry_run=...",
            "no request but a read",
            "`is_read`",
            "`reads` is empty exactly when it sent no request",
            "ADR-0050, decisions 5 and 6",
        ),
        id="s8-the-dry-run",
    ),
    pytest.param(
        "passes `preview_reads=True` from its patch on core 0.4.1",
        ("the dry run at its own choice", "off by default", "ADR-0050, decisions 4 and 5"),
        id="s8-when-a-source-switches-them-on",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), PREVIEW_RULES)
def test_each_rule_of_the_preview_is_one_sentence_that_cites_its_record(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(8), phrase)
    for name in names:
        assert name in rule, f"§8: {rule!r} does not name {name!r}"


def test_the_review_checklist_judges_a_write_task_s_preview_by_its_record() -> None:
    item = checklist_item(18)
    for name in (
        "**Write tools**",
        "whether its preview reads first and what the read costs",
        "preview_reads=True)`",
        "conventions §8",
        PREVIEW_RECORD,
    ):
        assert name in item, f"item 18 does not name {name!r}"


def test_the_preview_record_keeps_its_question() -> None:
    records = json.loads(INDEX.read_text(encoding="utf-8"))["records"]
    found = next(r for r in records if r["id"] == PREVIEW_RECORD)
    assert (found["decided_by"], found["amended"]) == (PREVIEW_QUESTION, [])


# §10, the layout of fixtures and the recorder: the recording of every exchange of a task
# (sdk-core#174, decided by the human in https://github.com/xippios/sdk-core/issues/376).

TASK_RECORD = "ADR-0057"

TASK_RULES = [
    pytest.param(
        "The exchanges of one recording of a task are numbered in the order the task made them",
        (
            "the first as `<case>.json`",
            "from the second on, as `<case>_<k>.json`",
            "beyond its last exchange writes nothing",
            "ADR-0057, decision 6",
        ),
        id="s10-the-numbering",
    ),
    pytest.param(
        "`record_task` records every exchange that a task makes through any client",
        (
            "each sent once",
            "none answered from the cache",
            "writes all of them or none",
            "no token request inside an auth flow",
            "refuses a task that downloads",
        ),
        id="s10-what-a-task-s-recording-holds",
    ),
    pytest.param(
        "`record_task` reads every answer of a task whole",
        ("as the task's client reads it", "`max_read_bytes` bounds none of them"),
        id="s10-a-task-s-answers-read-whole",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), TASK_RULES)
def test_each_rule_of_a_task_s_recording_is_one_sentence_that_cites_adr_0057(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(10), phrase)
    for name in (TASK_RECORD, *names):
        assert name in rule, f"§10: {rule!r} does not name {name!r}"


def test_a_recorder_redacts_a_field_of_a_request_and_drops_none_by_adr_0048() -> None:
    # §10, the recorder's rewrite step: what it writes for a field of a request that it must
    # not keep, the maintainer's answer on https://github.com/xippios/sdk-core/issues/439. It
    # drops none of a request's fields, and says nothing of an answer's.
    rule = sentence(section(10), "A recorder writes `REDACTED` in place of the value of a field")
    for name in ("of a request that it must not keep", "drops none of them", "key by key"):
        assert name in rule, f"§10: {rule!r} does not name {name!r}"
    assert "drops no field" not in rule, f"§10: {rule!r} reaches an answer's fields"
    assert "ADR-0048, decision 7" in rule, f"§10: {rule!r} does not cite its record"


# §3, the snapshot: the check of the committed FETCHED.md without a request (sdk-core#426,
# decided by the human in https://github.com/xippios/sdk-core/issues/428).

SNAPSHOT_DECISION = "ADR-0046, decision 6"

SNAPSHOT_RULES = [
    pytest.param(
        "names its `Snapshot` `SNAPSHOT` at its top level",
        ("sends no request and writes no file", 'if __name__ == "__main__":', "the family check"),
        id="s3-the-name-of-the-declaration",
    ),
    pytest.param(
        "ends `FETCHED.md` with one line that names the file's form",
        ("rewords what the frame writes into the file raises the form",),
        id="s3-the-mark-of-the-form",
    ),
    pytest.param(
        "The family check fails a source whose committed `FETCHED.md`",
        ("differs from its `SNAPSHOT`", "the form of an ETag's cell", "a file without a row"),
        id="s3-what-the-check-holds",
    ),
    pytest.param(
        "What only a response knows is read back from the file and not judged",
        ("sizes and hashes", "`linked`", "`split`", "`sections`", "second origin"),
        id="s3-what-the-check-reads-back",
    ),
    pytest.param(
        "A source passes the check while its script declares no `SNAPSHOT`",
        ("no mark of the form its core writes", "held from its first refresh on"),
        id="s3-what-the-check-passes",
    ),
]


@pytest.mark.parametrize(("phrase", "names"), SNAPSHOT_RULES)
def test_each_rule_of_the_check_of_fetched_md_is_one_sentence_that_cites_adr_0046(
    phrase: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(3), phrase)
    for name in (SNAPSHOT_DECISION, *names):
        assert name in rule, f"§3: {rule!r} does not name {name!r}"


# §3, the snapshot: what the frame's attribution check reads and accepts, by the maintainer's
# answer on https://github.com/xippios/sdk-core/issues/437 (ADR-0046, decision 7), and the rule
# on an API document's `info` that only the code and its tests stated
# (https://github.com/xippios/sdk-x/issues/57), which no question decided and ADR-0046 states in
# its Consequences (finding 2 of the review of https://github.com/xippios/sdk-core/pull/451).

ATTRIBUTION_DECISION = "ADR-0046, decision 7"
ATTRIBUTION_CONSEQUENCES = "ADR-0046, Consequences"

ATTRIBUTION_RULES = [
    pytest.param(
        "The frame's attribution check reads an HTML page's visible text",
        ATTRIBUTION_DECISION,
        (
            "alternative text",
            "where the image stands",
            "no other attribute",
            "without the alternative text",
            "a sample",
        ),
        id="s3-what-the-attribution-check-reads",
    ),
    pytest.param(
        "A statement recorded with a link passes the check only as the text of a link",
        ATTRIBUTION_DECISION,
        ("on any page", "without a link", "vocabulary", "no HTML"),
        id="s3-a-statement-recorded-with-a-link",
    ),
    pytest.param(
        "An API document in JSON names a licence, terms or a contact in its `info`",
        ATTRIBUTION_CONSEQUENCES,
        ("`license`", "`termsOfService`", "`contact`", "YAML"),
        id="s3-an-api-document-s-info",
    ),
]


@pytest.mark.parametrize(("phrase", "record", "names"), ATTRIBUTION_RULES)
def test_each_rule_of_the_attribution_check_is_one_sentence_that_cites_adr_0046(
    phrase: str, record: str, names: tuple[str, ...]
) -> None:
    rule = sentence(section(3), phrase)
    for name in (record, *names):
        assert name in rule, f"§3: {rule!r} does not name {name!r}"
    others = {ATTRIBUTION_DECISION, ATTRIBUTION_CONSEQUENCES} - {record}
    assert not any(other in rule for other in others), f"§3: {rule!r} cites another part"


def test_the_review_checklist_holds_the_name_the_family_check_reads() -> None:
    # The family check passes a script that names its declaration otherwise, so the review
    # holds the name (ADR-0046, decision 6).
    item = checklist_item(2)
    for name in ("`SNAPSHOT`", "`scripts/refresh_upstream.py`", SNAPSHOT_DECISION):
        assert name in item, f"item 2 does not name {name!r}"


# §12 and the code a core PR adds: the maintainer's answer on
# https://github.com/xippios/sdk-core/issues/455, ADR-0058. A patch keeps a source's package and
# its callers compatible while a stricter check may fail a source's own test, and the
# maintainer's decision on a step's closed design question is a fourth reason for one consumer.

PATCH_RECORD = "ADR-0058"
PATCH_QUESTION = "https://github.com/xippios/sdk-core/issues/455"
COMPATIBLE = "Core patch releases stay compatible."
"""The sentence of §12 that the organization's check quoted, whose reach ADR-0058 states."""


def test_what_a_core_patch_keeps_compatible_is_one_sentence_that_cites_adr_0058() -> None:
    # It stands right after the sentence it says the reach of, so the check reads them together.
    text = section(12)
    phrase = "A patch of core keeps a source's package and its callers compatible"
    rule = sentence(text, phrase)
    for name in (
        "a check of `xippios.core.testing`",
        "the family check",
        "the recorder",
        "makes stricter",
        "may fail a source's own test at the lock's move",
        "`Adopting core X.Y.Z`",
        PATCH_QUESTION,
        "ADR-0058, decision 2",
    ):
        assert name in rule, f"§12: {rule!r} does not name {name!r}"
    assert f"{COMPATIBLE} {phrase}" in text, f"§12: {phrase!r} does not follow {COMPATIBLE!r}"


def test_the_one_consumer_reason_names_the_record_that_adds_the_fourth() -> None:
    # The definition of done's line on consumers and the review checklist's item 11 judge a core
    # PR's ADR by the reasons of ADR-0023, decision 3, and by the fourth that ADR-0058 adds, so
    # an ADR that names the fourth meets both as they read.
    done = DONE.read_text(encoding="utf-8").splitlines()
    lines = [flat(line) for line in done if "the two consumers of what it adds" in line]
    assert len(lines) == 1, "the definition of done has one line on a core PR's consumers"
    for where, rule in (("the definition of done", lines[0]), ("item 11", checklist_item(11))):
        for name in ("the one-consumer reason of ADR-0023 decision 3", "ADR-0058, decision 1"):
            assert name in rule, f"{where}: {rule!r} does not name {name!r}"


def test_the_patch_record_keeps_its_question() -> None:
    records = json.loads(INDEX.read_text(encoding="utf-8"))["records"]
    found = next((r for r in records if r["id"] == PATCH_RECORD), None)
    assert found, f"the index holds no {PATCH_RECORD}"
    assert (found["decided_by"], found["amended"]) == (PATCH_QUESTION, [])
