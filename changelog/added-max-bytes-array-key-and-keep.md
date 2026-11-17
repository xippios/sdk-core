- `record`, `record_sync` and `fixture_from_response` take `array_key=`, with which
  `max_bytes=` cuts the array of a top-level key of a JSON object, `{"data": [...]}`, the rest
  of the object kept as upstream wrote it, and `keep="last"`, which keeps an array's last whole
  elements, for a list ordered oldest first. A JSON object without `array_key` is still
  refused. (ADR-0019, §10, https://github.com/xippios/sdk-core/issues/127)
