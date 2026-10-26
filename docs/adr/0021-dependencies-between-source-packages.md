# ADR-0021: Dependencies between source packages

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview)

## Context

`sdk-usda-wasde` needs what `sdk-usda-esmis` provides: find the release, download the
file. Either wasde copies the catalog client and the download, a further copy of the
kind §15 item 4 limits, or it depends on the esmis package. The family has no rule for a
source depending on another source; §12 covers core only.

## Decision

1. A source package may depend on another source package when it consumes that
   package's task layer: it imports `xippios.<dep>.tasks` and its models, never `api/`
   or `_client`. The dependency is declared `xippios-<dep>~=X.Y.0`, one minor, like core
   (§12, ADR-0018), and adopted through a §15 adoption PR when the dependency releases
   a new minor. Both packages share one core minor: the dependent adopts a core minor
   only after the dependency has released on it.
2. The dependent's MCP and HTTP servers register the dependent's tasks only; nothing is
   re-exported. An agent that wants the dependency's tools runs the dependency's server.
3. No cycles, and one level only: a dependency of a dependency is not allowed until a
   case needs it, and that case writes the amendment.
4. The dependent records its own fixtures for the dependency's HTTP calls (they go
   through core's client, so replay matches host and path as usual) and names the
   dependency's release in its CHANGELOG. `check-siblings.sh` installs the dependency
   from PyPI.
5. Releases in order: the dependency tags first; the dependent's release PR pins the
   published version.
6. The dependent's README and CLAUDE.md name the dependency and what it is used for, one
   line each.

## Consequences

- wasde → esmis is the first case; Eurostat and FAOSTAT need none.
- Conventions §12 gains the paragraph; §15 names the dependency floor beside the core
  floor; the template renders `source_dependencies` (name and minor) into
  `pyproject.toml` and the sibling check (template cleanup).
- A dependency's breaking minor reaches the dependent through §15, never implicitly:
  the `~=` bound keeps a fresh install on the tested pair.
