- `decode_csv` reads an open text stream beside a path and a response, such as a gzip or
  ZIP member that the source opens with the stdlib: row by row, a leading byte order mark
  stripped, and left open for the caller that opened it. Its errors name the stream's file
  name without the directories, `stream` for one without a name, and a binary stream is
  refused with `TypeError`, naming `io.TextIOWrapper`.
  (ADR-0019, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/89)
  - Hand-apply: `src/xippios/eurostat/parse/sdmx_csv.py` (sdk-eurostat) — `_gzip_records`
    (lines 102 to 105) yields from `decode_csv(text, source=SOURCE)` where it built its own
    `csv.DictReader(text)`, inside the same `_reading` and `_text(path, packed=True)`,
    which stay for `_header` and the gzip errors. The module docstring's sentence that
    the gzip file is read with the stdlib's `csv.DictReader` "since `decode_csv` takes a
    path or a response, not an open stream" (lines 23 to 30) says that both files' rows
    are read through `decode_csv`, a gzip file's as a stream — core reads the stream, and
    `tests/test_parse.py`'s `test_parse_sdmx_csv_refuses_text_that_is_not_utf8` (line
    300) and `test_parse_sdmx_csv_refuses_csv_the_csv_module_cannot_read` (line 317) pass
    unchanged, since core names a `gzip.open` stream by its file's name.
    `src/xippios/faostat/parse/bulk_csv.py` (sdk-faostat) — `parse_bulk_csv` (lines 124
    to 150) reads the table's rows through `decode_csv(io.TextIOWrapper(raw,
    encoding="utf-8-sig", newline=""), source=SOURCE)`, and its header for the check of a
    column named twice apart, from a first `archive.open(member)`, as sdk-eurostat's
    `_header` reads its own, since `decode_csv` gives rows as mappings, in which a column
    named twice is one key. `_reading` keeps its ZIP branch, and the module docstring's
    "`decode_csv` takes a path or a response, not an open stream" (lines 26 to 34) goes —
    core reads the stream. The errors of the rows' reading then name the member alone,
    not `<member> in <zip>`: `tests/test_parse.py`'s
    `test_parse_bulk_csv_refuses_text_that_is_not_utf8` (line 278) expects
    `f"faostat: {table_name(RL)} is not UTF-8 text: invalid start byte"`, and
    `test_parse_bulk_csv_refuses_csv_the_csv_module_cannot_read` (line 290)
    `f"faostat: {table_name(RL)} is not CSV the csv module reads: ..."`.
