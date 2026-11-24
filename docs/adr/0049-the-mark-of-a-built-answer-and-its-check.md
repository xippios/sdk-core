# ADR-0049: The mark of a built answer and its check

Status: Superseded by ADR-0064 · Date: 2026-11-21 · Decided by https://github.com/xippios/sdk-core/issues/367 · Amended 2026-11-22 by https://github.com/xippios/sdk-core/issues/439

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

The trial of the release ran the check once in six sources ported onto core's `main`
(https://github.com/xippios/sdk-core/issues/410) and met two places where it read an input of
the test more narrowly than §10. sdk-google-mail's recorder tests build their exchanges in four
helpers, each returning an `httpx.Response`, and hand them on through a fifth, which gives its
parameter to `fixture_from_response`, so 18 calls that §10 calls inputs could take no sentence,
since the check followed only a response that the test itself hands to `fixture_from_response`
(https://github.com/xippios/sdk-google-mail/issues/72). And a test of a snapshot hook builds the
frame's `Response` of `xippios.core.refresh`, the record of a documentation page, which the
check read as httpx's wherever the test called it by its bare name, so four ports could not mark
it as the input it is (https://github.com/xippios/sdk-comtrade/issues/60,
https://github.com/xippios/sdk-cashctrl/issues/134,
https://github.com/xippios/sdk-usda-esr/issues/59, https://github.com/xippios/sdk-x/issues/57).
Decision 10, the amendment of 2026-11-22, is the maintainer's answer on
https://github.com/xippios/sdk-core/issues/439.

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
10. **An exchange that a helper builds, and the module's imports.** By the maintainer's answer
    on https://github.com/xippios/sdk-core/issues/439, given on 2026-11-22, the check reads more
    inputs than decisions 3 and 4 took from sdk-cashctrl's, and no new place. Of what a module's
    text shows, nothing that it flagged before passes but the shapes below; a name that the
    module binds again at run time, through `globals()`, `setattr` or `monkeypatch.setattr`, no
    reader of the text sees, and the check reads it as the text binds it:
    - *The helper's exchange.* An `httpx.Response` is handed to the recorder, and no route
      serves it, where it reaches `fixture_from_response` alone as a positional argument,
      directly or by a local name that nothing else reads, either of `fixture_from_response`
      itself or of a function of the module that gives that parameter to
      `fixture_from_response` and reads it nowhere else. A response that a function of the
      module returns, directly or by such a name, is judged at each call of the function by the
      same rule: a call so handed is an input, and a call that is not is served and takes a
      kind, so a helper whose exchange one call hands to the recorder and another serves takes
      the sentence for the first and a kind for the second. The sentence in the helper's reach
      covers each call that hands its exchange on, and a kind there covers every call. For a
      helper's exchange and for a function that hands one on, `fixture_from_response` is
      core's recorder only where every binding of the name in the module is an import from
      `xippios.core.testing` or a module under it and no star import stands beside it, as the
      recorder tests of sdk-cashctrl and sdk-google-mail, and sdk-x's trial port, import it; an
      exchange built in the test and given to the name directly is read as before.
    - *No further.* A response that travels by a keyword, a container, a second function that
      returns it or hands it on, a conditional expression or a function of another module,
      `conftest.py` among them, is not followed: it is built in the test or takes a kind. Nor
      is any shape in which a route could reach the exchange unseen: a function that a
      decorator receives; one whose name something else binds at the module's top, a
      `global` or `nonlocal` statement included, or that the module reads otherwise than to
      call it, a route's `side_effect=` among them; a call whose name the calling function
      binds itself; a module with a star import, which may bind any name; an exchange kept in
      a name that a `global` or `nonlocal` statement names; and a fixture's, which pytest hands
      on and no call does. So the rule stays checked: a response that reaches a route is served
      whether a helper built it or not, where taking the sentence on the author's word would
      leave that unseen.
    - *The frame's `Response`.* A bare `Response(...)` is the frame's record of a page, which
      no route serves and the input's sentence marks, only where every binding of the name in
      the module is an import from `xippios.core.refresh` and no star import stands beside
      it. Anywhere else it is httpx's, as before: a re-export, another library's, an
      assignment, a parameter or a class of that name, or httpx's import anywhere in the
      module. A call under another name, `Answer(...)` after `from httpx import Response as
      Answer`, is no place, and a call through an attribute keeps its reading,
      `httpx.Response` httpx's and any other `*.Response` not, both as before.

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
- By decision 10, sdk-google-mail marks its recorder tests' exchanges with the input's
  sentence, in its four helpers' docstrings or at the calls, and a test of a snapshot hook
  marks the frame's `Response` so, by its bare name or as `refresh.Response(...)`. A suite that
  passed the check passes it after the amendment, since the check reads more inputs and no new
  place: sdk-cashctrl, the one source that collects it on 2026-11-22, keeps its entry of
  `ALLOWED`, whose helper hands a response that a nested function returns to a route. Read on
  every module under `tests/` of the twelve sources' `main` and of the six trial branches, no
  source gains a place. httpx's `Response` called through another name of `httpx`,
  `h.Response(...)` after `import httpx as h`, which the check read as served by no route
  before this decision, it still cannot see, nor a name that the module binds again at run
  time, through `globals()`, `setattr` or `monkeypatch.setattr`, which its module states
  with what the check cannot see.
