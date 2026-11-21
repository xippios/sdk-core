- `assert_write_tools` holds what a write task's preview shows, in two parts, each off by
  default: `preview_reads=True` fails a write task unless its `Result` has exactly one member
  tagged `performed: Literal[False]`, the preview, that declares `reads: list[str]`, and
  `dry_run=` with `sent=`, the `respx` router, calls each write tool without `confirm` and
  fails a preview that sent a request other than a read, or whose `reads` is not empty exactly
  when it sent none. A read is a `GET`, `HEAD` or `OPTIONS` request unless `is_read=` says
  otherwise. Conventions §8 state that a preview sends no write, that whether it reads first
  is the tool's, said in its docstring with the read's cost, and that it carries `reads`.
  (ADR-0050, §8, https://github.com/xippios/sdk-core/issues/182, https://github.com/xippios/sdk-core/issues/369)
  - Hand-apply: `src/xippios/cashctrl/models.py` (sdk-cashctrl) — `WritePreview` declares
    `reads: list[str]` — the field that `preview_reads=True` holds.
    `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — `_preview` sets `reads`, the
    `read.json` it read for the eight updates and deletes that read and `[]` for the six that
    do not, and each of the fourteen docstrings says whether its preview reads and what that
    costs — the rule of §8.
    `tests/test_tasks_write.py` (sdk-cashctrl) — `test_the_write_server_serves_write_tasks_only`
    passes `preview_reads=True` in the patch that declares the field, and the dry run with the
    eight reads served at the source's choice — it fails while `WritePreview` lacks `reads`.
    `src/xippios/google/mail/models.py` (sdk-google-mail) — `ComposePreview` and
    `ActionPreview` declare `reads: list[str]` — the field that `preview_reads=True` holds.
    `src/xippios/google/mail/tasks_write.py` (sdk-google-mail) — each preview sets `reads`,
    `["gmail.users.messages.get"]` for a reply's and `[]` for the rest, and each of the five
    docstrings says whether its preview reads and what that costs — the rule of §8.
    `tests/test_tasks_write.py` (sdk-google-mail) —
    `test_the_write_server_serves_the_write_tasks_only` passes `preview_reads=True` in the
    patch that declares the field, and the dry run at the source's choice, with an `is_read`
    that takes the token request a reply's read sends first — it fails while the two previews
    lack `reads`.
