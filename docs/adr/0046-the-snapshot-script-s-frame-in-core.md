# ADR-0046: The snapshot script's frame in core

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/363

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
- The reference frame (https://github.com/xippios/sdk-core/issues/370) joins as a module of
  this subpackage, and `run` names both frames' entry, so the step that adds it makes `run`
  take either declaration without renaming either.

Conventions §3, the README and the docstrings of `xippios.core.refresh` state its decisions.
