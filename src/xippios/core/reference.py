"""Loader for reference data packaged with a source (conventions §3).

Files live in ``<package>/reference/`` as CSV or JSON and ship inside the wheel. File
contents are cached per process; callers get fresh objects on every call.

The renderers write a source's generated ``enums.py``: ``StrEnum`` for value lists,
``IntEnum`` for lists of integer ids and names (conventions §3, ADR-0008). Their output is
what ``ruff format`` would write and passes ``ruff check`` under the family's
configuration, but for the two edges ``render_str_enums`` names.
"""

import csv
import functools
import io
import json
import re
import textwrap
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from importlib import resources
from typing import Any, cast

from pydantic import TypeAdapter

__all__ = [
    "enum_member_name",
    "id_name_pairs",
    "load_csv",
    "load_json",
    "load_table",
    "render_int_enums",
    "render_str_enums",
]

_LINE_LENGTH = 100
"""The family's ``line-length``, which every line of a generated module keeps where it can."""


@functools.cache
def _read_text(package: str, name: str) -> str:
    path = resources.files(package).joinpath("reference", name)
    if not path.is_file():
        raise FileNotFoundError(f"reference file {name!r} not found in package {package!r}")
    return path.read_text(encoding="utf-8")


def load_csv(package: str, name: str) -> list[dict[str, str]]:
    """Rows of a packaged CSV file as dicts keyed by the header row.

    Args:
        package: Import path of the source package, e.g. ``"xippios.usda_nass"``.
        name: File name under ``reference/``, e.g. ``"commodities.csv"``.
    """
    rows = csv.DictReader(io.StringIO(_read_text(package, name)))
    return [cast(dict[str, str], dict(row)) for row in rows]


def load_json(package: str, name: str) -> Any:
    """Decoded contents of a packaged JSON file.

    Args:
        package: Import path of the source package, e.g. ``"xippios.usda_nass"``.
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
    """
    raw = load_csv(package, name) if name.endswith(".csv") else load_json(package, name)
    return TypeAdapter(list[model]).validate_python(raw)  # type: ignore[valid-type]


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
    """``(id, name)`` pairs from upstream's records, in upstream order, for ``render_int_enums``.

    Args:
        records: Upstream's records under upstream's field names, e.g. PSD's
            ``commodityAttributes``.
        id_field: The field holding the integer id, e.g. ``"attributeId"``; an ``int`` or
            a string of ASCII digits (``"28"``).
        name_field: The field holding the name, a string, e.g. ``"attributeName"``.

    Raises:
        ValueError: When a record lacks a field, its id is not an integer, or its name
            is not a string. The message names the field and the record's position,
            never the record.
    """
    pairs: list[tuple[int, str]] = []
    for index, record in enumerate(records):
        for field in (id_field, name_field):
            if field not in record:
                raise ValueError(f"record {index} has no field {field!r}")
        ident, name = record[id_field], record[name_field]
        if isinstance(ident, str) and ident.isascii() and ident.isdigit():
            ident = int(ident)
        if not isinstance(ident, int) or isinstance(ident, bool):
            raise ValueError(f"record {index}: field {id_field!r} is not an integer id")
        if not isinstance(name, str):
            raise ValueError(f"record {index}: field {name_field!r} is not a string")
        pairs.append((ident, name))
    return pairs


def _class_name(key: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", key) if part)


def _width(text: str) -> int:
    """Columns ``text`` takes as ruff counts them: wide characters two, combining marks none."""
    return sum(
        0
        if unicodedata.category(char) in ("Mn", "Me")
        else 2
        if unicodedata.east_asian_width(char) in ("W", "F")
        else 1
        for char in text
    )


def _escaped(char: str, quote: str) -> str:
    """``char`` inside a literal delimited by ``quote``: ``repr()``'s escape, the quote escaped."""
    return "\\" + char if char == quote else repr(char)[1:-1]


def _literal(value: str) -> str:
    """``value`` as ruff writes a string: double quotes, single where they need fewer escapes."""
    quote = "'" if value.count('"') > value.count("'") else '"'
    return quote + "".join(_escaped(char, quote) for char in value) + quote


def _parts(value: str) -> list[str]:
    """``value`` as literals of at most 90 columns each, cut after a space where one is near.

    90 columns leave room for the indent of eight and the quotes. Widths are counted as
    though every quote needed its escape, since each part picks its own quotes.
    """
    budget = _LINE_LENGTH - 10
    widths = [_width(repr(char)[1:-1]) + (char in "'\"") for char in value]
    parts: list[str] = []
    start, used, space = 0, 0, -1
    for index, width in enumerate(widths):
        if used + width > budget:
            head = sum(widths[start : space + 1]) if space >= start else 0
            cut = space + 1 if head >= budget // 2 else index
            parts.append(value[start:cut])
            start, space = cut, -1
            used = sum(widths[start:index])
        used += width
        if value[index] == " ":
            space = index
    parts.append(value[start:])
    return [_literal(part) for part in parts]


def _member(name: str, literal: str, value: str | None = None) -> list[str]:
    """``name = literal`` in a class body, laid out as ruff formats it.

    A literal too long for the line moves into parentheses on a line of its own; a string
    too long even there (``value`` given) is split into implicitly concatenated parts.
    Where ``name = (`` itself is too long, nothing can shorten the line and it stays one.
    """
    line = f"    {name} = {literal}"
    if _width(line) <= _LINE_LENGTH or _width(f"    {name} = (") > _LINE_LENGTH:
        return [line]
    if _width(f"        {literal}") <= _LINE_LENGTH:
        return [f"    {name} = (", f"        {literal}", "    )"]
    if value is None:
        return [line]
    return [f"    {name} = (", *(f"        {part}" for part in _parts(value)), "    )"]


def _all_order(name: str) -> tuple[int, list[str | int]]:
    """Ruff's order for ``__all__`` (RUF022): constants, classes, the rest; each natural."""
    kind = 0 if len(name) > 1 and name.isupper() else 1 if name[:1].isupper() else 2
    pieces = re.split("([0-9]+)", name)
    return kind, [int(piece) if index % 2 else piece for index, piece in enumerate(pieces)]


def _module(
    kind: str, summary: str, paragraphs: Sequence[str], classes: Sequence[tuple[str, list[str]]]
) -> str:
    """A generated module: docstring, import, sorted ``__all__`` one per line, the classes."""
    lines = [f'"""{summary}']
    for paragraph in paragraphs:
        lines += [
            "",
            *textwrap.wrap(paragraph, _LINE_LENGTH, break_long_words=False, break_on_hyphens=False),
        ]
    lines += ['"""', ""]
    if classes:
        lines += [f"from enum import {kind}", ""]
    names = sorted((name for name, _ in classes), key=_all_order)
    if names:
        lines += ["__all__ = [", *(f'    "{name}",' for name in names), "]"]
    else:
        lines.append("__all__ = []")
    for _, body in classes:
        lines += ["", "", *body]
    return "\n".join(lines) + "\n"


def render_str_enums(
    lists: Mapping[str, Sequence[str]],
    *,
    class_names: Mapping[str, str] | None = None,
    fetched: str | None = None,
    generator: str = "the reference refresh script",
) -> str:
    """Python source for one ``StrEnum`` per value list, formatted as ruff formats it.

    Member names come from ``enum_member_name``; values are the upstream strings,
    verbatim, each written through ``repr()``, so a quote, a backslash or a control
    character is escaped, in double quotes unless single quotes need fewer escapes. A
    member too long for a line of 100 columns is laid out as ruff lays it out: the value
    in parentheses on a line of its own, and a value too long for that line split into
    implicitly concatenated parts. ``__all__`` names the classes sorted as ruff sorts it
    (RUF022), one per line; the classes keep the order of ``lists``.

    The result passes ``ruff format --check`` and ``ruff check`` unchanged, with two
    edges: a member name too long for a line of its own cannot be shortened (E501), and a
    value holding a character ruff calls ambiguous, such as a typographic apostrophe
    (U+2019) or an en dash (U+2013), trips RUF001.
    Generated code is the only way enums enter a source package, so this module is the
    one place the rendering lives.

    Args:
        lists: Enum key (``"state_alpha"``) to its values, in upstream order.
        class_names: Class name per key; default ``StateAlpha`` for ``state_alpha``.
        fetched: Date to mention in each docstring.
        generator: What to name as the generator in the module docstring.

    Raises:
        ValueError: When two values of one list map to the same member name.
    """
    names = {key: (class_names or {}).get(key, _class_name(key)) for key in lists}
    when = f" (fetched {fetched})" if fetched else ""
    classes: list[tuple[str, list[str]]] = []
    for key, values in lists.items():
        members = [enum_member_name(value) for value in values]
        if len(set(members)) != len(members):
            raise ValueError(f"{key}: member names collide: {sorted(members)}")
        body = [f"class {names[key]}(StrEnum):", f'    """Values of ``{key}``{when}."""', ""]
        for member, value in zip(members, values, strict=True):
            body += _member(member, _literal(value), value)
        classes.append((names[key], body))
    return _module(
        "StrEnum",
        "StrEnums for packaged value lists (conventions §3).",
        [
            f"Generated by {generator}; do not edit by hand. Member names are derived from the "
            "values, values are upstream's."
        ],
        classes,
    )


def render_int_enums(
    lists: Mapping[str, Sequence[tuple[int, str]]],
    *,
    class_names: Mapping[str, str] | None = None,
    fetched: str | None = None,
    generator: str = "the reference refresh script",
) -> str:
    """Python source for one ``IntEnum`` per list of integer ids, formatted as ruff formats it.

    For an upstream whose ids are integers (conventions §3): an ``IntEnum`` member
    compares equal to the id in upstream's data, where a ``StrEnum`` of its digits would
    not. Values are the ids, in upstream order; member names come from the names through
    ``enum_member_name``, and a name several ids share gets ``_<id>`` appended
    (``TOTAL_DISAPPEARANCE_126``, ``TOTAL_DISAPPEARANCE_173``). Layout and ``__all__`` as
    in ``render_str_enums``. ``id_name_pairs`` builds the pairs from upstream's records.

    Args:
        lists: Enum key (``"attributeId"``) to its ``(id, name)`` pairs, in upstream order,
            e.g. ``[(4, "Area Harvested"), (20, "Beginning Stocks")]``.
        class_names: Class name per key; default ``Attributeid`` for ``attributeId``, so a
            camelCase key wants one (``{"attributeId": "AttributeId"}``).
        fetched: Date to mention in each docstring.
        generator: What to name as the generator in the module docstring.

    Raises:
        ValueError: When two members of one list still share a name after the suffix,
            or a suffix makes no identifier (a negative id).
    """
    names = {key: (class_names or {}).get(key, _class_name(key)) for key in lists}
    when = f" (fetched {fetched})" if fetched else ""
    classes: list[tuple[str, list[str]]] = []
    for key, pairs in lists.items():
        plain = [enum_member_name(name) for _, name in pairs]
        counts = Counter(plain)
        members = [
            name if counts[name] == 1 else f"{name}_{ident}"
            for name, (ident, _) in zip(plain, pairs, strict=True)
        ]
        if len(set(members)) != len(members):
            raise ValueError(f"{key}: member names collide: {sorted(members)}")
        invalid = [member for member in members if not member.isidentifier()]
        if invalid:
            raise ValueError(f"{key}: not identifiers: {invalid}")
        body = [f"class {names[key]}(IntEnum):", f'    """Values of ``{key}``{when}."""', ""]
        for member, (ident, _) in zip(members, pairs, strict=True):
            body += _member(member, f"{ident:d}")
        classes.append((names[key], body))
    return _module(
        "IntEnum",
        "IntEnums for packaged id lists (conventions §3).",
        [
            f"Generated by {generator}; do not edit by hand. Values are upstream's integer ids; "
            "member names are derived from upstream's names, with ``_<id>`` appended where "
            "several ids share a name.",
            "Upstream's ids are integers, so these are ``IntEnum``, not ``StrEnum``: a member "
            "compares equal to the id in upstream's data, where a string of its digits would "
            "not (conventions §3).",
        ],
        classes,
    )
