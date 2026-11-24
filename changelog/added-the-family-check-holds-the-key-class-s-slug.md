- The family check fails a source whose key class names another slug than the package's
  own: a `KeyAuth` that `_client.py` holds by a name, the `auth` of its `AsyncClient`, or the
  `auth` of a gateway that a publisher's shared package builds with the slug it is given. A
  source's envelopes then read its key's name as a credential, since the registries are kept
  for each source, and every source's key class names its own slug on its `main` today.
  (ADR-0040, §10, https://github.com/xippios/sdk-core/issues/526)
