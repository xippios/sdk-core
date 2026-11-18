# ADR-0030: Credentials never enter the result envelope; core is exempt from the upstream snapshot

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0005

## Context

`ResultMeta.request` records the parameters a task function used, for reproducibility, and
is serialised into every MCP tool result and every HTTP response; a task that passes its
parameters straight through would put a key sent as a query parameter into agent context,
logs and stores. Error text reaches the same places. And `sdk-core` wraps no upstream, so it
cannot keep the `docs/upstream/` that conventions §13 requires. This record states ADR-0005
with its amendments of 2026-10-23, 2026-10-27 (two) and 2026-11-18 as they stand, and changes
no decision; their history stays in ADR-0005.

## Decision

1. **The envelope redacts credentials.** `ResultMeta` redacts, at construction, the value of
   every `request` key whose name is a credential, at any nesting depth; the value becomes
   the string `"REDACTED"`. A name is a credential when a whole word of it, separated by `_`
   or `-`, is `api_key`, `token`, `secret`, `password`, `passwd`, `pwd`, `auth`,
   `authorization`, `sig`, `signature`, `credential` or `credentials`; a bare `key` is a
   credential only where a `QueryKeyAuth` sends the key under that name (USDA NASS). The
   rule is one module, `xippios.core.redaction`, read by `ResultMeta`, the fixture recorder
   and the replay helpers alike (ADR-0040, decision 6). Enforcing it in the model rather
   than in an adapter covers MCP, HTTP and plain Python callers alike.
2. **Reproducibility names the variable, not the value**: the credential comes from the
   environment by conventions §7, so the name is enough.
3. **`sdk-core` is exempt from `docs/upstream/`**; every `xippios-<source>` package still
   requires it.
4. **Error messages follow the same rule.** `error_from_response` names the request's method
   and path, never its host or its query string (`404 from GET /v1/series: ...`), and
   `error_from_exception` replaces the host with `<host>` where a transport failure's text
   quotes it (a TLS hostname mismatch does): the query string can carry a key, and the host
   of a multi-tenant source names the tenant. `xippios.core.errors.request_description(response)`,
   which `xippios.core` exports beside `error_from_response`, gives the method and path that
   its messages name, `GET /v1/x` for an answer to `https://host.test/v1/x?year=2024`, and a
   source's own messages name the request with it; `download`'s refusal of a 1xx or 3xx
   names the request with it too. A quota policy's refusal of a request it does not send is
   written before any answer exists, and names the request's method and path from the
   request itself. A message that shows the path as sent, its percent-escapes kept, keeps
   its own. The decoders' subject, `response from <path>`, names a path their caller may
   give for a response built without a request, and stays. A body the upstream echoes into
   the message or into `UpstreamError.body` remains the source's to scrub in `classify`.
5. **Fixtures follow the same rule.** The recorder keeps no more generous pattern of its own:
   the whole-word rule of decision 1 applies to fixtures as to the envelope. The backstops
   for fixtures are the named values of `Scrub(secrets=...)`, the verify step and the
   definition of done's grep of every fixture for key patterns. The verify step searches
   each value of `Scrub(secrets=...)` as given, a plain substring, in the URL, the header
   values and the text bodies of a recording; the JSON-decoded and percent-encoded forms are
   the source's recorder's to look for (ADR-0042, decision 3).
6. **Nobody who works in a repository reads a credential.** Nobody who works in a repository
   of the family, a person or an agent, reads or prints `.envrc`, `.env` or a variable that
   holds a credential, each one the package reads a credential from and any whose name ends
   in `_API_KEY`, `_TOKEN` or `_SECRET`, and a leak check greps the files for key patterns,
   never comparing against a key. The suffix `_TOKEN` takes in sdk-google-mail's
   `GOOGLE_DEMO_REFRESH_TOKEN` and the host's bearer variables, whose names a config's
   `token_env` gives and the host requires to end in `_TOKEN`.

## Consequences

- An envelope is safe to return anywhere by construction; adapters need no second scrub.
- A parameter whose name matches the rule but is not a credential is redacted too. That is
  the accepted cost; `request` is provenance, not the canonical copy of the parameters. A
  `sort_key` is data, since a bare `key` is not on the list.

Conventions §4, §5, §7 and §13, the review checklist's Before judging, the README and the
docstrings of `xippios.core.errors`, `xippios.core.redaction`, `ResultMeta`,
`xippios.core.data_gov`, `xippios.core.tenants`, `build_server`, the testing plugin and
`Scrub` state its decisions from 1.28 on.
