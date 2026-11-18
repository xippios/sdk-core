# ADR-0040: Bulk downloads and non-JSON payloads in core

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0019

## Context

Core's client decoded JSON, cached every answer without a size bound, replayed fixtures of one
JSON exchange and registered every task as a tool, while ESMIS, WASDE, the NASS bulk datasets,
Eurostat and FAOSTAT publish files, tables of tens or hundreds of MB, and Eurostat's SDMX
series parameter `key` read as a credential. Johannes decided the shape on 2026-10-26, from
the family review of 2026-10-25. This record states ADR-0019 with its amendments of
2026-10-27 (two), 2026-11-13 and 2026-11-18 as they stand, and changes no decision; their
history stays in ADR-0019.

## Decision

1. **Streaming download.** Core's client has `download(url, dest, *, auth=<the client's>)
   -> Downloaded`: it streams the body to `dest`, written under a temporary name through
   `tempfile.mkstemp`, renamed when complete and removed on failure, never holds it in
   memory and never touches the response cache. The file's mode is `0600`, which the rename
   keeps, also over a file of another mode, since a file fetched with a key is its owner's
   until the caller shares it; `download`'s and `Downloaded`'s documents state it. The
   limiter, the hooks (`before_request`, `observe`), `classify` and the retry rule
   (ADR-0011: idempotent methods only; a retry restarts the file) apply as they do to
   `get()`, with two differences: a success's body goes to the file unread, so `observe` and
   `classify` see its status and headers only (a hook that reads the body finds it unread,
   which counts as nothing observed and as `None`), and a 1xx or 3xx answer raises
   `UpstreamError` where `get()` returns it, since redirects are not followed. `dest` names a
   file in a directory that exists: a directory, or a missing one, is refused with
   `InvalidRequestError` in the client's source's name, `dest is a directory; name the file
   to write` or `dest's directory does not exist; create it first`, before anything is
   sent, `before_request` included (ADR-0007). A source that refuses a bad `dest` before a
   request that comes ahead of the download keeps its check, so that a bad `dest` costs no
   request. `Downloaded` carries `path`, `bytes`, `content_type`, the file name from
   `Content-Disposition` when sent, `etag`, `last_modified` and `retrieved_at`.
2. **Text and CSV decode.** `decode_text(response)` (charset from `Content-Type`, UTF-8
   default, a byte order mark stripped) and `decode_csv(data, *, delimiter=",",
   source=None)` (stdlib `csv`, `DictReader`, headers as upstream prints them) join
   `decode_json`. `data` is a path (`Path` or `str`), a response or an open text stream, such
   as `io.TextIOWrapper(gzip.open(path), encoding="utf-8-sig", newline="")` or a ZIP member
   wrapped alike, read row by row from where it stands, a leading byte order mark stripped
   as a path's is, and left open for the caller that opened it to close. Its error names the
   stream's file name without the directories, or `stream` for a stream without one, and the
   stream's encoding where it is not UTF-8; a binary stream is refused with `TypeError` at
   the first row, naming `io.TextIOWrapper`. gzip and zip are opened with the stdlib by the
   source, since which member to read is the source's to know. Core ships no XML,
   spreadsheet or PDF parser (ADR-0020).
3. **A byte bound on the cache.** `ClientConfig.cache_max_bytes` (default 8 MiB): a larger
   body is passed through and not stored. `cache_filter` stays for finer rules. A source that
   wants a larger list cached raises the bound and says why in `CLAUDE.md`.
4. **Bulk tasks are Python-only.** A task named in `BULK_TASKS` (a frozenset in `tasks.py`,
   beside `MCP_CAPS`) is skipped by `register_tasks` and `router_from_tasks`. It returns
   `Result[Downloaded]` or `Result[list[T]]` read from the file. No adapter ever returns a
   file path to an agent. The MCP surface of a bulk source is its catalog tasks (which files
   exist, with sizes and release identifiers) and, where the slice fits the cap (ADR-0038),
   a filtered read of the file.
5. **Fixtures for files.** A download fixture holds either a small real answer (a short date
   range, one commodity) or the first part of the file, which the recorder cuts on request.
   - One `max_bytes=`, on `record`, `record_sync` and `fixture_from_response`, cuts texts and
     JSON arrays alike; it bounds the body, not the fixture file, which escapes the body as a
     JSON string. A JSON array (a `Content-Type` of `application/json` or `...+json`, or a
     body that parses as JSON, a byte order mark allowed) is cut at an element boundary in
     its original text, never re-serialised: the first whole elements that fit in
     `max_bytes` bytes with a closing `]`, numbers and spacing as upstream wrote them, the
     boundaries found with `json.JSONDecoder.raw_decode` (Johannes, 2026-10-27), and
     `original_count` records its length. "Cut the array that a top-level key names, and keep
     the last elements on request" (https://github.com/xippios/sdk-core/issues/237):
     `array_key=` names a top-level key of a JSON object, and the cut takes the array it
     holds at its element boundaries, the rest of the object kept as upstream wrote it and
     counted in `max_bytes`; `keep="last"` keeps the array's last whole elements that fit,
     after the opening `[`, for a list ordered oldest first, and `"first"`, the default, the
     first ones. The text after a top-level array, a final newline say, is kept too. Another
     text is cut at `max_bytes` bytes, back to a whole UTF-8 character and back to the start
     of a secret value the cut would split, so no part of one is kept.
   - A cut is marked `truncated` with `original_bytes` and `sha256`, both of the whole body
     before the scrub, which then runs on what is kept, and an array's `original_count`. A
     body within `max_bytes` is kept whole and unmarked, and a fixture that was not cut is
     written without the four fields.
   - Refused: a JSON object without `array_key`, since an object's parts are no list to take
     the first of; a key the object lacks, and a key whose value is no array; `array_key` or
     `keep` on a body that is not JSON, and either without `max_bytes`, the last before
     anything is sent; a body declared JSON that does not parse; an array whose first element
     alone does not fit; and a text cut that keeps nothing, since an empty sample tells a
     parser test nothing. XML is refused, since a cut-off XML document is not well-formed,
     and so are ZIP, XLSX, gzip, XLS and a body that is not UTF-8 text, since a cut-off
     binary or compressed file cannot be parsed: such a fixture is a small real sample (a
     short query, one member of the archive, a few rows).
   - A recording reads at most `max_read_bytes` of the body, an argument of `record` and
     `record_sync`, 32 MiB by default (`MAX_READ_BYTES` of `xippios.core.testing.record`),
     `None` for no bound. The body is streamed and counted as httpx decodes it, the measure
     of `original_bytes`, and once it passes the bound the reading stops, the rest is never
     fetched, and the recording raises `ValueError` naming the request's method and path
     and the bound, with nothing written; `observe` sees the refused answer's status and
     headers, its body unread. `max_bytes` cuts what the fixture keeps and is no refusal;
     this bound refuses what the recorder would read. A source that means to read more and
     cut it raises the bound.
   - The fixture keeps the response headers but the wire-encoding ones and those that only
     identify a request, `REQUEST_ID_HEADERS` of `xippios.core.testing.fixtures`:
     `x-amz-cf-id`, `x-amz-id-2`, `x-amz-request-id`, `x-amzn-requestid` and
     `x-amzn-trace-id` of AWS, `x-request-id`, X's `x-transaction-id`,
     `x-api-umbrella-request-id` of api.data.gov, `x-vcap-request-id` of Cloud Foundry,
     `x-ms-request-id` of Azure, `x-oracle-dms-ecid` of Oracle's middleware, and Cloudflare's
     `cf-ray` and `origin-cf-ray`. S3's `x-amz-version-id`, which names the version of the
     object answered, is provenance as an `ETag` is, and stays. A fixture recorded before
     keeps its headers until a PR records it again.
   - Tests assert the parser's shape on the sample, never a size. A fixture file a PR adds or
     changes stays under 256 KiB (definition of done); a fixture over the cap recorded before
     the rule bound stays until a PR re-records it. The cap reads by what a pull request does
     to a fixture file: a file the PR only moves, its content unchanged, is neither added nor
     changed, so it moves with its directory (conventions §2) and stays until a PR
     re-records it; a file moved and changed is judged by its size under its new path.
6. **The one credential rule.** It lives in `xippios.core.redaction`. A name is a credential
   when a whole word of it, between `_`, `-` or the ends, is `api_key` (also `apikey`,
   `api-key`), `token`, `secret`, `password`, `passwd`, `pwd`, `auth`, `authorization`,
   `sig`, `signature`, `credential` or `credentials`; a bare `key` is not. `sig` and `pwd`
   are on the list because catalog file links can arrive as pre-signed URLs (an Azure SAS
   carries `sig=`). A `QueryKeyAuth(param, ...)` registers `param` when it is built, and the
   name is a credential from then on in the whole process, matched exactly in any letter
   case: USDA NASS's `QueryKeyAuth("key", ...)` makes `key` one, and Eurostat, keyless, keeps
   its SDMX `key` as data; a process that imports both treats `key` as a credential for
   both. `ResultMeta.request`, the recorder's scrub, `sent_urls`, `sent_query`,
   `recorded_query` and `mount_fixture` read the one rule, so `sort_key` and `keyword` are
   data everywhere. Johannes decided the mechanism on 2026-10-27.
   - `register_data_name(name)` of `xippios.core.redaction`, a module imported by its path,
     declares a name data for the process, matched exactly in any letter case: the envelope,
     the recorder and replay keep its value, and replay can match it. Only a name that holds
     the whole word `token` and no other credential word can be declared; `token` alone and
     the token names of OAuth 2.0 and OpenID Connect, `access_token`, `refresh_token` and
     `id_token`, are refused with `ValueError`, and a name a `QueryKeyAuth` registers stays a
     credential though declared.
   - `redact_credentials`, which `ResultMeta` applies at construction, reads every text value
     at any depth that starts with `http://` or `https://`: a link whose query holds a
     credential name (an Azure SAS `sig`, an S3 `X-Amz-Signature` and `X-Amz-Credential`) or
     whose userinfo is set is written as `scrub_url` writes it, its path and its other
     parameters kept; a link that carries neither is kept byte for byte; and a link that
     httpx cannot read is `REDACTED` whole, since its credentials cannot be told from the
     rest. A task records the link it sent and scrubs nothing itself.

## Consequences

- Testing plugin: the no-network guard covers `download` (same transport); replay serves the
  truncated body (ADR-0035).
- Template: `BULK_TASKS = frozenset()` in the scaffold next to `MCP_CAPS`.
- Not decided here: XML for Eurostat (its design round); resumable downloads (none; a retry
  restarts the file).

The conventions' header, §2, §4, §6, §8, §9 and §10, the review checklist's items 1 and 4,
the definition of done's Tests block, the README and the docstrings of `download`,
`Downloaded`, `decode_text`, `decode_csv`, `ClientConfig`, `xippios.core.redaction`,
`register_tasks`, `router_from_tasks`, the family check, the fixtures, the recorder and
`Scrub` state its decisions from 1.28 on.
