"""Loader for reference data packaged with a source (conventions §3).

Files live in ``<package>/reference/`` as CSV or JSON and ship inside the wheel. File
contents are cached per process; callers get fresh objects on every call.

The renderers write a source's generated ``enums.py``: ``StrEnum`` for value lists,
``IntEnum`` for lists of integer ids and names (conventions §3, ADR-0008). Their output is
ASCII, what ``ruff format`` would write, and passes ``ruff check`` under the family's
configuration; a member name too long for any line is refused, not rendered.
"""

import csv
import functools
import io
import json
import keyword
import re
import textwrap
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
"""The family's ``line-length``, which every line of a generated module keeps."""

_NAME_LIMIT = _LINE_LENGTH - len("    ") - len(" = (")
"""The longest member name, in columns, for which ``    NAME = (`` still fits a line."""


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


def _class_name(key: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^A-Za-z0-9]+", key) if part)


def _escaped(char: str, quote: str) -> str:
    r"""``char`` inside a literal delimited by ``quote``, as ``ascii()`` writes it.

    Every character outside ASCII becomes an escape (``\xf4``, ``\u2019``,
    ``\U0001d400``), the quote and a backslash are escaped, and the rest stays as it is:
    the literal is ASCII, which no version of ruff flags as ambiguous.
    """
    return "\\" + char if char == quote else ascii(char)[1:-1]


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
    widths = [len(_escaped(char, '"')) + (char == "'") for char in value]
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
    ``name`` is at most ``_NAME_LIMIT`` columns wide, so ``name = (`` fits.
    """
    line = f"    {name} = {literal}"
    if len(line) <= _LINE_LENGTH:
        return [line]
    if len(f"        {literal}") <= _LINE_LENGTH:
        return [f"    {name} = (", f"        {literal}", "    )"]
    if value is None:
        return [line]
    return [f"    {name} = (", *(f"        {part}" for part in _parts(value)), "    )"]


def _derived(text: str) -> str | None:
    """``enum_member_name(text)``, or ``None`` when ``text`` has nothing to derive it from."""
    try:
        return enum_member_name(text)
    except ValueError:
        return None


def _acceptable(member: str) -> bool:
    """Whether ``member`` is an ASCII identifier that an enum takes as a member.

    An enum refuses ``mro`` and ``_sunder_`` names and does not make a member of a name
    that starts with ``__``; a keyword is no identifier to assign to.
    """
    sunder = len(member) > 2 and member[0] == member[-1] == "_"
    return (
        member.isascii()
        and member.isidentifier()
        and not keyword.iskeyword(member)
        and not member.startswith("__")
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
            accepts, two names collide, or a name is too long for a line
            (``_NAME_LIMIT``).
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
    for member in members:
        if not _acceptable(member):
            raise ValueError(f"{key}: {member!r} is not a member name an enum accepts")
    if len(set(members)) != len(members):
        colliding = sorted(name for name, count in Counter(members).items() if count > 1)
        raise ValueError(f"{key}: member names collide: {colliding}")
    for index, (member, label) in enumerate(zip(members, labels, strict=True)):
        if len(member) > _NAME_LIMIT:
            raise ValueError(
                f"{key}: the member name for {label} at position {index} is {len(member)} "
                f"characters long; at most {_NAME_LIMIT} fit a line of {_LINE_LENGTH} "
                f"columns; {hint}"
            )
    return members


def _unknown_keys(member_names: Mapping[str, object], lists: Mapping[str, object]) -> None:
    unknown = sorted(set(member_names) - set(lists))
    if unknown:
        raise ValueError(f"member_names names lists that are not rendered: {unknown}")


def _natural(left: str, right: str) -> int:
    """Ruff's natural order of two names (the ``natord`` crate), as -1, 0 or 1.

    Characters compare as they are. Where both names reach an ASCII digit, the two digit
    runs compare as numbers, the longer run being the greater; a run that starts with
    ``0`` on either side compares digit by digit from the left instead, so ``Code05``
    comes before ``Code1``, ``Code001`` before ``Code1`` and ``B0`` before ``B00``.
    """
    digits = "0123456789"
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] in digits and right[j] in digits:
            leading_zero = "0" in (left[i], right[j])
            bias = 0
            while i < len(left) and j < len(right) and left[i] in digits and right[j] in digits:
                if left[i] != right[j]:
                    if leading_zero:
                        return -1 if left[i] < right[j] else 1
                    bias = bias or (-1 if left[i] < right[j] else 1)
                i, j = i + 1, j + 1
            more_left = i < len(left) and left[i] in digits
            more_right = j < len(right) and right[j] in digits
            if more_left != more_right:
                return 1 if more_left else -1
            if bias:
                return bias
        elif left[i] != right[j]:
            return -1 if left[i] < right[j] else 1
        else:
            i, j = i + 1, j + 1
    return (i < len(left)) - (j < len(right))


def _kind(name: str) -> int:
    """Ruff's groups for ``__all__``: constants (``HS``), classes (``Hs``), the rest."""
    return 0 if len(name) > 1 and name.isupper() else 1 if name[:1].isupper() else 2


def _all_order(left: str, right: str) -> int:
    """Ruff's order for ``__all__`` (RUF022): by group, then natural, as -1, 0 or 1."""
    return (_kind(left) > _kind(right)) - (_kind(left) < _kind(right)) or _natural(left, right)


def _class_docstring(key: str, fetched: str | None) -> list[str]:
    """The docstring of the class for ``key``, on one line where it fits.

    Where the fetch date would push it past the line, it moves into a paragraph of its
    own, wrapped as the module docstring is.

    Raises:
        ValueError: When the key is too long for the summary line on its own.
    """
    when = f" (fetched {fetched})" if fetched else ""
    line = f'    """Values of ``{key}``{when}."""'
    if len(line) <= _LINE_LENGTH:
        return [line]
    summary = f'    """Values of ``{key}``."""'
    if len(summary) > _LINE_LENGTH:
        limit = _LINE_LENGTH - len(summary) + len(key)
        raise ValueError(
            f"key {key!r} is {len(key)} characters long; at most {limit} fit its class "
            f"docstring on a line of {_LINE_LENGTH} columns"
        )
    paragraph = textwrap.wrap(
        f"Fetched {fetched}.",
        _LINE_LENGTH,
        initial_indent="    ",
        subsequent_indent="    ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [summary[:-3], "", *paragraph, '    """']


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
    names = sorted((name for name, _ in classes), key=functools.cmp_to_key(_all_order))
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
    member_names: Mapping[str, Mapping[str, str]] | None = None,
    fetched: str | None = None,
    generator: str = "the reference refresh script",
) -> str:
    r"""Python source for one ``StrEnum`` per value list, formatted as ruff formats it.

    Member names come from ``enum_member_name``, or from ``member_names`` where a source
    names a member by hand. Values are the upstream strings, verbatim, each written as
    ``ascii()`` writes it: a quote, a backslash or a control character is escaped, and so is
    every character outside ASCII (``"Côte"`` as ``"C\xf4te"``, a typographic apostrophe as
    ``\u2019``), in double quotes unless single quotes need fewer escapes. The generated
    module is ASCII, so no version of ruff finds an ambiguous character in it (RUF001), and
    the value is the same at runtime; accents are traded for that stability. A member too
    long for a line of 100 columns is laid out as ruff lays it out: the value in parentheses
    on a line of its own, and a value too long for that line split into implicitly
    concatenated parts. ``__all__`` names the classes sorted as ruff sorts it (RUF022), one
    per line; the classes keep the order of ``lists``.

    The result passes ``ruff format --check`` and ``ruff check`` unchanged. A member name
    longer than 92 columns fits no line, so it is refused: the source's refresh script
    names that member once in ``member_names``. Generated code is the only way enums
    enter a source package, so this module is the one place the rendering lives.

    Args:
        lists: Enum key (``"state_alpha"``) to its values, in upstream order.
        class_names: Class name per key; default ``StateAlpha`` for ``state_alpha``.
        member_names: Member names set by hand, per key and value, for a value whose
            derived name is too long or collides, or that has none (an empty or a
            non-Latin label), e.g.
            ``{"short_desc": {"CORN, GRAIN, ... ALL PRACTICES": "CORN_GRAIN_ALL"}}``. Taken
            before any name is derived; each must be an identifier an enum accepts and
            unique in its list.
        fetched: Date to mention in each class docstring, in a paragraph of its own
            where the summary line would grow past 100 columns.
        generator: What to name as the generator in the module docstring.

    Raises:
        ValueError: When two members of one list share a name, a member name is longer
            than 92 columns (naming the key, its length and the limit), a value without
            an override has nothing to derive a name from (naming the key and the
            position), a key is longer than the 75 characters its class docstring has
            room for, or a name in ``member_names`` is no ASCII identifier, one ``enum``
            does not take (``mro``, ``__x``, ``_x_``), or for a key or a value that
            ``lists`` does not hold.
    """
    _unknown_keys(member_names or {}, lists)
    names = {key: (class_names or {}).get(key, _class_name(key)) for key in lists}
    classes: list[tuple[str, list[str]]] = []
    for key, values in lists.items():
        derived = [_derived(value) for value in values]
        labels = [repr(value) for value in values]
        overrides = (member_names or {}).get(key, {})
        members = _member_names(key, values, derived, labels, overrides)
        body = [f"class {names[key]}(StrEnum):", *_class_docstring(key, fetched), ""]
        for member, value in zip(members, values, strict=True):
            body += _member(member, _literal(value), value)
        classes.append((names[key], body))
    return _module(
        "StrEnum",
        "StrEnums for packaged value lists (conventions, section 3).",
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
    member_names: Mapping[str, Mapping[int, str]] | None = None,
    fetched: str | None = None,
    generator: str = "the reference refresh script",
) -> str:
    """Python source for one ``IntEnum`` per list of integer ids, formatted as ruff formats it.

    For an upstream whose ids are integers (conventions §3): an ``IntEnum`` member
    compares equal to the id in upstream's data, where a ``StrEnum`` of its digits would
    not. Values are the ids, in upstream order; member names come from the names through
    ``enum_member_name``, and a name several ids share gets ``_<id>`` appended
    (``TOTAL_DISAPPEARANCE_126``, ``TOTAL_DISAPPEARANCE_173``); ``member_names`` names a
    member by hand and leaves every other member's name as it was. Layout, ``__all__`` and
    the refusal of a member name longer than 92 columns as in ``render_str_enums``; the
    values are integers, so no character needs escaping. ``id_name_pairs`` builds the
    pairs from upstream's records.

    Args:
        lists: Enum key (``"attributeId"``) to its ``(id, name)`` pairs, in upstream order,
            e.g. ``[(4, "Area Harvested"), (20, "Beginning Stocks")]``.
        class_names: Class name per key; default ``Attributeid`` for ``attributeId``, so a
            camelCase key wants one (``{"attributeId": "AttributeId"}``).
        member_names: Member names set by hand, per key and id, for an id whose derived
            name is too long or collides, or whose name has none, e.g.
            ``{"attributeId": {173: "TOTAL_USE"}}``. Taken before any name is derived;
            each must be an identifier an enum accepts and unique in its list.
        fetched: Date to mention in each docstring.
        generator: What to name as the generator in the module docstring.

    Raises:
        ValueError: When an id is listed twice (naming the key and the id), two members of
            one list still share a name after the suffix, a suffix makes no identifier (a
            negative id), a member name is longer than 92 columns, a name without an
            override has nothing to derive one from, a key is longer than 75 characters, or
            a name in ``member_names`` is no ASCII identifier, one ``enum`` does not take
            (``mro``, ``__x``, ``_x_``), or for a key or an id that ``lists`` does not hold.
    """
    _unknown_keys(member_names or {}, lists)
    names = {key: (class_names or {}).get(key, _class_name(key)) for key in lists}
    classes: list[tuple[str, list[str]]] = []
    for key, pairs in lists.items():
        repeated = sorted(
            ident for ident, count in Counter(i for i, _ in pairs).items() if count > 1
        )
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
        overrides = (member_names or {}).get(key, {})
        members = _member_names(key, ids, derived, labels, overrides)
        body = [f"class {names[key]}(IntEnum):", *_class_docstring(key, fetched), ""]
        for member, (ident, _) in zip(members, pairs, strict=True):
            body += _member(member, f"{ident:d}")
        classes.append((names[key], body))
    return _module(
        "IntEnum",
        "IntEnums for packaged id lists (conventions, section 3).",
        [
            f"Generated by {generator}; do not edit by hand. Values are upstream's integer ids; "
            "member names are derived from upstream's names, with ``_<id>`` appended where "
            "several ids share a name.",
            "Upstream's ids are integers, so these are ``IntEnum``, not ``StrEnum``: a member "
            "compares equal to the id in upstream's data, where a string of its digits would "
            "not (conventions, section 3).",
        ],
        classes,
    )
