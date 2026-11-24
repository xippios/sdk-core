- A host that applies a tool set's option hooks itself finds in core's text that what a hook
  sets is the process's, as a `Ceiling`'s value is, so every endpoint that a host serves from one
  process holds the same values. A `XippiosError` that `apply_options` raises reaches the host,
  which catches it itself and stops as `main` does, with exit status 2, and `option_defaults()`
  holds no tenant's `--<param>`, which `main` adds where it is given `tenants`. ADR-0063,
  decision 4, the README and the docstrings of `Ceiling` and `ToolSet` say so, and the code does
  not change. (ADR-0063, ADR-0054, https://github.com/xippios/sdk-core/issues/571)
