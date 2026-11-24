"""The nightly comparison of a packaged list with the list upstream serves now (ADR-0055).

The proof of https://github.com/xippios/sdk-core/issues/319: on a recorded list, a code that
upstream added and one that it removed are both named, and an equal list passes. A changed
name is named by its code and never shown, a list in another order is equal, and a fetch
returns records or bare codes. The collected test runs under the live gate with a fetch that
the test supplies, reading a recorded list, as the plugin's tests drive a live run without a
network.
"""

import importlib
import json
import sys
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

import pytest
from pydantic import Field

from xippios.core import Answer, PackagedCodes, PackagedList, UpstreamModel
from xippios.core.reference import _read_text
from xippios.core.testing import live
from xippios.core.testing.live import assert_list_current
from xippios.core.testing.plugin import LIVE_ENV

FETCHED = "2026-10-23T09:00:00Z"

RECORDS: list[dict[str, Any]] = [
    {"countryCode": "US", "countryName": "United States", "regionCode": "R01"},
    {"countryCode": "BR", "countryName": "Brazil", "regionCode": "R04"},
    {"countryCode": "E4", "countryName": "European Union", "regionCode": "R03"},
]
"""A source's countries as its packaged file holds them, text codes."""


def codes_of(
    records: list[dict[str, Any]], code: str = "countryCode", name: str | None = "countryName"
) -> PackagedCodes:
    """A packaged list of ``records``, declared by its code and name fields."""
    packaged = PackagedList.model_validate(
        {
            "param": "countries",
            "endpoint": "countries",
            "fetched": FETCHED,
            "records": records,
        }
    )
    return packaged.codes(code, name)


TEXT_CODES = codes_of(RECORDS)

INTEGER_CODES = PackagedList.model_validate(
    {
        "param": "commodities",
        "endpoint": "commodities",
        "fetched": FETCHED,
        "records": [
            {"commodityCode": 104, "commodityName": "Wheat - White"},
            {"commodityCode": 107, "commodityName": "Wheat - HRW"},
        ],
    }
).codes("commodityCode", "commodityName")
"""A source's commodities, integer codes."""


def head(gone: int, new: int, changed: int, packaged: int = 3, served: int = 3) -> str:
    return (
        f"packaged list countries (fetched 2026-10-23) differs from the list upstream serves "
        f"now: {gone} gone, {new} new, {changed} changed of {packaged} packaged codes, {served} "
        "served; refresh it (conventions §10, ADR-0055):"
    )


def failure(codes: PackagedCodes, current: Any, **options: Any) -> list[str]:
    """The lines of the failure ``assert_list_current`` fails the test with."""
    with pytest.raises(pytest.fail.Exception) as failed:
        assert_list_current(codes, current, **options)
    assert not failed.value.pytrace, "the failure shows no frame of the test"
    return str(failed.value).splitlines()


def test_the_list_upstream_serves_unchanged_passes_in_any_order() -> None:
    assert_list_current(TEXT_CODES, RECORDS)
    assert_list_current(TEXT_CODES, list(reversed(RECORDS)))
    assert_list_current(TEXT_CODES, [dict(reversed(list(record.items()))) for record in RECORDS])


def test_an_added_and_a_removed_code_are_both_named() -> None:
    argentina = {"countryCode": "AR", "countryName": "Argentina", "regionCode": "R04"}
    assert failure(TEXT_CODES, [RECORDS[0], RECORDS[2], argentina]) == [
        head(gone=1, new=1, changed=0),
        "- gone: 'BR'",
        "- new: 'AR'",
    ]


def test_a_changed_name_is_named_by_its_code_and_no_record_is_shown() -> None:
    renamed = [RECORDS[0], {**RECORDS[1], "countryName": "Brasil"}, RECORDS[2]]
    lines = failure(TEXT_CODES, renamed)
    assert lines == [head(gone=0, new=0, changed=1), "- changed: 'BR'"]
    shown = "\n".join(lines)
    for value in ("Brasil", "Brazil", "R04", "United States"):
        assert value not in shown


def test_gone_new_and_changed_are_counted_and_named_in_the_lists_order() -> None:
    current = [
        {"countryCode": "CN", "countryName": "China", "regionCode": "R02"},
        {**RECORDS[2], "regionCode": "R09"},
        {"countryCode": "AR", "countryName": "Argentina", "regionCode": "R04"},
    ]
    assert failure(TEXT_CODES, current) == [
        head(gone=2, new=2, changed=1),
        "- gone: 'US', 'BR'",
        "- new: 'CN', 'AR'",
        "- changed: 'E4'",
    ]


class Country(UpstreamModel):
    country_code: str = Field(alias="countryCode")
    country_name: str = Field(alias="countryName")
    region_code: str = Field(alias="regionCode")


def test_a_fetch_may_return_upstream_models_read_by_their_upstream_names() -> None:
    models = [Country.model_validate(record) for record in RECORDS]
    assert_list_current(TEXT_CODES, models)
    moved = [*models[:2], models[2].model_copy(update={"region_code": "R09"})]
    assert failure(TEXT_CODES, moved)[1:] == ["- changed: 'E4'"]


class Code(StrEnum):
    US = "US"


def test_bare_codes_are_compared_by_code_alone() -> None:
    assert_list_current(TEXT_CODES, ["E4", "US", "BR"])
    assert_list_current(TEXT_CODES, [Code.US, "BR", "E4", "E4"])
    assert failure(TEXT_CODES, ["US", "E4", "AR"]) == [
        head(gone=1, new=1, changed=0),
        "- gone: 'BR'",
        "- new: 'AR'",
    ]


def test_a_list_of_values_takes_its_values_as_bare_codes() -> None:
    states = codes_of([{"state_alpha": "AK"}, {"state_alpha": "VA"}], code="state_alpha", name=None)
    assert_list_current(states, ["VA", "AK"])
    assert_list_current(states, [{"state_alpha": "VA"}, {"state_alpha": "AK"}])
    assert failure(states, ["AK", "va"])[1:] == ["- gone: 'VA'", "- new: 'va'"]


def test_integer_codes_given_as_text_are_gone_and_new() -> None:
    assert_list_current(INTEGER_CODES, [107, 104])
    lines = failure(INTEGER_CODES, ["104", 107])
    assert lines[0].startswith("packaged list commodities (fetched 2026-10-23) differs")
    assert lines[1:] == ["- gone: 104", "- new: '104'"]


def test_a_code_listed_twice_compares_its_records_together() -> None:
    twice = codes_of([RECORDS[0], {**RECORDS[0], "regionCode": "R02"}])
    assert_list_current(twice, [{**RECORDS[0], "regionCode": "R02"}, RECORDS[0]])
    assert failure(twice, [RECORDS[0]]) == [
        head(gone=0, new=0, changed=1, packaged=1, served=1),
        "- changed: 'US'",
    ]


def test_a_record_is_compared_as_the_json_the_packaged_file_holds() -> None:
    dated = codes_of([{"countryCode": "US", "since": "2026-01-01"}], name=None)
    assert_list_current(dated, [{"countryCode": "US", "since": date(2026, 1, 1)}])


def test_each_kind_names_its_first_twenty_codes_and_counts_the_rest() -> None:
    many = codes_of(
        [{"countryCode": f"C{i:02d}", "countryName": f"Country {i}"} for i in range(25)]
    )
    lines = failure(many, [])
    assert lines[0] == head(gone=25, new=0, changed=0, packaged=25, served=0)
    first = ", ".join(repr(f"C{i:02d}") for i in range(20))
    assert lines[1:] == [f"- gone: {first} and 5 more"]


def test_packaged_reads_both_sides_through_one_view() -> None:
    """A source's lists carry the release they came from, which each release changes."""

    def view(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in record.items() if k != "regionCode"} for record in records]

    current = [{**record, "regionCode": "R99"} for record in RECORDS]
    assert failure(TEXT_CODES, current)[1:] == ["- changed: 'US', 'BR', 'E4'"]
    assert_list_current(TEXT_CODES, view(current), packaged=view(RECORDS))
    assert failure(TEXT_CODES, view(current[:2]), packaged=view(RECORDS))[1:] == ["- gone: 'E4'"]


@pytest.mark.parametrize(
    ("current", "problem"),
    [
        ([RECORDS[0], "BR"], "the list upstream serves now mixes records and bare codes"),
        (
            [{"countryName": "Brazil"}],
            "the list upstream serves now: record 0 has no field 'countryCode'",
        ),
        (
            [RECORDS[0], {"countryCode": None, "countryName": "Brazil"}],
            "the list upstream serves now: record 1: field 'countryCode' is neither text nor an "
            "integer",
        ),
        ([1.5], "the list upstream serves now: item 0 is a float, neither a record nor a code"),
        ([True], "the list upstream serves now: item 0 is a bool, neither a record nor a code"),
    ],
    ids=["mixed", "no-code-field", "code-of-no-type", "float", "bool"],
)
def test_a_list_that_holds_neither_records_nor_codes_fails_naming_the_item(
    current: list[Any], problem: str
) -> None:
    lines = failure(TEXT_CODES, current)
    assert lines == [f"packaged list countries: {problem} (ADR-0055)"]
    assert "Brazil" not in lines[0]


RETRIEVED = datetime(2026, 11, 24, 8, 0, tzinfo=UTC)
"""When an ``api/`` wrapper's ``Answer`` was retrieved, which the comparison does not read."""


def test_an_answer_is_compared_as_the_list_it_holds() -> None:
    """https://github.com/xippios/sdk-core/issues/577: an ``api/`` wrapper answers an
    ``Answer`` (https://github.com/xippios/sdk-core/issues/479), which the comparison reads
    by its ``payload``: it passes and fails as the records or codes it holds do."""
    argentina = {"countryCode": "AR", "countryName": "Argentina", "regionCode": "R04"}
    models = [Country.model_validate(record) for record in RECORDS]
    assert_list_current(TEXT_CODES, Answer(RECORDS, RETRIEVED))
    assert_list_current(TEXT_CODES, Answer(models, RETRIEVED))
    assert_list_current(TEXT_CODES, Answer(["E4", "US", "BR"], RETRIEVED))
    for current in ([RECORDS[0], RECORDS[2], argentina], ["US", "E4", "AR"]):
        assert failure(TEXT_CODES, Answer(current, RETRIEVED)) == failure(TEXT_CODES, current)
    renamed = [RECORDS[0], {**RECORDS[1], "countryName": "Brasil"}, RECORDS[2]]
    assert failure(TEXT_CODES, Answer(renamed, RETRIEVED))[1:] == ["- changed: 'BR'"]


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        ({"data": RECORDS}, "a dict"),
        ("US", "a str"),
        (None, "a NoneType"),
        (Answer(RECORDS, RETRIEVED), "an Answer"),
    ],
    ids=["body", "text", "none", "answer"],
)
def test_an_answer_that_holds_no_list_fails_naming_its_payloads_type(
    payload: object, kind: str
) -> None:
    """https://github.com/xippios/sdk-core/issues/577: an ``Answer`` of the body that holds
    the records, of a text or of no list at all is refused as a list that holds neither
    records nor codes is, naming the payload's type and never a value, and says to hand the
    records."""
    answer: Any = Answer(payload, RETRIEVED)
    lines = failure(TEXT_CODES, answer)
    assert len(lines) == 1, lines
    assert lines[0].startswith(
        f"packaged list countries: the list upstream serves now is an Answer of {kind}: "
    ), lines
    assert "hand the records" in lines[0], lines
    assert lines[0].endswith(" (ADR-0055)"), lines
    for value in ("Brazil", "'US'", "data"):
        assert value not in lines[0]


BY_CODE = {record["countryCode"]: record for record in RECORDS}
"""The packaged records keyed by their code: a mapping, whose keys are the codes."""

NO_LISTS = pytest.mark.parametrize(
    ("given", "kind"),
    [
        ({"data": RECORDS}, "a dict"),
        (BY_CODE, "a dict"),
        (OrderedDict(BY_CODE), "an OrderedDict"),
        ("USBRE4", "a str"),
        (b"US", "a bytes"),
    ],
    ids=["body", "by-code", "ordered", "text", "bytes"],
)
"""What is no list of either side: a mapping, whose keys, and a text or bytes, whose
characters, would read as bare codes."""


@NO_LISTS
def test_a_mapping_or_a_text_as_the_list_fails_and_asks_for_the_records(
    given: object, kind: str
) -> None:
    """A mapping, a text or bytes handed as the list upstream serves now, the body that holds
    the records or records by their code say, is refused naming its type, never read as bare
    codes of its keys or characters, and the failure says to hand the records or the
    wrapper's ``Answer`` of them."""
    assert failure(TEXT_CODES, given) == [
        f"packaged list countries: the list upstream serves now is {kind}: hand its records, "
        "or the wrapper's Answer of them, not the body or the text that holds them (ADR-0055)"
    ]


@NO_LISTS
def test_a_mapping_or_a_text_as_the_packaged_side_fails_and_asks_for_the_records(
    given: object, kind: str
) -> None:
    """``packaged=`` is guarded as the current side is: a mapping of the packaged records by
    their code, beside a current list with a changed record, fails naming its type where it
    would pass, its keys read as the codes."""
    renamed = [RECORDS[0], {**RECORDS[1], "countryName": "Brasil"}, RECORDS[2]]
    assert failure(TEXT_CODES, renamed, packaged=given) == [
        f"packaged list countries: the packaged list is {kind}: hand its records, not the body "
        "or the text that holds them (ADR-0055)"
    ]


class Item:
    """A type of a source's own that is neither a record nor a code, its name capitalized."""


def test_a_type_is_named_with_its_article_whatever_its_case() -> None:
    """ "an Item" and "an Answer", never "a Item": the vowel is read in either case."""
    assert failure(TEXT_CODES, [Item()]) == [
        "packaged list countries: the list upstream serves now: item 0 is an Item, neither a "
        "record nor a code (ADR-0055)"
    ]
    nested: Any = Answer(Answer(RECORDS, RETRIEVED), RETRIEVED)
    assert failure(TEXT_CODES, nested)[0].startswith(
        "packaged list countries: the list upstream serves now is an Answer of an Answer: "
    )
    with pytest.raises(TypeError, match=r"^codes is an Item; "):
        assert_list_current(Item(), RECORDS)  # type: ignore[arg-type]


def test_a_packaged_side_given_is_read_as_the_current_one() -> None:
    assert failure(TEXT_CODES, RECORDS, packaged=[{"countryName": "Brazil"}]) == [
        "packaged list countries: the packaged list: record 0 has no field 'countryCode' (ADR-0055)"
    ]


def test_the_collected_test_is_marked_live() -> None:
    """Marked itself, so a module without ``pytestmark`` gates it too: offline it sends nothing."""
    marks = getattr(live.test_packaged_list_is_current, "pytestmark", [])
    assert "live" in [mark.name for mark in marks]
    assert live.__all__ == ["pytest_generate_tests", "test_packaged_list_is_current"]


# The collected test, in a source laid out as the template does, under --import-mode=importlib.

REGIONS: list[dict[str, Any]] = [{"regionCode": "R01"}, {"regionCode": "R04"}]

LIVE_MODULE = '''"""Live tests: the packaged lists against the recordings under tests/upstream/."""

import json
from pathlib import Path

import pytest

from xippios.core import PackagedList
from xippios.core.testing.live import *  # noqa: F403

pytestmark = [pytest.mark.live, pytest.mark.anyio]

UPSTREAM = Path(__file__).parent / "upstream"
COUNTRIES = PackagedList.load("xippios.example", "countries").codes("countryCode", "countryName")
REGIONS = PackagedList.load("xippios.example", "regions").codes("regionCode")


def fetch_countries():
    """The list upstream serves now: its recording, read as a wrapper would answer."""
    return json.loads((UPSTREAM / "countries.json").read_text(encoding="utf-8"))


async def fetch_regions():
    """An async fetch: the test runs it on core's loop."""
    return [row["regionCode"] for row in json.loads((UPSTREAM / "regions.json").read_text())]


LIVE_LISTS = {"countries": (COUNTRIES, fetch_countries), "regions": (REGIONS, fetch_regions)}
NO_LIVE_LIST = {"units": "Upstream serves no list of units; its specification gives them."}


def test_upstream_answers():
    assert True
'''


def packaged_file(param: str, records: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"param": param, "endpoint": f"get_{param}", "fetched": FETCHED, "records": records}
    )


LIVE_TREE: dict[str, str] = {
    "pyproject.toml": (
        '[tool.pytest.ini_options]\naddopts = "-p no:cacheprovider --import-mode=importlib"\n'
    ),
    "src/xippios/example/__init__.py": '__version__ = "0.1.0"\n',
    "src/xippios/example/reference/countries.json": packaged_file("countries", RECORDS),
    "src/xippios/example/reference/regions.json": packaged_file("regions", REGIONS),
    "tests/conftest.py": 'pytest_plugins = ["xippios.core.testing.plugin"]\n',
    "tests/test_live.py": LIVE_MODULE,
    "tests/upstream/countries.json": json.dumps(RECORDS),
    "tests/upstream/regions.json": json.dumps(REGIONS),
}


def run_live(
    pytester: pytest.Pytester, changes: dict[str, str | None], *options: str
) -> pytest.RunResult:
    """Write the source with ``changes`` (``None`` deletes a file) and run its tests."""
    for path, content in {**LIVE_TREE, **changes}.items():
        target = pytester.path / path
        if content is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    pytester.syspathinsert(pytester.path / "src")
    for name in [m for m in sys.modules if m.split(".")[:2] == ["xippios", "example"]]:
        del sys.modules[name]
    importlib.invalidate_caches()
    _read_text.cache_clear()  # the packaged files of an earlier run share their names
    try:
        return pytester.runpytest("tests", "-ra", *options)
    finally:
        _read_text.cache_clear()


def test_the_collected_test_compares_each_declared_list_under_the_gate(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_ENV, "1")
    result = run_live(pytester, {}, "-v")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(
        [
            "*test_live.py::test_packaged_list_is_current[[]countries[]] PASSED*",
            "*test_live.py::test_packaged_list_is_current[[]regions[]] PASSED*",
        ]
    )


def test_the_collected_test_fails_naming_codes_and_never_records(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_ENV, "1")
    upstream = [
        {**RECORDS[0], "countryName": "United States of America"},
        RECORDS[2],
        {"countryCode": "AR", "countryName": "Argentina", "regionCode": "R04"},
    ]
    changes: dict[str, str | None] = {
        "tests/upstream/countries.json": json.dumps(upstream),
        "tests/upstream/regions.json": json.dumps([REGIONS[0]]),
    }
    result = run_live(pytester, changes, "--tb=long", "--showlocals")
    result.assert_outcomes(passed=1, failed=2)
    result.stdout.fnmatch_lines(
        [
            "*packaged list countries (fetched 2026-10-23) differs from the list upstream serves "
            "now: 1 gone, 1 new, 1 changed of 3 packaged codes, 3 served; refresh it*",
            "- gone: 'BR'",
            "- new: 'AR'",
            "- changed: 'US'",
        ]
    )
    result.stdout.fnmatch_lines(["*packaged list regions (fetched 2026-10-23)*", "- gone: 'R04'"])
    shown = result.stdout.str()
    for value in ("United States", "Argentina", "Brazil", "European Union"):
        assert value not in shown


ANSWERED = (
    LIVE_MODULE.replace(
        "from xippios.core import PackagedList\n",
        "from datetime import UTC, datetime\n\nfrom xippios.core import Answer, PackagedList\n",
    )
    .replace(
        '    return json.loads((UPSTREAM / "countries.json").read_text(encoding="utf-8"))\n',
        '    records = json.loads((UPSTREAM / "countries.json").read_text(encoding="utf-8"))\n'
        "    return Answer(records, datetime.now(UTC))\n",
    )
    .replace(
        '    return [row["regionCode"] for row in json.loads('
        '(UPSTREAM / "regions.json").read_text())]\n',
        '    rows = json.loads((UPSTREAM / "regions.json").read_text())\n'
        '    return Answer([row["regionCode"] for row in rows], datetime.now(UTC))\n',
    )
)
"""``tests/test_live.py`` whose two fetches answer as ``api/`` wrappers do, an ``Answer`` each,
one of records and one of bare codes, the second async."""


def test_the_collected_test_compares_a_fetch_that_answers_an_answer(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """https://github.com/xippios/sdk-core/issues/577: an entry's fetch may be an ``api/``
    wrapper, whose ``Answer`` the test compares by its ``payload``, passing and failing as
    for the records or codes it holds."""
    assert ANSWERED.count("Answer(") == 2, "both fetches answer an Answer"
    monkeypatch.setenv(LIVE_ENV, "1")
    result = run_live(pytester, {"tests/test_live.py": ANSWERED}, "-v")
    result.assert_outcomes(passed=3)
    upstream = [RECORDS[0], RECORDS[2], {**RECORDS[1], "countryCode": "AR"}]
    changes: dict[str, str | None] = {
        "tests/test_live.py": ANSWERED,
        "tests/upstream/countries.json": json.dumps(upstream),
        "tests/upstream/regions.json": json.dumps([REGIONS[0]]),
    }
    result = run_live(pytester, changes)
    result.assert_outcomes(passed=1, failed=2)
    result.stdout.fnmatch_lines(["*packaged list countries*1 gone, 1 new, 0 changed*"])
    result.stdout.fnmatch_lines(["*packaged list regions (fetched 2026-10-23)*", "- gone: 'R04'"])


def test_an_offline_run_fetches_nothing(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the gate closed every live test skips, and no fetch runs: none could read a list."""
    monkeypatch.delenv(LIVE_ENV, raising=False)
    gone: dict[str, str | None] = {
        "tests/upstream/countries.json": None,
        "tests/upstream/regions.json": None,
    }
    result = run_live(pytester, gone)
    result.assert_outcomes(skipped=3)


def test_an_entry_that_is_no_pair_fails_its_live_test_naming_it(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_ENV, "1")
    broken = LIVE_MODULE.replace(
        '"regions": (REGIONS, fetch_regions)', '"regions": (fetch_regions, REGIONS)'
    )
    result = run_live(pytester, {"tests/test_live.py": broken})
    result.assert_outcomes(passed=2, failed=1)
    result.stdout.fnmatch_lines(
        [
            "*regions: LIVE_LISTS holds no pair of its PackagedCodes and the function that "
            "fetches it now*"
        ]
    )


def test_the_test_reads_the_declaration_wherever_the_module_holds_it(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declaration may stand above the collecting line: pytest reads it at collection."""
    monkeypatch.setenv(LIVE_ENV, "1")
    line = "from xippios.core.testing.live import *  # noqa: F403\n"
    moved = LIVE_MODULE.replace(line, "") + "\n\n" + line
    result = run_live(pytester, {"tests/test_live.py": moved})
    result.assert_outcomes(passed=3)


def test_a_module_that_declares_no_list_collects_no_comparison(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(LIVE_ENV, "1")
    bare = (
        LIVE_MODULE.split("LIVE_LISTS = ")[0]
        + "\n\ndef test_upstream_answers():\n    assert True\n"
    )
    result = run_live(pytester, {"tests/test_live.py": bare}, "-v")
    result.assert_outcomes(passed=1, skipped=1)
    result.stdout.fnmatch_lines(["*test_packaged_list_is_current*SKIPPED*"])
