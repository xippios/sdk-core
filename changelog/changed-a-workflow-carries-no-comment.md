- A workflow carries no comment but the version after a pinned action, as conventions §13 now
  states, and §13 no longer asks for a comment on the checkout of the release train's `tag`
  job. Core's `ci.yml` and `publish.yml` lose their comments, and the README says of each of
  the four workflows what it checks, when it runs, what it is handed and what switches it.
  (ADR-0039, §13, https://github.com/xippios/sdk-core/issues/494)
