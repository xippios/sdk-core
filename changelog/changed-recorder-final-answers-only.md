- The recorder refuses an answer of a 1xx or a 3xx status, which is no final answer of its
  operation, on every path: `send_once`, `record` and `fixture_from_response` raise before
  anything is written, the message naming the method, the path, the status and what to record
  instead. A final answer is still kept whatever its status, a 4xx or a 5xx included, and no
  fixture of the twelve sources holds a 1xx or a 3xx.
  (ADR-0048, §10, https://github.com/xippios/sdk-core/issues/364)
