# ADR-0048: Core's recorder frame around a source's rewrite step

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/364 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/439

## Context

ADR-0042 left a source's rewriting to the source's own recorder: decision 4 gave it core's writer
and no hook, and decision 6 put nothing in place of the recorder's extras that left core in 0.3.0.
Three sources now rewrite a fixture before its one write, sdk-x by key in a JSON body,
sdk-google-mail a message's content and its secrets' encoded forms, sdk-cashctrl a tenant's host
and its key's encoded forms, and each copies the same frame around its own rules: a client built
for one attempt with `RetryPolicy(max_attempts=1)`, the send through `client.request(...,
raise_on_error=False)`, the step on the `Fixture` that `fixture_from_response` returns, a check that
nothing it replaced survives, and the write. sdk-usda-wasde's `scripts/cut_sample.py` builds the
same client to download the file it cuts its samples from, and sdk-cashctrl prints a reminder from
a write's answer, so two of the four need the answer itself. ADR-0037, decision 6, keeps those
clients, since `record` writes the file itself and ADR-0042, decision 4, gives it no hook
(https://github.com/xippios/sdk-core/issues/281).

What a recorder does with an answer that is no final answer of its operation differs as well:
sdk-x writes it, sdk-cashctrl refuses a 1xx or 3xx on its five file paths since
https://github.com/xippios/sdk-cashctrl/pull/116 and writes one on its other paths, sdk-usda-wasde
refuses every status but 200, and core records an answer whatever its status. Compared part by
part (https://github.com/xippios/sdk-core/issues/322), the four scripts differ in their command
line, their guard and their rules, and do alike the send, the order of the steps, the check by
value and the write.

The trial of the release (https://github.com/xippios/sdk-core/issues/410) met one step that drops
a field of a request it must not keep: sdk-google-mail's leaves `raw`, the whole message, out of
a recorded write's body. Core's census compares a replay's JSON body with its recording key by
key, through the recording's redaction (ADR-0049, decision 5), so it named four tests that
replay their own recordings as answering another body
(https://github.com/xippios/sdk-google-mail/issues/72). No record of core said what a step does
with such a field: ADR-0017 keeps a value out of a fixture, and decision 1 has the step return
the values it replaced. Decision 7, the amendment of 2026-11-22, is the maintainer's answer on
https://github.com/xippios/sdk-core/issues/439.

## Decision

1. **Core's recorder runs the source's rewrite step.** `record`, `record_sync` and
   `fixture_from_response` take `rewrite=`, a function of the scrubbed `Fixture` that returns the
   fixture rewritten and the values it replaced, `(fixture, [value, ...])`. The order is fixed:
   the scrub with its verify (ADR-0042, decision 3), the step, the check of decision 2, the write.
   The step raises `ValueError` to refuse, and a refusal writes nothing. A step that returns no
   pair of a `Fixture` and text values, or one string for its values, is refused with `TypeError`,
   and an empty value is passed over, since nothing of it can survive. `fixture_from_response`
   runs the refusal of decision 4, the scrub, the step and the check on one exchange without the
   write, so a source that writes several files checks every exchange before it writes any
   (sdk-google-mail's recording of a task, and the recording of every exchange of a task,
   https://github.com/xippios/sdk-core/issues/174). This supersedes decision 4 of ADR-0042: the
   writer stays core's (`write_fixture`, `fixture_text`), and the step it ran beside core's
   recorder runs inside it.
2. **No value the step replaced survives.** After the step, core searches the request URL, every
   header value the fixture keeps (the request's content type and each response header), both
   bodies as text and, where a body is JSON, every key and string decoded from it, for each value
   the step returned, as given: a plain substring in the letter case given, `REDACTED` masked
   first, as the verify of ADR-0042, decision 3, searches for a secret. A hit refuses the write
   with a message that names the place (`request URL`, `response header 'location'`, `response
   body`, `response body, a decoded JSON string`) and never the value. The values of the `Scrub`
   are verified again on the fixture the step returned, so a step cannot bring one back. The
   search of decoded strings has three carriers, sdk-x, sdk-google-mail and sdk-cashctrl, and
   enters core by ADR-0023, decision 2. A percent-encoded form stays out: the two recorders that
   look for one, sdk-google-mail and sdk-cashctrl, look for the encoded forms of their secrets and
   of a tenant's host, which they replace beside core's scrub, each in a shape of its own, and
   sdk-x, the one recorder that returns the values it replaced, looks for none, so no two
   consumers carry it for a step's values. It stays the source's: a step returns each encoded
   form it replaced, which core then searches as given, or keeps its own search by pattern and
   raises `ValueError`.
3. **The one send is public.** `send_once(client, path, ...)` and `send_once_sync` send one request
   through the source's client as `record` sends it: never retried, whatever its `RetryPolicy`
   says, never answered from the cache nor stored in it, its `before_request`, limiter and
   `observe` as for any request (ADR-0037, decision 6), its body read up to `max_read_bytes`. They
   return the answer as it came, and write nothing. `record` sends through it. A source that needs
   the answer itself, sdk-usda-wasde's samples cut from a file's bytes or sdk-cashctrl's reminder
   after a write, sends through it and builds the fixture with `fixture_from_response`, so no
   recorder needs a client built for one attempt. The command line, the guard before the request
   and the rules stay the source's.
4. **A recording keeps a final answer only.** An answer of a 1xx or a 3xx status is no final
   answer of its operation, and the recorder refuses it on every path. `send_once` raises once the
   answer is read and `observe` has seen it, so `record` writes nothing, and `fixture_from_response`
   raises before the scrub, for an answer that reached it another way. The message names the
   method, the path and the status, never a header's value, and says what to record instead: a
   request that upstream answers itself, at the URL that a redirect's `Location` header names.
   The refusal sits where the answer arrives and where a fixture is built, not where a file is
   written, so a recording of several exchanges is refused before it writes any. No fixture of the
   twelve sources records such an answer, nor does a test of core, so nothing recorded is lost,
   and a redirect can no longer be recorded on purpose.
5. **ADR-0042, decision 6, is superseded for the recorder.** Its first sentence, that nothing
   replaces the recorder's extras, gives way to decisions 1 to 3 here for the frame: the step, the
   check by value and the one send. What a recorder rewrites and its checks by shape (an e-mail
   address, a token's form, a key's prefix) stay the source's, and so do `Scrub(host=...)`,
   `Scrub(rewrite=...)`, the percent-encoded matching and the host check, which left core in 0.3.0
   (ADR-0042, decision 1). The kit's return in 0.4.0, the rest of decision 6, stands.
6. **Two sentences of other records.** ADR-0037, decision 6, keeps the one-attempt client of a
   recorder that sends through `client.request` to rewrite a fixture, "since `record` writes the
   file itself and ADR-0042, decision 4, gives it no hook": that reason falls with decision 1, and
   the carve-out with it. Its recording of an answer "whatever its status" reads from this record
   a final answer whatever its status, by decision 4. ADR-0037 carries an amendment that says so.
   ADR-0023, decision 3 (b), calls "a recorder's pre-write hooks" a source's own projection
   policy, which one consumer does not bring into core: it stands as written. A step's rules stay
   the source's, and what enters core is the frame that runs them, by decision 2 of ADR-0023, with
   three carriers of the step and four of the one-attempt client, not by 3 (b).
7. **A recorder redacts a field of a request and drops none.** By the maintainer's answer on
   https://github.com/xippios/sdk-core/issues/439, given on 2026-11-22: a recorder writes
   `REDACTED` in place of the value of a field of a request that it must not keep, and drops
   none of them, so that the census compares a replay with its recording key by key, the field's
   recorded `REDACTED` matching any value sent. The rule speaks of the fields of a request, which
   the census compares, and of none of an answer's. Which fields a recorder must not keep stays
   the source's, as decision 5 leaves a step's rules to it: the rule is how its step writes them.
   Core's code stays as it is, and so does its census, which compares what it compared, with no
   table of fields and no declaration of a dropped one, as strict for every source.

## Consequences

- Each of the four sources deletes, in its patch, its client built for one attempt and its copy of
  the frame. The changelog's Hand-apply note names, per source, what its recorder deletes and what
  it keeps.
- sdk-cashctrl's refusal of a 1xx or 3xx on its five file paths becomes core's on every path, and
  its refusal of another 2xx and of a binary file at those paths stays its own. sdk-x and
  sdk-google-mail no longer write a 1xx or 3xx.
- sdk-x masks its placeholders before its check, and core masks `REDACTED` alone: a replaced value
  found only inside a placeholder the step wrote (`rewritten` inside `[name rewritten]`) refuses
  the write in core where sdk-x writes it today. A word of a placeholder that is also a key of
  the body (`text`, `name`) is refused by both, since sdk-x searches the keys too. Such a
  recording is narrowed, or the step leaves the value out of what it returns.
- A recording that ends in a redirect names the redirect's status, and the source records the
  request that upstream answers itself.
- By decision 7, sdk-google-mail's step writes `REDACTED` for `raw` in a write's request body,
  where it dropped the key, and the source records `send_message/ok.json` and
  `create_draft/ok.json` again with it, in a pull request before its adoption: a keyed write on
  its demo mailbox, which needs the maintainer's go and a budget. Of the other two sources with a
  recorder of their own, read on their `main` of 2026-11-21, sdk-cashctrl's step redacts and
  drops nothing, and sdk-x's rewrites answers alone.

Conventions §3 and §10, the README and the docstrings of `record`, `send_once`,
`fixture_from_response`, `write_fixture`, `fixture_text`, `Scrub` and `xippios.core.testing` state
its decisions from 1.29 on.
