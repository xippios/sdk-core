# ADR-0016: Per-tool result caps

Status: Accepted · Date: 2026-10-24

## Context

Conventions §8 caps every MCP tool result at 200 rows or 64 KB (65,536 bytes),
whichever comes first, and over the cap returns the first page plus a note on how to
narrow the query. `register_tasks` and `build_server` took one `cap` for every tool of
a server.

The same section makes reference lookups tools, `<source>_list_<thing>`, because agents
need them to form valid calls. sdk-comtrade's are larger than the cap:
`comtrade_list_reporters` has 255 rows and `comtrade_list_partners` 310, and
`comtrade_list_commodities` returns a whole classification, 8,262 codes and about 2 MB
for `HS`. The cap cut the first two at 200 rows in upstream's alphabetical order, before
Switzerland and the USA, and showed only the top of a classification tree. sdk-comtrade
worked around it in its own package: its three list tasks took a `search` filter, and
their docstrings told agents to search. sdk-usda-psd's `usda_psd_list_countries` stops
at 200 of its 251 countries, before the United States, and its README tells agents to
filter by region or search.

More rows alone would not have made comtrade's two lists whole. From its packaged
tables (fetched 2026-10-23), the result of the 255 reporters is 69,011 bytes of compact
JSON and that of the 310 partners 83,270 bytes, both over the byte cap: with their row
caps raised and the byte cap at the default, the tools would show about 242 and 244
rows.

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
   its `tasks.py`. A tool with an entry uses that cap in place of `cap`, a field the
   entry leaves unset taking the family default, not `cap`'s; every other tool uses
   `cap`, 200 rows or 64 KB by default. A key that names none of the tasks being
   registered is refused with `ValueError` naming it, before anything is registered: a
   misspelt key would otherwise leave the tool on the default cap without a word.
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
4. **A per-tool cap sets rows and bytes.** A cap in `caps` sets `max_rows` and
   `max_bytes` as the source judges the tool needs. A byte bound above the default 64 KB
   is a deliberate choice for one tool, a reference list an agent needs whole, made in
   that tool's entry; every tool without one keeps the family default, 200 rows or
   64 KB. No tool goes uncapped: every result stays bounded, and every cut carries the
   note. Bytes are those of the compact JSON text encoded as UTF-8, which the convention
   always said; until this ADR core counted characters, so a non-ASCII result now keeps
   fewer rows than before. `max_bytes` is a soft bound: it bounds the rows and the
   preview, and the envelope and the note can add to it. A list keeps the most rows
   whose whole text fits; when not even zero rows fit, a tiny bound with a long note, it
   returns zero rows plus the note. A non-list result over the bound returns a preview
   of `max_bytes` bytes, which JSON escaping lengthens, plus the note. Results stay
   bounded and are never truncated silently (§8).
5. **Caps live with the tasks.** A source keeps its per-tool caps in an
   `MCP_CAPS: Mapping[str, ResultCap]` mapping in its `tasks.py`, next to `__all__`: a
   cap's note names the task's filters, so the mapping belongs with the tasks it
   describes. Its `mcp.py` passes it through,
   `build_server(..., caps=getattr(tasks, "MCP_CAPS", None))`, and holds no cap of its
   own. Core's API is unchanged by this: `register_tasks` and `build_server` take any
   mapping.

## Consequences

- The known adopters:
  - sdk-comtrade caps `list_reporters` and `list_partners` at
    `ResultCap(max_rows=400, max_bytes=100_000)`, so both lists, 69,011 and 83,270
    bytes, reach an agent whole; it may drop their `search` filters or keep them as a
    convenience.
  - sdk-usda-psd caps `list_countries` at `ResultCap(max_rows=300)`, so its 251
    countries reach an agent whole, the United States included; the packaged file is
    31,883 bytes, under the default byte cap.
  - The HS commodity list, about 2 MB, is not served whole: comtrade's
    `list_commodities` keeps `search` and a cap of its own whose note names it.
- A tool that has filters sets a note naming them; one without keeps the default.
- sdk-template's `mcp.py` renders `caps=getattr(tasks, "MCP_CAPS", None)` in its
  `build_server` call, in a template PR after the core release that carries this ADR; a
  source without a large list defines no `MCP_CAPS` and keeps the default for every
  tool.
- **Behaviour change**, pre-1.0 (conventions §12): the default note's wording changes.
  A test that asserts the old text ("more filters or a shorter date range") fails; none
  is known in the family. A result with non-ASCII text keeps fewer rows under the same
  `max_bytes`, since each such character now counts its two to four UTF-8 bytes.
- The review of ADR-0015's change found three edges of the testing plugin's quota
  guarantee, documented with this change: consecutive live tests share every policy's
  snapshot; a quota a fixture of wider scope spends while it is set up is forgotten in
  the setup of the first test not marked `live` from then on; and a subclass's override
  of `before_request` is not called through the hook `install` sets and is not
  neutralised by the plugin. ADR-0013's edges and ADR-0015's consequences state them.
- Conventions 1.11: §8 states the default cap and that its bytes are the UTF-8 bytes of
  the compact JSON text, the per-tool cap, rows and bytes, for a reference tool whose
  whole list an agent needs, where a source keeps its caps (`MCP_CAPS` in `tasks.py`),
  and that the note never promises a filter the tool lacks; §10 points to the edges of
  the quota guarantee.

Amended by ADR-0015's amendment of 2026-10-27 (core 0.3.0): the third edge no longer holds
as written. `install` sets `before_request` itself as the hook, so a subclass's override
is called through it; the testing plugin still turns off the pause step alone, not a wait
or refusal of the override's own.
