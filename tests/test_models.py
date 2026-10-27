import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import AliasChoices, Field, computed_field

from xippios.core.errors import ValidationError
from xippios.core.models import (
    Result,
    ResultCap,
    ResultMeta,
    UpstreamModel,
    parse,
    parse_decimal,
)


class Series(UpstreamModel):
    series_id: str = Field(alias="seriesId")
    value: float


def test_upstream_model_is_frozen_and_ignores_unknown_fields() -> None:
    item = Series.model_validate({"seriesId": "a", "value": "1.5", "newUpstreamField": 1})
    assert item.series_id == "a"
    assert item.value == 1.5
    with pytest.raises(Exception, match="frozen"):
        item.value = 2  # type: ignore[misc]
    assert Series(series_id="b", value=1).series_id == "b"  # by name as well as by alias


def test_result_meta_defaults() -> None:
    meta = ResultMeta(source="example", endpoint="get_thing")
    assert meta.retrieved_at.tzinfo is not None
    assert meta.published_at is None
    assert meta.published_at_naive is False
    assert meta.vintage is None
    assert meta.request == {}
    assert meta.total is None
    assert meta.tenant is None


def test_result_meta_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultMeta(source="x", endpoint="y", retrieved_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware: published_at is naive"):
        ResultMeta(source="x", endpoint="y", published_at=datetime(2026, 1, 1))


def test_a_naive_release_time_is_kept_as_printed_with_the_flag() -> None:
    # ADR-0022, rule 2: FAS prints release times without a zone (sdk-usda-gats).
    printed = datetime(2026, 10, 6, 8, 0)
    meta = ResultMeta(
        source="usda-gats",
        endpoint="GATSData_GetCensusExportDataReleaseInfo",
        published_at=printed,
        published_at_naive=True,
        vintage="2026-10-06T08:00:00",
    )
    assert meta.published_at == printed
    assert meta.published_at is not None
    assert meta.published_at.tzinfo is None
    dumped = meta.model_dump(mode="json")
    assert (dumped["published_at"], dumped["published_at_naive"]) == ("2026-10-06T08:00:00", True)
    assert ResultMeta.model_validate_json(meta.model_dump_json()) == meta


@pytest.mark.parametrize(
    ("published_at", "states"),
    [(datetime(2026, 10, 6, 8, 0, tzinfo=UTC), "published_at carries one"),
     (None, "published_at is None")],
)  # fmt: skip
def test_the_flag_without_a_naive_release_time_is_refused(
    published_at: datetime | None, states: str
) -> None:
    with pytest.raises(ValueError, match=f"printed published_at without a zone, but {states}"):
        ResultMeta(source="s", endpoint="e", published_at=published_at, published_at_naive=True)


def test_result_meta_refuses_a_field_it_does_not_define() -> None:
    # Queue row 21 a (sdk-cashctrl): an unknown field used to be dropped without a word.
    with pytest.raises(ValueError, match=r"totl\n  Extra inputs are not permitted"):
        ResultMeta(source="s", endpoint="e", totl=3)  # type: ignore[call-arg]


def test_request_omits_what_the_caller_left_none() -> None:
    # ADR-0022, rule 3 (sdk-usda-psd): request records what was sent.
    meta = ResultMeta(
        source="s",
        endpoint="e",
        request={"search": None, "year": 2024, "filters": {"state": None}, "token": None},
    )
    assert meta.request == {"year": 2024, "filters": {"state": None}}


def test_result_meta_rejects_a_negative_total() -> None:
    with pytest.raises(ValueError, match="total must not be negative"):
        ResultMeta(source="s", endpoint="e", total=-1)


def test_result_envelope_round_trips() -> None:
    meta = ResultMeta(
        source="example",
        endpoint="account/list.json",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
        request={"id": 7},
        total=40,  # upstream's count, never len(data) (ADR-0012)
        tenant="acme",
    )
    result = Result[list[Series]](data=[Series(series_id="a", value=1)], meta=meta)
    dumped = result.model_dump(mode="json")
    assert (dumped["meta"]["total"], dumped["meta"]["tenant"]) == (40, "acme")
    assert dumped["data"][0]["series_id"] == "a"
    assert Result[list[Series]].model_validate(dumped) == result
    assert Result[list[Series]].model_validate_json(result.model_dump_json()) == result


def test_parse_model_and_generic() -> None:
    one = parse(Series, {"seriesId": "a", "value": 1}, source="example", endpoint="e")
    assert one.series_id == "a"
    many = parse(list[Series], [{"seriesId": "a", "value": 1}], source="example", endpoint="e")
    assert many[0].value == 1.0


MARKER = "payload-marker-of-row-42"
"""What a failing payload carries: it reaches ``raw``, never a printed traceback (row 42)."""


def test_parse_raises_the_first_failure_without_a_value_and_keeps_the_payload_on_raw() -> None:
    raw = [{"seriesId": MARKER, "value": 1}, {"seriesId": MARKER, "value": MARKER}]
    with pytest.raises(ValidationError) as info:
        parse(list[Series], raw, source="example", endpoint="get_thing")
    message = (
        "example get_thing: 1 validation error(s); first at 1.value (float_parsing): Input "
        "should be a valid number, unable to parse string as a number"
    )
    assert (str(info.value), repr(info.value)) == (message, f"ValidationError({message!r})")
    assert (info.value.raw, info.value.source) == (raw, "example")
    assert (info.value.__cause__, info.value.__suppress_context__) == (None, True)


FAILING_PARSES = f"""
from xippios.core import UpstreamModel, parse

RAW = [{{"value": "{MARKER}"}}]


class Series(UpstreamModel):
    value: float


class Wide(UpstreamModel):
    label: str
    value: str


WIDE = Wide(label="{MARKER}", value="{MARKER}")


def test_parse():
    parse(list[Series], RAW, source="example", endpoint="get_thing")


def test_project():
    Series.project(WIDE)
"""


def test_a_failing_parse_prints_no_payload_under_pytests_default_traceback(
    pytester: pytest.Pytester,
) -> None:
    # Row 42 (sdk-cashctrl): --tb=auto prints the raising frame long, its arguments too.
    pytester.makepyfile(FAILING_PARSES)
    result = pytester.runpytest()
    result.assert_outcomes(failed=2)
    printed = result.stdout.str()
    assert "first at 0.value (float_parsing)" in printed
    assert "Series.project: 1 validation error(s); first at value (float_parsing)" in printed
    assert "raw = " not in printed  # parse's frame, a middle entry, is printed short
    assert MARKER not in printed


def test_a_projection_that_does_not_fit_raises_the_taxonomys_error() -> None:
    wide = Wide(label=MARKER, amount=None, extra=1)
    with pytest.raises(ValidationError) as info:
        Row.project(wide, amounts=[MARKER])
    assert str(info.value) == (
        "Row.project: 1 validation error(s); first at amounts.0 (decimal_parsing): Input "
        "should be a valid decimal"
    )
    assert info.value.raw == {"label": MARKER, "amount": None, "amounts": [MARKER]}


class Row(UpstreamModel):
    label: str
    amount: Decimal | None
    amounts: list[Decimal]


class Wide(UpstreamModel):
    label: str
    amount: Decimal | None
    extra: int


@pytest.mark.parametrize(
    ("text", "expected"),
    [("510,000", Decimal("510000")), ("4.61", Decimal("4.61")), (" 98 ", Decimal("98")),
     ("(D)", None), ("", None), ("(NA)", None), ("1,234.5", Decimal("1234.5"))],
)  # fmt: skip
def test_parse_decimal(text: str, expected: Decimal | None) -> None:
    assert parse_decimal(text) == expected


def test_decimal_fields_serialise_as_json_numbers() -> None:
    row = Row(label="x", amount=Decimal("98.5"), amounts=[Decimal("1"), Decimal("2.25")])
    assert row.model_dump(mode="json") == {"label": "x", "amount": 98.5, "amounts": [1.0, 2.25]}
    assert json.loads(row.model_dump_json())["amount"] == 98.5
    assert row.model_dump()["amount"] == Decimal("98.5")
    assert Row(label="x", amount=None, amounts=[]).model_dump(mode="json")["amount"] is None
    envelope = Result[list[Row]](data=[row], meta=ResultMeta(source="s", endpoint="e"))
    assert envelope.model_dump(mode="json")["data"][0]["amounts"] == [1.0, 2.25]


def test_project_copies_same_named_fields_and_applies_overrides() -> None:
    wide = Wide(label="corn", amount=Decimal("3"), extra=7)
    row = Row.project(wide, amounts=[Decimal("1")])
    assert row == Row(label="corn", amount=Decimal("3"), amounts=[Decimal("1")])
    parsed = Row.project(wide, amount=parse_decimal("(D)"), amounts=[])
    assert parsed.amount is None


def test_project_names_the_missing_field() -> None:
    with pytest.raises(TypeError, match=r"Row\.project: Wide has no field amounts"):
        Row.project(Wide(label="x", amount=None, extra=1))


class Unit(UpstreamModel):
    unit_id: int = Field(validation_alias="unitId")
    unit_description: str = Field(serialization_alias="unitDescription")


class Country(UpstreamModel):
    country_code: str = Field(alias="countryCode")
    region_code: str = Field(validation_alias=AliasChoices("regionCode", "region_code"))
    genc_code: str | None = Field(default=None, validation_alias="gencCode")
    released: date
    share: Decimal
    unit: Unit
    units: list[Unit]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        return f"{self.country_code} ({self.region_code})"


def test_dump_upstream_restores_upstream_names_at_every_level() -> None:
    # Queue row 32 a: psd's, esr's, gats's and the template's upstream_record.
    record = {
        "countryCode": "US",
        "regionCode": "R01",
        "gencCode": None,
        "released": "2026-10-23",
        "share": "0.25",
        "unit": {"unitId": 8, "unit_description": "(1000 MT)"},
        "units": [{"unitId": 4, "unit_description": "(1000 HA)"}],
    }
    country = Country.model_validate(record)
    assert country.dump_upstream() == {
        "countryCode": "US",
        "regionCode": "R01",
        "gencCode": None,
        "released": "2026-10-23",
        "share": 0.25,
        "unit": {"unitId": 8, "unitDescription": "(1000 MT)"},
        "units": [{"unitId": 4, "unitDescription": "(1000 HA)"}],
    }
    assert list(country.dump_upstream()) == list(record)  # field order, no computed label


class Priced(UpstreamModel):
    label: str
    value: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_number(self) -> Decimal | None:
        return parse_decimal(self.value)


def test_computed_decimal_fields_serialise_as_json_numbers() -> None:
    priced = Priced(label="x", value="1,234.5")
    assert priced.value_number == Decimal("1234.5")
    dumped = priced.model_dump(mode="json")
    assert dumped == {"label": "x", "value": "1,234.5", "value_number": 1234.5}
    assert json.loads(priced.model_dump_json())["value_number"] == 1234.5
    assert Priced(label="x", value="(D)").model_dump(mode="json")["value_number"] is None
    assert priced.model_dump()["value_number"] == Decimal("1234.5")


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        ({"max_rows": 0}, "max_rows and max_bytes must be at least 1"),
        ({"max_bytes": 0}, "max_rows and max_bytes must be at least 1"),
        ({"note": ""}, "note must say how to see the rest"),
        ({"note": "   "}, "note must say how to see the rest"),
    ],
)
def test_result_cap_refuses_an_empty_bound_or_a_blank_note(
    arguments: dict[str, object], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        ResultCap(**arguments)  # type: ignore[arg-type]
