- A pull request runs the organization's checks from `xippios/.github`:
  `.github/workflows/organization.yml` calls the conventions review as the job
  `conventions` and the ADR-index check as the job `adr-index`, and `gates.yml`, which
  called the two workflows of the retired gates, is deleted. `mypy --strict` reads
  `scripts/` beside `src` and `tests`. (§11, §13,
  https://github.com/xippios/sdk-core/issues/191,
  https://github.com/xippios/sdk-core/issues/206)
