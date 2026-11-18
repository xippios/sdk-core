- The secret scan of `.pre-commit-config.yaml` skips the line on which the fixture recorder
  writes a cut or sampled body's sha256, so a fixture that holds one needs no audited entry
  in `.secrets.baseline`. Every other line is still scanned, a body stored base64 included,
  which keeps its audited entry. Its comment says that `.copier-answers.yml` can name a
  key's variable, which a keyless source's does not.
  (ADR-0019, https://github.com/xippios/sdk-template/issues/42,
  https://github.com/xippios/sdk-core/issues/210)
