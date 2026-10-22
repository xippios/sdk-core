# ADR-0005: Credentials never enter the result envelope; core is exempt from the upstream snapshot

Status: Accepted · Date: 2026-10-22

## Context

`ResultMeta.request` records the parameters a task function used, for reproducibility.
It is serialised into every MCP tool result and every HTTP response. A task that
passes its request parameters straight through would put an API key sent as a query
parameter (USDA NASS does this) into agent context, logs and stores.

Separately, conventions §13 lists `docs/upstream/FETCHED.md` as a required file.
`sdk-core` wraps no upstream, so the definition of done could not be ticked honestly
for it.

## Decision

- `ResultMeta` redacts, at construction, the value of every `request` key whose name
  looks like a credential: `key`, `api_key`, `token`, `secret`, `password`, `auth`,
  `signature`, `credential`, as whole words separated by `_` or `-`, at any nesting
  depth. The value becomes the string `"REDACTED"`. Enforcing this in the model rather
  than in an adapter covers MCP, HTTP and plain Python callers alike.
- Reproducibility is preserved by naming the variable, not the value: the credential
  comes from the environment by convention §7, so the name is enough.
- `sdk-core` is exempt from `docs/upstream/`; every `xippios-<source>` package still
  requires it.

## Consequences

- An envelope is safe to return anywhere by construction; adapters need no second
  scrub.
- A parameter whose name matches the pattern but is not a credential (a `sort_key`,
  say) is redacted too. That is the accepted cost; `request` is provenance, not the
  canonical copy of the parameters.
- The fixture recorder in `xippios.core.testing` keeps its own, more generous
  pattern: fixtures are committed to git, so over-redaction there is the safe side.
