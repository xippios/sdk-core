# ADR-0009: One key variable per issuer when one key serves several sources

Status: Accepted · Date: 2026-10-23 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

## Context

The FAS Open Data Services portal documents three APIs of USDA's Foreign Agricultural
Service, PSD, ESR and GATS, behind one api.data.gov gateway, `api.fas.usda.gov`. An
api.data.gov key gives access to the APIs of every agency participating in api.data.gov,
and its rate limits apply across all of that key's api.data.gov requests
(https://api.data.gov/docs/developer-manual/, read 2026-10-23).

Conventions §1 names the variable for a key `<SOURCE>_API_KEY`, §7 reads the key from
it, and ADR-0006 counts the environment variable among the things the slug names. For
the three FAS packages that would be `USDA_PSD_API_KEY`, `USDA_ESR_API_KEY` and
`USDA_GATS_API_KEY` holding three copies of one key: three lines in `.envrc`, three org
secrets, three places to rotate it, and three names that hide that the packages share
one quota. The family already has a variable named after an issuer rather than a slug:
`usda-nass` reads `NASS_API_KEY`.

The §1 example list names `usda-fas` as one source for the portal; the portal is three
APIs.

## Decision

- When one key serves several sources, the variable is named after the key's issuer.
  Every source reached through api.data.gov reads `DATA_GOV_API_KEY`: `usda-psd`,
  `usda-esr`, `usda-gats`, and any later one.
- Otherwise `<SOURCE>_API_KEY` stays (`COMTRADE_API_KEY`). usda-nass keeps its
  historical `NASS_API_KEY`, an issuer's name that predates this ADR.
- The variable is the template answer `api_key_env`, as for any source, and it still
  ends in `_API_KEY`, so the template's validator and the rule never to read or print
  such a variable apply unchanged.
- The §1 example list replaces `usda-fas` with `usda-psd`, `usda-esr` and `usda-gats`:
  the portal is three APIs and gets three packages, nested under one provider by
  ADR-0006 (`xippios.usda.psd`, `xippios.usda.esr`, `xippios.usda.gats`).

## Consequences

- One key is one gateway quota. api.data.gov documents a default of 1,000 requests per
  rolling hour per key, which a service may change, reported on every response in
  `X-RateLimit-Limit` and `X-RateLimit-Remaining`. Every package and every process that
  uses the key draws on that one quota, while each package keeps its own per-minute
  limiter; how a package spends the quota is ADR-0010. A caller who wants a separate
  quota passes its own key through the constructor override (§7).
- One org secret, `DATA_GOV_API_KEY`, exposed to each repository that needs it; a
  further api.data.gov source extends the secret's repository access instead of adding
  a secret. Locally it is one line in `.envrc`.
- Where this ADR applies, the environment variable is no longer among the names the
  slug gives (ADR-0006); the MCP entry point, tool prefix and topics still follow it.
- Docs only. Core reads whatever variable a source names (`resolve_api_key`, the
  `EnvKeyAuth` helpers) and the template accepts any `*_API_KEY` answer, so nothing in
  code waits.

## Amendment 2026-10-26

The nightly live tests spend a shared key too, so the shape of the live workflow that
sdk-template renders becomes the rule for every source, stated in conventions §10 from
1.15 on (queue row 29 d). A source runs its live tests in that one workflow,
`.github/workflows/live.yml`: one job, `contents: read`, nightly and on
`workflow_dispatch`, never on a pull request. The org secret named by `api_key_env`
reaches only that job's `uv run pytest -m live` step, so checkout, setup-uv and `uv sync`
never see it. Its start time is derived from the slug and folded onto 01:00 to 05:59 UTC,
so the sources that read one key (`usda-psd`, `usda-esr` and `usda-gats` on
`DATA_GOV_API_KEY`) start at different times and do not draw on the shared hourly quota
together.

Amended by ADR-0002's amendment of 2026-10-27 (core 0.3.0): `resolve_api_key` is no
longer public; core reads whatever variable a source names through the `EnvKeyAuth`
helpers alone.

Amended 2026-10-27 (core 0.3.0; the family review's C14, decided by Johannes on
2026-10-27): `xippios.core.data_gov` is the code side of one key per issuer. Its
`Gateway(source)` gives a source behind api.data.gov the key from `DATA_GOV_API_KEY` in the
`X-Api-Key` header, the gateway's `classify` (its `API_KEY_*`, 429 and `NOT_FOUND` answers
as taxonomy errors in the source's name) and `Gateway.policy`, one `QuotaPolicy` per
process for the key in `DATA_GOV_API_KEY`, which every source in that process shares: a
quota one of them spends, the next request of another waits out or is refused without being
sent (ADR-0010, decision 4). Separate processes still keep a snapshot each. `Gateway` takes
no key of its own, so the consequence's constructor override no longer gives a separate
quota: a key passed to a source's client still draws on `Gateway.policy`'s snapshot, and a
caller with a key of its own, a separate quota, builds its own `HeaderKeyAuth` and
`QuotaPolicy`. The consequence "Docs only" no longer holds for the gateway: its handling is
core's. Like `xippios.core.reference`, the module is imported by its path and keeps an
`__all__` of its own; it is in none of the five export lists of ADR-0004's amendment of
2026-10-27, which name what consumers import from a package. The consumers are
sdk-usda-psd, sdk-usda-esr and sdk-usda-gats, which carried the same code as copies, and
the template's api.data.gov gateway answer, which renders it from template v0.3.0 on
(ADR-0023). Queue rows 30 d and 39 e are closed. Conventions 1.17 names the module in §7.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **The gateway reads its own answers alone** (step 7;
https://github.com/xippios/sdk-core/issues/163). The `classify` of the amendment of
2026-10-27 read every answer, so a 429, 401, 403 or 404 from another host, a bulk file that a
source downloads through its one client, came back as the gateway's error naming
`DATA_GOV_API_KEY`. It now returns `None` for an answer whose request the client marked as
sent to another origin than its base URL's (ADR-0015, amendment 2026-11-18, point d), and
core's status mapping follows; the key does not go there, and the shared policy neither
holds that request back nor reads its answer (point e there). A response built without the
marks, as a source's test builds one with `response_from_fixture`, is read as before.

(b) **FAS's empty 404 on a data path** (step 7; https://github.com/xippios/sdk-core/issues/106,
found by sdk-usda-esr; ADR-0023, decisions 2 and 4). PSD and ESR answer a market year they
hold no data for with HTTP 404, an empty body and `text/plain`, on every data path, and
sdk-usda-psd and sdk-usda-esr each carried `NoDataForYear(NotFoundError)` and the same
branch after the gateway's `classify`. `Gateway(source, data_path=...)` takes the source's
data paths as a pattern that the whole request path matches, and `classify` maps that
answer there to `xippios.core.data_gov.NoDataForYear`, a `NotFoundError` in the source's
name with the request's `path`, whose text names the path and says that the year it names
holds no data; a task raises it again with a text of its own, `NoDataForYear(path, message,
source=...)`. An empty 404 on another path, one with a body or another content type, and
the gateway's `NOT_FOUND` are left to the source and to core, and a gateway without
`data_path`, sdk-usda-gats's, whose data paths answer `[]`, maps none. The class keeps the
name both sources gave it, so their adoption changes an import and deletes their copies.

(c) **A pull request counts its live calls** (the consequences above; step 17;
https://github.com/xippios/sdk-core/issues/208). The definition of done and the review
checklist asked a pull request's description to count the live calls it spent, keyed calls
by number and `none` a count, and no document said why or what counts, once the budgets of
live calls that an earlier way of working kept were gone. The count stays a rule of the
product, for the first consequence above: one key is one quota, which every source and every
process holding the key draws on, so a keyed call that one change spends is not there for
the others. A live call is every request the change sent to an upstream, a probe's, a
recording's or a live test run's, and the description counts them, the keyed ones by number;
`none` is a count.

(d) **A live run's log keeps no payload** (the amendment of 2026-10-26; step 17;
https://github.com/xippios/sdk-core/issues/219). The live workflow of the amendment of
2026-10-26 runs in the source's repository, and the logs of a public repository are
public. Every live run takes `--tb=short --assert=plain`: the first keeps a failing test's
frame arguments out of the log, a raw upstream payload among them, and the second the
values a failed `assert` compares. A live test therefore asserts on shapes and counts,
never on a raw payload. Every source's `live.yml`, as the template renders it, runs
`uv run pytest -m live --tb=short --assert=plain`, and the rule stood in the template's
`.claude/family.md`, which sdk-template 0.3.3 deleted
(https://github.com/xippios/sdk-template/pull/142).

Conventions §7 and the README state points (a) and (b) from 1.28 on, the definition of
done's Process block and the review checklist's item 10 point (c), and conventions §10
point (d).
