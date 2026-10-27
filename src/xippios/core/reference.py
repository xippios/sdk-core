"""Loader for reference data packaged with a source (conventions §3).

Files live in ``<package>/reference/`` as CSV or JSON and ship inside the wheel. File
contents are cached per process; callers get fresh objects on every call.

A packaged list, the records of one upstream operation as the refresh script fetched
them, is a ``PackagedList``: it loads the file, builds the ``ResultMeta`` of an answer
from it (ADR-0022), parses its records and writes the file. ``matches`` is the ``search``
filter of the ``list_*`` tasks, ``closest`` finds the known codes near a value that
``UnknownCode`` refuses.

``render_enums`` writes a source's generated ``enums.py``, ``StrEnum`` for a value list and
``IntEnum`` for a list of integer ids and names in one module (conventions §3, ADR-0008):
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
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time
from importlib import resources
from pathlib import Path
from typing import Any, Self, cast

import pydantic
from pydantic import BaseModel, ConfigDict, TypeAdapter, field_validator

from xippios.core.errors import ValidationError
from xippios.core.models import ResultMeta, _validation_text, parse

__all__ = [
    "PackagedList",
    "closest",
    "enum_member_name",
    "id_name_pairs",
    "load_csv",
    "load_json",
    "load_table",
    "matches",
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
        ValidationError: A row does not fit ``model``; raised ``from None``, its text
            naming the package, the file and the first failure's location, type and
            message as ``parse``'s does, the rows on ``raw``.
    """
    raw = load_csv(package, name) if name.endswith(".csv") else load_json(package, name)
    try:
        return TypeAdapter(list[model]).validate_python(raw)  # type: ignore[valid-type]
    except pydantic.ValidationError as exc:
        message = f"{package} reference/{name}: {_validation_text(exc)}"
        raise ValidationError(message, raw=raw) from None


class PackagedList(BaseModel):
    """One packaged list, ``reference/<name>.json``: upstream's records as fetched.

    The file holds ``{"param", "endpoint", "fetched", "records"}`` and, where the source
    has one, ``"note"``. ``<name>`` is usually ``param``; two lists derived from one
    upstream parameter keep it as ``param`` in files of their own names. A list of
    values is records of one field named by the upstream parameter,
    ``[{"state_alpha": "AK"}, ...]``; a table is records of its columns. Any other key
    is refused (ADR-0022, amendment 2026-10-27). Instances are frozen.

    Attributes:
        param: The list, as upstream names it, e.g. ``"commodities"`` or
            ``"state_alpha"``.
        endpoint: The upstream operation the list was fetched from, an operationId or a
            URL path, e.g. ``"PSDData_GetCommodities"`` or
            ``"files/v1/app/reference/Reporters.json"``; never ``"reference"`` or a
            file of the package (ADR-0022, rule 1).
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
            pydantic.ValidationError: The file is not a packaged list.
        """
        file = name if name.endswith(".json") else f"{name}.json"
        return cls.model_validate(load_json(package, file))

    def meta(
        self,
        source: str,
        *,
        request: Mapping[str, Any] | None = None,
        vintage: str | None = None,
        published_at: datetime | None = None,
        published_at_naive: bool = False,
    ) -> ResultMeta:
        """The ``ResultMeta`` of an answer from this list (ADR-0022, rule 1).

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
    match first. An agent that passes ``"us"`` for ``"US"`` or ``"wheat"`` for
    ``"0410000"`` is led to the code. For ``UnknownCode``'s ``closest``.

    Args:
        value: The value given, e.g. ``"wheat"``.
        codes: Upstream's code to its name, e.g. ``{"0410000": "Wheat"}``.
        n: The most pairs returned.

    Returns:
        ``(code, name)`` pairs, e.g. ``[("0410000", "Wheat")]``; empty when none is close.
    """
    found = difflib.get_close_matches(value.upper(), list(codes), n=n)
    by_name = {name.lower(): code for code, name in codes.items()}
    found += [
        by_name[name]
        for name in difflib.get_close_matches(value.lower(), list(by_name), n=n)
        if by_name[name] not in found
    ]
    return [(code, codes[code]) for code in found[:n]]


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


def _fit(line: str) -> str:
    """``line``, with ``# noqa: E501`` when it is longer than the family's 100 columns.

    No tool can shorten an upstream value, a long key or a member name derived from a long
    label, so such a line is exempted, not refused; ruff drops the comment again where
    ``ruff format`` makes the line fit (RUF100).
    """
    return f"{line}  # noqa: E501" if len(line) > _LINE_LENGTH else line


def _class_name(key: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", key) if part)


def _unknown_keys(argument: str, given: Mapping[str, object], lists: Mapping[str, object]) -> None:
    unknown = sorted(set(given) - set(lists))
    if unknown:
        raise ValueError(f"{argument} names lists that are not rendered: {unknown}")


def _class_names(lists: Mapping[str, object], class_names: Mapping[str, str]) -> dict[str, str]:
    """The class name per key, once every key is known to fit a docstring.

    Raises:
        ValueError: A key is not ``_TEXT_RULE``; a class name is no ASCII identifier, is a
            keyword or is longer than ``_CLASS_NAME_LIMIT``; two keys get one class name.
            The message names the position.
    """
    names: dict[str, str] = {}
    for index, key in enumerate(lists):
        if not _plain_text(key):
            raise ValueError(f"the key at position {index} of lists must be {_TEXT_RULE}")
        given = class_names.get(key)
        name = _class_name(key) if given is None else given
        too_long = len(name) > _CLASS_NAME_LIMIT
        if not (name.isascii() and name.isidentifier()) or keyword.iskeyword(name) or too_long:
            where = (
                f"the class name derived from the key at position {index} of lists"
                if given is None
                else f"class_names for the key at position {index} of lists"
            )
            raise ValueError(
                f"{where} must be an ASCII identifier, not a keyword, of at most "
                f"{_CLASS_NAME_LIMIT} characters; set it in class_names"
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
            pairs of an ``int`` and a ``str``.
    """
    if isinstance(values, str) or not isinstance(values, Sequence) or not values:
        raise ValueError(f"{key}: a list of values or of (id, name) pairs is needed, not empty")
    if all(isinstance(item, str) for item in values):
        return "StrEnum"
    if all(_is_pair(item) for item in values):
        return "IntEnum"
    raise ValueError(
        f"{key}: the list mixes kinds; it holds strings (a StrEnum) or (id, name) pairs of an "
        "int and a str (an IntEnum), as id_name_pairs builds them"
    )


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

    The output is plain and ASCII-only (ADR-0008): a value is written as ``ascii()``
    writes it, so a quote, a backslash, a control character and every character outside
    ASCII is escaped (``"Côte"`` as ``'C\xf4te'``) and the value is the same at runtime;
    one member per line; ``__all__`` one name per line in the order of ``lists``; the
    import names the kinds the module needs. A line longer than 100 columns carries
    ``# noqa: E501``. The refresh script runs ``ruff format`` and ``ruff check --fix`` on
    the result, which choose the quotes, wrap what fits and sort ``__all__`` (RUF022); the
    module is committed as formatted.

    Args:
        lists: Enum key to its values in upstream order: strings
            (``{"state_alpha": ["AK", "AL"]}``) or ``(id, name)`` pairs
            (``{"attributeId": [(4, "Area Harvested"), (20, "Beginning Stocks")]}``).
        fetched: When the lists were fetched, as text: one date for the module
            (``"2026-10-27"``), or one per key (``{"state_alpha": "2026-10-27",
            "attributeId": "2026-10-23"}``) for lists fetched on different days.
        class_names: Class name per key; default ``StateAlpha`` for ``state_alpha`` and
            ``Attributeid`` for ``attributeId``, so a camelCase key wants one
            (``{"attributeId": "AttributeId"}``).
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
            double quotes; a class name is no ASCII identifier, is a keyword or is longer
            than 84 characters, or two lists get one; an id is listed twice; a value
            without an override has nothing to derive a member name from; two members of
            one list share a name; a name in ``member_names`` is not one an enum takes
            (``mro``, ``_x_``, any with ``__``); or ``fetched``, ``class_names`` or
            ``member_names`` names a key ``lists`` does not hold, ``fetched`` lacks one, or
            ``member_names`` names a value or an id its list does not hold. A message names
            the argument and the position.
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
                *(_fit(f"    {member} = {literal}") for member, literal in members),
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
