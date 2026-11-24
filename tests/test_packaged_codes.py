"""The check of an argument against a packaged list (ADR-0045, sdk-core#313).

Each form the sources' copies take has its test: a text code, an integer code, a folded
case, a hint table (``COUNTRY_HINTS``), a text for a list of integer codes, the text for when no
code is close, a strategy of the source's own and the reason. The cases that the trial of the
release met have theirs: a text for integer codes that the source's strategy names, a hinted
refusal of a value that is no code, and the reason on the refusal of a value of the other type.
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

COUNTRIES = PackagedList.model_validate(
    {
        "param": "countries",
        "endpoint": "countries",
        "fetched": FETCHED,
        "records": [
            {"countryCode": "US", "countryName": "United States", "regionCode": "R01"},
            {"countryCode": "BR", "countryName": "Brazil", "regionCode": "R04"},
            {"countryCode": "E4", "countryName": "European Union", "regionCode": "R03"},
        ],
    }
)
"""A list of countries, text codes."""

COMMODITIES = PackagedList.model_validate(
    {
        "param": "commodities",
        "endpoint": "commodities",
        "fetched": FETCHED,
        "records": [
            {"commodityCode": 104, "commodityName": "Wheat - White"},
            {"commodityCode": 401, "commodityName": "Corn"},
            {"commodityCode": 902, "commodityName": "Soybean Oil"},
            {"commodityCode": 1001, "commodityName": "Flaxseed"},
        ],
    }
)
"""A list of commodities, integer codes."""

STATES = PackagedList.model_validate(
    {
        "param": "state_alpha",
        "endpoint": "api/get_param_values",
        "fetched": FETCHED,
        "records": [{"state_alpha": "VA"}, {"state_alpha": "IA"}, {"state_alpha": "US"}],
    }
)
"""A list of states, a value list that upstream compares without case."""

REASON = "Upstream answers unknown codes with an empty result, so the package refuses them."

COUNTRY_HINTS = {
    "all": "Omit country_code for every country; upstream's 'all' is a path element, not a code.",
}
"""A hint table: a value that is no code, with what to do instead."""


def countries() -> PackagedCodes:
    return COUNTRIES.codes("countryCode", "countryName", source="example")


def commodities() -> PackagedCodes:
    return COMMODITIES.codes("commodityCode", "commodityName", source="example")


def states() -> PackagedCodes:
    return STATES.codes("state_alpha", fold_case=True, source="example")


# The forms of the row's proof


def test_a_text_code_the_list_holds_is_returned_as_given() -> None:
    code = "".join(["U", "S"])  # a new object, equal to the list's code
    assert countries().check("country_code", code) is code


def test_a_text_code_the_list_lacks_raises_unknown_code_naming_list_date_and_closest() -> None:
    with pytest.raises(UnknownCode) as info:
        countries().check("country_code", "us", reason=REASON)
    error = info.value
    assert str(error) == str(  # the refusal its arguments make; its words are test_errors.py's
        UnknownCode(
            "country_code",
            "us",
            list_name="countries",
            fetched=datetime(2026, 10, 23, tzinfo=UTC),
            closest=[("US", "United States")],
            reason=REASON,
        )
    )
    assert (error.param, error.value, error.list_name) == ("country_code", "us", "countries")
    assert error.fetched == datetime(2026, 10, 23, tzinfo=UTC)
    assert error.closest == (("US", "United States"),)
    assert error.source == "example"


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
    exact = STATES.codes("state_alpha")
    with pytest.raises(UnknownCode) as info:
        exact.check("state_alpha", "va")
    assert "Did you mean VA?" in str(info.value)  # a value list: the code named once


def test_a_value_the_hint_table_holds_is_refused_with_its_hint_in_place_of_closest() -> None:
    for given in ("all", " ALL "):  # the table is read stripped and without case
        with pytest.raises(UnknownCode) as info:
            countries().check("country_code", given, hints=COUNTRY_HINTS, reason=REASON)
        assert str(info.value) == str(
            UnknownCode(
                "country_code",
                given,
                list_name="countries",
                fetched=datetime(2026, 10, 23, tzinfo=UTC),
                hint=COUNTRY_HINTS["all"],
                reason=REASON,
                outdated=False,  # no code at all: no refresh of the list would make it one
            )
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
    assert str(info.value).endswith("Nothing was sent. Omit commodity_code for every commodity.")
    assert info.value.closest == ()
    with pytest.raises(UnknownCode) as world:  # an integer for text codes, by its text
        countries().check("reporter_code", 0, hints={"0": "0 (World) is a partner code only."})
    assert str(world.value).endswith("Nothing was sent. 0 (World) is a partner code only.")


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
        "commodities list (fetched 2026-10-23), such as 104 (Wheat - White). Nothing was sent. "
        "Pass it as the integer 104."
    )
    assert info.value.source == "example"


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
        {**COUNTRIES.model_dump(), "records": [{"code": "757", "name": "Switzerland"}]}
    ).codes("code", "name")
    with pytest.raises(InvalidRequestError) as info:
        reporters.check("reporter_code", 757)
    assert str(info.value) == (
        "757 is not a text code: reporter_code takes the text codes of the packaged countries "
        "list (fetched 2026-10-23), such as 757 (Switzerland). Nothing was sent. Pass it as the "
        "text '757'."
    )


def test_an_integer_for_a_list_of_text_codes_names_the_closest_texts() -> None:
    texts = PackagedList.model_validate(
        {**COUNTRIES.model_dump(), "records": [{"code": "0410000", "name": "Wheat"}]}
    ).codes("code", "name")
    with pytest.raises(InvalidRequestError) as info:
        texts.check("commodity_code", 410000)  # the leading zero lost
    assert str(info.value).endswith("Did you mean 0410000 (Wheat)?")


def test_otherwise_is_the_text_when_no_code_is_close() -> None:
    otherwise = "list_param_values('state_alpha') lists the known values."
    with pytest.raises(UnknownCode) as info:
        states().check("state_alpha", "ZZZZZZ", otherwise=otherwise)
    assert info.value.closest == ()
    assert f"Nothing was sent. {otherwise} If upstream" in str(info.value)


def test_otherwise_stays_out_when_a_code_is_close() -> None:
    with pytest.raises(UnknownCode) as info:
        states().check("state_alpha", "VAA", otherwise="never shown")
    assert "never shown" not in str(info.value)
    assert "Did you mean VA?" in str(info.value)


def test_otherwise_follows_a_wrong_type_that_names_no_code() -> None:
    with pytest.raises(InvalidRequestError) as info:
        commodities().check("commodity_code", None, otherwise="list_commodities lists them.")
    assert str(info.value).endswith(
        "such as 104 (Wheat - White). Nothing was sent. list_commodities lists them."
    )


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


# Several codes in one call, and a refusal that says nothing was sent
# (https://github.com/xippios/sdk-core/issues/481, parts 1 and 2)

EXAMPLE_REGIONS = PackagedList.model_validate(
    {
        "param": "regions",
        "endpoint": "regions",
        "fetched": FETCHED,
        "records": [
            {"code": "R1", "name": "North"},
            {"code": "R2", "name": "South"},
            {"code": "R3", "name": "East"},
        ],
    }
)
"""The invented source's regions, text codes."""

EXAMPLE_SERIES = PackagedList.model_validate(
    {
        "param": "series",
        "endpoint": "series",
        "fetched": FETCHED,
        "records": [{"id": 10, "label": "Exports"}, {"id": 20, "label": "Imports"}],
    }
)
"""The invented source's series, integer codes."""


def regions() -> PackagedCodes:
    return EXAMPLE_REGIONS.codes("code", "name", source="example")


def series() -> PackagedCodes:
    return EXAMPLE_SERIES.codes("id", "label", source="example")


def test_a_list_of_codes_the_list_holds_is_returned_as_given() -> None:
    given = ["R1", "R3", "R1"]
    assert regions().check("region_code", given) is given
    ids = (20, 10)  # a tuple is several codes too
    assert series().check("series_id", ids) is ids


def test_a_list_names_the_first_code_the_packaged_list_lacks() -> None:
    with pytest.raises(UnknownCode) as info:
        regions().check("region_code", ["R1", "R9", "X"])
    assert (info.value.param, info.value.value) == ("region_code", "R9")
    assert str(info.value).startswith(
        "'R9' is not a region_code in the packaged regions list (fetched 2026-10-23). Nothing "
        "was sent."
    )
    assert info.value.source == "example"


def test_a_list_refuses_its_first_code_of_the_other_type() -> None:
    with pytest.raises(InvalidRequestError) as info:
        series().check("series_id", [10, "20", 99])
    assert not isinstance(info.value, UnknownCode)
    assert str(info.value).startswith("'20' is not an integer code: series_id takes")
    assert str(info.value).endswith("Nothing was sent. Pass it as the integer 20.")


def test_each_code_of_a_list_reads_the_hint_table() -> None:
    hints = {"all": "Omit region_code for every region."}
    with pytest.raises(UnknownCode, match=r"Omit region_code for every region\.$"):
        regions().check("region_code", ["R2", "ALL"], hints=hints)


def test_an_empty_list_is_refused_naming_what_the_parameter_takes() -> None:
    nothing: list[list[str] | tuple[str, ...]] = [[], ()]
    for empty in nothing:
        with pytest.raises(InvalidRequestError) as info:
            regions().check("region_code", empty, otherwise="list_regions lists them.")
        assert not isinstance(info.value, UnknownCode)
        assert str(info.value) == (
            "region_code lists no code: it takes one or more text codes of the packaged regions "
            "list (fetched 2026-10-23), such as R1 (North). Nothing was sent. list_regions lists "
            "them."
        )
        assert info.value.source == "example"
    with pytest.raises(
        InvalidRequestError, match=r"^series_id lists no code: it takes one or more"
    ):
        series().check("series_id", [])


def test_a_list_inside_a_list_is_a_value_of_the_wrong_type() -> None:
    with pytest.raises(InvalidRequestError) as info:
        regions().check("region_code", [["R1"]])
    assert str(info.value).startswith("['R1'] is not a text code: region_code takes")


def test_every_refusal_of_the_check_says_that_nothing_was_sent() -> None:
    # A task calls check before any request of the call, which makes the sentence true
    # (conventions §5).
    refusals = []
    for codes, value in (
        (regions(), "R9"),  # a code the list lacks
        (regions(), 1),  # a value of the other type
        (regions(), []),  # no code at all
        (regions(), ["R1", "R9"]),  # the first code of a list that the list lacks
        (series(), "ten"),
    ):
        with pytest.raises(InvalidRequestError) as info:
            codes.check("param", value, reason="Example answers it with an empty list.")
        refusals.append(str(info.value))
    for refusal in refusals:
        first, sentence, _ = refusal.partition(". Nothing was sent.")
        assert sentence, refusal
        assert "Nothing was sent" not in first, refusal


# What the trial of the release met (https://github.com/xippios/sdk-core/issues/410)

PARTNERS = PackagedList.model_validate(
    {
        "param": "partnerAreas",
        "endpoint": "partnerAreas.json",
        "fetched": FETCHED,
        "records": [
            {"PartnerCode": 36, "PartnerDesc": "Australia", "PartnerCodeIsoAlpha2": "AU"},
            {"PartnerCode": 40, "PartnerDesc": "Austria", "PartnerCodeIsoAlpha2": "AT"},
            {"PartnerCode": 112, "PartnerDesc": "Belarus", "PartnerCodeIsoAlpha2": "BY"},
            {"PartnerCode": 757, "PartnerDesc": "Switzerland", "PartnerCodeIsoAlpha2": "CH"},
            {"PartnerCode": 842, "PartnerDesc": "USA", "PartnerCodeIsoAlpha2": "US"},
        ],
    }
)
"""A list of partner areas, integer codes, each with its ISO alpha-2 code."""

PARTNER_REASON = (
    "Upstream answers a code it does not have with count 0, so the package refuses it "
    "before the call."
)

ALPHA_3_HINTS = {"CHE": "CHE is the ISO alpha-3 code of 757 (Switzerland): pass 757."}
"""A hint table: an ISO alpha-3 code is no code of upstream's (ADR-0067, 11)."""


def partners() -> PackagedCodes:
    return PARTNERS.codes("PartnerCode", "PartnerDesc", source="example")


PARTNER_NAMES = {36: "Australia", 40: "Austria", 112: "Belarus", 757: "Switzerland", 842: "USA"}
"""The partners' codes to their names, as a strategy is handed them."""


def alpha_2_first(seen: list[tuple[object, Mapping[Any, str]]]) -> Any:
    """A source's own strategy: an ISO alpha-2 code names its area, else nothing."""
    by_alpha_2 = {
        str(record["PartnerCodeIsoAlpha2"]): int(record["PartnerCode"])
        for record in PARTNERS.records
    }

    def strategy(value: object, names: Mapping[Any, str]) -> list[tuple[Any, str]]:
        seen.append((value, names))
        code = by_alpha_2.get(value.strip().upper()) if isinstance(value, str) else None
        return [] if code is None else [(code, names[code])]

    return strategy


def test_a_text_for_integer_codes_asks_the_sources_strategy() -> None:
    # "US" for a partner: the codes whose name holds the two letters are Australia, Austria
    # and Belarus, and the source's strategy knows 842
    # (https://github.com/xippios/sdk-core/issues/418).
    seen: list[tuple[object, Mapping[Any, str]]] = []
    with pytest.raises(InvalidRequestError) as info:
        partners().check("partner_code", "US", closest=alpha_2_first(seen), reason=PARTNER_REASON)
    assert not isinstance(info.value, UnknownCode)
    assert str(info.value) == (
        "'US' is not an integer code: partner_code takes the integer codes of the packaged "
        "partnerAreas list (fetched 2026-10-23), such as 36 (Australia). Nothing was sent. Did "
        f"you mean 842 (USA)? {PARTNER_REASON}"
    )
    assert seen == [("US", PARTNER_NAMES)]  # the value as given, the names as shown


def test_a_text_for_integer_codes_is_named_by_name_without_a_strategy() -> None:
    with pytest.raises(InvalidRequestError) as info:
        partners().check("partner_code", "US")
    assert str(info.value).endswith(
        "such as 36 (Australia). Nothing was sent. By name: 36 (Australia), 40 (Austria), "
        "112 (Belarus)."
    )


def test_a_text_the_strategy_names_nothing_for_is_named_by_name() -> None:
    seen: list[tuple[object, Mapping[Any, str]]] = []
    with pytest.raises(InvalidRequestError) as info:
        partners().check("partner_code", "Switzerland", closest=alpha_2_first(seen))
    assert str(info.value).endswith(
        "such as 36 (Australia). Nothing was sent. By name: 757 (Switzerland)."
    )
    assert [value for value, _ in seen] == ["Switzerland"]


def test_a_text_of_digits_names_the_integer_and_asks_no_strategy() -> None:
    seen: list[tuple[object, Mapping[Any, str]]] = []
    with pytest.raises(InvalidRequestError) as info:
        partners().check("partner_code", " 842 ", closest=alpha_2_first(seen))
    assert str(info.value).endswith(
        "such as 36 (Australia). Nothing was sent. Pass it as the integer 842."
    )
    assert seen == []


def test_an_integer_the_list_lacks_still_gets_the_strategy_and_else_the_nearest() -> None:
    seen: list[tuple[object, Mapping[Any, str]]] = []
    with pytest.raises(UnknownCode) as info:
        partners().check("partner_code", 841, closest=alpha_2_first(seen))
    assert seen == [(841, PARTNER_NAMES)]
    assert info.value.closest == ()
    with pytest.raises(UnknownCode) as nearest:
        partners().check("partner_code", 841)
    assert nearest.value.closest == ((842, "USA"), (757, "Switzerland"), (112, "Belarus"))


def test_a_value_of_the_hint_table_leaves_out_that_the_list_is_out_of_date() -> None:
    # "CHE" is no code at all: no refresh of the list makes it one
    # (https://github.com/xippios/sdk-core/issues/430).
    with pytest.raises(UnknownCode) as info:
        partners().check("reporter_code", "CHE", hints=ALPHA_3_HINTS, reason=PARTNER_REASON)
    assert str(info.value).endswith(
        f"Nothing was sent. CHE is the ISO alpha-3 code of 757 (Switzerland): pass 757. "
        f"{PARTNER_REASON}"
    )
    assert "out of date" not in str(info.value)


def test_a_refusal_without_a_hint_keeps_that_the_list_may_be_out_of_date() -> None:
    tail = "If upstream added it since, the packaged list is out of date."
    with pytest.raises(UnknownCode) as close:
        partners().check("partner_code", 843, hints=ALPHA_3_HINTS, reason=PARTNER_REASON)
    assert str(close.value).endswith(
        f"Did you mean 842 (USA), 757 (Switzerland), 112 (Belarus)? {PARTNER_REASON} {tail}"
    )
    with pytest.raises(UnknownCode) as far:
        states().check("state_alpha", "ZZZZZZ", hints={"all": "never shown"}, otherwise="Ask.")
    assert str(far.value).endswith(f"Nothing was sent. Ask. {tail}")  # otherwise is no hint


def test_an_integer_for_text_codes_carries_the_reason() -> None:
    # An aggregation level given as 19 (https://github.com/xippios/sdk-core/issues/432).
    levels = PackagedList.model_validate(
        {
            "param": "agg_level_desc",
            "endpoint": "api/get_param_values",
            "fetched": FETCHED,
            "records": [{"agg_level_desc": "COUNTY"}, {"agg_level_desc": "STATE"}],
        }
    ).codes("agg_level_desc", fold_case=True, source="example")
    reason = "Upstream answers an unknown value with HTTP 400, so nothing was sent."
    with pytest.raises(InvalidRequestError) as info:
        levels.check("agg_level_desc", 19, reason=reason)
    assert not isinstance(info.value, UnknownCode)
    assert str(info.value) == (
        "19 is not a text code: agg_level_desc takes the text codes of the packaged "
        f"agg_level_desc list (fetched 2026-10-23), such as COUNTY. Nothing was sent. {reason}"
    )
    reporters = PackagedList.model_validate(
        {**COUNTRIES.model_dump(), "records": [{"code": "757", "name": "Switzerland"}]}
    ).codes("code", "name")
    with pytest.raises(InvalidRequestError) as text:
        reporters.check("reporter_code", 757, reason=reason)
    assert str(text.value).endswith(
        f"such as 757 (Switzerland). Nothing was sent. Pass it as the text '757'. {reason}"
    )


def test_a_text_for_integer_codes_carries_the_reason_after_its_hint() -> None:
    reason = "Upstream answers unknown codes with an empty result, so the package refuses them."
    with pytest.raises(InvalidRequestError) as digits:
        commodities().check("commodity_code", "104", reason=reason)
    assert str(digits.value) == (
        "'104' is not an integer code: commodity_code takes the integer codes of the packaged "
        "commodities list (fetched 2026-10-23), such as 104 (Wheat - White). Nothing was sent. "
        f"Pass it as the integer 104. {reason}"
    )
    with pytest.raises(InvalidRequestError) as named:
        commodities().check("commodity_code", "wheat", reason=reason)
    assert str(named.value).endswith(f"By name: 104 (Wheat - White). {reason}")
    otherwise = "list_commodities lists them."
    with pytest.raises(InvalidRequestError) as bare:
        commodities().check("commodity_code", None, otherwise=otherwise, reason=reason)
    assert str(bare.value).endswith(
        f"such as 104 (Wheat - White). Nothing was sent. {otherwise} {reason}"
    )


# The index, kept for the process


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    name = "codespkg_for_tests"
    root = tmp_path / name
    (root / "reference").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    COUNTRIES.write(root / "reference" / "countries.json")
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
    packaged = COUNTRIES.model_copy(deep=True)
    declared = packaged.codes("countryCode", "countryName")
    packaged.records.clear()  # what a check reads is the declaration's own index
    assert declared.check("country_code", "BR") == "BR"
    assert declared.name_of("BR") == "Brazil"


# The read access of the declaration, for the live comparison (#374) and meta.names (#375)


def test_the_declaration_reads_what_core_reads_of_it() -> None:
    declared = countries()
    assert (declared.code, declared.list_name, declared.integer) == (
        "countryCode",
        "countries",
        False,
    )
    assert declared.packaged is COUNTRIES


def test_the_members_that_no_caller_read_have_left() -> None:
    # name, fold_case, source, names and the in test (https://github.com/xippios/sdk-core/issues/475).
    example = PackagedList.model_validate(
        {
            "param": "regions",
            "endpoint": "regions",
            "fetched": FETCHED,
            "records": [{"code": "R1", "name": "North"}],
        }
    ).codes("code", "name", source="example")
    for member in ("name", "fold_case", "source", "names"):
        assert not hasattr(example, member), member
    with pytest.raises(TypeError):
        _ = "R1" in example  # type: ignore[operator]
    assert example.name_of("R1") == "North"


def test_name_of_compares_as_the_check_does() -> None:
    assert countries().name_of("E4") == "European Union"
    assert countries().name_of("XX") is None
    assert countries().name_of(4) is None  # a text list holds no integer
    assert commodities().name_of(1001) == "Flaxseed"
    assert commodities().name_of("1001") is None  # nor an integer list a text
    assert commodities().name_of(True) is None
    assert states().name_of("va") == "VA"  # a value list: its own name, as upstream spells it


def test_a_list_names_itself_by_its_param_unless_given_its_own_name() -> None:
    elements = PackagedList.model_validate(
        {
            "param": "element",
            "endpoint": "definitions/domain/QCL/element",
            "fetched": FETCHED,
            "records": [{"code": "5510", "label": "Production"}],
        }
    )
    assert elements.codes("code", "label").list_name == "element"
    declared = elements.codes("code", "label", list_name="element_QCL")
    with pytest.raises(UnknownCode) as info:
        declared.check("element", "5511")
    assert info.value.list_name == "element_QCL"
    assert "the packaged element_QCL list" in str(info.value)


def test_a_code_without_a_name_is_named_by_its_own_text() -> None:
    listed = PackagedList.model_validate(
        {
            **COUNTRIES.model_dump(),
            "records": [{"code": "A", "label": None}, {"code": "B", "label": ""}],
        }
    ).codes("code", "label")
    assert (listed.name_of("A"), listed.name_of("B")) == ("A", "B")


def test_a_code_listed_twice_keeps_the_name_of_its_first_record() -> None:
    matrices = PackagedList.model_validate(
        {
            **COUNTRIES.model_dump(),
            "records": [
                {"commodity": "CORN", "table": "sr12"},
                {"commodity": "CORN", "table": "x"},
            ],
        }
    ).codes("commodity", "table")
    assert matrices.name_of("CORN") == "sr12"


def test_names_show_upstreams_padding_collapsed_in_a_refusal_and_kept_in_names() -> None:
    padded = PackagedList.model_validate(
        {
            **COMMODITIES.model_dump(),
            "records": [{"countryCode": 1220, "countryDescription": "CANADA                  "}],
        }
    ).codes("countryCode", "countryDescription")
    assert padded.name_of(1220) == "CANADA                  "  # upstream's record, verbatim
    with pytest.raises(UnknownCode) as info:
        padded.check("country_code", 1202)
    assert info.value.closest == ((1220, "CANADA"),)
    with pytest.raises(InvalidRequestError) as named:
        padded.check("country_code", "canada")
    assert str(named.value).endswith(
        "such as 1220 (CANADA). Nothing was sent. By name: 1220 (CANADA)."
    )


# What a declaration refuses, at once


def records(*items: dict[str, Any]) -> PackagedList:
    return PackagedList.model_validate({**COUNTRIES.model_dump(), "records": list(items)})


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
        COMMODITIES.codes("commodityCode", fold_case=True)
    with pytest.raises(ValueError, match="in two cases") as info:
        records({"region": "CORN"}, {"region": "Corn"}).codes("region", fold_case=True)
    assert str(info.value) == "countries: records 0 and 1 hold one code in two cases: 'Corn'"


def test_an_empty_list_holds_no_code() -> None:
    empty = records().codes("code")
    assert (empty.name_of("A"), empty.integer) == (None, False)
    with pytest.raises(UnknownCode) as info:
        empty.check("code", "A")
    assert info.value.closest == ()
