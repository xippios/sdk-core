# The surface's consumers at the proof's final heads, 2026-11-25

Counted again on the commits that the proof of 0.5.0 ends on, core's surface and its consumers
give every figure and every table of the first count,
https://github.com/xippios/sdk-core/blob/main/docs/reports/2026-11-25-the-surface-and-its-consumers.md,
as it stands. Core holds 112 unique names in 16,480 lines, 72 in 8,740 for the run-time part and
41 in 7,740 for the workbench. Among the five proving packages 15 names have no consumer, 36 have
one and 61 have two or more, and 92 parameters have none, 60 one and 40 two or more. With the nine
other sources on `main`, 8, 15 and 89 names and 64, 35 and 93 parameters. Two uses of core moved
since the first count, and neither moves a piece across two consumers: sdk-faostat's tests now
import `Snapshot` beside `Page`, `Response` and `Row`, and `MemoryCache`, while its
`tests/test_live.py` no longer imports `assert_time_between`, which its other tests still import.
One reading of the first count was wrong and is corrected here: a proving package uses the
snapshot frame's `pause`, so it is no addition that no proving package uses.

## Basis

- Core: this repository at
  [4c6c154](https://github.com/xippios/sdk-core/commit/4c6c15426acec85e9482d102363cd97156ee50b6),
  whose `src/` is the candidate's, counted by `python3 -I scripts/count_surface.py --json`, which
  reads by `ast` and imports nothing (README, Counting the surface and its consumers).
- The five proving packages, each extracted by `git archive` at the commit that the proof ends
  on and read as committed:
  - sdk-faostat, the tree of its adoption's second step,
    [5bb3bda](https://github.com/xippios/sdk-faostat/commit/5bb3bdabdd428afa082338a00fd34eb1e40634b1)
    (https://github.com/xippios/sdk-faostat/pull/70), with `scripts/refresh_reference.py` of its
    third step put in its place, from
    [81e48a1](https://github.com/xippios/sdk-faostat/commit/81e48a10ca9f11b889644edd6619115c7acd96cc)
    (https://github.com/xippios/sdk-faostat/pull/76); the two count as one consumer;
  - sdk-cashctrl,
    [16ea4a0](https://github.com/xippios/sdk-cashctrl/commit/16ea4a086d8a3030d66d499a73b8a84fb4aca542)
    (https://github.com/xippios/sdk-cashctrl/pull/157);
  - sdk-usda-esr, at commit `08683722ffa121ebaf0e9c9e81d8b148f38c7de4`, not yet public;
  - sdk-usda-fas, the shared package of the three FAS sources, proven as code before its
    repository exists, at commit `f3f02faf5f2b059c2d7299d28a1b7e83247bdeeb`, not yet public;
  - xippios-mcp, the host, at commit `beeda309420d0c4f35f209ca2c2a2aa53b06b86f`, not yet public.
- The nine other sources on `main` at the commits that the first count names.

## What moved

- `xippios.core.refresh:Snapshot`: sdk-faostat imports it in its tests now, beside its scripts,
  and the name keeps its four consumers.
- `xippios.core:MemoryCache`: sdk-faostat imports it in its tests now, beside its package, and
  the name keeps its two consumers.
- `xippios.core.testing:assert_time_between`: sdk-faostat's `tests/test_live.py` no longer
  imports it, and its `tests/test_api.py` and `tests/test_tasks.py` still do, so sdk-faostat
  stays its consumer by its tests.
- sdk-usda-esr and the host moved by no import of core since the commits of the first count.

## A correction of the first count

The first count's section "The additions that no proving package uses" names the snapshot
frame's `pause` among them. sdk-usda-fas's `tests/test_portal.py:521` builds a `Snapshot` with
`pause=0.0`, at the same commit as then, so its tests use the field, which the script does not
count since a dataclass's field may be passed by position. The other additions of that section
stand: no proving tree passes `ToolSet(add_options=, apply_options=, loopback_only=)`,
`MemoryCache(lifetimes=)`, `fetch_pages(stop=, key=)`, a `KeyAuth` with `location="query"` or
`"bearer"` or `Lists(after=)`. Core's changelog entry of its surface names the same list without
`pause`.
