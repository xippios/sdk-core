- The 27 decision records have an index, `docs/adr.md` for people and `docs/adr.json` for
  machines, which `scripts/adr_index.py` writes from the records' headers. With `--check` it
  writes nothing and exits 1 when either file is stale, a record's first line does not read
  `# ADR-NNNN: <title>` or two records take one number. Each header reads
  `Status: <status> · Date: <date>`, then its other fields, and `docs/reports/` holds the dated
  reports a record cites.
  (https://github.com/xippios/sdk-core/issues/193)
