- Conventions §2 lets a task compose another task of its own `tasks.py`, awaiting its
  `_async` function, so the request, its refusals and the meta live once, and §4 has the
  composing task build its meta through the `ResultMeta` constructor, never `model_copy`.
  A parser of a bulk file kind may return `Iterator[Model]`, a generator that reads the
  file as the records are taken, where every other parser returns `list[Model]`.
  (ADR-0001, ADR-0020, §2, §4, https://github.com/xippios/sdk-core/issues/70,
  https://github.com/xippios/sdk-core/issues/90)
