"""Loader for reference data packaged with a source (conventions §3).

Files live in ``<package>/reference/`` as CSV or JSON and ship inside the wheel. File
contents are cached per process; callers get fresh objects on every call.

A packaged list, the records of one upstream operation as the refresh script fetched
them, is a ``PackagedList``: it loads the file, builds the ``ResultMeta`` of an answer
from it (ADR-0041), parses its records and writes the file. ``PackagedList.codes``
declares its code field, its name field and its folding once, a ``PackagedCodes``, whose
``check`` returns an argument as given or raises ``UnknownCode`` (ADR-0045). ``matches`` is
the ``search`` filter of the ``list_*`` tasks; ``closest``, by text, and ``nearest``, by
number, find the known codes near a value that ``UnknownCode`` refuses.

``render_enums`` writes a source's generated ``enums.py``, ``StrEnum`` for a value list and
``IntEnum`` for a list of integer ids and names in one module (conventions §3, ADR-0031):
plain, ASCII-only Python that the refresh script formats with ``ruff format`` and
``ruff check --fix`` before it is committed.
"""

import csv
import difflib
import functools
import io
import json
import keyword
import os
import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time
from enum import Enum
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self, cast

import pydantic
from pydantic import BaseModel, ConfigDict, TypeAdapter, field_validator

from xippios.core.errors import InvalidRequestError, UnknownCode, ValidationError, _raise
from xippios.core.models import ResultMeta, _validation_text, parse

__all__ = [
    "PackagedCodes",
    "PackagedList",
    "closest",
    "enum_member_name",
    "id_name_pairs",
    "load_csv",
    "load_json",
    "load_table",
    "matches",
    "nearest",
    "render_enums",
]

_LINE_LENGTH = 100
"""The family's ``line-length``; a longer generated line carries ``# noqa: E501``."""


@functools.cache
def _read_text(package: str, name: str) -> str:
    path = resources.files(package).joinpath("reference", name)
    if not path.is_file():
        raise FileNotFoundError(f"reference file {name!r} not found in package {package!r}")
    return path.read_text(encoding="utf-8")


def load_csv(package: str, name: str) -> list[dict[str, str]]:
    """Rows of a packaged CSV file as dicts keyed by the header row.

    Args:
        package: Import path of the source package, e.g. ``"xippios.usda.nass"``.
        name: File name under ``reference/``, e.g. ``"commodities.csv"``.
    """
    rows = csv.DictReader(io.StringIO(_read_text(package, name)))
    return [cast(dict[str, str], dict(row)) for row in rows]


def load_json(package: str, name: str) -> Any:
    """Decoded contents of a packaged JSON file.

    Args:
        package: Import path of the source package, e.g. ``"xippios.usda.nass"``.
        name: File name under ``reference/``, e.g. ``"countries.json"``.
    """
    return json.loads(_read_text(package, name))


def load_table[T](package: str, name: str, model: type[T]) -> list[T]:
    """Rows of a packaged CSV or JSON file validated into ``model`` instances.

    The format is chosen by extension: ``.csv`` rows are strings coerced by the model,
    ``.json`` must hold a list of objects.

    Args:
        package: Import path of the source package.
        name: File name under ``reference/``.
        model: The row model, e.g. a ``UpstreamModel`` subclass.

    Raises:
        ValidationError: A row does not fit ``model``; raised as ``parse`` raises it,
            its text naming the package, the file and the first failure's location, type
            and message, the rows on ``raw``.
    """
    raw = load_csv(package, name) if name.endswith(".csv") else load_json(package, name)
    try:
        return TypeAdapter(list[model]).validate_python(raw)  # type: ignore[valid-type]
    except pydantic.ValidationError as exc:
        message = f"{package} reference/{name}: {_validation_text(exc)}"
        _raise(ValidationError(message, raw=raw))


class PackagedList(BaseModel):
    """One packaged list, ``reference/<name>.json``: upstream's records as fetched.

    The file holds ``{"param", "endpoint", "fetched", "records"}`` and, where the source
    has one, ``"note"``. ``<name>`` is usually ``param``; two lists derived from one
    upstream parameter keep it as ``param`` in files of their own names. A list of
    values is records of one field named by the upstream parameter,
    ``[{"state_alpha": "AK"}, ...]``; a table is records of its columns. Any other key
    is refused (ADR-0041, decision 5). Instances are frozen.

    Attributes:
        param: The list, as upstream names it, e.g. ``"commodities"`` or
            ``"state_alpha"``.
        endpoint: The upstream operation the list was fetched from, an operationId or a
            URL path, e.g. ``"PSDData_GetCommodities"`` or
            ``"files/v1/app/reference/Reporters.json"``; never ``"reference"`` or a
            file of the package (ADR-0041, decision 1).
        fetched: When the refresh script fetched the list, timezone-aware UTC; ``write``
            writes it to the second (``"2026-10-27T09:15:00Z"``). A bare date, as
            refresh scripts wrote it before template v0.3.0 (``"2026-10-23"``), reads as
            00:00 UTC of that day, the start of the day the old scripts truncated the
            time to; the source's next refresh writes the full time. A time without a
            zone is refused.
        note: Free-text provenance the source keeps with the list, e.g. what a derived
            list is derived from or how a list was reconciled with upstream's
            documentation; ``None`` when there is none. Core reads nothing from it.
        records: Upstream's records verbatim, under upstream's field names, in
            upstream order, e.g. ``{"commodityCode": "0410000", "commodityName":
            "Wheat"}``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    param: str
    endpoint: str
    fetched: datetime
    note: str | None = None
    records: list[dict[str, Any]]

    @field_validator("fetched", mode="before")
    @classmethod
    def _a_day_is_its_start(cls, value: Any) -> Any:
        if isinstance(value, str) and len(value) == len("2026-10-23"):
            try:
                value = date.fromisoformat(value)
            except ValueError:
                return value
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time(), UTC)
        return value

    @field_validator("fetched")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "fetched must carry a zone (the refresh script writes datetime.now(UTC)) "
                "or be a bare date"
            )
        return value.astimezone(UTC)

    @classmethod
    def load(cls, package: str, name: str) -> Self:
        """The packaged list ``reference/<name>.json`` of ``package``, validated.

        Read through ``load_json``, so the file's text is cached per process; each call
        returns a new instance.

        Args:
            package: Import path of the source package, e.g. ``"xippios.usda.psd"``.
            name: The file, with or without ``.json``, e.g. ``"commodities"``.

        Raises:
            FileNotFoundError: The package ships no such file.
            ValidationError: The file is not a packaged list; raised as ``parse`` raises
                it, its text naming the package, the file and the first failure's
                location, type and message, the file's contents on ``raw``.
        """
        file = name if name.endswith(".json") else f"{name}.json"
        data = load_json(package, file)
        try:
            return cls.model_validate(data)
        except pydantic.ValidationError as exc:
            _raise(
                ValidationError(f"{package} reference/{file}: {_validation_text(exc)}", raw=data)
            )

    def meta(
        self,
        source: str,
        *,
        request: Mapping[str, Any] | None = None,
        vintage: str | None = None,
        published_at: datetime | None = None,
        published_at_naive: bool = False,
    ) -> ResultMeta:
        """The ``ResultMeta`` of an answer from this list (ADR-0041, decision 1).

        ``endpoint`` is the list's upstream operation and ``retrieved_at`` its
        ``fetched``, as a cache hit's is the time its entry was stored; ``total`` stays
        ``None``, since the list carries no count of upstream's.

        Args:
            source: Source slug, e.g. ``"usda-psd"``.
            request: The task's parameters, e.g. ``{"search": "wheat"}``; a ``None``
                is dropped, as for every ``ResultMeta``.
            vintage: Upstream's release identifier of the list, when upstream has one;
                never the fetch date, which is not a vintage.
            published_at: Upstream's release time of the list, when it states one.
            published_at_naive: ``True`` when upstream printed that time without a zone.
        """
        return ResultMeta(
            source=source,
            endpoint=self.endpoint,
            retrieved_at=self.fetched,
            published_at=published_at,
            published_at_naive=published_at_naive,
            vintage=vintage,
            request=dict(request or {}),
        )

    def parse[M](self, model: type[M], *, source: str) -> list[M]:
        """The records validated into ``model`` instances, in upstream order.

        Args:
            model: The record model, e.g. a ``UpstreamModel`` subclass ``Commodity``.
            source: Source slug for the error, e.g. ``"usda-psd"``.

        Raises:
            ValidationError: A record does not fit ``model``; the message names the
                list's ``endpoint``.
        """
        return parse(list[model], self.records, source=source, endpoint=self.endpoint)  # type: ignore[valid-type]

    def codes(
        self,
        code: str,
        name: str | None = None,
        *,
        fold_case: bool = False,
        list_name: str | None = None,
        source: str | None = None,
    ) -> "PackagedCodes":
        """The list's codes, declared once, with the check of an argument (ADR-0045).

        A source declares each list it checks once, as a constant of its module or behind
        ``functools.cache`` where the list is large, and calls ``check`` on it: the index
        of the codes is built here, once, and kept with the declaration.

        Args:
            code: The field that holds the code, e.g. ``"commodityCode"``.
            name: The field that holds the code's name, e.g. ``"commodityName"``;
                ``None`` for a list of values, each its own name.
            fold_case: ``True`` to compare without case, for a list of text codes that
                upstream compares so, as Quick Stats does; ``False`` compares exactly.
            list_name: The list as a refusal names it, e.g. ``"element_QCL"`` where the
                file's name says more than its ``param``; ``param`` by default.
            source: Source slug every refusal carries, e.g. ``"usda-psd"``.

        Raises:
            ValueError: A record lacks ``code`` or ``name``, a code is neither text nor an
                integer, the list holds both, a name is not text, or ``fold_case`` is set
                for integer codes or finds two codes that differ in case alone; the
                message names the field and the record's position, never the record.
        """
        return PackagedCodes(
            self, code, name, fold_case=fold_case, list_name=list_name, source=source
        )

    def write(self, path: str | os.PathLike[str]) -> None:
        """Write the list to ``path`` as its packaged file, for the refresh script.

        JSON with the keys ``param``, ``endpoint``, ``fetched``, ``note`` when it is set,
        and ``records``, in that order, indented by two spaces, non-ASCII text as it is,
        UTF-8, a newline at the end. ``fetched`` is written to the second, as ISO 8601
        UTC with ``Z``: a fraction of a second is dropped, so the refresh script may
        pass ``datetime.now(UTC)`` as it is. ``PackagedList.load`` reads the file back.

        Args:
            path: The file, e.g. ``REFERENCE / "commodities.json"``.
        """
        written = self.model_copy(update={"fetched": self.fetched.replace(microsecond=0)})
        payload = written.model_dump(mode="json", exclude={"note"} if self.note is None else None)
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        Path(path).write_text(text + "\n", encoding="utf-8")


type _Strategy = Callable[[Any, Mapping[Any, str]], Sequence[tuple[Any, str]]]
"""A source's own way to the closest codes: the value and the codes to their names in,
``(code, name)`` pairs out, best first."""


class PackagedCodes:
    """The codes of one packaged list, declared once, and the check of an argument (ADR-0045).

    Made by ``PackagedList.codes``: the codes under the field ``code`` in upstream order,
    each with its name under the field ``name``, upstream's text as the record holds it, or
    with its own text where the list has no name field or a record holds no name. The list's
    type is its codes' own: text or integers, as its records hold them, and a value of the
    other type is refused, never compared by its text. The index is built once, when the
    list is declared, and kept with the declaration for the process.

    ``check`` is conventions §5's refusal of a code the packaged list lacks, in one call; the
    live comparison of a list (https://github.com/xippios/sdk-core/issues/374) and the names
    of a request's codes in ``meta`` (https://github.com/xippios/sdk-core/issues/375) read
    the same declaration through ``code``, ``name``, ``packaged``, ``names`` and
    ``name_of``. Its properties are read-only.
    """

    __slots__ = (
        "_code",
        "_fold_case",
        "_folded",
        "_integer",
        "_list_name",
        "_name",
        "_names",
        "_packaged",
        "_shown",
        "_source",
    )

    def __init__(
        self,
        packaged: PackagedList,
        code: str,
        name: str | None = None,
        *,
        fold_case: bool = False,
        list_name: str | None = None,
        source: str | None = None,
    ) -> None:
        self._packaged = packaged
        self._code = code
        self._name = name
        self._fold_case = fold_case
        self._list_name = packaged.param if list_name is None else list_name
        self._source = source
        names, folded, integer = _declared(packaged.records, code, name, fold_case, self._list_name)
        self._names: Mapping[str | int, str] = MappingProxyType(names)
        self._folded = folded
        self._integer = integer
        self._shown: Mapping[str | int, str] | None = None

    def __repr__(self) -> str:
        return (
            f"PackagedCodes({self._list_name!r}, code={self._code!r}, name={self._name!r}, "
            f"fold_case={self._fold_case!r})"
        )

    @property
    def packaged(self) -> PackagedList:
        """The list it was declared from."""
        return self._packaged

    @property
    def code(self) -> str:
        """The field that holds the code, e.g. ``"countryCode"``."""
        return self._code

    @property
    def name(self) -> str | None:
        """The field that holds the name, e.g. ``"countryName"``; ``None`` for a list of values."""
        return self._name

    @property
    def fold_case(self) -> bool:
        """Whether codes are compared without case."""
        return self._fold_case

    @property
    def list_name(self) -> str:
        """The list as a refusal names it: ``list_name`` as declared, else the list's ``param``."""
        return self._list_name

    @property
    def source(self) -> str | None:
        """Source slug every refusal carries, or ``None``."""
        return self._source

    @property
    def integer(self) -> bool:
        """``True`` for a list of integer codes, ``False`` for one of text codes."""
        return self._integer

    @property
    def names(self) -> Mapping[str | int, str]:
        """Each code to its name in upstream order, read-only.

        A code listed twice keeps the name of its first record, and a code without a name,
        every code of a list of values among them, is named by its own text.
        """
        return self._names

    def name_of(self, value: object) -> str | None:
        """The name of the code ``value`` stands for, compared as ``check`` compares it.

        Args:
            value: A code as a caller gives it, e.g. ``"va"`` for a folded list, ``401``
                for integer codes, or an enum member, read by its value.

        Returns:
            The code's name as ``names`` holds it, e.g. ``"Corn"``, and for a list of
            values the code as upstream spells it, ``"VA"``; ``None`` when the list lacks
            the code or ``value`` is of the other type.
        """
        found = self._canonical(_plain(value))
        return None if found is None else self._names[found]

    def __contains__(self, value: object) -> bool:
        """Whether the list holds ``value``, compared as ``check`` compares it."""
        return self._canonical(_plain(value)) is not None

    def check[V](
        self,
        param: str,
        value: V,
        *,
        hints: Mapping[str, str] | None = None,
        otherwise: str | None = None,
        closest: _Strategy | None = None,
        reason: str | None = None,
    ) -> V:
        """``value`` as the caller gave it, or the refusal of a code the list lacks (§5).

        The value is compared with the list's codes as upstream compares them, without case
        where the list folds it, an enum member by its value, and is returned itself, so
        the task sends it, and records it in ``meta.request``, as given: under folding the
        caller's spelling, which upstream compares without case.

        Args:
            param: The parameter, as the package names it, e.g. ``"country_code"``.
            value: The value given, e.g. ``"US"`` or ``401``.
            hints: Values that are no codes, each with the text that explains it in place
                of the closest codes, e.g. ``{"all": "Omit country_code for every
                country."}``; read with the value's text stripped and without case, as the
                table's keys are.
            otherwise: The text of a refusal that names no code, e.g. ``"list_regions
                lists them."``; left out where a code is close.
            closest: The source's own strategy for the closest codes, a function of the
                value and the codes to their names that returns ``(code, name)`` pairs,
                best first, e.g. ISO codes first; each name with its runs of white space
                collapsed, as a refusal shows it. By default core's ``closest`` for text
                codes and ``nearest`` for integer codes.
            reason: Why the package refuses the value rather than asking upstream, e.g.
                ``"PSD answers unknown codes with an empty result, so the package refuses
                them."``.

        Returns:
            ``value``, the very object given.

        Raises:
            UnknownCode: The list lacks the code; it names the list, its fetch date, the
                closest codes, or the hint, or ``otherwise``, the reason and the source.
            InvalidRequestError: ``value`` is not of the list's type: a text of digits for
                integer codes names the integer to pass, another text the codes whose name
                holds it or comes close, an integer for text codes its text or the codes
                close to it; ``otherwise`` where none is named.
        """
        plain = _plain(value)
        if not self._typed(plain):
            raise self._wrong_type(param, plain, otherwise=otherwise, strategy=closest)
        if self._canonical(plain) is not None:
            return value
        table = {key.strip().casefold(): text for key, text in (hints or {}).items()}
        hint = table.get(str(plain).strip().casefold())
        close: Sequence[tuple[Any, str]] = ()
        if hint is None:
            close = self._closest(plain, closest)
            hint = None if close else otherwise
        raise UnknownCode(
            param,
            cast(str | int, plain),
            list_name=self._list_name,
            fetched=self._packaged.fetched,
            closest=close,
            hint=hint,
            reason=reason,
            source=self._source,
        )

    def _typed(self, plain: object) -> bool:
        if isinstance(plain, bool):
            return False
        return isinstance(plain, int) if self._integer else isinstance(plain, str)

    def _canonical(self, plain: object) -> str | int | None:
        """The list's code that ``plain`` stands for, ``None`` for none."""
        if not self._typed(plain):
            return None
        if self._folded is not None:
            return self._folded.get(cast(str, plain).casefold())
        return cast(str | int, plain) if plain in self._names else None

    def _shown_names(self) -> Mapping[str | int, str]:
        """Each code to its name as a refusal shows it, white space collapsed: ESR pads."""
        if self._shown is None:
            self._shown = MappingProxyType(
                {code: " ".join(name.split()) or str(code) for code, name in self._names.items()}
            )
        return self._shown

    def _closest(self, plain: Any, strategy: _Strategy | None) -> list[tuple[Any, str]]:
        shown = self._shown_names()
        if strategy is not None:
            return list(strategy(plain, shown))
        if self._integer:
            return list(nearest(plain, cast(Mapping[int, str], shown)))
        return list(closest(plain, cast(Mapping[str, str], shown)))

    def _wrong_type(
        self, param: str, plain: object, *, otherwise: str | None, strategy: _Strategy | None
    ) -> InvalidRequestError:
        """The refusal of a value that is not of the list's type (ADR-0045, decision 4)."""
        shown = self._shown_names()
        tail = ""
        if self._integer and isinstance(plain, str):
            digits = plain.strip()
            if digits.isascii() and digits.isdigit():
                tail = f" Pass it as the integer {int(digits)}."
            elif named := _by_name(plain, shown):
                tail = f" By name: {_named(named)}."
        elif not self._integer and isinstance(plain, int) and not isinstance(plain, bool):
            text = str(plain)
            if self._canonical(text) is not None:
                tail = f" Pass it as the text {text!r}."
            elif close := self._closest(text, strategy):
                tail = f" Did you mean {_named(close)}?"
        if not tail and otherwise:
            tail = f" {otherwise}"
        kind = "integer" if self._integer else "text"
        first = next(iter(shown.items()), None)
        such = "" if first is None else f", such as {_named([first])}"
        return InvalidRequestError(
            f"{plain!r} is not {'an' if self._integer else 'a'} {kind} code: {param} takes the "
            f"{kind} codes of the packaged {self._list_name} list (fetched "
            f"{self._packaged.fetched:%Y-%m-%d}){such}.{tail}",
            source=self._source,
        )


def _plain(value: object) -> object:
    """``value``, an enum member read by its value."""
    return value.value if isinstance(value, Enum) else value


def _named(pairs: Iterable[tuple[Any, str]]) -> str:
    """Codes as ``UnknownCode`` names them: ``0410000 (Wheat)``, a code named by itself once."""
    return ", ".join(str(code) if name == str(code) else f"{code} ({name})" for code, name in pairs)


def _by_name(text: str, shown: Mapping[str | int, str]) -> list[tuple[str | int, str]]:
    """Up to three codes whose name holds ``text``, then those whose name comes close.

    Case and runs of white space are ignored, so ``"wheat"`` names ``104 (Wheat - White)``,
    and ``"Flaxsed"`` names ``1001 (Flaxseed)`` by ``difflib``.
    """
    wanted = " ".join(text.split()).casefold()
    if not wanted:
        return []
    found = [code for code, name in shown.items() if wanted in name.casefold()]
    by_name: dict[str, str | int] = {}
    for code, name in shown.items():
        by_name.setdefault(name.casefold(), code)
    found += [
        by_name[name]
        for name in difflib.get_close_matches(wanted, list(by_name), n=3)
        if by_name[name] not in found
    ]
    return [(code, shown[code]) for code in found[:3]]


def _declared(
    records: Sequence[Mapping[str, Any]],
    code: str,
    name: str | None,
    fold_case: bool,
    list_name: str,
) -> tuple[dict[str | int, str], dict[str, str] | None, bool]:
    """The codes to their names, the folded codes to the codes, and whether codes are integers.

    Raises:
        ValueError: As ``PackagedList.codes`` documents; the message opens with
            ``list_name`` and names the field and the record's position.
    """
    names: dict[str | int, str] = {}
    folded: dict[str, tuple[int, str]] = {}
    kinds: set[type] = set()
    for position, record in enumerate(records):
        for field in (code, name):
            if field is not None and field not in record:
                raise ValueError(f"{list_name}: record {position} has no field {field!r}")
        value = record[code]
        if isinstance(value, bool) or not isinstance(value, str | int):
            raise ValueError(
                f"{list_name}: record {position}: field {code!r} is neither text nor an integer"
            )
        kinds.add(str if isinstance(value, str) else int)
        label = None if name is None else record[name]
        if label is not None and not isinstance(label, str):
            raise ValueError(f"{list_name}: record {position}: field {name!r} is not text")
        names.setdefault(value, label or str(value))
        if fold_case and isinstance(value, str):
            first = folded.setdefault(value.casefold(), (position, value))
            if first[1] != value:
                raise ValueError(
                    f"{list_name}: records {first[0]} and {position} hold one code in two "
                    f"cases: {value!r}"
                )
    if len(kinds) > 1:
        raise ValueError(
            f"{list_name}: field {code!r} holds integers and text; a list's codes are one or "
            "the other"
        )
    integer = kinds == {int}
    if fold_case and integer:
        raise ValueError(
            f"{list_name}: fold_case compares text; the codes of field {code!r} are integers"
        )
    index = {key: original for key, (_, original) in folded.items()} if fold_case else None
    return names, index, integer


def matches(search: str | None, *fields: object) -> bool:
    """Whether ``search`` occurs in any of ``fields``, ignoring case: a list task's filter.

    Each field is matched on its own, as text (``str(field)``, so an id matches by its
    digits), never joined with another. A field that is ``None`` (a country without a
    GENC code) matches nothing.

    Args:
        search: The text to look for, e.g. ``"wheat"``; ``None`` matches every record.
        *fields: The record's fields to look in, e.g. its code and its name.
    """
    if search is None:
        return True
    needle = search.casefold()
    return any(needle in str(field).casefold() for field in fields if field is not None)


def closest(
    value: str, codes: Mapping[str, str], *, n: int = 3, cutoff: float = 0.6
) -> list[tuple[str, str]]:
    """Up to ``n`` known codes close to ``value``: by code first, then by upstream name.

    Two ``difflib.get_close_matches`` passes: ``value`` upper-cased against the codes,
    then ``value`` lower-cased against the lower-cased names, each code named once, best
    match first. An agent that passes ``"us"`` for ``"US"`` or ``"wheat"`` for
    ``"0410000"`` is led to the code. For ``UnknownCode``'s ``closest``; ``nearest``
    matches integer codes by number instead.

    Args:
        value: The value given, e.g. ``"wheat"``.
        codes: Upstream's code to its name, e.g. ``{"0410000": "Wheat"}``, or each value
            to itself for a list of bare values, e.g. ``{"VA": "VA"}``.
        n: The most pairs returned.
        cutoff: The least similarity a match needs in either pass, from 0 to 1, as
            ``difflib`` scores it: 0.6, ``difflib``'s own, by default; 0.5 lets a code of
            two characters with one of them wrong match, ``"VS"`` naming ``"VA"``.

    Returns:
        ``(code, name)`` pairs, e.g. ``[("0410000", "Wheat")]``; empty when none is close.

    Raises:
        ValueError: ``n`` is less than 1, or ``cutoff`` is outside 0 to 1, as ``difflib``
            refuses them.
    """
    found = difflib.get_close_matches(value.upper(), list(codes), n=n, cutoff=cutoff)
    by_name = {name.lower(): code for code, name in codes.items()}
    found += [
        by_name[name]
        for name in difflib.get_close_matches(value.lower(), list(by_name), n=n, cutoff=cutoff)
        if by_name[name] not in found
    ]
    return [(code, codes[code]) for code in found[:n]]


def nearest[K: (int, str)](
    value: int, codes: Mapping[K, str], *, n: int = 3
) -> list[tuple[K, str]]:
    """Up to ``n`` known integer codes nearest to ``value`` by number, nearest first.

    The strategy sdk-usda-esr and sdk-usda-gats carried for their integer codes, where a
    code close in number is likelier the one meant than a code close in spelling: ``999``
    among ``902``, ``1001`` and ``104`` names ``1001``, then ``902``, then ``104``. Of two
    codes equally near, the lower comes first. A code keyed by its text, as sdk-usda-gats
    keys its customs districts (``"10"``), is compared as the integer it writes and
    returned as given. For ``UnknownCode``'s ``closest``, as ``closest`` is for codes
    matched by their text and names.

    Args:
        value: The integer given, e.g. ``999``.
        codes: Upstream's integer code to its name, keyed by the integer, e.g.
            ``{1001: "Flaxseed"}``, or by its text, e.g. ``{"1001": "Flaxseed"}``.
        n: The most pairs returned.

    Returns:
        ``(code, name)`` pairs with the codes as ``codes`` keys them, e.g.
        ``[(1001, "Flaxseed"), (902, "Soybean Oil")]``; empty when ``codes`` is.

    Raises:
        ValueError: ``n`` is less than 1, or a code keyed by its text is no integer.
    """
    if n < 1:
        raise ValueError(f"n must be > 0: {n!r}")
    distances: list[tuple[int, int, K]] = []
    for code in codes:
        try:
            number = code if isinstance(code, int) else int(code)
        except ValueError:
            raise ValueError(f"the code {code!r} of codes is not an integer") from None
        distances.append((abs(number - value), number, code))
    distances.sort(key=lambda distance: distance[:2])
    return [(code, codes[code]) for _, _, code in distances[:n]]


def enum_member_name(value: str) -> str:
    """An identifier for an enum member: ``"ANIMALS & PRODUCTS"`` → ``ANIMALS_AND_PRODUCTS``.

    Upper case, ``&`` read as ``AND``, every other run of non-alphanumerics folded to one
    underscore, a leading digit prefixed with an underscore.
    """
    name = re.sub(r"[^A-Z0-9]+", "_", value.upper().replace("&", " AND ")).strip("_")
    if not name:
        raise ValueError(f"no identifier can be made from {value!r}")
    return f"_{name}" if name[0].isdigit() else name


def id_name_pairs(
    records: Iterable[Mapping[str, Any]], *, id_field: str, name_field: str
) -> list[tuple[int, str]]:
    """``(id, name)`` pairs from upstream's records, in upstream order, for ``render_enums``.

    Args:
        records: Upstream's records under upstream's field names, e.g. PSD's
            ``commodityAttributes``.
        id_field: The field holding the integer id, e.g. ``"attributeId"``; an ``int`` or
            a string of ASCII digits without leading zeros (``"28"``, not ``"007"``).
        name_field: The field holding the name, a string, e.g. ``"attributeName"``.

    Raises:
        ValueError: When a record lacks a field, its id is not an integer or has leading
            zeros that ``int`` would drop, or its name is not a string. The message names
            the field and the record's position, never the record.
    """
    pairs: list[tuple[int, str]] = []
    for index, record in enumerate(records):
        for field in (id_field, name_field):
            if field not in record:
                raise ValueError(f"record {index} has no field {field!r}")
        ident, name = record[id_field], record[name_field]
        if isinstance(ident, str) and ident.isascii() and ident.isdigit():
            if len(ident) > 1 and ident.startswith("0"):
                raise ValueError(
                    f"record {index}: field {id_field!r} has leading zeros an integer id would lose"
                )
            ident = int(ident)
        if not isinstance(ident, int) or isinstance(ident, bool):
            raise ValueError(f"record {index}: field {id_field!r} is not an integer id")
        if not isinstance(name, str):
            raise ValueError(f"record {index}: field {name_field!r} is not a string")
        pairs.append((ident, name))
    return pairs


_TEXT_RULE = "non-empty printable ASCII without a backslash or three double quotes"

_BASES = frozenset({"IntEnum", "StrEnum"})
"""The names the generated module imports, which no class of it may take."""

_CLASS_NAME_LIMIT = _LINE_LENGTH - len("class (StrEnum):")
"""84: the longest class name whose ``class`` line fits; ``ruff format`` cannot shorten one."""


def _plain_text(text: str) -> bool:
    """Whether ``text`` fits a generated docstring as it is: ``_TEXT_RULE``."""
    return (
        bool(text)
        and text.isascii()
        and text.isprintable()
        and "\\" not in text
        and '"""' not in text
    )


_AMBIGUOUS = frozenset({"I", "O", "l"})
"""Names ruff flags as ambiguous (E741) and cannot fix: a member upstream's ``"I"`` names."""


def _fit(line: str, *codes: str) -> str:
    """``line`` with a ``# noqa`` for ``codes``, and for E501 when it is over 100 columns.

    No tool can shorten an upstream value, a long key or a member name derived from a long
    label, nor rename a member upstream's value names ``I`` or ``O`` (E741), so such a line
    is exempted, not refused; ruff drops a code again where ``ruff format`` makes the line
    fit (RUF100).
    """
    exempt = ("E501",) * (len(line) > _LINE_LENGTH) + codes
    return f"{line}  # noqa: {', '.join(exempt)}" if exempt else line


_HUMP = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
"""Where a camelCase part starts a word: before an upper-case letter after a lower-case
letter or a digit."""


def _class_name(key: str) -> str:
    """The default class name: each word of ``key`` capitalized, a camelCase hump kept.

    ``attributeId`` → ``AttributeId``, ``partner2Code`` → ``Partner2Code``, ``state_alpha``
    and ``STATE_ALPHA`` → ``StateAlpha``: a key splits into parts at each run of characters
    that are no ASCII letters or digits, a part that holds a lower-case letter splits again
    before each hump, and every word is capitalized. A part in upper case alone has no hump
    (``STATE2ALPHA`` → ``State2alpha``), nor has an upper-case run (``HSCode`` →
    ``Hscode``): such a key keeps the name it had before humps were kept.
    """
    words: list[str] = []
    for part in re.split(r"[^A-Za-z0-9]+", key):
        words += _HUMP.split(part) if re.search(r"[a-z]", part) else [part]
    return "".join(word.capitalize() for word in words if word)


def _unknown_keys(argument: str, given: Mapping[str, object], lists: Mapping[str, object]) -> None:
    unknown = sorted(set(given) - set(lists))
    if unknown:
        raise ValueError(f"{argument} names lists that are not rendered: {unknown}")


def _class_names(lists: Mapping[str, object], class_names: Mapping[str, str]) -> dict[str, str]:
    """The class name per key, once every key is known to fit a docstring.

    Raises:
        ValueError: A key is not ``_TEXT_RULE``; a class name is no ASCII identifier, is a
            keyword or one of ``_BASES``, which the module could not execute with, or is
            longer than ``_CLASS_NAME_LIMIT``; two keys get one class name. The message
            names the position.
    """
    names: dict[str, str] = {}
    for index, key in enumerate(lists):
        if not _plain_text(key):
            raise ValueError(f"the key at position {index} of lists must be {_TEXT_RULE}")
        given = class_names.get(key)
        name = _class_name(key) if given is None else given
        too_long = len(name) > _CLASS_NAME_LIMIT
        refused = keyword.iskeyword(name) or name in _BASES or too_long
        if not (name.isascii() and name.isidentifier()) or refused:
            where = (
                f"the class name derived from the key at position {index} of lists"
                if given is None
                else f"class_names for the key at position {index} of lists"
            )
            raise ValueError(
                f"{where} must be an ASCII identifier, not a keyword, IntEnum or StrEnum, of "
                f"at most {_CLASS_NAME_LIMIT} characters; set it in class_names"
            )
        names[key] = name
    positions: dict[str, list[int]] = {}
    for index, name in enumerate(names.values()):
        positions.setdefault(name, []).append(index)
    shared = [
        f"{name!r} at positions {', '.join(map(str, where))}"
        for name, where in positions.items()
        if len(where) > 1
    ]
    if shared:
        raise ValueError(f"class names collide: {'; '.join(shared)}; set them in class_names")
    return names


def _dates(lists: Mapping[str, object], fetched: str | Mapping[str, str]) -> dict[str, str]:
    """The fetch date per key: ``fetched`` for every list, or each list's own.

    Raises:
        ValueError: A date is not ``_TEXT_RULE``, or a mapping lacks a key of ``lists``
            or names one it does not hold.
    """
    if isinstance(fetched, str):
        if not _plain_text(fetched):
            raise ValueError(f"fetched must be {_TEXT_RULE}")
        return dict.fromkeys(lists, fetched)
    _unknown_keys("fetched", fetched, lists)
    dates: dict[str, str] = {}
    for index, key in enumerate(lists):
        if key not in fetched:
            raise ValueError(f"fetched has no date for the key at position {index} of lists")
        if not _plain_text(fetched[key]):
            raise ValueError(
                f"fetched for the key at position {index} of lists must be {_TEXT_RULE}"
            )
        dates[key] = fetched[key]
    return dates


def _is_pair(item: object) -> bool:
    return (
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], int)
        and not isinstance(item[0], bool)
        and isinstance(item[1], str)
    )


def _kind(key: str, values: object) -> str:
    """``"StrEnum"`` for a list of strings, ``"IntEnum"`` for a list of ``(id, name)`` pairs.

    Raises:
        ValueError: ``values`` is a string or empty, or is neither all strings nor all
            pairs of an ``int`` and a ``str``; the message names what it found, by type.
    """
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(
            f"{key}: a list of values or of (id, name) pairs is needed, not {_described(values)}"
        )
    if not values:
        raise ValueError(f"{key}: the list is empty; an enum needs at least one value")
    if all(isinstance(item, str) for item in values):
        return "StrEnum"
    if all(_is_pair(item) for item in values):
        return "IntEnum"
    if isinstance(values[0], str) or _is_pair(values[0]):
        fits = _is_pair if _is_pair(values[0]) else (lambda item: isinstance(item, str))
        position = next(index for index, item in enumerate(values) if not fits(item))
        found = (
            f"item 0 is {_described(values[0])} and item {position} {_described(values[position])}"
        )
    else:
        found = f"item 0 is {_described(values[0])}"
    raise ValueError(
        f"{key}: a list holds strings (a StrEnum) or (id, name) pairs of an int and a str (an "
        f"IntEnum), as id_name_pairs builds them; {found}"
    )


def _described(item: object) -> str:
    """What ``item`` is, by type, never by value: ``"a str"``, ``"a tuple of int, str"``."""
    if _is_pair(item):
        return "an (id, name) pair"
    if isinstance(item, tuple):
        return f"a tuple of {', '.join(type(part).__name__ for part in item) or 'nothing'}"
    name = type(item).__name__
    return f"{'an' if name[:1] in 'aeiou' else 'a'} {name}"


def _derived(text: str) -> str | None:
    """``enum_member_name(text)``, or ``None`` when ``text`` has nothing to derive it from."""
    try:
        return enum_member_name(text)
    except ValueError:
        return None


def _acceptable(member: str) -> bool:
    """Whether ``member`` is an ASCII identifier that an enum takes as a member.

    An enum refuses ``mro`` and ``_sunder_`` names and makes no member of a name with a
    double underscore in it, a ``__dunder__`` or a class-private ``_Class__name``; a
    keyword is no identifier to assign to. A derived name never holds ``__``.
    """
    sunder = len(member) > 2 and member[0] == member[-1] == "_"
    return (
        member.isascii()
        and member.isidentifier()
        and not keyword.iskeyword(member)
        and "__" not in member
        and not sunder
        and member != "mro"
    )


def _member_names[T](
    key: str,
    items: Sequence[T],
    derived: Sequence[str | None],
    labels: Sequence[str],
    overrides: Mapping[T, str],
) -> list[str]:
    """Member names for ``items``: each item's override, else its derived name.

    An override is taken before any name is derived, so a value with nothing to derive a
    name from (``None`` in ``derived``) can be named by hand. ``labels`` describe the
    items in messages.

    Raises:
        ValueError: When an override names an item the list does not hold, an item has
            neither a derived name nor an override, a name is no identifier an enum
            accepts, or two names collide.
    """
    held = set(items)
    unknown = [item for item in overrides if item not in held]
    if unknown:
        raise ValueError(f"{key}: member_names names what the list does not hold: {unknown}")
    hint = f"name it by hand in member_names={{{key!r}: {{...}}}}"
    members: list[str] = []
    for index, (item, name, label) in enumerate(zip(items, derived, labels, strict=True)):
        if item in overrides:
            members.append(overrides[item])
        elif name is None:
            raise ValueError(
                f"{key}: no member name can be derived from {label} at position {index}; {hint}"
            )
        else:
            members.append(name)
    for index, (member, label) in enumerate(zip(members, labels, strict=True)):
        if not _acceptable(member):
            raise ValueError(
                f"{key}: {member!r} for {label} at position {index} is not a member name an "
                "enum accepts"
            )
    positions: dict[str, list[int]] = {}
    for index, member in enumerate(members):
        positions.setdefault(member, []).append(index)
    colliding = [
        f"{member!r} at positions {', '.join(map(str, where))}"
        for member, where in sorted(positions.items())
        if len(where) > 1
    ]
    if colliding:
        raise ValueError(f"{key}: member names collide: {'; '.join(colliding)}")
    return members


def _str_members(
    key: str, values: Sequence[str], overrides: Mapping[str, str]
) -> list[tuple[str, str]]:
    """``(member, literal)`` per value, the value written as ``ascii()`` writes it."""
    derived = [_derived(value) for value in values]
    labels = [repr(value) for value in values]
    members = _member_names(key, values, derived, labels, overrides)
    return [(member, ascii(value)) for member, value in zip(members, values, strict=True)]


def _int_members(
    key: str, pairs: Sequence[tuple[int, str]], overrides: Mapping[int, str]
) -> list[tuple[str, str]]:
    """``(member, literal)`` per pair: names from the names, ``_<id>`` where one repeats.

    Raises:
        ValueError: An id is listed twice, naming the key and the ids.
    """
    repeated = sorted(ident for ident, count in Counter(i for i, _ in pairs).items() if count > 1)
    if repeated:
        raise ValueError(f"{key}: ids listed more than once: {repeated}")
    plain = [_derived(name) for _, name in pairs]
    counts = Counter(name for name in plain if name is not None)
    derived = [
        name if name is None or counts[name] == 1 else f"{name}_{ident}"
        for name, (ident, _) in zip(plain, pairs, strict=True)
    ]
    ids = [ident for ident, _ in pairs]
    labels = [f"{name!r} (id {ident})" for ident, name in pairs]
    members = _member_names(key, ids, derived, labels, overrides)
    return [(member, f"{ident:d}") for member, ident in zip(members, ids, strict=True)]


def render_enums(
    lists: Mapping[str, Sequence[str] | Sequence[tuple[int, str]]],
    *,
    fetched: str | Mapping[str, str],
    class_names: Mapping[str, str] | None = None,
    member_names: Mapping[str, Mapping[Any, str]] | None = None,
    generator: str = "the reference refresh script",
) -> str:
    r"""Python source for a source's ``enums.py``: one enum per packaged list (conventions §3).

    The kind is inferred per list, so one module holds both: a list of strings renders a
    ``StrEnum`` whose members are the upstream strings, verbatim; a list of ``(id, name)``
    pairs, as ``id_name_pairs`` builds them, renders an ``IntEnum`` whose members are the
    ids, so a member compares equal to the id in upstream's data, with ``_<id>`` appended
    to a name several ids share (``TOTAL_DISAPPEARANCE_126``). Member names come from
    ``enum_member_name``, or from ``member_names`` where a source names one by hand. Each
    class's docstring is one line, ``Values of ``<key>`` (fetched <date>).``, which an MCP
    tool's input schema shows an agent (conventions §8).

    The output is plain and ASCII-only (ADR-0031): a value is written as ``ascii()``
    writes it, so a quote, a backslash, a control character and every character outside
    ASCII is escaped (``"Côte"`` as ``'C\xf4te'``) and the value is the same at runtime;
    one member per line; ``__all__`` one name per line in the order of ``lists``; the
    import names the kinds the module needs. A line longer than 100 columns carries
    ``# noqa: E501``, and a member named ``I``, ``O`` or ``l``, which ruff flags as
    ambiguous with no fix, ``# noqa: E741``. The refresh script runs ``ruff format`` and
    ``ruff check --fix`` on the result, which choose the quotes, wrap what fits and sort
    ``__all__`` (RUF022); the module is committed as formatted.

    Args:
        lists: Enum key to its values in upstream order: strings
            (``{"state_alpha": ["AK", "AL"]}``) or ``(id, name)`` pairs
            (``{"attributeId": [(4, "Area Harvested"), (20, "Beginning Stocks")]}``).
        fetched: When the lists were fetched, as text: one date for the module
            (``"2026-10-27"``), or one per key (``{"state_alpha": "2026-10-27",
            "attributeId": "2026-10-23"}``) for lists fetched on different days.
        class_names: Class name per key, e.g. ``{"progress_stages": "ProgressStage"}``;
            by default each word of the key capitalized, a camelCase hump kept:
            ``StateAlpha`` for ``state_alpha`` and ``AttributeId`` for ``attributeId``.
        member_names: Member names set by hand, per key and value (an id for an
            ``IntEnum``), for a value whose derived name collides or that has none (an
            empty or a non-Latin label), e.g. ``{"short_desc": {"CORN, GRAIN": "CORN"}}``
            or ``{"attributeId": {173: "TOTAL_USE"}}``. Taken before any name is derived;
            each must be an identifier an enum accepts and unique in its list.
        generator: What the module docstring names as its generator, e.g.
            ``"scripts/refresh_reference.py"``.

    Raises:
        ValueError: A list is empty, a string, or mixes strings and pairs; ``generator``,
            a date or a key is not non-empty printable ASCII or holds a backslash or three
            double quotes; a class name is no ASCII identifier, is a keyword, ``IntEnum``
            or ``StrEnum``, is longer than 84 characters, or two lists get one; an id is
            listed twice; a value without an override has nothing to derive a member name
            from; two members of one list share a name; a name in ``member_names`` is not
            one an enum takes (``mro``, ``_x_``, any with ``__``); or ``fetched``,
            ``class_names`` or ``member_names`` names a key ``lists`` does not hold,
            ``fetched`` lacks one, or ``member_names`` names a value or an id its list does
            not hold. A message names the argument and the position, a list's items by
            type.
    """
    if not _plain_text(generator):
        raise ValueError(f"generator must be {_TEXT_RULE}")
    _unknown_keys("class_names", class_names or {}, lists)
    _unknown_keys("member_names", member_names or {}, lists)
    names = _class_names(lists, class_names or {})
    dates = _dates(lists, fetched)
    kinds: set[str] = set()
    classes: list[list[str]] = []
    for key, values in lists.items():
        kind = _kind(key, values)
        overrides = (member_names or {}).get(key, {})
        members = (
            _str_members(key, cast(Sequence[str], values), overrides)
            if kind == "StrEnum"
            else _int_members(key, cast(Sequence[tuple[int, str]], values), overrides)
        )
        kinds.add(kind)
        classes.append(
            [
                f"class {names[key]}({kind}):",
                _fit(f'    """Values of ``{key}`` (fetched {dates[key]})."""'),
                "",
                *(
                    _fit(f"    {member} = {literal}", *("E741",) * (member in _AMBIGUOUS))
                    for member, literal in members
                ),
            ]
        )
    lines = [
        _fit(f'"""Enums of the packaged lists, generated by {generator}; do not edit by hand."""'),
        "",
    ]
    if kinds:
        lines += [f"from enum import {', '.join(sorted(kinds))}", ""]
    if names:
        lines += ["__all__ = [", *(f'    "{name}",' for name in names.values()), "]"]
    else:
        lines.append("__all__ = []")
    for body in classes:
        lines += ["", "", *body]
    return "\n".join(lines) + "\n"
