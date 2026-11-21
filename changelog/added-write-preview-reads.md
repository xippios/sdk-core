- `assert_write_tools` holds what a write task's preview shows, in two parts, each off by
  default: `preview_reads=True` fails a write task unless its `Result` has exactly one member
  tagged `performed: Literal[False]`, the preview, that declares `reads: list[str]`, and
  `dry_run=` with `sent=`, the `respx` router, calls each write tool without `confirm` and
  fails a preview that sent a request other than a read, or whose `reads` is not empty exactly
  when it sent none. A read is a `GET`, `HEAD` or `OPTIONS` request unless `is_read=` says
  otherwise. Conventions §8 state that a preview sends no write, that whether it reads first
  is the tool's, said in its docstring with the read's cost, and that it carries `reads`.
  (ADR-0050, §8, https://github.com/xippios/sdk-core/issues/182, https://github.com/xippios/sdk-core/issues/369)
  - Hand-apply: `src/xippios/cashctrl/models.py` (sdk-cashctrl) — the package's own
    `WritePreview` declares `reads: list[str]`, the operations its preview read, and it and
    `WriteResult` stay the package's, since core provides no preview model — the field that
    `preview_reads=True` holds.
    `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — `_preview` sets `reads` from the
    read it made. The eight previews that read their record once with `GET`, the updates and
    deletes of journal entries, persons, orders and order book entries, name its `read.json`,
    such as `["journal/read.json"]`. The six that send no request, the four creates,
    `update_order_status` and `create_order_payment`, set `[]`. Each of the fourteen
    docstrings says whether its preview reads and what the read costs, the eight that their
    preview reads the record once with its `read.json`, one request, and the six that their
    preview sends no request — the rule of §8, which leaves whether a preview reads to the
    source.
    `tests/test_tasks_write.py` (sdk-cashctrl) — `test_the_write_server_serves_write_tasks_only`
    passes `preview_reads=True`, and `dry_run=` with `sent=respx_mock` at the source's choice,
    the eight reads served by their routes and no `is_read`, since it reads with `GET` and
    writes with `POST` — it fails while `WritePreview` lacks `reads`.
    `src/xippios/google/mail/models.py` (sdk-google-mail) — the package's own
    `ComposePreview` and `ActionPreview` declare `reads: list[str]` and stay the package's,
    since core provides no preview model — the field that `preview_reads=True` holds.
    `src/xippios/google/mail/tasks_write.py` (sdk-google-mail) — each of the five previews
    sets `reads` to the operations it read. As the code reads on 2026-11-21, that is
    `["gmail.users.messages.get"]` for the preview of a reply by `create_draft` or
    `send_message` and `[]` for the others, since the previews of `delete_draft`,
    `modify_message` and `trash_message` are built from the arguments alone and send no
    request. Each of the five docstrings says whether its preview reads and what the read
    costs, the two that compose that a reply's preview reads the original once, 20 quota
    units, and the other three that their preview reads nothing — the rule of §8, which
    leaves whether a preview reads to the source.
    `tests/test_tasks_write.py` (sdk-google-mail) —
    `test_the_write_server_serves_the_write_tasks_only` passes `preview_reads=True`, and
    `dry_run=` with `sent=respx_mock` at the source's choice, with an `is_read` that takes the
    token request, a `POST`, that a reply's read sends first — it fails while the two previews
    lack `reads`.
