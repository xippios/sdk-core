# ADR-0017: Sensitive upstream fields — personal identifiers stay out of task projections

Status: Accepted · Date: 2026-10-25

## Context

CashCtrl's person records carry values that identify a person to an authority or reach
their money. Its documentation (sdk-cashctrl `docs/upstream/person.md`) lists `ssn`,
"Social security number of the employee", and, in each of a person's `bankAccounts`,
`iban`, "The IBAN (International Bank Account Number)". ADR-0003 has a package's models
mirror the payload, so a task that returns a person whole puts these values into every
MCP tool result and HTTP envelope, and from there into the agent's context, logs and
stores. ADR-0005 keeps credentials out of the envelope, but it covers `request` keys
that look like credentials, not upstream data.

A mechanism in core that would hide such fields in the adapters' output was drafted and
dropped: it would add public surface to core for what one source's tasks can decide,
and conventions §3 already lets a task return a projection, a subset of an upstream
record's columns under their upstream names. Johannes decided the rule on 2026-10-25.

## Decision

- A source keeps documented personal identifiers out of its agent-facing projections,
  the models its tasks return: `ssn`, `iban` and what the source judges equivalent (a
  national identification number, a bank account number, a tax number). A task that
  fetches them deliberately may return them, and says so in its docstring.
- The source's Python read models, those of its endpoint wrappers, stay faithful
  (ADR-0003): they carry these fields under their upstream names, with their values.
- Fixtures never carry the values: the recording names them in `Scrub(secrets=...)`,
  which scrubs them before the one write (conventions §10), and the definition of done's
  fixture grep looks for them in `tests/fixtures/`.

## Consequences

- Nothing in `xippios.core` changes.
- sdk-cashctrl applies the rule in its own models: the projections its tasks return
  leave out `ssn` and `iban`.
- sdk-template's model scaffold gets a comment pointing to this rule.
- Conventions 1.13: §3 states the rule, and §4 points to it from the envelope.
