- The response cache stores an answer only once `get_answer` has decoded it and, with
  `parse=`, parsed it, so a 200 whose body fails is requested again on the next call
  instead of answering from the cache until its entry expires. `get`, `get_json`,
  `request` and `record` still read the cache and store nothing.
  (ADR-0015, §6, https://github.com/xippios/sdk-core/issues/122)
