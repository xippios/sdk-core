# ADR-0046: The snapshot script's frame in core

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/363 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/428

## Context

Every source keeps `scripts/refresh_upstream.py`, which snapshots its upstream documentation
into `docs/upstream/` (ADR-0028, decision 4). sdk-template renders the script once from its
skeleton, `template/scripts/refresh_upstream.py.jinja`, 966 lines at v0.4.0, and an update
never overwrites a file a source fills, so twelve sources carry twelve copies, 11,191 lines
from 625 to 1,547 each, that kept between 6 and 23 of the skeleton's 61 blocks as they stand.
A rule of the frame reaches no source: the conventions check routed three findings of the
first releases to it, a `FETCHED.md` without its table `Not fetched` and with a redirect to
another host followed (https://github.com/xippios/sdk-usda-esmis/pull/49), and one without
the row of `OBSERVED.md` (https://github.com/xippios/sdk-eurostat/pull/77), and a fourth
from sdk-faostat's review, a hex ETag that the skeleton writes outside a code span
(https://github.com/xippios/sdk-core/issues/340). ADR-0023, decision 1, sends a helper the
template renders into every repository to core. https://github.com/xippios/sdk-core/issues/309
took the frame into sdk-core 0.4.1 (https://github.com/xippios/sdk-core/issues/320), and the
human answered its design question on 2026-11-21, prompted in the sdk-core panel.

Five tests of sdk-cashctrl, sdk-faostat, sdk-usda-esr and sdk-usda-wasde compared the committed
`FETCHED.md` with their script's render and sent no request. They went with the copies
(https://github.com/xippios/sdk-core/pull/424), since the frame compares the file in `--check`
alone, after a request to every page, and its render takes rows that each hold an answer. Two of
them compared prose and the declared tables, two read cells back from the committed file, and
none computed a size or a hash again. The human took a check without a request into the package
(https://github.com/xippios/sdk-core/issues/425) and answered its design question on
2026-11-22, prompted in the sdk-core panel: decision 6, the amendment of that day, is the answer
of https://github.com/xippios/sdk-core/issues/428.

## Decision

1. **The home: `xippios.core.refresh`, with no extra.** The frames of the scripts a source
   runs to refresh what it commits from upstream live in one subpackage: the snapshot's in
   `xippios.core.refresh.upstream`, and the reference lists' in a module beside it
   (https://github.com/xippios/sdk-core/issues/370). The concern has more than one
   internal module, so it is a subpackage by ADR-0029, decision 1, and it needs the standard
   library alone, so it has no extra. It sits on top of ADR-0029's dependency direction,
   beside the adapters: the snapshot frame imports nothing of core's, the reference frame
   imports `reference` below it, and nothing in core imports either, nor does
   `xippios.core` re-export them. Its `__init__` is a sixth public surface beside ADR-0029's
   five, exporting what a source's script imports, and `tests/test_public_surface.py` pins
   it. A converter a source's hooks use, markdownify or Beautiful Soup, stays the source's
   own dependency, since a pin in core would let one core release change five sources'
   snapshots.
2. **The shape: a declaration with hooks, and closed internals.** A source's script holds a
   `Snapshot` with its name, its slug, its pages, its attribution, the pages it leaves out,
   its vocabulary, its paragraph of how it captures, and its hook functions, and calls
   `run(snapshot, argv=None)`, which returns the exit status. The command line is the
   skeleton's, `--out` and `--check`, and `--keyless` where the snapshot declares
   credentials. The hooks see a `Page`, a `Response` or a `Row` and return a value; none of
   them replaces the fetch, the attribution check, `FETCHED.md`, the write or the
   comparison, which are where the twelve copies drifted. The skeleton's slots and hooks are
   the declaration's fields as they stand (`reduce`, `canonical`, `linked`), and the API
   document is one of the pages, so `SPEC_URL` stays a constant of the source's script.
3. **What holds byte for byte.** Every file a source's hooks make is written as they make
   it, so a source's page files stay byte for byte what its script writes today. `FETCHED.md`
   is written in the frame's one form in all twelve sources, and the first run of a source's
   ported script rewrites it once, which ADR-0028, decision 4, allows: a rule that changes
   what `FETCHED.md` records reaches it with the next run that fetches. This narrows the
   proof of https://github.com/xippios/sdk-core/issues/320 to every file but `FETCHED.md`.
4. **The frame's own rules.** Every ETag stands in a code span on a row that ends in the
   secret scan's allowlist mark, hex or not, with no test for hex, since a code span alone
   does not pass the scan. The table `Not fetched` stands under its heading even when it has
   no row, so that its absence never claims anything. A redirect to another host is never
   followed: it stops the run unless the page is recorded by that status, and then its row
   in `Not fetched` names the host. `OBSERVED.md`, where it exists, has a row whose first
   cell is the file's name, which the family check matches. A `Last-Modified` stands in UTC,
   a date that parses without a zone read as GMT, as every form of an HTTP date is (RFC
   9110, section 5.6.7), and one that is no HTTP date as sent, in a code span, so that one
   odd header ends no capture. A file's name stays inside `docs/upstream/`: `FETCHED.md`, an
   absolute name and a `..` part are refused, whether a page declares the name or a `split`
   makes it from an answer. The frame takes no rule on a
   publisher's terms for modified text: the conventions settle
   https://github.com/xippios/sdk-core/issues/58 after the port, since a mark in each
   converted file would change its bytes.
5. **A hook for each thing the copies do beyond the skeleton.** Credentials on the samples
   whose operation needs them, sdk-faostat's login, are a `Credentials` declaration, its
   variables checked by name before anything is fetched, its login called once right before
   the first sample marked `keyed`, its headers sent on those samples alone, under its base,
   with no redirect followed and no retry (conventions §3; ADR-0028, decision 7). A keyed
   sample has the base's origin, its scheme, host and port as parsed, as core's client sends
   its credentials to its base URL's origin alone (ADR-0037, decision 4), and a path under
   the base's by its segments, so that a base with or without its trailing slash admits the
   same samples and a host that only shares its text admits none; a base that cannot be
   compared so, with no host, a user, a query, a fragment or a dot segment, is refused
   before anything is fetched. A file
   kept as recorded where only noise differs, sdk-eurostat's WADL, is a page marked
   `keep_recorded`, whose recorded file a writing run keeps where this run's content is the
   same after `canonical`; sdk-faostat's samples and sdk-x's document, compared that way in
   `--check` alone, take `canonical` as it stands. One page that gives several files,
   sdk-cashctrl's, is a page marked `split`, whose files the snapshot's `split` makes. A
   second origin after a 403, sdk-usda-wasde's USDA CDN origin (conventions §2), is a
   page's `origin`. A wait on a 429, sdk-eurostat's, is `quota_wait`, which reads the wait
   from the 429's headers before the one retry. A section of the source's own in
   `FETCHED.md`, sdk-comtrade's "Products found", is `sections`, placed after "How this is
   captured". A row's note made from its answer, as sdk-faostat's and the FAS portal kit's
   notes count what an answer holds, is `note`, which also stops the run on an answer it
   does not recognise, and sdk-eurostat's five seconds between requests are `pause`.
6. **The check of the committed `FETCHED.md` without a request.** By the human's answer to
   https://github.com/xippios/sdk-core/issues/428, given in the sdk-core panel on 2026-11-22:
   - *The mark of the form.* The frame ends `FETCHED.md` with one line that names the form of
     the file, `<!-- form 1 of the FETCHED.md that xippios.core.refresh writes -->`, an HTML
     comment that renders as nothing, holds nothing the secret scan flags and names the
     module that writes it, which is true in every source. `FORM` in
     `xippios.core.refresh.upstream` is its number. No source held a file of the frame when
     the mark entered, so it is part of decision 3's one form, and the first run of a ported
     script writes it. A change of core that rewords anything the frame writes into the file
     raises the form, and a test of core pins the digest of a render that reaches every
     sentence and cell form, so a change of the render that does not raise it fails.
   - *One public function.* `compare_fetched(snapshot, out=None)` of `xippios.core.refresh`
     returns the lines in which the committed file differs from the declaration and sends no
     request. It writes the expected file through the render's own parts, the same function
     that `render_fetched` writes through, with what only a response knows read back from the
     committed file, and names each differing line, `line <n> holds: ...` and `line <n> should
     hold: ...`, then each row whose file is missing and each file without a row. Decision 1's
     sentence that nothing in core imports either frame gains one exception: the family check
     imports this function inside its test, as it imports the adapters (ADR-0029).
   - *What is judged.* Every line that follows from the declaration and from the frame's own
     text; each declared page's row with its file, its URL, its status and the clauses of its
     note that its flags give, a row's URL being the page's or, for a page with `origin`, one
     of its two URLs; the rows of `Not fetched` of the declared pages an anonymous client
     cannot read, by their URL and status, and of `not_fetched`; the row of `OBSERVED.md` where
     the file exists; the form of every ETag's cell, `-` or a code span on a row that ends in
     the allowlist mark, and `-` for a page marked `stable=False`; each row's file under
     `docs/upstream/`, and no file without a row in the subdirectories that a row writes to,
     the bound of the frame's removal of stale files. A declared page's row is told by its
     file, by its URL for a page without one, and every row with a file at a `split` page's
     URL is that page's.
   - *What is read back.* What only a response knows stands in the expected file as the
     committed file holds it and is not judged: the time of the fetch, an ETag's value,
     Last-Modified, Bytes and sha256, the redirect clauses a note holds before the part that
     its page's declaration gives, the rest of a note where the snapshot's `note` makes it, the
     reason of an unread page's row where `note` makes it, the host a page redirects to, the
     row of a page's 403 before its second origin, the names of the files that `split` made,
     the lines from the first heading after the frame's paragraph of how it captures to the
     frame's table of files where the snapshot declares `sections`, and a statement's clause
     that no run checks it where the page's answer decided it. The file is read as the frame
     writes it: its lines split at each line feed alone, a cell with the one space on each
     side taken off and its pipes unescaped, and the tables found from the end, so a source's
     own text that reads like a line of the frame's, a capture that opens like a heading or a
     section that quotes the table, stays the source's (the review of
     https://github.com/xippios/sdk-core/pull/429). A row that
     no declared page owns is read back, after the row it follows, as a page that `linked`
     found where the snapshot declares `linked`, and is otherwise a difference, so a removed
     page and a hand-added row are held only in a snapshot without `linked`. In one sentence of
     the question: what `--check` compares once its five measures are blanked, less the
     answers. Sizes and hashes are not computed again, and `Page` gains no field.
   - *The family check.* `test_family_fetched_md_agrees_with_the_snapshot` loads a source's
     `scripts/refresh_upstream.py` by its path, under a module name of its own so that its
     `if __name__ == "__main__":` block does not run, takes the declaration named `SNAPSHOT` at
     its top level and calls the function. It reads the script first and runs it only where
     its top level assigns `SNAPSHOT`, since a copy of the template's skeleton runs by its
     `# /// script` block with what the project need not install, and urllib's opener refuses
     while it loads, so a script that runs its snapshot at its top level stops before its first
     request and before any write. A source passes with no script, with a script whose
     `SNAPSHOT` is no `Snapshot` or is not assigned at its top level, and with a `FETCHED.md`
     that is missing, holds no mark, as a copy's file and sdk-template's stub do, or holds the
     mark of an older form. A file of a later form is one difference, since this core cannot
     judge it. A script that does not load fails the check, which is never skipped, as
     ADR-0044, decision 4, and ADR-0055 have it for the family check's other new tests. So no
     adoption PR, which fetches nothing, turns red, and a source is held from its first refresh
     on with no line of its own.
   - *The rule.* Conventions §3 say that the script names its declaration `SNAPSHOT` at its
     top level, which imports and declares alone, sends no request and writes no file, its
     run under `if __name__ == "__main__":`, and that the family check holds the committed
     file to it as above.

## Consequences

- The consumers are the twelve sources, each of which ports its script in its patch, and
  sdk-template, which renders the short script on this frame in its 0.4.1
  (https://github.com/xippios/coordinate-sdk/issues/134). A fix of the frame reaches every
  source with its next core patch.
- A source's ported script keeps its pages, its attribution, its hooks and their helpers,
  from 330 lines (sdk-usda-nass) to 1,230 (sdk-eurostat) by the research's count; the
  sdk-template short script, which a new source starts from, is about 70.
- The frame reads a page's visible text, where some copies read the whole body, and its
  search knows four phrases that none of the twelve copies' checks knew (terms and
  conditions, all rights reserved, Creative Commons, CC BY), so a port may record a
  statement or a vocabulary word that its old check never met, and a redirect that a copy
  followed stops the port until the page is recorded by its status.
- A file split from a page into the top of `docs/upstream/` is not removed when the page no
  longer gives it, since the frame removes stale files in the subdirectories it writes to
  alone; sdk-cashctrl's port chooses between that and a subdirectory for its entries. It
  also gives up its run from a saved copy of its page, `--from-file`, its own User-Agent and
  its request for the page gzipped, since the frame takes no option of a source's own,
  writes one User-Agent from the slug and asks for each page as it is; one source needs
  each, and a second would bring it into the frame (ADR-0023, decision 2).
- Decision 6 holds all twelve sources and every source made from sdk-template from their
  first refresh on core 0.4.1, the four whose comparisons went with their copies,
  sdk-cashctrl, sdk-faostat, sdk-usda-esr and sdk-usda-wasde, among them, by the family check
  and with no test of their own (ADR-0023, decision 4, met by those four copies). A source
  that declares `linked` has the rows that no declared page owns read back: six ports do,
  sdk-comtrade, sdk-usda-esmis, sdk-usda-esr, sdk-usda-gats, sdk-usda-psd and
  sdk-usda-wasde, and a source that links no page declares no `linked`, so that a removed
  page's row stays a difference. Whether a script names its declaration `SNAPSHOT` is the
  review's, since the check passes a script that names it otherwise.
- The reference frame (https://github.com/xippios/sdk-core/issues/370) joins as a module of
  this subpackage, and `run` names both frames' entry, so the step that adds it makes `run`
  take either declaration without renaming either.

Conventions §3, the README and the docstrings of `xippios.core.refresh` state its decisions.
