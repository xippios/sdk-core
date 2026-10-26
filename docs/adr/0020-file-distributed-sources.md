# ADR-0020: File-distributed sources

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview)

## Context

ADR-0001's three layers assume an upstream that answers HTTP requests with records.
Three USDA sources distribute files. ESMIS publishes every USDA report series as release
files (PDF, TXT, ZIP, XLS) behind a JSON catalog, since 2025-10-01 at
esmis.nal.usda.gov (moved there from Cornell's Mann Library). WASDE is one of those
series, its tables in XLS and XML. NASS offers the Quick Stats database as gzipped TSV
files. Eurostat and FAOSTAT ship bulk files beside their APIs. Nothing says what layer 1
is for a file, which formats are in scope, where a parser's dependency lives, or whether
a PDF is ever read.

## Decision

1. **Three layers stay.** Layer 1 of a file-distributed source has two parts. `api/`
   wraps the HTTP endpoints the source has (ESMIS's catalog); the download itself goes
   through core's `download` (ADR-0019) or through the retrieval package the source
   depends on (ADR-0021). `parse/` holds one module per file kind
   (`parse/wasde_xls.py`, `parse/qs_crops.py`) with one function per file kind,
   `parse_<file_kind>(path) -> list[Model]`. Layer 2 composes fetch and parse into
   tasks; layer 3 is unchanged and skips bulk tasks (ADR-0019).
2. **Fidelity applies to files** (ADR-0003). Models mirror the file: field names are
   the column headers snake_cased; sheet and table names stay on the record as upstream
   prints them; units and footnote markers stay as text. Nothing is renamed, converted
   or joined across files. `docs/upstream/` snapshots the file-format documentation
   (layout notes, a dataset's README) the way it snapshots API documentation.
3. **Formats.** CSV/TSV, XML (`xml.etree.ElementTree`), gzip and zip through the
   standard library; XLS/XLSX, or a hardened XML library the source prefers, through a
   library the source declares itself: a plain dependency when its tasks cannot work
   without it, an extra (`xippios-usda-wasde[xls]`) when only some can. Core keeps its
   footprint (httpx, pydantic; ADR-0002) and never ships a spreadsheet, XML or PDF
   parser.
4. **PDF: narrative only.** A source may extract the text of a PDF release (the
   report's narrative, for an agent to read under the cap) with a library it declares
   (`pypdf`). It never reads numbers from a PDF: a figure a task returns comes from the
   XLS, XML, CSV or TXT the release carries, or is not returned. A reconstructed table
   is not upstream fidelity; a release that carries only a PDF yields text.
5. **Envelope.** `meta.endpoint` names the file kind as upstream names it (`wasde.xls`,
   `qs.crops`); `meta.vintage` the release identifier (ESMIS release id, the report
   date as printed); `meta.published_at` the catalog's release time (ADR-0022);
   `meta.request` the file's URL or release id and the filters applied in Python.
6. **Fixtures and live tests.** A sample of each file kind (a small real file, or one
   truncated as ADR-0019 decision 5 allows) lives under
   `tests/fixtures/files/<file_kind>/<case>.*` with a provenance line (release id, URL,
   sha256 and bytes of the full file, fetched time with `Z`); parser tests run on it.
   The two formats serve two reads: the recorded exchange of a download
   (ADR-0019 decision 5, the recorder's envelope with `truncated`) is what the plugin
   replays for the download call; the sample file under
   `tests/fixtures/files/<file_kind>/` is what the parser tests read, a small real or
   truncated file, and since a binary file carries no comment, the samples' provenance
   lives as one row per file in `tests/fixtures/files/README.md`. One live test per file
   kind fetches the current release and checks the parser still reads it: shape, headers
   and sheet names, never values.

## Consequences

- ESMIS is the family's retrieval point for USDA report files: a catalog-and-download
  package with no parsers of its own. WASDE is the first parser package and depends on
  it (ADR-0021). NASS bulk datasets join `sdk-usda-nass` (0.3.0) as `parse/` modules and
  bulk tasks beside the Quick Stats wrappers.
- Conventions §2 gains the `parse/` layer and the PDF rule; §3 the file snapshot; §10
  the file fixture and the live-parser test. Template: a `parse/` directory and the
  fixtures path when a source answers `has_files` (template cleanup).
- A file kind changing its layout upstream breaks the live test first and the parser
  second; the fix is a parser change with a CHANGELOG line, as for an endpoint change.
