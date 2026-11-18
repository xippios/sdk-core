- A cache miss through `get_answer` carries the time its entry was stored, one reading of
  the clock for both, taken when the answer arrived and before the decode and the parse,
  so a later hit and the miss that stored it report one `retrieved_at` and a test
  asserts them equal.
  (ADR-0015, §4, https://github.com/xippios/sdk-core/issues/79)
