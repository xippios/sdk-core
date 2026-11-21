- Where a source keeps `docs/upstream/OBSERVED.md`, the family check holds it to three rules
  and fails at once: `FETCHED.md` lists the file in a row of its own at any width, every note
  ends with a paragraph that opens with `Probe: <date>` or `Observed: <date>`, and every file
  that a code span of the file cites from the repository's root exists. A source without the
  file passes all three. sdk-eurostat fails the row until its patch writes it.
  (ADR-0044, §3, https://github.com/xippios/sdk-core/issues/348)
  - Hand-apply: `tests/test_observed.py` (sdk-usda-esmis) — delete
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own` and
    `test_every_note_ends_with_its_probe_and_its_date`, and keep
    `test_every_recording_a_note_cites_is_a_fixture`, whose bare fixture names the family
    check does not read — the family check holds the row and the probe's label and date.
    `tests/test_observed.py` (sdk-usda-wasde) — delete
    `test_fetched_md_lists_observed_md_in_a_row_of_its_own` and the label and date of
    `test_every_note_ends_with_what_it_was_observed_in_and_its_date`, and keep its cited file
    in each note, `test_every_file_a_note_was_observed_in_exists` for the release files and
    the paths under `docs/upstream/`, `test_the_layouts_name_the_release_files_they_were_written_from`
    and `test_the_notes_are_observed_md_and_no_layout_md_remains` — the family check holds the
    row, the label and the date.
    `tests/test_observed.py` (sdk-usda-esr) — delete `test_every_file_the_notes_cite_exists`,
    the row of `test_fetched_md_lists_observed_md_in_a_row_of_its_own` and the label and date
    of `test_every_note_ends_with_its_probe`, and keep the sentence of `FETCHED.md`, each
    probe's operation, recording or request and the dates of its recordings, the pointers of
    `test_the_rules_point_to_the_notes` and `test_no_probe_stands_outside_the_notes` — the
    family check holds the row, the label and date and the cited files.
    `tests/test_observed.py` (sdk-cashctrl) — delete `test_every_file_the_notes_cite_exists`,
    the row of `test_fetched_md_lists_observed_md_in_a_row_of_its_own` and the label and date
    of `test_every_note_ends_with_its_probe`, and keep the sentence of `FETCHED.md` and the row
    as its last line, the count of 20 notes, each probe's operation, recording or answer not
    kept and the dates of its recordings, the documented operations, the pointers and
    `test_the_package_keeps_no_probe` — the family check holds the row, the label and date and
    the cited files.
    `tests/test_refresh_upstream.py` (sdk-faostat) — delete
    `test_every_file_a_note_cites_exists` and the label and date of
    `test_every_note_ends_with_its_probe_its_date_and_its_operation`, and keep its count of 12
    notes and each probe's operation or request — the family check holds the label and date and
    the cited files.
    `docs/upstream/FETCHED.md` (sdk-eurostat) — the row of `OBSERVED.md`, which
    `scripts/refresh_upstream.py` writes at its next run —
    `test_family_fetched_md_lists_observed_md_in_a_row_of_its_own` fails without it.
