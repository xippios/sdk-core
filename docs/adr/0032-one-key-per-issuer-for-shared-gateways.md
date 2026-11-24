# ADR-0032: One key variable per issuer when one key serves several sources

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0009 · Amended 2026-11-24 by
https://github.com/xippios/sdk-core/issues/485

## Context

The FAS Open Data Services portal documents three APIs, PSD, ESR and GATS, behind one
api.data.gov gateway, `api.fas.usda.gov`. An api.data.gov key serves the APIs of every agency
behind api.data.gov, and its rate limits apply across all of that key's requests
(https://api.data.gov/docs/developer-manual/, read 2026-10-23). A variable per slug would hold
three copies of one key and hide that the packages share one quota. This record states
ADR-0009 with its amendments of 2026-10-26, 2026-10-27 (two) and 2026-11-18 as they stand,
and changes no decision; their history stays in ADR-0009.

## Decision

1. **The issuer names a shared key.** When one key serves several sources, the variable is
   named after the key's issuer. Every source reached through api.data.gov reads
   `DATA_GOV_API_KEY`: `usda-psd`, `usda-esr`, `usda-gats`, and any later one.
2. Otherwise `<SOURCE>_API_KEY` stays (`COMTRADE_API_KEY`). usda-nass keeps its historical
   `NASS_API_KEY`, an issuer's name.
3. The variable is the template answer `api_key_env`, as for any source, and it still ends
   in `_API_KEY`, so the template's validator and the rule never to read or print such a
   variable apply unchanged.
4. The §1 example list names `usda-psd`, `usda-esr` and `usda-gats`, not `usda-fas`: the
   portal is three APIs and gets three packages, nested under one provider by ADR-0006
   (`xippios.usda.psd`, `xippios.usda.esr`, `xippios.usda.gats`).
5. **The gateway module.** `xippios.core.data_gov` is the code side of one key per issuer;
   Johannes decided it on 2026-10-27. Its `Gateway(source, data_path=...)` gives a source
   behind api.data.gov:
   - the key from `DATA_GOV_API_KEY` in the `X-Api-Key` header;
   - the gateway's `classify`, its `API_KEY_*`, 429 and `NOT_FOUND` answers as taxonomy
     errors in the source's name. It reads the gateway's own answers alone: it returns
     `None` for an answer whose request the client marked as sent to another origin than
     its base URL's (ADR-0037, decision 4), and core's status mapping follows; a response
     built without the marks, as a source's test builds one with `response_from_fixture`,
     is read as before. `data_path` is the source's data paths as a pattern that the whole
     request path matches, and `classify` maps FAS's answer there for a market year it holds
     no data for, HTTP 404 with an empty body and `text/plain`, to
     `xippios.core.data_gov.NoDataForYear`, a `NotFoundError` in the source's name with the
     request's `path`, whose text names the path and says that the year it names holds no
     data; a task raises it again with a text of its own, `NoDataForYear(path, message,
     source=...)`. An empty 404 on another path, one with a body or another content type,
     and the gateway's `NOT_FOUND` are left to the source and to core, and a gateway
     without `data_path` maps none;
   - `Gateway.policy`, one `QuotaPolicy` per process for the key in `DATA_GOV_API_KEY`,
     which every source in that process shares: a quota one of them spends, the next
     request of another waits out or is refused without being sent (ADR-0033, decision 4).
     It neither holds back a request sent to another origin nor reads its answer
     (ADR-0037, decision 2). Separate processes keep a snapshot each.

   `Gateway` takes no key of its own: a key passed to a source's client still draws on
   `Gateway.policy`'s snapshot, and a caller with a key of its own, a separate quota, builds
   its own `HeaderKeyAuth` and `QuotaPolicy`. Like `xippios.core.reference`, the module is
   imported by its path and keeps an `__all__` of its own; it is in none of the five export
   lists (ADR-0029, decision 4).
6. **The live workflow.** A source runs its live tests in one workflow,
   `.github/workflows/live.yml`, the shape sdk-template renders: one job, `contents: read`,
   nightly and on `workflow_dispatch`, never on a pull request. The org secret named by
   `api_key_env` reaches only that job's `uv run pytest -m live` step, so checkout, setup-uv and
   `uv sync` never see it. Its start time is derived from the slug and folded onto 01:00 to
   05:59 UTC, so the sources that read one key start at different times and do not draw on
   the shared hourly quota together. The logs of a public repository are public, so every
   live run takes `--tb=short --assert=plain`, as `uv run pytest -m live --tb=short
   --assert=plain`: the first keeps a failing test's frame arguments out of the log, a raw
   upstream payload among them, and the second the values a failed `assert` compares. A
   live test therefore asserts on shapes and counts, never on a raw payload.
7. **A pull request counts its live calls.** One key is one quota, which every source and
   every process holding the key draws on, so a keyed call that one change spends is not
   there for the others. A live call is every request the change sent to an upstream, a
   probe's, a recording's or a live test run's, and the pull request's description counts
   them, the keyed ones by number; `none` is a count.

## Consequences

- One key is one gateway quota. api.data.gov documents a default of 1,000 requests per
  rolling hour per key, which a service may change, reported on every response in
  `X-RateLimit-Limit` and `X-RateLimit-Remaining`. Every package and every process that uses
  the key draws on that one quota, while each package keeps its own per-minute limiter; how
  a package spends the quota is ADR-0033.
- One org secret, `DATA_GOV_API_KEY`, exposed to each repository that needs it; a further
  api.data.gov source extends the secret's repository access instead of adding a secret.
  Locally it is one line in `.envrc`.
- Where this record applies, the environment variable is no longer among the names the slug
  gives (ADR-0006); the MCP entry point, tool prefix and topics still follow it.
- Core reads whatever variable a source names through the `EnvKeyAuth` helpers, and the
  template accepts any `*_API_KEY` answer; the gateway's handling is core's.

Conventions §1, §7 and §10, the review checklist's item 10, the definition of done's Process
block, the README and the docstrings of `xippios.core.data_gov` state its decisions from
1.28 on.

## Amendment 2026-11-24

Amended by ADR-0065 (https://github.com/xippios/sdk-core/issues/485): decision 5 leaves core
with `xippios.core.data_gov`, which goes to the shared package `sdk-usda-fas` of the sources
behind api.data.gov, import `xippios.usda.fas`, and whose first record takes the decision as it
stands here, while decisions 1 to 4, 6 and 7, one key variable for each issuer among them, stand
in core as written.
