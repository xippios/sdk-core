# ADR-0052: One filter for a vintage taken back

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/371 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/455 · Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/473

## Context

ADR-0041, decision 2, and conventions §4 state the rule of a parameter that takes back the
`meta.vintage` of an earlier call: the text as `vintage` wrote it, what is strictly later kept,
an equal release being no newer, `meta.vintage` and `meta.published_at` those of the whole
upstream answer, and a zone against a naive release time and a text the parameter cannot read
refused with `InvalidRequestError`. Core gives the rule no code, and two sources carry it
(https://github.com/xippios/sdk-core/issues/318), each reading `since` before its request:

- sdk-usda-esr's `get_release_dates` reads a release time printed without a zone with
  `datetime.fromisoformat`, a date alone as its midnight, refuses a zone, and compares times
  (`_since` and the filter in `src/xippios/usda/esr/tasks.py`).
- sdk-usda-psd reads a release month, `YYYY-MM`, by a pattern into `(year, month)`
  (`validate_since` in `src/xippios/usda/psd/params.py`), which no time parser takes, and uses
  it twice in `tasks.py`: as a filter of the records in `get_release_dates`, and as all or
  nothing on the newest release in `get_latest_release`.

A comparison of the texts is right for the fixed-width month and wrong for a time, where a
fraction of a second and a date beside its midnight sort wrongly and a zone goes unseen, and one
parser in core fits only one of the two. Eleven tasks of four sources take another `since`: an
inclusive bound on dates or periods beside an `until`, which sdk-usda-esmis filters by,
sdk-usda-wasde takes through it, and sdk-faostat and sdk-eurostat send upstream, and none of
them takes back a vintage.

This record stands beside ADR-0041, decision 2, and changes none of its rule: that decision
keeps the rule, and this record gives it its code and names the other `since`. A change to the
rule is ADR-0041's, a change to the helper this record's. Decisions 1 to 3 are the answer of
https://github.com/xippios/sdk-core/issues/371, and decisions 4 to 6 are those of the pull
request that built the helper.

## Decision

1. **The source hands its reader of the vintage text, and core compares strictly.**
   `newer_than(since, items, *, released, read)`, exported from `xippios.core`, returns the
   items whose release, `released(item)`, is strictly later than `read(since)`, in their order,
   and every item when `since` is `None`. `read` is the source's reader of its vintage text,
   which raises `InvalidRequestError` for a text it cannot read. The helper reads `since` once,
   before any item, so an empty answer refuses an unreadable text as a full one does, and lets
   the reader's error pass as it is. Core ships one reader, `naive_time(text, *, source=None)`,
   for a release time printed without a zone: it reads with `datetime.fromisoformat`, a date
   alone as its midnight, and refuses with `InvalidRequestError` a text that is no ISO date and
   time and one that carries a zone, since the release times it is compared with carry none and
   the comparison would invent one (ADR-0028). sdk-usda-psd hands its own reader of a month.
2. **A filter only, beside `vintage`.** The helper returns the kept items and nothing else. It
   lives in `xippios.core.models`, beside `ResultMeta`, and the task sets `meta.vintage` and
   `meta.published_at` from the whole upstream answer, so an answer with nothing newer still
   names the newest release, the marker to store for the next call.
3. **No `until`.** The inclusive bound on dates or periods with `until` is another rule, which
   one package filters by, so ADR-0023, decision 2, admits no helper for it. Conventions §4 name
   the two meanings of `since` in one sentence, and the eleven tasks change nothing.
4. **An item without a release time is kept.** Where `released` returns `None`, the item cannot
   be shown to be no newer than `since`, and a filter that dropped it would hide it from every
   later call, which the caller cannot tell from no change. Keeping it costs the caller a repeat,
   dropping it a change. The helper reads no release time that upstream did not give (ADR-0028).
5. **A task refuses an unreadable `since` before its request.** A bad argument is detected
   before the call (conventions §5), so a task calls its reader on `since` before it sends the
   request, and the helper reads it again on the answer. The reader raises
   `InvalidRequestError`, the class that both copies raise, so a source's tests of the refusal
   keep their class.
6. **A reader whose value does not compare with the releases is the source's fault.** A month
   read against releases that are times, or a time with a zone against `naive_time`'s, is no
   argument the caller can change, so it raises no taxonomy error, whose `InvalidRequestError`
   tells the caller to change the request (conventions §5). The helper raises `TypeError`, as
   core does for a fault of a source's code, naming both values and their types and chaining
   the comparison's own error. mypy accepts such a pair, since it infers the bound for the two.

## Consequences

- sdk-usda-esr's `_since` and filter reduce to `naive_time` and the call, and its refusal takes
  core's wording, its class unchanged. sdk-usda-psd's two filters reduce to the call with its
  `validate_since`, whose wording stays. Each deletes its copy in its patch, by
  https://github.com/xippios/sdk-usda-esr/issues/31 and
  https://github.com/xippios/sdk-usda-psd/issues/33.
- sdk-usda-psd's `get_release_dates` sets no `meta.vintage`, so its empty answer carries no
  marker. That is sdk-usda-psd's own to decide, and this record builds nothing for it.
- `naive_time` has one caller today, sdk-usda-esr, and none of the three reasons of ADR-0023,
  decision 3, admits it. It is the exception to that decision that the maintainer's answer to
  https://github.com/xippios/sdk-core/issues/371, part 1, makes: core ships the reader of a
  naive time with the helper.
- The walk of a list bounded by `since` stays out, with one consumer
  (https://github.com/xippios/sdk-core/issues/149).

## Amendment 2026-11-22

https://github.com/xippios/sdk-core/issues/455 amends the third consequence, on `naive_time`'s one
caller, from finding 2 of the organization's range review of core 0.4.1
(https://github.com/xippios/sdk-core/pull/453#issuecomment-7082327015). `naive_time` enters core
by reason (d), which ADR-0058, decision 1, adds to the three of ADR-0023, decision 3: the
maintainer's decision on the closed design question of the step that added it, his answer on
https://github.com/xippios/sdk-core/issues/371, part 1, that core ships the reader of a naive time
with the helper. It is therefore no exception to ADR-0023, and the consequence's words that none
of the three reasons admits it stay true of those three. Decisions 1 to 6 and the other
consequences stand as written.

Amended 2026-11-24 by https://github.com/xippios/sdk-core/issues/473: the amendment of 2026-11-22
is taken back and `naive_time` leaves core for its one consumer, sdk-usda-esr, since ADR-0059,
decision 4, ends the reason (d) that admitted it, so that decision 1's sentences on core's one
reader no longer hold and every source hands `newer_than` its own reader of its vintage text,
decision 6's rule stands with a source's reader of a time without a zone in place of its example
of `naive_time`, in the first consequence sdk-usda-esr's filter reduces to the call with its own
`_since`, whose wording stays, and the third consequence no longer holds, since core ships no
reader of a naive time, while decisions 2 to 5, the rest of decision 6 and the second and fourth
consequences stand as written.
