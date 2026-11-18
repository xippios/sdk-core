- A sync task whose coroutine raises `SystemExit` or `KeyboardInterrupt`, or awaits a task
  that does, hands it to its caller, and the background loop serves the next call, where
  the loop's thread ended and that call and every later one waited for ever. So a script
  may exit from inside a sync task with its status. `sync` of a callable without a
  `__name__`, a `functools.partial` say, raises a `TypeError` that names
  `functools.update_wrapper`, where it raised an `AttributeError`.
  (ADR-0002, https://github.com/xippios/sdk-core/issues/77)
  - Hand-apply: `scripts/refresh_reference.py` (sdk-usda-esmis) — the docstring of
    `Refused` (lines 58 to 63) drops its reason, that a `SystemExit` raised in the
    coroutine stops the loop's thread and leaves the caller waiting for ever. `Refused`
    may stay as the walk's refusal that `main` turns into its exit — core hands a
    `SystemExit` back to the caller.
