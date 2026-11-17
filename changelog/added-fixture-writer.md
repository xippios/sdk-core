- `xippios.core.testing` exports `write_fixture(fixture, path)`, which writes a `Fixture` laid
  out as `record` writes it, and `fixture_text(fixture)`, which gives that text, so a recorder
  step that rewrites a fixture writes it as core does. `write_fixture` took a response before
  and was no export: `write_fixture(fixture_from_response(response), path)` does what it did.
  (ADR-0024, §10, https://github.com/xippios/sdk-core/issues/125)
  - Hand-apply: `scripts/record_fixture.py` (sdk-cashctrl, sdk-google-mail, sdk-x) — `to_json`
    and `_CUT_MARKS` → `fixture_text`, the file's write → `write_fixture` — core's writer.
    `scripts/cut_sample.py` (sdk-usda-wasde) — the JSON dump and its write →
    `write_fixture` — core's writer.
