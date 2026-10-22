from datetime import UTC, datetime

import pytest
from pydantic import Field

from xippios.core.errors import ValidationError
from xippios.core.models import (
    REDACTED,
    Result,
    ResultMeta,
    UpstreamModel,
    is_credential_key,
    parse,
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


def test_result_meta_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultMeta(source="x", endpoint="y", retrieved_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        ResultMeta(source="x", endpoint="y", published_at=datetime(2026, 1, 1))


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
