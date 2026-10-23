import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import Field, computed_field

from xippios.core.errors import ValidationError
from xippios.core.models import (
    REDACTED,
    Result,
    ResultMeta,
    UpstreamModel,
    is_credential_key,
    parse,
    parse_decimal,
    redact_credentials,
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


def test_upstream_model_populates_by_name() -> None:
    assert Series(series_id="b", value=1).series_id == "b"


def test_result_meta_defaults() -> None:
    meta = ResultMeta(source="example", endpoint="get_thing")
    assert meta.retrieved_at.tzinfo is not None
    assert meta.published_at is None
    assert meta.vintage is None
    assert meta.request == {}
    assert meta.total is None


def test_result_meta_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultMeta(source="x", endpoint="y", retrieved_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultMeta(source="x", endpoint="y", published_at=datetime(2026, 1, 1))


def test_result_meta_total_serialises_as_an_integer() -> None:
    meta = ResultMeta(source="cashctrl", endpoint="journal/list.json", total=1234)
    assert meta.total == 1234
    dumped = meta.model_dump(mode="json")
    assert dumped["total"] == 1234
    assert type(dumped["total"]) is int
    assert json.loads(meta.model_dump_json())["total"] == 1234
    assert ResultMeta(source="s", endpoint="e", total=0).total == 0
    assert ResultMeta(source="s", endpoint="e").model_dump(mode="json")["total"] is None


def test_result_meta_rejects_a_negative_total() -> None:
    with pytest.raises(ValueError, match="total must not be negative"):
        ResultMeta(source="s", endpoint="e", total=-1)


def test_result_meta_total_is_never_computed_from_data() -> None:
    rows = [Series(series_id=str(i), value=i) for i in range(3)]
    result = Result[list[Series]](data=rows, meta=ResultMeta(source="s", endpoint="e"))
    assert result.meta.total is None
    page = Result[list[Series]](data=rows, meta=ResultMeta(source="s", endpoint="e", total=40))
    assert page.meta.total == 40
    assert Result[list[Series]].model_validate(page.model_dump(mode="json")) == page


def test_result_envelope_round_trips() -> None:
    meta = ResultMeta(
        source="example",
        endpoint="get_thing",
        retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
        request={"id": 7},
    )
    result = Result[list[Series]](data=[Series(series_id="a", value=1)], meta=meta)
    dumped = result.model_dump(mode="json")
    assert dumped["meta"]["source"] == "example"
    assert dumped["data"][0]["series_id"] == "a"
    again = Result[list[Series]].model_validate(dumped)
    assert again == result


def test_parse_model_and_generic() -> None:
    one = parse(Series, {"seriesId": "a", "value": 1}, source="example", endpoint="e")
    assert one.series_id == "a"
    many = parse(list[Series], [{"seriesId": "a", "value": 1}], source="example", endpoint="e")
    assert many[0].value == 1.0


def test_parse_wraps_validation_error_with_raw() -> None:
    raw = {"seriesId": "a", "value": "not a number"}
    with pytest.raises(ValidationError) as info:
        parse(Series, raw, source="example", endpoint="get_thing")
    assert info.value.raw is raw
    assert info.value.source == "example"
    assert str(info.value).startswith("example get_thing: 1 validation error(s); first at value:")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("key", True), ("api_key", True), ("apikey", True), ("API_KEY", True), ("x-api-key", True),
        ("access_token", True), ("client_secret", True), ("password", True), ("auth", True),
        ("Authorization", True), ("signature", True), ("credentials", True), ("sort_key", True),
        ("keyword", False), ("author", False), ("commodity_desc", False), ("year", False),
        ("tokens_used", False), ("design", False),
    ],
)  # fmt: skip
def test_is_credential_key(name: str, expected: bool) -> None:
    assert is_credential_key(name) is expected


def test_redact_credentials_is_deep_and_copies() -> None:
    params = {"key": "SECRET", "year": 2024, "nested": {"token": "T", "ok": [{"secret": "S"}, 1]}}
    redacted = redact_credentials(params)
    assert redacted == {
        "key": REDACTED,
        "year": 2024,
        "nested": {"token": REDACTED, "ok": [{"secret": REDACTED}, 1]},
    }
    assert params["key"] == "SECRET"


def test_result_meta_never_carries_credentials() -> None:
    meta = ResultMeta(
        source="usda-nass", endpoint="api_GET", request={"key": "SECRET", "commodity_desc": "CORN"}
    )
    assert meta.request == {"key": REDACTED, "commodity_desc": "CORN"}
    assert "SECRET" not in meta.model_dump_json()


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
