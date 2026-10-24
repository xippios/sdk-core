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
