- Conventions §4 settles four cases of a release's time and `vintage`. The naive flag also
  marks a time whose printed zone upstream's own calendar and files contradict, kept with
  its offset dropped, and a release identifier that is a day or a month stays in `vintage`
  with `published_at` empty. A frozen feed whose answers carry their own releases keeps
  each answer's release in `vintage`, and a parameter that takes back a vintage keeps what
  is strictly later, keeps the whole answer's meta and refuses a value with a zone.
  (ADR-0022, §4, https://github.com/xippios/sdk-core/issues/53,
  https://github.com/xippios/sdk-core/issues/108,
  https://github.com/xippios/sdk-core/issues/119,
  https://github.com/xippios/sdk-core/issues/158)
