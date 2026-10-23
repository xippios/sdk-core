"""Result envelope, release metadata and the base for upstream payload models (conventions §4)."""

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Self

import pydantic
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    field_serializer,
    field_validator,
)

from xippios.core.errors import ValidationError

__all__ = [
    "REDACTED",
    "Result",
    "ResultMeta",
    "UpstreamModel",
    "is_credential_key",
    "parse",
    "parse_decimal",
    "redact_credentials",
    "utcnow",
]

REDACTED = "REDACTED"
"""What a credential-like value in ``ResultMeta.request`` is replaced with."""

_CREDENTIAL_KEY = re.compile(
    r"(?i)(?:^|[_-])"
    r"(?:api_?key|key|token|secret|password|passwd|auth|authorization|signature|credentials?)"
    r"(?:[_-]|$)"
)


def is_credential_key(name: str) -> bool:
    """True when a parameter name looks like it carries a credential (ADR-0005).

    Matches whole words separated by ``_`` or ``-``: ``key``, ``api_key``, ``x-api-key``,
    ``access_token``, ``client_secret``, ``sort_key`` all match; ``keyword`` does not.
    """
    return _CREDENTIAL_KEY.search(name) is not None


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_credentials(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def redact_credentials(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of ``mapping`` with credential-like keys set to ``REDACTED`` at any depth."""
    return {
        key: REDACTED if is_credential_key(key) else _redact_value(value)
        for key, value in mapping.items()
    }


def parse_decimal(text: str) -> Decimal | None:
    """A published figure as a number, or ``None`` when it is a code rather than a value.

    Thousands separators are removed (``"510,000"`` → ``510000``); anything that is not
    a number, such as a suppression code like ``"(D)"`` or an empty string, gives
    ``None``. Within-source hygiene only: the text is never reinterpreted.
    """
    try:
        return Decimal(text.replace(",", "").strip())
    except InvalidOperation:
        return None


def _as_json_number(value: Any, rendered: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list | tuple) and isinstance(rendered, list):
        return [
            float(item) if isinstance(item, Decimal) else out
            for item, out in zip(value, rendered, strict=True)
        ]
    return rendered


class UpstreamModel(BaseModel):
    """Base for models that mirror an upstream payload field by field.

    Instances are frozen. Fields upstream adds later are ignored rather than rejected,
    and fields can be populated by name as well as by alias, so upstream ``camelCase``
    maps onto ``snake_case`` attributes without breaking construction in tests.
    ``Decimal`` fields serialise as JSON numbers in both adapters (ADR-0008); Python
    keeps the ``Decimal``.
    """

    model_config = ConfigDict(
        frozen=True, extra="ignore", validate_by_name=True, validate_by_alias=True
    )

    @field_serializer("*", mode="wrap", when_used="json")
    def _decimal_as_json_number(self, value: Any, handler: SerializerFunctionWrapHandler) -> Any:
        return _as_json_number(value, handler(value))

    @classmethod
    def project(cls, source: BaseModel, **overrides: Any) -> Self:
        """Build this model from another model's same-named fields.

        A projection keeps a subset of the source's columns under their upstream names
        (ADR-0008). ``overrides`` are for parsing only, e.g. ``value=parse_decimal(...)``;
        every other field is copied from ``source`` unchanged.

        Args:
            source: The record to project, usually the full upstream record.
            **overrides: Values for fields that are parsed rather than copied.

        Raises:
            TypeError: When a field of this model is neither on ``source`` nor overridden.
        """
        missing = [
            name for name in cls.model_fields if name not in overrides and not hasattr(source, name)
        ]
        if missing:
            raise TypeError(
                f"{cls.__name__}.project: {type(source).__name__} has no field "
                + ", ".join(missing)
            )
        copied = {name: getattr(source, name) for name in cls.model_fields if name not in overrides}
        return cls(**copied, **overrides)


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
        request: The parameters used, for reproducibility. Credential-like keys are
            redacted at construction (ADR-0005); record the variable name, never the value.
        total: Upstream's count of the records matching the request, when the source
            reports one; ``None`` when it does not or the count is unknown. Set only from
            what upstream reports, never computed from ``len(data)`` (ADR-0012).
        tenant: The tenant the data came from, by name, e.g. ``"acme"``; never a
            credential, nor a host or another value of the tenant's (conventions §7).
            ``None`` for a single-tenant source and for the list of tenant names.
    """

    source: str
    endpoint: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None
    vintage: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    total: int | None = None
    tenant: str | None = None

    @field_validator("retrieved_at", "published_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("request")
    @classmethod
    def _no_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        return redact_credentials(value)

    @field_validator("total")
    @classmethod
    def _not_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("total must not be negative")
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
