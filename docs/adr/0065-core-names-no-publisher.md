# ADR-0065: Core names no publisher

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/485

## Context

Core 0.3.0 took the api.data.gov gateway into `xippios.core.data_gov` (ADR-0032, decision 5):
the key from `DATA_GOV_API_KEY`, the gateway's documented answers as taxonomy errors, one
`QuotaPolicy` per process for the key and `NoDataForYear`, FAS's empty 404 on a data path. Three
sources behind the gateway use it, sdk-usda-psd, sdk-usda-esr and sdk-usda-gats, and no other
package does. Its subclass of the policy set `QuotaPolicy._subject`, a private attribute that no
other code of core sets, so that core's refusal before sending named the key's variable, and its
refusal of a 429 called two private methods of the policy and the policy's private clock.

The design sitting of core 0.5.0 answered where the gateway belongs. Part 6 of the answer on
https://github.com/xippios/sdk-core/issues/473 has its names live with the three sources, and
core keep nothing that knows one publisher. Part 4 of the answer on
https://github.com/xippios/sdk-core/issues/482 has what is specific to the USDA sources stand in
one shared package that the three depend on, for one place and one count of the quota. The
answer on https://github.com/xippios/sdk-core/issues/485 names that package, part 3, and frees
core of publishers in all that binds, part 4: the package, its tests, the conventions, the
README and the handover's part for 0.5.0 use one invented source and name no real one, records
and the changelog may name sources, and two checks hold the line. ADR-0059's consequences left
this record to say how the gateway leaves.

## Decision

1. **The gateway leaves core.** `xippios.core.data_gov`, 308 lines, and its tests, 299 lines,
   leave core for the shared package `sdk-usda-fas`, distribution `xippios-usda-fas`, import
   `xippios.usda.fas` (https://github.com/xippios/sdk-core/issues/485, part 3).
   `QuotaPolicy._subject` leaves with it. The gateway's own decisions, ADR-0032's decision 5 as
   it stands, go to the first record of `sdk-usda-fas`, and ADR-0032's other decisions stand in
   core, one key variable for each issuer among them. Core's `fetch_periods` keeps its `skip`,
   which takes a source's own error for a period without data.
2. **The refusal of a spent quota.** Core gives the policy no public subject and no public wait.
   Its refusal before sending calls the quota "quota" and names the policy's `source`, as for
   every other policy. The shared package words its own refusal of a 429 from what stays public:
   `snapshot()`, which `observe` has updated before a `classify` runs (ADR-0037, decision 1),
   `parse_retry_after`, the policy's `window`, and the clock that it hands the policy as
   `clock=`, about ten lines of its own. A public subject and a public wait would be two names
   with one consumer that can do the same through what stays, so they do not enter (ADR-0059,
   decision 2).
3. **A publisher's shared package.** A publisher's shared package holds code that knows one
   publisher and that two or more of its sources share, as `sdk-usda-fas` holds the gateway for
   the three sources behind api.data.gov, and a closed question makes each. A source depends on
   it by the rules that ADR-0021 has for a dependency on a source package, with the shared
   package's public names in the place of the task layer that ADR-0021, decision 1, names: one
   minor with an upper bound, one core minor for both, the shared package released first and
   its own fixtures recorded by each source. The shared package depends on core and on no
   source, registers no task and runs no server. Conventions §1, §5, §6, §7, §10, §11, §12,
   §13 and §15 bind it where it holds what their rules name, without `docs/upstream/`, and no
   other section does, which conventions §12 says in one sentence.
4. **One invented source.** What binds uses one invented source, `example`, and names no real
   source or publisher: the slug `example`, the import path `xippios.example`, the base URL
   `https://api.example.org/v1`, the tasks `list_regions`, `get_series` and `create_thing`, and
   the tenant `acme`. No source of the family ever takes the slug `example`.
5. **What binds and what tells history.** What binds is the package, its tests and its scripts,
   the conventions, the README, `CLAUDE.md`, the review checklist, the definition of done and
   the handover's part for the coming release. What tells history is the records under
   `docs/adr/`, `CHANGELOG.md` and the fragments under `changelog/`, the dated reports under
   `docs/reports/` and a handover part of an earlier release while it stands: each may name a
   real source or publisher, as a consumer, as evidence or as history.
6. **Two checks hold the line.** A test of core lists the shapes that core may name and refuses
   every other in what binds, and it reads no record and no changelog. A step of the
   organization's conventions check takes each source's names from its template answers and
   finds them in what binds of core; it is the organization repository's to build
   (https://github.com/xippios/.github/issues/169), with the organization's package after the
   sources' first wave, where the maintainer's answer on
   https://github.com/xippios/.github/issues/170 places it. Until that step stands, core's own
   test is the one check, and the tag of 0.5.0 waits for no step of the organization's.

## Consequences

- sdk-usda-psd, sdk-usda-esr and sdk-usda-gats stay on core 0.4.x, which holds the module, until
  they adopt 0.5.0, and their bound on core keeps 0.5.0 out, so no release of `sdk-usda-fas`
  comes first. At its adoption each imports `Gateway` and its names from `xippios.usda.fas`,
  declares the dependency on `xippios-usda-fas`, and drops six tests of the gateway, named
  alike in all three, which the shared package's tests cover, two under the same names, while
  `test_the_client_is_wired_for_the_gateway` stays, since it reads the source's own
  `_client.py`. The handover's part for 0.5.0 states it without a source's name.
- The refusal of a spent quota before sending no longer names the key's variable, which told an
  operator which of the shared keys is spent. The adoption of sdk-usda-esr with the shared
  package overturns decision 2 if the refusal that an agent meets no longer tells it what to
  wait for.
- ADR-0032 is amended: decision 5 leaves for the first record of `sdk-usda-fas`, and its six
  other decisions stand. ADR-0033 and ADR-0037 keep their passages on api.data.gov, which cite
  ADR-0032, decision 5, whose amendment says where it went.
- ADR-0021 is amended: a source may depend on its publisher's shared package by its rules, with
  the shared package's public names in the place of a task layer.
- ADR-0025 is amended: its plan that what the Google sources share moves to core as
  `xippios.core.google` is taken back, since core holds no code that knows one publisher.
- Conventions §7 says where one key serves several sources without naming a module, and §12
  states the dependency on a publisher's shared package and the sections that bind one. The
  README and the docstrings of `xippios.core.series` and `xippios.core.client.quota` stop naming
  the module, and `CLAUDE.md` follows within 0.5.0.
- Core's surface loses seven names of an unpinned module and no pinned name.
