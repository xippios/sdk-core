- The recorder drops the response headers that only identify a request, such as
  `x-amz-cf-id`, `x-request-id` and `x-transaction-id`
  (`xippios.core.testing.fixtures.REQUEST_ID_HEADERS`), so a new recording brings no audited
  entry of the secret scan for them. `ETag` and `x-amz-version-id` stay.
  (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/161)
