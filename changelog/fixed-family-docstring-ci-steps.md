- The docstring of `xippios.core.testing.family` describes the two CI steps of a source as
  sdk-template 0.3.3 renders them: every pull request but Dependabot's brings an entry, a
  fragment under `changelog/` or a change of `CHANGELOG.md`, and no branch name exempts a
  release or an adoption. A fixture that a pull request only moves is neither added nor
  changed under the cap, as ADR-0019's amendment of 2026-11-13 reads it.
  (ADR-0019, §12, https://github.com/xippios/sdk-core/issues/209)
