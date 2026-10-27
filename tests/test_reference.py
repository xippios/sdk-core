import importlib
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
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
    render_enums,
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


def test_a_row_that_does_not_fit_is_refused_from_none(package: str, tmp_path: Path) -> None:
    (tmp_path / PKG / "reference" / "bad.csv").write_text("code,name,rank\nUS,MARKER,first\n")
    with pytest.raises(ValidationError) as info:
        load_table(package, "bad.csv", Code)
    assert str(info.value) == (
        f"{PKG} reference/bad.csv: 1 validation error(s); first at 0.rank (int_parsing): Input "
        "should be a valid integer, unable to parse string as an integer"
    )
    assert info.value.raw == [{"code": "US", "name": "MARKER", "rank": "first"}]
    assert info.value.__cause__ is None  # row 42: no chained pydantic text quoting the row


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


def test_a_packaged_list_refuses_a_time_without_a_zone_and_records_that_do_not_parse() -> None:
    with pytest.raises(ValueError, match="fetched must carry a zone"):
        PackagedList.model_validate({**COMMODITIES, "fetched": "2026-10-23T09:15:00"})
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


def run(source: str) -> dict[str, Any]:
    """The rendered module's namespace: plain output is valid Python as rendered."""
    namespace: dict[str, Any] = {}
    exec(compile(source, "enums.py", "exec"), namespace)
    return namespace


def test_a_value_list_renders_a_str_enum() -> None:
    source = render_enums(
        {"state_alpha": ["AK", "AL"], "sector_desc": ["ANIMALS & PRODUCTS", "CROPS"]},
        fetched="2026-10-22",
        class_names={"sector_desc": "Sector"},
        generator="tests",
    )
    namespace = run(source)
    assert [m.value for m in namespace["StateAlpha"]] == ["AK", "AL"]
    assert namespace["Sector"].ANIMALS_AND_PRODUCTS == "ANIMALS & PRODUCTS"
    assert namespace["__all__"] == ["StateAlpha", "Sector"]  # the order of lists; ruff sorts
    assert "from enum import StrEnum\n" in source
    assert '    """Values of ``state_alpha`` (fetched 2026-10-22)."""\n' in source
    assert source.startswith('"""Enums of the packaged lists, generated by tests; do not edit')


ATTRIBUTES: list[dict[str, Any]] = [
    {"attributeId": 126, "attributeName": "Total Disappearance"},
    {"attributeId": "4", "attributeName": "Area Harvested", "unused": None},
    {"attributeId": 173, "attributeName": "Total Disappearance"},
    {"attributeId": 20, "attributeName": "Beginning Stocks"},
]
"""PSD's ``commodityAttributes`` in shape: a repeated name, an id sent as digits."""


def test_id_name_pairs_render_an_int_enum_equal_to_upstreams_ids() -> None:
    pairs = id_name_pairs(ATTRIBUTES, id_field="attributeId", name_field="attributeName")
    source = render_enums(
        {"attributeId": pairs}, fetched="2026-10-23", class_names={"attributeId": "AttributeId"}
    )
    attribute_id = run(source)["AttributeId"]
    assert [(m.name, m.value) for m in attribute_id] == [
        ("TOTAL_DISAPPEARANCE_126", 126),  # a name several ids share carries the id
        ("AREA_HARVESTED", 4),
        ("TOTAL_DISAPPEARANCE_173", 173),
        ("BEGINNING_STOCKS", 20),
    ]
    assert attribute_id.AREA_HARVESTED == 4  # equal to the id in upstream's data (ADR-0008)
    assert "from enum import IntEnum\n" in source


LONG_VALUE = (
    "CORN, GRAIN, IRRIGATED, ENTIRE CROP - ACRES HARVESTED, MEASURED IN ACRES / PLANTED, "
    "NET OF ABANDONMENT, EXCL SILAGE AND SEED, ALL PRACTICES, ALL TYPES"
)
"""150 characters: no line of 100 columns holds its member."""


def test_a_mixed_module_is_clean_after_the_refresh_scripts_ruff(tmp_path: Path) -> None:
    # ADR-0008, amended 2026-10-27: plain output, then ruff format && ruff check --fix.
    values = [
        LONG_VALUE,
        "CORN, GRAIN, IRRIGATED - ACRES HARVESTED, NET OF ABANDONMENT",  # fits once wrapped
        'say "hi"', "it's", "C:\\data", "C\u00f4te d\u2019Ivoire", "Beijing \u5317\u4eac",
    ]  # fmt: skip
    lists: dict[str, Sequence[str] | Sequence[tuple[int, str]]] = {
        "zeta": values,
        "unitId": [(8, "(1000 MT)"), (21, "(MT)")],
        "alpha": ["A"],
    }
    source = render_enums(
        lists,
        fetched={"zeta": "2026-10-27", "unitId": "2026-10-23", "alpha": "2026-10-01"},
        class_names={"unitId": "UnitId"},
        generator="scripts/refresh_reference.py",
    )
    assert source.isascii()
    assert f"{enum_member_name(LONG_VALUE)} = {LONG_VALUE!a}  # noqa: E501\n" in source
    assert '    """Values of ``unitId`` (fetched 2026-10-23)."""\n' in source
    path = tmp_path / "enums.py"
    path.write_text(source, encoding="ascii")
    for command in (("format",), ("check", "--fix"), ("format", "--check"), ("check",)):
        result = ruff(path, *command)
        assert result.returncode == 0, result.stdout + result.stderr
    formatted = path.read_text(encoding="ascii")
    namespace = run(formatted)
    assert [m.value for m in namespace["Zeta"]] == values  # the same values at runtime
    assert [m.value for m in namespace["UnitId"]] == [8, 21]
    assert namespace["__all__"] == ["Alpha", "UnitId", "Zeta"]  # sorted by ruff (RUF022)
    assert "from enum import IntEnum, StrEnum\n" in formatted
    assert formatted.count("# noqa: E501") == 1  # the line ruff wrapped lost it (RUF100)


def test_no_lists_render_a_module_that_imports_nothing() -> None:
    source = render_enums({}, fetched="2026-10-27")
    assert "import" not in source
    assert run(source)["__all__"] == []


@pytest.mark.parametrize("values", [[], "AK", ["AK", (1, "Area")], [(1, "Area", "x")]])
def test_a_list_that_is_empty_or_of_no_one_kind_is_refused(values: Any) -> None:
    with pytest.raises(ValueError, match=r"^state: (a list of values|the list mixes kinds)"):
        render_enums({"state": values}, fetched="2026-10-27")


BAD_TEXT = ["2026\u201310\u201324", "C:\\data", 'say """hi"""', "a\nb", ""]
"""An en dash, a backslash, three double quotes, a newline, nothing."""


@pytest.mark.parametrize("text", BAD_TEXT)
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (lambda t: {"lists": {"ok": ["A"], t: ["A"]}, "class_names": {t: "Fine"}},
         "the key at position 1 of lists must be"),
        (lambda t: {"fetched": t}, "fetched must be"),
        (lambda t: {"fetched": {"x": t}}, "fetched for the key at position 0 of lists must be"),
        (lambda t: {"generator": t}, "generator must be"),
    ],
)  # fmt: skip
def test_text_that_would_not_stay_printable_ascii_is_refused(
    text: str, arguments: Callable[[str], dict[str, Any]], message: str
) -> None:
    given = {"lists": {"x": ["A"]}, "fetched": "2026-10-27"} | arguments(text)
    with pytest.raises(ValueError, match=f"^{message} non-empty printable ASCII without"):
        render_enums(given.pop("lists"), **given)


@pytest.mark.parametrize(
    ("class_names", "message"),
    [
        ({"1st": "Caf\u00e9"}, "class_names for the key at position 1 of lists must be an ASCII"),
        ({"1st": "None"}, "class_names for the key at position 1 of lists must be an ASCII"),
        ({"1st": "C" * 85}, "class_names for the key at position 1 of lists must be an ASCII"),
        ({}, "the class name derived from the key at position 1 of lists must be"),  # "1st"
        ({"1st": "Ok"}, r"class names collide: 'Ok' at positions 0, 1; set them in class_names"),
        ({"2nd": "X"}, r"class_names names lists that are not rendered: \['2nd'\]"),
    ],
)  # fmt: skip
def test_a_class_name_that_is_no_ascii_identifier_or_collides_is_refused(
    class_names: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}"):
        render_enums({"ok": ["A"], "1st": ["A"]}, fetched="2026-10-27", class_names=class_names)
    assert "C" * 84 in render_enums({"x": ["A"]}, fetched="2026-10-27", class_names={"x": "C" * 84})


@pytest.mark.parametrize(
    ("fetched", "message"),
    [
        ({"x": "2026-10-27"}, r"^fetched has no date for the key at position 1 of lists$"),
        ({"x": "d", "y": "d", "z": "d"}, r"^fetched names lists that are not rendered: \['z'\]$"),
    ],
)
def test_a_date_per_list_names_every_list_and_no_other(
    fetched: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        render_enums({"x": ["A"], "y": ["B"]}, fetched=fetched)


def test_an_id_listed_twice_is_refused() -> None:
    with pytest.raises(ValueError, match=r"^unitId: ids listed more than once: \[5, 7\]$"):
        render_enums({"unitId": [(7, "Z"), (5, "X"), (7, "W"), (5, "Y")]}, fetched="d")


@pytest.mark.parametrize(
    ("lists", "message", "member_names"),
    [
        ({"note": ["A", "\u5317\u4eac"]},
         r"^note: no member name can be derived from '\u5317\u4eac' at position 1; name it by "
         r"hand in member_names=\{'note': \{\.\.\.\}\}$", {"note": {"\u5317\u4eac": "BEIJING"}}),
        ({"unitId": [(1, "Area"), (2, "---")]},
         r"^unitId: no member name can be derived from '---' \(id 2\) at position 1;",
         {"unitId": {2: "DASHES"}}),
        ({"note": ["A B", "OK", "A-B"]},
         r"^note: member names collide: 'A_B' at positions 0, 2$", {"note": {"A-B": "A_HYPHEN_B"}}),
        ({"unitId": [(1, "A"), (2, "A"), (3, "A 1")]},
         r"^unitId: member names collide: 'A_1' at positions 0, 2$", {"unitId": {3: "A_ONE"}}),
    ],
)  # fmt: skip
def test_a_member_name_that_derives_to_nothing_or_collides_is_named_by_hand(
    lists: dict[str, Any], message: str, member_names: dict[str, dict[Any, str]]
) -> None:
    with pytest.raises(ValueError, match=message):
        render_enums(lists, fetched="2026-10-27")
    namespace = run(render_enums(lists, fetched="2026-10-27", member_names=member_names))
    enum = namespace[namespace["__all__"][0]]
    named = next(iter(member_names.values()))
    for item, member in named.items():
        assert getattr(enum, member).value == item
    assert len(enum) == len(next(iter(lists.values())))  # the others keep their names


@pytest.mark.parametrize(
    ("member_names", "message"),
    [
        ({"x": {"CORN": "mro"}}, r"^x: 'mro' for 'CORN' at position 0 is not a member name an "),
        ({"x": {"CORN": "_CORN_"}}, r"^x: '_CORN_' for 'CORN' at position 0 is not a member "),
        ({"x": {"CORN": "CORN__ALL"}}, r"^x: 'CORN__ALL' for 'CORN' at position 0 is not a "),
        ({"x": {"CORN": "class"}}, r"^x: 'class' for 'CORN' at position 0 is not a member name"),
        ({"x": {"RICE": "RICE"}}, r"^x: member_names names what the list does not hold"),
        ({"y": {"CORN": "C"}}, r"^member_names names lists that are not rendered: \['y'\]$"),
    ],
)  # fmt: skip
def test_a_member_name_set_by_hand_that_an_enum_cannot_take_is_refused(
    member_names: dict[str, dict[str, str]], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        render_enums({"x": ["CORN", "WHEAT"]}, fetched="2026-10-27", member_names=member_names)


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
