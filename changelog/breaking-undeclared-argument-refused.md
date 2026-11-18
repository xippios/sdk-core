- A tool refuses an argument that it does not declare before it runs, whatever its value,
  and names the ones it declares, where the argument was dropped and the tool ran with its
  default:
  `error: InvalidRequestError: yaer: Not an argument of this tool; it takes series_id, year`.
  So a call that still names a tenant on a server that a lock binds is refused, where it
  ran for the bound tenant.
  (ADR-0014, §8, https://github.com/xippios/sdk-core/issues/84)
  - Hand-apply: `tests/test_org_lock.py` (sdk-cashctrl) —
    `test_a_call_that_still_passes_org_is_answered_for_the_bound_org` (line 175) → the
    call is refused with
    `error: InvalidRequestError: org: Not an argument of this tool; it takes note`
    and the tool does not run, and
    `test_the_bound_read_server_reaches_the_bound_organisation_only` (line 216) → calls
    `cashctrl_list_currencies` with `{}`, its `{"org": "xa"}` refused — core refuses an
    argument that no tool of a bound server declares.
    `CLAUDE.md` (sdk-cashctrl) — the sentence that a call that still passes `org` is not
    refused, observed under core 0.3.0 → core's argument check refuses it, naming the
    tool's arguments — as above.
    `tests/test_account_lock.py` (sdk-google-mail) —
    `test_a_call_that_still_passes_account_is_answered_for_the_bound_account` (line 185)
    → refused with
    `error: InvalidRequestError: account: Not an argument of this tool; it takes note`,
    and `test_the_bound_read_server_answers_for_the_bound_account_only` (line 221) →
    calls `google_mail_get_profile` with `{}`, its `{"account": "xa"}` refused — as above.
