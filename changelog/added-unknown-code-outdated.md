- `UnknownCode(..., outdated=False)` leaves out the sentence that the packaged list is out of
  date, for a value that is no code of upstream's at all, which no refresh would make one. The
  check of a packaged list refuses every value of its hint table so, such as an ISO alpha-3 code
  where upstream takes integers, and keeps the sentence on every other refusal.
  (ADR-0041, ADR-0045, §5, https://github.com/xippios/sdk-core/issues/430,
  https://github.com/xippios/sdk-core/issues/440)
