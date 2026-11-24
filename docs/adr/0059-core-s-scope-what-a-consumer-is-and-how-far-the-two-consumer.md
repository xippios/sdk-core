# ADR-0059: Core's scope: what a consumer is and how far the two-consumer rule reaches

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/473 · Supersedes ADR-0023 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/555

## Context

ADR-0023 let code into `xippios-core` with two consumers, or with one for a reason of three kinds,
and ADR-0058, decision 1, added a fourth: the maintainer's decision on the closed design question
of the step that adds the code. Neither record said which code of a package makes it a consumer,
and ADR-0023 judged public names alone, while core's surface also holds methods, keyword
parameters, fields of a declaration and hooks that one source shaped. By the fourth reason two
public names of 0.4.1 entered with one consumer each, `naive_time` (ADR-0052) and `record_task`
(ADR-0057).

The design sitting of core 0.5.0 asked what a consumer is and how far the rule reaches, and the
maintainer's answer on https://github.com/xippios/sdk-core/issues/473 ends the fourth reason. His
answer on https://github.com/xippios/sdk-core/issues/485, part 6, adds how the consumers are
counted. ADR-0023's decisions 1, 3 and 5 change, and it holds three amendments, so this record
supersedes it whole and restates each of its decisions that stands. ADR-0058, decision 1, goes
with it; ADR-0058, decision 2, stands.

## Decision

1. **Consumer.** A consumer is a source or the host `xippios-mcp`, counted once, by any code it
   runs: its package, its scripts, its tests, and a code block that a rendered command has a
   session run. Prose that names a piece consumes none. A helper that the template renders into
   every source runs in each of them, so each counts, as ADR-0023, decision 1, said. This
   reverses the rest of that decision, which counted any package that depends on core, family
   member or not.
2. **What the rule binds.** It judges every piece that a caller can name: a public name, a
   method, a keyword parameter, a field of a declaration and a hook. A piece with one consumer
   leaves where that consumer can do the same through what stays, as `delete_json`,
   `request(raise_on_error=False)` and `Tenants(validate=, hints=)` leave in 0.5.0. Where it
   cannot, the piece stays, and the record of its mechanism names its consumer, as for
   `Tenants(var_prefix=)` and `serve_tenants(noun=)`.
3. **A name that core calls itself** stays in its pinned list while one consumer imports it.
   Each of the six `__init__.py` files exports what consumers import, and a helper that core
   calls itself and no consumer imports stays importable from its own module, outside the list,
   as ADR-0023, decision 5, said.
4. **One consumer is enough for the family's contract alone:** the result envelope, the error
   taxonomy, the package contract with the one host, the family check and the three security
   properties, which are credential redaction in `ResultMeta.request`, the placeholder key in
   offline tests and secret scrubbing in recorded fixtures. The record that brings in a piece
   with one consumer names which of these it serves, and "a second source will probably need
   it" stays no reason. This list replaces the three reasons of ADR-0023, decision 3, and the
   maintainer's decision on a step's design question stops being a reason of its own, which
   reverses ADR-0058, decision 1.
5. **Entry and copies,** carried from ADR-0023, decisions 2 and 4, with the consumers of
   decision 1 here. Code enters core when two consumers consume it: two carry it, or the same
   shape of it; or one carries it and an issue of sdk-core names a second one's same need within
   the same core minor; or the template renders it. A source that needs what core lacks carries
   it with one comment naming the issue of sdk-core; a second source may carry the same helper
   when the issue names both; a third never: core takes it in that minor. The issue stays open
   with its consumers until the second arrives.
6. **The count is a report.** A script counts the consumers of core's names and keyword
   parameters over the consumers' trees and reports them; it fails no check, and no name and no
   parameter leaves by the count alone (https://github.com/xippios/sdk-core/issues/485, part 6).
   A piece leaves by a closed design question that names it, and the record of its mechanism
   says so. This reverses the floor of ADR-0023, decision 5, by which a public name with no
   consumer across two consecutive minors left in the next minor.
7. **One key class** takes where the key travels, in place of `QueryKeyAuth`, `HeaderKeyAuth`,
   `BearerAuth` and `BasicKeyAuth` (https://github.com/xippios/sdk-core/issues/473, part 5). The
   change of the client that builds it words its name and its values.
8. **Scope and review,** carried from ADR-0023, decisions 6 and 7. This record governs
   `xippios-core`; the template's bar is that nothing source-specific is scaffolded (ADR-0031). An
   issue of sdk-core that asks core for a piece names its consumers, and the review holds a core
   pull request to name the two consumers of what it adds, or the part of the contract under
   decision 4 in its record. ADR-0023's two fields of a row, `consumers` and
   `second-consumer-by`, were the coordination layer's, as its last consequence said, and are
   not carried.

## Consequences

- `naive_time` returns to sdk-usda-esr, which reads its `since` itself and hands that reader to
  `newer_than` as `read=`. `newer_than` stays, with its two consumers, sdk-usda-esr and
  sdk-usda-psd, and its refusal of a reader whose value does not compare with the releases no
  longer names a reader of core's. `load_table`, with `load_csv`, which it calls, returns to
  sdk-usda-nass, which reads its `columns.csv` itself.
- `assert_list_current` leaves the list of `xippios.core.testing`, since no source imports it,
  and stays in `xippios.core.testing.live`, which calls it (decision 3). `REDACTED` enters the
  root's list, since core writes it and sdk-cashctrl's package imports it (decision 3): the root
  is the path a source's package imports it by, and `xippios.core.testing` keeps it for a
  source's tests.
- `BODY_LIMIT`, `parse_retry_after`, `error_from_response` and the root's `load_json` stay in the
  root's list: core calls each itself, and a consumer imports it (decision 3). Of the five names
  of `xippios.core.mcp` that the host reads, `register_tasks`, `LOOPBACK_HOSTS` and
  `quiet_request_logging` stay, the host their consumer, and `is_write_server` and
  `is_loopback_only` leave in 0.5.0 with their registries, since a tool set's `read_only` and
  `loopback_only` say the same (https://github.com/xippios/sdk-core/issues/485, part 1).
- `record_task` and `record_task_sync` return to sdk-google-mail (decision 4) with the change of
  the recorder in 0.5.0. Each change of 0.5.0 that sends a piece back cites this record, and the
  record of each mechanism names the consumer of each piece with one consumer that it keeps.
- Part 6 of the answer on https://github.com/xippios/sdk-core/issues/473, that core keeps nothing
  of the api.data.gov gateway, is the record of the gateway's leaving, in 0.5.0, and not this
  one's.
- ADR-0058 is amended: its decision 1 leaves for decision 4 here, and its decision 2 stands.
  ADR-0052 is amended: core ships no reader of a vintage text, and its amendment of 2026-11-22,
  which admitted `naive_time` by the fourth reason, is taken back. ADR-0023 stays in the tree,
  marked superseded, its consequences and amendments the history of 0.3.0, 0.4.0 and 0.4.1.
- The definition of done's line on a core pull request's consumers and the review checklist's
  item 11 name decision 4 here in place of ADR-0023, decision 3, and ADR-0058, decision 1.
  Conventions §15, items 3 and 4, cite this record for the code that core removes for its one
  consumer and for the copies that a source carries.

## Amendment 2026-11-24

Amended by https://github.com/xippios/sdk-core/issues/555: a piece that a maintainer's answer adds
enters core with fewer than two consumers when that answer decided it, beside decision 5's two
consumers and decision 4's part of the family's contract, since every decided addition is in 0.5.0
(https://github.com/xippios/sdk-core/issues/485, part 6) and nothing decided is removed, and the
record of its mechanism names the answer and the piece with its one consumer or with none, as the
release's statement of core's surface names it too (ADR-0068, decision 6), so that decision 8's
review holds a core pull request to that naming for such a piece, as ADR-0034 and ADR-0040 name
`fetch_pages(stop=, key=)` and `download(headers=)` in their amendments of 2026-11-24, while the
rest of decisions 4, 5 and 8, the other decisions and the consequences stand as written.
