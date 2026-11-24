- `Scrub` replaces a secret's percent-encoding whose sign stands behind a JSON escape too, `%`
  as `\u0025` or a space's `+` as `\u002B`, as a JSON body writes a query it echoes. Its verify
  searches each key and string of a body that is JSON as well, decoded and then percent-decoded,
  so a nesting of the two encodings that the scrub does not replace, a percent-encoding encoded
  again say, refuses the recording before anything is written, the error naming where.
  (ADR-0066, §10, https://github.com/xippios/sdk-core/issues/581)
  - Hand-apply: `scripts/record_fixture.py` (sdk-cashctrl, sdk-google-mail) — a search of a JSON
    body's decoded strings for a named secret's forms, kept for a percent-encoding behind a JSON
    escape, may leave with the test that holds it — core's verify searches those strings,
    decoded and percent-decoded, and refuses what it finds.
