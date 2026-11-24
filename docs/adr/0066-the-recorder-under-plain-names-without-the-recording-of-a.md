# ADR-0066: The recorder under plain names, without the recording of a task

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/483 · Supersedes ADR-0048 · Supersedes ADR-0057

## Context

Core 0.4.1 took the frame of a source's recorder into `xippios.core.testing` (ADR-0048): the
source's rewrite step run between the scrub and the write, the check that no value it replaced
survives, the one send as a public `send_once`, and the refusal of an answer that is no final
answer of its operation. Each of the two recording functions stood twice, `record` and
`send_once` async under the plain name and `record_sync` and `send_once_sync` beside them, where
a task's sync form has the plain name. It took in `record_task` and `record_task_sync` too, with
a collector inside the client that sent every request of a recorded task once and handed each
answer over (ADR-0057), for one source, sdk-google-mail, by the maintainer's answer on
https://github.com/xippios/sdk-core/issues/364, part 3.

The design sitting of core 0.5.0 asked what core keeps of the recorder. The maintainer's answer on
https://github.com/xippios/sdk-core/issues/483 keeps one function under each plain name, the sync
one (part 1), sends the recording of a task back to its source, as the answer on
https://github.com/xippios/sdk-core/issues/473, part 4, settled, since a maintainer's decision is
no reason for one consumer any more (ADR-0059, decision 4), and gives `Scrub` the encoded forms of
a secret, which core held until 0.3.0 and which three sources carry today (part 4). The answer on
https://github.com/xippios/sdk-core/issues/475, parts 4 and 7, lets `array_key`, the cut of a
text and `mount_fixture` go, which no source passes or calls.

The two `_sync` names and the recording of a task are reversed, so this record supersedes
ADR-0048 and ADR-0057 whole. It keeps ADR-0048's numbers for decisions 1 to 7 and restates each,
the names of decision 8 and the encoded forms of decision 11 read into them; decision 8 takes the
place of the two `_sync` names, decision 9 that of ADR-0057, decisions 1 to 5, and decision 10
carries ADR-0057, decisions 6 and 7. Decisions 11 and 12 amend ADR-0042 and ADR-0040, which
carry a sentence each that points here.

## Decision

1. **Core's recorder runs the source's rewrite step.** Carried from ADR-0048, decision 1, under
   the names of decision 8. `record` and `fixture_from_response` take `rewrite=`, a function of
   the scrubbed `Fixture` that returns the fixture rewritten and the values it replaced,
   `(fixture, [value, ...])`. The order is fixed: the scrub with its verify (ADR-0042, decision
   3), the step, the check of decision 2, the write. The step raises `ValueError` to refuse, and
   a refusal writes nothing. A step that returns no pair of a `Fixture` and text values, or one
   string for its values, is refused with `TypeError`, and an empty value is passed over, since
   nothing of it can survive. `fixture_from_response` runs the refusal of decision 4, the scrub,
   the step and the check on one exchange without the write, so a source that writes several
   files, as sdk-google-mail's capture of a task does (decision 9), checks every exchange before
   it writes any. This supersedes decision 4 of ADR-0042: the writer stays core's
   (`write_fixture`, `fixture_text`), and the step it ran beside core's recorder runs inside it.
2. **No value the step replaced survives.** Carried from ADR-0048, decision 2. After the step,
   core searches the request URL, every header value the fixture keeps (the request's content
   type and each response header), both bodies as text and, where a body is JSON, every key and
   string decoded from it, for each value the step returned, as given: a plain substring in the
   letter case given, `REDACTED` masked first. A hit refuses the write with a message that names
   the place (`request URL`, `response header 'location'`, `response body`, `response body, a
   decoded JSON string`) and never the value. The values of the `Scrub` are verified again on
   the fixture the step returned, in every form of decision 11, so a step cannot bring one back.
   The search of decoded strings has three carriers, sdk-x, sdk-google-mail and sdk-cashctrl. An
   encoded form of a value the step returned stays the source's: a step returns each encoded
   form it replaced, which core then searches as given, or keeps its own search by pattern and
   raises `ValueError`. The encoded forms of a secret that the `Scrub` names or reads are core's
   by decision 11, and a tenant's host stays the source's.
3. **The one send is public.** Carried from ADR-0048, decision 3, under the name of decision 8.
   `send_once(client, path, ...)` sends one request through the source's client as `record`
   sends it: never retried, whatever its `RetryPolicy` says, never answered from the cache nor
   stored in it, its `before_request`, limiter and `observe` as for any request (ADR-0037,
   decision 6), its body read up to `max_read_bytes`. It returns the answer as it came, and
   writes nothing. `record` sends through it. A source that needs the answer itself,
   sdk-usda-wasde's samples cut from a file's bytes or sdk-cashctrl's reminder after a write,
   sends through it and builds the fixture with `fixture_from_response`, so no recorder of one
   exchange needs a client built for one attempt. The command line, the guard before the
   request and the rules stay the source's.
4. **A recording keeps a final answer only.** Carried from ADR-0048, decision 4. An answer of a
   1xx or a 3xx status is no final answer of its operation, and the recorder refuses it on every
   path. `send_once` raises once the answer is read and `observe` has seen it, so `record` writes
   nothing, and `fixture_from_response` raises before the scrub, for an answer that reached it
   another way. The message names the method, the path and the status, never a header's value,
   and says what to record instead: a request that upstream answers itself, at the URL that a
   redirect's `Location` header names. The refusal sits where the answer arrives and where a
   fixture is built, not where a file is written, so a recording of several exchanges is refused
   before it writes any. No fixture of the twelve sources records such an answer, nor does a
   test of core, so nothing recorded is lost, and a redirect can no longer be recorded on
   purpose.
5. **ADR-0042, decision 6, is superseded for the recorder.** Carried from ADR-0048, decision 5,
   but for the percent-encoded matching of a secret, which returns by decision 11. Its first
   sentence, that nothing replaces the recorder's extras, gives way to decisions 1 to 3 here for
   the frame: the step, the check by value and the one send. What a recorder rewrites and its
   checks by shape (an e-mail address, a token's form, a key's prefix) stay the source's, and so
   do `Scrub(host=...)`, `Scrub(rewrite=...)` and the host check, which left core in 0.3.0
   (ADR-0042, decision 1). The kit's return in 0.4.0, the rest of decision 6, stands.
6. **Two sentences of other records.** Carried from ADR-0048, decision 6. ADR-0037, decision 6,
   kept the one-attempt client of a recorder that sends through `client.request` to rewrite a
   fixture, "since `record` writes the file itself and ADR-0042, decision 4, gives it no hook":
   that reason fell with decision 1, and the carve-out with it, for a recording of one exchange,
   as ADR-0037's amendment of 2026-11-21 says. Its recording of an answer "whatever its status"
   reads a final answer whatever its status, by decision 4. ADR-0023, decision 3 (b), now
   superseded by ADR-0059, called "a recorder's pre-write hooks" a source's own projection
   policy: a step's rules stay the source's, and what entered core is the frame that runs them,
   with three carriers of the step and four of the one-attempt client, by the entry of two
   consumers that ADR-0059, decision 5, carries.
7. **A recorder redacts a field of a request and drops none.** Carried from ADR-0048, decision 7,
   unchanged. By the maintainer's answer on https://github.com/xippios/sdk-core/issues/439, given
   on 2026-11-22: a recorder writes `REDACTED` in place of the value of a field of a request that
   it must not keep, and drops none of them, so that the census compares a replay with its
   recording key by key, the field's recorded `REDACTED` matching any value sent. The rule speaks
   of the fields of a request, which the census compares, and of none of an answer's. Which
   fields a recorder must not keep stays the source's, as decision 5 leaves a step's rules to it:
   the rule is how its step writes them. Core's code stays as it is, and so does its census,
   which compares what it compared, with no table of fields and no declaration of a dropped one,
   as strict for every source.
8. **The plain names are the sync functions.** `record` and `send_once` are the sync functions
   that `sync` derives, as a task's sync form is, and `record_sync` and `send_once_sync` leave
   (https://github.com/xippios/sdk-core/issues/483, part 1). A caller on an event loop, an async
   script or an `anyio` test, awaits `record.async_fn` or `send_once.async_fn`, which `sync` sets
   on every function it derives, and a sync call from the thread of core's own loop is refused
   with `RuntimeError`, as for every sync facade (ADR-0002). This reverses the two `_sync` names
   of ADR-0048, decisions 1 and 3. sdk-x's script records through `record`, sdk-cashctrl's
   awaits `send_once.async_fn` in its two async sends, sdk-usda-wasde's in its one, and the
   one-off call of sdk-template's `/record-fixture` names `record`.
9. **The recording of a task goes back to its source.** `record_task`, `record_task_sync` and
   the client's collector leave core for sdk-google-mail, their one consumer
   (https://github.com/xippios/sdk-core/issues/473, part 4;
   https://github.com/xippios/sdk-core/issues/483, part 1), since a maintainer's decision is no
   reason for one consumer (ADR-0059, decision 4) and the source can do the same through what
   stays (ADR-0059, decision 2). This reverses ADR-0057, decisions 1 to 5, whole. The source
   records a task by its own capture: the task's client built for one attempt, an `observe` hook
   that keeps each answer, `fixture_from_response` with the scrub and the step for each exchange,
   `fixture_text`, and `write_fixture` once every exchange passed. Its client for one attempt is
   the one that a recorder keeps, since a task sends through `client.request` and no send of
   core records a task. The client keeps one path for a request sent once, `send_once`'s, and
   `request` sends, retries and caches as its configuration says, always: no context of the
   running task changes it, and a download is never refused for a recording.
10. **The fixtures of a task, and their replay.** Carried from ADR-0057, decisions 6 and 7,
    without the helper. The fixtures of one recording of a task stand under the task's name
    without `_async`, the first at `fixture_path(fixtures, <task>, case)` and the k-th, from the
    second on, at `<case>_<k>.json`, and a source's capture writes them so. The recorder deletes
    no fixture: §10 makes the deletion of a fixture that no test replays the PR's, named in its
    description (ADR-0039, decision 8), and a case whose own name ends in `_<k>`, such as §10's
    `CH_2026_8`, may stand beside the case `CH_2026`; the helper's refusal of a numbered file
    beyond the last exchange leaves with it. `replay_fixture` mounts one fixture per route on its
    method, host and path (§10), so a task's fixtures replay where its calls differ by path or by
    the parameters a test names with `match_params`; two exchanges on one path that no parameter
    tells apart share one route, the later answer replacing the earlier, and no replay in order
    enters core. `mount_fixture` folds into `replay(router, path, *, match_params=None,
    url=None)`, which loads the file and mounts it, since no source mounts a `Fixture` it holds
    in memory (https://github.com/xippios/sdk-core/issues/475, part 7). Records that name the
    names that leave read the names that stand, and none is amended for it: ADR-0028, decision 8
    and its closing paragraph, and ADR-0064, decisions 4 and 5, read `replay` where they name
    `mount_fixture`, and ADR-0037, decisions 4 and 6, read `record` and `send_once` where they
    name `record_sync`, the sync functions of decision 8.
11. **`Scrub` takes a secret's encoded forms.** Each value that `Scrub(secrets=...)` names or
    `Scrub(response_secrets=...)` reads is replaced and verified in its every form, not as given
    alone (https://github.com/xippios/sdk-core/issues/483, part 4): each character as given,
    percent-encoded as its UTF-8 bytes in either hex case, a space also as `+`, or behind a JSON
    escape, `\uXXXX` in either hex case (a surrogate pair for a character beyond the Basic
    Multilingual Plane), `\/`, `\"`, `\\` and the short escape of a control character, in any
    mix, the letter case given, the longest value first. The sign of a percent-encoding, `%` or
    a space's `+`, is replaced behind a JSON escape too, `\u0025` or `\u002B` in either hex
    case, as a JSON body writes a query it echoes
    (https://github.com/xippios/sdk-core/issues/581). The verify searches the URL, every header
    value and both text bodies for the same forms, and every text that each of them decodes to,
    JSON-unescaped and percent-decoded in either order, round after round until it no longer
    changes, so any nesting of the two encodings that the replacement does not offer, a hex digit
    behind a JSON escape, a percent-encoding encoded again or a JSON text stringified twice,
    refuses the recording as a value left does (https://github.com/xippios/sdk-core/pull/587). The
    decoding takes eight rounds at most, and a text that still changes after them is refused rather
    than passed. `REDACTED` is masked first, and a body stored base64 is searched for none. Core
    held the percent-encoded matching until 0.3.0 (ADR-0042, decision 1), and three sources carry
    it today: sdk-cashctrl's patterns of its key and its basic-auth token, sdk-google-mail's
    `forms_of`, and sdk-faostat's instructions, which name the encoded forms of a login at each
    recording. Their lines for a secret's forms leave at their adoption, while sdk-cashctrl's
    patterns of a tenant's host stay its own (decision 5). This amends ADR-0042, decisions 1 and 3.
12. **The cut keeps a JSON array alone.** `max_bytes=` cuts a body that is a JSON array, by whole
    elements in upstream's own text, the first ones or with `keep="last"` the last; `array_key=`
    and the cut of a text leave, since every fixture of the family over the 256 KiB cap holds a
    JSON array at its top and no script passes either
    (https://github.com/xippios/sdk-core/issues/475, parts 4 and 7). A JSON object, a text that is
    not JSON, and the formats a cut would break are refused over `max_bytes`, and the source
    records a small real answer or sample. The scrub's search for where a cut would split a
    secret leaves with the cut of a text, since an element is cut whole and then scrubbed. This
    amends ADR-0040, decision 5.

## Consequences

- `src/xippios/core/testing/record.py` loses `record_task` with its helpers and the two `_sync`
  names, the client loses its collector, its context variable and the branches of `request`,
  `_send_once` and `download` that read it, and `tests/testing/test_record_task.py` and
  `tests/client/test_collector.py`, 658 lines, leave core. `fixture_from_response` and `record`
  lose `array_key`, and the fixtures module the cut of a text, the cut of an object's array and
  the scrub's `spared_end`.
- sdk-google-mail keeps its capture of a task, about 60 lines that its port to `record_task_sync`
  would have deleted, and records its one exchange through `send_once` and `record`. Its own
  search for a secret's encoded forms leaves, since `Scrub` replaces and verifies them.
- sdk-cashctrl's two sends await `send_once.async_fn`, and its `TenantScrub` no longer looks for
  its secrets plain or percent-encoded, which `Scrub` does, while it keeps its host and its
  subdomain. sdk-x's script records through `record`, and sdk-usda-wasde's `cut_sample.py`
  awaits `send_once.async_fn`. sdk-faostat names a login's user name and password once each.
- The one-off recording of sdk-template's `/record-fixture` calls `record`, and the nine sources
  without a recorder of their own gain the guard on an encoded secret with it.
- A recording whose secret stands only percent-encoded or behind a JSON escape, which core
  wrote before, is now redacted, so a fixture recorded again can differ from the one before in
  that place alone, and one that holds it, in any place, in a nesting of the two that the
  scrub does not replace is refused.
- ADR-0028, decision 8, and ADR-0064, decisions 4 and 5, name `mount_fixture`, which no source
  imports: the check reads a call of `replay_fixture` or `replay` with `url=`, the census keeps
  what `replay` mounts, and a recording is served at another URL by `replay(url=)`. ADR-0037,
  decisions 4 and 6, name `record_sync`, which the sync `record` replaces (decision 10).

Conventions §3 and §10, the README and the docstrings of `record`, `send_once`,
`fixture_from_response`, `write_fixture`, `fixture_text`, `replay`, `Scrub` and
`xippios.core.testing` state its decisions from 0.5.0 on.
