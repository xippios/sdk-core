"""The check of a built answer's mark, on small trees that these tests write (ADR-0049).

The reader's rules run on one module's text through ``built_answers.uncovered``. What a source
meets runs through pytester, on a tree laid out as a source's: ``tests/conftest.py`` enables
the plugin and ``tests/test_built_answers.py`` holds the collecting line.
"""

import json
import sys
import textwrap
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from xippios.core.testing import built_answers
from xippios.core.testing.fixtures import Fixture


def clean(source: str) -> str:
    """``source`` as a module's text: dedented, its first line break dropped."""
    return textwrap.dedent(source).lstrip("\n")


def lines(
    source: str, *, readers: tuple[str, ...] = (), allowed: tuple[str, ...] = ()
) -> list[int]:
    """The lines of the places of ``source`` that no mark covers."""
    places = built_answers.uncovered(
        clean(source), "tests/test_x.py", readers=readers, allowed=allowed
    )
    return [place.line for place in places]


def at(source: str, text: str) -> int:
    """The first line of ``source``, read as ``clean`` gives it, that holds ``text``."""
    numbered = enumerate(clean(source).splitlines(), start=1)
    return next(number for number, line in numbered if text in line)


UNMARKED = """
import httpx

def test_one():
    answer = httpx.Response(200, json={"total": 0, "data": []})
"""


# --- the mark ---


def test_a_response_a_test_builds_is_a_place_until_a_mark_names_its_kind() -> None:
    assert lines(UNMARKED) == [4]
    marked = UNMARKED.replace(
        "def test_one():\n",
        'def test_one():\n    """NOT RECORDED: an empty list (conventions §10, kind 2)."""\n',
    )
    assert lines(marked) == []
    assert lines(marked.replace("kind 2", "composed")) == [5], "a mark names its kind by number"
    assert lines(marked.replace("§10", "§9")) == [5], "a mark names §10"
    assert lines(marked.replace("kind 2", "kind 6")) == [5], "§10 has five kinds"
    docstring = '    """Composed, §10 of the conventions.\n\n    It is of kind 2.\n    """\n'
    apart = UNMARKED.replace("def test_one():\n", f"def test_one():\n{docstring}")
    assert lines(apart) == [], "the section and the kind stand anywhere in one docstring"


def test_a_comment_block_marks_as_a_docstring_does() -> None:
    above = UNMARKED.replace(
        "    answer", "    # NOT RECORDED: composed\n    # (conventions §10, kind 2).\n    answer"
    )
    assert lines(above) == []
    on_its_line = UNMARKED.replace("[]})\n", "[]})  # composed (conventions §10, kind 2)\n")
    assert lines(on_its_line) == []
    apart = UNMARKED.replace("    answer", "    # composed (conventions §10, kind 2)\n\n    answer")
    assert lines(apart) == [6], "a block of comments marks the statement right below it"


# --- each kind of place ---

PLACES = [
    pytest.param(
        """
        def test_one(respx_mock):
            respx_mock.get("https://api.example.test/v1/x").respond(200, json={})
        """,
        ".respond(",
        id="a-route-s-respond",
    ),
    pytest.param(
        """
        from httpx import Response

        def test_one():
            Response(404)
        """,
        "Response(404)",
        id="a-response-by-its-bare-name",
    ),
    pytest.param(
        """
        def test_one():
            classify("Unauthorized")
        """,
        "classify(",
        id="a-literal-to-classify",
    ),
    pytest.param(
        """
        def test_one():
            Series.model_validate({"id": 1})
        """,
        "model_validate(",
        id="a-literal-to-a-model",
    ),
    pytest.param(
        """
        def test_one(n):
            Series.model_validate_json(f'{{"id": {n}}}')
        """,
        "model_validate_json(",
        id="an-f-string-to-a-model",
    ),
    pytest.param(
        """
        def test_one():
            scrub_body(b"secret")
        """,
        "scrub_body(",
        id="a-literal-to-a-scrub",
    ),
    pytest.param(
        """
        def test_one(replay_fixture):
            replay_fixture("series", "corn", url="https://api.example.test/v1/other")
        """,
        "url=",
        id="a-replay-at-another-url",
    ),
    pytest.param(
        """
        def test_one(respx_mock):
            replay(respx_mock, PATH, url="https://api.example.test/v1/other")
        """,
        "url=",
        id="a-replay-of-a-path-at-another-url",
    ),
    pytest.param(
        """
        def test_one(respx_mock, fixture):
            mount_fixture(respx_mock, fixture, url="https://api.example.test/v1/other")
        """,
        "url=",
        id="a-mounted-fixture-at-another-url",
    ),
]


@pytest.mark.parametrize(("source", "where"), PLACES)
def test_each_kind_of_place_needs_a_mark(source: str, where: str) -> None:
    assert lines(source) == [at(source, where)]
    docstring = '):\n    """Composed (conventions §10, kind 2)."""\n'
    assert lines(clean(source).replace("):\n", docstring, 1)) == []


NO_PLACES = [
    pytest.param(
        """
        def test_one(replay_fixture):
            replay_fixture("series", "corn")
            replay_fixture("series", "corn", url=None)
        """,
        id="a-replay-at-its-own-path",
    ),
    pytest.param(
        """
        def test_one(response):
            classify(response)
        """,
        id="a-body-handed-by-its-name",
    ),
    pytest.param(
        """
        def test_one():
            Series.model_validate(obj={"id": 1})
        """,
        id="a-literal-by-keyword",
    ),
    pytest.param(
        """
        def test_one():
            merge_custom("<values/>", {})
        """,
        id="a-function-the-source-did-not-name",
    ),
]


@pytest.mark.parametrize("source", NO_PLACES)
def test_what_the_reader_does_not_take_for_a_place(source: str) -> None:
    assert lines(source) == []


def test_a_source_names_its_own_readers() -> None:
    source = """
    def test_one():
        merge_custom("<values/>", {})
    """
    assert lines(source, readers=("merge_custom",)) == [2]
    handed = clean(source).replace(
        "():\n", '():\n    """The stored text is an input of the test, not an answer."""\n'
    )
    assert lines(handed, readers=("merge_custom",)) == [], "a reader takes an input"


# --- the reach of a mark ---


def test_a_class_docstring_reaches_its_methods() -> None:
    source = '''
    import httpx

    class TestSeries:
        """Answers composed from the snapshot's table (conventions §10, kind 2)."""

        def test_one(self):
            httpx.Response(200)
    '''
    assert lines(source) == []
    assert lines(source.replace("kind 2", "two")) == [7]


def test_a_comment_above_an_enclosing_statement_reaches_inside_it() -> None:
    source = """
    import httpx

    def test_one(respx_mock):
        # The 429 as sdk-usda-psd recorded it, served here (conventions §10, kind 3).
        with respx_mock:
            respx_mock.get("https://api.example.test/v1/x").mock(
                return_value=httpx.Response(429)
            )
    """
    assert lines(source) == []
    outside = """
    import httpx

    # The 429 as sdk-usda-psd recorded it, served here (conventions §10, kind 3).
    def test_one(respx_mock):
        with respx_mock:
            respx_mock.get("https://api.example.test/v1/x").mock(
                return_value=httpx.Response(429)
            )
    """
    assert lines(outside) == [at(outside, "return_value=")], "a mark above a function is outside"


def test_a_module_docstring_reaches_nothing() -> None:
    source = '"""Every answer here is composed (conventions §10, kind 2)."""\n' + clean(UNMARKED)
    assert lines(source) == [5]


def test_a_helper_passes_an_unmarked_place_to_each_of_its_calls() -> None:
    source = '''
    import httpx

    def answer(body):
        return httpx.Response(200, json=body)

    def test_marked():
        """A read changed in memory (conventions §10, kind 4)."""
        answer({})

    def test_unmarked():
        answer({})
    '''
    assert lines(source) == [at(source, "def test_unmarked") + 1]
    marked_helper = clean(source).replace(
        "def answer(body):\n",
        'def answer(body):\n    """A read changed in memory (conventions §10, kind 4)."""\n',
    )
    assert lines(marked_helper) == [], "a helper's docstring reaches its calls"
    assert lines(source.split("def test_marked")[0]) == [4], "a helper nothing calls"


def test_a_class_passes_an_unmarked_place_to_its_calls() -> None:
    source = """
    import httpx

    class Upstream:
        def answer(self):
            return httpx.Response(503)

    def test_one():
        Upstream().answer()
    """
    assert lines(source) == [at(source, "Upstream().answer()")]


def test_a_fixture_that_builds_passes_it_to_the_tests_that_take_it() -> None:
    source = '''
    import pytest

    @pytest.fixture
    def served(respx_mock):
        respx_mock.get("https://api.example.test/v1/a").respond(200, json={})

    def test_one(served):
        pass

    def test_two(served):
        """The served list is composed (conventions §10, kind 2)."""
    '''
    assert lines(source) == [at(source, "def test_one")]
    places = built_answers.uncovered(clean(source), "tests/test_x.py")
    assert [place.text for place in places] == ["takes the fixture served"]


def test_a_method_that_takes_the_fixture_is_a_place_as_a_function_is() -> None:
    source = '''
    import httpx
    import pytest

    @pytest.fixture
    def page():
        return httpx.Response(200, json={"rows": []})

    def test_marked(page):
        """The empty page is composed (conventions §10, kind 2)."""

    class TestPages:
        def test_unmarked(self, page):
            pass
    '''
    places = built_answers.uncovered(clean(source), "tests/test_x.py")
    assert [(place.line, place.scope, place.text) for place in places] == [
        (at(source, "def test_unmarked"), "TestPages.test_unmarked", "takes the fixture page")
    ]
    marked = source.replace(
        "class TestPages:\n",
        'class TestPages:\n        """Pages composed (conventions §10, kind 2)."""\n\n',
    )
    assert lines(marked) == [], "the class's docstring reaches its method"


# --- the input of a test ---

INPUT = "is an input of the test, not an answer from Example."


def test_an_input_marks_a_value_handed_to_the_code_and_no_served_answer() -> None:
    served = UNMARKED.replace("def test_one():\n", f'def test_one():\n    """The body {INPUT}"""\n')
    assert lines(served) == [5], "a served answer takes a kind"
    handed = served.replace("    answer = ", "    fixture = fixture_from_response(").replace(
        "})\n", "}))\n"
    )
    assert lines(handed) == [], "an exchange handed to the recorder's code alone is an input"
    by_name = clean(served) + "    step(fixture_from_response(answer))\n"
    assert lines(by_name) == [], "handed on by its name, to fixture_from_response alone"
    used_otherwise = clean(served) + "    step(fixture_from_response(answer), answer)\n"
    assert lines(used_otherwise) == [5]


def test_the_input_s_sentence_is_fixed_up_to_the_word_test() -> None:
    source = f'''
    def test_one():
        """The record {INPUT}"""
        Series.model_validate({{"id": 1}})
    '''
    assert lines(source) == []
    assert lines(source.replace("Example", "CashCtrl")) == [], "the upstream is the source's"
    assert lines(source.replace("is an input of", "is one of the inputs of")) == []
    assert lines(source.replace("of the test", "to the test")) == [3]
    assert lines(source.replace("of the test", "of this test")) == [3]
    commented = source.replace(f'    """The record {INPUT}"""\n', f"    # The record {INPUT}\n")
    assert lines(commented) == []


# --- an exchange that a helper of the module builds for the recorder ---

# The shapes of sdk-google-mail's recorder tests: helpers that return a built exchange, and one
# that gives its parameter to fixture_from_response alone.
RECORDER_TESTS = """
import json

import httpx

URL = "https://api.example.test/v1/messages/1"


def token_exchange():
    request = httpx.Request("POST", "https://auth.example.test/token", data={"code": "c"})
    return httpx.Response(200, json={"access_token": "made-up"}, request=request)


def message_exchange(body, url=URL):
    return httpx.Response(200, json=body, request=httpx.Request("GET", url))


def scrubbed(recorder, response):
    fixture = recorder.rewrite(fixture_from_response(response, scrub=SCRUB), SECRETS)
    return fixture


def test_the_token_is_scrubbed(recorder):
    fixture = scrubbed(recorder, token_exchange())


def test_core_alone_leaves_the_token(recorder):
    fixture = fixture_from_response(token_exchange(), scrub=SCRUB)


def test_a_message_by_its_name(recorder):
    response = message_exchange({"id": "1"})
    fixture = scrubbed(recorder, response)


def test_a_message_s_body(recorder):
    body = json.loads(scrubbed(recorder, message_exchange({"id": "1"})).response.body)
"""

CALLS = (
    "scrubbed(recorder, token_exchange())",
    "fixture_from_response(token_exchange(),",
    "response = message_exchange(",
    "json.loads(scrubbed(recorder, message_exchange(",
)
"""The calls of the helpers in ``RECORDER_TESTS``, each one place where no mark covers it."""


def test_the_input_marks_an_exchange_that_a_helper_returns_to_the_recorder_alone() -> None:
    assert lines(RECORDER_TESTS) == [at(RECORDER_TESTS, call) for call in CALLS]
    in_the_tests = RECORDER_TESTS.replace(
        "(recorder):\n", f'(recorder):\n    """The exchange {INPUT}"""\n'
    )
    assert lines(in_the_tests) == [], "each call is handed to the recorder alone"
    in_the_helpers = RECORDER_TESTS.replace(
        "def token_exchange():\n", f'def token_exchange():\n    """The exchange {INPUT}"""\n'
    ).replace(
        "def message_exchange(body, url=URL):\n",
        f'def message_exchange(body, url=URL):\n    """The exchange {INPUT}"""\n',
    )
    assert lines(in_the_helpers) == [], "the helper's docstring reaches each call that hands it on"
    built_here = """
    import httpx

    def scrubbed(recorder, response):
        return fixture_from_response(response)

    def test_one(recorder):
        scrubbed(recorder, httpx.Response(200, json={}))
    """
    assert lines(built_here) == [at(built_here, "scrubbed(recorder, httpx")]
    marked = clean(built_here).replace("(recorder):\n", f'(recorder):\n    """It {INPUT}"""\n')
    assert lines(marked) == [], "an exchange the test builds, handed on by a function"


SERVED_AND_RECORDED = f'''
import httpx


def exchange():
    """The exchange {INPUT}"""
    return httpx.Response(200, json={{}}, request=httpx.Request("GET", "https://api.example.test"))


def test_recorded():
    fixture_from_response(exchange())


def test_served(respx_mock):
    respx_mock.get("https://api.example.test").mock(return_value=exchange())
'''


def test_a_helper_s_exchange_is_judged_at_each_call_and_a_served_one_takes_a_kind() -> None:
    served = at(SERVED_AND_RECORDED, "mock(return_value=exchange())")
    assert lines(SERVED_AND_RECORDED) == [served], "the call that a route serves takes a kind"
    unmarked = SERVED_AND_RECORDED.replace(f'    """The exchange {INPUT}"""\n', "")
    assert lines(unmarked) == [at(unmarked, "fixture_from_response(exchange())"), served - 1]
    in_the_test = SERVED_AND_RECORDED.replace(
        "(respx_mock):\n", f'(respx_mock):\n    """The exchange {INPUT}"""\n'
    )
    assert lines(in_the_test) == [served + 1], "the input's sentence marks no served answer"
    kind = SERVED_AND_RECORDED.replace(
        "(respx_mock):\n", '(respx_mock):\n    """Composed (conventions §10, kind 2)."""\n'
    )
    assert lines(kind) == []


EXCHANGE = f'''
import httpx


def exchange():
    """The exchange {INPUT}"""
    return httpx.Response(200)


def scrubbed(recorder, response):
    return fixture_from_response(response)


'''
"""A helper that returns an exchange, and one that gives its parameter to the recorder."""

NOT_FOLLOWED = [
    pytest.param(
        "fixture_from_response(response=exchange())",
        "fixture_from_response(response=exchange())",
        id="a-keyword-of-the-recorder",
    ),
    pytest.param(
        "scrubbed(recorder, response=exchange())",
        "scrubbed(recorder, response=exchange())",
        id="a-keyword-of-the-function",
    ),
    pytest.param(
        "for response in [exchange()]:\n        fixture_from_response(response)",
        "for response in [exchange()]:",
        id="a-container",
    ),
    pytest.param(
        "fixture_from_response(wrapped())\n\n\ndef wrapped():\n    return exchange()",
        "fixture_from_response(wrapped())",
        id="a-second-function-that-returns-it",
    ),
    pytest.param(
        "checked(recorder, exchange())\n\n\n"
        "def checked(recorder, response):\n    return scrubbed(recorder, response)",
        "checked(recorder, exchange())",
        id="a-second-function-that-hands-it-on",
    ),
    pytest.param(
        "logged(recorder, exchange())\n\n\n"
        "def logged(recorder, response):\n    print(response)\n"
        "    return fixture_from_response(response)",
        "logged(recorder, exchange())",
        id="a-function-that-reads-it-otherwise",
    ),
    pytest.param(
        "fixture_from_response(exchange())\n\n\n"
        "def test_served(respx_mock):\n"
        "    respx_mock.get('https://api.example.test').mock(side_effect=exchange)",
        "fixture_from_response(exchange())",
        id="a-helper-also-passed-by-its-name",
    ),
    pytest.param(
        "scrubbed = lambda recorder, response: SERVED.append(response)\n"
        "    scrubbed(recorder, exchange())",
        "    scrubbed(recorder, exchange())",
        id="a-name-of-the-function-that-the-test-binds-again",
    ),
]


@pytest.mark.parametrize(("body", "where"), NOT_FOLLOWED)
def test_an_exchange_that_travels_further_is_built_in_the_test_or_takes_a_kind(
    body: str, where: str
) -> None:
    test = f'def test_one(recorder):\n    """The exchange {INPUT}"""\n    {body}\n'
    source = clean(EXCHANGE) + test
    assert lines(source) == [at(source, where)]


HIDDEN = [
    pytest.param("def exchange():", "@serving\ndef exchange():", id="a-decorated-helper"),
    pytest.param(
        "def scrubbed(", "@serving\ndef scrubbed(", id="a-decorated-function-that-hands-it-on"
    ),
    pytest.param(
        "    return httpx.Response(200)",
        "    global LAST\n    LAST = httpx.Response(200)\n    return LAST",
        id="a-helper-that-keeps-it-in-a-global",
    ),
    pytest.param("import httpx\n", "import httpx\nfrom helpers import *\n", id="a-star-import"),
]
"""What could hand the helper or its exchange elsewhere than its calls see, unread by the check."""


@pytest.mark.parametrize(("old", "new"), HIDDEN)
def test_a_helper_whose_exchange_could_go_elsewhere_unseen_is_not_followed(
    old: str, new: str
) -> None:
    # A decorator receives the function, a global is read by any function, and a star import
    # may bind the names of both functions again: a route could serve the exchange unseen.
    docstring = f'    """The exchange {INPUT}"""\n'
    test = f"def test_one(recorder):\n{docstring}    scrubbed(recorder, exchange())\n"
    source = clean(EXCHANGE).replace(old, new) + test
    assert lines(source) == [at(source, "    scrubbed(recorder, exchange())")]


def test_a_return_inside_an_if_statement_is_followed_at_each_call() -> None:
    source = f'''
    import httpx

    def exchange(ok=True):
        """The exchange {INPUT}"""
        if ok:
            return httpx.Response(200)
        return None

    def test_recorded():
        fixture_from_response(exchange())

    def test_served(respx_mock):
        respx_mock.get("https://api.example.test").mock(return_value=exchange(True))
    '''
    assert lines(source) == [at(source, "mock(return_value=exchange(True))")]


def test_an_exchange_chosen_by_a_conditional_expression_is_not_followed() -> None:
    source = f'''
    import httpx

    def exchange(ok):
        """The exchange {INPUT}"""
        return httpx.Response(200) if ok else httpx.Response(404)

    def test_one():
        """The exchange {INPUT}"""
        fixture_from_response(exchange(True))
    '''
    assert lines(source) == [at(source, "fixture_from_response(exchange(True))")]


def test_a_helper_that_nothing_in_its_module_calls_is_judged_as_served() -> None:
    # A helper of conftest.py, whose calls stand in other modules, among them.
    source = clean(EXCHANGE).split("\n\ndef scrubbed")[0]
    assert lines(source) == [at(source, "return httpx.Response(200)")]


# --- the module's imports: which Response a bare name calls ---

HOOK = f'''
def test_reduce():
    """The page {INPUT}"""
    reduce(Response("https://docs.example.test/a", 200, b"", None, None, None, ()))
'''
"""A test of a snapshot hook that builds a page's answer by the bare name ``Response``."""


@pytest.mark.parametrize(
    ("imports", "served"),
    [
        pytest.param("from xippios.core.refresh import Response\n", False, id="the-frame-s"),
        pytest.param("from xippios.core.refresh import Page, Response\n", False, id="among-others"),
        pytest.param("from httpx import Response\n", True, id="httpx-s"),
        pytest.param("from httpx._models import Response\n", True, id="a-module-of-httpx"),
        pytest.param("", True, id="a-name-the-module-does-not-import"),
        pytest.param("from xippios.core.refresh import *\n", True, id="a-star-import"),
        pytest.param("from tests.helpers import Response\n", True, id="a-re-export"),
        pytest.param("from .helpers import Response\n", True, id="a-relative-re-export"),
        pytest.param("from respx.models import Response\n", True, id="another-library-s"),
    ],
)
def test_a_bare_response_is_the_frame_s_only_where_its_module_imports_it_from_the_frame(
    imports: str, served: bool
) -> None:
    source = imports + clean(HOOK)
    assert lines(source) == ([at(source, "reduce(Response(")] if served else [])
    unmarked = source.replace(f'    """The page {INPUT}"""\n', "")
    assert lines(unmarked) == [at(unmarked, "reduce(Response(")], "the frame's Response is a place"


FRAME = "from xippios.core.refresh import Response\n"


def inside(statement: str) -> str:
    """``HOOK`` with ``statement`` as the first line of its test, after the docstring."""
    return clean(HOOK).replace('"""\n', f'"""\n    {statement}\n', 1)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(FRAME + "import httpx\n" + inside("Response = httpx.Response"), id="assigned"),
        pytest.param(FRAME + clean(HOOK).replace("():", "(Response):"), id="a-parameter"),
        pytest.param(
            FRAME
            + "import httpx\n\n\nclass Response(httpx.Response):\n    pass\n\n\n"
            + clean(HOOK),
            id="a-class",
        ),
        pytest.param(FRAME + inside("from httpx import Response"), id="httpx-s-in-the-function"),
        pytest.param(
            "from httpx import Response\n" + inside(FRAME.strip()), id="httpx-s-at-the-top"
        ),
        pytest.param(FRAME + "from helpers import *\n" + clean(HOOK), id="beside-a-star-import"),
    ],
)
def test_the_frame_s_import_names_the_response_only_where_nothing_else_binds_the_name(
    source: str,
) -> None:
    assert lines(source) == [at(source, "reduce(Response(")], "read as httpx's, as before"


def test_the_frame_s_import_in_a_function_and_at_the_top_names_the_frame_s_response() -> None:
    assert lines(FRAME + inside(FRAME.strip())) == []


def test_httpx_s_response_under_another_name_is_no_place() -> None:
    alias = "from httpx import Response as Answer\n\ndef test_one():\n    Answer(200)\n"
    assert lines(alias) == [], "a call the check reads by its name, Answer, is no place"


def test_an_allowed_definition_covers_its_places_and_its_calls() -> None:
    source = """
    import httpx

    def serve(respx_mock):
        respx_mock.get("https://api.example.test/v1/a").respond(200)

    def test_one(respx_mock):
        serve(respx_mock)
    """
    assert lines(source) == [at(source, "    serve(respx_mock)")]
    assert lines(source, allowed=("serve",)) == []


# --- the census's comparison, through the recording's redaction ---


def recording(url: str, *, method: str = "GET", body: str | None = None, **request: str) -> Fixture:
    """A recorded exchange of ``url``, answered ``{}``."""
    return Fixture.model_validate(
        {
            "recorded_at": "2026-11-21T00:00:00Z",
            "request": {"method": method, "url": url, "body": body, **request},
            "response": {"status": 200, "headers": [], "body": "{}"},
        }
    )


SERIES = "https://api.example.test/v1/series"


@pytest.mark.parametrize(
    ("recorded", "sent", "differs"),
    [
        pytest.param(f"{SERIES}?year=2024", f"{SERIES}?year=2024", [], id="the-same"),
        pytest.param(f"{SERIES}?a=1&b=2", f"{SERIES}?b=2&a=1", [], id="in-another-order"),
        pytest.param(f"{SERIES}?year=2024", f"{SERIES}?year=2023", ["query"], id="another-year"),
        pytest.param(SERIES, f"{SERIES}?year=2024", ["query"], id="a-parameter-added"),
        pytest.param(
            f"{SERIES}?year=2024", "https://files.example.test/v1/series?year=2024", ["host"]
        ),
        pytest.param(f"{SERIES}?year=2024", f"{SERIES}/2024?year=2024", ["path"], id="path"),
        pytest.param(
            f"{SERIES}?api_key=REDACTED&year=2024",
            f"{SERIES}?api_key=placeholder&year=2024",
            [],
            id="a-credential",
        ),
        pytest.param(
            f"{SERIES}?api_key=recorded-before-its-scrub",
            f"{SERIES}?api_key=placeholder",
            [],
            id="a-credential-by-the-rule-of-redaction",
        ),
        pytest.param(
            f"{SERIES}?key=REDACTED&year=2024",
            f"{SERIES}?key=placeholder&year=2024",
            [],
            id="a-value-the-recording-redacted",
        ),
        pytest.param(
            f"{SERIES}?q=from%3AREDACTED",
            f"{SERIES}?q=from%3Aalice%40example.test",
            [],
            id="a-value-redacted-in-part",
        ),
        pytest.param(
            f"{SERIES}?key=REDACTED&year=2024",
            f"{SERIES}?key=placeholder&year=2023",
            ["query"],
            id="a-redacted-value-and-another-year",
        ),
    ],
)
def test_the_census_compares_a_request_through_the_recording_s_redaction(
    recorded: str, sent: str, differs: list[str]
) -> None:
    request = httpx.Request("GET", sent)
    assert built_answers._another_request(recording(recorded), request) == differs


FORM = "application/x-www-form-urlencoded"


@pytest.mark.parametrize(
    ("body", "content_type", "sent", "differs"),
    [
        pytest.param("a=1&b=2", FORM, {"data": {"b": "2", "a": "1"}}, [], id="the-same-form"),
        pytest.param("a=1&b=2", FORM, {"data": {"a": "1", "b": "3"}}, ["body"], id="a-form"),
        pytest.param(
            "token=REDACTED&a=1", FORM, {"data": {"token": "placeholder", "a": "1"}}, [], id="cred"
        ),
        pytest.param('{"a": [1, 2]}', "application/json", {"json": {"a": [1, 2]}}, [], id="json"),
        pytest.param(
            '{"a": [1, 2]}', "application/json", {"json": {"a": [1, 3]}}, ["body"], id="json-diff"
        ),
        pytest.param(
            '{"name": "REDACTED", "n": 1}',
            "application/json",
            {"json": {"name": "acme", "n": 1}},
            [],
            id="json-redacted",
        ),
        pytest.param(None, None, {}, [], id="none-sent-none-recorded"),
        pytest.param(None, None, {"data": {"a": "1"}}, ["body"], id="a-body-none-recorded"),
    ],
)
def test_the_census_compares_a_request_s_body(
    body: str | None, content_type: str | None, sent: dict[str, Any], differs: list[str]
) -> None:
    kept = {"content_type": content_type} if content_type else {}
    fixture = recording(SERIES, method="POST", body=body, **kept)
    request = httpx.Request("POST", SERIES, **sent)
    assert built_answers._another_request(fixture, request) == differs


# --- what a source meets: the trees that pytester runs ---

PYPROJECT = '[tool.pytest.ini_options]\naddopts = "-ra --strict-markers --import-mode=importlib"\n'
CONFTEST = 'pytest_plugins = ["xippios.core.testing.plugin"]\n'
COLLECTING = "from xippios.core.testing.built_answers import *  # noqa: F403\n"
CHECKS = 3
"""The tests that the collecting line collects."""

RECORDED = {
    "recorded_at": "2026-11-21T00:00:00Z",
    "request": {"method": "GET", "url": f"{SERIES}?key=REDACTED&year=2024"},
    "response": {"status": 200, "headers": [], "body": '{"data": []}'},
}

# A source's layout. Under --import-mode=importlib, a tree's tests/conftest.py takes the
# module name of this repository's own, which pytest finds imported and uses in its place; that
# one enables the same plugin, so a test that needs no plugin blocks it with -p no:.
TREE: dict[str, str] = {
    "pyproject.toml": PYPROJECT,
    "tests/conftest.py": CONFTEST,
    "tests/test_built_answers.py": COLLECTING,
    "tests/fixtures/series/corn.json": json.dumps(RECORDED),
}

STATIC = "test_built_answers_carry_their_mark"
STALE = "test_built_answers_allowed_entries_are_not_stale"
CENSUS = "test_built_answers_replays_for_another_request_name_the_third_kind"


def run_tree(
    pytester: pytest.Pytester, changes: Mapping[str, str | None], *args: str
) -> pytest.RunResult:
    """Write ``TREE`` with ``changes`` (a path to its text, ``None`` removes it) and run it.

    No bytecode is written: a module rewritten within the second at the same size would
    otherwise run as its earlier text.
    """
    for path, text in {**TREE, **changes}.items():
        target = pytester.path / path
        if text is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(clean(text), encoding="utf-8")
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        return pytester.runpytest(*args)
    finally:
        sys.dont_write_bytecode = writes


def reports(result: pytest.RunResult, test: str) -> list[pytest.TestReport]:
    """The reports of the collected test named ``test``, its setup's, call's and teardown's."""
    every = result.reprec.getreports("pytest_runtest_logreport")  # type: ignore[attr-defined]
    return [report for report in every if report.nodeid.endswith(f"::{test}")]


def outcome(result: pytest.RunResult, test: str) -> str:
    """``passed``, ``failed`` or ``skipped`` for the collected test named ``test``."""
    ours = reports(result, test)
    called: set[str] = {report.outcome for report in ours if report.when == "call"}
    skipped: set[str] = {report.outcome for report in ours if report.skipped}
    return (called or skipped or {"not run"}).pop()


def message(result: pytest.RunResult, test: str) -> str:
    """The message with which the collected test named ``test`` failed or skipped, or ``""``.

    Read from its report, never from the run's output: where the environment names a CI
    (``CI`` or ``BUILD_NUMBER``), pytest's short test summary repeats a failure's message
    whole, and elsewhere it cuts the line at the terminal's width.
    """
    for report in reports(result, test):
        if report.failed or report.skipped:
            if isinstance(report.longrepr, tuple):  # a skip: its path, its line, its reason
                return str(report.longrepr[2])
            return report.longreprtext
    return ""


def ran(result: pytest.RunResult) -> list[str]:
    """The progress lines of a ``-v`` run, one per test, in the order the tests ran."""
    return [
        line
        for line in result.outlines
        if line.startswith("tests/") and (" PASSED" in line or " FAILED" in line)
    ]


TASKS_UNMARKED = """
import httpx


def test_series_is_empty():
    answer = httpx.Response(200, json={"data": []})
    assert answer.json() == {"data": []}
"""


def test_a_source_that_collects_the_check_fails_on_an_unmarked_answer_and_names_it(
    pytester: pytest.Pytester,
) -> None:
    result = run_tree(pytester, {"tests/test_tasks.py": TASKS_UNMARKED})
    result.assert_outcomes(passed=3, failed=1)  # the source's own test and two checks pass
    assert outcome(result, STATIC) == "failed"
    failure = message(result, STATIC)
    assert "names its kind of conventions §10, or that it is an input of the test" in failure
    assert "- tests/test_tasks.py:5 in test_series_is_empty: httpx.Response(200," in failure
    marked = TASKS_UNMARKED.replace(
        "():\n", '():\n    """NOT RECORDED: an empty page (conventions §10, kind 2)."""\n'
    )
    result = run_tree(pytester, {"tests/test_tasks.py": marked})
    result.assert_outcomes(passed=CHECKS + 1)


def test_the_check_reads_the_tests_under_the_root_and_not_beside_its_module(
    pytester: pytest.Pytester,
) -> None:
    result = run_tree(
        pytester,
        {
            "tests/test_built_answers.py": None,
            "tests/checks/test_built_answers.py": COLLECTING,
            "tests/test_tasks.py": TASKS_UNMARKED,
            "tests/fixtures/series/helper.py": TASKS_UNMARKED,
            "scripts/test_elsewhere.py": TASKS_UNMARKED,
        },
        "tests",
    )
    assert outcome(result, STATIC) == "failed"
    failure = message(result, STATIC)
    assert "tests/test_tasks.py:5" in failure
    assert "tests/fixtures/series/helper.py" not in failure, "tests/fixtures/ is not read"
    assert "scripts/test_elsewhere.py" not in failure, "only tests/ is read"


ALLOWING = (
    COLLECTING
    + "\nALLOWED = {\n"
    + '    ("tests/test_tasks.py", "serve"): "each page served where and as it was recorded",\n'
    + "}\n"
)

TASKS_SERVING = """
import httpx


def serve(respx_mock, pages):
    for start, page in pages.items():
        respx_mock.get("https://api.example.test/v1/journal", params={"start": start}).respond(
            200, json=page
        )


def test_journal(respx_mock):
    serve(respx_mock, {})
"""


def test_the_table_of_the_collecting_module_covers_a_helper_with_its_reason(
    pytester: pytest.Pytester,
) -> None:
    result = run_tree(pytester, {"tests/test_tasks.py": TASKS_SERVING})
    assert outcome(result, STATIC) == "failed"
    assert "tests/test_tasks.py:12 in test_journal: serve(respx_mock, {})" in message(
        result, STATIC
    )
    result = run_tree(
        pytester, {"tests/test_tasks.py": TASKS_SERVING, "tests/test_built_answers.py": ALLOWING}
    )
    result.assert_outcomes(passed=CHECKS + 1)


def test_a_stale_entry_of_the_table_fails_and_names_it(pytester: pytest.Pytester) -> None:
    marked = TASKS_SERVING.replace(
        "def serve(respx_mock, pages):\n",
        'def serve(respx_mock, pages):\n    """Pages composed (conventions §10, kind 2)."""\n',
    )
    result = run_tree(
        pytester, {"tests/test_tasks.py": marked, "tests/test_built_answers.py": ALLOWING}
    )
    assert outcome(result, STATIC) == "passed"
    assert outcome(result, STALE) == "failed"
    assert "('tests/test_tasks.py', 'serve'): it covers no place" in message(result, STALE)
    gone = ALLOWING.replace("tests/test_tasks.py", "tests/test_gone.py")
    result = run_tree(
        pytester, {"tests/test_tasks.py": marked, "tests/test_built_answers.py": gone}
    )
    assert outcome(result, STALE) == "failed"
    assert "('tests/test_gone.py', 'serve'): no such module" in message(result, STALE)


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param('ALLOWED = {"serve": "a reason"}\n', id="a-key-that-is-no-pair"),
        pytest.param('ALLOWED = {("tests/test_tasks.py", "serve"): ""}\n', id="no-reason"),
        pytest.param('READERS = "merge_custom"\n', id="readers-as-one-text"),
    ],
)
def test_a_declaration_of_another_form_fails_and_says_the_form(
    pytester: pytest.Pytester, declaration: str
) -> None:
    result = run_tree(
        pytester,
        {
            "tests/test_tasks.py": TASKS_SERVING,
            "tests/test_built_answers.py": COLLECTING + declaration,
        },
    )
    assert outcome(result, STATIC) == "failed"
    assert "the collecting module declares" in message(result, STATIC)


TASKS_READING = """
from example import merge_custom


def test_merged():
    assert merge_custom("<values/>", {"a": "1"})
"""


def test_a_source_names_its_readers_in_the_collecting_module(pytester: pytest.Pytester) -> None:
    files = {
        "tests/test_tasks.py": TASKS_READING,
        "tests/example.py": "def merge_custom(*a): return a\n",
    }
    result = run_tree(pytester, files, "tests/test_built_answers.py")
    assert outcome(result, STATIC) == "passed"
    reading = COLLECTING + 'READERS = frozenset({"merge_custom"})\n'
    result = run_tree(
        pytester, {**files, "tests/test_built_answers.py": reading}, "tests/test_built_answers.py"
    )
    assert outcome(result, STATIC) == "failed"
    assert "tests/test_tasks.py:5 in test_merged: merge_custom(" in message(result, STATIC)


TASKS_REPLAYING = '''
import httpx
import pytest

from xippios.core.client import QueryKeyAuth

QueryKeyAuth("key", "EXAMPLE_API_KEY")  # key is a credential here, as in sdk-usda-nass

SERIES = "https://api.example.test/v1/series"


def test_corn_2024(replay_fixture):
    """The recording at its own path and query."""
    replay_fixture("series", "corn")
    assert httpx.get(SERIES, params={"year": "2024", "key": "placeholder"}).json() == {"data": []}


def test_corn_2023(replay_fixture):
    """MARK"""
    replay_fixture("series", "corn")
    assert httpx.get(SERIES, params={"year": "2023", "key": "placeholder"}).json() == {"data": []}


class TestElsewhere:
    @pytest.mark.parametrize("year", ["2022", "2021"])
    def test_year(self, replay_fixture, year):
        replay_fixture("series", "corn")
        httpx.get(SERIES, params={"year": year, "key": "placeholder"})
'''

THIRD = "The 2024 answer stands for any year without data (conventions §10, kind 3)."


def test_the_census_names_a_replay_for_another_request_without_the_third_kind(
    pytester: pytest.Pytester,
) -> None:
    result = run_tree(pytester, {"tests/test_tasks.py": TASKS_REPLAYING})
    assert outcome(result, STATIC) == "passed", "a replay at its own path is no place"
    assert outcome(result, CENSUS) == "failed"
    failure = message(result, CENSUS)
    assert "- tests/test_tasks.py::test_corn_2023: a replay answered another query" in failure
    assert "- tests/test_tasks.py::TestElsewhere::test_year: a replay answered" in failure
    assert "test_corn_2024" not in failure, "a redacted key is the recorded one"
    assert failure.count("TestElsewhere::test_year") == 1, "a parametrized test is named once"
    marked = TASKS_REPLAYING.replace("MARK", THIRD).replace(
        "class TestElsewhere:\n", f'class TestElsewhere:\n    """{THIRD}"""\n\n'
    )
    result = run_tree(pytester, {"tests/test_tasks.py": marked})
    result.assert_outcomes(passed=CHECKS + 4)


@pytest.mark.parametrize(
    ("mark", "passes"),
    [
        pytest.param('    """MARK"""\n', False, id="no-mark"),
        pytest.param(f'    """{THIRD.replace("kind 3", "kind 2")}"""\n', False, id="another-kind"),
        pytest.param(f"    # {THIRD}\n", True, id="a-comment-inside"),
        pytest.param('    """Of kinds 2 and 3 of conventions §10."""\n', True, id="kinds-2-and-3"),
    ],
)
def test_the_census_reads_the_third_kind_beside_section_10(
    pytester: pytest.Pytester, mark: str, passes: bool
) -> None:
    tasks = TASKS_REPLAYING.split("\n\nclass TestElsewhere")[0].replace('    """MARK"""\n', mark)
    result = run_tree(pytester, {"tests/test_tasks.py": tasks})
    assert outcome(result, CENSUS) == ("passed" if passes else "failed")


def test_the_census_reads_the_third_kind_in_a_helper_or_fixture_the_test_uses(
    pytester: pytest.Pytester,
) -> None:
    helper = f'''
    import httpx
    import pytest


    @pytest.fixture
    def corn(replay_fixture):
        """{THIRD}"""
        return replay_fixture("series", "corn")


    def test_corn_2023(corn):
        httpx.get("https://api.example.test/v1/series", params={{"year": "2023"}})
    '''
    result = run_tree(pytester, {"tests/test_tasks.py": helper})
    assert outcome(result, CENSUS) == "passed"
    result = run_tree(pytester, {"tests/test_tasks.py": helper.replace("kind 3", "kind 2")})
    assert outcome(result, CENSUS) == "failed"


def test_a_recording_served_at_another_url_is_a_place_and_takes_the_third_kind(
    pytester: pytest.Pytester,
) -> None:
    tasks = '''
    import httpx

    OTHER = "https://api.example.test/v1/series/2023"


    def test_corn_2023(replay_fixture):
        """The 2024 answer served at 2023's path (conventions §10, kind 2)."""
        replay_fixture("series", "corn", url=OTHER)
        httpx.get(OTHER, params={"year": "2024"})
    '''
    result = run_tree(pytester, {"tests/test_tasks.py": tasks})
    assert outcome(result, STATIC) == "passed", "any kind marks the place"
    assert outcome(result, CENSUS) == "failed"
    assert "test_corn_2023: a replay answered another path and query" in message(result, CENSUS)
    result = run_tree(pytester, {"tests/test_tasks.py": tasks.replace("kind 2", "kind 3")})
    assert outcome(result, CENSUS) == "passed"


def test_the_census_compares_a_form_body(pytester: pytest.Pytester) -> None:
    posted = {
        "recorded_at": "2026-11-21T00:00:00Z",
        "request": {
            "method": "POST",
            "url": "https://api.example.test/v1/save.json",
            "body": "name=Corn&n=2",
            "content_type": FORM,
        },
        "response": {"status": 200, "headers": [], "body": '{"success": true}'},
    }
    tasks = """
    import httpx


    def test_save(replay_fixture):
        replay_fixture("save", "corn")
        httpx.post("https://api.example.test/v1/save.json", data={"n": "2", "name": "NAME"})
    """
    files = {"tests/fixtures/save/corn.json": json.dumps(posted)}
    result = run_tree(pytester, {**files, "tests/test_tasks.py": tasks.replace("NAME", "Corn")})
    assert outcome(result, CENSUS) == "passed", "the same form, its fields in another order"
    result = run_tree(pytester, {**files, "tests/test_tasks.py": tasks.replace("NAME", "Wheat")})
    assert outcome(result, CENSUS) == "failed"
    assert "test_save: a replay answered another body" in message(result, CENSUS)


def test_the_census_judges_each_call_by_the_recording_mounted_before_it(
    pytester: pytest.Pytester,
) -> None:
    # respx gives back the route it holds for an equal pattern, so the second recording's
    # route is the first's: each call is judged by the recording that answered it.
    corn_2023 = {
        **RECORDED,
        "request": {"method": "GET", "url": f"{SERIES}?key=REDACTED&year=2023"},
    }
    tasks = """
    import httpx

    SERIES = "https://api.example.test/v1/series"


    def test_two_years_in_turn(replay_fixture):
        replay_fixture("series", "corn")
        httpx.get(SERIES, params={"year": "2024", "key": "placeholder"})
        replay_fixture("series", "corn_2023")
        httpx.get(SERIES, params={"year": "SECOND", "key": "placeholder"})
    """
    files = {"tests/fixtures/series/corn_2023.json": json.dumps(corn_2023)}
    result = run_tree(pytester, {**files, "tests/test_tasks.py": tasks.replace("SECOND", "2023")})
    assert outcome(result, CENSUS) == "passed", "each call is the request its recording holds"
    result = run_tree(pytester, {**files, "tests/test_tasks.py": tasks.replace("SECOND", "2024")})
    assert outcome(result, CENSUS) == "failed", "2023's recording answered a request for 2024"
    assert "test_two_years_in_turn: a replay answered another query" in message(result, CENSUS)


def test_the_census_runs_after_every_test_it_judges(pytester: pytest.Pytester) -> None:
    first = {
        "tests/test_built_answers.py": None,
        "tests/test_a_built_answers.py": COLLECTING,
        "tests/test_z_tasks.py": TASKS_REPLAYING,
    }
    result = run_tree(pytester, first, "-v")
    assert outcome(result, CENSUS) == "failed", "the census saw the module collected after it"
    assert CENSUS in ran(result)[-1]
    assert CENSUS not in ran(result)[0]
    again = run_tree(pytester, first, "-v", "--ff")
    assert CENSUS in ran(again)[-1], "a failed census stays last under --ff"
    assert outcome(again, CENSUS) == "failed"


def test_a_partial_run_judges_only_the_tests_that_ran(pytester: pytest.Pytester) -> None:
    files = {"tests/test_tasks.py": TASKS_REPLAYING}
    result = run_tree(pytester, files, "tests/test_built_answers.py")
    assert outcome(result, CENSUS) == "passed"
    result = run_tree(pytester, files, "-k", "not test_corn_2023 and not TestElsewhere")
    assert outcome(result, CENSUS) == "passed"
    result = run_tree(pytester, files, "-k", "test_corn_2023 or built_answers")
    assert outcome(result, CENSUS) == "failed"


def test_the_census_needs_the_plugin(pytester: pytest.Pytester) -> None:
    result = run_tree(pytester, {"tests/conftest.py": None}, "-p", "no:xippios.core.testing.plugin")
    assert outcome(result, CENSUS) == "failed"
    assert "the census of replays needs the plugin" in message(result, CENSUS)
    assert outcome(result, STATIC) == "passed", "the reader needs no plugin"


def test_the_census_skips_in_a_worker_of_pytest_xdist(pytester: pytest.Pytester) -> None:
    # At the tree's root: under --import-mode=importlib, the outer run's tests/conftest.py
    # stands for the tree's own, which has its module name.
    worker = "def pytest_configure(config):\n    config.workerinput = {}  # as pytest-xdist's\n"
    result = run_tree(pytester, {"conftest.py": worker, "tests/test_tasks.py": TASKS_REPLAYING})
    assert outcome(result, CENSUS) == "skipped"
    assert "pytest-xdist" in message(result, CENSUS)


def test_the_census_keeps_nothing_in_a_run_that_does_not_collect_it(
    pytester: pytest.Pytester,
) -> None:
    probe = """
    from xippios.core.testing import replay


    def test_kept(replay_fixture):
        replay_fixture("series", "corn")
        assert replay._mounted is not None


    def test_nothing_kept(replay_fixture):
        replay_fixture("series", "corn")
        assert replay._mounted is None
    """
    result = run_tree(pytester, {"tests/test_tasks.py": probe})
    assert outcome(result, "test_kept") == "passed"
    assert outcome(result, "test_nothing_kept") == "failed"
    result = run_tree(pytester, {"tests/test_tasks.py": probe, "tests/test_built_answers.py": None})
    assert outcome(result, "test_kept") == "failed"
    assert outcome(result, "test_nothing_kept") == "passed"
