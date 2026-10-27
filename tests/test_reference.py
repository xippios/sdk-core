import importlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import Field

from xippios.core.errors import ValidationError
from xippios.core.models import UpstreamModel
from xippios.core.reference import (
    PackagedList,
    _read_text,
    closest,
    enum_member_name,
    id_name_pairs,
    load_csv,
    load_json,
    load_table,
    matches,
    render_int_enums,
    render_str_enums,
)

PKG = "refpkg_for_tests"
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
"""The family's ruff configuration, the one sdk-template gives every source."""


class Code(UpstreamModel):
    code: str
    name: str
    rank: int


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    root = tmp_path / PKG
    (root / "reference").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "reference" / "codes.csv").write_text(
        "code,name,rank\nUS,United States,1\nDE,Germany,2\n"
    )
    (root / "reference" / "codes.json").write_text(
        json.dumps([{"code": "US", "name": "United States", "rank": 1}])
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, PKG, raising=False)  # this test's directory, not the last
    importlib.invalidate_caches()
    _read_text.cache_clear()
    return PKG


def test_load_csv(package: str) -> None:
    rows = load_csv(package, "codes.csv")
    assert rows == [
        {"code": "US", "name": "United States", "rank": "1"},
        {"code": "DE", "name": "Germany", "rank": "2"},
    ]


def test_load_json(package: str) -> None:
    assert load_json(package, "codes.json")[0]["code"] == "US"


def test_load_table_csv_coerces_types(package: str) -> None:
    rows = load_table(package, "codes.csv", Code)
    assert rows[1] == Code(code="DE", name="Germany", rank=2)


def test_load_table_json(package: str) -> None:
    assert load_table(package, "codes.json", Code)[0].rank == 1


def test_callers_get_fresh_objects(package: str) -> None:
    first = load_csv(package, "codes.csv")
    first[0]["code"] = "mutated"
    assert load_csv(package, "codes.csv")[0]["code"] == "US"


def test_missing_file(package: str) -> None:
    with pytest.raises(FileNotFoundError, match=r"nope\.csv"):
        load_csv(package, "nope.csv")


class Commodity(UpstreamModel):
    commodity_code: str = Field(alias="commodityCode")
    commodity_name: str = Field(alias="commodityName")


COMMODITIES = {
    "param": "commodities",
    "endpoint": "PSDData_GetCommodities",
    "fetched": "2026-10-23",
    "records": [
        {"commodityCode": "0410000", "commodityName": "Wheat"},
        {"commodityCode": "0440000", "commodityName": "Corn"},
    ],
}
"""sdk-usda-psd's layout, ``fetched`` a bare date as every refresh script wrote it so far."""


def test_a_packaged_list_answers_with_the_meta_of_adr_0022(package: str, tmp_path: Path) -> None:
    (tmp_path / PKG / "reference" / "commodities.json").write_text(json.dumps(COMMODITIES))
    packaged = PackagedList.load(package, "commodities")
    assert PackagedList.load(package, "commodities.json") == packaged
    assert packaged.fetched == datetime(2026, 10, 23, tzinfo=UTC)  # the start of that day
    meta = packaged.meta("usda-psd", request={"search": None})
    assert (meta.endpoint, meta.retrieved_at) == ("PSDData_GetCommodities", packaged.fetched)
    assert (meta.vintage, meta.published_at, meta.total, meta.request) == (None, None, None, {})
    rows = packaged.parse(Commodity, source="usda-psd")
    assert [row.commodity_name for row in rows] == ["Wheat", "Corn"]


def test_meta_takes_an_upstream_release_but_never_the_fetch_date() -> None:
    packaged = PackagedList.model_validate({**COMMODITIES, "fetched": "2026-10-27T11:15:00+02:00"})
    assert packaged.fetched == datetime(2026, 10, 27, 9, 15, tzinfo=UTC)
    released = datetime(2026, 10, 6, 8, 0)
    meta = packaged.meta(
        "usda-gats", vintage="202608", published_at=released, published_at_naive=True
    )
    assert (meta.vintage, meta.published_at, meta.published_at_naive) == ("202608", released, True)
    assert meta.retrieved_at == packaged.fetched


def test_a_one_field_value_list_round_trips_through_write_and_load(
    package: str, tmp_path: Path
) -> None:
    values = PackagedList(
        param="state_alpha",
        endpoint="get_param_values",
        fetched=datetime(2026, 10, 27, 9, 15, tzinfo=UTC),
        records=[{"state_alpha": "AK"}, {"state_alpha": "C\u00f4te"}],
    )
    path = tmp_path / PKG / "reference" / "state_alpha.json"
    values.write(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith(
        '{\n  "param": "state_alpha",\n  "endpoint": "get_param_values",\n'
        '  "fetched": "2026-10-27T09:15:00Z",\n  "records": [\n    {\n'
    )
    assert '"C\u00f4te"' in text
    assert text.endswith("]\n}\n")
    loaded = PackagedList.load(package, "state_alpha")
    assert loaded == values
    assert [record["state_alpha"] for record in loaded.records] == ["AK", "C\u00f4te"]


def test_a_note_is_written_when_set_and_fetched_to_the_second(package: str, tmp_path: Path) -> None:
    # sdk-usda-nass: two lists derived from api_GET's unit_desc, each in a file of its own.
    derived = PackagedList(
        param="unit_desc",
        endpoint="api_GET",
        fetched=datetime(2026, 10, 27, 9, 15, 30, 654321, tzinfo=UTC),
        note="derived from statisticcat_desc=CONDITION, agg_level_desc=NATIONAL",
        records=[{"unit_desc": "PCT EXCELLENT"}, {"unit_desc": "PCT FAIR"}],
    )
    derived.write(tmp_path / PKG / "reference" / "condition_categories.json")
    loaded = PackagedList.load(package, "condition_categories")
    assert loaded == derived.model_copy(
        update={"fetched": datetime(2026, 10, 27, 9, 15, 30, tzinfo=UTC)}
    )
    text = (tmp_path / PKG / "reference" / "condition_categories.json").read_text("utf-8")
    assert '"fetched": "2026-10-27T09:15:30Z",\n  "note": "derived from statisticcat' in text


def test_a_packaged_list_refuses_a_naive_time_an_unknown_key_and_unparsable_records() -> None:
    with pytest.raises(ValueError, match="fetched must carry a zone"):
        PackagedList.model_validate({**COMMODITIES, "fetched": "2026-10-23T09:15:00"})
    with pytest.raises(ValueError, match=r"origin\n  Extra inputs are not permitted"):
        PackagedList.model_validate({**COMMODITIES, "origin": "https://example.test/c.json"})
    broken = PackagedList.model_validate({**COMMODITIES, "records": [{"commodityCode": "1"}]})
    with pytest.raises(ValidationError, match=r"^usda-psd PSDData_GetCommodities: 1 validation"):
        broken.parse(Commodity, source="usda-psd")


@pytest.mark.parametrize(
    ("search", "fields", "expected"),
    [(None, ("0410000", "Wheat"), True), ("WHEAT", ("0410000", "Wheat"), True),
     ("0410", ("0410000", "Wheat"), True), ("28", (128, "Dom. Leaf Consumption"), True),
     ("corn", ("0410000", "Wheat"), False), ("None", ("US", None), False),
     ("tesus", ("Unit", "ed States", "US"), False)],
)  # fmt: skip
def test_matches_each_field_ignoring_case(
    search: str | None, fields: tuple[object, ...], expected: bool
) -> None:
    assert matches(search, *fields) is expected


CODES = {"US": "United States", "UK": "United Kingdom", "BR": "Brazil", "0410000": "Wheat"}


@pytest.mark.parametrize(
    ("value", "n", "expected"),
    [("us", 3, [("US", "United States")]), ("wheat", 3, [("0410000", "Wheat")]),
     ("united", 3, [("US", "United States"), ("UK", "United Kingdom")]),
     ("united", 1, [("US", "United States")]), ("ZZ", 3, [])],
)  # fmt: skip
def test_closest_by_code_then_by_name(value: str, n: int, expected: list[tuple[str, str]]) -> None:
    assert closest(value, CODES, n=n) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("CORN", "CORN"), ("ANIMALS & PRODUCTS", "ANIMALS_AND_PRODUCTS"),
     ("REGION : MULTI-STATE", "REGION_MULTI_STATE"), ("5 YEAR AVG", "_5_YEAR_AVG"),
     ("pct planted", "PCT_PLANTED"), ("$ / BU", "BU")],
)  # fmt: skip
def test_enum_member_name(value: str, expected: str) -> None:
    assert enum_member_name(value) == expected


def test_enum_member_name_rejects_empty() -> None:
    with pytest.raises(ValueError, match="no identifier"):
        enum_member_name("---")


def ruff(path: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *command, "--no-cache", "--config", str(PYPROJECT),
         str(path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip


def written(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "enums.py"
    path.write_text(source, encoding="utf-8")
    return path


def assert_ruff_clean(tmp_path: Path, source: str) -> dict[str, Any]:
    """Ruff leaves the rendered module as it is and finds nothing; returns its namespace."""
    path = written(tmp_path, source)
    for command in (("format", "--check"), ("check",)):
        result = ruff(path, *command)
        assert result.returncode == 0, result.stdout + result.stderr
    namespace: dict[str, Any] = {}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def test_render_str_enums_is_valid_formatted_python(tmp_path: Path) -> None:
    source = render_str_enums(
        {"state_alpha": ["AK", "AL"], "sector_desc": ["ANIMALS & PRODUCTS", "CROPS"]},
        class_names={"sector_desc": "Sector"},
        fetched="2026-10-22",
        generator="tests",
    )
    namespace = assert_ruff_clean(tmp_path, source)
    state_alpha = namespace["StateAlpha"]
    sector = namespace["Sector"]
    assert [m.value for m in state_alpha] == ["AK", "AL"]
    assert sector.ANIMALS_AND_PRODUCTS.value == "ANIMALS & PRODUCTS"
    assert namespace["__all__"] == ["Sector", "StateAlpha"]
    assert source.index("class StateAlpha") < source.index("class Sector")  # upstream order
    assert "fetched 2026-10-22" in source
    assert "Generated by tests" in source


def test_render_str_enums_escapes_quotes_and_backslashes(tmp_path: Path) -> None:
    values = [
        'say "hi"', "C:\\data\\x", "it's", "both ' and \"", "tab\there", 'quote \\"', "slash \\",
    ]  # fmt: skip
    source = render_str_enums({"label": values}, generator="tests")
    namespace = assert_ruff_clean(tmp_path, source)
    assert [m.value for m in namespace["Label"]] == values
    assert """    SAY_HI = 'say "hi"'\n""" in source  # single quotes where they need no escape
    assert '    C_DATA_X = "C:\\\\data\\\\x"\n' in source
    assert '    IT_S = "it\'s"\n' in source
    assert '    BOTH_AND = "both \' and \\""\n' in source  # as many of each: double quotes
    assert '    TAB_HERE = "tab\\there"\n' in source
    assert "    QUOTE = 'quote \\\\\"'\n" in source
    assert '    SLASH = "slash \\\\"\n' in source


def test_render_str_enums_writes_ascii_only(tmp_path: Path) -> None:
    # A right single quotation mark, an en dash, a no-break space, accents, Chinese and a
    # mathematical letter outside the BMP.
    values = [
        "Côte d\u2019Ivoire", "1990\u20132000", "Total\xa0area", "Zürich, Genève",
        "Beijing 北京", "BOLD \U0001d400",
    ]  # fmt: skip
    source = render_str_enums({"label": values}, generator="tests")
    assert source.isascii()
    namespace = assert_ruff_clean(tmp_path, source)
    assert [m.value for m in namespace["Label"]] == values  # unchanged at runtime
    assert '    C_TE_D_IVOIRE = "C\\xf4te d\\u2019Ivoire"\n' in source
    assert '    _1990_2000 = "1990\\u20132000"\n' in source
    assert '    TOTAL_AREA = "Total\\xa0area"\n' in source
    assert '    Z_RICH_GEN_VE = "Z\\xfcrich, Gen\\xe8ve"\n' in source
    assert '    BEIJING = "Beijing \\u5317\\u4eac"\n' in source
    assert '    BOLD = "BOLD \\U0001d400"\n' in source


@pytest.mark.parametrize(
    "value",
    [
        # 150 characters. A label in another script keeps its member name short (only the
        # code is ASCII), so the value alone is too long for a line.
        ("02 Κρέας και βρώσιμα παραπροϊόντα σφαγίων, νωπά, διατηρημένα με απλή ψύξη ή "
         "κατεψυγμένα: κρέας και βρώσιμα παραπροϊόντα σφαγίων, \"νωπά\" ή κατεψυγμένα."),
        # 150 characters without a space or a letter outside ASCII, a quote and a backslash
        # in each part.
        "07-" + '\\"' * 49 + "-" * 49,
    ],
)  # fmt: skip
def test_render_str_enums_wraps_a_long_value(tmp_path: Path, value: str) -> None:
    assert len(value) == 150
    source = render_str_enums({"chapter": [value]}, generator="tests")
    namespace = assert_ruff_clean(tmp_path, source)
    assert next(iter(namespace["Chapter"])).value == value
    member = source[source.index(" = (\n") : source.index("\n    )\n")].splitlines()[1:]
    assert len(member) >= 2  # implicitly concatenated parts, one per line
    assert all(line.startswith("        ") for line in member)


def test_render_str_enums_parenthesizes_a_value_too_long_for_its_member_line(
    tmp_path: Path,
) -> None:
    value = "CORN, GRAIN, IRRIGATED - ACRES HARVESTED, NET OF ABANDONMENT"
    source = render_str_enums({"short_desc": [value]}, generator="tests")
    assert_ruff_clean(tmp_path, source)
    assert f'    {enum_member_name(value)} = (\n        "{value}"\n    )\n' in source


def test_render_str_enums_sorts_all_as_ruff_does(tmp_path: Path) -> None:
    keys = ["zeta", "code10", "HS", "code2", "alpha"]
    source = render_str_enums(
        {key: ["A"] for key in keys}, class_names={"HS": "HS"}, generator="tests"
    )
    namespace = assert_ruff_clean(tmp_path, source)  # RUF022 included
    expected = ["HS", "Alpha", "Code2", "Code10", "Zeta"]
    assert namespace["__all__"] == expected
    assert "__all__ = [\n" + "".join(f'    "{name}",\n' for name in expected) + "]\n" in source
    classes = [line.split("(")[0][6:] for line in source.splitlines() if line.startswith("class ")]
    assert classes == ["Zeta", "Code10", "HS", "Code2", "Alpha"]  # upstream order


@pytest.mark.parametrize(
    "expected",
    [["Code05", "Code1"], ["Code001", "Code1"], ["B0", "B00"], ["Code1", "Code2", "Code10"]],
)
def test_render_str_enums_sorts_digit_runs_as_ruff_does(
    tmp_path: Path, expected: list[str]
) -> None:
    keys = [name.lower() for name in reversed(expected)]
    source = render_str_enums(
        {key: ["A"] for key in keys},
        class_names={name.lower(): name for name in expected},
        generator="tests",
    )
    assert assert_ruff_clean(tmp_path, source)["__all__"] == expected  # RUF022 agrees


@pytest.mark.parametrize("render", [render_str_enums, render_int_enums])
def test_a_long_key_and_fetch_date_wrap_the_class_docstring(
    tmp_path: Path, render: Callable[..., str]
) -> None:
    key = "reporter_partner_flow_customs_transport_codes"  # 45 characters
    fetched = "2026-10-24, reconciled with the snapshot of the spec of 2026-10-23"
    values: list[Any] = ["A"] if render is render_str_enums else [(1, "A")]
    source = render({key: values}, fetched=fetched, generator="tests")
    assert_ruff_clean(tmp_path, source)  # no line over 100 columns, D rules included
    assert f'    """Values of ``{key}``.\n\n    Fetched {fetched}.\n    """\n' in source
    short = render({key: values}, fetched="2026-10-24", generator="tests")
    assert f'    """Values of ``{key}`` (fetched 2026-10-24)."""\n' in short


@pytest.mark.parametrize("render", [render_str_enums, render_int_enums])
def test_a_key_too_long_for_its_class_docstring_is_refused(render: Callable[..., str]) -> None:
    values: list[Any] = ["A"] if render is render_str_enums else [(1, "A")]
    assert render({"k" * 75: values}).count("k" * 75) == 1
    with pytest.raises(ValueError, match=r"^key 'k{76}' is 76 characters long; at most 75 fit"):
        render({"k" * 76: values})


BAD_TEXT = ["2026\u201310\u201324", "scripts\u2019s refresh", "C:\\data", 'say """hi"""', "a\nb"]
"""An en dash, a typographic apostrophe, a backslash, three double quotes, a newline."""


@pytest.mark.parametrize("render", [render_str_enums, render_int_enums])
@pytest.mark.parametrize("text", BAD_TEXT)
@pytest.mark.parametrize("argument", ["generator", "fetched"])
def test_caller_text_that_would_not_stay_ascii_is_refused(
    render: Callable[..., str], text: str, argument: str
) -> None:
    values: list[Any] = ["A"] if render is render_str_enums else [(1, "A")]
    message = rf"^{argument} must be printable ASCII without a backslash or three double quotes$"
    with pytest.raises(ValueError, match=message):
        render({"x": values}, **{argument: text})


@pytest.mark.parametrize("render", [render_str_enums, render_int_enums])
@pytest.mark.parametrize("text", BAD_TEXT)
def test_a_key_that_would_not_stay_ascii_is_refused(render: Callable[..., str], text: str) -> None:
    values: list[Any] = ["A"] if render is render_str_enums else [(1, "A")]
    with pytest.raises(
        ValueError, match=r"^the key at position 1 of lists must be printable ASCII without"
    ):
        render({"ok": values, text: values}, class_names={text: "Fine"})


@pytest.mark.parametrize("render", [render_str_enums, render_int_enums])
@pytest.mark.parametrize(
    ("class_name", "where"),
    [
        ("Caf\u00e9", "class_names for the key"),
        ("Two Words", "class_names for the key"),
        ('X"""', "class_names for the key"),
        ("None", "class_names for the key"),
        ("C" * 85, "class_names for the key"),
        (None, "the class name derived from the key"),  # the key "1st" gives "1st"
    ],
)
def test_a_class_name_that_is_no_ascii_identifier_is_refused(
    render: Callable[..., str], class_name: str | None, where: str
) -> None:
    values: list[Any] = ["A"] if render is render_str_enums else [(1, "A")]
    class_names = {} if class_name is None else {"1st": class_name}
    message = (
        rf"^{where} at position 1 of lists must be an ASCII identifier, not a keyword, of at "
        r"most 84 characters; set it in class_names$"
    )
    with pytest.raises(ValueError, match=message):
        render({"ok": values, "1st": values}, class_names=class_names)
    assert render({"x": values}, class_names={"x": "C" * 84}).count("C" * 84) == 2


def test_the_whole_module_is_ascii(tmp_path: Path) -> None:
    source = render_str_enums(
        {"x": ["Caf\u00e9"]}, fetched="2026-10-24", generator="scripts/refresh_reference.py"
    )
    assert source.isascii()
    assert_ruff_clean(tmp_path, source)


LONG_VALUE = (
    "CORN, GRAIN, IRRIGATED, ENTIRE CROP - ACRES HARVESTED, MEASURED IN ACRES / PLANTED, "
    "NET OF ABANDONMENT, EXCL SILAGE AND SEED, ALL PRACTICES, ALL TYPES"
)
"""150 characters of ASCII; its derived member name is far longer than 92."""


def test_render_str_enums_refuses_a_member_name_too_long_for_any_line() -> None:
    assert len(LONG_VALUE) == 150
    width = len(enum_member_name(LONG_VALUE))
    assert width > 92
    message = (
        rf"^short_desc: the member name for '{re.escape(LONG_VALUE)}' at position 1 is "
        rf"{width} characters long; at most 92 fit a line of 100 columns; name it by hand in "
        r"member_names=\{'short_desc': \{\.\.\.\}\}$"
    )
    with pytest.raises(ValueError, match=message):
        render_str_enums({"short_desc": ["CORN", LONG_VALUE]})


def test_render_str_enums_takes_a_member_name_set_by_hand(tmp_path: Path) -> None:
    source = render_str_enums(
        {"short_desc": ["CORN", LONG_VALUE]},
        member_names={"short_desc": {LONG_VALUE: "CORN_GRAIN_IRRIGATED_ALL"}},
        generator="tests",
    )
    namespace = assert_ruff_clean(tmp_path, source)
    short_desc = namespace["ShortDesc"]
    assert short_desc.CORN_GRAIN_IRRIGATED_ALL.value == LONG_VALUE
    assert [m.name for m in short_desc] == ["CORN", "CORN_GRAIN_IRRIGATED_ALL"]


@pytest.mark.parametrize(
    "value",
    ["", "北京", "Κρέας", "---"],  # empty, CJK, Greek, punctuation: nothing to derive from
)
def test_render_str_enums_takes_a_member_name_for_a_value_with_no_derivable_name(
    tmp_path: Path, value: str
) -> None:
    message = (
        rf"^note: no member name can be derived from {re.escape(repr(value))} at position 1; "
        r"name it by hand in member_names=\{'note': \{\.\.\.\}\}$"
    )
    with pytest.raises(ValueError, match=message):
        render_str_enums({"note": ["A", value]})
    source = render_str_enums(
        {"note": ["A", value]}, member_names={"note": {value: "OTHER"}}, generator="tests"
    )
    assert assert_ruff_clean(tmp_path, source)["Note"].OTHER.value == value


def test_a_member_name_an_enum_refuses_is_named_with_its_value_and_position() -> None:
    message = r"^x: 'mro' for 'WHEAT' at position 1 is not a member name an enum accepts$"
    with pytest.raises(ValueError, match=message):
        render_str_enums({"x": ["CORN", "WHEAT"]}, member_names={"x": {"WHEAT": "mro"}})


@pytest.mark.parametrize("member", ["_", "_CORN", "CORN_", "name", "value"])
def test_render_str_enums_takes_a_member_name_an_enum_accepts(tmp_path: Path, member: str) -> None:
    source = render_str_enums({"x": ["CORN"]}, member_names={"x": {"CORN": member}})
    assert getattr(assert_ruff_clean(tmp_path, source)["X"], member).value == "CORN"


def test_render_str_enums_takes_a_member_name_that_resolves_a_collision(tmp_path: Path) -> None:
    source = render_str_enums(
        {"x": ["A B", "A-B"]}, member_names={"x": {"A-B": "A_HYPHEN_B"}}, generator="tests"
    )
    namespace = assert_ruff_clean(tmp_path, source)
    assert [(m.name, m.value) for m in namespace["X"]] == [("A_B", "A B"), ("A_HYPHEN_B", "A-B")]


@pytest.mark.parametrize(
    ("member_names", "message"),
    [
        ({"x": {"CORN": "WHEAT"}}, r"^x: member names collide: 'WHEAT' at positions 0, 1$"),
        ({"x": {"CORN": "corn-grain"}}, r"^x: 'corn-grain' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "class"}}, r"^x: 'class' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "_CORN_"}}, r"^x: '_CORN_' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "__CORN"}}, r"^x: '__CORN' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "_X__CORN"}}, r"^x: '_X__CORN' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "CORN__ALL"}}, r"^x: 'CORN__ALL' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "mro"}}, r"^x: 'mro' for 'CORN' at position 0 is not a"),
        ({"x": {"CORN": "MA\u00cfS"}}, r"^x: 'MA\u00cfS' for 'CORN' at position 0 is not a"),
        ({"x": {"RICE": "RICE"}}, r"^x: member_names names what the list does not hold"),
        ({"y": {"CORN": "C"}}, r"^member_names names lists that are not rendered: \['y'\]$"),
        ({"x": {"CORN": "C" * 93}}, r"^x: the member name for 'CORN' at position 0 is 93 "),
    ],
)  # fmt: skip
def test_render_str_enums_refuses_a_member_name_set_by_hand_it_cannot_use(
    member_names: dict[str, dict[str, str]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        render_str_enums({"x": ["CORN", "WHEAT"]}, member_names=member_names)


def test_render_str_enums_rejects_colliding_members() -> None:
    with pytest.raises(
        ValueError,
        match=r"^x: member names collide: 'A_B' at positions 0, 3; 'C_D' at positions 2, 4$",
    ):
        render_str_enums({"x": ["A B", "OK", "C D", "A-B", "C-D", "FINE"]})  # only those two


def test_render_str_enums_with_no_lists_imports_nothing(tmp_path: Path) -> None:
    source = render_str_enums({}, generator="tests")
    assert "import" not in source
    assert "__all__ = []" in source
    assert_ruff_clean(tmp_path, source)


ATTRIBUTES: list[dict[str, Any]] = [
    {"attributeId": 126, "attributeName": "Total Disappearance"},
    {"attributeId": "4", "attributeName": "Area Harvested", "unused": None},
    {"attributeId": 173, "attributeName": "Total Disappearance"},
    {"attributeId": 20, "attributeName": "Beginning Stocks"},
]
"""PSD's ``commodityAttributes`` in shape: a repeated name, an id sent as digits."""


def test_id_name_pairs_keeps_upstream_order() -> None:
    pairs = id_name_pairs(ATTRIBUTES, id_field="attributeId", name_field="attributeName")
    assert pairs == [
        (126, "Total Disappearance"),
        (4, "Area Harvested"),
        (173, "Total Disappearance"),
        (20, "Beginning Stocks"),
    ]


@pytest.mark.parametrize("field", ["attributeId", "attributeName"])
def test_id_name_pairs_names_the_missing_field_never_the_record(field: str) -> None:
    record = {"attributeId": 1, "attributeName": "Secret-ish name", "note": "do not print"}
    del record[field]
    with pytest.raises(ValueError, match=f"record 1 has no field '{field}'") as error:
        id_name_pairs([ATTRIBUTES[0], record], id_field="attributeId", name_field="attributeName")
    assert "Secret" not in str(error.value)
    assert "do not print" not in str(error.value)


@pytest.mark.parametrize("ident", ["2.5", " 28", "-3", "²", "", 2.0, True, None])
def test_id_name_pairs_refuses_an_id_that_is_not_an_integer(ident: object) -> None:
    with pytest.raises(ValueError, match="'attributeId' is not an integer id") as error:
        id_name_pairs(
            [{"attributeId": ident, "attributeName": "Area"}],
            id_field="attributeId",
            name_field="attributeName",
        )
    assert "Area" not in str(error.value)


@pytest.mark.parametrize("ident", ["007", "00", "0123"])
def test_id_name_pairs_refuses_leading_zeros(ident: str) -> None:
    with pytest.raises(
        ValueError, match=r"^record 1: field 'attributeId' has leading zeros an integer id"
    ) as error:
        id_name_pairs(
            [
                {"attributeId": "0", "attributeName": "Zero"},
                {"attributeId": ident, "attributeName": "Bond"},
            ],
            id_field="attributeId",
            name_field="attributeName",
        )
    assert ident not in str(error.value)
    assert "Bond" not in str(error.value)


def test_id_name_pairs_refuses_a_name_that_is_not_a_string() -> None:
    with pytest.raises(ValueError, match="'attributeName' is not a string"):
        id_name_pairs(
            [{"attributeId": 1, "attributeName": 7}],
            id_field="attributeId",
            name_field="attributeName",
        )


def test_render_int_enums_suffixes_repeated_names_and_keeps_order(tmp_path: Path) -> None:
    pairs = id_name_pairs(ATTRIBUTES, id_field="attributeId", name_field="attributeName")
    source = render_int_enums(
        {"unitId": [(8, "(1000 MT)"), (21, "(MT)")], "attributeId": pairs},
        class_names={"attributeId": "AttributeId", "unitId": "UnitId"},
        fetched="2026-10-23",
        generator="tests",
    )
    assert source.isascii()
    namespace = assert_ruff_clean(tmp_path, source)
    attribute_id = namespace["AttributeId"]
    assert [(m.name, m.value) for m in attribute_id] == [
        ("TOTAL_DISAPPEARANCE_126", 126),
        ("AREA_HARVESTED", 4),
        ("TOTAL_DISAPPEARANCE_173", 173),
        ("BEGINNING_STOCKS", 20),
    ]
    assert attribute_id.AREA_HARVESTED == 4  # equal to the id in upstream's data
    assert attribute_id(173) is attribute_id.TOTAL_DISAPPEARANCE_173
    assert [m.name for m in namespace["UnitId"]] == ["_1000_MT", "MT"]
    assert namespace["__all__"] == ["AttributeId", "UnitId"]
    assert '    """Values of ``attributeId`` (fetched 2026-10-23)."""' in source
    assert "Generated by tests" in source
    assert "``IntEnum``, not ``StrEnum``" in source


def test_render_int_enums_parenthesizes_a_member_too_long_for_its_line(tmp_path: Path) -> None:
    name = (
        "Production of the reference marketing year, all varieties, in thousand metric tons, "
        "total crop"
    )
    member = enum_member_name(name)
    assert len(f"    {member} = 1000") > 100
    source = render_int_enums({"attributeId": [(1000, name)]}, generator="tests")
    assert_ruff_clean(tmp_path, source)
    assert f"    {member} = (\n        1000\n    )\n" in source


@pytest.mark.parametrize(
    "pairs",
    [[(1, "A"), (2, "A"), (3, "A 1")], [(-1, "Loss"), (2, "Loss")]],
)
def test_render_int_enums_rejects_names_it_cannot_make_unique(
    pairs: list[tuple[int, str]],
) -> None:
    with pytest.raises(
        ValueError,
        match=r"^attributeId: (member names collide: 'A_1' at positions 0, 2$|"
        r"'LOSS_-1' for 'Loss' \(id -1\) at position 0 is not a member name)",
    ):
        render_int_enums({"attributeId": pairs})


@pytest.mark.parametrize(
    ("pairs", "repeated"),
    [
        ([(5, "X"), (5, "Y")], r"\[5\]"),  # would silently become an alias
        ([(5, "X"), (5, "X")], r"\[5\]"),
        ([(7, "Z"), (5, "X"), (7, "W"), (5, "Y")], r"\[5, 7\]"),
    ],
)
def test_render_int_enums_refuses_a_repeated_id(
    pairs: list[tuple[int, str]], repeated: str
) -> None:
    with pytest.raises(ValueError, match=rf"^unitId: ids listed more than once: {repeated}$"):
        render_int_enums({"unitId": pairs})


def test_render_int_enums_refuses_a_member_name_too_long_for_any_line(tmp_path: Path) -> None:
    pairs = [(1, "Area"), (2, LONG_VALUE)]
    with pytest.raises(
        ValueError, match=r"^attributeId: the member name for '.+' \(id 2\) at position 1 is \d+ "
    ):
        render_int_enums({"attributeId": pairs})
    source = render_int_enums(
        {"attributeId": pairs}, member_names={"attributeId": {2: "CORN_ALL"}}, generator="tests"
    )
    assert assert_ruff_clean(tmp_path, source)["Attributeid"].CORN_ALL == 2


def test_render_int_enums_takes_a_member_name_for_a_name_with_none_derivable(
    tmp_path: Path,
) -> None:
    pairs = [(1, "Area"), (2, "北京"), (3, "")]
    message = (
        r"^unitId: no member name can be derived from '北京' \(id 2\) at position 1; "
        r"name it by hand in member_names=\{'unitId': \{\.\.\.\}\}$"
    )
    with pytest.raises(ValueError, match=message):
        render_int_enums({"unitId": pairs})
    source = render_int_enums(
        {"unitId": pairs}, member_names={"unitId": {2: "BEIJING", 3: "BLANK"}}, generator="tests"
    )
    unit_id = assert_ruff_clean(tmp_path, source)["Unitid"]
    assert [(m.name, m.value) for m in unit_id] == [("AREA", 1), ("BEIJING", 2), ("BLANK", 3)]


def test_render_int_enums_takes_a_member_name_and_leaves_the_others(tmp_path: Path) -> None:
    pairs = id_name_pairs(ATTRIBUTES, id_field="attributeId", name_field="attributeName")
    source = render_int_enums(
        {"attributeId": pairs},
        class_names={"attributeId": "AttributeId"},
        member_names={"attributeId": {173: "TOTAL_USE"}},
        generator="tests",
    )
    namespace = assert_ruff_clean(tmp_path, source)
    assert [m.name for m in namespace["AttributeId"]] == [
        "TOTAL_DISAPPEARANCE_126",  # keeps its suffix: the rule counts upstream's names
        "AREA_HARVESTED",
        "TOTAL_USE",
        "BEGINNING_STOCKS",
    ]


@pytest.mark.parametrize(
    ("member_names", "message"),
    [
        (
            {"attributeId": {173: "AREA_HARVESTED"}},
            r"member names collide: 'AREA_HARVESTED' at positions 1, 2$",
        ),
        (
            {"attributeId": {173: "1ST"}},
            r"'1ST' for 'Total Disappearance' \(id 173\) at position 2 is not a member name",
        ),
        ({"attributeId": {999: "X"}}, r"member_names names what the list does not hold: \[999\]"),
        ({"unitId": {1: "X"}}, r"member_names names lists that are not rendered: \['unitId'\]"),
    ],
)  # fmt: skip
def test_render_int_enums_refuses_a_member_name_set_by_hand_it_cannot_use(
    member_names: dict[str, dict[int, str]], message: str
) -> None:
    pairs = id_name_pairs(ATTRIBUTES, id_field="attributeId", name_field="attributeName")
    with pytest.raises(ValueError, match=message):
        render_int_enums({"attributeId": pairs}, member_names=member_names)


def test_render_int_enums_with_no_lists_imports_nothing(tmp_path: Path) -> None:
    source = render_int_enums({}, generator="tests")
    assert "import" not in source
    assert "__all__ = []" in source
    assert_ruff_clean(tmp_path, source)
