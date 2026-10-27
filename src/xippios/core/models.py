"""Result envelope, release metadata and the base for upstream payload models (conventions §4)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Self

import pydantic
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo

from xippios.core.errors import ValidationError
from xippios.core.redaction import REDACTED, redact_credentials

__all__ = [
    "REDACTED",
    "Result",
    "ResultCap",
    "ResultMeta",
    "UpstreamModel",
    "parse",
    "parse_decimal",
    "utcnow",
]


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


def _upstream_name(name: str, info: FieldInfo) -> str:
    """The name upstream gives a field: its alias for output, else for input, else its own."""
    if info.serialization_alias is not None:
        return info.serialization_alias
    alias = info.validation_alias
    if isinstance(alias, AliasChoices):
        alias = alias.choices[0]
    return alias if isinstance(alias, str) else name


def _upstream_value(value: Any, dumped: Any) -> Any:
    """``dumped`` with a nested ``UpstreamModel``, alone or in a list, under upstream's names."""
    if isinstance(value, UpstreamModel):
        return value.dump_upstream()
    if isinstance(value, list | tuple) and isinstance(dumped, list):
        return [_upstream_value(item, out) for item, out in zip(value, dumped, strict=True)]
    return dumped


class UpstreamModel(BaseModel):
    """Base for models that mirror an upstream payload field by field.

    Instances are frozen. Fields upstream adds later are ignored rather than rejected,
    and fields can be populated by name as well as by alias, so upstream ``camelCase``
    maps onto ``snake_case`` attributes without breaking construction in tests.
    ``Decimal`` fields serialise as JSON numbers in both adapters (ADR-0008); Python
    keeps the ``Decimal``. ``dump_upstream`` gives the record back under upstream's
    names, for a packaged reference file.
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

    def dump_upstream(self) -> dict[str, Any]:
        """This record as JSON values under upstream's field names, in field order.

        What a refresh script writes into a packaged reference file (conventions §3):
        ``model_dump(mode="json")``, a ``Decimal`` as a number and a date as ISO text,
        with each field under the name upstream gives it: its ``serialization_alias``
        when set, else its ``validation_alias`` when that is a string, else the first
        choice of an ``AliasChoices`` when that is a string, else the field's own name.
        ``Field(alias="seriesId")`` sets the first two, so ``series_id`` comes back as
        ``"seriesId"``. A nested ``UpstreamModel``, alone or in a list or tuple, is
        dumped the same way; one inside a mapping keeps the field names
        ``model_dump`` gives it. A computed field is the package's, not upstream's, and
        is left out, as is a field excluded from dumping.

        The ``serialization_alias`` wins over the validation alias, and the model reads
        by alias or by name: a field with a ``serialization_alias`` and no validation
        alias of the same name writes a key the model cannot read back:
        ``PackagedList.parse`` refuses the record, or the field takes its default. A
        model whose records are packaged names the upstream field with
        ``Field(alias=...)`` or a ``validation_alias``.

        Returns:
            E.g. ``{"seriesId": "CORN_YIELD", "value": 177.3}``.
        """
        dumped = self.model_dump(mode="json")
        return {
            _upstream_name(name, info): _upstream_value(getattr(self, name), dumped[name])
            for name, info in type(self).model_fields.items()
            if name in dumped
        }


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ResultMeta(BaseModel):
    """Release metadata attached to every result (conventions §4).

    A field the model does not define is refused at construction, never dropped
    silently: a misspelt ``totl=`` is an error, not a lost count.

    Attributes:
        source: Source slug, e.g. ``"usda-nass"``.
        endpoint: Upstream operation name, e.g. ``"api_GET"``; for a packaged answer the
            operation the list came from (ADR-0022), as ``PackagedList.meta`` sets it.
        retrieved_at: When we fetched the data; timezone-aware UTC, defaults to now. A
            cache hit's is the time its entry was stored (``AsyncClient.get_answer``), a
            packaged answer's the time the list was fetched (ADR-0022, rule 1).
        published_at: Upstream publication or release time when known, timezone-aware;
            naive only with ``published_at_naive`` set.
        published_at_naive: ``True`` when upstream printed ``published_at`` without a
            zone (FAS: ``2026-10-06T08:00:00``): the value is stored as given, no zone
            attached, upstream's text and not comparable across sources (ADR-0022,
            rule 2). Set only with a naive ``published_at``.
        vintage: Upstream release identifier when the source has one, as upstream names
            it; never a fetch date (ADR-0022, rule 1).
        request: The parameters sent, for reproducibility. A top-level parameter whose
            value is ``None``, one the caller left out, is dropped at construction
            (ADR-0022, rule 3); a ``None`` inside a nested mapping is kept as given. The
            value of every key that names a credential, at any depth, is ``REDACTED``
            by the one rule of ``xippios.core.redaction`` (ADR-0005; ``key`` only where
            a ``QueryKeyAuth`` sends it, ADR-0019); record the variable name, never the
            value.
        total: Upstream's count of the records matching the request, when the source
            reports one; ``None`` when it does not or the count is unknown. Set only from
            what upstream reports, never computed from ``len(data)`` (ADR-0012).
        tenant: The tenant the data came from, by name, e.g. ``"acme"``; never a
            credential, nor a host or another value of the tenant's (conventions §7).
            ``None`` for a single-tenant source and for the list of tenant names.

    Raises:
        pydantic.ValidationError: A field the model does not define; a naive
            ``retrieved_at``; a naive ``published_at`` without ``published_at_naive``,
            or the flag set with an aware ``published_at`` or none; a negative
            ``total``.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    endpoint: str
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None
    published_at_naive: bool = False
    vintage: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)
    total: int | None = None
    tenant: str | None = None

    @field_validator("retrieved_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _published_at_as_upstream_printed_it(self) -> Self:
        naive = self.published_at is not None and self.published_at.tzinfo is None
        if naive and not self.published_at_naive:
            raise ValueError(
                "datetime must be timezone-aware: published_at is naive; a time upstream "
                "printed without a zone takes published_at_naive=True"
            )
        if self.published_at_naive and not naive:
            raise ValueError(
                "published_at_naive says upstream printed published_at without a zone, but "
                + ("published_at carries one" if self.published_at else "published_at is None")
            )
        return self

    @field_validator("request")
    @classmethod
    def _sent_and_no_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        return redact_credentials({name: item for name, item in value.items() if item is not None})

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


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultCap:
    """Limits for one tool result, and what to tell the agent when they cut it (conventions §8).

    The defaults are the family's: 200 rows or 64 KB. A reference tool whose whole list
    an agent needs gets a cap of its own, through ``caps=`` of ``register_tasks`` or
    ``build_server`` (ADR-0016), with the rows and bytes the source judges it needs; a
    byte bound above the default is a deliberate choice for that tool. It lives here, not
    in ``xippios.core.mcp``, so a source's ``tasks.py`` can declare its ``MCP_CAPS``
    without the ``mcp`` extra; ``xippios.core.mcp.cap_result`` applies it.

    Attributes:
        max_rows: Most items of a list result that are returned.
        max_bytes: Bytes of JSON text, encoded as UTF-8, a soft bound: it bounds the
            rows and the preview, and the envelope and the note can add to it (see
            ``cap_result``).
        note: The text after the counts when the cap cuts a result, used verbatim, e.g.
            ``"filter by period or by reporter to see the rest"`` for a tool that has
            those filters. ``None`` says ``"narrow the query to see the rest"``, which
            promises no filter the tool may lack.

    Raises:
        ValueError: ``max_rows`` or ``max_bytes`` is below 1, or ``note`` is blank.
    """

    max_rows: int = 200
    max_bytes: int = 65_536
    note: str | None = None

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.max_bytes < 1:
            raise ValueError("max_rows and max_bytes must be at least 1")
        if self.note is not None and not self.note.strip():
            raise ValueError("note must say how to see the rest; None keeps the default")


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
