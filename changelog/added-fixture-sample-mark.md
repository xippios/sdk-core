- `FixtureResponse.sample` marks a download's replay fixture whose body is the sample its
  parser tests read, with the whole file's `original_bytes` and `sha256`, so the download
  replays that file and `truncated` keeps meaning the recorder's cut. `FixtureResponse`,
  `write_fixture` and `load_fixture` refuse a fixture with both marks, with either and without
  those two fields, or with them on a whole body. (ADR-0020, §10,
  https://github.com/xippios/sdk-core/issues/125)
  - Hand-apply: `scripts/cut_sample.py` (sdk-usda-wasde) — the replay fixture's `truncated` →
    `sample`, and the download fixtures written again — a sample is no first part of
    upstream's answer.
