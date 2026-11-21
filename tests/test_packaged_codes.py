"""The check of an argument against a packaged list (ADR-0045, sdk-core#313).

Each form the nine sources' copies take has its test: a text code (sdk-usda-psd), an
integer code (sdk-usda-esr), a folded case (sdk-usda-nass), a hint table (sdk-usda-psd's
``COUNTRY_HINTS``), a text for a list of integer codes, the text for when no code is close
(sdk-usda-nass, sdk-usda-gats), a strategy of the source's own (sdk-usda-esr, sdk-usda-gats,
sdk-comtrade, sdk-usda-wasde) and the reason.
"""

import importlib
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum, IntEnum, StrEnum
from pathlib import Path
from typing import Any

import pytest

import xippios.core.reference as reference
from xippios.core import InvalidRequestError, PackagedCodes, PackagedList, UnknownCode
from xippios.core.reference import _read_text

FETCHED = "2026-10-23"

PSD_COUNTRIES = PackagedList.model_validate(
    {
        "param": "countries",
        "endpoint": "PSDData_GetCountries",
        "fetched": FETCHED,
        "records": [
            {"countryCode": "US", "countryName": "United States", "regionCode": "R01"},
            {"countryCode": "BR", "countryName": "Brazil", "regionCode": "R04"},
            {"countryCode": "E4", "countryName": "European Union", "regionCode": "R03"},
        ],
    }
)
"""sdk-usda-psd's countries, text codes."""

ESR_COMMODITIES = PackagedList.model_validate(
    {
        "param": "commodities",
        "endpoint": "ESRData_GetCommodities",
        "fetched": FETCHED,
        "records": [
            {"commodityCode": 104, "commodityName": "Wheat - White"},
            {"commodityCode": 401, "commodityName": "Corn"},
            {"commodityCode": 902, "commodityName": "Soybean Oil"},
            {"commodityCode": 1001, "commodityName": "Flaxseed"},
        ],
    }
)
"""sdk-usda-esr's commodities, integer codes."""

NASS_STATES = PackagedList.model_validate(
    {
        "param": "state_alpha",
        "endpoint": "api/get_param_values",
        "fetched": FETCHED,
        "records": [{"state_alpha": "VA"}, {"state_alpha": "IA"}, {"state_alpha": "US"}],
    }
)
"""sdk-usda-nass's states, a value list that Quick Stats compares without case."""

REASON = "PSD answers unknown codes with an empty result, so the package refuses them."

COUNTRY_HINTS = {
    "all": "Omit country_code for every country; PSD's 'all' is a path element, not a code.",
}
"""sdk-usda-psd's hint table: a value that is no code, with what to do instead."""


def countries() -> PackagedCodes:
    return PSD_COUNTRIES.codes("countryCode", "countryName", source="usda-psd")


def commodities() -> PackagedCodes:
    return ESR_COMMODITIES.codes("commodityCode", "commodityName", source="usda-esr")


def states() -> PackagedCodes:
    return NASS_STATES.codes("state_alpha", fold_case=True, source="usda-nass")


# The forms of the row's proof


def test_a_text_code_the_list_holds_is_returned_as_given() -> None:
    code = "".join(["U", "S"])  # a new object, equal to the list's code
    assert countries().check("country_code", code) is code


def test_a_text_code_the_list_lacks_raises_unknown_code_naming_list_date_and_closest() -> None:
    with pytest.raises(UnknownCode) as info:
        countries().check("country_code", "us", reason=REASON)
    error = info.value
    assert str(error) == (
        "'us' is not a country_code in the packaged countries list (fetched 2026-10-23). "
        "Did you mean US (United States)? PSD answers unknown codes with an empty result, so "
        "the package refuses them. If upstream added it since, the packaged list is out of date."
    )
    assert (error.param, error.value, error.list_name) == ("country_code", "us", "countries")
    assert error.fetched == datetime(2026, 10, 23, tzinfo=UTC)
    assert error.closest == (("US", "United States"),)
    assert error.source == "usda-psd"


def test_an_integer_code_the_list_holds_is_returned_as_given() -> None:
    assert commodities().check("commodity_code", 401) == 401


def test_an_integer_code_the_list_lacks_names_the_codes_nearest_by_number() -> None:
    with pytest.raises(UnknownCode) as info:
        commodities().check("commodity_code", 999)
    assert info.value.closest == ((1001, "Flaxseed"), (902, "Soybean Oil"), (401, "Corn"))
    assert "Did you mean 1001 (Flaxseed), 902 (Soybean Oil), 401 (Corn)?" in str(info.value)
    assert info.value.value == 999


def test_a_folded_case_passes_and_the_callers_spelling_is_returned() -> None:
    assert states().check("state_alpha", "va") == "va"  # sent and recorded as given (§5)
    assert states().check("state_alpha", "Ia") == "Ia"


def test_without_folding_another_case_is_unknown() -> None:
    exact = NASS_STATES.codes("state_alpha")
    with pytest.raises(UnknownCode) as info:
        exact.check("state_alpha", "va")
    assert "Did you mean VA?" in str(info.value)  # a value list: the code named once


def test_a_value_the_hint_table_holds_is_refused_with_its_hint_in_place_of_closest() -> None:
    for given in ("all", " ALL "):  # the table is read stripped and without case
        with pytest.raises(UnknownCode) as info:
            countries().check("country_code", given, hints=COUNTRY_HINTS, reason=REASON)
        assert str(info.value) == (
            f"{given!r} is not a country_code in the packaged countries list (fetched "
            "2026-10-23). Omit country_code for every country; PSD's 'all' is a path element, "
            "not a code. PSD answers unknown codes with an empty result, so the package refuses "
            "them. If upstream added it since, the packaged list is out of date."
        )
        assert info.value.closest == ()


def test_a_hint_table_with_keys_in_capitals_is_read_without_case() -> None:
    with pytest.raises(UnknownCode, match="Omit it"):
        countries().check("country_code", "all", hints={"ALL": "Omit it."})


def test_a_value_the_hint_table_lacks_names_the_closest_codes() -> None:
    with pytest.raises(UnknownCode, match=r"Did you mean BR \(Brazil\)\?"):
        countries().check("country_code", "Brasil", hints=COUNTRY_HINTS)


def test_a_hint_is_read_before_the_lists_type() -> None:
    # A hint is for a value that is no code, and a text given for integer codes is one
    # (https://github.com/xippios/sdk-core/issues/361, parts 2 and 3).
    hints = {"all": "Omit commodity_code for every commodity."}
    with pytest.raises(UnknownCode) as info:
        commodities().check("commodity_code", "all", hints=hints)
    assert str(info.value) == (
        "'all' is not a commodity_code in the packaged commodities list (fetched 2026-10-23). "
        "Omit commodity_code for every commodity. If upstream added it since, the packaged "
        "list is out of date."
    )
    assert info.value.closest == ()
    with pytest.raises(UnknownCode) as world:  # an integer for text codes, by its text
        countries().check("reporter_code", 0, hints={"0": "0 (World) is a partner code only."})
    assert "(fetched 2026-10-23). 0 (World) is a partner code only. If" in str(world.value)


def test_a_hint_is_read_for_text_and_integers_alone() -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", None, hints={"none": "never shown"})
    assert not isinstance(info.value, UnknownCode)
    assert "never shown" not in str(info.value)


def test_a_digit_text_for_a_list_of_integer_codes_is_refused_with_the_integer_to_pass() -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", "104")
    assert not isinstance(info.value, UnknownCode)
    assert str(info.value) == (
        "'104' is not an integer code: commodity_code takes the integer codes of the packaged "
        "commodities list (fetched 2026-10-23), such as 104 (Wheat - White). Pass it as the "
        "integer 104."
    )
    assert info.value.source == "usda-esr"


def test_a_name_for_a_list_of_integer_codes_is_refused_naming_the_codes_by_name() -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", "wheat")
    assert str(info.value).endswith("By name: 104 (Wheat - White).")
    with pytest.raises(InvalidRequestError) as near:
        commodities().check("commodity_code", "Flaxsed")  # a name misspelt
    assert str(near.value).endswith("By name: 1001 (Flaxseed).")


@pytest.mark.parametrize("value", [True, 4.0, None])
def test_a_value_of_no_integer_type_is_refused_for_a_list_of_integer_codes(value: object) -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", value)
    assert str(info.value).startswith(f"{value!r} is not an integer code: commodity_code takes")


def test_an_integer_for_a_list_of_text_codes_is_refused_with_the_text_to_pass() -> None:
    reporters = PackagedList.model_validate(
        {**PSD_COUNTRIES.model_dump(), "records": [{"code": "757", "name": "Switzerland"}]}
    ).codes("code", "name")
    with pytest.raises(InvalidRequestError) as info:
        reporters.check("reporter_code", 757)
    assert str(info.value) == (
        "757 is not a text code: reporter_code takes the text codes of the packaged countries "
        "list (fetched 2026-10-23), such as 757 (Switzerland). Pass it as the text '757'."
    )


def test_an_integer_for_a_list_of_text_codes_names_the_closest_texts() -> None:
    psd = PackagedList.model_validate(
        {**PSD_COUNTRIES.model_dump(), "records": [{"code": "0410000", "name": "Wheat"}]}
    ).codes("code", "name")
    with pytest.raises(InvalidRequestError) as info:
        psd.check("commodity_code", 410000)  # the leading zero lost
    assert str(info.value).endswith("Did you mean 0410000 (Wheat)?")


def test_otherwise_is_the_text_when_no_code_is_close() -> None:
    otherwise = "list_param_values('state_alpha') lists the known values."
    with pytest.raises(UnknownCode) as info:
        states().check("state_alpha", "ZZZZZZ", otherwise=otherwise)
    assert info.value.closest == ()
    assert f"(fetched 2026-10-23). {otherwise} If upstream" in str(info.value)


def test_otherwise_stays_out_when_a_code_is_close() -> None:
    with pytest.raises(UnknownCode) as info:
        states().check("state_alpha", "VAA", otherwise="never shown")
    assert "never shown" not in str(info.value)
    assert "Did you mean VA?" in str(info.value)


def test_otherwise_follows_a_wrong_type_that_names_no_code() -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", None, otherwise="list_commodities lists them.")
    assert str(info.value).endswith("such as 104 (Wheat - White). list_commodities lists them.")


def test_a_strategy_of_the_sources_own_names_its_codes() -> None:
    seen: list[tuple[object, Mapping[Any, str]]] = []

    def three_letter_first(value: str, names: Mapping[str, str]) -> list[tuple[str, str]]:
        seen.append((value, names))
        return [("US", names["US"])] if value == "USA" else []

    with pytest.raises(UnknownCode) as info:
        countries().check("partner_code", "USA", closest=three_letter_first)
    assert info.value.closest == (("US", "United States"),)
    assert seen == [("USA", {"US": "United States", "BR": "Brazil", "E4": "European Union"})]


def test_a_strategy_for_integer_codes_gets_the_integer() -> None:
    def by_digits(value: int, names: Mapping[int, str]) -> list[tuple[int, str]]:
        return [(code, names[code]) for code in names if str(code).startswith(str(value)[:2])]

    with pytest.raises(UnknownCode) as info:
        commodities().check("commodity_code", 1040, closest=by_digits)
    assert info.value.closest == ((104, "Wheat - White"), (1001, "Flaxseed"))


def test_the_reason_ends_the_refusal_before_the_lists_age() -> None:
    reason = "The task keeps this id's records after the call, so the package refuses it."
    with pytest.raises(UnknownCode) as info:
        commodities().check("attribute_id", 3, reason=reason)
    assert str(info.value).endswith(
        f"{reason} If upstream added it since, the packaged list is out of date."
    )


def test_an_enum_member_is_compared_by_its_value_and_returned_as_given() -> None:
    class State(StrEnum):
        VA = "VA"
        ZZ = "ZZ"

    class Unit(IntEnum):
        CORN = 401
        RYE = 7

    class Plain(Enum):
        IA = "IA"

    assert states().check("state_alpha", State.VA) is State.VA
    assert commodities().check("commodity_code", Unit.CORN) is Unit.CORN
    assert states().check("state_alpha", Plain.IA) is Plain.IA
    with pytest.raises(UnknownCode) as info:
        states().check("state_alpha", State.ZZ)
    assert str(info.value).startswith("'ZZ' is not a state_alpha")  # the value, not the member
    with pytest.raises(UnknownCode) as unit:
        commodities().check("commodity_code", Unit.RYE)
    assert str(unit.value).startswith("7 is not a commodity_code")


# The index, kept for the process


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    name = "codespkg_for_tests"
    root = tmp_path / name
    (root / "reference").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    PSD_COUNTRIES.write(root / "reference" / "countries.json")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, name, raising=False)
    importlib.invalidate_caches()
    _read_text.cache_clear()
    return name


def test_two_checks_of_one_declaration_load_the_list_once(
    package: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    loads: list[str] = []
    load_json = reference.load_json

    def counted(package: str, name: str) -> Any:
        loads.append(name)
        return load_json(package, name)

    monkeypatch.setattr(reference, "load_json", counted)
    declared = PackagedList.load(package, "countries").codes("countryCode", "countryName")
    assert declared.check("country_code", "US") == "US"
    with pytest.raises(UnknownCode):
        declared.check("country_code", "XX")
    assert loads == ["countries.json"]


def test_the_index_is_built_once_when_the_list_is_declared() -> None:
    packaged = PSD_COUNTRIES.model_copy(deep=True)
    declared = packaged.codes("countryCode", "countryName")
    packaged.records.clear()  # what a check reads is the declaration's own index
    assert declared.check("country_code", "BR") == "BR"
    assert declared.name_of("BR") == "Brazil"


# The read access of the declaration, for the live comparison (#374) and meta.names (#375)


def test_the_declaration_reads_its_fields_its_names_and_its_list() -> None:
    declared = countries()
    assert (declared.code, declared.name, declared.fold_case) == (
        "countryCode",
        "countryName",
        False,
    )
    assert declared.packaged is PSD_COUNTRIES
    assert (declared.list_name, declared.source, declared.integer) == (
        "countries",
        "usda-psd",
        False,
    )
    assert dict(declared.names) == {"US": "United States", "BR": "Brazil", "E4": "European Union"}
    assert list(declared.names) == ["US", "BR", "E4"]  # upstream order


def test_names_cannot_be_changed_through_the_declaration() -> None:
    with pytest.raises(TypeError):
        countries().names["US"] = "changed"  # type: ignore[index]


def test_name_of_compares_as_the_check_does() -> None:
    assert countries().name_of("E4") == "European Union"
    assert countries().name_of("XX") is None
    assert countries().name_of(4) is None  # a text list holds no integer
    assert commodities().name_of(1001) == "Flaxseed"
    assert commodities().name_of("1001") is None  # nor an integer list a text
    assert commodities().name_of(True) is None
    assert states().name_of("va") == "VA"  # a value list: its own name, as upstream spells it


def test_membership_compares_as_the_check_does() -> None:
    assert "US" in countries()
    assert "us" not in countries()
    assert "us" in states()
    assert 401 in commodities()
    assert "401" not in commodities()


def test_a_list_names_itself_by_its_param_unless_given_its_own_name() -> None:
    faostat = PackagedList.model_validate(
        {
            "param": "element",
            "endpoint": "definitions/domain/QCL/element",
            "fetched": FETCHED,
            "records": [{"code": "5510", "label": "Production"}],
        }
    )
    assert faostat.codes("code", "label").list_name == "element"
    declared = faostat.codes("code", "label", list_name="element_QCL")
    with pytest.raises(UnknownCode) as info:
        declared.check("element", "5511")
    assert info.value.list_name == "element_QCL"
    assert "the packaged element_QCL list" in str(info.value)


def test_a_code_without_a_name_is_named_by_its_own_text() -> None:
    listed = PackagedList.model_validate(
        {
            **PSD_COUNTRIES.model_dump(),
            "records": [{"code": "A", "label": None}, {"code": "B", "label": ""}],
        }
    ).codes("code", "label")
    assert dict(listed.names) == {"A": "A", "B": "B"}


def test_a_code_listed_twice_keeps_the_name_of_its_first_record() -> None:
    matrices = PackagedList.model_validate(
        {
            **PSD_COUNTRIES.model_dump(),
            "records": [
                {"commodity": "CORN", "table": "sr12"},
                {"commodity": "CORN", "table": "x"},
            ],
        }
    ).codes("commodity", "table")
    assert dict(matrices.names) == {"CORN": "sr12"}


def test_names_show_upstreams_padding_collapsed_in_a_refusal_and_kept_in_names() -> None:
    esr = PackagedList.model_validate(
        {
            **ESR_COMMODITIES.model_dump(),
            "records": [{"countryCode": 1220, "countryDescription": "CANADA                  "}],
        }
    ).codes("countryCode", "countryDescription")
    assert esr.names[1220] == "CANADA                  "  # upstream's record, verbatim
    with pytest.raises(UnknownCode) as info:
        esr.check("country_code", 1202)
    assert info.value.closest == ((1220, "CANADA"),)
    with pytest.raises(InvalidRequestError) as named:
        esr.check("country_code", "canada")
    assert str(named.value).endswith("such as 1220 (CANADA). By name: 1220 (CANADA).")


# What a declaration refuses, at once


def records(*items: dict[str, Any]) -> PackagedList:
    return PackagedList.model_validate({**PSD_COUNTRIES.model_dump(), "records": list(items)})


@pytest.mark.parametrize(
    ("listed", "code", "name", "message"),
    [
        (records({"code": "A"}, {"name": "B"}), "code", None, "record 1 has no field 'code'"),
        (
            records({"code": "A", "name": "x"}, {"code": "B"}),
            "code",
            "name",
            "record 1 has no field 'name'",
        ),
        (
            records({"code": "A"}, {"code": 2}),
            "code",
            None,
            "field 'code' holds integers and text; a list's codes are one or the other",
        ),
        (
            records({"code": True}),
            "code",
            None,
            "record 0: field 'code' is neither text nor an integer",
        ),
        (
            records({"code": 2.5}),
            "code",
            None,
            "record 0: field 'code' is neither text nor an integer",
        ),
        (
            records({"code": "A", "name": 7}),
            "code",
            "name",
            "record 0: field 'name' is not text",
        ),
    ],
)
def test_a_declaration_refuses_records_that_do_not_fit_naming_the_field_never_the_record(
    listed: PackagedList, code: str, name: str | None, message: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(message)) as info:
        listed.codes(code, name)
    assert str(info.value) == f"countries: {message}"


def test_folding_is_refused_for_integer_codes_and_for_codes_one_fold_apart() -> None:
    with pytest.raises(ValueError, match="commodities: fold_case compares text"):
        ESR_COMMODITIES.codes("commodityCode", fold_case=True)
    with pytest.raises(ValueError, match="in two cases") as info:
        records({"region": "CORN"}, {"region": "Corn"}).codes("region", fold_case=True)
    assert str(info.value) == "countries: records 0 and 1 hold one code in two cases: 'Corn'"


def test_an_empty_list_holds_no_code() -> None:
    empty = records().codes("code")
    assert (dict(empty.names), empty.integer) == ({}, False)
    with pytest.raises(UnknownCode) as info:
        empty.check("code", "A")
    assert info.value.closest == ()
