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

## Amendment 2026-10-29

A read-only analysis of 2026-10-29 found that xippios-usda-wasde 0.1.1 declares
`xippios-usda-esmis~=0.1.0` while esmis 0.2.0 is on PyPI, so a joint install of the
latest release of all nine packages resolves esmis to 0.1.0 (queue row 268). Points 1
and 4 are Johannes's decisions of that day (D106, D109 (2)); point 2 follows from his
version rule of the same day (D110 (1)); point 3 is the route the review of the
sdk-usda-wasde 0.2.0 briefing required on 2026-10-29 (queue row 273).

1. **The dependency order.** When a dependency releases a new minor, the dependent's
   adoption release, its §15 adoption PR (decision 1) and the release that carries it,
   follows right after, so the latest of both install together. A dependent that bundles
   the adoption with feature work says so in its briefing and accepts the window;
   sdk-usda-wasde 0.2.0 does, its PR 1 the adoption of esmis 0.2.0 (queue row 260). A
   check that the latest of every published package installs together is the
   coordination's (queue row 269).
2. **A breaking minor only.** By ADR-0018's version rule (amendment (g)), only a
   breaking change bumps a minor before 1.0, so a dependency's patch, which may add
   tasks or parameters, reaches the dependent inside its `~=X.Y.0` bound; the adoption
   release of point 1 follows a breaking minor only.
3. **New surface the dependent uses.** When the dependent uses what a dependency's minor
   adds or changes, the adoption PR stays pure and the use is the next PR, as the
   sdk-usda-wasde 0.2.0 briefing splits its PR 1 (`chore/template-update-esmis-0.2.0`)
   and its PR 2 (`fix/revision-file`) (conventions §15's second route; ADR-0018,
   amendment (i)).
4. **The host's exception.** The host xippios-mcp declares the source packages as extras
   with `>=` lower bounds, an exception to decision 1's one-minor bound for the host
   alone (ADR-0026, decision 9).

Conventions §12 states points 1 and 2 from 1.23 on, §15 point 3.
