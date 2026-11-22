- sdk-core's pull requests start the organization's checks from one trigger file each,
  `conventions.yml` and `adr-index.yml`, in place of `organization.yml`, and keep their checks
  `conventions / conventions` and `adr-index / adr-index`, while a push to `main` or a
  dispatch starts the review of a range. A variable `WORKFLOW_CONVENTIONS` or
  `WORKFLOW_ADR_INDEX` of `off` switches a check off, and CI and the release train take no
  switch. The release train's workflow is titled `Publish`, which sdk-template copies into
  every source with the rest of `publish.yml`.
  (§13, https://github.com/xippios/sdk-core/issues/407)
