- `scripts/count_surface.py` counts core's surface in two parts, the run-time part and the
  workbench (`testing/` and `refresh/`), in names and in lines. Given the trees of consumers as
  `name=<path>`, it reports who consumes each pinned name and each keyword-only parameter, by
  kind of code, and every import from core outside the pinned lists. It is a report: it fails
  nothing, and nothing leaves core by its count alone.
  (https://github.com/xippios/sdk-core/issues/485)
