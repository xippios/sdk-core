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

``render_enums`` writes a source's generated ``enums.py``, ``StrEnum`` for a value list and
``IntEnum`` for a list of integer ids and names in one module (conventions §3, ADR-0031):
plain, ASCII-only Python that the refresh script formats with ``ruff format`` and
``ruff check --fix`` before it is committed.
"""

import difflib
import functools
import inspect
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
    "enum_member_name",
    "id_name_pairs",
    "load_json",
    "matches",
    "names_codes",
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


def load_json(package: str, name: str) -> Any:
    """Decoded contents of a packaged JSON file.

    Args:
        package: Import path of the source package, e.g. ``"xippios.usda.nass"``.
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
    "Upstream was asked, but an answer names the country of each code it is for, and the "
    "packaged list holds no name for this one, so the answer is withheld."
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
