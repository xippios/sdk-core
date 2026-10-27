# ADR-0008: Hardening core from the first source package

Status: Accepted · Date: 2026-10-22

## Context

`sdk-usda-nass` was built on `xippios-core` with the three API-shaped tasks, packaged
reference data and four task-shaped slices. Four things the package had to write itself
are generic, and one behaviour was a surprise:

1. `Decimal` fields serialised as JSON strings in both adapters, so an agent read
   `"value": "98"`.
2. Two endpoint wrappers repeated the same sequence to map upstream's documented error
   bodies: request without raising, inspect status and body, raise the mapped error,
   fall back to the default mapping, parse JSON with `ValidationError` wrapping.
3. Four projection models each carried a hand-written field-by-field constructor and
   an identical fidelity test.
4. Parsing a published value (thousands separators, suppression codes) existed twice,
   and the refresh script generated `StrEnum` source from value lists in a way every
   source will need.

## Decision

- **JSON numbers.** `UpstreamModel` serialises `Decimal` as a JSON number in JSON mode.
  Python keeps the `Decimal`; the wire loses only precision JSON could not carry.
- **Error classifier.** `ClientConfig.classify` is an optional callable from a
  response to a taxonomy error or `None`. The client calls it on every response, before
  the default status mapping, unless the caller asked for the raw response
  (`raise_on_error=False`). Sources state their documented error shapes there once.
- **Projections.** `UpstreamModel.project(source, **overrides)` builds a model from
  another model's same-named fields; overrides are for parsing only.
  `xippios.core.testing.assert_projection` checks fidelity.
- **Helpers.** `xippios.core.parse_decimal` (separators, suppression codes → `None`);
  `xippios.core.reference.render_str_enums` and `enum_member_name` for generated enums;
  `xippios.core.testing.mcp_call` for end-to-end tool tests.
- **Template.** Generated repositories get the refresh-script scaffold wired to the
  enum helper, a `params` module for packaged lists, and adapter tests that assert the
  route methods and the tool schemas. Nothing source-specific is scaffolded.

## Consequences

- The next source writes no error-mapping boilerplate, no projection constructors and
  no enum generator, and its numbers arrive as numbers.
- `classify` makes the wrapper layer thinner, which ADR-0001 wants; the classifier is
  the one place a reviewer checks against `docs/upstream/`.
- A `Decimal` that needs exact transport would need a string field by design; none of
  the family's sources has one.

Followed up by ADR-0015 (2026-10-24): before a 429 or 5xx is retried, the client also
asks `classify`, for a raw response (`raise_on_error=False`) too, and its answer can
set the wait or end the retries.

## Amendment 2026-10-24

The enum renderers guarantee a generated `enums.py` that is committed as rendered.
`render_str_enums` writes each value as `ascii()` writes it, so a quote, a backslash, a
control character and every character outside ASCII is escaped, where a quote or a
backslash broke the file; lays out a member too long for 100 columns as ruff formats it,
the value in parentheses on a line of its own and, too long even there, split into
implicitly concatenated parts; and writes `__all__` sorted in ruff's order (RUF022), one
name per line, so a source's own lines do not conflict on `copier update`. The module
passes `ruff format --check` and `ruff check` under the family's configuration with no
exemption, where sdk-comtrade had to format it after every refresh. The whole module is
ASCII-only, trading readable accents (`C\xf4te`) for stability across ruff versions:
values are escaped, and a key, a class name, a fetch date or a generator text that is
not printable ASCII, or holds a backslash or three double quotes, is refused, so no ruff
version can find an ambiguous character in it (RUF001, RUF002), and the values are the
same at runtime. A member name that fits no line of 100 columns, or a value with nothing
to derive one from, is refused with `ValueError`, and the source's refresh script names
that member once in the renderers' `member_names`. An upstream whose ids are integers
renders `IntEnum`, not the `StrEnum` default: `render_int_enums` takes `(id, name)`
pairs, which `id_name_pairs` builds from upstream's records, takes member names from the
names and appends `_<id>` to a name several ids share. Fidelity wins over the default,
because upstream's data carries the ids as integers, which a `StrEnum` of their digits
never equals, and its names are not unique (PSD's "Total Disappearance" is both
attribute 126 and 173). sdk-usda-psd ruled this on 2026-10-23 and rendered its
`AttributeId` and `UnitId` in its own refresh script; conventions §3 states the rule
from 1.12 on.

Amended 2026-10-27 (core 0.3.0; the family review's C7, decided by Johannes on 2026-10-27;
queue rows 31 c and 32 b, found by sdk-template, and 39 c, found by sdk-usda-gats): the
amendment of 2026-10-24 no longer holds where it reproduces ruff's layout or splits the
renderers. One `render_enums(lists, *, fetched, class_names=None, member_names=None,
generator=...)` replaces `render_str_enums` and `render_int_enums` and infers the kind per
list: a list of strings renders a `StrEnum`, a list of `(id, name)` pairs, as
`id_name_pairs` builds them, an `IntEnum` with `_<id>` appended to a name several ids
share, so one module holds both; an empty list is refused. `fetched` is one date for the
module or one per list. Each class docstring is one line, "Values of ``<key>`` (fetched
<date>).", and since it reaches an MCP tool's input schema through the parameter type it
holds what an agent needs; a maintainer's note goes into a comment. The output is plain:
values as `ascii()` writes them, so the module stays ASCII-only and the values the same at
runtime; one member per line; `__all__` one name per line in the order of the lists; the
import names the kinds the module needs; a line over 100 columns carries `# noqa: E501`,
since no tool can shorten upstream's value. The quote choice, the parentheses, the RUF022
order, the docstring wrapping, the string splitting and the refusal of a member name too
long for a line go. A key, a class name, a date or a generator text that is not printable
ASCII, or holds a backslash or three double quotes, is still refused, and so is a class
name longer than 84 characters, whose `class` line `ruff format` cannot shorten. The
refresh script, the template's, runs `ruff format && ruff check --fix` after rendering,
which choose the quotes, wrap what fits, drop a `# noqa` the wrapping made unused (RUF100)
and sort `__all__` (RUF022, whose fix applies to an `__all__` without comments), and the
module is committed as formatted. Every source re-renders at its 0.3.0 adoption through
the template's script (ADR-0023, decision 5). Conventions §3, §8 and §15 item 6 state it
from 1.20 on.
