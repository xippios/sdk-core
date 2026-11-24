"""Loader for reference data packaged with a source (conventions §3).

Files live in ``<package>/reference/`` and ship inside the wheel, and core reads the JSON
ones: ``load_json`` and ``PackagedList``. File contents are cached per process; callers get
fresh objects on every call.

A packaged list, the records of one upstream operation as the refresh script fetched
them, is a ``PackagedList``: it loads the file, builds the ``ResultMeta`` of an answer
from it (ADR-0041), parses its records and writes the file. ``PackagedList.codes``
declares its code field, its name field and its folding once, a ``PackagedCodes``, whose
``check`` returns an argument, one code or a list of codes, as given or raises
``UnknownCode`` (ADR-0045), and from which ``names_codes`` names each code of a task's call,
and a record's ``NamedBy`` each code of the answer's records, in ``meta.names`` (ADR-0067).
``matches`` is the ``search`` filter of the ``list_*`` tasks; ``closest``, by text, and
``nearest``, by number, find the known codes near a value that ``UnknownCode`` refuses.

A source's generated ``enums.py`` is rendered by the reference frame,
``xippios.core.refresh``, which alone calls its renderer and holds it (ADR-0062, decision 13).
"""

import difflib
import functools
import inspect
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time
from enum import Enum
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Self, cast

import pydantic
from pydantic import BaseModel, ConfigDict, field_validator

from xippios.core.errors import (
    _UNSENT,
    InvalidRequestError,
    UnknownCode,
    ValidationError,
    _asked,
    _raise,
)
from xippios.core.models import (
    Result,
    ResultMeta,
    _code,
    _codes_in,
    _validation_text,
    parse,
)

__all__ = [
    "PackagedCodes",
    "PackagedList",
    "closest",
    "load_json",
    "matches",
    "names_codes",
    "nearest",
]


@functools.cache
def _read_text(package: str, name: str) -> str:
    path = resources.files(package).joinpath("reference", name)
    if not path.is_file():
        raise FileNotFoundError(f"reference file {name!r} not found in package {package!r}")
    return path.read_text(encoding="utf-8")


def load_json(package: str, name: str) -> Any:
    """Decoded contents of a packaged JSON file.

    Args:
        package: Import path of the source package, e.g. ``"xippios.example"``.
        name: File name under ``reference/``, e.g. ``"countries.json"``.
    """
    return json.loads(_read_text(package, name))


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
            URL path, e.g. ``"Regions_List"`` or
            ``"v1/reference/regions.json"``; never ``"reference"`` or a
            file of the package (ADR-0041, decision 1).
        fetched: When the refresh script fetched the list, timezone-aware UTC; ``write``
            writes it to the second (``"2026-10-27T09:15:00Z"``). A bare date
            (``"2026-10-23"``) reads as 00:00 UTC of that day, and the source's next
            refresh writes the full time. A time without a zone is refused.
        note: Free-text provenance the source keeps with the list, e.g. what a derived
            list is derived from or how a list was reconciled with upstream's
            documentation; ``None`` when there is none. Core reads nothing from it.
        records: Upstream's records verbatim, under upstream's field names, in
            upstream order, e.g. ``{"regionCode": "R01", "regionName":
            "North"}``.
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
            package: Import path of the source package, e.g. ``"xippios.example"``.
            name: The file, with or without ``.json``, e.g. ``"regions"``.

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
            source: Source slug, e.g. ``"example"``.
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
            source: Source slug for the error, e.g. ``"example"``.

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
            code: The field that holds the code, e.g. ``"regionCode"``.
            name: The field that holds the code's name, e.g. ``"regionName"``;
                ``None`` for a list of values, each its own name.
            fold_case: ``True`` to compare without case, for a list of text codes that
                upstream compares so; ``False`` compares exactly.
            list_name: The list as a refusal names it, e.g. ``"regions_v2"`` where the
                file's name says more than its ``param``; ``param`` by default.
            source: Source slug every refusal carries, e.g. ``"example"``.

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
``(code, name)`` pairs out, best first. The value is the caller's, so a strategy of integer
codes takes a text as well and returns no pair for one it does not read (ADR-0045, amendment
2026-11-22)."""


class PackagedCodes:
    """The codes of one packaged list, declared once, and the check of an argument (ADR-0045).

    Made by ``PackagedList.codes``: the codes under the field ``code`` in upstream order,
    each with its name under the field ``name``, upstream's text as the record holds it, or
    with its own text where the list has no name field or a record holds no name. The list's
    type is its codes' own: text or integers, as its records hold them, and a value of the
    other type is refused, never compared by its text. The index is built once, when the
    list is declared, and kept with the declaration for the process.

    ``check`` is conventions §5's refusal of a code the packaged list lacks, in one call, for
    one code or a list of them; the live comparison of a list
    (https://github.com/xippios/sdk-core/issues/374) and the names of a request's codes in
    ``meta`` (https://github.com/xippios/sdk-core/issues/375) read the same declaration
    through ``code``, ``list_name``, ``packaged``, ``integer`` and ``name_of``, the members
    that core reads and the ones that stay (ADR-0045, amendment 2026-11-24). Its properties
    are read-only.
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
    def list_name(self) -> str:
        """The list as a refusal names it: ``list_name`` as declared, else the list's ``param``."""
        return self._list_name

    @property
    def integer(self) -> bool:
        """``True`` for a list of integer codes, ``False`` for one of text codes."""
        return self._integer

    def name_of(self, value: object) -> str | None:
        """The name of the code ``value`` stands for, compared as ``check`` compares it.

        A code listed twice keeps the name of its first record, and a code without a name,
        every code of a list of values among them, is named by its own text.

        Args:
            value: A code as a caller gives it, e.g. ``"r1"`` for a folded list, ``10``
                for integer codes, or an enum member, read by its value.

        Returns:
            The code's name as its record holds it, e.g. ``"North"``, and for a list of
            values the code as upstream spells it, ``"R1"``; ``None`` when the list lacks
            the code or ``value`` is of the other type.
        """
        found = self._canonical(_plain(value))
        return None if found is None else self._names[found]

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

        The value is one code or a list of codes, several values of one filter, and each
        code is compared with the list's codes as upstream compares them, without case where
        the list folds it, an enum member by its value. The value is returned itself, so the
        task sends it, and records it in ``meta.request``, as given: under folding the
        caller's spelling, which upstream compares without case. A list is checked in its
        order and refused for its first code that the check refuses, and an empty list is
        refused, since it holds no code to send.

        A task calls ``check`` before any request of the call, which makes the sentence of
        each refusal, ``Nothing was sent.``, true (conventions §5; ADR-0045, amendment
        2026-11-24)::

            REGIONS.check("region_code", ["R1", "R9"])
            # UnknownCode: 'R9' is not a region_code in the packaged regions list (fetched
            # 2026-10-23). Nothing was sent. Did you mean R1 (North)? ...

        Args:
            param: The parameter, as the package names it, e.g. ``"region_code"``.
            value: The value given: one code, e.g. ``"R1"`` or ``10``, or a list (or a
                tuple) of codes, e.g. ``["R1", "R3"]``.
            hints: Values that are no codes, each with the text that explains it in place
                of the closest codes, e.g. ``{"all": "Omit country_code for every
                country."}``; read with the value's text stripped and without case, as the
                table's keys are, before the list's type: a text or an integer the table
                holds is refused with its text whatever the list's type, so ``"all"``
                given for integer codes reads its hint. Such a value is no code, so its
                refusal leaves out that the packaged list is out of date (ADR-0041,
                decision 8, amended 2026-11-22).
            otherwise: The text of a refusal that names no code, e.g. ``"list_regions
                lists them."``; left out where a code is close.
            closest: The source's own strategy for the closest codes, a function of the
                value and the codes to their names that returns ``(code, name)`` pairs,
                best first, e.g. ISO codes first; each name with its runs of white space
                collapsed, as a refusal shows it. By default core's ``closest`` for text
                codes and ``nearest`` for integer codes. For integer codes it is asked for
                a text that is no number as well, such as ``"US"``, so it takes a text and
                returns no pair for one it does not read, and the codes are then named by
                name (ADR-0045, amendment 2026-11-22).
            reason: Why the package refuses the value rather than asking upstream, e.g.
                ``"Example answers an unknown code with an empty list, so the package
                refuses it."``.

        Returns:
            ``value``, the very object given.

        Raises:
            UnknownCode: The list lacks the code, a list's first such code; it names the
                list, its fetch date, that nothing was sent, the closest codes, or the hint,
                or ``otherwise``, the reason and the source.
            InvalidRequestError: The code is not of the list's type and the hint table
                does not hold it: a text of digits for integer codes names the integer to
                pass, another text the codes the source's strategy names for it, else
                those whose name holds it or comes close, an integer for text codes its
                text or the codes close to it; ``otherwise`` where none is named, then the
                reason and the source. Or the list is empty: the refusal names the codes
                the parameter takes, then ``otherwise``.
        """
        codes: Sequence[object] = value if isinstance(value, list | tuple) else [value]
        if not codes:
            raise self._empty(param, otherwise)
        for code in codes:
            refusal = self._refusal(
                param, code, hints=hints, otherwise=otherwise, strategy=closest, reason=reason
            )
            if refusal is not None:
                raise refusal
        return value

    def _refusal(
        self,
        param: str,
        code: object,
        *,
        hints: Mapping[str, str] | None,
        otherwise: str | None,
        strategy: _Strategy | None,
        reason: str | None,
        asked: bool = False,
    ) -> InvalidRequestError | None:
        """The refusal of one code, ``None`` for a code the list holds.

        ``asked`` is the switch of core's own check after the call, ``names_codes``: its
        refusal leaves out ``Nothing was sent.``, since upstream was asked, and its reason
        says so (ADR-0045, amendment 2026-11-24).
        """
        plain = _plain(code)
        if self._canonical(plain) is not None:
            return None
        hint = _hint(plain, hints)
        if hint is None and not self._typed(plain):
            return self._wrong_type(
                param, plain, otherwise=otherwise, strategy=strategy, reason=reason, asked=asked
            )
        close: Sequence[tuple[Any, str]] = ()
        outdated = hint is None  # the table's value is no code: no refresh makes it one
        if hint is None:
            close = self._closest(plain, strategy)
            hint = None if close else otherwise
        refusal = UnknownCode(
            param,
            cast(str | int, plain),
            list_name=self._list_name,
            fetched=self._packaged.fetched,
            closest=close,
            hint=hint,
            reason=reason,
            source=self._source,
            outdated=outdated,
        )
        return _asked(refusal) if asked else refusal

    def _empty(self, param: str, otherwise: str | None) -> InvalidRequestError:
        """The refusal of an empty list of codes, which names what ``param`` takes."""
        return InvalidRequestError(
            f"{param} lists no code: it takes one or more {self._kind()} codes of the packaged "
            f"{self._list_name} list (fetched {self._packaged.fetched:%Y-%m-%d}){self._such()}. "
            f"{_UNSENT}{' ' + otherwise if otherwise else ''}",
            source=self._source,
        )

    def _kind(self) -> str:
        return "integer" if self._integer else "text"

    def _such(self) -> str:
        """``, such as R1 (North)``, the list's first code as a refusal shows it, or nothing."""
        first = next(iter(self._shown_names().items()), None)
        return "" if first is None else f", such as {_named([first])}"

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
        """Each code to its name as a refusal shows it, white space collapsed, as upstream pads."""
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
        self,
        param: str,
        plain: object,
        *,
        otherwise: str | None,
        strategy: _Strategy | None,
        reason: str | None,
        asked: bool,
    ) -> InvalidRequestError:
        """The refusal of a value that is not of the list's type (ADR-0045, decision 4).

        A text that is no number, given for integer codes, is named by the source's strategy
        first, as an ISO code names the area it stands for, and by name where the strategy
        names none or none is given (ADR-0045, decision 4, amended 2026-11-22). After its
        first sentence it says that nothing was sent unless ``asked``, as ``UnknownCode``
        does, and it ends with the ``reason`` (conventions §5).
        """
        shown = self._shown_names()
        tail = ""
        if self._integer and isinstance(plain, str):
            digits = plain.strip()
            if digits.isascii() and digits.isdigit():
                tail = f" Pass it as the integer {int(digits)}."
            elif strategy is not None and (close := list(strategy(plain, shown))):
                tail = f" Did you mean {_named(close)}?"
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
        if reason:
            tail += f" {reason}"
        kind = self._kind()
        return InvalidRequestError(
            f"{plain!r} is not {'an' if self._integer else 'a'} {kind} code: {param} takes the "
            f"{kind} codes of the packaged {self._list_name} list (fetched "
            f"{self._packaged.fetched:%Y-%m-%d}){self._such()}.{'' if asked else ' ' + _UNSENT}"
            f"{tail}",
            source=self._source,
        )


_DECLARED = "_xippios_names_codes"
"""The attribute of a task that ``names_codes`` wraps: its parameters to their lists."""

_WITHHELD = (
    "Upstream was asked, but an answer names each code it is for, and the packaged list "
    "holds no name for this one, so the answer is withheld."
)
"""The reason of a refusal after the call, for a code that reached the answer unchecked."""


def names_codes[F: Callable[..., Any]](**codes: PackagedCodes) -> Callable[[F], F]:
    """Name each code of a call in ``meta.names`` of the answer (ADR-0067, decision 3).

    A task that takes a code that an answer names, a country's say, declares, per
    parameter, the list that names its codes, ``PackagedList.codes`` (ADR-0045), and every
    ``Result`` it returns carries the name of each code it was called with (conventions
    §4). The codes of the answer's records are named by their model's ``NamedBy``::

        COUNTRIES = PackagedList.load("xippios.example", "countries").codes(
            "countryCode", "countryName", source="example"
        )


        @names_codes(country_code=COUNTRIES)
        async def get_data_async(country_code: str | None = None) -> Result[list[Row]]: ...


        get_data = sync(get_data_async)
        get_data("CN").meta.names  # {"country_code": {"CN": "Comoros"}}

    The decorator wraps an ``async def``, a plain function or a ``sync`` facade, whose async
    twin it wraps too, so the MCP adapter, the HTTP router and ``bind_tasks``, which await
    that twin, answer with the names as a direct call does. The task keeps its name, module,
    docstring, signature and annotations, and so a tool's schema and a route's.

    The codes are read from the call's arguments, defaults applied, once the task returned:

    - ``None`` names nothing: the task asked for every country;
    - a text is one code, and a list, a tuple or a set holds several, since several values
      of one filter are a list (ADR-0061, decision 1); an enum member is read by its value;
    - a text of digits is read as the integer for a list of integer codes, and an integer as
      its text for a list of text codes, as a task whose parameter takes upstream's text or
      its integers sends them;
    - each code stands once, under its text as the caller gave it, with the name its list
      holds, runs of white space collapsed as a refusal shows it.

    Names the answer carries already are kept, those of its records or of a composed answer
    say, beside the decorator's own, which take a code's place where both name it, so two
    decorators stack. The task checks its codes before the call with its own hints and
    reason, so a code the list lacks never reaches the decorator; one that does, sent
    unchecked, is refused with ``check``'s refusal, its reason saying that upstream was asked
    and that the answer is withheld, and without ``Nothing was sent.``, the sentence of a
    refusal before the call (ADR-0045, amendment 2026-11-24). What the task raises passes as
    raised, and the answer's own object is not changed.

    Args:
        **codes: Each code parameter of the task to the list that names its codes, e.g.
            ``country_code=COUNTRIES``.

    Returns:
        The decorator, which returns the task wrapped.

    Raises:
        TypeError: No parameter is named, a value is no ``PackagedCodes``, and, when the
            task is decorated, a name is no parameter of it, or its ``**`` parameter, or is
            named by a decorator of the task already; a decorated task's answer that is no
            ``Result``.
        UnknownCode: A code that its list lacks reached the answer.
        InvalidRequestError: A value that is neither a code of its list's type nor its
            digits or its text reached the answer.
    """
    if not codes:
        raise TypeError("names_codes names no parameter")
    for param, listed in codes.items():
        if not isinstance(cast(object, listed), PackagedCodes):  # a caller mypy does not check
            kind = type(listed).__name__
            raise TypeError(
                "names_codes takes a PackagedCodes per parameter, PackagedList.codes(...), and "
                f"{param} is {_article(kind)} {kind}"
            )
    declared = MappingProxyType(dict(codes))

    def decorate(task: F) -> F:
        return cast(F, _naming(task, declared))

    return decorate


def _naming(task: Callable[..., Any], codes: Mapping[str, PackagedCodes]) -> Callable[..., Any]:
    """``task`` wrapped to name its codes; see ``names_codes``."""
    signature = inspect.signature(task)
    name = getattr(task, "__name__", repr(task))
    parameters = signature.parameters
    for param in codes:
        found = parameters.get(param)
        if found is None:
            raise TypeError(
                f"names_codes names {param}, which {name} does not take: it takes "
                f"{_and(list(parameters)) or 'no parameter'}"
            )
        if found.kind is inspect.Parameter.VAR_KEYWORD:
            raise TypeError(
                f"names_codes names {param}, the **{param} of {name}, which holds no code by "
                "its name"
            )
    inner = _named_parameters(task)
    twice = [param for param in codes if param in inner]
    if twice:
        raise TypeError(f"names_codes names {_and(twice)} of {name} twice")

    def answer(result: object, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        return _with_names(result, name, signature.bind(*args, **kwargs), codes)

    wrapper: Callable[..., Any]
    if inspect.iscoroutinefunction(task):

        @functools.wraps(task)
        async def named_async(*args: Any, **kwargs: Any) -> Any:
            return answer(await task(*args, **kwargs), args, kwargs)

        wrapper = named_async
    else:

        @functools.wraps(task)
        def named(*args: Any, **kwargs: Any) -> Any:
            return answer(task(*args, **kwargs), args, kwargs)

        twin = getattr(task, "async_fn", None)  # a sync facade's, which the adapters await
        if twin is not None and inspect.iscoroutinefunction(twin):
            named.async_fn = _naming(twin, codes)  # type: ignore[attr-defined]
        wrapper = named
    setattr(wrapper, _DECLARED, MappingProxyType({**inner, **codes}))
    return wrapper


def _named_parameters(fn: Callable[..., Any]) -> dict[str, PackagedCodes]:
    """The parameters of ``fn`` that ``names_codes`` names, each with its list.

    Read from ``fn`` and each ``__wrapped__`` below it, as ``functools.wraps`` leaves them,
    so a ``sync`` facade of a decorated async function, a decorated facade and two stacked
    decorators all count, and a parameter named twice is refused.
    """
    found: dict[str, PackagedCodes] = {}
    seen: set[int] = set()
    layer: Any = fn
    while layer is not None and id(layer) not in seen:
        seen.add(id(layer))
        for param, listed in getattr(layer, _DECLARED, {}).items():
            found.setdefault(param, listed)
        layer = getattr(layer, "__wrapped__", None)
    return found


def _with_names(
    result: object,
    task: str,
    call: inspect.BoundArguments,
    codes: Mapping[str, PackagedCodes],
) -> Result[Any]:
    """``result`` with the names of the codes of ``call`` in its ``meta.names``."""
    if not isinstance(result, Result):
        kind = type(result).__name__
        raise TypeError(
            f"{task} returned {_article(kind)} {kind}, not a Result: names_codes names the codes "
            "of an answer's meta (conventions §4, ADR-0067)"
        )
    call.apply_defaults()
    named: dict[str, dict[str, str]] = {}
    for param, listed in codes.items():
        found: dict[str, str] = {}
        for member in _codes_in(call.arguments.get(param)):
            text, label = _name(param, member, listed)
            found.setdefault(text, label)
        if found:
            named[param] = {**result.meta.names.get(param, {}), **found}
    if not named:
        return result
    meta = result.meta
    fields = {field: getattr(meta, field) for field in type(meta).model_fields}
    fields["names"] = {**meta.names, **named}
    return result.model_copy(update={"meta": type(meta)(**fields)})


def _name(param: str, member: object, listed: PackagedCodes) -> tuple[str, str]:
    """``member``'s text as given and the name ``listed`` holds for it, or the list's refusal."""
    text, read = _code(member, listed.integer)
    refusal = listed._refusal(  # a code the list lacks withholds the answer, upstream asked
        param, read, hints=None, otherwise=None, strategy=None, reason=_WITHHELD, asked=True
    )
    if refusal is not None:
        raise refusal
    return text, " ".join((listed.name_of(read) or text).split()) or text


def _article(word: str) -> str:
    return "an" if word[:1].lower() in set("aeiou") else "a"


def _and(words: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``; empty for no word."""
    if len(words) < 2:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def _plain(value: object) -> object:
    """``value``, an enum member read by its value."""
    return value.value if isinstance(value, Enum) else value


def _hint(plain: object, hints: Mapping[str, str] | None) -> str | None:
    """The text ``hints`` holds for ``plain``, read stripped and without case.

    A hint is for a value that is no code, whatever the list's type (ADR-0045, decision 3):
    ``"all"`` for integer codes, or ``0`` for text codes by its text ``"0"``. A value that
    is neither text nor an integer reads none.
    """
    if not hints or isinstance(plain, bool) or not isinstance(plain, str | int):
        return None
    table = {key.strip().casefold(): text for key, text in hints.items()}
    return table.get(str(plain).strip().casefold())


def _named(pairs: Iterable[tuple[Any, str]]) -> str:
    """Codes as ``UnknownCode`` names them: ``R01 (North)``, a code named by itself once."""
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


def closest(value: str, codes: Mapping[str, str], *, n: int = 3) -> list[tuple[str, str]]:
    """Up to ``n`` known codes close to ``value``: by code first, then by upstream name.

    Two ``difflib.get_close_matches`` passes: ``value`` upper-cased against the codes,
    then ``value`` lower-cased against the lower-cased names, each code named once, best
    match first, each match at ``difflib``'s own similarity of 0.6 or more. An agent that
    passes ``"r1"`` for ``"R1"`` or ``"north"`` for ``"R1"`` is led to the code. For
    ``UnknownCode``'s ``closest``; ``nearest`` matches integer codes by number instead.

    Args:
        value: The value given, e.g. ``"north"``.
        codes: Upstream's code to its name, e.g. ``{"R1": "North"}``, or each value to
            itself for a list of bare values, e.g. ``{"VA": "VA"}``.
        n: The most pairs returned.

    Returns:
        ``(code, name)`` pairs, e.g. ``[("R1", "North")]``; empty when none is close.

    Raises:
        ValueError: ``n`` is less than 1, as ``difflib`` refuses it.
    """
    found = difflib.get_close_matches(value.upper(), list(codes), n=n)
    by_name = {name.lower(): code for code, name in codes.items()}
    found += [
        by_name[name]
        for name in difflib.get_close_matches(value.lower(), list(by_name), n=n)
        if by_name[name] not in found
    ]
    return [(code, codes[code]) for code in found[:n]]


def nearest[K: (int, str)](
    value: int, codes: Mapping[K, str], *, n: int = 3
) -> list[tuple[K, str]]:
    """Up to ``n`` known integer codes nearest to ``value`` by number, nearest first.

    For integer codes, where a code close in number is likelier the one meant than a code
    close in spelling: ``999`` among ``902``, ``1001`` and ``104`` names ``1001``, then
    ``902``, then ``104``. Of two codes equally near, the lower comes first. A code keyed
    by its text, such as ``"10"``, is compared as the integer it writes and returned as
    given. For ``UnknownCode``'s ``closest``, as ``closest`` is for codes
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
