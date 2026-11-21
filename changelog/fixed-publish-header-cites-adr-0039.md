- The first line of `.github/workflows/publish.yml` cites the release train's standing record,
  ADR-0039, decision 6, where it cited ADR-0018's amendment (b), which ADR-0039 supersedes. No
  step of the workflow changes. sdk-template copies the file from core, so its next adoption of
  core takes the line, and a source gets it from that template release by `copier update`.
  (ADR-0039, §12, https://github.com/xippios/sdk-core/issues/323)
