- `UnknownCode(..., no_code=True)` refuses a value that is no code of upstream's at all without
  the sentence that the packaged list is out of date, since no refresh would make it a code.
  The check of a packaged list refuses a value of its hint table so, such as an ISO alpha-3
  code where upstream takes integers, and keeps the sentence on every other refusal.
  (ADR-0045, §5, https://github.com/xippios/sdk-core/issues/430)
