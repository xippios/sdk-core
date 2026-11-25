# ADR-0062: The two refresh frames: one declaration, one table header, the fetch through the client and no check without a request

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/482 · Supersedes ADR-0046 · Supersedes ADR-0051

## Context

Core 0.4.1 took the frames of a source's two refresh scripts into `xippios.core.refresh`: the
snapshot of the upstream documentation under `docs/upstream/` with its `FETCHED.md` (ADR-0046),
and the packaged lists under `reference/` with `enums.py` (ADR-0051). ADR-0046 holds two
amendments of 2026-11-22: its decision 6, the check of a committed `FETCHED.md` without a
request (https://github.com/xippios/sdk-core/issues/428), and its decision 7, what the
attribution check reads and accepts (https://github.com/xippios/sdk-core/issues/437).

The design sitting of core 0.5.0 asked what the two frames declare, fetch, share and leave out.
The maintainer's answer on https://github.com/xippios/sdk-core/issues/482 gives the reference
frame one declaration beside `Snapshot` under one `run`, has the snapshot frame fetch through
core's client, sends what one source needs to that source's script, and sends the api.data.gov
gateway and the FAS portal's kit of three snapshot scripts to one shared package of the USDA
sources, which the answer on https://github.com/xippios/sdk-core/issues/485, part 3, names
`sdk-usda-fas`. Part 3 of the answer on https://github.com/xippios/sdk-core/issues/483 takes
back the answer of 2026-11-22 that took the check without a request in: `--check` at a refresh
is the one comparison, and each refresh writes the file whole. Part 4 of the answer on
https://github.com/xippios/sdk-core/issues/485 counts the second header of the provenance
table, which core calls the FAS sources', among the pieces of core shaped for one publisher.
The answer on https://github.com/xippios/sdk-core/issues/475 lets the unread members and
parameters of the frames leave, and keeps the family check's own test of the row of
`OBSERVED.md` until every source's `FETCHED.md` carries the frame's mark.

ADR-0046's decisions 1, 2, 5 and 6 change, and so do ADR-0051's decisions 1, 2 and 4, so this
record supersedes both whole. It numbers its decisions anew, restates each decision of the two
that stands and names each part that it reverses. When it was written no source had run a
ported script against its upstream, and no committed `FETCHED.md` carried the frame's mark
(https://github.com/xippios/sdk-core/issues/475, part 5), so the check of ADR-0046, decision 6,
had judged no source.

## Decision

1. **The home: `xippios.core.refresh`, with no extra.** Carried from ADR-0046, decision 1, and
   ADR-0051, decision 1. The frames of the scripts that a source runs to refresh what it commits
   from upstream live in one subpackage, the snapshot's in `xippios.core.refresh.upstream` and
   the reference lists' in `xippios.core.refresh.reference` beside it: the concern has more than
   one internal module, so it is a subpackage by ADR-0029, decision 1. It sits on top of
   ADR-0029's dependency direction, beside the adapters. The snapshot frame imports core's
   client (decision 4), the reference frame imports `client`, `models` and `reference` below it
   and `upstream` beside it, and nothing in core imports either frame, nor does `xippios.core`
   re-export them: the one exception that ADR-0046, decision 6, made, the family check's import
   of `compare_fetched`, leaves with it (decision 9). Core's client needs no extra of core, so
   the subpackage has none; this reverses ADR-0046, decision 1, by which the snapshot frame
   imported nothing of core's and needed the standard library alone. Its `__init__` is a sixth
   public surface beside ADR-0029's five, exporting what a source's script imports, and
   `tests/test_public_surface.py` pins it. A converter that a source's hooks use, markdownify or
   Beautiful Soup, stays the source's own dependency, since a pin in core would let one core
   release change several sources' snapshots, and no rule makes one way from HTML to Markdown:
   the converters that sdk-eurostat, sdk-usda-esmis and sdk-faostat wrote on the standard
   library stay theirs (https://github.com/xippios/sdk-core/issues/482, part 5).
2. **One declaration per frame, and one entry.** A source's snapshot script declares a
   `Snapshot`, and its reference script a `Lists(package, lists, packaged, client,
   quota_header, before, after)`, a frozen dataclass beside it. `run(declaration, argv=None)` is
   the one signature of both frames and returns the exit status
   (https://github.com/xippios/sdk-core/issues/482, part 1). The two overloads of `run`, its six
   keywords and its two `TypeError`s leave, which reverses ADR-0051, decision 1, where the lists
   were handed to `run(lists, argv=None, *, package, client, quota_header=None, before=None,
   after=None)`. As ADR-0051, decision 1, had it, a source's two scripts import their
   declarations and `run` from one surface, and neither frame's entry takes a second name.
3. **The snapshot's declaration: hooks, and closed internals.** Carried from ADR-0046,
   decision 2. A `Snapshot` holds the source's name, its slug, its pages, its attribution, the
   pages it leaves out, its vocabulary, its paragraph of how it captures and its hook functions.
   The hooks see a `Page`, a `Response` or a `Row` and return a value, and none of them replaces
   the fetch, the attribution check, `FETCHED.md`, the write or the comparison, which are where
   the twelve copies of the template's skeleton drifted. The skeleton's slots and hooks are the
   declaration's fields (`reduce`, `canonical`, `linked`), and the API document is one of the
   pages. The command line is `--check`, and `--keyless` where a sample sends a credential, which
   fetches and compares the pages that send none and writes nothing. `--out` leaves, since the
   declaration's `out` names where the snapshot stands
   (https://github.com/xippios/sdk-core/issues/475, part 7). The script names its `Snapshot`
   `SNAPSHOT` at its top level, which imports and declares alone, sends no request and writes no
   file, its run under `if __name__ == "__main__":`. ADR-0046, decision 6, set that form so that
   the family check could load the script; the loader leaves (decision 9), and the form stays as
   the one that sdk-template renders, which the review holds and no check of core reads.
4. **The snapshot frame fetches through core's client.** The frame sends each request through
   `AsyncClient`, one that it builds from the slug or one that a source hands it as
   `Snapshot.client`, runs it on core's loop and keeps its own record of redirects, and its own
   fetch on `urllib` leaves (https://github.com/xippios/sdk-core/issues/482, part 2). It names
   itself in a request's header as the client does, `xippios-<slug>/<version>`, so how each
   documentation host answers that client shows only at a source's first refresh, and a host
   that refuses it there reopens part 2 of that answer. The credentials of a keyed sample, with
   the frame's own rule of where they go, and the wait after a 429 become the client's, so
   `Credentials` and `quota_wait` leave the declaration
   (https://github.com/xippios/sdk-core/issues/482, part 3), which reverses those parts of
   ADR-0046, decision 5. What the fetch promised stands: every page is fetched before anything
   is written, one request at a time after the snapshot's `pause`, two seconds by default, each
   URL retried at most once after a network error or a 5xx; no browser is imitated. Only a keyed
   sample sends a credential, to the origin of its base URL alone, as ADR-0037, decision 4, has
   it for the client, and a keyed sample follows no redirect and is never retried by the frame;
   a renewing auth sends it once more after a refused bearer (ADR-0025); neither a
   credential nor a token is written, and `FETCHED.md` names the variables that a login reads,
   never their values (ADR-0028, decision 7). The run counts each request that the client hands
   to its transport, the token requests of a renewing auth and its resend among them, those of
   a call that an error ends and a refused login's included, and prints the count as its last
   line, a failed run's too, as decision 14 has the reference frame print it; the client's
   rebuilt answer keeps the earlier answers of an auth's flow in its `history` as statuses
   alone, with no body, header or request (https://github.com/xippios/sdk-core/issues/579,
   https://github.com/xippios/sdk-core/pull/580). The frame's reader of a JSON answer takes a name of its own, since the
   root's `load_json` is another function, and the `indent` of that reader and of the frame's
   JSON writer leaves (https://github.com/xippios/sdk-core/issues/475, part 7). A second reader,
   `parse_json`, parses a JSON answer, refuses a key twice and returns the document as served,
   held to no form, for a hook that writes nothing of it again; `read_json` reads through it,
   and a source keeps no reader of its own that refuses a duplicate key alone (ADR-0059,
   decision 5; https://github.com/xippios/sdk-core/issues/579).
5. **What a source's hooks carry.** Carried from ADR-0046, decision 5, without the fields that
   leave it. A page that gives several files is a page marked `split`, whose files the
   snapshot's `split` makes: one source, sdk-cashctrl, needs it, and it stays, since no hook of
   a source can write a second file (https://github.com/xippios/sdk-core/issues/482, part 3). A
   section of the source's own in `FETCHED.md`, sdk-comtrade's "Products found", is `sections`,
   placed after "How this is captured". A check of one page against another, the FAS portal
   kit's comparison of its two documents say, runs in `sections` too, which sees every row after
   the last request and before anything is written, returns `()` where it adds no section and
   stops the run with `changed` where the pages disagree. A row's note made from its answer, as
   sdk-faostat's and the FAS portal kit's notes count what an answer holds, is `note`, which also
   stops the run on an answer it does not recognise. sdk-eurostat's five seconds between requests
   are `pause`, and a sample whose operation needs the source's credentials, sdk-faostat's, is a
   page marked `keyed`. `canonical` is the form in which `--check` compares a file, as sdk-faostat's
   samples and sdk-x's document take it. A file kept as recorded where only noise differs,
   sdk-eurostat's WADL, is kept by the source's `reduce` hook, and a page that answers 403 where the
   publisher serves a copy from a second origin, sdk-usda-wasde's, is declared twice, the refused
   page and its copy (https://github.com/xippios/sdk-core/issues/482, part 3), so
   `Page.keep_recorded` and `Page.origin` leave, which reverses those parts of ADR-0046, decision 5.
   The FAS portal's kit that three snapshot scripts carry, the reader of the portal's shell and of
   its Swagger UI, the cut of the shared Swagger document to one API and the comparison of the two
   documents, stands in `sdk-usda-fas` and enters no module of core
   (https://github.com/xippios/sdk-core/issues/482, part 4;
   https://github.com/xippios/sdk-core/issues/485, part 3). Every hook stops the run with
   `changed(url, what)` on a page that it does not recognise.
6. **What holds byte for byte.** Carried from ADR-0046, decision 3. Every file that a source's
   hooks make is written as they make it. `FETCHED.md` is written in the frame's one form in
   every source, and the first run that fetches on a frame of a new form rewrites it whole, which
   ADR-0028, decision 4, allows: a rule that changes what `FETCHED.md` records reaches a source
   with its next run that fetches. The fetch through the client changes what the frame writes,
   its name in a request's header among it, so that change raises the form (decision 8).
7. **The frame's own rules.** Carried from ADR-0046, decision 4, and its Consequences. Every
   ETag stands in a code span on a row that ends in the secret scan's allowlist mark, hex or not,
   with no test for hex, since a code span alone does not pass the scan. The table `Not fetched`
   stands under its heading even when it has no row, so that its absence never claims anything. A
   redirect to another host is never followed: it stops the run unless the page is recorded by
   that status, and then its row in `Not fetched` names the host. `OBSERVED.md`, where it exists,
   has a row whose first cell is the file's name, which the family check matches (ADR-0044). A
   `Last-Modified` stands in UTC, a date that parses without a zone read as GMT, as every form of
   an HTTP date is (RFC 9110, section 5.6.7), and one that is no HTTP date as sent, in a code
   span, so that one odd header ends no capture. A value written into a cell keeps its row on one
   line: a line feed, with a carriage return before it, is written as a space, as the frame's
   paragraphs write one, and any other character that splits a text into lines as given
   (https://github.com/xippios/sdk-core/issues/434). A file's name stays inside
   `docs/upstream/`: `FETCHED.md`, an absolute name and a `..` part are refused, whether a page
   declares the name or a `split` makes it from an answer. Files that the run does not produce
   are removed from the subdirectories it writes to and nothing else under `docs/upstream/` is
   touched, so a file split into the top of `docs/upstream/` is not removed when the page no
   longer gives it. The frame takes no rule on a publisher's terms for modified text, which the
   conventions settle (https://github.com/xippios/sdk-core/issues/58), since a mark in each
   converted file would change its bytes.
8. **The mark of the form.** Carried from ADR-0046, decision 6. The frame ends `FETCHED.md` with
   one line that names the form of the file, `<!-- form 1 of the FETCHED.md that
   xippios.core.refresh writes -->`, an HTML comment that renders as nothing, holds nothing the
   secret scan flags and names the module that writes it, and `FORM` in
   `xippios.core.refresh.upstream` is its number. A change of core that rewords anything the
   frame writes into the file raises the form, and a test of core pins the digest of a render
   that reaches every sentence and cell form, so a change of the render that does not raise it
   fails. The frame keeps writing the mark while nothing in core reads it: the family check's own
   test of the row of `OBSERVED.md` (ADR-0044) leaves in a release after 0.5.0, once every
   source's `FETCHED.md` carries the mark (https://github.com/xippios/sdk-core/issues/475,
   part 5).
9. **No check without a request.** `--check` at a refresh is the one comparison of a snapshot,
   and each refresh writes `FETCHED.md` whole (https://github.com/xippios/sdk-core/issues/483,
   part 3). `compare_fetched` leaves `xippios.core.refresh` with its helpers, and the family
   check's test `test_family_fetched_md_agrees_with_the_snapshot` leaves with its loader of the
   script. This reverses the rest of ADR-0046, decision 6: its public function, what it judged
   and what it read back, the family check's test, and the rule of the conventions that the
   family check holds the committed file to the script's declaration. `--check`, carried from
   ADR-0046, decision 2, fetches every page and writes nothing, and it exits 1 when a file differs
   from what upstream serves now, compared after `canonical`, or when `FETCHED.md` would change
   in more than its rows' measures, Fetched, Bytes, sha256, ETag and Last-Modified; a measure
   that moved while the content stayed is an information line, never a change. It reads the
   committed file at its line feeds alone, the carriage return of a checkout that ends its lines
   in CRLF dropped, so a note that holds another character that splits a text into lines passes
   it right after the write that made the file (https://github.com/xippios/sdk-core/issues/434).
10. **What the attribution check reads and accepts.** Carried from ADR-0046, decision 7, and its
    Consequences. Every run stops, before writing, when a page that it reads states a copyright,
    a licence or terms of use that the attribution does not record, or no longer prints one that
    it records. A statement recorded with a link passes only as the text of a link to the
    recorded target, the target taken without the white space around it and made absolute against
    the page's URL, and its text flattened, on every page that prints the link; the same words in
    prose, or linked to another target, stop the run. A statement without a link and every word of
    the vocabulary are read past wherever they stand, after the links, and a statement or a word
    whose text is empty or white space is read past nowhere. A page that is no HTML has no link,
    so there a linked statement's words are searched as any others. The reader takes the `alt` of
    an `img` where the image stands, set apart from the words around it, and as part of the text
    of a link it stands in, and no other attribute; where an alternative text stands, the search
    reads the text twice, with it and without it, both read past the recorded links, the
    statements and the vocabulary, and words of the search in either stop the run. A statement
    shows on its own page its text and, with a link, a link of its text to its target; a terms
    page, `terms=True`, must print each statement recorded from it and is searched no further;
    a sample, a page that an anonymous client cannot read and a binary body are not read. A JSON
    body whose top level holds `openapi` or `swagger` is an API document: each of `license`,
    `termsOfService` and `contact` that its `info` holds is quoted by a statement recorded from
    that document, its text or link equal to the field's value or, for an object, to one of its
    values, and the three then leave the document's text before the search, while a document in
    YAML or another form is searched as text whole.
11. **The reference frame: one `Listed` per list.** Carried from ADR-0051, decision 2, without
    its unread members. A source's script declares each list with its name, the file
    `reference/<name>.json` and the name `--only` takes; its fetch through the source's `api/`
    wrappers, async or not; the upstream operation and parameter its file records; its
    `Enumeration`, if any; and its origin. A fetch answers records, a model's by
    `dump_upstream` and a mapping as it is, or a finished `PackagedList`, written as built, whose
    `param` and `endpoint` must be those its `Listed` declares where it declares them. Since
    every `api/` wrapper answers an `Answer` by `get_answer`
    (https://github.com/xippios/sdk-core/issues/479), a fetch may answer the wrapper's `Answer`
    whose `payload` is those records, which the frame reads as the records, so a wrapper is a
    fetch as it stands and a source needs no function of its own that only takes the payload;
    an `Answer` of anything else, the body that holds the records say, stops the run and says
    to hand the records (https://github.com/xippios/sdk-core/issues/577). The fetch that answers
    plain values leaves, with `Enumeration.values` and `Enumeration.key`
    (https://github.com/xippios/sdk-core/issues/475, part 7), which reverses that part of
    ADR-0051, decision 2. `Lists.package` is the source's import path, as `PackagedList.load`
    takes it: the frame writes into its directory as imported, and refuses one outside the
    directory the script runs in, an installed copy. `Lists.packaged` names the lists the package
    declares it ships, and the lists declared must be exactly those, or the run stops before a
    request and names the lists declared on one side alone; the frame takes the names from the
    source and reads no `params` of its own.
12. **When a list was fetched.** Carried from ADR-0051, decision 3, without the values that
    leave. The fetch carries the moment: records are stamped when their fetch returned, an
    `Answer`'s too, and a finished list keeps its own `fetched`, the wrapper's `retrieved_at`,
    the time of its first request or the time its file was complete, so no source's `fetched`
    changes its meaning.
13. **The packaged files, `enums.py` and one table header.** Carried from ADR-0051, decision 4,
    but for its second header. The packaged files are `PackagedList.write`'s. `enums.py` is one
    render in the order the lists are declared, each `Enumeration` naming the field its values
    are read from, or the fields of its ids and names for an `IntEnum`, its class name and its
    members named by hand, a mapping or a function of the values; where no list declares an enum,
    `enums.py` is left alone, hand-written or empty. The renderer, which the reference frame alone
    calls, stands in the frame's module, in the workbench that the statement of core's surface
    counts apart from the run-time part (https://github.com/xippios/sdk-core/issues/485, part 7).
    The frame knows one header of the provenance table of `reference/README.md`, the one that
    sdk-template renders, and writes the count of a file's records into every table or into none,
    as that header has the column or not. The second header, `| File | Origin | Fetched (UTC) |
    Records |`, the FAS sources', leaves with its test, and the sources that keep it take the
    template's header at their adoption (https://github.com/xippios/sdk-core/issues/485, part 4),
    which reverses that part of ADR-0051, decision 4. Each list's row is rewritten where it
    stands, from its file: its Origin a declared text, a function of the written list or by
    default its endpoint in a code span, and its `fetched` in UTC to the second. A row of a file
    that no list declares is kept, the template's `(none yet)` is dropped, and a list without a
    row gets one after the others.
14. **The run of the reference frame.** Carried from ADR-0051, decision 5. The command line takes
    `--only LIST [LIST ...]` or `--render-only`, one choice. Every list is fetched before the
    first file is written, through the declaration's client with one attempt per request for the
    run, so a 5xx or a 429 spends no second call of upstream's quota, and the run prints the
    requests it sent and the quota left in `quota_header`, a failed run's too, a request that
    ended in a transport error counted as sent, and each token request and resend of a renewing
    auth counted as the client sends it, a refused login's too
    (https://github.com/xippios/sdk-core/issues/579, https://github.com/xippios/sdk-core/pull/580). Every file the run writes is made before the first
    write: the packaged files in a temporary directory outside the repository, the rows, and
    `enums.py` formatted by `ruff format` and `ruff check --fix` under the configuration the
    repository gives its path. The files are then written as one: a write that fails halfway, or
    an interrupt, puts back each file the run replaced and removes each it made, and the error is
    raised, so a run that fails leaves the tree as it was. `--only` fetches the lists it names and
    keeps every other list's file, which must be packaged already, and `--render-only` writes the
    rows and `enums.py` from the packaged files, without a request or a key; both check what they
    need before the first request.
15. **Two hooks beside the lists.** Carried from ADR-0051, decision 6. `before` is called once
    the command line and the declaration are checked and before the first request, for what can
    stop a run before it spends one; `after` is called after the last write with the lists the
    run fetched, by name, for what a script writes beside them. `--render-only` calls neither.
    `after` runs once the frame's files stand written whole, so a hook that raises leaves them
    written and consistent with one another, the run says so before the hook's error ends it, and
    a hook makes what it writes before it writes, as the frame does.
16. **What stays the source's.** Carried from ADR-0051, decision 7, and ADR-0046's Consequences.
    Neither frame takes an option of a source's own: a script that keeps one reads it before the
    call and passes the rest as `argv`, and what one source needs around the call stays there,
    sdk-faostat's count of its logins in the reference script and sdk-usda-nass's longer read
    timeout among it. A second source that needs the same brings it into the frame by the rule of
    entry (ADR-0059, decision 5).

## Consequences

- The consumers are the twelve sources, which run the snapshot frame, the nine of them that
  package lists, which run the reference frame, and sdk-template, which renders both short
  scripts. `sdk-usda-fas` carries the FAS portal's kit, and sdk-usda-psd, sdk-usda-esr and
  sdk-usda-gats take it from there. Of the pieces that the frames keep, four have one consumer
  each, named by ADR-0059, decision 2: `split` (sdk-cashctrl), `Snapshot.pause` (sdk-eurostat),
  `Page.keyed` (sdk-faostat) and `Lists.before` (sdk-usda-nass); they stay, since nothing leaves
  by the count alone (https://github.com/xippios/sdk-core/issues/485, part 6).
- Decision 9 hands a source nothing to delete: no source's code calls `compare_fetched`, and the
  family check's test leaves every source with the core update. Each source's first refresh on
  core 0.5.0 writes its `FETCHED.md` whole, in the form that decision 6 raises. Between two
  refreshes nothing notices a `FETCHED.md` out of step with its script's declaration, the cost
  that the answer on https://github.com/xippios/sdk-core/issues/483 accepted, and the four
  sources whose own comparisons went with their copies in 0.4.1, sdk-cashctrl, sdk-faostat,
  sdk-usda-esr and sdk-usda-wasde, get no check without a request back.
- Decisions 2, 11 and 13 change one call of each reference script, to `run(Lists(...))`, and the
  `reference/README.md` of each source that keeps the FAS header takes the template's header.
  Decisions 4 and 5 move sdk-faostat's login to its client, sdk-eurostat's wait after a 429 to
  its client and its kept WADL to its `reduce` hook, and sdk-usda-wasde's refused pages to two
  declared pages each. A fetch through the client shows only on the wire, so each source's first
  capture on core 0.5.0 is a networked run with the maintainer's consent and its count of
  requests.
- This record is written before the changes of 0.5.0 that build decisions 2, 4, 5 and 6 and the
  changed parts of decisions 11 and 13, and until each merges the code of the frames is as
  ADR-0046 and ADR-0051 left it. A sentence of the conventions, the README or a docstring that
  cites ADR-0046 or ADR-0051 cites this record once a change of 0.5.0 words it anew; the change
  that writes this record words anew the sentences of the check without a request, of the mark
  of the form and of the script's form.
- ADR-0046 and ADR-0051 stay in the tree, marked superseded, the history of 0.4.1. ADR-0044 is
  not changed: the row of `OBSERVED.md` keeps its test.

Conventions §3, the README and the docstrings of `xippios.core.refresh` state its decisions.
