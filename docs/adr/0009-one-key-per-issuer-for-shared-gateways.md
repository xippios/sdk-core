# ADR-0009: One key variable per issuer when one key serves several sources

Status: Accepted · Date: 2026-10-23

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
- Otherwise `<SOURCE>_API_KEY` stays. `NASS_API_KEY`, already an issuer's name, does
  not change.
- The variable is the template answer `api_key_env`, as for any source, and it still
  ends in `_API_KEY`, so the template's validator and the rule never to read or print
  such a variable apply unchanged.
- The §1 example list replaces `usda-fas` with `usda-psd`, `usda-esr` and `usda-gats`:
  the portal is three APIs and gets three packages, nested under one provider by
  ADR-0006 (`xippios.usda.psd`, `xippios.usda.esr`, `xippios.usda.gats`).

## Consequences

- One key is one gateway quota. api.data.gov's default is 1,000 requests per rolling
  hour per key, a service may set its own, and every response reports the quota in
  `X-RateLimit-Limit` and `X-RateLimit-Remaining`. Every package and every process that
  uses the key draws on that one quota, while each package keeps its own per-minute
  limiter; how a package spends the quota is ADR-0010.
- One org secret, `DATA_GOV_API_KEY`, exposed to each repository that needs it; a
  further api.data.gov source extends the secret's repository access instead of adding
  a secret. Locally it is one line in `.envrc`.
- Where this ADR applies, the environment variable is no longer among the names the
  slug gives (ADR-0006); the MCP entry point, tool prefix and topics still follow it.
- Docs only. Core reads whatever variable a source names (`resolve_api_key`, the
  `EnvKeyAuth` helpers) and the template accepts any `*_API_KEY` answer, so nothing in
  code waits.
