- Conventions 1.26: the documents say what a change must satisfy wherever a repository is
  worked and no longer how it lands, so §13, §15, the definition of done and the review
  checklist drop the merge classes, the auto-merge of an adoption or release PR, the
  branch names and the rule that a PR's description is the checklist. A change's entry is
  a fragment under `changelog/`, which a release PR assembles and deletes as one of the
  files §12 lets it change, and a repository without the folder keeps a line under
  `## [Unreleased]`. §2 names an existing source's rename PR without ambiguity, §10 lets a
  fixture over the cap move with its directory, §12 has a dependent that bundles its
  adoption with feature work say so in its release's section of `CHANGELOG.md`, §13 names
  `xippios/.github` as the organization's repository whose reusable workflows are called
  at `@main`, and the hand-over and the roadmap lose their stale sentences. (ADR-0018, §2,
  §10, §12, §13, §15, https://github.com/xippios/sdk-core/issues/203,
  https://github.com/xippios/sdk-core/issues/207)
