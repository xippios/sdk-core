- A new record states how a release run that fails is finished, the four rules of §12 as they
  stand: the failed jobs re-run after the tag and before it, no `concurrency` group in
  `publish.yml`, and a rejected deployment at `pypi` where two runs found the version untagged.
  §12 cites it in place of ADR-0039, decision 6, which states none of them, and says that when a
  release PR merges is the process of the work, while the snapshot frame's docstrings cite
  ADR-0062 in place of the superseded ADR-0046 for the attribution check.
  (ADR-0069, ADR-0039, ADR-0062, §12, https://github.com/xippios/sdk-core/issues/559)
