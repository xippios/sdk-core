- `.github/workflows/organization.yml` runs on the opening, a push, a reopening and an edit
  of a pull request, no longer on `labeled`, and neither of its jobs has a condition of its
  own, as sdk-template renders the file for a source: GitHub reports a head's checks from
  its newest run, and a label set at the opening started a run that skipped both jobs.
  `.github/CODEOWNERS` no longer owns `/rules/**`, a path that the same render drops and
  that holds no file here. (https://github.com/xippios/sdk-template/issues/152,
  https://github.com/xippios/sdk-core/issues/231)
