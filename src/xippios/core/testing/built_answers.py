"""The check of a built answer's mark: every body a test builds names its kind (conventions §10).

A source collects it with one line, in ``tests/test_built_answers.py``::

    from xippios.core.testing.built_answers import *  # noqa: F403

The star import puts two tests into that module (ADR-0064). The first reads the source's
tests and fails on each answer that a test builds, and each body that it hands to the
package's code, where no mark says which kind of conventions §10 it is or that it is an input
of the test, naming its file and line. The second, the census, fails on each test whose replay
answered another request than the recorded one without saying that it is §10's third kind.
The plugin (``pytest_plugins = ["xippios.core.testing.plugin"]``) must be enabled, as it is in
every source, since it takes the census. The check has a line of its own, so a source meets it
once it adds the line, and the family check gains nothing. The collecting module declares
nothing beside the line: the check reads no name of it (ADR-0064, decision 7).

**What is read.** Every ``.py`` file under ``tests/`` of pytest's rootdir, as the family
check finds the package, ``tests/fixtures/`` left out, with ``ast`` and its comments.

**A place** is:

- a ``Response`` that a test builds, by its bare name or through a module's name,
  ``httpx.Response`` and the frame's ``Response`` of ``xippios.core.refresh`` alike;
- a route's ``.respond(...)``;
- a body written in the test (a dict, list or tuple display, a string, an f-string or bytes)
  given as a positional argument to ``classify``, to a model's ``model_validate`` or
  ``model_validate_json``, or to a scrub (``scrub`` or ``scrub_<name>``);
- a recording served at another URL: ``replay_fixture``, ``replay`` or ``mount_fixture``
  given ``url=``;
- a call of a helper, a class or a fixture of the same module that holds a place no mark
  covers, a test that takes such a fixture included, a test class's method as a top-level
  test.

A recording replayed at its own operation's path is no place: the census judges it.

**A mark** names ``§10`` and a kind, ``kind 1`` to ``kind 5`` in §10's order, anywhere in one
docstring or one block of comments, usually as ``NOT RECORDED: ... (conventions §10, kind
2)``, or says that the value is an input of the test, in the sentence ``... is an input of the
test, not an answer from <upstream>.``, whose words up to "test" are fixed. Either covers any
place: the check follows no body from where it is built to where it is served or handed to
the recorder, so that a served answer takes a kind, as §10 has it, is the review's to hold
(ADR-0064, decision 9).

**Its reach.** A mark covers a place from the docstring of a function or class that encloses
it, from a comment on the place's own lines, from a block of comments that ends right above
the statement that holds it or above a statement that encloses that one inside its function,
and, for a call of a helper or a test that takes a fixture, from the helper's or the
fixture's docstring. A place inside a helper that no mark covers is judged at each call of the
helper. A module's docstring covers nothing, so that a test added to a module states its own
kind.

**The census.** In a run that collects the census test, the plugin keeps what
``mount_fixture`` mounts in each test (behind ``replay_fixture`` and ``replay``), and before
the test's fixtures are torn down it compares each request that a route answered with the
recorded one: its host, its path, its query and its body, through the redaction that
``recorded_query`` and ``sent_query`` apply, so a credential's value reads ``REDACTED`` on
both sides and a value that the recording holds ``REDACTED``, whole or in part, matches any
value sent. A test whose replay answered another request names ``kind 3`` beside ``§10`` in
its docstring, its class's, a comment inside it, or the docstring of a helper or fixture of
its module that it calls or takes. The census test runs after every other test of the run,
moved there once the run's own reordering is done (``--ff``, ``-k`` and the like), and judges
the tests that ran: a partial run judges only those.

**What the check cannot see:**

- whether a mark is true: that the body is of the kind it names and comes from where it
  says, that a value marked as an input is served by no route and read by no ``classify``,
  and that the third kind's condition holds;
- which of several bodies in its reach a mark speaks of, since one mark covers them all: an
  unmarked body added to a test that carries a mark passes, and a helper's mark covers a
  test that uses the helper for another kind; nor which replay of a test the third kind
  speaks of;
- a body built in another module than the one that serves it, a fixture of ``conftest.py``
  that another module uses among them, or under a name the rules above do not list;
- httpx's ``Response`` called under another name, ``Answer(...)`` after ``from httpx import
  Response as Answer``, which is no place;
- a body passed by keyword or by a name, ``classify(response)`` or
  ``Model.model_validate(obj={...})``, a body handed to a source's own function, and a
  recording changed by assignment, a loaded recording's header replaced and the response then
  handed on by its name;
- in the census: an answer that a test serves otherwise than through ``mount_fixture``, a
  request sent while the test's fixtures are torn down, and a streamed request body, which
  it does not read.
"""

import ast
import base64
import io
import json
import re
import tokenize
from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest
import respx

from xippios.core.redaction import REDACTED, _redact_value, scrub_params
from xippios.core.testing import replay as _replay
from xippios.core.testing.fixtures import Fixture

__all__ = [
    "test_built_answers_carry_their_mark",
    "test_built_answers_replays_for_another_request_name_the_third_kind",
]

_KIND = re.compile(r"\bkinds?\s+[1-5]\b")
_THIRD = re.compile(r"\bkind\s+3\b|\bkinds\s+(?:[1-5],?\s+(?:and\s+)?)*3\b")
_SECTION = re.compile(r"§10\b")
_INPUT = re.compile(r"\binputs?\s+of\s+the\s+test\b", re.IGNORECASE)
_SCRUB = re.compile(r"^scrub(?:_\w+)?$")
_READS = ("classify", "model_validate", "model_validate_json")
_REPLAYS = ("replay_fixture", "replay", "mount_fixture")
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_FORM = "application/x-www-form-urlencoded"

_Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _is_mark(text: str | None) -> bool:
    """A text that names a kind of §10, or says that the value is an input of the test."""
    if not text:
        return False
    return bool(_SECTION.search(text) and _KIND.search(text)) or bool(_INPUT.search(text))


def _literal(node: ast.expr) -> bool:
    """A body written in the test: a dict, list or tuple display, a string or bytes."""
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.JoinedStr)):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))


def _called(func: ast.expr) -> str:
    """The name a call calls: ``respond`` for ``route.respond``, ``Response`` for itself."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


@dataclass(frozen=True)
class Place:
    """A place that builds an answer and no mark covers: where, in what, and what.

    Attributes:
        module: The module's path from the repository's root, ``tests/test_tasks.py``.
        line: The place's line.
        scope: The definitions that hold it, ``TestSeries.test_one``, or ``<module>``.
        text: The place's first line as ``ast`` writes it, or the fixture a test takes.
    """

    module: str
    line: int
    scope: str
    text: str

    def __str__(self) -> str:
        return f"{self.module}:{self.line} in {self.scope}: {self.text}"


class _Module:
    """One test module's tree, its parents, its comments and its top-level definitions."""

    def __init__(self, source: str) -> None:
        self.tree = ast.parse(source)
        self.lines = source.splitlines()
        self.parent: dict[ast.AST, ast.AST] = {
            child: node for node in ast.walk(self.tree) for child in ast.iter_child_nodes(node)
        }
        self.comments = {
            token.start[0]: token.string
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT
        }
        self.defs: dict[str, _Definition] = {
            node.name: node for node in self.tree.body if isinstance(node, _DEFINITIONS)
        }

    def scopes(self, node: ast.AST) -> list[ast.AST]:
        """The functions, lambdas and classes that enclose ``node``, innermost first."""
        found: list[ast.AST] = []
        current = self.parent.get(node)
        while current is not None:
            if isinstance(current, _SCOPES):
                found.append(current)
            current = self.parent.get(current)
        return found

    def named(self, node: ast.AST) -> list[_Definition]:
        """The functions and classes that enclose ``node``, innermost first."""
        return [scope for scope in self.scopes(node) if isinstance(scope, _DEFINITIONS)]

    def outermost(self, node: ast.AST) -> str | None:
        """The top-level definition that holds ``node``, ``None`` at module level."""
        named = self.named(node)
        return named[-1].name if named else None

    def holder(self, node: ast.AST) -> str | None:
        """The top-level definition a place belongs to: a top-level function is its own."""
        if isinstance(node, _FUNCTIONS) and node in self.tree.body:
            return node.name
        return self.outermost(node)

    def scope_name(self, node: ast.AST) -> str:
        return ".".join(scope.name for scope in reversed(self.named(node))) or "<module>"

    def block_above(self, line: int) -> str:
        """The comment lines that end right above ``line``."""
        texts = []
        current = line - 1
        while current >= 1 and self.lines[current - 1].lstrip().startswith("#"):
            texts.append(self.comments.get(current, ""))
            current -= 1
        return "\n".join(reversed(texts))

    def marked(self, node: ast.AST) -> bool:
        """A mark of an enclosing docstring, a comment on its lines or a block above."""
        if any(_is_mark(ast.get_docstring(scope)) for scope in self.named(node)):
            return True
        line = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", None) or line
        if _is_mark(" ".join(self.comments.get(n, "") for n in range(line, end + 1))):
            return True
        if _is_mark(self.block_above(line)):
            return True
        current: ast.AST | None = node
        while current is not None and not isinstance(current, (*_SCOPES, ast.Module)):
            if isinstance(current, ast.stmt) and _is_mark(self.block_above(current.lineno)):
                return True
            current = self.parent.get(current)
        return False

    def builds(self, node: ast.AST) -> bool:
        """Whether ``node`` builds an answer or hands a written body to the package's code."""
        if not isinstance(node, ast.Call):
            return False
        name = _called(node.func)
        if name == "Response" or (isinstance(node.func, ast.Attribute) and name == "respond"):
            return True
        if name in _READS or _SCRUB.match(name):
            return any(_literal(arg) for arg in node.args)
        if name not in _REPLAYS:
            return False
        moved = [k.value for k in node.keywords if k.arg == "url"]
        return any(not (isinstance(v, ast.Constant) and v.value is None) for v in moved)

    def takes_fixtures(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Whether pytest hands ``node`` fixtures: a top-level function, or a class's method.

        A test class's test is such a method, as is a fixture that a class defines.
        """
        return node in self.tree.body or isinstance(self.parent.get(node), ast.ClassDef)

    def calls_of(self, helpers: set[str]) -> dict[ast.AST, str]:
        """Each call of a helper outside it, and each function taking it as a fixture."""
        sites: dict[ast.AST, str] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in helpers and self.holder(node) != node.func.id:
                    sites[node] = node.func.id
            elif isinstance(node, _FUNCTIONS) and self.takes_fixtures(node):
                for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                    if arg.arg in helpers and isinstance(self.defs.get(arg.arg), _FUNCTIONS):
                        sites[node] = arg.arg
        return sites


def uncovered(source: str, name: str) -> list[Place]:
    """The places of one test module that build an answer and no mark covers, by line.

    Args:
        source: The module's text.
        name: Its path from the repository's root, ``tests/test_tasks.py``, for the places.
    """
    module = _Module(source)
    unmarked: set[ast.AST] = {
        node for node in ast.walk(module.tree) if module.builds(node) and not module.marked(node)
    }
    sites: dict[ast.AST, str] = {}
    while True:  # a helper that holds an unmarked place passes it to its calls
        held = {holder for node in unmarked if (holder := module.holder(node)) is not None}
        sites = module.calls_of({helper for helper in held if not helper.startswith("test_")})
        new = {
            site
            for site in sites
            if site not in unmarked
            and not module.marked(site)
            and not (isinstance(site, _FUNCTIONS) and _is_mark(ast.get_docstring(site)))
        }
        if not new:
            break
        unmarked |= new
    judged_at_calls = set(sites.values())
    places = []
    for node in unmarked:
        if isinstance(node, _FUNCTIONS):
            classes = [scope.name for scope in reversed(module.named(node))]
            scope, text = ".".join([*classes, node.name]), f"takes the fixture {sites[node]}"
        elif module.outermost(node) in judged_at_calls:
            continue  # inside a helper: judged where the helper is called
        else:
            scope, text = module.scope_name(node), ast.unparse(node).splitlines()[0][:90]
        places.append(Place(name, getattr(node, "lineno", 0), scope, text))
    return sorted(places, key=lambda place: (place.line, place.text))


def _test_modules(root: Path) -> list[Path]:
    """The ``.py`` files under ``<root>/tests/``, ``tests/fixtures/`` left out."""
    tests = root / "tests"
    if not tests.is_dir():
        pytest.fail(f"the check of built answers reads tests/ under {root}, which has none")
    return sorted(
        path
        for path in tests.rglob("*.py")
        if path.relative_to(tests).parts[0] != "fixtures"
        and not any(part.startswith(".") for part in path.relative_to(tests).parts)
    )


def _module_name(root: Path, path: Path) -> str:
    """``path`` from the repository's root, as a place names its module."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def test_built_answers_carry_their_mark(request: pytest.FixtureRequest) -> None:
    """Every answer a test builds names its kind of §10, or that it is an input (ADR-0064)."""
    root = request.config.rootpath
    places: list[Place] = []
    for path in _test_modules(root):
        places += uncovered(path.read_text(encoding="utf-8"), _module_name(root, path))
    if places:
        pytest.fail(
            "a body built in a test says where it comes from and names its kind of conventions "
            "§10, or that it is an input of the test (ADR-0064):\n"
            + "\n".join(f"- {place}" for place in places),
            pytrace=False,
        )


def test_built_answers_replays_for_another_request_name_the_third_kind(
    request: pytest.FixtureRequest,
) -> None:
    """A test whose replay answered another request names §10's third kind (ADR-0064).

    Judged over the tests of this run that ran before it, the census's (ADR-0043 makes a
    replay at its own path for other parameters the third kind).
    """
    config = request.config
    census = config.stash.get(_CENSUS, None)
    if census is None:
        pytest.fail(
            "the census of replays needs the plugin: pytest_plugins = "
            '["xippios.core.testing.plugin"] in tests/conftest.py',
            pytrace=False,
        )
    unmarked = [
        f"- {module}::{'::'.join(test)}: a replay answered another {' and '.join(sorted(what))}"
        for (module, test), what in sorted(census.found.items())
        if not _names_the_third_kind(census.root / module, test)
    ]
    if unmarked:
        pytest.fail(
            "a replay that answers another request than its recording is the third kind of "
            "conventions §10, and the test says so beside §10, with the condition under which "
            "upstream answers alike or that it asserts only what was sent (ADR-0043):\n"
            + "\n".join(unmarked),
            pytrace=False,
        )


def _names_the_third_kind(path: Path, test: tuple[str, ...]) -> bool:
    """Whether ``test``, its names from its module down, says it is §10's third kind.

    In its docstring or its classes', in a comment inside it, or in the docstring of a helper
    or a fixture of its module that it calls or takes.
    """
    try:
        module = _Module(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    texts: list[str] = []
    found: ast.AST = module.tree
    for name in test:
        body = found.body if isinstance(found, (ast.Module, ast.ClassDef)) else []
        match = next((n for n in body if isinstance(n, _DEFINITIONS) and n.name == name), None)
        if match is None:
            return False
        texts.append(ast.get_docstring(match) or "")
        found = match
    if not isinstance(found, _FUNCTIONS):
        return False
    function = found
    end = function.end_lineno or function.lineno
    texts += [text for line, text in module.comments.items() if function.lineno <= line <= end]
    used = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    arguments = function.args
    used |= {arg.arg for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}
    texts += [
        ast.get_docstring(helper) or ""
        for helper in (module.defs.get(name) for name in used)
        if isinstance(helper, _FUNCTIONS)
    ]
    return any(_SECTION.search(text) and _THIRD.search(text) for text in texts)


def _another_request(fixture: Fixture, request: httpx.Request) -> list[str]:
    """What of ``request`` differs from the request ``fixture`` recorded, in this order.

    ``host``, ``path``, ``query`` and ``body``, compared through the recording's redaction.
    """
    recorded = httpx.URL(fixture.request.url)
    differs = []
    if request.url.host != recorded.host:
        differs.append("host")
    if request.url.path != recorded.path:
        differs.append("path")
    if not _same_fields(recorded.params.multi_items(), request.url.params.multi_items()):
        differs.append("query")
    if not _same_body(fixture, request):
        differs.append("body")
    return differs


def _same_fields(recorded: Iterable[tuple[str, str]], sent: Iterable[tuple[str, str]]) -> bool:
    """The same names and values, in any order, through the recording's redaction.

    A credential's value reads ``REDACTED`` in both, and a value that the recording holds
    ``REDACTED``, whole or in part, matches any value sent under its name.
    """
    kept, given = scrub_params(recorded), scrub_params(sent)
    hidden = {name for name, value in kept if REDACTED in value}

    def fields(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return sorted((name, REDACTED if name in hidden else value) for name, value in items)

    return fields(kept) == fields(given)


def _same_body(fixture: Fixture, request: httpx.Request) -> bool:
    """Whether ``request`` sent the body ``fixture`` recorded, read by its content type."""
    try:
        sent = request.content
    except httpx.RequestNotRead:  # a streamed body: the census does not read it
        return True
    recorded = fixture.request
    if recorded.body is None:
        return not sent
    if recorded.body_base64:
        return base64.b64decode(recorded.body) == sent
    declared = recorded.content_type or request.headers.get("content-type") or ""
    media = declared.split(";", 1)[0].strip().lower()
    text = sent.decode("utf-8", "replace")
    if media == _FORM:
        fields = parse_qsl(recorded.body, keep_blank_values=True)
        return _same_fields(fields, parse_qsl(text, keep_blank_values=True))
    if media == "application/json" or media.endswith("+json"):
        try:
            return _same_json(
                _redact_value(json.loads(recorded.body)), _redact_value(json.loads(text))
            )
        except ValueError:
            pass
    return recorded.body.encode("utf-8") == sent


def _same_json(recorded: Any, sent: Any) -> bool:
    """Equal JSON values, where a text the recording holds ``REDACTED`` in matches any value."""
    if isinstance(recorded, str) and REDACTED in recorded:
        return True
    if isinstance(recorded, dict):
        return (
            isinstance(sent, dict)
            and recorded.keys() == sent.keys()
            and all(_same_json(recorded[key], sent[key]) for key in recorded)
        )
    if isinstance(recorded, list):
        return (
            isinstance(sent, list)
            and len(recorded) == len(sent)
            and all(map(_same_json, recorded, sent))
        )
    return bool(recorded == sent)


class _Census:
    """The plugin's census of the tests whose replay answered another request (ADR-0064).

    It listens only in a run that collects the census test. Each test's mounts are kept from
    its setup, by ``mount_fixture``, and judged before its fixtures are torn down, while the
    routes still hold their calls. respx gives back the route it holds for an equal pattern,
    so a route may serve several recordings in turn: each call is judged by the recording
    mounted last before it.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.listening = False
        self.found: dict[tuple[str, tuple[str, ...]], set[str]] = {}
        """Per test, its module from the root and its names, what its replays answered."""

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Move the census test after every other, once the run's own reordering is done.

        ``pytest_collection_modifyitems`` would run before the wrappers of ``--ff`` and
        ``--lf`` reorder and deselect; ``tryfirst`` runs this before the hooks of other plugins
        that read the order, the listing of ``--collect-only`` among them.
        """
        census = test_built_answers_replays_for_another_request_name_the_third_kind
        last = [item for item in session.items if getattr(item, "function", None) is census]
        if last:
            session.items[:] = [item for item in session.items if item not in last] + last
        self.listening = bool(last)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Generator[None, None, None]:
        if self.listening:
            _replay._mounted = []
        return (yield)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_teardown(self, item: pytest.Item) -> Generator[None, None, None]:
        mounted, _replay._mounted = _replay._mounted, None
        if mounted:
            self.judge(item, mounted)
        return (yield)

    def pytest_unconfigure(self) -> None:
        _replay._mounted = None

    def judge(self, item: pytest.Item, mounted: list[tuple[Fixture, respx.Route, int]]) -> None:
        """Keep ``item`` with what its replays answered of another request, if any."""
        routes: dict[int, respx.Route] = {}
        mounts: dict[int, list[tuple[int, Fixture]]] = {}
        for fixture, route, before in mounted:
            routes[id(route)] = route
            mounts.setdefault(id(route), []).append((before, fixture))
        differs: set[str] = set()
        for key, route in routes.items():
            for index, call in enumerate(route.calls):
                serving = [fixture for before, fixture in mounts[key] if before <= index]
                if serving:  # a call before the first mount was no recording's
                    differs.update(_another_request(serving[-1], call.request))
        if differs:
            names = (*_classes(item), getattr(item, "originalname", item.name))
            test = (_module_name(self.root, item.path), names)
            self.found.setdefault(test, set()).update(differs)


def _classes(item: pytest.Item) -> Iterator[str]:
    """The names of the classes that hold ``item``, outermost first."""
    return (node.name for node in item.listchain() if isinstance(node, pytest.Class))


_CENSUS = pytest.StashKey[_Census]()


def _install_census(config: pytest.Config) -> None:
    """Register the census for this run; the plugin's ``pytest_configure`` calls it."""
    census = _Census(config.rootpath)
    config.stash[_CENSUS] = census
    config.pluginmanager.register(census, "xippios-replay-census")
