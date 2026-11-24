import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import Field

from xippios.core.errors import ValidationError
from xippios.core.models import UpstreamModel
from xippios.core.reference import (
    PackagedList,
    _read_text,
    closest,
    load_json,
    matches,
    nearest,
)

PKG = "refpkg_for_tests"


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    root = tmp_path / PKG
    (root / "reference").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "reference" / "codes.json").write_text(
        json.dumps([{"code": "US", "name": "United States", "rank": 1}])
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, PKG, raising=False)  # this test's directory, not the last
    importlib.invalidate_caches()
    _read_text.cache_clear()
    return PKG


def test_load_json(package: str) -> None:
    assert load_json(package, "codes.json")[0]["code"] == "US"


def test_callers_get_fresh_objects(package: str) -> None:
    first = load_json(package, "codes.json")
    first[0]["code"] = "mutated"
    assert load_json(package, "codes.json")[0]["code"] == "US"


def test_missing_file(package: str) -> None:
    with pytest.raises(FileNotFoundError, match=r"nope\.json"):
        load_json(package, "nope.json")


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


def test_a_file_that_is_no_packaged_list_raises_the_taxonomys_error(
    package: str, tmp_path: Path
) -> None:
    (tmp_path / PKG / "reference" / "old.json").write_text(json.dumps({"param": "x"}))
    with pytest.raises(ValidationError) as info:
        PackagedList.load(package, "old")
    assert str(info.value) == (
        f"{PKG} reference/old.json: 3 validation error(s); first at endpoint (missing): "
        "Field required"
    )
    assert (info.value.raw, info.value.__cause__) == ({"param": "x"}, None)


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


VALUES = {"VA": "VA", "AK": "AK", "TX": "TX"}
"""Bare values, sdk-usda-nass's ``state_alpha`` in shape: each value is its own name."""


def test_closest_needs_difflib_s_default_similarity_and_takes_no_cutoff() -> None:
    # One wrong letter of two is a ratio of 0.5, under difflib's 0.6: no code is named. The
    # keyword that lowered it had no caller (https://github.com/xippios/sdk-core/issues/475).
    assert closest("VS", VALUES) == []
    assert closest("VA ", {"VA": "Virginia"}) == [("VA", "Virginia")]
    with pytest.raises(TypeError, match="cutoff"):
        closest("VS", VALUES, cutoff=0.5)  # type: ignore[call-arg]


ESR_COMMODITIES = {902: "Soybean Oil", 1001: "Flaxseed", 104: "Wheat - White"}
"""Three of sdk-usda-esr's commodities, keyed by their integer codes."""


def test_nearest_names_the_codes_nearest_by_number() -> None:
    # sdk-usda-esr's and sdk-usda-gats's strategy (https://github.com/xippios/sdk-core/issues/107).
    assert nearest(999, ESR_COMMODITIES, n=2) == [(1001, "Flaxseed"), (902, "Soybean Oil")]
    assert nearest(999, ESR_COMMODITIES) == [
        (1001, "Flaxseed"),
        (902, "Soybean Oil"),
        (104, "Wheat - White"),
    ]


def test_nearest_reads_codes_keyed_by_their_text_and_returns_them_so() -> None:
    # sdk-usda-gats keys its customs districts by the id's text.
    districts = {
        "10": "NEW YORK, N.Y.",
        "2": "ST.ALBANS, VT.",
        "0": "Z UNKNOW CDIST CODES",
        "1": "PORTLAND,MAINE",
    }
    assert nearest(-1, districts) == [
        ("0", "Z UNKNOW CDIST CODES"),
        ("1", "PORTLAND,MAINE"),
        ("2", "ST.ALBANS, VT."),
    ]
    by_text = {str(code): name for code, name in ESR_COMMODITIES.items()}
    assert nearest(999, by_text, n=2) == [("1001", "Flaxseed"), ("902", "Soybean Oil")]


def test_nearest_takes_the_lower_of_two_codes_equally_near() -> None:
    assert nearest(5, {6: "six", 9: "nine", 4: "four"}, n=2) == [(4, "four"), (6, "six")]


def test_nearest_of_no_codes_is_none() -> None:
    assert nearest(5, {}) == []


def test_nearest_refuses_an_n_below_one_and_a_code_that_is_no_integer() -> None:
    with pytest.raises(ValueError, match=r"n must be > 0: 0"):
        nearest(999, ESR_COMMODITIES, n=0)
    with pytest.raises(ValueError, match=r"the code 'R04' of codes is not an integer"):
        nearest(4, {"R04": "South America"})
