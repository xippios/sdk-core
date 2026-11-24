- `assert_write_tools` holds every write task's preview in each call: its `Result`'s data has
  one member tagged `performed: Literal[False]`, which declares `reads: list[str]`, and
  `preview_reads=`, which no source passed, leaves. Its second check of
  `confirm: bool = False` leaves too, since the write tool set makes it when it is built, and
  `confirm` stays checked as a write task's last parameter.
  (ADR-0050, §8, https://github.com/xippios/sdk-core/issues/475)
  - Hand-apply: `src/xippios/cashctrl/models.py` (sdk-cashctrl) — `WritePreview` (line 2268
    on its `main`) declares `reads: list[str]`, the operations its preview read, and `_preview`
    of `src/xippios/cashctrl/tasks_write.py` (lines 186 to 200) sets it from the read it made,
    `[]` where it read nothing — until it does, `test_the_write_server_serves_write_tasks_only`
    of `tests/test_tasks_write.py` (line 163) fails, naming each write tool's preview.
    `src/xippios/google/mail/models.py` (sdk-google-mail) — `ComposePreview` (line 395) and
    `ActionPreview` (line 426) declare `reads: list[str]`, and the four previews that
    `src/xippios/google/mail/tasks_write.py` builds (lines 188, 275, 398 and 436) set it, a
    reply's `["gmail.users.messages.get"]` and every other `[]` — until they do,
    `test_the_write_server_serves_the_write_tasks_only` of `tests/test_tasks_write.py` (line
    161) fails, naming each write tool's preview.
