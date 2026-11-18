# ADR-0038: Per-tool result caps

Status: Accepted · Date: 2026-11-18 · Decided by the record it supersedes, restated under
https://github.com/xippios/coordinate-core/issues/757 · Supersedes ADR-0016

## Context

Conventions §8 caps every MCP tool result at 200 rows or 64 KB (65,536 bytes), whichever
comes first, and over the cap returns the first page plus a note on how to narrow the query.
One cap for every tool of a server cut reference lists that agents need whole, and its note
sent an agent looking for filters the tool did not have. An exemption for every tool named
`<source>_list_*` was rejected: a name should not become behaviour. This record states
ADR-0016 with ADR-0015's amendment of 2026-10-27 and its amendments of 2026-10-27, 2026-10-30
and 2026-11-18 as they stand, and changes no decision; their history stays in ADR-0016.

## Decision

1. **A cap per tool, keyed by the task function's name.**
   `register_tasks(..., caps: Mapping[str, ResultCap] | None = None)`, and
   `build_server(..., caps=None)`, which passes it through. A key is the task function's
   `__name__` (`list_partners`; a sync facade's, with `_async` stripped), not the tool name
   with the source prefix (`comtrade_list_partners`): the name the source writes in its
   `tasks.py`. A tool with an entry uses that cap in place of `cap`, a field the entry leaves
   unset taking the family default, not `cap`'s; every other tool uses `cap`, 200 rows or
   64 KB by default. A key that names none of the tasks being registered is refused with
   `ValueError` naming it, before anything is registered.
2. **A cap carries its note.** `ResultCap(note: str | None = None)`: when set, the text after
   the counts, used verbatim, in the note of a cut list and in the note of a non-list result
   over the byte cap. A tool with filters names them in its own cap, e.g.
   `ResultCap(max_rows=..., note="filter by period or by reporter to see the rest")`. A
   blank note is refused with `ValueError`.
3. **The default note promises nothing, and says where to resume.** A cut list reads
   "showing {shown} of {total} rows (cap: {max_rows} rows or {max_bytes} bytes); narrow the
   query to see the rest", a non-list result over the byte cap "result is {n} bytes, over
   the cap of {max_bytes}; narrow the query to see the rest". Neither names a filter or a
   date range the tool may lack. The note of a cut list ends `; resume with start=<start +
   shown>` where the result's `meta.request` records an integer `start`, an offset-paged
   task's, after the default text or the cap's own `note`; every other note, the byte-cap
   note included, is unchanged. When the first row alone passes the byte bound, the cut
   shows no row, and its note says after the counts `the first row alone exceeds the byte
   cap`, or `the row at offset <start> alone exceeds the byte cap` where `meta.request`
   records an integer `start`, then the cap's own note or the default, and names no resume
   offset. Where not even zero rows with that note fit, a tiny bound or a long note, the
   note gives the counts and the cap's own note alone, again with no resume offset. A source
   names the tool that reads one long row in its cap's note, as sdk-google-mail's
   `get_thread` names `google_mail_get_message`.
4. **A per-tool cap sets rows and bytes.** A cap in `caps` sets `max_rows` and `max_bytes` as
   the source judges the tool needs. A byte bound above the default 64 KB is a deliberate
   choice for one tool, made in that tool's entry, in three cases:
   - a reference list an agent needs whole;
   - a tool whose result is one upstream page that must return whole, a cursor-paged page
     with its `next_token` or a bounded lookup, with a byte bound of its own and the row
     bound unchanged, as sdk-x's four post tools take 128,000 bytes and its `lookup_users`
     160,000 (Johannes, 2026-10-30); where the upstream bills per result, the tool's
     docstring states the price per result (ADR-0027, decision 4), so a larger page is a
     known cost;
   - a tool whose result is one upstream document or table that an agent reads whole, a
     report or a statement, a table's page or a matrix, with the rows and bytes the source
     judges it needs and a note that says how to read a part of it, as sdk-cashctrl's
     `get_report_data` takes 131,072 bytes and sdk-usda-wasde's `get_table` and
     `get_balance_sheet` 400 and 300 rows, each 131,072 bytes (Johannes, 2026-10-28).

   Every other tool keeps the family default, 200 rows or 64 KB. No tool goes uncapped: every
   result stays bounded, and every cut carries the note. Bytes are those of the compact JSON
   text encoded as UTF-8. `max_bytes` is a soft bound: it bounds the rows and the preview,
   and the envelope and the note can add to it. A list keeps the most rows whose whole text
   fits; when not even zero rows fit, it returns zero rows plus the note. A result whose
   `data` is a model that holds one list of rows, and no other field a list (a field left
   `None` is none), is cut by those rows once its text passes the byte bound, as a list
   result's rows are, to the row and the byte bound, with decision 3's note and its resume
   offset, and the model's other fields stay whole beside them; within the byte bound such a
   model returns whole, however many rows it holds. Any other result over the bound, a model
   with no list or with two and one whose other fields alone pass the byte bound among them,
   returns a preview of `max_bytes` bytes, which JSON escaping lengthens, plus the note. A
   page that must return whole still takes a byte bound of its own, since a cut keeps its
   `next_token`, which points past the rows the cut left out. Results stay bounded and are
   never truncated silently (§8).
5. **Caps live with the tasks.** A source keeps its per-tool caps in an
   `MCP_CAPS: Mapping[str, ResultCap]` mapping in its `tasks.py`, next to `__all__`: a cap's
   note names the task's filters, so the mapping belongs with the tasks it describes. Its
   `mcp.py` passes it through, `build_server(..., caps=getattr(tasks, "MCP_CAPS", None))`,
   and holds no cap of its own. `register_tasks` and `build_server` take any mapping.

## Consequences

- A tool that has filters sets a note naming them; one without keeps the default.
- sdk-template's `mcp.py` renders `caps=getattr(tasks, "MCP_CAPS", None)` in its
  `build_server` call; a source without a large list defines no `MCP_CAPS` and keeps the
  default for every tool.
- A result with non-ASCII text keeps fewer rows under the same `max_bytes`, since each such
  character counts its two to four UTF-8 bytes.
- The edges of the testing plugin's quota guarantee stand in ADR-0035's consequences and
  ADR-0037's.

Conventions §8, the README and the docstrings of `xippios.core.mcp.server` and `ResultCap`
state its decisions from 1.28 on.
