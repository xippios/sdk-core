"""The check of a built answer's mark: every body a test builds names its kind (conventions §10).

A source collects it with one line, in ``tests/test_built_answers.py``::

    from xippios.core.testing.built_answers import *  # noqa: F403

The star import puts three tests into that module (ADR-0049). The first reads the source's
tests and fails on each answer that a test builds, and each body that it hands to the
package's code, where no mark says which kind of conventions §10 it is, naming its file and
line. The second fails on a stale entry of the module's table. The third, the census, fails on
each test whose replay answered another request than the recorded one without saying that it
is §10's third kind. The plugin (``pytest_plugins = ["xippios.core.testing.plugin"]``) must
be enabled, as it is in every source, since it takes the census. The check has a line of its
own, so a source meets it once its patch adds the line, and the family check gains nothing.

**What is read.** Every ``.py`` file under ``tests/`` of pytest's rootdir, as the family
check finds the package, ``tests/fixtures/`` left out, with ``ast`` and its comments.

**A place** is:

- an ``httpx.Response`` that a test builds, or another ``*.Response``, which no route serves:
  a bare ``Response`` is httpx's unless it is the frame's record of a page, where every
  binding of the name in the module is an import from ``xippios.core.refresh`` and no star
  import stands beside it, so a re-export, another library's, an assignment, a parameter or
  a class of that name reads as httpx's;
- a route's ``.respond(...)``;
- a body written in the test (a dict, list or tuple display, a string, an f-string or bytes)
  given as a positional argument to ``classify``, to a model's ``model_validate`` or
  ``model_validate_json``, to a scrub (``scrub`` or ``scrub_<name>``) or to a function that
  the collecting module names in ``READERS``;
- a recording served at another URL: ``replay_fixture``, ``replay`` or ``mount_fixture``
  given ``url=``;
- a call of a helper, a class or a fixture of the same module that holds a place no mark
  covers, a test that takes such a fixture included, a test class's method as a top-level
  test.

A recording replayed at its own operation's path is no place: the census judges it.

**A mark** names ``§10`` and a kind, ``kind 1`` to ``kind 5`` in §10's order, anywhere in one
docstring or one block of comments, usually as ``NOT RECORDED: ... (conventions §10, kind
2)``. A value that no route serves and no ``classify`` reads, handed to the code under test,
may instead say that it is an input of the test, in the sentence ``... is an input of the
test, not an answer from <upstream>.``, whose words up to "test" are fixed; a served answer
takes a kind. Such a value is a literal given to a model, a scrub or a reader, the frame's
``Response``, or an ``httpx.Response`` handed to the recorder: one that reaches
``fixture_from_response`` alone as a positional argument, directly or by a local name that
nothing else reads, of ``fixture_from_response`` itself or of a function of the module that
gives that parameter to ``fixture_from_response`` and reads it nowhere else.

**A helper's exchange.** An ``httpx.Response`` that a function of the module returns, directly
or by such a name, is judged at each call of the function: a call handed to the recorder as
above takes the sentence, and one that is not is served and takes a kind. The sentence in the
helper's reach covers each call that hands its exchange on, and a kind there covers every
call. Nothing further is followed: an exchange that travels by a keyword, a container, a
second function that returns it or hands it on, a conditional expression or a function of
another module is built in the test or takes a kind. So is the exchange of a helper, and the
exchange given to a function, that could reach a route unseen: a function that a decorator
receives, whose name the module binds again or reads otherwise than to call it
(``side_effect=helper``), or that stands in a module with a star import; a name that a
``global`` or ``nonlocal`` statement names; and a fixture, which pytest hands on and no call
does (ADR-0049, decision 10).

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
the tests that ran: a partial run judges only those. pytest-xdist splits a run across
processes that each keep a census of their own, so in a worker the census test skips and
says why; the other two tests read files and run under it alike.

**The collecting module's declarations**, both optional:

- ``READERS``, the names of the source's own functions that take a body written in the
  test, judged as a scrub is: ``READERS = frozenset({"merge_custom"})``;
- ``ALLOWED``, ``{("tests/<module>.py", "<top-level definition>"): "<reason>"}``: a helper or
  test whose places are neither a kind of §10 nor an input, with its reason. An entry covers
  the places inside that definition and the calls of it. An entry that covers no place, or
  names a module that is gone, is stale and fails. The census takes no entry, since a
  replay for another request is §10's third kind.

**What the check cannot see:**

- whether a mark is true: that the body is of the kind it names and comes from where it
  says, and that the third kind's condition holds;
- which of several bodies in its reach a mark speaks of, since one mark covers them all: an
  unmarked body added to a test that carries a mark passes, and a helper's mark covers a
  test that uses the helper for another kind; nor which replay of a test the third kind
  speaks of;
- a body built in another module than the one that serves it, a fixture of ``conftest.py``
  that another module uses among them, or under a name the rules above do not list;
- httpx's ``Response`` called under another name, ``Answer(...)`` after ``from httpx import
  Response as Answer``, which is no place, or through another name of ``httpx``,
  ``h.Response(...)`` after ``import httpx as h``, which it reads as served by no route;
- a body passed by keyword or by a name, ``classify(response)`` or
  ``Model.model_validate(obj={...})``, and a recording changed by assignment, a loaded
  recording's header replaced and the response then handed on by its name;
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
from collections.abc import Collection, Generator, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest
import respx

from xippios.core.redaction import REDACTED, _redact_value, scrub_params
from xippios.core.testing import replay as _replay
from xippios.core.testing.fixtures import Fixture

__all__ = [
    "test_built_answers_allowed_entries_are_not_stale",
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
_FRAME = "xippios.core.refresh"
"""The module whose ``Response`` is the frame's record of a page, which no route serves."""
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_FORM = "application/x-www-form-urlencoded"
_FORMS = (
    "the collecting module declares READERS as a set of function names, READERS = "
    'frozenset({"merge_custom"}), and ALLOWED as a mapping of ("tests/<module>.py", '
    '"<top-level definition>") to its reason'
)

_Definition = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _is_mark(text: str | None, served: bool) -> bool:
    """A text that names a kind of §10, or, for a value no route serves, says it is an input."""
    if not text:
        return False
    if _SECTION.search(text) and _KIND.search(text):
        return True
    return not served and _INPUT.search(text) is not None


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
    """One test module's tree, its parents, its comments and its top-level definitions.

    With the names it reads, each to its nodes; every binding of each name anywhere in the
    module, each with the module an import brings it from, ``None`` for any other binding;
    whether a star import may bind any name; and the positions of the parameters of each
    function that can be followed that it gives to ``fixture_from_response`` alone.
    """

    def __init__(self, source: str, readers: Collection[str] = ()) -> None:
        self.tree = ast.parse(source)
        self.lines = source.splitlines()
        self.readers = frozenset(readers)
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
        self.names: dict[str, list[ast.Name]] = {}
        self.bindings: dict[str, list[tuple[ast.AST, str | None, ast.AST]]] = {}
        self.star = False
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                self.names.setdefault(node.id, []).append(node)
            for name, origin in self._binds(node):
                # A global or nonlocal statement may bind the name anywhere: the module's.
                local = not isinstance(node, (ast.Global, ast.Nonlocal))
                scope = next(iter(self.scopes(node)), self.tree) if local else self.tree
                self.bindings.setdefault(name, []).append((node, origin, scope))
        self.handing = {
            name: self._handing(node)
            for name, node in self.defs.items()
            if isinstance(node, _FUNCTIONS) and self.followed(name)
        }

    def _binds(self, node: ast.AST) -> list[tuple[str, str | None]]:
        """The names that ``node`` binds, each with the module an import brings it from.

        A star import binds names that no text shows, so it sets ``star`` and binds none here.
        """
        if isinstance(node, ast.Name):
            return [] if isinstance(node.ctx, ast.Load) else [(node.id, None)]
        if isinstance(node, ast.arg):
            return [(node.arg, None)]
        if isinstance(node, _DEFINITIONS):
            return [(node.name, None)]
        if isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            return [(node.name, None)] if node.name else []
        if isinstance(node, ast.MatchMapping):
            return [(node.rest, None)] if node.rest else []
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return [(name, None) for name in node.names]
        if isinstance(node, ast.Import):
            return [(a.asname or a.name.split(".")[0], f"import {a.name}") for a in node.names]
        if isinstance(node, ast.ImportFrom):
            self.star = self.star or any(alias.name == "*" for alias in node.names)
            origin = "." * node.level + (node.module or "")
            return [(a.asname or a.name, origin) for a in node.names if a.name != "*"]
        return []

    def followed(self, name: str) -> bool:
        """Whether ``name`` at the module's top is its function, which no route reaches unseen.

        Nothing else binds the name at the module's top, a star import, a ``global`` or a
        ``nonlocal`` statement included, and no decorator receives the function. A call is
        the function's where, further, no function that encloses it binds the name
        (``shadowed``).
        """
        function = self.defs.get(name)
        top = [node for node, _, scope in self.bindings.get(name, []) if scope is self.tree]
        return (
            isinstance(function, _FUNCTIONS)
            and not function.decorator_list
            and not self.star
            and len(top) == 1
            and top[0] is function
        )

    def shadowed(self, node: ast.AST, name: str) -> bool:
        """Whether a function, lambda or class that encloses ``node`` binds ``name`` itself."""
        enclosing = set(self.scopes(node))
        return any(scope in enclosing for _, _, scope in self.bindings.get(name, []))

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

    def marked(self, node: ast.AST, served: bool) -> bool:
        """A mark of an enclosing docstring, a comment on its lines or a block above."""
        if any(_is_mark(ast.get_docstring(scope), served) for scope in self.named(node)):
            return True
        line = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", None) or line
        if _is_mark(" ".join(self.comments.get(n, "") for n in range(line, end + 1)), served):
            return True
        if _is_mark(self.block_above(line), served):
            return True
        current: ast.AST | None = node
        while current is not None and not isinstance(current, (*_SCOPES, ast.Module)):
            if isinstance(current, ast.stmt) and _is_mark(self.block_above(current.lineno), served):
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
        if name in _READS or _SCRUB.match(name) or name in self.readers:
            return any(_literal(arg) for arg in node.args)
        if name not in _REPLAYS:
            return False
        moved = [k.value for k in node.keywords if k.arg == "url"]
        return any(not (isinstance(v, ast.Constant) and v.value is None) for v in moved)

    def uses(self, node: ast.expr) -> list[ast.expr]:
        """Where the value of ``node`` is read.

        ``node`` itself, or each read of the one name it is assigned to, in the function that
        holds it.
        """
        parent = self.parent.get(node)
        if not (
            isinstance(parent, ast.Assign)
            and len(parent.targets) == 1
            and isinstance(parent.targets[0], ast.Name)
        ):
            return [node]
        name = parent.targets[0].id
        scope = next((s for s in self.scopes(node) if isinstance(s, _FUNCTIONS)), self.tree)
        return [
            n
            for n in ast.walk(scope)
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
        ]

    def _to_recorder(self, use: ast.AST) -> bool:
        """Whether ``use`` is a positional argument of ``fixture_from_response``."""
        call = self.parent.get(use)
        return (
            isinstance(call, ast.Call)
            and use in call.args
            and ast.unparse(call.func) == "fixture_from_response"
        )

    def _handing(self, function: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[int]:
        """The positions of ``function``'s parameters that it hands to the recorder alone.

        Each read of the parameter a positional argument of ``fixture_from_response``, and no
        other use, so that an exchange given there is handed to the recorder.
        """
        positional = [*function.args.posonlyargs, *function.args.args]
        return frozenset(
            index
            for index, parameter in enumerate(positional)
            if (
                reads := [
                    n
                    for n in ast.walk(function)
                    if isinstance(n, ast.Name) and n.id == parameter.arg
                ]
            )
            and all(isinstance(n.ctx, ast.Load) and self._to_recorder(n) for n in reads)
        )

    def _hands(self, use: ast.expr) -> bool:
        """Whether ``use`` is given to the recorder, directly or through one function.

        A positional argument of ``fixture_from_response``, or of a function of the module at a
        parameter that the function gives to ``fixture_from_response`` alone.
        """
        if self._to_recorder(use):
            return True
        call = self.parent.get(use)
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
            return False
        if use not in call.args or any(isinstance(arg, ast.Starred) for arg in call.args):
            return False
        if self.shadowed(call, call.func.id):  # the calling function's own, not the module's
            return False
        return call.args.index(use) in self.handing.get(call.func.id, frozenset())

    def _escapes(self, node: ast.expr) -> bool:
        """Whether ``node`` is assigned to a name that other functions may read unseen.

        A name that a ``global`` or ``nonlocal`` statement names in the function that holds
        the assignment, where ``uses`` reads that function alone.
        """
        parent = self.parent.get(node)
        if not (
            isinstance(parent, ast.Assign)
            and len(parent.targets) == 1
            and isinstance(parent.targets[0], ast.Name)
        ):
            return False
        name = parent.targets[0].id
        scope = next((s for s in self.scopes(node) if isinstance(s, _FUNCTIONS)), None)
        return scope is not None and any(
            isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names for n in ast.walk(scope)
        )

    def handed(self, node: ast.expr) -> bool:
        """Whether the exchange ``node`` gives reaches ``fixture_from_response`` alone.

        Directly, or by a local name that nothing else reads, as a positional argument of
        ``fixture_from_response``, as before; or so to a function of the module that gives
        that parameter to it alone, where no other function can read the name: an exchange
        handed to the recorder's code, which no route serves.
        """
        uses = self.uses(node)
        if not uses:
            return False
        if all(self._to_recorder(use) for use in uses):
            return True
        return not self._escapes(node) and all(self._hands(use) for use in uses)

    def returned_by(self, node: ast.Call) -> str | None:
        """The top-level function whose every call receives the ``Response`` ``node`` builds.

        The function returns it, directly or by a local name that nothing else reads, no
        ``global`` or ``nonlocal`` statement names that name, the function can be followed
        (``followed``) and the module reads its name only to call it, so each call can be
        judged on its own. ``None`` for anything else: a conditional expression, a fixture,
        which pytest hands on, or a function that a second one returns.
        """
        scopes = self.scopes(node)
        function = scopes[0] if scopes else None
        if _called(node.func) != "Response" or not (
            isinstance(function, _FUNCTIONS)
            and function in self.tree.body
            and self.followed(function.name)
            and not self._escapes(node)
        ):
            return None
        uses = self.uses(node)
        if not uses or not all(
            isinstance(self.parent.get(use), ast.Return) and self.scopes(use)[0] is function
            for use in uses
        ):
            return None
        reads = self.names.get(function.name, [])
        if not reads or not all(
            isinstance(call := self.parent.get(name), ast.Call) and call.func is name
            for name in reads
        ):
            return None
        return function.name

    def serves_at(self, site: ast.AST) -> bool:
        """Whether a helper's returned exchange is served at ``site``, one of its call sites.

        A test that takes the helper as a fixture serves it, and so does a call that does not
        hand it to the recorder, hands it on by a name that other functions may read, or calls
        a name that its own function binds again.
        """
        if not isinstance(site, ast.expr) or self._escapes(site):
            return True
        called = site.func if isinstance(site, ast.Call) else None
        if isinstance(called, ast.Name) and self.shadowed(site, called.id):
            return True
        return not self.handed(site)

    def served_at(self, place: ast.AST, helper: str, site: ast.AST, served: set[ast.AST]) -> bool:
        """Whether ``place``, inside ``helper``, is served at ``site``, a call of the helper.

        An exchange the helper returns, by that call alone; any other place as it was judged.
        """
        if place not in served:
            return False
        if isinstance(place, ast.Call) and self.returned_by(place) == helper:
            return self.serves_at(site)
        return True

    def from_httpx(self, node: ast.Call) -> bool:
        """Whether the ``Response`` that ``node`` builds is httpx's.

        ``httpx.Response`` by its attribute, as before. The bare name is httpx's, as before,
        unless it is the frame's: every binding of the name in the module an import from
        ``xippios.core.refresh``, and no star import beside it.
        """
        if not isinstance(node.func, ast.Name):
            return ast.unparse(node.func) == "httpx.Response"
        bound = self.bindings.get(node.func.id, [])
        frame = bool(bound) and not self.star and all(origin == _FRAME for _, origin, _ in bound)
        return not frame

    def serves(self, node: ast.Call) -> bool:
        """Whether the place serves an answer, which a kind of §10 alone marks.

        A route's answer or one ``classify`` reads; a value handed to the code may be marked
        an input instead. httpx's ``Response`` that a function of the module returns is served
        where a call of the function serves it.
        """
        name = _called(node.func)
        if name == "respond" or name in _REPLAYS or name == "classify":
            return True
        if name != "Response" or not self.from_httpx(node) or self.handed(node):
            return False
        helper = self.returned_by(node)
        if helper is None:
            return True
        sites = self.calls_of({helper})
        return not sites or any(self.serves_at(site) for site in sites)

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


def uncovered(
    source: str, name: str, *, readers: Collection[str] = (), allowed: Collection[str] = ()
) -> list[Place]:
    """The places of one test module that build an answer and no mark covers, by line.

    Args:
        source: The module's text.
        name: Its path from the repository's root, ``tests/test_tasks.py``, for the places.
        readers: The source's own functions that take a body written in the test, judged as
            a scrub is, ``READERS`` of the collecting module.
        allowed: The module's top-level definitions taken as covered, with the calls of
            them, the entries of ``ALLOWED`` for this module.
    """
    module = _Module(source, readers)
    allowed = set(allowed)
    built = [node for node in ast.walk(module.tree) if module.builds(node)]
    served: set[ast.AST] = {n for n in built if isinstance(n, ast.Call) and module.serves(n)}
    unmarked: set[ast.AST] = {
        node
        for node in built
        if not module.marked(node, node in served) and module.outermost(node) not in allowed
    }
    sites: dict[ast.AST, str] = {}
    while True:  # a helper that holds an unmarked place passes it to its calls
        held: dict[str, list[ast.AST]] = {}
        for node in unmarked:
            holder = module.holder(node)
            if holder is not None:
                held.setdefault(holder, []).append(node)
        sites = module.calls_of({h for h in held if not h.startswith("test_")})
        new: set[ast.AST] = set()
        for site, helper in sites.items():
            if site in unmarked or module.holder(site) in allowed:
                continue
            inside = held[helper]
            serves = any(module.served_at(place, helper, site, served) for place in inside)
            if module.marked(site, serves):
                continue
            if isinstance(site, _FUNCTIONS) and _is_mark(ast.get_docstring(site), serves):
                continue
            if not serves and all(module.marked(place, False) for place in inside):
                continue  # the input's sentence in the helper's reach, at a call that hands it on
            new.add(site)
            if serves:
                served.add(site)
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


def _declared(module: ModuleType | None) -> tuple[frozenset[str], dict[tuple[str, str], str]]:
    """``READERS`` and ``ALLOWED`` of the collecting module, either empty where it has none."""
    readers: Any = getattr(module, "READERS", frozenset())
    allowed: Any = getattr(module, "ALLOWED", {})
    names = isinstance(readers, (set, frozenset, list, tuple)) and all(
        isinstance(name, str) and name.isidentifier() for name in readers
    )
    table = isinstance(allowed, Mapping) and all(
        isinstance(key, tuple)
        and len(key) == 2
        and all(isinstance(part, str) for part in key)
        and isinstance(reason, str)
        and reason.strip()
        for key, reason in allowed.items()
    )
    if not (names and table):
        pytest.fail(_FORMS, pytrace=False)
    return frozenset(readers), dict(allowed)


def _module_name(root: Path, path: Path) -> str:
    """``path`` from the repository's root, as the table names a module."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def test_built_answers_carry_their_mark(request: pytest.FixtureRequest) -> None:
    """Every answer a test builds names its kind of §10, or that it is an input (ADR-0049)."""
    readers, allowed = _declared(request.module)
    root = request.config.rootpath
    places: list[Place] = []
    for path in _test_modules(root):
        name = _module_name(root, path)
        covered = {helper for where, helper in allowed if where == name}
        source = path.read_text(encoding="utf-8")
        places += uncovered(source, name, readers=readers, allowed=covered)
    if places:
        pytest.fail(
            "a body built in a test says where it comes from and names its kind of conventions "
            "§10, or that it is an input of the test (ADR-0049):\n"
            + "\n".join(f"- {place}" for place in places),
            pytrace=False,
        )


def test_built_answers_allowed_entries_are_not_stale(request: pytest.FixtureRequest) -> None:
    """Each entry of ``ALLOWED`` still covers a place of its module, or it goes (ADR-0049)."""
    readers, allowed = _declared(request.module)
    root = request.config.rootpath
    stale = []
    for where, helper in allowed:
        path = root / where
        if not path.is_file():
            stale.append(f"({where!r}, {helper!r}): no such module")
            continue
        covered = {h for w, h in allowed if w == where}
        source = path.read_text(encoding="utf-8")
        kept = uncovered(source, where, readers=readers, allowed=covered)
        if uncovered(source, where, readers=readers, allowed=covered - {helper}) == kept:
            stale.append(f"({where!r}, {helper!r}): it covers no place")
    if stale:
        pytest.fail(
            "an entry of ALLOWED that covers nothing is stale and goes:\n"
            + "\n".join(f"- {entry}" for entry in stale),
            pytrace=False,
        )


def test_built_answers_replays_for_another_request_name_the_third_kind(
    request: pytest.FixtureRequest,
) -> None:
    """A test whose replay answered another request names §10's third kind (ADR-0049).

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
    if hasattr(config, "workerinput"):
        pytest.skip(
            "the census of replays judges the tests of one process, and pytest-xdist runs them "
            "in several: run the tests without -n for it"
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
    """The plugin's census of the tests whose replay answered another request (ADR-0049).

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
        ``--lf`` reorder and deselect; ``tryfirst`` runs this before pytest-xdist reports a
        worker's collection, so every worker holds the same order.
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
