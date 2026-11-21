- `docs/adr.md` opens each record's line with its anchor, so a link to `docs/adr.md#0014` lands
  on ADR-0014, and lists the records in force first and the superseded ones after them.
  `docs/adr.json` keeps its order. `scripts/adr_index.py` is the version the organization's
  repositories share, byte for byte, and runs as `python3 -I scripts/adr_index.py`.
  (https://github.com/xippios/sdk-core/issues/350)
