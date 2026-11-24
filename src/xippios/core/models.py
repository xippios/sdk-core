"""Result envelope, release metadata and the base for upstream payload models (conventions §4)."""

import functools
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Literal, Protocol, Self, runtime_checkable

import pydantic
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo

from xippios.core.errors import ValidationError, _raise
from xippios.core.redaction import REDACTED, redact_credentials

__all__ = [
    "REDACTED",
    "NamedBy",
    "Result",
    "ResultCap",
    "ResultMeta",
    "UpstreamModel",
    "newer_than",
    "parse",
    "parse_decimal",
    "utcnow",
]


def parse_decimal(text: str) -> Decimal | None:
    """A published figure as a number, or ``None`` when it is a code rather than a value.

    It reads a comma between thousands and a point before decimals: the commas are
    removed (``"510,000"`` → ``510000``, ``"1,234.5"`` → ``1234.5``). Anything that is not
    a finite number, such as a code in place of a withheld value, an empty string,
    ``"NaN"`` or ``"Infinity"``, gives ``None``. Within-source hygiene only: the text is
    never reinterpreted.
    """
    try:
        number = Decimal(text.replace(",", "").strip())
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _json_number(value: Decimal) -> int | float:
    """``value`` as JSON carries it: an integer without fractional digits, else a number.

    Read from the exponent, never from the value, so ``Decimal("16217")`` is ``16217`` and
    upstream's ``Decimal("16217.0")`` keeps its digit as ``16217.0`` (ADR-0067, decision 10).
    """
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent >= 0:  # a NaN's or an infinity's is a letter
        return int(value)
    return float(value)


def _as_json_number(value: Any, rendered: Any) -> Any:
    if isinstance(value, Decimal):
        return _json_number(value)
    if isinstance(value, list | tuple) and isinstance(rendered, list):
        return [
            _json_number(item) if isinstance(item, Decimal) else out
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
    ``Decimal`` fields serialise as JSON numbers in both adapters (ADR-0031), one without
    fractional digits as an integer, ``16217`` and not ``16217.0`` (ADR-0067, decision 10);
    Python keeps the ``Decimal``. ``dump_upstream`` gives the record back under upstream's
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
        (ADR-0031). ``overrides`` are for parsing only, e.g. ``value=parse_decimal(...)``;
        every other field is copied from ``source`` unchanged.

        Args:
            source: The record to project, usually the full upstream record.
            **overrides: Values for fields that are parsed rather than copied.

        Raises:
            TypeError: When a field of this model is neither on ``source`` nor overridden.
            ValidationError: When a copied or overridden value does not fit this model;
                raised as ``parse`` raises it, its text naming the location, type and
                message, the values on ``raw``.
        """
        missing = [
            name for name in cls.model_fields if name not in overrides and not hasattr(source, name)
        ]
        if missing:
            raise TypeError(
                f"{cls.__name__}.project: {type(source).__name__} has no field "
                + ", ".join(missing)
            )
        values = {name: getattr(source, name) for name in cls.model_fields if name not in overrides}
        values |= overrides
        try:
            return cls(**values)
        except pydantic.ValidationError as exc:
            message = f"{cls.__name__}.project: {_validation_text(exc)}"
            _raise(ValidationError(message, raw=values))

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


class _Listed(Protocol):
    @property
    def fetched(self) -> datetime: ...


@runtime_checkable
class _Codes(Protocol):
    """What the names of a record's codes read of their list: a ``PackagedCodes`` (ADR-0045).

    ``xippios.core.reference`` builds it above this module, so it is read by its members.
    """

    @property
    def list_name(self) -> str: ...

    @property
    def integer(self) -> bool: ...

    @property
    def packaged(self) -> _Listed: ...

    def name_of(self, value: object) -> str | None: ...


@dataclass(frozen=True, slots=True)
class NamedBy:
    """Where the names of a record's codes come from (conventions §4, ADR-0067, decision 6).

    The mark of a code field of a record's model, in its annotation: the packaged list that
    names the field's codes, ``PackagedList.codes(...)`` (ADR-0045), or the name of the field
    of the same record in which upstream sends the code's name::

        REGIONS = PackagedList.load("xippios.example", "regions").codes(
            "regionCode", "regionName"
        )


        class Row(UpstreamModel):
            region_code: Annotated[str, NamedBy(REGIONS)] = Field(validation_alias="regionCode")
            item_code: Annotated[int, NamedBy("item")] = Field(validation_alias="itemCode")
            item: str

    With a list, every ``Result`` whose data holds the record names each code of the field in
    ``meta.names`` under the field's name, so every task that returns the model is named, and a
    code that the list lacks is left out of the map and said in a note of ``meta.notes``. With a
    field, the name stands on the record beside its code, in upstream's words, and ``meta.names``
    takes nothing for it. A field holds one code, text or an integer, or a list of them, and
    ``None`` holds none.

    Attributes:
        by: The list, a ``PackagedCodes``, e.g. ``REGIONS``; or the name of the field that holds
            the code's name, e.g. ``"item"``.

    Raises:
        TypeError: ``by`` is neither a ``PackagedCodes`` nor a field's name.
    """

    by: _Codes | str

    def __post_init__(self) -> None:
        by: object = self.by
        if isinstance(by, str) and by.isidentifier():
            return
        if not isinstance(by, str) and isinstance(by, _Codes):
            return
        shown = repr(by) if isinstance(by, str) else _a(type(by).__name__)
        raise TypeError(
            "NamedBy takes the list that names the codes, PackagedList.codes(...), or the name "
            f"of the field beside the code that holds its name, and got {shown}"
        )


def _a(word: str) -> str:
    return f"{'an' if word[:1].lower() in 'aeiou' else 'a'} {word}"


def _bare(annotation: Any) -> Any:
    """The annotation without the ``Annotated`` around it."""
    while typing.get_origin(annotation) is typing.Annotated:
        annotation = typing.get_args(annotation)[0]
    return annotation


def _kinds(annotation: Any) -> list[Any]:
    """The kinds an annotation allows besides ``None``: ``int | None`` gives ``[int]``."""
    annotation = _bare(annotation)
    if typing.get_origin(annotation) in (typing.Union, type(int | str)):
        return [_bare(kind) for kind in typing.get_args(annotation) if kind is not type(None)]
    return [annotation]


def _holds_text(annotation: Any) -> bool:
    """A field of ``str`` or a subclass of it, ``None`` allowed beside it."""
    kinds = _kinds(annotation)
    return bool(kinds) and all(isinstance(kind, type) and issubclass(kind, str) for kind in kinds)


_COLLECTIONS = (list, tuple, set, frozenset, Sequence, AbstractSet)


def _holds_codes(annotation: Any) -> bool:
    """A field of text or integer codes, one or a list of them, ``None`` allowed beside it."""
    kinds: list[Any] = []
    for kind in _kinds(annotation):
        if typing.get_origin(kind) in _COLLECTIONS:
            kinds += [_bare(item) for item in typing.get_args(kind) if item is not Ellipsis]
        else:
            kinds.append(kind)
    return bool(kinds) and all(
        isinstance(kind, type) and issubclass(kind, str | int) and not issubclass(kind, bool)
        for kind in kinds
    )


def _reaches_model(annotation: Any) -> bool:
    """Whether an annotation names a pydantic model, alone, in a union or in a container."""
    annotation = _bare(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return True
    return any(_reaches_model(argument) for argument in typing.get_args(annotation))


_UNREAD = (
    "carries NamedBy inside its type, where no answer reads it: mark the field, "
    "Annotated[str | None, NamedBy(...)] or Annotated[str, NamedBy(...)] | None"
)


def _marks_in(annotation: Any) -> bool:
    """Whether a ``NamedBy`` stands anywhere in ``annotation``, at any depth."""
    if typing.get_origin(annotation) is typing.Annotated:
        if any(isinstance(mark, NamedBy) for mark in annotation.__metadata__):
            return True
        return _marks_in(typing.get_args(annotation)[0])
    return any(_marks_in(argument) for argument in typing.get_args(annotation))


def _field_marks(info: FieldInfo) -> tuple[list[NamedBy], bool]:
    """The marks of a field that a ``Result`` reads, and whether another stands unread.

    A mark reads on the field, ``Annotated[str | None, NamedBy(...)]``, whose metadata pydantic
    keeps, and on an optional code, ``Annotated[str, NamedBy(...)] | None`` or ``Optional`` of
    it, the plain spelling. A mark anywhere else, on a list's items or in a union of codes,
    would name nothing (https://github.com/xippios/sdk-core/pull/537, finding 1).
    """
    marks = [mark for mark in info.metadata if isinstance(mark, NamedBy)]
    inside: Any = info.annotation
    if typing.get_origin(inside) in (typing.Union, type(int | str)):
        kinds = [kind for kind in typing.get_args(inside) if kind is not type(None)]
        if len(kinds) == 1 and typing.get_origin(kinds[0]) is typing.Annotated:
            marks += [mark for mark in kinds[0].__metadata__ if isinstance(mark, NamedBy)]
            inside = typing.get_args(kinds[0])[0]
    return marks, _marks_in(inside)


def _named_by(model: type[BaseModel]) -> tuple[list[tuple[str, NamedBy]], list[str]]:
    """Each field of ``model`` that a ``NamedBy`` marks, with it, and what is wrong with them.

    A field marked twice, a mark that no answer reads, a field that holds no code, and a name
    that is no other field of the model or one that holds no text are wrong (ADR-0067,
    decision 6); each problem is one text that names the model and the field.
    """
    marked: list[tuple[str, NamedBy]] = []
    problems: list[str] = []
    fields = model.model_fields
    for field, info in fields.items():
        marks, unread = _field_marks(info)
        where = f"{model.__name__}.{field}"
        if unread:
            problems.append(f"{where} {_UNREAD}")
            continue
        if not marks:
            continue
        if len(marks) > 1:
            problems.append(f"{where} is marked by NamedBy twice; keep one")
            continue
        if not _holds_codes(info.annotation):
            problems.append(
                f"{where} holds {_shown(info.annotation)}, no code: NamedBy marks a field of "
                "text or integer codes, one or a list of them"
            )
            continue
        by = marks[0].by
        if isinstance(by, str):
            if by == field or by not in fields:
                problems.append(f"{where} is named by {by}, which is no other field of the model")
                continue
            if not _holds_text(fields[by].annotation):
                problems.append(
                    f"{where} is named by {by}, which holds "
                    f"{_shown(fields[by].annotation)}, not text"
                )
                continue
        marked.append((field, marks[0]))
    return marked, problems


def _shown(annotation: Any) -> str:
    bare = _bare(annotation)
    return bare.__name__ if isinstance(bare, type) else repr(bare)


@dataclass(frozen=True, slots=True)
class _Reading:
    """What naming the codes of a record reads of its model: built once per model."""

    lists: tuple[tuple[str, _Codes], ...]
    """The fields named by a packaged list, each with its list."""
    nested: tuple[str, ...]
    """The fields whose annotation names a model, which can hold more records."""


@functools.cache
def _reading(model: type[BaseModel]) -> _Reading:
    """How the codes of ``model``'s records are named, or a ``TypeError`` for a wrong mark."""
    marked, problems = _named_by(model)
    if problems:
        raise TypeError("; ".join(problems) + " (conventions §4, ADR-0067, decision 6)")
    return _Reading(
        lists=tuple((field, mark.by) for field, mark in marked if not isinstance(mark.by, str)),
        nested=tuple(
            field for field, info in model.model_fields.items() if _reaches_model(info.annotation)
        ),
    )


def _codes_in(value: object) -> list[object]:
    """The codes ``value`` holds: none for ``None``, one for a text, a collection's members."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence | AbstractSet) and not isinstance(value, bytes | bytearray):
        return [code for member in value for code in _codes_in(member)]
    return [value]


def _code(member: object, integer: bool) -> tuple[str, object]:
    """A code's text as given and the value its list compares, digits and integers crossed.

    A text of digits reads as the integer for a list of integer codes, and an integer as its
    text for a list of text codes, as an upstream or a caller may send either; an enum member
    reads by its value.
    """
    plain = member.value if isinstance(member, Enum) else member
    if integer and isinstance(plain, str) and plain.isascii() and plain.isdigit():
        return plain, int(plain)
    if not integer and isinstance(plain, int) and not isinstance(plain, bool):
        return str(plain), str(plain)
    return str(plain), plain


def _and(words: Sequence[str], last: str = "and") -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    if len(words) < 2:
        return "".join(words)
    return f"{', '.join(words[:-1])} {last} {words[-1]}"


class _Names:
    """The names of the codes of an answer's records, and the codes their lists lack."""

    def __init__(self) -> None:
        self.names: dict[str, dict[str, str]] = {}
        # Each field with its list, then the codes that the list lacks in order, since two models
        # of one answer may mark fields of one name with two lists.
        self.lacking: dict[tuple[str, _Codes], dict[str, None]] = {}

    def read(self, value: object) -> None:
        """Name the codes of every record that ``value`` holds, at any depth."""
        if isinstance(value, BaseModel):
            reading = _reading(type(value))
            for field, listed in reading.lists:
                for member in _codes_in(getattr(value, field)):
                    self._name(field, listed, member)
            for field in reading.nested:
                self.read(getattr(value, field))
        elif isinstance(value, Mapping):
            for item in value.values():
                self.read(item)
        elif isinstance(value, list | tuple | AbstractSet):
            for item in value:
                self.read(item)

    def _name(self, field: str, listed: _Codes, member: object) -> None:
        text, compared = _code(member, listed.integer)
        name = listed.name_of(compared)
        if name is None:
            self.lacking.setdefault((field, listed), {})[text] = None
        else:
            self.names.setdefault(field, {}).setdefault(text, " ".join(name.split()) or text)

    def notes(self) -> list[str]:
        """One sentence per field and list that lacks a code (ADR-0067, decision 7).

        A code that another list names under the field's name, as the answer is read whole,
        stands in ``meta.names`` and is no gap.
        """
        notes = []
        for (field, listed), texts in self.lacking.items():
            named = self.names.get(field, {})
            codes = [code for code in texts if code not in named]
            if not codes:
                continue
            notes.append(
                f"The packaged {listed.list_name} list (fetched "
                f"{listed.packaged.fetched:%Y-%m-%d}) holds no name for {field} "
                f"{_and(codes, 'or')} of this answer, so meta.names leaves "
                f"{'it' if len(codes) == 1 else 'them'} out."
            )
        return notes


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class ResultMeta(BaseModel):
    """Release metadata attached to every result (conventions §4).

    A field the model does not define is refused at construction, never dropped
    silently: a misspelt ``totl=`` is an error, not a lost count.

    Attributes:
        source: Source slug, e.g. ``"example"``.
        endpoint: Upstream operation name, e.g. ``"getSeries"``; for a packaged answer the
            operation the list came from (ADR-0041), as ``PackagedList.meta`` sets it.
        retrieved_at: When we fetched the data; timezone-aware UTC, defaults to now. A
            cache hit's is the time its entry was stored (``AsyncClient.get_answer``), a
            packaged answer's the time the list was fetched (ADR-0041, decision 1).
        published_at: Upstream publication or release time when known, timezone-aware;
            naive only with ``published_at_naive`` set.
        published_at_naive: ``True`` when upstream printed ``published_at`` without a
            zone (e.g. ``2026-10-06T08:00:00``): the value is stored as given, no zone
            attached, upstream's text and not comparable across sources (ADR-0041,
            decision 2). Set only with a naive ``published_at``.
        vintage: Upstream release identifier when the source has one, as upstream names
            it; never a fetch date (ADR-0041, decision 1).
        request: The parameters sent, for reproducibility. A top-level parameter whose
            value is ``None``, one the caller left out, is dropped at construction
            (ADR-0041, decision 3); a ``None`` inside a nested mapping is kept as given. The
            value of every key that names a credential, at any depth, is ``REDACTED``
            by the one rule of ``xippios.core.redaction`` for ``source`` (ADR-0030;
            ``key`` only where the source's query ``KeyAuth`` sends it, ADR-0040; a
            ``token`` name the source declares data, ``next_token`` say, kept as sent;
            another source's names change nothing), and so is each credential in the
            query of a link, a signed file link's signature say, as ``scrub_url``
            writes it; record the variable name, never the value.
        total: Upstream's count of the records matching the request, when the source
            reports one; ``None`` when it does not or the count is unknown. Set only from
            what upstream reports, never computed from ``len(data)`` (ADR-0034).
        tenant: The tenant the data came from, by name, e.g. ``"acme"``; never a
            credential, nor a host or another value of the tenant's (conventions §7).
            ``None`` for a single-tenant source and for the list of tenant names.
        names: Each code parameter of the request, and each code field of the answer's
            records that its model names by a packaged list, to its codes and the names the
            list holds, e.g. ``{"country_code": {"CN": "Comoros"}}``: a request's code under
            its text as the caller gave it, which ``names_codes`` fills, and a record's under
            its text as upstream sent it, which the ``Result`` fills from the model's
            ``NamedBy`` (ADR-0067, decisions 2, 3 and 6). Empty for an answer without such a
            code, and left out of a dump while it is empty.
        notes: One sentence per fact that the task says about its answer and that neither
            a record nor another field states, e.g. the periods a series passed over, or a
            record's code that its list does not name (ADR-0067, decisions 1 and 7). Empty
            by default, and left out of a dump while it is empty, so an answer without a
            note dumps as it did before the field.

    Raises:
        pydantic.ValidationError: A field the model does not define; a naive
            ``retrieved_at``; a naive ``published_at`` without ``published_at_naive``,
            or the flag set with an aware ``published_at`` or none; a negative
            ``total``; a blank note.
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
    names: dict[str, dict[str, str]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    # No return annotation, on purpose: pydantic then reads the schema of a dump from the
    # fields, ``names`` and ``notes`` optional properties, where ``-> Any`` would make it a
    # dump of any shape, and an HTTP route's response and an MCP tool's output read that schema.
    @model_serializer(mode="wrap")
    def _empty_lists_left_out(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]  # noqa: ANN202
        """The dump, ``names`` and ``notes`` left out while empty (ADR-0067, decisions 1, 2)."""
        dumped = handler(self)
        if isinstance(dumped, dict):
            for field in ("names", "notes"):
                if not getattr(self, field):
                    dumped.pop(field, None)
        return dumped

    @field_validator("notes")
    @classmethod
    def _sentences(cls, value: list[str]) -> list[str]:
        if any(not note.strip() for note in value):
            raise ValueError("a note is a sentence about the answer, never blank")
        return value

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
    def _sent_and_no_credentials(
        cls, value: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        # The source's own names, never another's (ADR-0040, decision 6, amendment
        # 2026-11-24); ``source`` is validated first, as it is declared first.
        source = info.data.get("source")
        return redact_credentials(
            {name: item for name, item in value.items() if item is not None},
            source=source if isinstance(source, str) else None,
        )

    @field_validator("total")
    @classmethod
    def _not_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("total must not be negative")
        return value


class _Ordered(Protocol):
    """A release that ``>`` compares: a ``datetime``, or a ``(year, month)`` tuple say."""

    def __gt__(self, other: Any, /) -> bool: ...


def newer_than[T, K: _Ordered](
    since: str | None,
    items: Iterable[T],
    *,
    released: Callable[[T], K | None],
    read: Callable[[str], K],
) -> list[T]:
    """The items released strictly later than ``since``, a vintage taken back (ADR-0052).

    The filter of a parameter that takes the ``meta.vintage`` of an earlier call to return
    only what changed since (conventions §4; ADR-0041, decision 2). ``read`` reads the text
    as the source's ``vintage`` wrote it, and ``released`` gives each item's release in the
    same form, so the two compare: a ``datetime`` for a release time printed without a zone,
    or a release month read into ``(year, month)`` say. Each source hands its own reader, since
    core ships none (ADR-0059, decision 4). An equal release is no newer.

    It filters and nothing else: the task sets ``meta.vintage`` and ``meta.published_at``
    from the whole upstream answer, so an answer with nothing newer still names the newest
    release, the marker to store for the next call. The task also calls ``read`` on
    ``since`` before its request, so an unreadable text is refused before the call
    (conventions §5).

    Args:
        since: The ``meta.vintage`` text of an earlier call, as the caller gave it, e.g.
            ``"2026-10-22T08:30:42.67"``; ``None`` keeps every item.
        items: The items of the whole answer, in upstream's order; any iterable, read once.
        released: An item's release, or ``None`` where upstream gives the item none. Such an
            item is kept: it cannot be shown to be no newer, and dropping it would hide it
            from every later call.
        read: The source's reader of ``since``, which raises ``InvalidRequestError`` for a
            text it cannot read; called once, before the first item, and never for ``None``.

    Returns:
        A new list of the items released strictly later than ``since`` or without a release,
        in their order; every item when ``since`` is ``None``.

    Raises:
        InvalidRequestError: As ``read`` raises it, for a ``since`` it cannot read, whether
            the answer holds items or none.
        TypeError: A release does not compare with what ``read`` gave, a month against a
            time or a time with a zone against one without: a fault of the source's code,
            not of the caller's argument, so no taxonomy error (conventions §5). The message
            names both values and their types. mypy accepts such a pair.
    """
    if since is None:
        return list(items)
    after = read(since)
    kept: list[T] = []
    for item in items:
        release = released(item)
        if release is None or _later(release, after):
            kept.append(item)
    return kept


def _later[K: _Ordered](release: K, after: K) -> bool:
    """``release > after``, or a ``TypeError`` that names both where they do not compare."""
    try:
        return release > after
    except TypeError as exc:
        raise TypeError(
            f"newer_than compares each release with read(since): released gave {release!r}, a "
            f"{type(release).__name__}, and read gave {after!r}, a {type(after).__name__}, "
            f"which do not compare ({exc}). Hand it a reader that reads since into the form "
            "released gives."
        ) from exc


class Result[T](BaseModel):
    """What every task function returns: the data plus its release metadata.

    Built or validated, it names the codes of the records its data holds where their model
    marks a code field with ``NamedBy(<list>)``: each code with its name in ``meta.names``
    under the field's name, beside the names already there, and one note in ``meta.notes``
    per field for the codes its list lacks (ADR-0067, decisions 6 and 7). A record is read
    in the data, in a list, a tuple, a set or a mapping's values, and in the fields of a
    record whose annotation names a model. ``meta`` is then a new ``ResultMeta``, so the
    object the task passed is not changed.

    Raises:
        TypeError: A model of the data marks a field wrongly with ``NamedBy``.
    """

    data: T
    meta: ResultMeta

    @model_validator(mode="after")
    def _names_of_the_records(self) -> Self:
        found = _Names()
        found.read(self.data)
        notes = [note for note in found.notes() if note not in self.meta.notes]
        names = {
            field: {**codes, **self.meta.names.get(field, {})}
            for field, codes in found.names.items()
        }
        if not notes and all(self.meta.names.get(field) == codes for field, codes in names.items()):
            return self
        fields = {field: getattr(self.meta, field) for field in type(self.meta).model_fields}
        fields["names"] = {**self.meta.names, **names}
        fields["notes"] = [*self.meta.notes, *notes]
        self.meta = type(self.meta)(**fields)
        return self


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultCap:
    """Limits for one tool result, and what to tell the agent when they cut it (conventions §8).

    The defaults are the family's: 200 rows or 64 KB. A reference tool whose whole list
    an agent needs gets a cap of its own, through the ``caps`` of its ``ToolSet``
    (ADR-0038, ADR-0063), with the rows and bytes the source judges it needs; a
    byte bound above the default is a deliberate choice for that tool. It lives here, not
    in ``xippios.core.mcp``, so a source's ``tasks.py`` can declare its ``MCP_CAPS``
    without the ``mcp`` extra; ``xippios.core.mcp.cap_result`` applies it.

    Attributes:
        max_rows: Most rows of a result that are returned: the items of a list result,
            or those of the one list a model holds once the model passes ``max_bytes``.
        max_bytes: Bytes of JSON text, encoded as UTF-8, a soft bound: it bounds the
            rows and the preview, and the envelope and the note can add to it (see
            ``cap_result``).
        note: The text after the counts when the cap cuts a result, used verbatim, e.g.
            ``"filter by period or by reporter to see the rest"`` for a tool that has
            those filters. ``None`` says ``"narrow the query to see the rest"``, which
            promises no filter the tool may lack.
        paged: ``True`` gives the tool the adapter's own argument ``offset``, the rows of
            the answer already shown: the task runs again, the adapter cuts its rows from
            there, and the note of a cut answer ends with the call for the next rows
            (ADR-0047). For a read tool whose second run costs upstream nothing, a
            packaged table or an answer the response cache holds (ADR-0061, decision 9),
            never a write tool, which registration refuses; ``False``, the default,
            leaves the tool and its notes as they are.
        keep: ``"first"``, the default, keeps the first rows of a cut answer, ``"last"``
            the last, the newest of a series ordered oldest first; ``offset`` then counts
            from the last row, so a continuation walks to older rows (ADR-0047).

    Raises:
        ValueError: ``max_rows`` or ``max_bytes`` is below 1, ``note`` is blank, or
            ``keep`` is neither ``"first"`` nor ``"last"``.
    """

    max_rows: int = 200
    max_bytes: int = 65_536
    note: str | None = None
    paged: bool = False
    keep: Literal["first", "last"] = "first"

    def __post_init__(self) -> None:
        if self.max_rows < 1 or self.max_bytes < 1:
            raise ValueError("max_rows and max_bytes must be at least 1")
        if self.note is not None and not self.note.strip():
            raise ValueError("note must say how to see the rest; None keeps the default")
        if self.keep not in ("first", "last"):
            raise ValueError(f"keep must be 'first' or 'last', got {self.keep!r}")


def _validation_text(exc: pydantic.ValidationError) -> str:
    """``<n> validation error(s); first at <loc> (<type>): <msg>``, never an input value.

    pydantic's own text quotes each failing value, and the containing object around a
    missing field; this folds in the location, the error type and the message only, so a
    ``ValidationError`` raised ``from None`` carries no upstream data in its text (queue
    row 42).
    """
    first = exc.errors(include_url=False, include_context=False, include_input=False)[0]
    location = ".".join(str(part) for part in first["loc"]) or "<root>"
    return (
        f"{exc.error_count()} validation error(s); first at {location} ({first['type']}): "
        f"{first['msg']}"
    )


def parse[T](type_: type[T], raw: object, *, source: str, endpoint: str) -> T:
    """Validate an upstream payload, wrapping failures as ``ValidationError``.

    The error's text names the first failure's location, type and message and never a
    value; the payload stays on ``raw`` for a debugger, out of ``str()`` and ``repr()``.
    It is raised ``from None``, so no chained pydantic error quotes the values, and from a
    private helper's frame, so under pytest's default ``--tb=auto`` this function's frame
    is printed short, without its arguments; ``--tb=long`` and ``--showlocals`` still
    print them, which the live run's ``--tb=short`` avoids (queue row 42).

    Args:
        type_: The target type: a model class or a generic such as ``list[Series]``.
        raw: The decoded upstream payload.
        source: Source slug, used in the error message.
        endpoint: Upstream operation name, used in the error message.

    Returns:
        The validated value.

    Raises:
        ValidationError: With the raw payload attached, when validation fails, e.g.
            ``example get_thing: 1 validation error(s); first at value (float_parsing):
            Input should be a valid number, unable to parse string as a number``.
    """
    try:
        return TypeAdapter(type_).validate_python(raw)
    except pydantic.ValidationError as exc:
        message = f"{source} {endpoint}: {_validation_text(exc)}"
        _raise(ValidationError(message, raw=raw, source=source))
