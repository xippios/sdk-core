- Conventions §5 hold a publisher's shared package to name the request of its gateway's three
  messages about an answer, the refusal of a key, the answer to a spent rate limit and the answer
  for an unknown route, with `request_description`, as a source's `classify` does. §12 states
  that sdk-template's own `CHANGELOG.md` names the tag whose file holds its older sections, and
  that the remedy of the release race holds where a release has a `pypi` stage.
  (ADR-0030, ADR-0043, ADR-0065, ADR-0068, ADR-0069, §5, §12,
  https://github.com/xippios/sdk-core/issues/597)
  - Hand-apply: `src/xippios/usda/fas/data_gov.py` (sdk-usda-fas) — the gateway's refusal of a
    key, its answer to a spent rate limit and its answer for an unknown route name their request
    with `request_description`, as the package's commit `f3f02fa` already does, and the adoption
    checks that they still do and that `tests/test_data_gov.py` asserts those words — §5 binds a
    shared package's messages about an answer (ADR-0065, decision 3).
