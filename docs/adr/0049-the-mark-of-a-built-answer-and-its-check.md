# ADR-0049: The mark of a built answer and its check

Status: Accepted · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/367

## Context

Conventions §10 let a test serve or read a body that was not recorded where and as the test
uses it, of five kinds, and ask the test to say where the body comes from where it builds it,
"as the sources' `NOT RECORDED` docstrings do" (ADR-0028, decision 8). They give the saying no
form, and ADR-0043 settled three cases between the kinds. Three releases of the adoption wave
were held on unmarked answers: sdk-usda-esr
(https://github.com/xippios/sdk-usda-esr/pull/47), sdk-google-mail
(https://github.com/xippios/sdk-google-mail/pull/65) and sdk-cashctrl twice
(https://github.com/xippios/sdk-cashctrl/pull/120). Marking by a reviewer's list did not
converge: in sdk-cashctrl two steps led by reviews marked about 25 places, and a sweep by
script then found 216 more (https://github.com/xippios/sdk-cashctrl/pull/127).

sdk-cashctrl holds the check since that step, in two files of its tests: a reader of its test
modules by `ast`, with a table of exceptions, and a census that runs the replaying modules a
second time in a process of its own and names each test whose replay answered another request
than the recorded one. Measured with it on 2026-11-21, the eleven other sources hold 335
places that need a mark and name no kind (https://github.com/xippios/sdk-core/issues/344).

## Decision

1. **The mark.** A mark names `§10` and a kind, `kind 1` to `kind 5` in §10's order, anywhere
   in one docstring or one block of comments, usually as `NOT RECORDED: <where the body comes
   from> (conventions §10, kind 2)`. It is the phrase that sdk-cashctrl's tests carry, so
   sdk-cashctrl passes as it stands and a reviewer reads the same words as the check.
2. **Its reach.** A mark reaches the places of the function or class whose docstring holds it,
   of the statement that it stands on or above, and of every call of a helper whose docstring
   holds it. A place inside a helper that no mark covers is judged at each call of the helper,
   and a test that takes a fixture holding one is the place. A module's docstring reaches
   nothing, so that a test added to a module states its own kind.
3. **The input's sentence.** A value that no route serves as an answer and no `classify`
   reads, handed to the code under test, is an input of the test (ADR-0043), and says so in
   today's sentence, `<the value> is an input of the test, not an answer from <upstream>.`,
   whose words are fixed up to "test" and whose upstream is the source's own. A served answer
   takes a kind.
4. **The places.** The check reads as sdk-cashctrl's does: an `httpx.Response` or another
   `*.Response` that a test builds; a route's `.respond(...)`; a body written in the test,
   given as a positional argument to `classify`, to a model's `model_validate` or
   `model_validate_json`, to a scrub (`scrub`, `scrub_<name>`) or to a function the source
   names; a recording served at another URL (`replay_fixture`, `replay` or `mount_fixture`
   with `url=`); and the call of a helper, a class or a fixture of the same module that holds
   a place no mark covers. It reads every `.py` file under `tests/` of pytest's rootdir,
   `tests/fixtures/` left out, as the family check finds the package from the rootdir and not
   from its own file.
5. **The census, in the same run.** In a run that collects the census test, core's
   `mount_fixture` keeps what it mounts in each test, and the plugin compares, before the
   test's fixtures are torn down, each request that a route answered with the recorded one:
   its host, its path, its query and its body. The comparison goes through the recording's
   redaction, the rule that `recorded_query` and `sent_query` apply: a credential's value reads
   `REDACTED` on both sides, and a value that the recording holds `REDACTED`, whole or in part,
   matches any value sent, since all 53 fixtures of sdk-usda-nass hold its key redacted and a
   raw comparison would count every replay there. A test whose replay answered another
   request names `kind 3` beside `§10`, as ADR-0043 makes it the third kind. No second process
   runs: sdk-cashctrl's runs 409 of its 570 test functions twice.
6. **The census runs last and judges what ran.** The census test is moved after every other
   test in `pytest_collection_finish`, once `--ff`, `--lf`, `-k` and the deselections of
   `pytest_collection_modifyitems` are done, and judges the tests that ran before it, so a
   partial run judges only those. pytest-xdist runs each worker as a run of its own, whose
   census sees the tests of that worker alone, so in a worker the census test skips and says
   why. No source runs pytest-xdist on 2026-11-21.
7. **The exceptions.** `ALLOWED` in the collecting module maps
   `("tests/<module>.py", "<top-level definition>")` to its reason, as sdk-cashctrl's does: an
   entry covers the places inside that definition and the calls of it, and an entry that covers
   no place, or whose module is gone, fails. The census takes no entry: a replay for another
   request is the third kind by §10 and ADR-0043, so its test names its condition or says that
   it asserts only what was sent.
8. **A source's own names.** `READERS` in the collecting module names the source's own
   functions that take a body written in the test, judged as core's scrubs are
   (`READERS = frozenset({"merge_custom"})` for sdk-cashctrl). Core's check knows core's names
   alone. The names stand beside the table, so one file holds all that the check knows of a
   source, where decision 7 keeps its exceptions; an ini option would hold no reason and part
   it from the table.
9. **A module of its own, collected by a line of its own.**
   `xippios.core.testing.built_answers` is collected with
   `from xippios.core.testing.built_answers import *  # noqa: F403` in
   `tests/test_built_answers.py`. The family check gains nothing: the family module reaches
   every source with its next lock update inside `~=0.4.0`, and the 335 places would fail
   there at once. A source meets the check when its patch adds the line.

## Consequences

- sdk-cashctrl deletes `tests/test_built_answers.py` and `tests/replay_census.py`, collects
  core's check in their place with `READERS = frozenset({"merge_custom"})` and its one entry of
  `ALLOWED` as it stands. Read on its `main` of 2026-11-21, core's reader finds what sdk-cashctrl's
  own check finds, module by module: 103 places and none unmarked in its 17 other modules.
- Every other source marks its places in its patch on 0.4.1 and adds the line, and sdk-template
  renders it. Core's reader gives the row's unmarked counts on sdk-usda-esr (34) and
  sdk-google-mail (49), the same as sdk-cashctrl's check on those trees.
- What the check cannot see stays the review's, as its module states: whether a mark is true;
  which of several bodies in its reach a mark speaks of; a body built in another module, a
  fixture of `conftest.py` among them; a body passed by keyword or by a name; a recording
  changed by assignment; and, in the census, an answer served otherwise than through
  `mount_fixture`, a request sent while fixtures are torn down and a streamed body.
- The census costs a comparison per answered request in a run that collects it, and nothing
  in a run that does not.
