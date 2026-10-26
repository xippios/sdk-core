# ADR-0023: Core scope — code enters `xippios-core` with two consumers

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (drafted by the
architect from the family review of 2026-10-25 and the queue rows of core 0.2.0)

## Context

`xippios-core` 0.2.0 reached 5,776 source lines and 7,546 test lines for four consuming
sources. The family review counted 111 public names, of which 49 have no consumer and 24
have exactly one (cashctrl 18, psd 3, nass 2, comtrade 1); about half the tests exercise
code nobody calls. Tenants, the tenant lock, the write checks, `assert_write_tools`, the
host-placeholder scrub and the gzip-aware cache entered core from one source's rows, and
0.3.0 moves most of them back out (review C6–C9; Johannes's decision of 2026-10-25 that
sdk-cashctrl stands alone).

The queue made this easy: a source filed a row for what it needed, the row named an ADR or
convention it touched, and the core session built it. Nothing asked whether a second
package would ever call it. Conventions §15 item 4 covers the other direction, a source
carrying its own helper until core offers it, and forbids copying that helper further;
with no rule for when core should take it, the only way out of a copy was into core.

## Decision

1. **Consumer.** A consumer is any package that depends on `xippios-core`, family member
   or not; `sdk-cashctrl` counts after its standalone decision (its own conventions do not
   become family ADRs, its dependency on core is unchanged). A helper the template renders
   into every generated repository counts as consumed by every source, since ADR-0008
   forbids scaffolding anything source-specific: a rendered helper is family code and
   belongs in core, not in every repository.
2. **Entry.** Code enters `xippios-core` when at least two consumers consume it: two
   carry the helper (or the same shape of it); or one carries it and a second has a queue
   row naming the same need within the same core minor; or the template renders it.
3. **One consumer** is enough only when the ADR that introduces the code states the
   reason, and the reason is one of three: (a) a family invariant the template renders for
   every source (the envelope, the taxonomy, the conformance tests); (b) one of three
   security properties, credential redaction in `ResultMeta.request`, the placeholder key
   in offline tests, secret scrubbing in recorded fixtures, and no other: a source's own
   projection policy (ADR-0017 overrides, vendor tags, identifier shapes, a recorder's
   pre-write hooks) is the source's; (c) what the adapters need to generate MCP tools and
   HTTP routes from one signature. "A second source will probably need it" is not a reason.
4. **Copies** (amends conventions §15 item 4 and the definition of done's adoption line).
   A source keeps its helper with one comment naming the queue row. A second source may
   carry the same helper when the row names both; a third never: core takes it in that
   minor. The row stays open with its `consumers` until the second arrives.
5. **Removal floor.** A public name of `xippios-core` with no consumer across two
   consecutive minors is removed in the next minor (§12: no compatibility across minors
   while 0.x; a CHANGELOG line names it); `__init__.py` exports only what consumers
   import. This is a floor for code admitted under this ADR. It never delays an item the
   family review scheduled: C6's quota variants, C7's renderer layout and the one-caller
   helpers go on the review's clock, 0.3.0.
6. **Mechanics.** A `--kind change` queue row for core names `consumers` and
   `second-consumer-by`. The family session applies the test when it triages rows; the
   reviewer checks a core PR's ADR for the consumer statement or the reason under 3.
7. **Scope.** This ADR governs `xippios-core`. The template's bar is ADR-0008 (nothing
   source-specific is scaffolded); the family review applied the same test to template
   questions (T1, T2) and this ADR changes nothing there.

## Consequences

- Core stops growing ahead of its consumers; the family review's lean targets stop being
  aspirational.
- Sources carry copies for a while, two at most. The conformance tests keep the copies
  honest where shape matters.
- Applied to today's rows: the `api.data.gov` gateway module (C14) qualifies with three
  consumers; tenants and the write checks (C8) do not, one consumer, standalone; cashctrl's
  recorder extras (rows 23, 26c) stay in cashctrl under 3(b)'s closed list, as C9 says;
  `data=` form bodies (rows 2, 26a) are shipped code and stay by the review's C-items.
- Conventions §15 item 4 reads: "what it does not provide yet is carried by the source,
  named in the PR description and in a queue row; a second source may carry the same
  helper when the row names both; a third never: core takes it in that minor (ADR-0023)."
  The definition of done's adoption line says the same in one clause. §15 also gains "a
  core row names its consumers".
- The two row fields and `--kind` are the coordination layer's part.
