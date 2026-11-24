"""Count core's surface in two parts and, given trees of consumers, who consumes each piece.

A report and no check: it fails nothing, exits 0 on any tree it can read, and no name and no
parameter leaves core by its count alone (https://github.com/xippios/sdk-core/issues/485).

The surface is the six pinned lists, the ``__all__`` of the six ``__init__.py`` files of
``src/xippios/core``, read by ``ast`` and never imported. It is counted in two parts, and the
package stays one: the workbench, ``testing/`` and ``refresh/``, which a source's tests and
scripts import, and the run-time part, the rest. Each part counts its names, once each, and the
lines of the modules under it.

Each consumer is given as ``name=<path>``, the tree of a source or of the host. Its package
(``src/``), its scripts (``scripts/``), its tests (``tests/``) and the code blocks of its
rendered commands (``.claude/commands/*.md``) are the four kinds of code by which it consumes
core (https://github.com/xippios/sdk-core/issues/473). The report gives:

- each pinned name with its consumers by the kinds of code that reach it, and by the module's
  path where a consumer reaches the name's object outside the lists;
- each keyword-only parameter of a pinned function or class with the consumers that pass it;
- every import from core outside the pinned lists, a module's own import among them.

Run:
    python3 -I scripts/count_surface.py
    python3 -I scripts/count_surface.py example=../sdk-example host=../example-host
    python3 -I scripts/count_surface.py --json --core <tree of core> example=<path>
"""

import argparse
import ast
import json
import re
import sys
import textwrap
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Required, TypedDict

ROOT = "xippios.core"
PACKAGE = Path("src", "xippios", "core")
LISTS = (
    "xippios.core",
    "xippios.core.client",
    "xippios.core.mcp",
    "xippios.core.http",
    "xippios.core.testing",
    "xippios.core.refresh",
)
WORKBENCH = ("testing", "refresh")
RUN_TIME_PART, WORKBENCH_PART = "run time", "workbench"
AREAS = {"src": "package", "scripts": "scripts", "tests": "tests"}
COMMANDS = Path(".claude", "commands")
# A fixture is recorded data, and the other folders hold no code of the consumer's own.
SKIP = frozenset({".git", ".venv", ".worktrees", "__pycache__", "fixtures", "node_modules"})
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
IMPORT_LINE = re.compile(r"\bfrom\s+(xippios\.core(?:\.\w+)*)\s+import\s+\(?\s*([\w \t,]+)")
DEPTH = 10  # how far a re-export or a base class is followed

Key = tuple[str, str]  # (module, name); the name "" for the module itself


class Part(TypedDict):
    """A part of the surface, or the whole package."""

    names: int
    lines: int
    files: int


class Listed(TypedDict):
    """One pinned list."""

    part: str
    names: int


class Surface(TypedDict):
    """The surface in two counts."""

    lists: dict[str, Listed]
    run_time: Part
    workbench: Part
    package: Part
    in_both_parts: list[str]


class Use(TypedDict):
    """The consumers of a piece, each with the kinds of code that reach it."""

    count: int
    consumers: dict[str, list[str]]


class NameUse(Use):
    """A pinned name's consumers, and the modules outside the lists that reach its object."""

    by_other_path: dict[str, list[str]]


class OutsideUse(Use):
    """An import from core outside the pinned lists, and the entries that pin its object."""

    pinned_as: list[str]


class Seen(TypedDict):
    """What the script read of one consumer."""

    files: int
    unread: list[str]


class Tally(TypedDict):
    """How many pieces have no consumer, one, and two or more."""

    none: int
    one: int
    two_or_more: int


class Report(TypedDict, total=False):
    """The surface alone, or the surface and its consumers."""

    surface: Required[Surface]
    consumers: dict[str, Seen]
    names: dict[str, NameUse]
    parameters: dict[str, dict[str, Use]]
    outside: dict[str, OutsideUse]
    summary: dict[str, Tally]


class UnreadableError(Exception):
    """A tree of core that the script cannot read: no package, or a list it cannot parse."""


@dataclass(frozen=True)
class Found:
    """Where core defines a name: its module and the top-level statements that bind it."""

    module: str
    name: str
    nodes: tuple[ast.stmt, ...]


class Core:
    """Core's tree, read by ``ast``: its modules, its six lists and each name's definition."""

    def __init__(self, root: Path) -> None:
        self.package = root / PACKAGE
        if not (self.package / "__init__.py").is_file():
            raise UnreadableError(f"{root}: no package {PACKAGE.as_posix()}")
        self.files: dict[str, Path] = {}
        for path in sorted(self.package.rglob("*.py")):
            if "__pycache__" not in path.parts:
                parts = list(path.relative_to(self.package).with_suffix("").parts)
                if parts[-1] == "__init__":
                    parts.pop()
                self.files[".".join([ROOT, *parts])] = path
        self.modules = frozenset(self.files)
        self._trees: dict[str, ast.Module] = {}
        self._idents: dict[Key, Key | None] = {}
        self.lists = {module: self._pinned(module) for module in LISTS}

    def tree(self, module: str) -> ast.Module:
        """The module parsed, once."""
        if module not in self._trees:
            path = self.files[module]
            try:
                self._trees[module] = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError) as error:
                raise UnreadableError(f"{path}: {error}") from error
        return self._trees[module]

    def part(self, module: str) -> str:
        """The part of the surface that a module of core belongs to."""
        below = module.removeprefix(ROOT).lstrip(".").split(".")[0]
        return WORKBENCH_PART if below in WORKBENCH else RUN_TIME_PART

    def _pinned(self, module: str) -> list[str]:
        if module not in self.files:
            return []
        for node in self.tree(module).body:
            targets = node.targets if isinstance(node, ast.Assign) else []
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            value = getattr(node, "value", None)
            if value is not None and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in targets
            ):
                try:
                    return [str(name) for name in ast.literal_eval(value)]
                except ValueError as error:
                    path = self.files[module]
                    raise UnreadableError(f"{path}: __all__ is no literal list") from error
        return []

    def locate(self, module: str, name: str, depth: int = 0) -> Found | str | None:
        """Where ``module`` gets ``name``: a definition in core, a dotted path outside, or None."""
        if module not in self.files or depth > DEPTH:
            return None
        nodes = tuple(node for node in _top(self.tree(module)) if name in _binds(node))
        if nodes:
            return Found(module, name, nodes)
        source = self._imported(module, name)
        if source is None:
            return None
        origin, original = source
        if origin in self.files:
            return self.locate(origin, original, depth + 1)
        return f"{origin}.{original}"

    def _imported(self, module: str, name: str) -> Key | None:
        package = module if self.files[module].name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(self.tree(module)):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (alias.asname or alias.name) == name:
                        if not node.level:
                            return node.module or "", alias.name
                        parts = package.split(".")
                        parts = parts[: len(parts) - node.level + 1]
                        return ".".join([*parts, *filter(None, [node.module])]), alias.name
        return None

    def ident(self, module: str, name: str) -> Key | None:
        """The definition that ``module.name`` stands for, where core has one."""
        if (module, name) not in self._idents:
            found = self.locate(module, name) if name else None
            self._idents[module, name] = (
                (found.module, found.name) if isinstance(found, Found) else None
            )
        return self._idents[module, name]

    def keywords(self, found: Found) -> list[str]:
        """The keyword-only parameters of a function, every overload's, or of a constructor."""
        words: list[str] = []
        for node in found.nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                words += [arg.arg for arg in node.args.kwonlyargs]
            elif isinstance(node, ast.ClassDef):
                words += self._constructor(found.module, node, 0)
            elif isinstance(node, ast.Assign):
                words += self._derived(found.module, node.value)
        return list(dict.fromkeys(words))

    def _derived(self, module: str, value: ast.expr) -> list[str]:
        """The parameters of ``sync(fn)``, which derives a function with ``fn``'s parameters."""
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and len(value.args) == 1
            and isinstance(value.args[0], ast.Name)
        ):
            return []
        wrapper = self.locate(module, value.func.id)
        wrapped = self.locate(module, value.args[0].id)
        if isinstance(wrapper, Found) and wrapper.module == f"{ROOT}._loop":
            return self.keywords(wrapped) if isinstance(wrapped, Found) else []
        return []

    def _bases(self, module: str, node: ast.ClassDef) -> Iterator[tuple[str, ast.ClassDef]]:
        """The base classes that core defines, each with its module."""
        for base in node.bases:
            found = self.locate(module, base.id) if isinstance(base, ast.Name) else None
            if isinstance(found, Found) and isinstance(found.nodes[-1], ast.ClassDef):
                yield found.module, found.nodes[-1]

    def _constructor(self, module: str, node: ast.ClassDef, depth: int) -> list[str]:
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                return [arg.arg for arg in item.args.kwonlyargs]
        if _dataclass(node) is not None or self._pydantic(module, node, depth):
            return [name for name, keyword in self._fields(module, node, depth) if keyword]
        base = next(self._bases(module, node), None)
        if base is None or depth >= DEPTH:
            return []  # object's constructor, or one outside core: no keyword of core's
        return self._constructor(*base, depth + 1)

    def _pydantic(self, module: str, node: ast.ClassDef, depth: int) -> bool:
        """Whether the class is a pydantic model, whose fields are passed by keyword alone."""
        for base in node.bases:
            found = self.locate(module, base.id) if isinstance(base, ast.Name) else None
            if found in ("pydantic.BaseModel", "pydantic.main.BaseModel"):
                return True
        return depth < DEPTH and any(
            self._pydantic(*base, depth + 1) for base in self._bases(module, node)
        )

    def _fields(self, module: str, node: ast.ClassDef, depth: int) -> list[tuple[str, bool]]:
        """A dataclass's or a pydantic model's fields, each with whether it is keyword-only."""
        inherited: list[tuple[str, bool]] = []
        if depth < DEPTH:
            for base in self._bases(module, node):
                inherited += self._fields(*base, depth + 1)
        decorator = _dataclass(node)
        if decorator is None and not self._pydantic(module, node, depth):
            return inherited
        every = decorator is None or _flag(decorator, "kw_only")
        own: list[tuple[str, bool]] = []
        for item in node.body:
            if not (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)):
                continue
            annotation = ast.unparse(item.annotation)
            if annotation.split("[")[0].split(".")[-1] == "ClassVar":
                continue
            if annotation.split(".")[-1] == "KW_ONLY":
                every = True  # the fields after the marker are keyword-only
                continue
            if decorator is None and item.target.id.startswith("_"):
                continue  # a pydantic private attribute, no field
            spec = item.value if isinstance(item.value, ast.Call) else None
            if spec is not None and ast.unparse(spec.func).split(".")[-1] == "field":
                if _flag(spec, "init", default=True):
                    own.append((item.target.id, every or _flag(spec, "kw_only")))
            else:
                own.append((item.target.id, every))
        names = {name for name, _ in own}
        return [entry for entry in inherited if entry[0] not in names] + own


def _top(tree: ast.Module) -> Iterator[ast.stmt]:
    """A module's top-level statements, those inside a top-level ``if`` or ``try`` included."""
    stack = list(reversed(tree.body))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.If):
            stack += reversed([*node.body, *node.orelse])
        elif isinstance(node, ast.Try):
            handlers = [stmt for handler in node.handlers for stmt in handler.body]
            stack += reversed([*node.body, *handlers, *node.orelse, *node.finalbody])
        else:
            yield node


def _binds(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {target.id for target in node.targets if isinstance(target, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def _dataclass(node: ast.ClassDef) -> ast.expr | None:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if ast.unparse(target).split(".")[-1] == "dataclass":
            return decorator
    return None


def _flag(node: ast.expr, name: str, *, default: bool = False) -> bool:
    """The constant that a call passes as ``name=``, as a bool."""
    if isinstance(node, ast.Call):
        for keyword in node.keywords:
            if keyword.arg == name and isinstance(keyword.value, ast.Constant):
                return bool(keyword.value.value)
    return default


class FileReader(ast.NodeVisitor):
    """One file of a consumer: the pieces of core it names and the keywords it passes them."""

    def __init__(self, modules: frozenset[str]) -> None:
        self.modules = modules
        self.bound: dict[str, str] = {}  # a local name -> the dotted path in core it stands for
        self.taken: set[Key] = set()
        self.keywords: dict[Key, set[str]] = defaultdict(set)
        self.bases: list[Key | None] = []  # per class around the node, its first base in core

    def take(self, module: str, name: str) -> None:
        """Note ``from module import name``; a module that it names is a module of its own."""
        dotted = f"{module}.{name}"
        self.taken.add((dotted, "") if dotted in self.modules else (module, name))

    def resolve(self, node: ast.expr) -> tuple[str, str, list[str]] | None:
        """The module, the name and the attributes after it that an expression reaches in core.

        ``C.get``, where ``C`` is ``xippios.core.client.AsyncClient``, gives
        ``("xippios.core.client", "AsyncClient", ["get"])``; a module itself has the name "".
        """
        attributes: list[str] = []
        while isinstance(node, ast.Attribute):
            attributes.insert(0, node.attr)
            node = node.value
        if not (isinstance(node, ast.Name) and node.id in self.bound):
            return None
        parts = [*self.bound[node.id].split("."), *attributes]
        for end in range(len(parts), 1, -1):
            module = ".".join(parts[:end])
            if module in self.modules:
                rest = parts[end:]
                return module, (rest[0] if rest else ""), rest[1:]
        return None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """``from xippios.core... import name`` and ``from xippios import core``."""
        module = node.module or ""
        if node.level == 0 and (module == ROOT or module.startswith(f"{ROOT}.")):
            for alias in node.names:
                self.take(module, alias.name)
                if alias.name != "*":
                    self.bound[alias.asname or alias.name] = f"{module}.{alias.name}"
        elif node.level == 0 and module == "xippios":
            for alias in node.names:
                if alias.name == "core":
                    self.bound[alias.asname or "core"] = ROOT
                    self.taken.add((ROOT, ""))

    def visit_Import(self, node: ast.Import) -> None:
        """``import xippios.core...``, with an alias or without."""
        for alias in node.names:
            if alias.name == ROOT or alias.name.startswith(f"{ROOT}."):
                self.bound[alias.asname or "xippios"] = alias.name if alias.asname else "xippios"
                self.taken.add((alias.name, ""))

    def visit_Assign(self, node: ast.Assign) -> None:
        """``pytest_plugins``: pytest imports each module that it names."""
        if any(isinstance(t, ast.Name) and t.id == "pytest_plugins" for t in node.targets):
            values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else []
            for value in [node.value, *values]:
                text = value.value if isinstance(value, ast.Constant) else None
                if isinstance(text, str) and (text == ROOT or text.startswith(f"{ROOT}.")):
                    self.taken.add((text, ""))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """An attribute chain that reaches core through a bound name."""
        got = self.resolve(node)
        if got is None:
            self.generic_visit(node)
        else:
            self.taken.add(got[:2])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """A class of the consumer's, whose first base in core takes its ``super().__init__``."""
        bases = [self.resolve(base) for base in node.bases]
        self.bases.append(next((got[:2] for got in bases if got and got[1] and not got[2]), None))
        self.generic_visit(node)
        self.bases.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """A call of a piece of core or of its constructor, no other method: the keywords passed.

        ``Base.__init__(self, ...)`` and, in a subclass of a class of core's,
        ``super().__init__(...)`` pass their keywords to that class's constructor.
        """
        got = self.resolve(node.func)
        called = got[:2] if got and got[1] and got[2] in ([], ["__init__"]) else None
        func = node.func
        if (
            called is None
            and self.bases
            and isinstance(func, ast.Attribute)
            and func.attr == "__init__"
            and isinstance(func.value, ast.Call)
            and isinstance(func.value.func, ast.Name)
            and func.value.func.id == "super"
        ):
            called = self.bases[-1]
        if called is not None:
            self.keywords[called].update(k.arg for k in node.keywords if k.arg is not None)
        self.generic_visit(node)


@dataclass
class Reading:
    """What one consumer's code takes from core, each piece with the kinds of code that take it."""

    files: int = 0
    taken: dict[Key, set[str]] = field(default_factory=dict)
    keywords: dict[Key, dict[str, set[str]]] = field(default_factory=dict)
    unread: list[str] = field(default_factory=list)

    def keep(self, reader: FileReader, kind: str) -> None:
        """Add what one file or one code block took, as code of its kind."""
        for key in reader.taken:
            self.taken.setdefault(key, set()).add(kind)
        for key, words in reader.keywords.items():
            for word in words:
                self.keywords.setdefault(key, {}).setdefault(word, set()).add(kind)


def _code_blocks(text: str) -> Iterator[str]:
    """The fenced code blocks of a Markdown file, each dedented, at any indentation."""
    block: list[str] | None = None
    fence = ""
    for line in text.splitlines():
        found = FENCE.match(line)
        if block is None:
            if found:
                block, fence = [], found.group(1)
        elif found and found.group(1).startswith(fence):
            yield textwrap.dedent("\n".join(block))
            block = None
        else:
            block.append(line)


def read_consumer(base: Path, modules: frozenset[str]) -> Reading:
    """Read one consumer's tree: its package, scripts, tests and its commands' code blocks."""
    reading = Reading()
    for area, kind in AREAS.items():
        top = base / area
        for path in sorted(top.rglob("*.py")) if top.is_dir() else []:
            if SKIP.intersection(path.relative_to(base).parts):
                continue
            reading.files += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                reading.unread.append(path.relative_to(base).as_posix())
                continue
            reader = FileReader(modules)
            reader.visit(tree)
            reading.keep(reader, kind)
    commands = base / COMMANDS
    for path in sorted(commands.glob("*.md")) if commands.is_dir() else []:
        reading.files += 1
        for block in _code_blocks(path.read_text(encoding="utf-8", errors="replace")):
            reader = FileReader(modules)
            try:
                reader.visit(ast.parse(block))
            except (SyntaxError, ValueError):  # a shell block: its import lines alone
                for module, names in IMPORT_LINE.findall(block):
                    for name in names.split(","):
                        if name.split():
                            reader.take(module, name.split()[0])
            reading.keep(reader, "commands")
    return reading


def surface(core: Core) -> Surface:
    """Core's surface in two counts: names and lines of the run-time part and the workbench."""
    names: dict[str, set[str]] = {RUN_TIME_PART: set(), WORKBENCH_PART: set()}
    for module, pinned in core.lists.items():
        names[core.part(module)].update(pinned)
    parts = {part: Part(names=len(found), lines=0, files=0) for part, found in names.items()}
    for module, path in core.files.items():
        with path.open("rb") as handle:
            parts[core.part(module)]["lines"] += sum(1 for _ in handle)
        parts[core.part(module)]["files"] += 1
    return Surface(
        lists={m: Listed(part=core.part(m), names=len(found)) for m, found in core.lists.items()},
        run_time=parts[RUN_TIME_PART],
        workbench=parts[WORKBENCH_PART],
        package=Part(
            names=len(names[RUN_TIME_PART] | names[WORKBENCH_PART]),
            lines=sum(part["lines"] for part in parts.values()),
            files=sum(part["files"] for part in parts.values()),
        ),
        in_both_parts=sorted(names[RUN_TIME_PART] & names[WORKBENCH_PART]),
    )


Who = dict[str, set[str]]  # a consumer -> the kinds of code, or the modules' paths


def _use(who: Who, order: Sequence[str]) -> Use:
    return Use(
        count=sum(1 for c in order if who.get(c)),
        consumers={c: sorted(who[c]) for c in order if who.get(c)},
    )


def _tally(counts: list[int]) -> Tally:
    return Tally(
        none=counts.count(0),
        one=counts.count(1),
        two_or_more=sum(1 for count in counts if count >= 2),
    )


def report(core: Core, readings: dict[str, Reading]) -> Report:
    """The surface and, given consumers, who consumes each pinned name and parameter."""
    result = Report(surface=surface(core))
    if not readings:
        return result
    order = list(readings)
    pinned = [f"{module}:{name}" for module in LISTS for name in core.lists[module]]
    idents = {key: core.ident(*_key(key)) for key in pinned}
    pins: dict[Key, list[str]] = defaultdict(list)  # a definition -> the entries that pin it
    for key, ident in idents.items():
        if ident is not None:
            pins[ident].append(key)

    used: dict[str, Who] = {key: defaultdict(set) for key in pinned}
    other: dict[str, Who] = {key: defaultdict(set) for key in pinned}
    outside: dict[str, Who] = defaultdict(lambda: defaultdict(set))
    calls: dict[Key, dict[str, Who]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for consumer, reading in readings.items():
        for (module, name), kinds in reading.taken.items():
            if module in LISTS and name in ("", "*"):
                for each in core.lists[module] if name == "*" else []:
                    used[f"{module}:{each}"][consumer] |= kinds
            elif module in LISTS and name in core.lists[module]:
                used[f"{module}:{name}"][consumer] |= kinds
            else:
                outside[f"{module}:{name}" if name else module][consumer] |= kinds
                for key in pins.get(core.ident(module, name) or ("", ""), []):
                    other[key][consumer].add(module)
        for called, given in reading.keywords.items():
            ident = core.ident(*called)
            if ident is not None:
                for word, kinds in given.items():
                    calls[ident][word][consumer] |= kinds

    names: dict[str, NameUse] = {}
    for key in pinned:
        use = _use({c: used[key][c] | other[key][c] for c in order}, order)
        names[key] = NameUse(
            count=use["count"],
            consumers=_use(used[key], order)["consumers"],
            by_other_path=_use(other[key], order)["consumers"],
        )
    parameters: dict[str, dict[str, Use]] = {}
    for ident, keys in pins.items():
        found = core.locate(*ident)
        words = core.keywords(found) if isinstance(found, Found) else []
        if words:
            parameters[keys[0]] = {word: _use(calls[ident][word], order) for word in words}
    parameters = {key: parameters[key] for key in pinned if key in parameters}

    result["consumers"] = {c: Seen(files=r.files, unread=r.unread) for c, r in readings.items()}
    result["names"] = names
    result["parameters"] = parameters
    result["outside"] = {
        key: OutsideUse(
            **_use(who, order),
            pinned_as=pins.get(core.ident(*_key(key)) or ("", ""), []),
        )
        for key, who in sorted(outside.items())
    }
    result["summary"] = {
        "names": _tally([use["count"] for use in names.values()]),
        "parameters": _tally(
            [use["count"] for words in parameters.values() for use in words.values()]
        ),
    }
    return result


def _key(text: str) -> Key:
    module, _, name = text.partition(":")
    return module, name


def _who(use: Use, order: Sequence[str], other: dict[str, list[str]] | None = None) -> str:
    """``2 consumers: example (package; by xippios.core.models), host (package)``."""
    consumers, other = use["consumers"], other or {}
    entries = []
    for consumer in (c for c in order if c in consumers or c in other):
        how = ", ".join(consumers.get(consumer, []))
        by = f"by {', '.join(other[consumer])}" if consumer in other else ""
        entries.append(f"{consumer} ({'; '.join(filter(None, [how, by]))})")
    count = use["count"]
    plural = "" if count == 1 else "s"
    return f"{count} consumer{plural}" + (f": {', '.join(entries)}" if entries else "")


def text(result: Report) -> Iterator[str]:
    """The report as text, one line per item."""
    counted = result["surface"]
    for module, listed in counted["lists"].items():
        yield f"list {module}: {listed['names']} names, {listed['part']}"
    for label, part in (
        (RUN_TIME_PART, counted["run_time"]),
        (WORKBENCH_PART, counted["workbench"]),
    ):
        yield f"{label}: {part['names']} names, {part['lines']} lines in {part['files']} files"
    whole = counted["package"]
    yield (
        f"package: {whole['names']} names, {whole['lines']} lines in {whole['files']} files;"
        f" in both parts: {', '.join(counted['in_both_parts']) or 'none'}"
    )
    if "consumers" not in result:
        return
    order = list(result["consumers"])
    for consumer, seen in result["consumers"].items():
        files = f"{seen['files']} file{'' if seen['files'] == 1 else 's'}"
        yield f"consumer {consumer}: {files}" + (
            f", {len(seen['unread'])} unread" if seen["unread"] else ""
        )
    for key, name in result["names"].items():
        yield f"name {key}: {_who(name, order, name['by_other_path'])}"
    for key, words in result["parameters"].items():
        for word, use in words.items():
            yield f"parameter {key}({word}=): {_who(use, order)}"
    for key, reached in result["outside"].items():
        pinned = ", ".join(reached["pinned_as"])
        yield f"outside {key}: {_who(reached, order)}" + (f"; pinned as {pinned}" if pinned else "")
    for consumer, seen in result["consumers"].items():
        for path in seen["unread"]:
            yield f"unread {consumer}: {path}"
    for label, tally in result["summary"].items():
        yield (
            f"{label} by consumers: {tally['none']} with none, {tally['one']} with one,"
            f" {tally['two_or_more']} with two or more"
        )


def _consumer(value: str) -> tuple[str, Path]:
    name, sign, path = value.partition("=")
    if not (name and sign and Path(path).is_dir()):
        raise argparse.ArgumentTypeError(f"{value!r} is no name=<path> of a directory")
    return name, Path(path)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report; exit 0 on any tree that it can read, 2 on one that it cannot."""
    parser = argparse.ArgumentParser(
        prog="count_surface.py",
        description="Count core's surface in two parts, the run-time part and the workbench, "
        "and report who consumes each pinned name and each keyword-only parameter. "
        "A report: it fails nothing.",
    )
    parser.add_argument(
        "consumers",
        nargs="*",
        type=_consumer,
        metavar="name=<path>",
        help="a consumer's tree, such as example=../sdk-example",
    )
    parser.add_argument(
        "--core",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="the tree of core to count (default: this repository)",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    given: list[tuple[str, Path]] = args.consumers
    named = [name for name, _ in given]
    for name in dict.fromkeys(name for name in named if named.count(name) > 1):
        parser.error(f"{name} is named twice")
    try:
        core = Core(args.core)
        result = report(core, {name: read_consumer(path, core.modules) for name, path in given})
    except UnreadableError as error:
        parser.error(str(error))
    if args.json:
        sys.stdout.write(json.dumps(result, indent=1) + "\n")
    else:
        sys.stdout.writelines(f"{line}\n" for line in text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
