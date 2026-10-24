# ADR-0016: Per-tool result caps

Status: Accepted · Date: 2026-10-24

## Context

Conventions §8 caps every MCP tool result at 200 rows or 64 KB, whichever comes first,
and over the cap returns the first page plus a note on how to narrow the query.
`register_tasks` and `build_server` took one `cap` for every tool of a server.

The same section makes reference lookups tools, `<source>_list_<thing>`, because agents
need them to form valid calls. sdk-comtrade's are larger than the cap:
`comtrade_list_reporters` has 255 rows and `comtrade_list_partners` 310, and
`comtrade_list_commodities` returns a whole classification, 8,262 codes and about 2 MB
for `HS`. The cap cut the first two at 200 rows in upstream's alphabetical order, before
Switzerland and the USA, and showed only the top of a classification tree. sdk-comtrade
worked around it in its own package: its three list tasks took a `search` filter, and
their docstrings told agents to search.

The note said "narrow the query, for example with more filters or a shorter date range,
to see the rest". A reference list has neither a filter nor a date range unless its
source adds one, so the note sent an agent looking for parameters the tool did not
have.

An exemption for every tool named `<source>_list_*` was considered and rejected: a name
should not become behaviour. A list tool can be far too large to return whole (a
commodity classification), and a tool that needs more rows need not be named `list_*`.

## Decision

1. **A cap per tool, keyed by the task function's name.**
   `register_tasks(..., caps: Mapping[str, ResultCap] | None = None)`, and
   `build_server(..., caps=None)`, which passes it through. A key is the task function's
   `__name__` (`list_partners`; a sync facade's, with `_async` stripped), not the tool
   name with the source prefix (`comtrade_list_partners`): the name the source writes in
   its `tasks.py`. A tool with an entry uses that cap in place of `cap`; every other
   tool uses `cap`, 200 rows or 64 KB by default. A key that names none of the tasks
   being registered is refused with `ValueError` naming it, before anything is
   registered: a misspelt key would otherwise leave the tool on the default cap without
   a word.
2. **A cap carries its note.** `ResultCap(note: str | None = None)`: when set, the text
   after the counts, used verbatim, in the note of a cut list and in the note of a
   non-list result over the byte cap. A tool with filters names them in its own cap,
   e.g. `ResultCap(max_rows=..., note="filter by period or by reporter to see the
   rest")`. A blank note is refused with `ValueError`.
3. **The default note promises nothing.** A cut list reads "showing {shown} of {total}
   rows (cap: {max_rows} rows or {max_bytes} bytes); narrow the query to see the rest",
   a non-list result over the byte cap "result is {n} bytes, over the cap of
   {max_bytes}; narrow the query to see the rest". Neither names a filter or a date
   range the tool may lack.
4. **Rows per tool, bytes global.** A per-tool cap raises `max_rows`. The 64 KB byte cap
   stays the family's bound on what one tool result puts into an agent's context, for
   every tool: `ResultCap` keeps its `max_bytes` field, and a source may set it, but
   conventions §8 and the `caps` docstring say to leave it at the default. There is no
   byte-cap exemption.

## Consequences

- sdk-comtrade sets caps for its list tasks, `caps={"list_reporters": ResultCap(...),
  "list_partners": ResultCap(...)}` with `max_rows` at least the list's length, and may
  drop its `search` filters or keep them as a convenience. The byte cap still applies:
  computed from its packaged tables (fetched 2026-10-23), the compact JSON of the 255
  reporters is about 69 KB and of the 310 partners about 83 KB, so under the default
  byte cap the tools show about 242 and 244 rows, with the note. A classification of 8,262 codes stays
  far over the byte cap whatever its row cap; `list_commodities` keeps `search`, and a
  cap of its own whose note names it.
- A tool that has filters sets a note naming them; one without keeps the default.
- sdk-template's `mcp.py` passes `caps=` to `build_server` where a source has large
  reference lists, in a template PR after the core release that carries this ADR.
- **Behaviour change**, pre-1.0 (conventions §12): the default note's wording changes.
  A test that asserts the old text ("more filters or a shorter date range") fails; none
  is known in the family.
- Conventions 1.11: §8 states the default cap, the per-tool row cap for a reference tool
  whose whole list an agent needs, and that the note never promises a filter the tool
  lacks.
