# ADR-0031: Hardening core from the first source package

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0008 ·
Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/478

## Context

The first source package, `sdk-usda-nass`, had to write four generic things itself, an error
mapping, projection constructors, a published-value parser and an enum generator, and its
`Decimal` fields reached agents as JSON strings. This record states ADR-0008 with its
amendments of 2026-10-24, 2026-10-27 and 2026-11-18, and ADR-0015's follow-up of 2026-10-24,
as they stand, and changes no decision; their history stays in ADR-0008.

## Decision

1. **JSON numbers.** `UpstreamModel` serialises `Decimal` as a JSON number in JSON mode.
   Python keeps the `Decimal`; the wire loses only precision JSON could not carry.
2. **Error classifier.** `ClientConfig.classify` is an optional callable from a response to
   a taxonomy error or `None`. The client calls it on every response, before the default
   status mapping, unless the caller asked for the raw response (`raise_on_error=False`);
   before a 429 or 5xx is retried it also asks `classify`, for a raw response too, and its
   answer can set the wait or end the retries (ADR-0037, decision 3). Sources state their
   error shapes there once: the shapes upstream documents and, where upstream documents none
   for an answer, the shapes the source recorded, each backed by a fixture of that answer
   under `tests/fixtures/` and a test that passes it to `classify` through
   `response_from_fixture`.
3. **Projections.** `UpstreamModel.project(source, **overrides)` builds a model from another
   model's same-named fields; overrides are for parsing only.
   `xippios.core.testing.assert_projection` checks fidelity.
4. **Helpers.** `xippios.core.parse_decimal` drops thousands separators and gives `None` for
   a suppression code and for every result that is not a finite number (`NaN`, `Infinity`,
   `sNaN`); every finite text reads as `Decimal` reads it.
   `xippios.core.reference.render_enums` (decision 6) and `enum_member_name` generate enums;
   `xippios.core.testing.mcp_call` serves end-to-end tool tests.
5. **Template.** Generated repositories get the refresh-script scaffold wired to the enum
   helper, a `params` module for packaged lists, and adapter tests that assert the route
   methods and the tool schemas. Nothing source-specific is scaffolded.
6. **Generated enums.** One `render_enums(lists, *, fetched, class_names=None,
   member_names=None, generator=...)` infers the kind per list: a list of strings renders a
   `StrEnum`, a list of `(id, name)` pairs, as `id_name_pairs` builds them from upstream's
   records, an `IntEnum` with `_<id>` appended to a name several ids share, so one module
   holds both; an empty list is refused. An upstream whose ids are integers renders
   `IntEnum`: fidelity wins over the default, because upstream's data carries the ids as
   integers, which a `StrEnum` of their digits never equals, and its names are not unique.
   - `fetched` is one date for the module or one per list. Each class docstring is one line,
     "Values of ``<key>`` (fetched <date>).", and since it reaches an MCP tool's input
     schema through the parameter type it holds what an agent needs; a maintainer's note
     goes into a comment.
   - Where `class_names` names no class, the class name derives from the key: a part of the
     key that holds a lower-case letter is split before each hump, an upper-case letter
     after a lower-case letter or a digit, and each word is capitalized: `attributeId` gives
     `AttributeId`, `qtyUnitCode` `QtyUnitCode` and `partner2Code` `Partner2Code`. A part in
     upper case alone has no hump, nor has an upper-case run: `state_alpha` and
     `STATE_ALPHA` give `StateAlpha`, `STATE2ALPHA` `State2alpha` and `HSCode` `Hscode`.
   - The output is plain: values as `ascii()` writes them, so the module stays ASCII-only
     and the values the same at runtime; one member per line; `__all__` one name per line
     in the order of the lists; the import names the kinds the module needs; a line over
     100 columns carries `# noqa: E501`, since no tool can shorten upstream's value, and a
     member named `I`, `O` or `l`, which ruff flags as ambiguous (E741) with no fix,
     `# noqa: E741`.
   - Refused with `ValueError`: a key, a class name, a date or a generator text that is not
     printable ASCII, or holds a backslash or three double quotes; a class name longer than
     84 characters, whose `class` line `ruff format` cannot shorten; a class named `IntEnum`
     or `StrEnum`, which the module imports; two lists that would get one class name; a key
     of `fetched`, `class_names` or `member_names` that the lists do not hold; and a value
     with nothing to derive a member name from, which the source's refresh script names
     once in `member_names`.
   - The refresh script, the template's, runs `ruff format && ruff check --fix` after
     rendering, which choose the quotes, wrap what fits, drop a `# noqa` the wrapping made
     unused (RUF100) and sort `__all__` (RUF022), and the module is committed as formatted.
     Its consumers are every source, through the template's refresh script (ADR-0023,
     decisions 1 and 5).
   Johannes decided the one renderer on 2026-10-27.

## Consequences

- The next source writes no error-mapping boilerplate, no projection constructors and no
  enum generator, and its numbers arrive as numbers.
- `classify` makes the wrapper layer thinner, which ADR-0001 wants; the classifier is the
  one place a reviewer checks, a documented shape against `docs/upstream/` and a recorded
  one against its fixture.
- A `Decimal` that needs exact transport would need a string field by design; none of the
  family's sources has one.

The conventions' header, §3, §6, §8 and §15, the review checklist's item 3, the README and
the docstrings of `ClientConfig`, `UpstreamModel`, `xippios.core.reference` and
`assert_projection` state its decisions from 1.28 on.

## Amendment 2026-11-24

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/478: in decision 1 a `Decimal`
whose exponent is zero or more, without fractional digits, serialises as a JSON integer, `16217`,
and one with fractional digits as a JSON number with the digits upstream sent (ADR-0067,
decision 10), and decision 2's raw response, which a caller asked for with
`raise_on_error=False`, reads `send_once`, the recorder's one request, which asks no `classify`
since nothing is retried or raised, as the switch left the client by ADR-0037's amendment of the
same day (https://github.com/xippios/sdk-core/issues/479), while the rest of decisions 1 and 2,
decisions 3 to 6 and the consequences stand as written.

Decisions 4 to 6 place the renderer where it stood when they were decided: `render_enums`,
`enum_member_name` and `id_name_pairs` stand in `xippios.core.refresh.reference`, the frame
of the reference refresh script, which alone calls the renderer and formats `enums.py` with
ruff in place of the template's script (ADR-0062, decisions 13 and 14).
