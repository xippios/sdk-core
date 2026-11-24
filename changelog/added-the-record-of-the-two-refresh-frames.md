- One new record of the two refresh frames supersedes ADR-0046 and ADR-0051: one declaration
  for each frame under one `run`, one header of the provenance table, the snapshot fetched
  through core's client, what a source's hooks carry, and no check of a committed `FETCHED.md`
  without a request. Conventions §3 and the review checklist's item 2 cite it for the snapshot
  script's form, the mark of the form and the one comparison, and each change of 0.5.0 that
  builds the rest of it cites it where it words a sentence anew.
  (ADR-0062, ADR-0046, ADR-0051, §3, https://github.com/xippios/sdk-core/issues/482,
  https://github.com/xippios/sdk-core/issues/483, https://github.com/xippios/sdk-core/issues/485)
