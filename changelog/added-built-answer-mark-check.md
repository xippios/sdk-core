- `xippios.core.testing.built_answers`, which a source collects with one line in
  `tests/test_built_answers.py`, fails on each answer that a test builds or serves at another
  URL, and each body it hands to the package's code, where no mark names its kind of §10 or
  that it is an input of the test, and names the file and the line. Its census, in the same run
  and after every other test, fails a test whose replay answered another request than the
  recorded one without naming the third kind, compared through the recording's redaction. §10
  states the mark, its reach, the input's sentence, which an exchange that a function of the
  module returns to the recorder and the frame's `Response` take, and the census, and the
  collecting module declares the source's own `READERS` and its table `ALLOWED`.
  (ADR-0049, §10, https://github.com/xippios/sdk-core/issues/344, https://github.com/xippios/sdk-core/issues/439)
  - Hand-apply: `tests/test_built_answers.py` — the collecting line,
    `from xippios.core.testing.built_answers import *  # noqa: F403`, which sdk-template
    renders, with `READERS` and `ALLOWED` where the source needs them — the check reaches no
    source before it holds the line.
    `tests/test_built_answers.py` (sdk-cashctrl) — its own check replaced by the collecting
    line, with `READERS = frozenset({"merge_custom"})` and its one entry of `ALLOWED` as it
    stands — core holds the check, and its reader finds the same places in every module.
    `tests/replay_census.py` (sdk-cashctrl) — deleted — the plugin takes the census in the
    same run.
    `tests/*.py` (sdk-usda-esmis 10, sdk-eurostat 31, sdk-usda-psd 20, sdk-usda-nass 20,
    sdk-comtrade 27, sdk-faostat 38, sdk-usda-wasde 14, sdk-usda-gats 40, sdk-usda-esr 34,
    sdk-x 52, sdk-google-mail 49) — every place marked with `§10` and its kind, or as an input
    of the test, the counts measured on 2026-11-21 and an upper bound of the places without a
    mark alone, and every test that the census fails, whose replay answered another request,
    marked as the third kind or narrowed, which those counts leave out: the trial of the
    release counted 6 in sdk-google-mail, 4 in sdk-comtrade, 24 in sdk-usda-nass, 5 in
    sdk-usda-esr, 11 in sdk-x and none in sdk-cashctrl. Of the places, an exchange that a
    function of the module returns to the recorder, in sdk-google-mail's recorder tests, and
    the frame's `Response`, in a test of a hook, may take the input's sentence, and four of
    sdk-google-mail's six census tests answer their recordings once its two write fixtures are
    recorded again (https://github.com/xippios/sdk-core/issues/439) — the collected check
    fails on each place without its mark, and the census on each such test
    (https://github.com/xippios/sdk-core/issues/435).
