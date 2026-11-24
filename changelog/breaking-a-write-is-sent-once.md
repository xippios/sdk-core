- Core's client sends a `POST`, `PUT`, `PATCH` or `DELETE` once, after a 429 too, and
  `RetryPolicy` loses `retry_non_idempotent` and `retry_transport_errors`, so that a read alone
  is repeated and no keyword or mark asks for a repeat. The error of a write that met a 5xx or
  failed in transit says that the request was sent once and that its outcome is unknown, or that
  nothing was sent where the connection failed, while a 4xx keeps upstream's words. A client
  whose reads upstream bills takes `RetryPolicy(max_attempts=1)`, and a write task's docstring
  names the read that shows whether a failed write was applied.
  (ADR-0011, §6, https://github.com/xippios/sdk-core/issues/480)
  - Hand-apply: `src/xippios/x/_client.py` (sdk-x) — `config` takes
    `retry=RetryPolicy(max_attempts=1)`, since X bills each read, and `classify`'s docstring
    says that a 5xx is sent once where it says retried — no test breaks, since
    `tests/test_client.py::test_retries_wait_out_a_short_reset` sets a policy of its own.
    `src/xippios/cashctrl/tasks_write.py` (sdk-cashctrl) — the docstring of each write task
    names the read that shows whether a failed write was applied: `list_journal_entries` for
    `create_journal_entry`, `get_journal_entry` for `update_journal_entry` and
    `delete_journal_entry`, `list_persons` for `create_person`, `get_person` for
    `update_person` and `delete_person`, `list_orders` for `create_order`, `get_order` for
    `update_order`, `delete_order` and `update_order_status`, `list_order_book_entries` for
    `create_order_book_entry`, `update_order_book_entry` and `delete_order_book_entry`, and for
    `create_order_payment` that no read shows it but the order's status where the payment sets
    one — no test breaks, and the review holds it.
    `src/xippios/cashctrl/api/_form.py` (sdk-cashctrl) — at `:26-27`, core never repeats a
    `POST` after a 429 either — no test breaks, and the review holds the stale sentence.
    `README.md` (sdk-cashctrl) — at `:253-254`, a write is never repeated after a 429 either —
    no test breaks, and the review holds the stale sentence.
    `src/xippios/google/mail/tasks_write.py` (sdk-google-mail) — the docstring of each write
    task names the read that shows whether a failed write was applied: `list_messages` with the
    label `DRAFT` for `create_draft` and `delete_draft`, `search_messages` with `in:sent` for
    `send_message`, and `get_message`, its `label_ids`, for `modify_message` and
    `trash_message` — no test breaks, and the review holds it.
    `src/xippios/google/mail/api/<operation>.py` (sdk-google-mail: `drafts_create`,
    `drafts_delete`, `messages_send`, `messages_modify` and `messages_trash`) — the docstring's
    sentence that core never repeats the write after a 5xx or a transport failure names a 429
    too — no test breaks, and the review holds the stale sentence.
    `tests/test_refresh_reference.py` (sdk-usda-nass) — at `:306`, the assertion on
    `configured.retry.retry_transport_errors` leaves, since every policy retries a read's
    transport failure — the test fails there with `AttributeError`.
