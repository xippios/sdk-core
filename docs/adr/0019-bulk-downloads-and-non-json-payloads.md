# ADR-0019: Bulk downloads and non-JSON payloads in core

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview; the family review of 2026-10-25, C15; decision 5's two format rules from the
briefings review of the same day)

## Context

Core's client decodes JSON (`decode_json`), stores every answer in the response cache
without a size bound, replays fixtures that hold one JSON exchange, and the adapters
register every task in `tasks.py`. That fits the released sources. The next five do not:
ESMIS (a JSON catalog whose payload is file links; PDF, TXT, ZIP, XLS), WASDE (XLS
tables, a CSV to verify, through ESMIS), NASS bulk datasets (gzipped TSV of hundreds of
MB with Quick Stats' columns), Eurostat (JSON-stat 2.0 cubes and SDMX-CSV; datasets of
tens of MB; the SDMX series parameter `key` would be redacted as a credential, ADR-0005,
review C10), FAOSTAT (JSON plus bulk ZIP/CSV; authentication and paging unverified).

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
   `original_bytes` and the sha256 of the full file. An XML or ZIP fixture is a small
   real sample (a short query, one file of the archive), never a byte-truncated file. A
   JSON array is truncated by elements: the recorder keeps the first N, marks it
   `truncated: true` and records the full count and the sha256. Tests assert the
   parser's shape on the sample, never a size. A fixture file stays under 256 KiB
   (definition of done).
6. **C10.** The credential redaction in `ResultMeta.request` and in the recorder's scrub
   spares a parameter named `key` when the client's auth is not a query key
   (`api_key_location != query`); Eurostat's SDMX `key` is data.

## Consequences

- Core 0.3.0, about +250 lines (review C15), with C10. ESR and GATS are unaffected.
- Conventions: §6 gains download, decode and the cache bound; §8 and §9 the
  `BULK_TASKS` rule; §10 the fixture rule; §2 says bulk tasks live in `tasks.py` and are
  marked. The definition of done gains the fixture size and the `truncated` marker.
- Testing plugin: the no-network guard covers `download` (same transport); replay
  serves the truncated body.
- Template: `BULK_TASKS = frozenset()` in the scaffold next to `MCP_CAPS`; the file
  fixture rule in `record-fixture.md` (template cleanup, tagged with core 0.3.0).
- Not decided here: XML for Eurostat (its design round); resumable downloads (none; a
  retry restarts the file).
