- `Scrub` takes `response_secrets`, a function of the response that returns values that
  must never be written, such as the tokens of a login or a refresh answer, which the
  credential rule does not name (`AccessToken` is one word). Each value is scrubbed and
  verified as the named ones are, so such an exchange records through `record_sync`.
  (ADR-0024, §10, https://github.com/xippios/sdk-core/issues/164)
  - Hand-apply: `scripts/record_fixture.py` (sdk-google-mail) —
    `Scrub(secrets=[*secret_values(), *answer_tokens(response)])` at lines 1058 to 1061
    and 1089 to 1091 → `Scrub(secrets=secret_values(), response_secrets=answer_tokens)`,
    `rewrite` keeping its list for the encoded forms — core reads and verifies the
    answer's tokens.
