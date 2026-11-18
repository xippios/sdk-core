# ADR-0020: File-distributed sources

Status: Accepted · Date: 2026-10-26 · Decided by Johannes on 2026-10-26 (architect
interview) · Amended 2026-11-18 by https://github.com/xippios/sdk-core/issues/240

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

## Amendment 2026-11-18

Core 0.4.0, the package of https://github.com/xippios/sdk-core/issues/240, whose steps
each add their points here.

(a) **A download's replay fixture may carry the sample as its body** (step 10;
https://github.com/xippios/sdk-core/issues/125, found by sdk-usda-wasde; decided by
Johannes on 2026-11-17, https://github.com/xippios/sdk-core/issues/236). Decision 6 keeps
the recorded exchange of a download, which the plugin replays for the download call, apart
from the sample under `tests/fixtures/files/<file_kind>/` that the parser tests read. The
exchange may now carry that sample as its body, so that the download replays the file the
parser tests read. Such a body is marked `sample: true`, a field of its own, with the
whole file's `original_bytes` and `sha256`, and never `truncated`, which keeps meaning the
recorder's cut of ADR-0019, decision 5. `FixtureResponse`, `write_fixture` and
`load_fixture` refuse a fixture with both marks, one with either and without those two
fields, and one whose whole body carries them or `original_count`. The source replaces
the body on the `Fixture` that `fixture_from_response` returns and writes it with
`write_fixture` (ADR-0024's amendment of this date). The sample under
`tests/fixtures/files/` stays, with its provenance row. sdk-usda-wasde's download fixtures
carry its XML and XLS samples so, marked `truncated` until its adoption of core 0.4.0.

(b) **A bulk parser may yield its records** (decision 1; step 14;
https://github.com/xippios/sdk-core/issues/90, found by sdk-eurostat). Decision 1 types
every parser `parse_<file_kind>(path) -> list[Model]`. sdk-eurostat's `parse_sdmx_csv`
reads SDMX-CSV files of hundreds of MB and sdk-faostat's `parse_bulk_csv` the normalized
table of a bulk ZIP of up to 400 MB; a list would hold the whole file in memory, which
ADR-0019 keeps a bulk download from doing, so both are generators. A parser of a bulk file
kind, a file that a bulk task downloads (ADR-0019, decision 4), may therefore return
`Iterator[Model]`, as both write it a generator: it reads the file as the records are
taken, in the file's order, closes it when it ends or is closed, and its docstring says
so. Every other parser returns `list[Model]` as before. Conventions §2 states it from 1.28
on.

(c) **A file task's `meta.endpoint` names the file** (decision 5; step 15;
https://github.com/xippios/sdk-core/issues/135, found by sdk-usda-wasde; decided by
Johannes on 2026-11-17, https://github.com/xippios/sdk-core/issues/244). Decision 5 names
the file kind (`wasde.xls`, `qs.crops`). The three released sources that read files name
the file itself: sdk-usda-esmis's `download_release_file` the name ESMIS catalogs
(`wasde1026.txt`), sdk-usda-wasde's file tasks and the lists it packages from a release's
XML the same name (`wasde1026.xml`, a revision's `wasde0626v2.xml`), and sdk-faostat's
`download_dataset` the table its bulk ZIP holds, `All_Data_(Normalized).csv`. A task that
reads a file sets `meta.endpoint` to the file's name as upstream names it, which may
change with each release and carry a revision's suffix, and a list packaged from a
released file names that file the same way as its `endpoint` (ADR-0022, decision 1). A
narrative read from a PDF that prints a date but no month label keeps the ESMIS release
id as `vintage`, which decision 5 allows, as sdk-usda-wasde's `read_report_text` does. A
download of an operation's answer is no file upstream names and keeps the operation's
name, as sdk-eurostat's SDMX `dataQuery`, streamed to a file, does. The case of a file
read from an origin or mirror that the publisher runs is open under
https://github.com/xippios/sdk-core/issues/276. No source changes. Conventions §4 states
it from 1.28 on.
