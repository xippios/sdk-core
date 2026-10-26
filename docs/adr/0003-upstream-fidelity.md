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

## Amendment 2026-10-24

Vendor documentation is reproduced in the snapshot for reference. CashCtrl's API page,
the family's first snapshot of a vendor's documentation, is "© 2026 CashCtrl Ltd.", as
its footer states. The snapshot stays: it is what the agent and the reviewer check every
wrapper against, offline and as a diff. Its `FETCHED.md` carries the copyright line as
the documentation states it and the URL the text was fetched from, and says that the
text is reproduced as the package's reference under this ADR; sdk-cashctrl's section
"Attribution and vendor examples" has the form. A vendor's objection is honoured by
replacing the snapshot with a summary in the package's own words, by PR like any
refresh, that keeps the URL and the names and semantics the wrappers rely on. Raised in
the review of sdk-cashctrl's snapshot; Johannes decided it on 2026-10-23, with the
sdk-cashctrl session.

Two rules make snapshots alike across sources. `Fetched` in `FETCHED.md` is the UTC time
of the run in ISO 8601 with an explicit `Z` (`2026-10-24T09:15:00Z`): sdk-comtrade
recorded the local calendar date of its run, sdk-usda-psd and sdk-cashctrl the UTC date,
and nothing said which. A table that a Markdown pipe table cannot hold, one with merged
cells (`rowspan`, `colspan`) or with a table nested in it, is kept as its HTML in the
Markdown snapshot, and one line in `FETCHED.md` says so, as sdk-comtrade's Help Center
articles and sdk-cashctrl's nested parameter tables already do; a pipe table would lose
the cells' structure. Raised by sdk-comtrade; Johannes decided both on 2026-10-24, in
the interview before core PR G.

Conventions §3 states the three rules from 1.13 on.

## Amendment 2026-10-26

Two rules from the queue. Several FAS APIs are described in one shared OpenAPI
document. A source whose API is one part of a shared upstream document snapshots its own
part and records the full document's byte size and sha256 in `FETCHED.md`, so a refresh
can tell a change in its part from a change elsewhere in the whole (queue row 35 d).

A `project` override that drops a documented personal identifier (ADR-0017) applies
inside a kept list field too: a person's `bankAccounts` is kept and each account is
projected without its `iban` (`bankAccounts[].iban`). Such an override is still "parsing
only" in the sense of conventions §3, since nothing is renamed or computed; ADR-0017's
rule reaches nested fields (queue row 37 a).

Conventions §3 states both rules from 1.14 on.
