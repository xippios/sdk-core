- Core's pytest plugin sets the placeholder key in the secret variables of the one package with
  a `_client.py` under the repository's own `src/xippios/`, so a publisher's shared package that
  holds a key and no `tasks.py`, sdk-usda-fas the first, declares its variables in
  `_client.ENV_VARS` as a source does. A package with a `tasks.py` and no `_client.py` sets no
  variable and raises no error, and no ini option comes back.
  (ADR-0035, §10, https://github.com/xippios/sdk-core/issues/538)
