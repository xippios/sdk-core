# ADR-0028: Upstream fidelity — no cross-source normalization in SDK packages

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0003

## Context

The family's sources use incompatible concepts, marketing years and calendar years, HS, PSD
and FAOSTAT codes, bushels and tonnes, and agents already know the upstream vocabularies from
the public documentation. A common schema is product logic, and it changes as the product
learns. This record states ADR-0003 with its amendments of 2026-10-24, 2026-10-26, 2026-10-28
and 2026-11-18 as they stand, and changes no decision; each point's history, who found it and
which source showed it, stays in ADR-0003.

## Decision

1. **Packages mirror upstream.** SDK packages mirror upstream naming and semantics. They
   perform within-source hygiene only: typing, parsing, enums, pagination, errors,
   reference data. They never map one source's concept onto another's. Normalization,
   reconciliation and vintage logic live in product repositories that consume these
   packages. A `project` override that drops a documented personal identifier (ADR-0017)
   applies inside a kept list field too: a person's `bankAccounts` is kept and each account
   is projected without its `iban` (`bankAccounts[].iban`); such an override is still
   parsing only, since nothing is renamed or computed.
2. **Fidelity in names.** Fidelity in names is owed to what a consumer sees: `meta.endpoint`,
   which keeps the upstream operation name verbatim; the first line of a wrapper's
   docstring, which names it; the snapshot under `docs/upstream/`; and the packaged
   parameter names, a packaged list's file and its `param` named by the upstream parameter
   (ADR-0041). The Python identifiers of a layer-1 wrapper, its module and its function,
   carry the upstream operation name in snake case, from the operation's id in the snapshot
   (an OpenAPI `operationId`, a WADL method id), else from the path, minus a controller
   prefix the whole API shares (`ESRData_`, `PSDData_`, `GATSData_`). An id that restates
   the path, with or without the HTTP method (a generator's slug), or that is an opaque hex
   id, is no name and counts as absent. A file suffix that tells operations on one path
   apart stays as the last word, the default `.json` dropped (`order/document/read.pdf` is
   `order_document_read_pdf`); upstream's spelling survives the transform. The task layer
   and the MCP tool names are unchanged by it. Johannes decided it on 2026-10-28.
3. **A wrapper's fixture directory.** A wrapper's fixtures live in a directory named after
   it, `tests/fixtures/<wrapper>/`, and a fixture recorded through a task under the task
   (conventions §10). A wrapper whose every exchange is recorded through a task has no
   directory of its own, as sdk-google-mail records `messages_get` through `get_message`
   and `search_messages`. Where two wrappers of a package carry one name, as two service
   modules of conventions §2 can, each one's directory is `<service>_<wrapper>`,
   `<service>` its module's name, and the pull request that adds the second wrapper moves
   the first one's fixtures, content unchanged. An exchange of an auth flow, a login or a
   token refresh, lives under the name a wrapper of its operation carries by §2, as
   sdk-faostat's login lives under `auth_login`, and one sent to another host than the base
   URL's under that host's first label and its path, as sdk-google-mail's refresh at
   `https://oauth2.googleapis.com/token` lives under `oauth2_token`. Two path names that
   repeat across services would collide in §2's modules of one operation each before they
   reach a directory; §2 does not name that wrapper, and this decision leaves it to §2,
   under https://github.com/xippios/sdk-core/issues/287.
4. **The snapshot.** The upstream documentation is snapshotted into `docs/upstream/` so the
   agent reads the real reference offline, and so documentation changes are visible as
   diffs. The snapshot is fetched, never edited by hand, and a review traces every parameter
   and default to it.
   - Vendor documentation is reproduced in the snapshot for reference: its `FETCHED.md`
     carries the copyright line as the documentation states it and the URL the text was
     fetched from, and says that the text is reproduced as the package's reference under
     this record; sdk-cashctrl's section "Attribution and vendor examples" has the form. A
     vendor's objection is honoured by replacing the snapshot with a summary in the
     package's own words, by PR like any refresh, that keeps the URL and the names and
     semantics the wrappers rely on. Johannes decided it on 2026-10-23.
   - `Fetched` in `FETCHED.md` is the UTC time of the run in ISO 8601 with an explicit `Z`
     (`2026-10-24T09:15:00Z`). A table that a Markdown pipe table cannot hold, one with
     merged cells (`rowspan`, `colspan`) or with a table nested in it, is kept as its HTML
     in the Markdown snapshot, and one line in `FETCHED.md` says so. Johannes decided both
     on 2026-10-24.
   - A source whose API is one part of a shared upstream document snapshots its own part
     and records the full document's byte size and sha256 in `FETCHED.md`, so a refresh can
     tell a change in its part from a change elsewhere in the whole.
   - An adoption PR (conventions §15), which fetches nothing, leaves
     `docs/upstream/FETCHED.md` to the next `/refresh-upstream` and ports only the capture
     script's
     changes (`scripts/refresh_upstream.py`, where the source keeps one). `FETCHED.md`
     records a fetch, so a rule that changes what it records reaches it with the next run
     that fetches.
5. **What upstream does but never documents.** It goes in one hand-written file,
   `docs/upstream/OBSERVED.md`, the one file under `docs/upstream/` written by hand: the
   capture script neither writes nor checks it, and `FETCHED.md` lists it in a row of its
   own that says so. Each note names its evidence. A way the live API departs from its
   documentation, a type, a field, an answer's shape or a refusal, names the probe that
   showed it: its date, its operation and its sample, a request or the fixture that holds
   the answer. A file layout that no upstream page documents, the file-format notes of
   ADR-0020, decision 2 where upstream wrote none, names the files it was written from, with
   their release ids or URLs, bytes and sha256. A parameter or a default traceable to a note
   there is traceable to `docs/upstream/`. A source moves what it keeps elsewhere into the
   file with its next refresh of `docs/upstream/`, the PR that changes the snapshot and
   `FETCHED.md`.
6. **The pages a snapshot leaves out.** A page that the documentation links and the snapshot
   deliberately does not request, such as a feed, a third-party specification (cited, not
   snapshotted), an API answer or a page that is not API documentation, has a row with its
   reason in a table of `FETCHED.md` headed `Not fetched`. A page that an anonymous client
   cannot read is requested once, without credentials. The capture follows no redirect to
   another host and imitates no browser, the page's row in that table records the status and
   the host it redirects to, and the public pages that state the same facts are the
   snapshot's statement of the subject.
7. **Answer samples.** A small answer of the API, kept verbatim under
   `docs/upstream/samples/`, documents the answer's shape and is not a test fixture: its row
   in `FETCHED.md`'s file table gives the URL it was requested from and says that it is a
   sample. A sample whose operation needs the source's credentials is requested with them;
   only the samples' requests send a credential, and neither a credential nor a token is
   written.
8. **The test bodies that are not recorded where they are served.** Unit tests replay
   recorded fixtures, never hand-written ones (conventions §10), and a test that serves a
   body upstream documents and will not give on request, or a recording where it was not
   recorded, says so in its docstring, `NOT RECORDED`, and says where its body comes from
   where it builds it. Five kinds of body serve so, each as the sources use it.
   - A body the snapshot documents is read verbatim from `docs/upstream/` at test time, so it
     is neither recorded nor written by hand: sdk-eurostat's asynchronous `warning` and
     single-object `error` from its user guide.
   - A body composed from what the snapshot documents, a row of a documented table or a
     documented error, takes the shape upstream was recorded answering: sdk-eurostat's
     faults 100, 140 and 150 from the fault table in its recorded `error` array,
     api.data.gov's documented `NOT_FOUND` in sdk-usda-psd, sdk-usda-esr and sdk-usda-gats.
   - A recorded answer or sample is served at another URL, with `mount_fixture(url=)` or in
     memory, for a state upstream answers alike there, within one operation, as sdk-usda-esr
     serves its recorded empty answer at other market years, or behind one gateway, as
     sdk-usda-gats serves the api.data.gov 429 that sdk-usda-psd recorded; or anywhere for a
     test that asserts only what was sent, the answer unchecked, as sdk-eurostat serves its
     main base's STATINFO sample at the Comext base's codelist path. It never stands for a
     state another operation was never seen in, such as an exports answer's `[]` served as
     an empty release list.
   - A recorded answer or sample changed in memory, at another status, with a header
     replaced or removed, or with a field, a cell or a byte changed, shows a form upstream
     was not seen to send: sdk-eurostat's recorded asynchronous `error` array served at HTTP
     200, sdk-usda-psd's empty 404 with its content type upper-cased, sdk-faostat's and
     sdk-eurostat's samples cut or changed to show a parser's refusal.
   - A body of no shape upstream sends shows that the source leaves it to core, as
     sdk-usda-esr's 400 in another shape does.

   The test asserts what the source does with such a body, never that upstream sends it.
   Once upstream is recorded giving a documented answer, the recording replaces the
   documented body; a documented shape never seen keeps its test where the recorded answer
   takes another, as sdk-eurostat's `warning` stays beside the Statistics API's asynchronous
   answer recorded as an `error` array at HTTP 413. `mount_fixture`'s docstring says how far
   `url=` moves a recording.

## Consequences

- Packages stay valid as the product's schema evolves; they are reusable by anyone.
- Field names look different across packages. That is correct, not a defect.
- The product layer carries the full cost of normalization and owns its audit trail
  (source-shaped landing tables, normalized views on top).

Conventions §2, §3, §4, §10 and §15, the review checklist's items 2, 4 and 16, the
definition of done's Tests block, the README and the docstrings of `decode_csv` and
`mount_fixture` state its decisions from 1.28 on.
