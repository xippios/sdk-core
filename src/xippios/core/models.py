"""Result envelope, release metadata and the base for upstream payload models (conventions §4)."""

from datetime import UTC, datetime
from typing import Any

import pydantic
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from xippios.core.errors import ValidationError

__all__ = [
    "Result",
    "ResultMeta",
    "UpstreamModel",
    "parse",
    "utcnow",
]


class UpstreamModel(BaseModel):
    """Base for models that mirror an upstream payload field by field.

    Instances are frozen. Fields upstream adds later are ignored rather than rejected,
    and fields can be populated by name as well as by alias, so upstream ``camelCase``
    maps onto ``snake_case`` attributes without breaking construction in tests.
    """

    model_config = ConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ResultMeta(BaseModel):
    """Release metadata attached to every result.

    Attributes:
        source: Source slug, e.g. ``"usda-nass"``.
        endpoint: Upstream operation name, e.g. ``"api_GET"``.
        retrieved_at: When we fetched the data; timezone-aware UTC, defaults to now.
        published_at: Upstream publication or release time when known.
        vintage: Upstream release identifier when the source has one.
        request: The parameters used, for reproducibility.
    """

    source: str
    endpoint: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None
    vintage: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)

    @field_validator("retrieved_at", "published_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class Result[T](BaseModel):
    """What every task function returns: the data plus its release metadata."""

    data: T
    meta: ResultMeta


def parse[T](type_: type[T], raw: object, *, source: str, endpoint: str) -> T:
    """Validate an upstream payload, wrapping failures as ``ValidationError``.

    Args:
        type_: The target type: a model class or a generic such as ``list[Series]``.
        raw: The decoded upstream payload.
        source: Source slug, used in the error message.
        endpoint: Upstream operation name, used in the error message.

    Returns:
        The validated value.

    Raises:
        ValidationError: With the raw payload attached, when validation fails.
    """
    try:
        return TypeAdapter(type_).validate_python(raw)
    except pydantic.ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        message = (
            f"{source} {endpoint}: {exc.error_count()} validation error(s); "
            f"first at {location}: {first['msg']}"
        )
        raise ValidationError(message, raw=raw, source=source) from exc
