# ADR-0064: The built-answer check: its mark and its census, without following a body or the module's declarations

Status: Accepted · Date: 2026-11-24 · Decided by https://github.com/xippios/sdk-core/issues/483 · Supersedes ADR-0049

## Context

Core 0.4.1 took the check of a built answer's mark into `xippios.core.testing.built_answers`
(ADR-0049), read as sdk-cashctrl's own check read: a reader of the test modules by `ast`, the
source's own readers in `READERS` and its exceptions in `ALLOWED` beside the collecting line,
and a census of the replays in the same run. ADR-0049, decision 10, its amendment of
2026-11-22 (https://github.com/xippios/sdk-core/issues/439), followed an exchange that a helper
of the module builds to where it is served or handed to the recorder, and read a module's
imports to tell the frame's `Response` from httpx's, so that an input that no route serves could
take the input's sentence while a served answer took a kind.

The design sitting of core 0.5.0 asked what core keeps of the check. The maintainer's answer on
https://github.com/xippios/sdk-core/issues/483, part 2, keeps the mark and the census and lets
the rest go. The following cost 295 lines of the package and about 410 lines of tests, and with
it gone no test of a source fails: the check no longer tells a served answer that is marked as
an input, which it told in 39 places of five of the six sources ported onto core's `main`. The
two declarations cost about 60 lines, 84 lines of tests and 8 of the 9 lines that sdk-template
renders into every source, and one source fills them, sdk-cashctrl, with one reader and one
entry, where the template renders them empty for every other. By ADR-0059, decisions 2 and 6, a piece with one
consumer leaves where that consumer can do the same through what stays, by a closed question
that names it, and this record is the record of its mechanism.

ADR-0049's decisions 7, 8 and 10 are reversed, so this record supersedes it whole. It keeps
ADR-0049's numbers for decisions 1 to 6, restates each decision that it carries, and names
what it reverses: its decision 7 takes the place of ADR-0049's decisions 7 and 8, its decision
8 carries ADR-0049's decision 9, and its decision 9 that of ADR-0049's decision 10.

## Decision

1. **The mark.** Carried from ADR-0049, decision 1. A mark names `§10` and a kind, `kind 1` to
   `kind 5` in §10's order, anywhere in one docstring or one block of comments, usually as
   `NOT RECORDED: <where the body comes from> (conventions §10, kind 2)`. It is the phrase that
   sdk-cashctrl's tests carry, so a reviewer reads the same words as the check.
2. **Its reach.** Carried from ADR-0049, decision 2. A mark reaches the places of the function or
   class whose docstring holds it, of the statement that it stands on or above, and of every
   call of a helper whose docstring holds it. A place inside a helper that no mark covers is
   judged at each call of the helper, and a test that takes a fixture holding one is the place.
   A module's docstring reaches nothing, so that a test added to a module states its own kind.
3. **The input's sentence.** Carried from ADR-0049, decision 3. A value that no route serves as
   an answer and no `classify` reads, handed to the code under test, is an input of the test
   (ADR-0043), and says so in the sentence `<the value> is an input of the test, not an answer
   from <upstream>.`, whose words are fixed up to "test" and whose upstream is the source's
   own. A served answer takes a kind. The check reads the sentence as a mark at any place
   (decision 9), so that a served answer takes a kind is the review's to hold, as whether a
   mark is true is.
4. **The places.** Carried from ADR-0049, decision 4, without the functions that a source names
   (decision 7). The check reads an `httpx.Response` or another `*.Response` that a test
   builds; a route's `.respond(...)`; a body written in the test, given as a positional
   argument to `classify`, to a model's `model_validate` or `model_validate_json`, or to a
   scrub (`scrub`, `scrub_<name>`); a recording served at another URL (`replay_fixture`,
   `replay` or `mount_fixture` with `url=`); and the call of a helper, a class or a fixture of
   the same module that holds a place no mark covers. It reads every `.py` file under `tests/`
   of pytest's rootdir, `tests/fixtures/` left out, as the family check finds the package from
   the rootdir and not from its own file.
5. **The census, in the same run.** Carried from ADR-0049, decision 5. In a run that collects
   the census test, core's `mount_fixture` keeps what it mounts in each test, and the plugin
   compares, before the test's fixtures are torn down, each request that a route answered with
   the recorded one: its host, its path, its query and its body. The comparison goes through
   the recording's redaction, the rule that `recorded_query` and `sent_query` apply: a
   credential's value reads `REDACTED` on both sides, and a value that the recording holds
   `REDACTED`, whole or in part, matches any value sent. A test whose replay answered another
   request names `kind 3` beside `§10`, as ADR-0043 makes it the third kind. No second process
   runs.
6. **The census runs last and judges what ran.** Carried from ADR-0049, decision 6. The census
   test is moved after every other test in `pytest_collection_finish`, once `--ff`, `--lf`,
   `-k` and the deselections of `pytest_collection_modifyitems` are done, and judges the tests
   that ran before it, so a partial run judges only those. pytest-xdist runs each worker as a
   run of its own, whose census sees the tests of that worker alone, so in a worker the census
   test skips and says why.
7. **No declarations beside the line.** The collecting module declares nothing that the check
   reads: `READERS` and `ALLOWED` leave, with the test that failed a stale entry of `ALLOWED`
   (https://github.com/xippios/sdk-core/issues/483, part 2). This reverses ADR-0049, decisions
   7 and 8. A body written in the test and handed to a source's own function is no place, and
   the review reads it as it reads any input. A helper whose places are neither a kind nor an
   input builds none: a recording served where and as it was recorded is built by
   `response_from_fixture`, which the check does not read, as sdk-cashctrl's one excused
   helper is. A name that a collecting module still declares is read by nothing, and the check
   neither reads nor refuses it. The census took no entry before and takes none now: a replay
   for another request is the third kind.
8. **A module of its own, collected by a line of its own.** Carried from ADR-0049, decision 9.
   `xippios.core.testing.built_answers` is collected with
   `from xippios.core.testing.built_answers import *  # noqa: F403` in
   `tests/test_built_answers.py`, which puts two tests there: the reader of decisions 1 to 4
   and the census of decisions 5 and 6. The family check gains nothing, so a source meets the
   check when it adds the line, as ADR-0049 said of the 335 places that stood unmarked then.
9. **No following: any mark covers any place.** The check follows no built body from where it
   is built to where it is served or handed to the recorder, and reads no module's imports to
   tell one `Response` from another (https://github.com/xippios/sdk-core/issues/483, part 2). A
   place is covered by a kind of §10 or by the input's sentence in its reach, whatever the
   place, so the input's sentence marks a route's `.respond(...)` or a body that `classify`
   reads as it marks a literal given to a model. This reverses ADR-0049, decision 10, whole, and
   the reading that decision 4 carried from sdk-cashctrl's check, by which an `httpx.Response`
   given to `fixture_from_response`, directly or by a local name, was an input and any other a
   served answer that the sentence could not mark.

## Consequences

- `src/xippios/core/testing/built_answers.py` loses the following, the two declarations, their
  reader and the stale-entry test, 398 lines of its 980, and its tests lose 410 lines of
  1,347, where https://github.com/xippios/sdk-core/issues/483 estimated about 355 and about
  490: the module's docstring shrank with its rules, and the tests gained those of any mark at
  any place and of a collecting module whose declarations nothing reads. The census and its
  comparison are unchanged.
- sdk-cashctrl collects the check by the line alone: its `READERS = frozenset({"merge_custom"})`
  and its one entry of `ALLOWED` are not written, the five bodies that its tests hand to
  `merge_custom` are no places, and `serve_by_start` in `tests/test_tasks.py` answers each page
  by `response_from_fixture` of its recording in place of an `httpx.Response` built from the
  recorded body, about 10 lines out and 5 changed. The other eleven sources write no
  declaration, and delete the two empty ones where a render of the template put them;
  sdk-template renders the line alone.
- What a source loses: the check no longer tells a served answer that is marked as an input,
  and no entry excuses a helper whose places are neither a kind nor an input. A source that
  meets such a helper builds it on `response_from_fixture`, or asks for a rule of §10 in an
  issue of sdk-core. A suite that passed the check passes it still: the check reads more marks
  and no new place.
- What the check cannot see stays the review's, as its module states: whether a mark is true,
  whether a value marked as an input is served among it; which of several bodies in its reach a
  mark speaks of; a body built in another module, a fixture of `conftest.py` among them; a call
  of httpx's `Response` under another name, `Answer(...)` after `from httpx import Response as
  Answer`; a body passed by keyword or by a name; a recording changed by assignment; and, in the
  census, an answer served otherwise than through `mount_fixture`, a request sent while
  fixtures are torn down and a streamed body.
- The census costs a comparison per answered request in a run that collects it, and nothing in
  a run that does not.
