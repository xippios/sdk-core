# ADR-0003: Upstream fidelity — no cross-source normalization in SDK packages

Status: Accepted · Date: 2026-10-20

## Context

The sources (USDA, Comtrade, Eurostat, FAOSTAT, CashCtrl) use incompatible concepts:
marketing years vs calendar years, HS codes vs PSD codes vs FAOSTAT items, bushels vs
tonnes. A common schema is valuable but is product logic, and it changes as the
product learns. Agents, meanwhile, already know upstream vocabularies from the public
documentation.

## Decision

SDK packages mirror upstream naming and semantics. They perform within-source hygiene
only: typing, parsing, enums, pagination, errors, reference data. They never map one
source's concept onto another's. Normalization, reconciliation and vintage logic live
in product repositories that consume these packages.

The upstream documentation is snapshotted into `docs/upstream/` so the agent reads the
real reference offline, and so documentation changes are visible as diffs.

## Consequences

- Packages stay valid as the product's schema evolves; they are reusable by anyone.
- Field names look different across packages. That is correct, not a defect.
- The product layer carries the full cost of normalization and owns its audit trail
  (source-shaped landing tables, normalized views on top).
