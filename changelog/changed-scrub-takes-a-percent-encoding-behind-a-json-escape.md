- `Scrub` replaces a secret's percent-encoding whose sign stands behind a JSON escape too, `%`
  as `\u0025` or a space's `+` as `\u002B`, as a JSON body writes a query it echoes. Its verify
  searches every text that the URL, a header value or a body decodes to as well, JSON-unescaped
  and percent-decoded in either order until it no longer changes, so any nesting of the two
  encodings that the scrub does not replace refuses the recording before anything is written,
  the error naming where, and so does a text that still decodes after eight rounds.
  (ADR-0066, §10, https://github.com/xippios/sdk-core/issues/581)
  - Hand-apply: `scripts/record_fixture.py` (sdk-cashctrl, sdk-google-mail) — a search of a JSON
    body's decoded strings, or of a text percent-decoded, for a named secret's forms may leave
    with the test that holds it — core's verify searches every place decoded to the end and
    refuses what it finds.
