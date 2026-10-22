# ADR-0006: Nested import path for providers with several APIs

Status: Accepted · Date: 2026-10-22

## Context

Conventions §1 mapped every source slug to a flat import path with underscores:
`usda-nass` → `xippios.usda_nass`. USDA alone will have NASS Quick Stats, FAS and ESMIS
packages, and `xippios.usda_nass`, `xippios.usda_fas` read as three unrelated names where
`xippios.usda.nass`, `xippios.usda.fas` read as one provider's APIs. Comtrade, Eurostat,
FAOSTAT and CashCtrl each expose one API; a second level there would be artificial.

## Decision

- A provider with several APIs nests: `xippios.<provider>.<api>`. A single-API provider
  stays flat: `xippios.<source>`.
- Repository and distribution names do not change: `sdk-usda-nass`, `xippios-usda-nass`.
  GitHub and PyPI cannot nest, and the slug stays the one identifier used everywhere
  else (MCP entry point, tool prefix, environment variable, topics).
- The import path is an explicit template answer, `import_path`, defaulting to the slug
  with hyphens as dots. A single-API provider whose name carries a hyphen overrides it.
- Every level between `src/xippios/` and the package is a PEP 420 namespace portion:
  no `__init__.py` at `src/xippios/` or `src/xippios/usda/`. The generated tests guard
  this, as core's tests guard `src/xippios/`.

## Consequences

- Nothing changes for `xippios-core` or for single-API packages.
- `copier update` of an existing flat package to a nested path is a rename, not a
  template update; none exists yet, so no migration is needed.
- Tooling: hatchling packages `src/xippios` at any depth; mypy's namespace-package
  mode handles nested portions; ruff's isort treats `xippios.usda.nass` as first-party
  through `known-first-party`.
