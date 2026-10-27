# ADR-0019: Bulk downloads and non-JSON payloads in core

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview; the family review of 2026-10-25, C15; decision 5's two format rules from the
briefings review of the same day)

## Context

Core's client decodes JSON (`decode_json`), stores every answer in the response cache
without a size bound, replays fixtures that hold one JSON exchange, and the adapters
register every task in `tasks.py`. That fits the released sources. The next five do not:
ESMIS (a JSON catalog whose payload is file links; PDF, TXT, ZIP, XLS), WASDE (XLS or
XML tables, a CSV to verify, through ESMIS), NASS bulk datasets (gzipped TSV of hundreds
of MB with Quick Stats' columns), Eurostat (JSON-stat 2.0 cubes and SDMX-CSV; datasets
of tens of MB; the SDMX series parameter `key` would be redacted as a credential,
ADR-0005, review C10), FAOSTAT (JSON plus bulk ZIP/CSV; the API keyed by a login token,
probed 2026-10-26; paging unverified).

The family review of 2026-10-25 named what is missing and asked for the shape before
those sessions start. Without it each session writes its own download-and-parse, as
three sources wrote the api.data.gov gateway client (ADR-0015, review C14).

## Decision

1. **Streaming download.** Core's client gets
   `download(url, dest, *, auth=USE_CLIENT_DEFAULT) -> Downloaded`: streams the body to
   `dest` (written under a temporary name, renamed when complete, removed on failure),
   never holds it in memory, never touches the response cache. The limiter, the hooks
   (`before_request`, `observe`), `classify` and the retry rule (ADR-0011: idempotent
   methods only; a retry restarts the file) apply as they do to `get()`. `Downloaded`
   carries `path`, `bytes`, `content_type`, the file name from `Content-Disposition`
   when sent, `etag`, `last_modified`, `retrieved_at`.
2. **Text and CSV decode.** `decode_text(response)` (charset from `Content-Type`, UTF-8
   default, BOM stripped) and `decode_csv(source, *, delimiter=",")` (stdlib `csv`,
   `DictReader`, headers as upstream prints them) join `decode_json`. gzip and zip are
   opened with the stdlib by the source. Core ships no XML, spreadsheet or PDF parser
   (ADR-0020).
3. **A byte bound on the cache.** `ClientConfig.cache_max_bytes` (default 8 MiB): a
   larger body is passed through and not stored. `cache_filter` stays for finer rules. A
   source that wants a larger list cached raises the bound and says why in `CLAUDE.md`.
4. **Bulk tasks are Python-only.** A task named in `BULK_TASKS` (a frozenset in
   `tasks.py`, beside `MCP_CAPS`) is skipped by `register_tasks` and
   `router_from_tasks`. It returns `Result[Downloaded]` or `Result[list[T]]` read from
   the file. No adapter ever returns a file path to an agent. The MCP surface of a bulk
   source is its catalog tasks (which files exist, with sizes and release identifiers)
   and, where the slice fits the cap (ADR-0016), a filtered read of the file.
5. **Fixtures for files.** A download fixture holds either a small real answer (a short
   date range, one commodity) or the first N rows or bytes of the file: the recorder
   truncates on request (`max_bytes=`), marks the envelope `truncated: true` and keeps
   `original_bytes` and the sha256 of the full file. An XML, ZIP, gzip, XLS or XLSX
   fixture is a small real sample (a short query, one member of the archive, a few
   rows), never a byte-truncated file, since a cut-off binary or compressed file cannot
   be parsed; byte truncation (`max_bytes=`) applies to text bodies, and the recorder
   refuses it for those formats; a JSON array is truncated by elements: the recorder
   keeps the first N, marks it `truncated: true` and records the full count and the
   sha256. Tests assert the parser's shape on the sample, never a size. A fixture file
   a PR adds or changes stays under 256 KiB (definition of done); a fixture over the
   cap recorded before the rule bound stays until a PR re-records it.
6. **C10.** The credential redaction in `ResultMeta.request` and in the recorder's scrub
   spares a parameter named `key` when the client's auth is not a query key
   (`api_key_location != query`); Eurostat's SDMX `key` is data.

## Consequences

- Core 0.3.0, about +250 lines (review C15), with C10. ESR is unaffected; GATS's
  oversized list fixtures wait for the recorder's element truncation (queue row 43).
- Conventions: §6 gains download, decode and the cache bound; §8 and §9 the
  `BULK_TASKS` rule; §10 the fixture rule; §2 says bulk tasks live in `tasks.py` and are
  marked. The definition of done gains the fixture size and the `truncated` marker.
- Testing plugin: the no-network guard covers `download` (same transport); replay
  serves the truncated body.
- Template: `BULK_TASKS = frozenset()` in the scaffold next to `MCP_CAPS`; the file
  fixture rule in `record-fixture.md` (template cleanup, tagged with core 0.3.0).
- Not decided here: XML for Eurostat (its design round); resumable downloads (none; a
  retry restarts the file).

## Amendment 2026-10-27

Core 0.3.0 implements this ADR. Decision 5's recorder option rests on Johannes's
decisions of 2026-10-27, its shape first and then the cut of a JSON array as upstream's
original text; decision 6's mechanism on his decision of the same day; the JSON-object
rule on gate 5 of the same day (queue row 48).

- **Decision 1**: the default of `auth=` is the client's own credentials, core's own
  sentinel as on `request`, `get` and `get_json`, not httpx's `USE_CLIENT_DEFAULT`, which
  core no longer names (ADR-0015, amendment 2026-10-27): `download(url, dest, *,
  auth=<the client's>) -> Downloaded`. Two things differ from `get()`: a success's body
  goes to the file unread, so `observe` and `classify` see its status and headers only (a
  hook that reads the body finds it unread, which counts as nothing observed and as
  `None`), and a 1xx or 3xx answer raises `UpstreamError` where `get()` returns it, since
  redirects are not followed (queue row 82 asks whether a download should follow them).
  `dest` names a file in a directory that exists: a directory, or a missing one, is
  refused with `ValueError` before anything is sent.
- **Decision 2**: `decode_csv(data, *, delimiter=",", source=None)`. The positional
  parameter is `data`, a path (`Path` or `str`) or a response, so that it does not
  collide with the `source=` slug its errors carry, as `decode_json`'s and
  `decode_text`'s do.
- **Decision 5**: one `max_bytes=`, on `record`, `record_sync` and
  `fixture_from_response`, cuts texts and JSON arrays alike; it bounds the body, not the
  fixture file, which escapes the body as a JSON string. A JSON array (a `Content-Type`
  of `application/json` or `...+json`, or a body that parses as JSON, a byte order mark
  allowed) is cut at an element boundary in its original text, never re-serialised: the
  first whole elements that fit in `max_bytes` bytes with a closing `]`, numbers and
  spacing as upstream wrote them, the boundaries found with `json.JSONDecoder.raw_decode`
  (Johannes's decision of 2026-10-27, which replaced the re-serialised cut decided
  earlier that day), and `original_count` records its length. Another text
  is cut at `max_bytes` bytes, back to a whole UTF-8 character and back to the start of
  a secret value or of the request host the cut would split, so no part of one is kept.
  A cut is marked `truncated` with `original_bytes` and `sha256`, both of the whole body
  before the scrub, which then runs on what is kept. A JSON object is refused: the
  source records a small real answer, since an object's parts are no list to take the
  first of; so is a body declared JSON that does not parse, an array whose first element
  alone does not fit, and a text cut that keeps nothing, since an empty sample tells a
  parser test nothing. XML is refused for the reason that a cut-off XML document is not
  well-formed; ZIP, XLSX, gzip, XLS and a body that is not UTF-8 text for the reason
  above. A body within `max_bytes` is kept whole and unmarked, and a fixture that was
  not cut is written without the four fields, as fixtures were before them. Queue row 43
  (sdk-usda-gats) and the family's finding that a cut-off JSON object, a JSON-stat cube,
  does not decode on replay (row 48) are served by this.
- **Decision 6**, the mechanism: the one rule lives in `xippios.core.redaction`. A name
  is a credential when a whole word of it, between `_`, `-` or the ends, is `api_key`
  (also `apikey`, `api-key`), `token`, `secret`, `password`, `passwd`, `pwd`, `auth`,
  `authorization`, `sig`, `signature`, `credential` or `credentials`; a bare `key` is
  not. `sig` and `pwd` are on the list because catalog file links can arrive as
  pre-signed URLs (an Azure SAS carries `sig=`; queue row 84). A
  `QueryKeyAuth(param, ...)` registers `param` when it is built, and the name is a
  credential from then on in the whole process, matched exactly in any letter case: USDA
  NASS's `QueryKeyAuth("key", ...)` makes `key` one, and Eurostat, keyless, keeps its
  SDMX `key` as data. A process that imports both treats `key` as a credential for both.
  `ResultMeta.request`, the recorder's scrub, `sent_urls`, `sent_query`,
  `recorded_query` and `mount_fixture` read the one rule; the recorder's broader
  substring pattern is gone (ADR-0005, amendment 2026-10-27), so `sort_key` and
  `keyword` are data everywhere.
