- The secret scan of `.pre-commit-config.yaml` skips the two lines that the fixture recorder
  writes high in entropy, a body stored base64 and the whole body's sha256, so a fixture
  that holds them needs no audited entry in `.secrets.baseline`. A text body, a header and
  every other line are still scanned. Its comment says that `.copier-answers.yml` can name a
  key's variable, which a keyless source's does not.
  (ADR-0019, https://github.com/xippios/sdk-template/issues/42,
  https://github.com/xippios/sdk-core/issues/210)
