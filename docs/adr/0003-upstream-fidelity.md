# ADR-0003: Upstream fidelity — no cross-source normalization in SDK packages

Status: Superseded by ADR-0028 · Date: 2026-10-20 · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

## Context

The sources (USDA, Comtrade, Eurostat, FAOSTAT, CashCtrl) use incompatible concepts:
marketing years vs calendar years, HS codes vs PSD codes vs FAOSTAT items, bushels vs
tonnes. A common schema is valuable but is product logic, and it changes as the
product learns. Agents, meanwhile, already know upstream vocabularies from the public
documentation.

## Decision

SDK packages mirror upstream naming and semantics. They perform within-source hygiene
only: typing, parsing, enums, pagination, errors, reference data. They never map one
source's concept onto another's. Normalization, reconciliation and vintage logic live
in product repositories that consume these packages.

The upstream documentation is snapshotted into `docs/upstream/` so the agent reads the
real reference offline, and so documentation changes are visible as diffs.

## Consequences

- Packages stay valid as the product's schema evolves; they are reusable by anyone.
- Field names look different across packages. That is correct, not a defect.
- The product layer carries the full cost of normalization and owns its audit trail
  (source-shaped landing tables, normalized views on top).

## Amendment 2026-10-24

Vendor documentation is reproduced in the snapshot for reference. CashCtrl's API page,
the family's first snapshot of a vendor's documentation, is "© 2026 CashCtrl Ltd.", as
its footer states. The snapshot stays: it is what the agent and the reviewer check every
wrapper against, offline and as a diff. Its `FETCHED.md` carries the copyright line as
the documentation states it and the URL the text was fetched from, and says that the
text is reproduced as the package's reference under this ADR; sdk-cashctrl's section
"Attribution and vendor examples" has the form. A vendor's objection is honoured by
replacing the snapshot with a summary in the package's own words, by PR like any
refresh, that keeps the URL and the names and semantics the wrappers rely on. Raised in
the review of sdk-cashctrl's snapshot; Johannes decided it on 2026-10-23, with the
sdk-cashctrl session.

Two rules make snapshots alike across sources. `Fetched` in `FETCHED.md` is the UTC time
of the run in ISO 8601 with an explicit `Z` (`2026-10-24T09:15:00Z`): sdk-comtrade
recorded the local calendar date of its run, sdk-usda-psd and sdk-cashctrl the UTC date,
and nothing said which. A table that a Markdown pipe table cannot hold, one with merged
cells (`rowspan`, `colspan`) or with a table nested in it, is kept as its HTML in the
Markdown snapshot, and one line in `FETCHED.md` says so, as sdk-comtrade's Help Center
articles and sdk-cashctrl's nested parameter tables already do; a pipe table would lose
the cells' structure. Raised by sdk-comtrade; Johannes decided both on 2026-10-24, in
the interview before core PR G.

Conventions §3 states the three rules from 1.13 on.

## Amendment 2026-10-26

Three rules from the queue. Several FAS APIs are described in one shared OpenAPI
document. A source whose API is one part of a shared upstream document snapshots its own
part and records the full document's byte size and sha256 in `FETCHED.md`, so a refresh
can tell a change in its part from a change elsewhere in the whole (queue row 35 d).

A `project` override that drops a documented personal identifier (ADR-0017) applies
inside a kept list field too: a person's `bankAccounts` is kept and each account is
projected without its `iban` (`bankAccounts[].iban`). Such an override is still "parsing
only" in the sense of conventions §3, since nothing is renamed or computed; ADR-0017's
rule reaches nested fields (queue row 37 a).

An adoption PR (conventions §15), which fetches nothing, leaves
`docs/upstream/FETCHED.md` to the next `/refresh-upstream` and ports only the capture
script's changes (`scripts/refresh_upstream.py`, where the source keeps one).
`FETCHED.md` records a fetch, so a rule that changes what it records (`Fetched` as a
UTC time, amendment 2026-10-24) reaches it with the next run that fetches (queue row
37 b).

Conventions §3 states the first two rules from 1.14 on, §15 the third.

## Amendment 2026-10-28

Fidelity in names is owed to what a consumer sees: `meta.endpoint`, which keeps the
upstream operation name verbatim; the first line of a wrapper's docstring, which names
it; the snapshot under `docs/upstream/`; and the packaged parameter names, a packaged
list's file and its `param` named by the upstream parameter (ADR-0022). The Python
identifiers of a layer-1 wrapper, its module and its function, carry the upstream
operation name in snake case, from the operation's id in the snapshot (an OpenAPI
`operationId`, a WADL method id), else from the path, minus a controller prefix the
whole API shares (`ESRData_`, `PSDData_`, `GATSData_`); a file suffix that tells
operations on one path apart stays as the last word, the default `.json` dropped
(sdk-cashctrl's `order/document/read.pdf` is `order_document_read_pdf`); upstream's
spelling survives the transform. A wrapper's fixtures live in a directory named after
it, `tests/fixtures/<wrapper>/`. The task layer and the MCP tool names are unchanged by
it. Raised by the family session's harmonization of the sources' names: sdk-usda-esr,
sdk-usda-psd and sdk-usda-gats named their wrappers with the verbatim `operationId`;
sdk-usda-esmis and sdk-cashctrl in snake case; sdk-comtrade's ids restate the path, with
or without the HTTP method (a generator's slug: `get-getda`, `getmetadata`), or are
opaque hex ids, so they are not names and count as absent, and its wrappers are named
from the path; sdk-usda-nass's `api_GET` kept upstream's case, and so did sdk-eurostat's
four wrappers named by WADL method ids, `getData`, `getTocXml`, `codeListQuery` and
`dataQuery`. Johannes decided it on 2026-10-28.

Conventions §2 and §10 state it from 1.22 on.

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **What upstream does but never documents** (step 14;
https://github.com/xippios/sdk-core/issues/55, found by sdk-usda-esmis, with sdk-faostat
and sdk-usda-wasde). The snapshot is fetched, never edited by hand, and a review traces
every parameter and default to it, so what a source observed of upstream that no page
states had no home, and three sources chose three: sdk-usda-esmis a section of its README,
sdk-faostat a list in its capture script that it prints into `FETCHED.md`, sdk-usda-wasde
a hand-written `docs/upstream/layout.md`. It goes in one hand-written file,
`docs/upstream/OBSERVED.md`, named after sdk-faostat's list and written in capitals as
`FETCHED.md` is, since both are the source's own notes about the snapshot rather than a
page of it. It is the one file under `docs/upstream/` written by hand: the capture script
neither writes nor checks it, and `FETCHED.md` lists it in a row of its own that says so,
as sdk-usda-wasde's row for `layout.md` does. Each note names its evidence. A way the
live API departs from its documentation, a type, a field, an answer's shape or a refusal,
names the probe that showed it: its date, its operation and its sample, a request or the
fixture that holds the answer. A file layout that no upstream page documents, the
file-format notes of ADR-0020, decision 2 where upstream wrote none, names the files it
was written from, with their release ids or URLs, bytes and sha256. A parameter or a
default traceable to a note there is traceable to `docs/upstream/`. A source moves what
it keeps elsewhere into the file with its next refresh of `docs/upstream/`, since a
refresh is the PR that changes the snapshot and `FETCHED.md` (amendment 2026-10-26).

(b) **The pages a snapshot leaves out** (step 14;
https://github.com/xippios/sdk-core/issues/103, found by sdk-eurostat). `FETCHED.md`
recorded only what was fetched, so a reader could not tell a page left out on purpose from
one missed. A page that the documentation links and the snapshot deliberately does not
request, such as a feed, a third-party specification (cited, not snapshotted), an API
answer or a page that is not API documentation, has a row with its reason in a table of
`FETCHED.md` headed `Not fetched`, as sdk-eurostat's has since its first snapshot. A page
that an anonymous client cannot read is requested once, without credentials. The capture
follows no redirect to another host and imitates no browser, the page's row in that table
records the status and the host it redirects to, and the public pages that state the same
facts are the snapshot's statement of the subject, as sdk-eurostat's two pages behind EU
Login are recorded.

(c) **Answer samples** (step 14; https://github.com/xippios/sdk-core/issues/103, found by
sdk-eurostat, with sdk-faostat). A small answer of the API, kept verbatim under
`docs/upstream/samples/`, documents the answer's shape and is not a test fixture: its row
in `FETCHED.md`'s file table gives the URL it was requested from and says that it is a
sample, as each of the four samples of sdk-eurostat and of sdk-faostat does. A sample
whose operation needs the source's credentials is requested with them, as sdk-faostat's
four are with the account's bearer token after one login; only the samples' requests send
a credential, and neither a credential nor a token is written.

(d) **The test bodies that are not recorded where they are served** (the amendment of
2026-10-28; step 16; https://github.com/xippios/sdk-core/issues/64, found by sdk-eurostat,
with sdk-usda-esr, https://github.com/xippios/sdk-core/issues/121). Conventions §10 has
unit tests replay recorded fixtures, never hand-written ones, and the sources test answers
that upstream documents and will not give on request, and serve recordings where they were
not recorded, each test saying so in its docstring, `NOT RECORDED`. Five kinds of body
serve so, each as the sources use it, and the test says where its body comes from where it
builds it. A body the snapshot documents is read verbatim from `docs/upstream/` at test
time, so it is neither recorded nor written by hand: sdk-eurostat's asynchronous `warning`
and single-object `error` from its user guide, after four datasets in the documented band
answered synchronously. A body composed from what the snapshot documents, a row of a
documented table or a documented error, takes the shape upstream was recorded answering:
sdk-eurostat's faults 100, 140 and 150 from the fault table in its recorded `error` array,
api.data.gov's documented `NOT_FOUND` in sdk-usda-psd, sdk-usda-esr and sdk-usda-gats. A
recorded answer or sample is served at another URL, with `mount_fixture(url=)` or in
memory, for a state upstream answers alike there, within one operation, as sdk-usda-esr
serves its recorded empty answer at other market years, or behind one gateway, as
sdk-usda-gats serves the api.data.gov 429 that sdk-usda-psd recorded; or anywhere for a
test that asserts only what was sent, the answer unchecked, as sdk-eurostat serves its
main base's STATINFO sample at the Comext base's codelist path. It never stands for a
state another operation was never seen in: the review of an sdk-usda-esr change refused an
exports answer's `[]` served as an empty release list. A recorded answer or sample changed
in memory, at another status, with a header replaced or removed, or with a field, a cell
or a byte changed, shows a form upstream was not seen to send: sdk-eurostat's recorded
asynchronous `error` array served at HTTP 200, sdk-usda-psd's empty 404 with its content
type upper-cased, sdk-faostat's and sdk-eurostat's samples cut or changed to show a
parser's refusal. A body of no shape upstream sends shows that the source leaves it to
core, as sdk-usda-esr's 400 in another shape does. The test asserts what the source does
with such a body, never that upstream sends it. Once upstream is recorded giving a
documented answer, the recording replaces the documented body, as sdk-eurostat's SDMX
envelope and SOAP fault did on the Comext base; a documented shape never seen keeps its
test where the recorded answer takes another, as sdk-eurostat's `warning` stays beside the
Statistics API's asynchronous answer recorded as an `error` array at HTTP 413.
`mount_fixture`'s docstring says how far `url=` moves a recording.

(e) **The fixture directory where a wrapper's name repeats or none applies** (the
amendment of 2026-10-28; step 16; https://github.com/xippios/sdk-core/issues/147, found by
the family session, with sdk-comtrade, https://github.com/xippios/sdk-core/issues/173 and
https://github.com/xippios/sdk-core/issues/174). The amendment of 2026-10-28 names a
wrapper's fixture directory after it, and conventions §10 a fixture recorded through a
task after the task. Three cases took no directory. A wrapper whose every exchange is
recorded through a task has none of its own, as sdk-google-mail records `messages_get`
through `get_message` and `search_messages`; the review checklist's item 16 excepts it.
Where two wrappers of a package carry one name, as two service modules of conventions §2
can, each one's directory is `<service>_<wrapper>`, `<service>` its module's name, and the
pull request that adds the second wrapper moves the first one's fixtures, content
unchanged: sdk-eurostat's asynchronous API would give a second `get_data` beside
`api/statistics.py`'s. An exchange of an auth flow, a login or a token refresh, goes
through neither a wrapper nor a task; it lives under the name a wrapper of its operation
carries by §2, as sdk-faostat's login lives under its wrapper's, `auth_login`, and one
sent to another host than the base URL's under that host's first label and its path, as
sdk-google-mail's refresh at `https://oauth2.googleapis.com/token` lives under
`oauth2_token`. Two path names that repeat across services, sdk-comtrade's `public/v1`
twins of its `data/v1` operations, would collide in §2's modules of one operation each
before they reach a directory; §2 does not name that wrapper, and this point leaves it to
§2, under https://github.com/xippios/sdk-core/issues/287.

Conventions §3 and the review checklist's item 2 state points (a) to (c) from 1.28 on;
conventions §10, the review checklist's item 4, the definition of done's Tests block, the
README and `mount_fixture`'s docstring point (d); and conventions §10 and the review
checklist's item 16 point (e).
