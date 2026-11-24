- The built-answer check follows no body to where it is served and reads no declaration of
  its collecting module: a kind of §10 or the input's sentence marks any place, and `READERS`
  and `ALLOWED` leave with the test of a stale entry. A source collects the check by its line
  alone, a body handed to its own function is no place, and a helper that serves a recording
  where and as it was recorded builds its answer with `response_from_fixture`.
  (ADR-0064, §10, https://github.com/xippios/sdk-core/issues/483)
  - Hand-apply: `tests/test_built_answers.py` (sdk-cashctrl) — its own check gives way to the
    collecting line alone, without the `READERS = frozenset({"merge_custom"})` and the entry of
    `ALLOWED` for `serve_by_start` that the note of 0.4.1 carried over — core reads neither, so
    the five bodies that its tests hand to `merge_custom` are no places, and no test breaks by
    the two declarations left out.
    `tests/test_tasks.py` (sdk-cashctrl) — `serve_by_start` (lines 685 to 697 on its `main`)
    answers each request with `response_from_fixture` of the page's recording, loaded by
    `load_fixture`, in place of `answer_with` on the page's decoded body, and
    `test_the_count_kept_is_the_last_pages_and_never_corrected` (line 835), which changes a
    page in memory under its mark of kind 4, serves its pages through `answer_with` as the test
    above it does — no entry of `ALLOWED` covers the helper any more, so until it changes the
    check fails on its two unmarked calls, in
    `test_list_journal_entries_without_limit_collects_every_page` (line 772) and
    `test_start_without_limit_collects_every_page_from_start` (line 790).
    `tests/test_built_answers.py` (each source whose render of sdk-template 0.4.1 wrote it, none
    on its `main` of 2026-11-24) — the two empty declarations `READERS` and `ALLOWED` and the
    comment above them leave — core reads neither, and no test breaks.
