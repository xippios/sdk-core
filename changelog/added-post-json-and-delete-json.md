- `AsyncClient.post_json` and `delete_json` send a write through `request`, with
  `classify`, the hooks and the retry rule for a write, and decode its JSON answer as
  `get_json` decodes a read's, `None` for an answer with no body, a 204 say. A write
  wrapper no longer calls `request` and decodes the answer itself. `get_json` still
  refuses an empty body.
  (ADR-0015, ADR-0023, §6, https://github.com/xippios/sdk-core/issues/178)
  - Hand-apply: `src/xippios/google/mail/api/drafts_create.py` (sdk-google-mail) —
    `client.request("POST", "drafts", json=...)` and `decode_json(response, ...)` (lines 48
    and 49) → `await client.post_json("drafts", json=...)`, parsed as before, and the import
    of `decode_json` (line 20) goes — core's write call replaces the request and the decode,
    its `ValidationError` naming the path the wrapper passes.
    `src/xippios/google/mail/api/messages_send.py` (sdk-google-mail) — lines 46 and 47 →
    `client.post_json("messages/send", json=body)`, and the import of `decode_json` (line
    19) goes — the same.
    `src/xippios/google/mail/api/messages_modify.py` (sdk-google-mail) — lines 51 and 52 →
    `client.post_json(f"messages/{quote(id, safe='')}/modify", json=body)`, and the import
    of `decode_json` (line 16) goes — the same.
    `src/xippios/google/mail/api/messages_trash.py` (sdk-google-mail) — lines 35 and 36 →
    `client.post_json(f"messages/{quote(id, safe='')}/trash")`, and the import of
    `decode_json` (line 13) goes — the same.
    `src/xippios/google/mail/api/drafts_delete.py` (sdk-google-mail) —
    `client.request("DELETE", ...)` (line 32) → `client.delete_json(...)`, and the
    docstring's "a success's body, empty, is not read" (line 24) → `delete_json` returns
    `None` for it — core reads the 204 that `delete_draft/ok.json` records as `None`.
    `src/xippios/cashctrl/api/_form.py` (sdk-cashctrl) — `post_form`'s `request` and its
    own decode (lines 242 to 252) → `return await client_for(org).post_json(path,
    data=fields, headers={"Content-Type": FORM_CONTENT_TYPE})`, and `BODY_LIMIT` and
    `ValidationError` leave the import (line 39) — the same, its `ValidationError` now
    carrying the decoder's reason after "is not JSON".
    `src/xippios/faostat/api/auth_login.py` (sdk-faostat) — `client.request("POST",
    LOGIN_PATH, data=..., auth=None)` and `decode_json(response, source=SOURCE,
    path=LOGIN_PATH)` (lines 47 to 50) → `client.post_json(LOGIN_PATH, data=...,
    auth=None)`, and the import of `decode_json` (line 21) goes — the same.
