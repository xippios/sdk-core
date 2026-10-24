# ADR-0017: Sensitive upstream fields — faithful in Python, redacted at the adapters

Status: Accepted · Date: 2026-10-24

## Context

CashCtrl's person records carry values that identify a person to an authority or reach
their money. Its documentation (sdk-cashctrl `docs/upstream/person.md`) lists `ssn`,
"Social security number of the employee", and, in each of a person's `bankAccounts`,
`iban`, "The IBAN (International Bank Account Number)". sdk-cashctrl's models carry both
under their upstream names, and its write tasks take them, as ADR-0003 requires: names
and semantics come from upstream, and a model mirrors the payload.

A task's result reaches the adapters whole. An MCP tool's text goes into the agent's
context and into whatever the client logs; an HTTP envelope goes to the consumer, its
logs and its stores. ADR-0005 keeps credentials out of the envelope for that reason, by
construction, but it covers `request` keys that look like credentials, not upstream
data, so a person read through the MCP server hands the agent the employee's social
security number and bank account. Fidelity (ADR-0003) and the spirit of ADR-0005, that
what leaves the package is safe to hand on, pull apart here.

Dropping the fields from the models would break fidelity and the write tasks that set
them. Redacting them in the model, as `ResultMeta` redacts credentials, would take them
from the Python caller as well, who may need them (a payroll export). Johannes decided
the rule on 2026-10-24.

## Decision

1. **Faithful in Python.** A sensitive field stays in its model under its upstream name,
   with its value, typed like any other field. Task functions return it, write tasks
   take it, and a Python caller sees it.
2. **Redacted at the adapters by default.** The MCP tool text and the HTTP response
   envelope carry the family's `"REDACTED"` in place of the value of every field the
   source declares sensitive, wherever the envelope carries it: in `data` at any depth (a
   person's bank accounts are a nested list), and in `meta.request` where a write task
   records it as a parameter.
3. **The operator opts in.** A deployment that needs the values reveals them when it
   builds or starts its server or router. The opt-in belongs to the operator: no tool
   argument, request parameter or header reveals a field, so neither an agent nor an
   HTTP caller can opt itself in.
4. **A source declares the fields once.** It lists the sensitive fields its snapshot
   documents on its models, once each, and the adapters read that declaration; no tool
   or route lists them again. The known kinds are a person's government identifier
   (`ssn`) and a bank account number (`iban`); a source that judges another documented
   field sensitive declares it the same way and says why in its PR.
5. **Fixtures never record them.** A recorded fixture holds no value of a declared
   field, in a response or in a request body: the recording scrubs it before the one
   write (`Scrub`, conventions §10), and the definition of done's fixture grep looks for
   these values as it looks for keys. Recording only against synthetic or demo tenants
   stays the backstop.

## Consequences

- Implemented in core 0.2.0 by `UpstreamModel.sensitive`, `dump_redacted`,
  `reveal_sensitive=` on the adapters and `--reveal-sensitive` in `mcp.main` (PR H).
- sdk-cashctrl declares `ssn` and `iban` on its models when it adopts core 0.2.0
  (conventions §15), and checks its fixtures for their values.
- sdk-template scaffolds the declaration, empty, in the template release that goes with
  core 0.2.0, with a pointer to this ADR. A source whose upstream documents no sensitive
  field declares none and is unaffected.
- A Python caller holds the values and is responsible for them; storing or forwarding
  them is product logic outside the family (conventions §14).
- Conventions 1.13: §3 states the rule, §8 and §9 the redaction at the adapters.
