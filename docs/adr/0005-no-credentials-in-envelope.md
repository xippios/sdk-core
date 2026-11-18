# ADR-0005: Credentials never enter the result envelope; core is exempt from the upstream snapshot

Status: Superseded by ADR-0030 · Date: 2026-10-22 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

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

## Amendment 2026-10-23

Error messages follow the same rule as the envelope: `error_from_response` names the
request's method and path, never its host or its query string
(`404 from GET /v1/series: ...`), and `error_from_exception` replaces the host with
`<host>` where a transport failure's text quotes it (a TLS hostname mismatch does).
The query string can carry a key (usda-nass sends `key=`). The host of a multi-tenant
source names the tenant: CashCtrl serves every organisation from its own subdomain,
which sdk-cashctrl treats like a key and had to mask in its own `classify` while core
put the host into every `AuthError`, `NotFoundError`, `RateLimitError` and
`UpstreamError` message (found in the review of sdk-cashctrl's first endpoints,
2026-10-23). Error text reaches agents, logs and problem details as the envelope does.
A body the upstream echoes into the message or into `UpstreamError.body` remains the
source's to scrub in `classify`.

## Amendment 2026-10-27

Core 0.3.0 makes the rule one module, `xippios.core.redaction`, read by `ResultMeta`, the
fixture recorder and the replay helpers alike (ADR-0019, amendment 2026-10-27, decision
6). Two sentences above no longer hold. The list of words loses a bare `key`, which is a
credential only where a `QueryKeyAuth` sends the key under that name (USDA NASS), and
gains `passwd`, `authorization` and `credentials`, which the code already matched, and
`pwd` and `sig`, for pre-signed URLs (ADR-0019, amendment 2026-10-27); so a `sort_key`
is data, not redacted. And the recorder keeps no more generous pattern of its
own: its substring match (`keyword`, `author` and `passport` redacted) is gone, and the
whole-word rule applies to fixtures as to the envelope. The backstops for fixtures stay
the named values of `Scrub(secrets=...)`, the verify step and the definition of done's
grep of every fixture for key patterns.

Amended 2026-10-27 (ADR-0024): the verify step named above searches each value of
`Scrub(secrets=...)` as given, a plain substring, in the URL, the header values and the
text bodies of a recording; the JSON-decoded and percent-encoded forms it searched before
are the source's recorder's to look for.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **The request description is public** (the amendment of 2026-10-23; step 11;
https://github.com/xippios/sdk-core/issues/62, found by sdk-eurostat; ADR-0023, decision
2). `xippios.core.errors.request_description(response)`, which `xippios.core` exports
beside `error_from_response`, gives the method and path that `error_from_response`'s
messages name, `GET /v1/x` for an answer to `https://host.test/v1/x?year=2024`, and
replaces core's private copy, and `download`'s refusal of a 1xx or 3xx names the request
with it too. A quota policy's refusal of a request it does not send is written before any
answer exists, and names the request's method and path from the request itself.
sdk-eurostat and sdk-x each kept a copy as `_where`, and sdk-faostat, sdk-google-mail and
sdk-usda-esmis wrote it inline in their `classify` and their auth errors, so the rule
above is now one function that a source's own messages name the request with; their
adoption of core 0.4.0 deletes the copies. A message that shows the path as sent, its
percent-escapes kept, as sdk-usda-esmis's refusal of an encoded slash does, keeps its own.
The decoders' subject, `response from <path>`, names a path their caller may give for a
response built without a request, and stays.

(b) **Nobody who works in a repository reads a credential** (step 17;
https://github.com/xippios/sdk-core/issues/219, with the suffix of
https://github.com/xippios/sdk-core/issues/172, found by xippios-mcp). The decision and its
amendments keep a credential out of the envelope, error text and fixtures; that whoever works
in a source never reads or prints `.envrc`, `.env` or a credential variable stood in the
review checklist, for a review alone, and in the template's `.claude/family.md`, which
sdk-template 0.3.3 deleted (https://github.com/xippios/sdk-template/pull/142). Conventions §7
states it for every repository of the family: nobody who works in one, a person or an agent,
reads or prints `.envrc`, `.env` or a variable that holds a credential, each one the package
reads a credential from and any whose name ends in `_API_KEY`, `_TOKEN` or `_SECRET`, and a
leak check greps the files for key patterns, never comparing against a key. The suffix
`_TOKEN` replaces `_REFRESH_TOKEN` beside `_API_KEY` and `_SECRET`: it takes in
sdk-google-mail's `GOOGLE_DEMO_REFRESH_TOKEN` and the host's bearer variables, whose names a
config's `token_env` gives and the host requires to end in `_TOKEN`.

Conventions §5, the README and `request_description`'s docstring state point (a) from 1.28
on, and conventions §7 and the review checklist's Before judging point (b).
