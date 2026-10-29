# ADR-0025: Google Mail — loopback, the renewing bearer, scopes, the kit's return and the decoded view

Status: Accepted · Date: 2026-10-29 · Decided by Johannes on 2026-10-29 (D108, D109 (5),
D110 (4) for the claude.ai edge, D111; drafted by the family from the investigation of
2026-10-29; the host as the loopback option's second consumer the session's
recommendation, queue row 296)

## Context

The family's next source reads and writes several Gmail mailboxes behind one read server
and one write server, self-hosted (queue row 280). The investigation of 2026-10-29
(`coordination/reviews/2026-10-29-gmail-investigation.md` in the coordination
repository) read Google's OAuth, verification and Gmail API pages, Claude's connector
documentation and the family's own checkouts, and recorded the corrections C1 to C8 and
the facts F1 to F18; its `gmail` names and `GMAIL_*` variables read as D111's below. The
facts this ADR rests on:

- A Desktop-app client is a public client, and its consent runs on a loopback redirect
  with PKCE S256 (F1). A refresh is `POST https://oauth2.googleapis.com/token` with the
  form fields `client_id`, `client_secret`, `grant_type=refresh_token` and
  `refresh_token`, answered with `access_token`, `expires_in`, `scope` and `token_type`
  and no new refresh token (F2). The secret is sent, since Google's pages disagree on
  whether a Desktop client needs it (C2); the access token lives for `expires_in`, not a
  fixed hour (C3). A refresh with a dead refresh token, revoked, six months unused or
  ended in one of the other ways F2 lists, is answered with 400 `invalid_grant`; one
  with a wrong client id or secret with 401 `invalid_client` (F2, C4).
- `gmail.readonly` and `gmail.modify` are restricted scopes (F3). Gmail's error page
  folds a call the grant's scopes do not cover into 401 `authError`, "Invalid
  Credentials"; `insufficientPermissions` appears on other Google APIs' pages only (F8).
- `messages.get` with `format=full` answers the message with its `payload`, a MIME tree
  whose parts carry `partId`, `mimeType`, `filename`, `headers` as name and value pairs,
  and a `body` whose `data` is base64url or an `attachmentId` (the investigation's §2.3,
  from the discovery document, F6).
- Core keeps `ResultMeta.tenant`, `main`'s option hooks, the `confirm` check and the
  loopback rule, which `main` applies to a write server only (`is_write_server`);
  `apply_options(namespace, server)` sees `http`, `host` and `allow_remote`, and a
  `XippiosError` it raises ends the process with exit status 2 (F16; ADR-0014, decisions
  8 and 9; ADR-0024, decision 2). httpx lets an `auth_flow` yield a token request before
  the real one, and the testing plugin pins `EnvKeyAuth.key` offline (F16).
- `Tenants`, `list_task`, the tenant lock and `assert_write_tools` left core in 0.3.0
  for sdk-cashctrl, their one consumer, and nothing replaced them (ADR-0024, decisions 1
  and 6).

Johannes gave sixteen answers on 2026-10-29, to the investigation's fourteen questions,
the write tools and the demo account, and six more to the family's review of the
source's briefing (D108): the write server ships in 0.1.0; `get_message` returns a
decoded view, attachments as metadata only; the kit is copied from sdk-cashctrl with a
queue row naming both consumers; the read server's loopback rule is the source's now and
a core option later; the read server is named `-read` from the first PR; the demo
account is consented with the read scopes first and the write scopes later; no gateway
runbook in the package; `--topic email`. D109 (5) returns the kit to core in 0.4.0. D111
names the source by the USDA pattern, one repository per source under a shared
namespace: repository `sdk-google-mail`, package `xippios-google-mail`, import
`xippios.google.mail`, servers `xippios-google-mail-mcp-read` and
`xippios-google-mail-mcp-write`, and the consent tool `xippios-google-mail-auth`; the
credentials, shared by every Google source, are `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_ACCOUNTS`, `GOOGLE_<NAME>_REFRESH_TOKEN` and the demo
account's `GOOGLE_DEMO_REFRESH_TOKEN`; Google Drive joins later as `sdk-google-drive`,
`xippios.google.drive`. `mail` is Johannes's name for the product, which upstream calls
Gmail: the one departure from conventions §1's rule that a source is named as upstream
names it, dated 2026-10-29.

## Decision

### D-a. The read server stays on loopback

sdk-google-mail's read server reaches every declared mailbox and carries no
authentication, so it is held to loopback as a write server is: `--http` serves it on
`127.0.0.1`, `localhost` or `::1` only, unless `--allow-remote` is passed, with a
gateway in front (the investigation's §2.6 (a)). In 0.1.0 the source checks it in
`apply_options` (ADR-0014, decision 8; F16): a non-loopback `--host` without the flag
raises `ConfigError`, "the read server of xippios-google-mail reaches mailboxes and
carries no authentication; serve it on a loopback --host or pass --allow-remote behind a
gateway", and the process ends with exit status 2. The loopback names are a private copy
of core's `_LOOPBACK_HOSTS`, with a comment naming queue row 282 (ADR-0023, decision 4).
The core option, `build_server(..., loopback_only=True)` recorded beside the write
servers and read by `main`'s remote check, has its second consumer in the host
xippios-mcp, so it enters core 0.4.0 with the kit and the renewing-bearer base (queue
row 282; ADR-0023, decision 2); the host as that consumer is the session's
recommendation of 2026-10-29 (queue row 296; ADR-0026, decision 5), which Johannes can
overturn at G3 of the conventions 1.23 PR.

Rejected (the investigation's §4, D-a): loopback by default for every read server, which
would change every data source's deployment; and a rule keyed on tenancy, since the
property is the data's sensitivity, not the number of tenants.

### D-b. The renewing bearer

`RefreshTokenAuth(EnvKeyAuth)`, in the source's `_auth.py`: its key is the long-lived
refresh token, `GOOGLE_<NAME>_REFRESH_TOKEN` (the placeholder offline, F16), and its
`auth_flow` obtains and renews the short-lived access token in memory, one per tenant
client. It yields F2's token request, the client id and secret read from the environment
at that moment, when no access token is held or the one held expires within 60 seconds
of its `expires_in` (C3); keeps the answer's `access_token`, `expires_in` and granted
`scope`; yields the real request with `Authorization: Bearer`; and on a 401 refreshes
once more. A 400 `invalid_grant` is the `AuthError` that names the account and says to
re-run the consent tool ("account <name>: refresh token revoked or expired; re-run
xippios-google-mail-auth --account <name> and set GOOGLE_<NAME>_REFRESH_TOKEN"); a 401
`invalid_client` is a `ConfigError` naming the client variables (F2, C4; the
investigation's §2.1). Only `auth_flow` differs from `BearerAuth`, and an error inside
it is never retried. The account registry's digest covers the long-lived credential
only, `Tenants("google", list_var="GOOGLE_ACCOUNTS", fields=("REFRESH_TOKEN",),
reserved=("demo",))`, so a refresh rebuilds no client (§2.6 (b)). Nothing is written to
disk.

Rejected (§4, D-b): a token file or a keyring, since the environment is the contract
(conventions §7); and an access token in the environment, which expires within the hour
and would rotate the digest on every refresh.

Its shape is queue row 252's second consumer (ADR-0023, decision 2 counts the same
shape): sdk-faostat's `LoginAuth` exchanges a login for a bearer and sdk-google-mail's
auth a refresh token, each with a margin and one more exchange on a 401. Core 0.4.0
takes a renewing-bearer base with faostat's login and google-mail's refresh as its two
token requests (row 252, the family's status of 2026-10-29); until then `_auth.py`
carries a comment naming the row.

### D-c. A grant's scopes are upstream's to enforce

Each account is consented once, for the scope set its deployment needs: `read`, which is
`gmail.readonly`, or `write`, which is `gmail.modify` and serves every read method too
(F3; the investigation's §2.3; queue row 280). Neither server checks a grant before a
call. Upstream refuses a call the grant does not cover, and `classify` turns that answer
into the re-consent `AuthError`, naming the granted set and the set to re-run with
("account <name> was granted <scopes>; this tool needs gmail.modify; re-run
xippios-google-mail-auth --account <name> --scopes write"), the granted set read from
the refresh answer's `scope`, which the auth keeps (§2.6 (c)). Gmail's page folds the
refusal into 401 `authError` (F8); the demo account is consented with `read` first and
with `write` later, so the source's probe records the real shape before `classify` is
written against it (D108).

Rejected (§4, D-c): per-task pre-checks, a second code path beside upstream's own; and
one consent for both servers, a `write` grant for a deployment that only reads, since
`gmail.modify` widens what it can do.

### D-d. The kit returns to core

sdk-google-mail copies from sdk-cashctrl what sdk-cashctrl carries under ADR-0024,
decision 1, each piece with one comment naming queue row 281 (ADR-0023, decision 4): (a)
`Tenants`, (b) `list_task`, (c) the binding lock wrapper (sdk-cashctrl's `--org`,
sdk-google-mail's `--account`), (d) `assert_write_tools` and (e) the demo-only conftest
strip, the row's five pieces, and (f) the `_cli.py` serve command that binds an account
and starts the server, its sixth (row 281, extended 2026-10-29). Each piece then has two
consumers (ADR-0023, decision 2), so the six return to core in 0.4.0, which reverses
ADR-0024's decision 6, "nothing replaces what leaves", for them (D108, D109 (5);
ADR-0024's amendment of 2026-10-29). Both sources adopt them at their next minor:
sdk-google-mail at 0.2.0, sdk-cashctrl with its core 0.4.0 adoption.

Beside the kit, what the Google sources share, the Desktop-app client, the refresh-token
auth, the consent tool and the account registry, moves to core as `xippios.core.google`
when sdk-google-drive is its second consumer, as `xippios.core.data_gov` did for the
sources behind api.data.gov (D111).

### The decoded view

`get_message` makes one `format=full` call and returns a decoded view of the MIME tree
(the investigation's §2.4; D108): `id`, `thread_id`, `label_ids`, `internal_date`,
`size_estimate` and `snippet`; `headers`, upstream's name and value pairs cut to an
allowlist, From, To, Cc, Bcc, Date, Subject, Message-ID, In-Reply-To and References;
`text`, the first `text/plain` part decoded; `html`, on request only; and `attachments`
as metadata, `part_id`, `filename`, `mime_type`, `size` and `attachment_id`, with no
attachment content in 0.1.0. Decoding the tree is parsing a value, conventions §3's one
permitted override, and the view picks its fields by MIME role: a projection by role.
The faithful `payload` tree stays on the endpoint wrapper's model (ADR-0003). Over the
cap a long `text` or `html` comes back as a preview plus the note (ADR-0016).

## Consequences

- Conventions 1.23: §1 lists `google-mail` among the sources, with the dated sentence on
  `mail`, the `-read` and `-write` entry points (ADR-0026) and sdk-google-mail's
  `GOOGLE_<NAME>_REFRESH_TOKEN` beside sdk-cashctrl's per-tenant variable; §3 states
  that a MIME message's decoded view is a projection by role; §13 gains the topic
  `email`.
- Dated lines under ADR-0014 (the kit's return), ADR-0023 (the kit's and the renewing
  bearer's two consumers) and ADR-0024 (decision 6 reversed for the kit).
- Core 0.4.0's code: the kit (queue row 281), the renewing-bearer base (row 252) and the
  `loopback_only` option (row 282), two consumers each, the option's second the host
  xippios-mcp, the session's recommendation of 2026-10-29, which Johannes can overturn
  at G3 (row 296; ADR-0026, decision 5). Nothing in `xippios.core` changes with this
  ADR.
- sdk-google-mail 0.1.0 (queue row 280): its PR 3, the accounts and the auth, follows
  this ADR on sdk-core `main`.
- No gateway runbook in sdk-google-mail: its servers serve Streamable HTTP on loopback,
  read no header and validate no token. claude.ai needs an OAuth authorization server at
  the edge (F11), which the host xippios-mcp brings when it first serves claude.ai
  (D108; ADR-0026, decision 10; D110 (4)).
