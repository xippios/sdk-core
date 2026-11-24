- `compare_fetched` leaves `xippios.core.refresh`, and the family check's test
  `test_family_fetched_md_agrees_with_the_snapshot` leaves with its loader of the snapshot
  script: `--check` at a refresh is the one comparison of a snapshot, and each refresh writes
  `FETCHED.md` whole. A source deletes nothing at its adoption and its first refresh on this core
  writes its `FETCHED.md` whole, while the frame keeps ending the file with the mark of its form
  and the family check's own test of the row of `OBSERVED.md` stays.
  (ADR-0062, §3, https://github.com/xippios/sdk-core/issues/483)
