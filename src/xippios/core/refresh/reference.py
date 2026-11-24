"""The frame of a source's reference refresh script, ``scripts/refresh_reference.py`` (ADR-0062).

A source's script declares its packaged lists in one ``Lists``, one ``Listed`` per list with
the fetch that gets it through the source's ``api/`` wrappers, its enum, if any, and its
origin, and hands the declaration to ``run``; the frame does the rest, the same in every
source::

    LISTS = Lists(
        package="xippios.example",
        lists=(Listed("regions", api.get_regions, endpoint="listRegions"),),
        packaged=PACKAGED_LISTS,
        client=client,
    )

    if __name__ == "__main__":
        raise SystemExit(run(LISTS))

The lists must be those the package declares it ships, ``packaged``, its
``params.PACKAGED_LISTS``. Every list is fetched before anything is written, through
``client`` with one attempt per request, each counted, so a 5xx or a 429 spends no second
call of upstream's quota; the requests sent and the quota left are printed after the
fetches, a failed run's too. A fetch answers records or a finished ``PackagedList``. Then
each list is written to ``reference/<name>.json`` by ``PackagedList.write``, the rows of the
provenance table of ``reference/README.md`` are rewritten in place under its one header, and
``enums.py`` is rendered by ``render_enums``, this module's, in the order the lists are
declared, then formatted with ``ruff format`` and ``ruff check --fix``; where no list declares
an enum, ``enums.py`` is left alone. Every file is made, the module formatted, before the
first is written, and they are written as one: a write that fails puts back what the run
replaced, so a run that fails writes nothing and is run again.

``--only`` fetches the lists it names and keeps every other list's file. ``--render-only``
writes the provenance rows and ``enums.py`` from the packaged files alone, without a request
or a key. A hook before the first request and one after the last write carry what a script
writes beside the lists.

The enum renderer stands here, in the frame that alone calls it, and not in the run-time
module ``xippios.core.reference`` (ADR-0062, decision 13).
"""

import argparse
import importlib.util
import inspect
import keyword
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import (
    Awaitable,
    Callable,
    Collection,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx

from xippios.core._loop import run as _run_coroutine
from xippios.core.client import AsyncClient, RetryPolicy
from xippios.core.errors import TransportError
from xippios.core.models import UpstreamModel
from xippios.core.reference import PackagedList
from xippios.core.refresh.upstream import Snapshot
from xippios.core.refresh.upstream import run as _run_snapshot

COMMAND = "uv run python scripts/refresh_reference.py"
"""How a source runs its reference refresh script, from its repository's root."""
GENERATOR = "scripts/refresh_reference.py"
"""What the docstring of the generated ``enums.py`` names as its generator."""
README = "README.md"
"""The file under ``reference/`` that holds the provenance table, one row per file."""
HEADER = "| File | Origin | Fetched |"
"""The provenance table's one header, the one sdk-template renders: no row counts its
file's records (ADR-0062, decision 13)."""

type Record = UpstreamModel | Mapping[str, Any]
"""One record a fetch answers: a model, kept by ``dump_upstream``, or a mapping as it is."""
type Fetched = PackagedList | Sequence[Record]
"""What a list's fetch answers: records or a finished ``PackagedList``."""
type Fetch = Callable[[], Awaitable[Fetched] | Fetched]
"""A list's fetch: a function of no argument, async like the ``api/`` wrappers, or not."""
type MemberNames = Mapping[Any, str] | Callable[[Sequence[Any]], Mapping[Any, str]]
"""Members named by hand, per value or id, or made from the list's values or pairs."""

_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
"""A list's name: the file ``reference/<name>.json``, with no separator and no dot first."""
_ROW = re.compile(r"\| `(?P<file>[^`]+)` \|")
"""The start of a provenance row, its file's name in a code span."""


@dataclass(frozen=True)
class Enumeration:
    """The enum a list makes in ``enums.py``: a ``StrEnum`` of its values, or an ``IntEnum``.

    A ``StrEnum`` reads its values from the field its packaged file's ``param`` names, and its
    key, which its docstring names and its class takes its name from, is the list's name; an
    ``IntEnum`` reads the fields ``ids`` and ``names``, and its key is ``ids`` (ADR-0062,
    decision 11).

    Attributes:
        ids: The field of each integer id, for an ``IntEnum`` of ``(id, name)`` pairs,
            e.g. ``"seriesId"``; given with ``names``.
        names: The field of each id's name, e.g. ``"seriesName"``.
        class_name: The class's name where core's default from the key will not do, e.g.
            ``"Region"`` for ``regions``.
        member_names: Members named by hand, per value or per id, where a derived name
            collides or there is none: a mapping, or a function of the list's values or
            pairs that returns one, for a rule that names many (``render_enums``).
    """

    ids: str | None = None
    names: str | None = None
    class_name: str | None = None
    member_names: MemberNames | None = None


@dataclass(frozen=True)
class Listed:
    """One packaged list, ``reference/<name>.json``, and how the frame gets it.

    Attributes:
        name: The list's name, its file under ``reference/`` without ``.json`` and the name
            ``--only`` takes, e.g. ``"regions"`` or ``"regions_v2"``.
        fetch: Gets the list through the source's ``api/`` wrappers, never through a task
            that answers from the package: records, a model's by ``dump_upstream`` and a
            mapping as it is, a list of values as records of one field named by ``param``
            that the fetch makes; or a finished ``PackagedList``, written as built. Records
            are fetched when the fetch returns; a finished list carries its own
            ``fetched``, such as the wrapper's ``retrieved_at`` or the time of its first
            request.
        endpoint: The upstream operation the list comes from, the file's ``endpoint``:
            needed for records, and where given, a finished list's must match.
        param: The upstream parameter the list feeds, the file's ``param``: ``name`` by
            default for records, and where given, a finished list's must match.
        enum: The enum the list makes in ``enums.py``, or ``None`` for a table.
        origin: The provenance row's Origin: a text, or a function of the list as written
            that returns it; ``None`` writes the list's endpoint in a code span.
    """

    name: str
    fetch: Fetch
    endpoint: str | None = None
    param: str | None = None
    enum: Enumeration | None = None
    origin: str | Callable[[PackagedList], str] | None = None


@dataclass(frozen=True)
class Lists:
    """A source's reference refresh script's declaration, which ``run`` takes (ADR-0062).

    It stands beside ``Snapshot``, the snapshot script's, so that both frames take one
    declaration under one ``run``.

    Attributes:
        package: The source's import path, e.g. ``"xippios.example"``, as
            ``PackagedList.load`` takes it: the frame writes into its directory as imported,
            which must lie in the directory the script runs in.
        lists: The lists, one ``Listed`` each, in the order of their enums in ``enums.py``.
        packaged: The names of the lists the package declares it ships, such as its
            ``params.PACKAGED_LISTS``: the lists must be exactly these, or the run stops
            before a request, naming those declared on one side alone.
        client: The client the fetches send through, the one the ``api/`` wrappers hold:
            one attempt per request for the run, each counted, its configuration restored
            after.
        quota_header: The response header in which upstream reports the requests left in
            its quota, e.g. ``"x-ratelimit-remaining"``, or ``None`` where it reports none.
        before: Called once before the first request, after the command line and the
            declaration are checked: what can stop the run before it spends a request,
            such as parsing a snapshot's table that a file beside the lists is made from.
        after: Called after the last write with the lists this run fetched, by name: what
            a script writes beside the lists, an index or a manifest. A hook that raises
            leaves the frame's files written, and the run says so before the error ends
            it. Neither hook is called by ``--render-only``.
    """

    package: str
    lists: Sequence[Listed]
    packaged: Collection[str]
    client: AsyncClient
    quota_header: str | None = None
    before: Callable[[], object] | None = None
    after: Callable[[Mapping[str, PackagedList]], object] | None = None


class _Meter:
    """What a run spent: the requests it sent and the quota left that upstream reported.

    The client's ``observe`` hook for the run, which core calls with every response from the
    wire, after the hook the client had, a quota policy's say (ADR-0037).
    """

    def __init__(
        self, observe: Callable[[httpx.Response], None] | None, header: str | None
    ) -> None:
        self.sent = 0
        self.unanswered = 0
        self.left: int | None = None
        self._observe = observe
        self._header = header

    def __call__(self, response: httpx.Response) -> None:
        if self._observe is not None:
            self._observe(response)
        self.sent += 1
        value = response.headers.get(self._header) if self._header else None
        if value is not None and value.isascii() and value.isdigit():
            self.left = int(value)

    def report(self) -> str:
        """The requests sent and the quota left, as upstream last reported it, one line."""
        left = "not reported" if self.left is None else f"{self.left} ({self._header})"
        unanswered = (
            f" ({self.unanswered} ended in a transport error, counted as sent)"
            if self.unanswered
            else ""
        )
        return f"requests sent: {self.sent}{unanswered}; quota left: {left}"


@contextmanager
def _metered(client: AsyncClient, header: str | None) -> Iterator[_Meter]:
    """``client`` for the block: one attempt per request, each counted, then the report.

    A request that fails in transport has no response to count, and with one attempt its
    error ends the block: it is counted as sent, since it may have reached upstream. The
    client's configuration is restored after the block and the report printed, a failed
    run's too.
    """
    configured = client.config
    meter = _Meter(configured.observe, header)
    client.config = replace(configured, retry=RetryPolicy(max_attempts=1), observe=meter)
    try:
        yield meter
    except TransportError:
        meter.sent += 1
        meter.unanswered += 1
        raise
    finally:
        client.config = configured
        print(meter.report())  # noqa: T201


def _directory(package: str) -> Path:
    """The package's directory as imported, which must lie in the directory the script runs in.

    Raises:
        SystemExit: The package is not importable, or is imported from elsewhere, such as an
            installed copy, which the frame must not write into.
    """
    try:
        spec = importlib.util.find_spec(package)
    except (ImportError, ValueError):
        spec = None
    locations = list(spec.submodule_search_locations or []) if spec is not None else []
    if len(locations) != 1:
        raise SystemExit(
            f"{package} is not importable as one package directory: run the script from the "
            "repository's root in its project environment. Nothing was fetched or written."
        )
    directory = Path(locations[0]).resolve()
    if not directory.is_relative_to(Path.cwd().resolve()):
        raise SystemExit(
            f"{package} is imported from {directory}, outside the directory the script runs "
            f"in: run {COMMAND} from the repository's root in its project environment. "
            "Nothing was fetched or written."
        )
    return directory


def _check(lists: Sequence[Listed], packaged: Collection[str]) -> None:
    """Stop on a declaration the frame cannot run, before anything is fetched.

    Raises:
        SystemExit: No list, a name that is no file's name or that two lists take, an
            enum that names one of ``ids`` and ``names`` alone, two enums of one key, or
            lists other than those the package declares it ships, ``packaged``.
    """
    if not lists:
        raise SystemExit("Nothing to fetch: declare the lists, one Listed each.")
    if isinstance(packaged, str) or not all(isinstance(name, str) for name in packaged):
        raise SystemExit(
            "packaged names the lists the package ships, a collection of names such as its "
            "params.PACKAGED_LISTS, not a text"
        )
    names: set[str] = set()
    keys: set[str] = set()
    for listed in lists:
        if not isinstance(listed, Listed):
            raise SystemExit(f"Lists takes one Listed per list, not {type(listed).__name__}")
        if not _FILE.fullmatch(listed.name):
            raise SystemExit(
                f"{listed.name!r}: a list's name is a file's name under reference/, without "
                ".json, a separator or a dot first"
            )
        if listed.name in names:
            raise SystemExit(f"two lists are named {listed.name}")
        names.add(listed.name)
        enum = listed.enum
        if enum is None:
            continue
        if (enum.ids is None) != (enum.names is None):
            raise SystemExit(
                f"{listed.name}: an Enumeration of ids names both ids and names, the fields "
                "of the ids and of their names, and one of values names neither"
            )
        key = enum.ids or listed.name
        if key in keys:
            raise SystemExit(f"two lists declare the enum of key {key}")
        keys.add(key)
    shipped = set(packaged)
    if names != shipped:
        alone = ", ".join(sorted(names - shipped)) or "none"
        theirs = ", ".join(sorted(shipped - names)) or "none"
        raise SystemExit(
            "The lists declared to run are not those the package declares it ships: declared "
            f"to run alone: {alone}. Declared by the package alone: {theirs}. Nothing was "
            "fetched or written."
        )


def _origin(listed: Listed, packaged: PackagedList) -> str:
    """The provenance row's Origin for ``listed`` as written.

    Raises:
        SystemExit: The text holds a ``|`` or a line break, which would break the row.
    """
    if listed.origin is None:
        text = f"`{packaged.endpoint}`"
    elif isinstance(listed.origin, str):
        text = listed.origin
    else:
        text = listed.origin(packaged)
    if "|" in text or "\n" in text or "\r" in text:
        raise SystemExit(f"{listed.name}'s origin holds a | or a line break: {text!r}")
    return text


def _table(text: str, readme: Path) -> int:
    """Where the provenance table's one header stands in ``text``.

    Raises:
        SystemExit: ``text`` holds no ``HEADER`` followed by its separator line, a README
            under another header among them.
    """
    lines = text.split("\n")
    for index, line in enumerate(lines[:-1]):
        if line == HEADER and lines[index + 1].startswith("| --- |"):
            return index
    raise SystemExit(f"{readme} has no provenance table headed {HEADER!r}; nothing was written")


def _provenance(text: str, lists: Sequence[Listed], packaged: Mapping[str, PackagedList]) -> str:
    """``text``, a ``reference/README.md``, with the provenance rows of ``lists`` rewritten.

    Each row is ``| `<name>.json` | <origin> | <fetched> |``, ``fetched`` in UTC to the
    second with ``Z``, and no row counts its file's records, since the one header has no
    column for it. A list's row is rewritten where it stands; a row of a file no list
    declares, such as one a hook writes, is kept; a row that names no file, the template's
    ``(none yet)``, is dropped; and a list without a row gets one after the others, in the
    declared order. The text around the table is kept.

    Args:
        text: The README as it stands.
        lists: The declared lists.
        packaged: Every declared list by name, as written.

    Raises:
        SystemExit: The README holds no provenance table, or an origin would break its row.
    """
    start = _table(text, Path("reference", README))
    rows: dict[str, str] = {}
    for listed in lists:
        written = packaged[listed.name]
        cells = [f"`{listed.name}.json`", _origin(listed, written)]
        cells.append(f"{written.fetched.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}")
        rows[f"{listed.name}.json"] = f"| {' | '.join(cells)} |"
    lines = text.split("\n")
    end = start + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    table: list[str] = []
    for line in lines[start + 2 : end]:
        row = _ROW.match(line)
        if row is None:
            continue
        table.append(rows.pop(row["file"], line))
    table.extend(rows.values())
    return "\n".join([*lines[: start + 2], *table, *lines[end:]])


def _enums(lists: Sequence[Listed], packaged: Mapping[str, PackagedList]) -> tuple[str, int] | None:
    """``enums.py`` as ``render_enums`` writes it from the packaged lists, and its enums.

    ``None`` where no list declares an enum, so that ``enums.py`` is left alone.

    A ``StrEnum`` reads the field its file's ``param`` names and is keyed by the list's name,
    an ``IntEnum`` reads its ids and names and is keyed by ``ids``.

    Raises:
        SystemExit: A record lacks the field an enum reads its values from.
        ValueError: ``render_enums`` or ``id_name_pairs`` refuses a list, as they say.
    """
    declared = [listed for listed in lists if listed.enum is not None]
    if not declared:
        return None
    items: dict[str, Sequence[str] | Sequence[tuple[int, str]]] = {}
    fetched: dict[str, str] = {}
    class_names: dict[str, str] = {}
    member_names: dict[str, Mapping[Any, str]] = {}
    for listed in declared:
        enum = listed.enum
        if enum is None:
            continue
        written = packaged[listed.name]
        found: Sequence[str] | Sequence[tuple[int, str]]
        if enum.ids is not None and enum.names is not None:
            key = enum.ids
            found = id_name_pairs(written.records, id_field=enum.ids, name_field=enum.names)
        else:
            key = listed.name
            field = written.param
            missing = [index for index, record in enumerate(written.records) if field not in record]
            if missing:
                raise SystemExit(f"{listed.name}.json: record {missing[0]} has no field {field!r}")
            found = [record[field] for record in written.records]
        items[key] = found
        fetched[key] = f"{written.fetched.astimezone(UTC):%Y-%m-%d}"
        if enum.class_name is not None:
            class_names[key] = enum.class_name
        if enum.member_names is not None:
            given = enum.member_names
            member_names[key] = given if isinstance(given, Mapping) else given(found)
    module = render_enums(
        items,
        fetched=fetched,
        class_names=class_names,
        member_names=member_names,
        generator=GENERATOR,
    )
    return module, len(items)


def _read(reference: Path, name: str, why: str) -> PackagedList:
    """The packaged ``reference/<name>.json`` as written.

    Raises:
        SystemExit: The file is not packaged yet, naming the run that writes it.
    """
    path = reference / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"{path.name} is not packaged yet: {why}")
    return PackagedList.model_validate_json(path.read_text(encoding="utf-8"))


async def _awaited(answer: Awaitable[Fetched]) -> Fetched:
    return await answer


def _fetched(listed: Listed) -> PackagedList:
    """Fetch ``listed`` and make its packaged list, stamped now unless the fetch built it.

    Raises:
        SystemExit: A finished list that disagrees with the declaration, records with no
            endpoint, an item that is no record, a plain value among them, or an answer
            that is neither records nor a finished list.
    """
    answer = listed.fetch()
    if inspect.isawaitable(answer):
        answer = _run_coroutine(_awaited(answer))
    if isinstance(answer, PackagedList):
        for field, declared in (("endpoint", listed.endpoint), ("param", listed.param)):
            if declared is not None and getattr(answer, field) != declared:
                raise SystemExit(
                    f"{listed.name}'s fetch built a list of {field} {getattr(answer, field)!r}, "
                    f"declared {declared!r}; nothing was written"
                )
        return answer.model_copy(update={"fetched": answer.fetched.replace(microsecond=0)})
    fetched = datetime.now(UTC).replace(microsecond=0)
    given = cast(object, answer)  # a fetch that mypy does not check
    if isinstance(given, str | bytes) or not isinstance(given, Sequence):
        raise SystemExit(
            f"{listed.name}'s fetch answered a {type(given).__name__}: it answers records "
            "or a PackagedList; nothing was written"
        )
    if listed.endpoint is None:
        raise SystemExit(
            f"{listed.name}'s fetch answers records: name its endpoint, the upstream "
            "operation, in its Listed; nothing was written"
        )
    records: list[dict[str, Any]] = []
    for index, item in enumerate(given):
        if isinstance(item, UpstreamModel):
            records.append(item.dump_upstream())
        elif isinstance(item, Mapping):
            records.append(dict(item))
        else:
            raise SystemExit(
                f"{listed.name}'s fetch answered {_described(item)} at position {index}: a "
                "fetch answers records, a model or a mapping each, or a PackagedList, and "
                "makes a list of values records of one field named by its param; nothing "
                "was written"
            )
    param = listed.param or listed.name
    return PackagedList(param=param, endpoint=listed.endpoint, fetched=fetched, records=records)


def _formatted(source: str, path: Path) -> str:
    """``source`` as ``ruff format`` and then ``ruff check --fix`` leave it, as it is committed.

    Both read the source from standard input under ``--stdin-filename``, so they take the
    configuration the repository gives ``path``, and nothing is written.

    Raises:
        SystemExit: ruff leaves the module failing, its messages printed before.
    """
    for command in (["format"], ["check", "--fix"]):
        done = subprocess.run(
            [sys.executable, "-m", "ruff", *command, "--stdin-filename", str(path), "-"],
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode:
            sys.stderr.write(done.stderr)
            raise SystemExit(
                f"ruff {' '.join(command)} left {path.name} failing; nothing was written"
            )
        source = done.stdout
    return source


def _staged(written: Mapping[str, PackagedList]) -> dict[str, bytes]:
    """Each list's file as ``PackagedList.write`` writes it, by name, before the first write.

    The files are made in a temporary directory outside the repository and read back, so
    that the run writes them with the rest, at once.
    """
    files: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="xippios-refresh-") as staging:
        for name, packaged in written.items():
            path = Path(staging, f"{name}.json")
            packaged.write(path)
            files[name] = path.read_bytes()
    return files


def _commit(files: Mapping[Path, bytes]) -> None:
    """Write ``files`` as one: a write that fails puts back each file written before it.

    A file the run replaced gets its bytes back and one it made is removed, then the error
    is raised, an interrupt's too.
    """
    previous: dict[Path, bytes | None] = {}
    try:
        for path, content in files.items():
            previous[path] = path.read_bytes() if path.is_file() else None
            path.write_bytes(content)
    except BaseException:
        for path, old in previous.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(old)
        raise


def _refresh(declaration: Lists, argv: Sequence[str] | None) -> int:
    """The reference frame's run: ``run`` with a ``Lists``."""
    lists = declaration.lists
    _check(lists, declaration.packaged)
    names = [listed.name for listed in lists]
    parser = argparse.ArgumentParser(
        description=f"Refresh the packaged reference data of {declaration.package} from upstream."
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument(
        "--render-only",
        action="store_true",
        help="write enums.py and the provenance rows from the packaged files, no request or key",
    )
    choice.add_argument(
        "--only",
        nargs="+",
        default=[],
        metavar="LIST",
        help=f"fetch these lists alone and keep every other list's file: {', '.join(names)}",
    )
    args = parser.parse_args(argv)
    only: list[str] = args.only
    directory = _directory(declaration.package)
    reference = directory / "reference"
    readme = reference / README
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    _table(text, readme)
    if args.render_only:
        chosen: set[str] = set()
    else:
        if unknown := [name for name in only if name not in names]:
            raise SystemExit(f"--only: no list {', '.join(unknown)} in {', '.join(names)}")
        chosen = set(only or names)
    kept = [name for name in names if name not in chosen]
    why = (
        "run the script without --render-only"
        if args.render_only
        else "run the script without --only"
    )
    if missing := [name for name in kept if not (reference / f"{name}.json").is_file()]:
        absent = ", ".join(f"{name}.json" for name in missing)
        raise SystemExit(f"{absent} is not packaged yet: {why}")
    written: dict[str, PackagedList] = {}
    if chosen:
        if declaration.before is not None:
            declaration.before()
        with _metered(declaration.client, declaration.quota_header):
            for listed in lists:
                if listed.name in chosen:
                    written[listed.name] = _fetched(listed)
    packaged = {
        listed.name: written[listed.name]
        if listed.name in written
        else _read(reference, listed.name, why)
        for listed in lists
    }
    rows = _provenance(text, lists, packaged)
    module = _enums(lists, packaged)
    enums = directory / "enums.py"
    files = {reference / f"{name}.json": content for name, content in _staged(written).items()}
    files[readme] = rows.encode("utf-8")
    if module is not None:
        files[enums] = _formatted(module[0], enums).encode("utf-8")
    _commit(files)
    for name, fetched in written.items():
        print(f"{name}.json: {len(fetched.records)} records from {fetched.endpoint}")  # noqa: T201
    print(f"{README}: the rows of {len(lists)} lists in its provenance table")  # noqa: T201
    if module is None:
        print(f"{enums.name}: left alone, no list declares an enum")  # noqa: T201
    else:
        print(f"{enums.name}: {module[1]} enums")  # noqa: T201
    if chosen and declaration.after is not None:
        try:
            declaration.after(written)
        except BaseException as error:
            print(f"after raised {type(error).__name__}: the files above stand written")  # noqa: T201
            raise
    return 0


def run(declaration: Snapshot | Lists, argv: Sequence[str] | None = None) -> int:
    """Run a source's refresh script on its declaration, a ``Snapshot`` or a ``Lists``.

    The one entry of both frames (ADR-0062, decision 2). ``run(SNAPSHOT)`` is the snapshot
    frame's run, and ``run(LISTS)`` the reference frame's: it fetches every list of
    ``LISTS.lists`` through ``LISTS.client``, then writes each to ``reference/<name>.json``,
    the provenance rows of ``reference/README.md`` and ``enums.py`` as one, each file made,
    ``enums.py`` formatted by ruff, before the first is written, and a write that fails puts
    back what it replaced. The reference frame's command line takes ``--only LIST [LIST
    ...]``, which fetches those lists alone and keeps every other list's file, or
    ``--render-only``, which writes the rows and ``enums.py`` from the packaged files without
    a request.

    Args:
        declaration: The script's declaration: its ``Snapshot``, or its ``Lists``.
        argv: The command line's arguments, ``sys.argv[1:]`` by default.

    Returns:
        The exit status. The reference frame's is 0: a fetch's error, an upstream error
        among them, is raised as it is, after the requests sent are printed, and nothing is
        written. The snapshot frame's is 1 where ``--check`` or ``--keyless`` finds a
        difference.

    Raises:
        SystemExit: What is neither declaration, before anything is read; for the lists, a
            declaration the frame cannot run, lists other than ``packaged``, a list
            ``--only`` does not know, a packaged file missing, or a README without its
            provenance table, each before the first request; a fetch's answer that does
            not fit its declaration, or a module ruff leaves failing, before the first
            write.
    """
    given = cast(object, declaration)  # a script that mypy does not check
    if isinstance(given, Lists):
        return _refresh(given, argv)
    if isinstance(given, Snapshot):
        return _run_snapshot(given, argv)
    raise SystemExit(
        f"run takes one declaration, a Snapshot or a Lists, not a {type(given).__name__}: "
        "declare the lists in Lists(package, lists, packaged, client) and hand run that. "
        "Nothing was fetched or written."
    )


# --- enums.py: the renderer, which the frame alone calls (ADR-0062, decision 13) ----------

_LINE_LENGTH = 100
"""The family's ``line-length``; a longer generated line carries ``# noqa: E501``."""


def enum_member_name(value: str) -> str:
    """An identifier for an enum member: ``"ANIMALS & PRODUCTS"`` → ``ANIMALS_AND_PRODUCTS``.

    Upper case, ``&`` read as ``AND``, every other run of non-alphanumerics folded to one
    underscore, a leading digit prefixed with an underscore.
    """
    name = re.sub(r"[^A-Z0-9]+", "_", value.upper().replace("&", " AND ")).strip("_")
    if not name:
        raise ValueError(f"no identifier can be made from {value!r}")
    return f"_{name}" if name[0].isdigit() else name


def id_name_pairs(
    records: Iterable[Mapping[str, Any]], *, id_field: str, name_field: str
) -> list[tuple[int, str]]:
    """``(id, name)`` pairs from upstream's records, in upstream order, for ``render_enums``.

    Args:
        records: Upstream's records under upstream's field names, e.g. the
            ``regionAttributes`` of an answer.
        id_field: The field holding the integer id, e.g. ``"seriesId"``; an ``int`` or
            a string of ASCII digits without leading zeros (``"28"``, not ``"007"``).
        name_field: The field holding the name, a string, e.g. ``"attributeName"``.

    Raises:
        ValueError: When a record lacks a field, its id is not an integer or has leading
            zeros that ``int`` would drop, or its name is not a string. The message names
            the field and the record's position, never the record.
    """
    pairs: list[tuple[int, str]] = []
    for index, record in enumerate(records):
        for field in (id_field, name_field):
            if field not in record:
                raise ValueError(f"record {index} has no field {field!r}")
        ident, name = record[id_field], record[name_field]
        if isinstance(ident, str) and ident.isascii() and ident.isdigit():
            if len(ident) > 1 and ident.startswith("0"):
                raise ValueError(
                    f"record {index}: field {id_field!r} has leading zeros an integer id would lose"
                )
            ident = int(ident)
        if not isinstance(ident, int) or isinstance(ident, bool):
            raise ValueError(f"record {index}: field {id_field!r} is not an integer id")
        if not isinstance(name, str):
            raise ValueError(f"record {index}: field {name_field!r} is not a string")
        pairs.append((ident, name))
    return pairs


_TEXT_RULE = "non-empty printable ASCII without a backslash or three double quotes"

_BASES = frozenset({"IntEnum", "StrEnum"})
"""The names the generated module imports, which no class of it may take."""

_CLASS_NAME_LIMIT = _LINE_LENGTH - len("class (StrEnum):")
"""84: the longest class name whose ``class`` line fits; ``ruff format`` cannot shorten one."""


def _plain_text(text: str) -> bool:
    """Whether ``text`` fits a generated docstring as it is: ``_TEXT_RULE``."""
    return (
        bool(text)
        and text.isascii()
        and text.isprintable()
        and "\\" not in text
        and '"""' not in text
    )


_AMBIGUOUS = frozenset({"I", "O", "l"})
"""Names ruff flags as ambiguous (E741) and cannot fix: a member upstream's ``"I"`` names."""


def _fit(line: str, *codes: str) -> str:
    """``line`` with a ``# noqa`` for ``codes``, and for E501 when it is over 100 columns.

    No tool can shorten an upstream value, a long key or a member name derived from a long
    label, nor rename a member upstream's value names ``I`` or ``O`` (E741), so such a line
    is exempted, not refused; ruff drops a code again where ``ruff format`` makes the line
    fit (RUF100).
    """
    exempt = ("E501",) * (len(line) > _LINE_LENGTH) + codes
    return f"{line}  # noqa: {', '.join(exempt)}" if exempt else line


_HUMP = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
"""Where a camelCase part starts a word: before an upper-case letter after a lower-case
letter or a digit."""


def _class_name(key: str) -> str:
    """The default class name: each word of ``key`` capitalized, a camelCase hump kept.

    ``seriesId`` → ``SeriesId``, ``unit2Code`` → ``Unit2Code``, ``region_code``
    and ``REGION_CODE`` → ``RegionCode``: a key splits into parts at each run of characters
    that are no ASCII letters or digits, a part that holds a lower-case letter splits again
    before each hump, and every word is capitalized. A part in upper case alone has no hump
    (``STATE2ALPHA`` → ``State2alpha``), nor has an upper-case run (``HSCode`` →
    ``Hscode``): such a key keeps the name it had before humps were kept.
    """
    words: list[str] = []
    for part in re.split(r"[^A-Za-z0-9]+", key):
        words += _HUMP.split(part) if re.search(r"[a-z]", part) else [part]
    return "".join(word.capitalize() for word in words if word)


def _unknown_keys(argument: str, given: Mapping[str, object], lists: Mapping[str, object]) -> None:
    unknown = sorted(set(given) - set(lists))
    if unknown:
        raise ValueError(f"{argument} names lists that are not rendered: {unknown}")


def _class_names(lists: Mapping[str, object], class_names: Mapping[str, str]) -> dict[str, str]:
    """The class name per key, once every key is known to fit a docstring.

    Raises:
        ValueError: A key is not ``_TEXT_RULE``; a class name is no ASCII identifier, is a
            keyword or one of ``_BASES``, which the module could not execute with, or is
            longer than ``_CLASS_NAME_LIMIT``; two keys get one class name. The message
            names the position.
    """
    names: dict[str, str] = {}
    for index, key in enumerate(lists):
        if not _plain_text(key):
            raise ValueError(f"the key at position {index} of lists must be {_TEXT_RULE}")
        given = class_names.get(key)
        name = _class_name(key) if given is None else given
        too_long = len(name) > _CLASS_NAME_LIMIT
        refused = keyword.iskeyword(name) or name in _BASES or too_long
        if not (name.isascii() and name.isidentifier()) or refused:
            where = (
                f"the class name derived from the key at position {index} of lists"
                if given is None
                else f"class_names for the key at position {index} of lists"
            )
            raise ValueError(
                f"{where} must be an ASCII identifier, not a keyword, IntEnum or StrEnum, of "
                f"at most {_CLASS_NAME_LIMIT} characters; set it in class_names"
            )
        names[key] = name
    positions: dict[str, list[int]] = {}
    for index, name in enumerate(names.values()):
        positions.setdefault(name, []).append(index)
    shared = [
        f"{name!r} at positions {', '.join(map(str, where))}"
        for name, where in positions.items()
        if len(where) > 1
    ]
    if shared:
        raise ValueError(f"class names collide: {'; '.join(shared)}; set them in class_names")
    return names


def _dates(lists: Mapping[str, object], fetched: str | Mapping[str, str]) -> dict[str, str]:
    """The fetch date per key: ``fetched`` for every list, or each list's own.

    Raises:
        ValueError: A date is not ``_TEXT_RULE``, or a mapping lacks a key of ``lists``
            or names one it does not hold.
    """
    if isinstance(fetched, str):
        if not _plain_text(fetched):
            raise ValueError(f"fetched must be {_TEXT_RULE}")
        return dict.fromkeys(lists, fetched)
    _unknown_keys("fetched", fetched, lists)
    dates: dict[str, str] = {}
    for index, key in enumerate(lists):
        if key not in fetched:
            raise ValueError(f"fetched has no date for the key at position {index} of lists")
        if not _plain_text(fetched[key]):
            raise ValueError(
                f"fetched for the key at position {index} of lists must be {_TEXT_RULE}"
            )
        dates[key] = fetched[key]
    return dates


def _is_pair(item: object) -> bool:
    return (
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], int)
        and not isinstance(item[0], bool)
        and isinstance(item[1], str)
    )


def _kind(key: str, values: object) -> str:
    """``"StrEnum"`` for a list of strings, ``"IntEnum"`` for a list of ``(id, name)`` pairs.

    Raises:
        ValueError: ``values`` is a string or empty, or is neither all strings nor all
            pairs of an ``int`` and a ``str``; the message names what it found, by type.
    """
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise ValueError(
            f"{key}: a list of values or of (id, name) pairs is needed, not {_described(values)}"
        )
    if not values:
        raise ValueError(f"{key}: the list is empty; an enum needs at least one value")
    if all(isinstance(item, str) for item in values):
        return "StrEnum"
    if all(_is_pair(item) for item in values):
        return "IntEnum"
    if isinstance(values[0], str) or _is_pair(values[0]):
        fits = _is_pair if _is_pair(values[0]) else (lambda item: isinstance(item, str))
        position = next(index for index, item in enumerate(values) if not fits(item))
        found = (
            f"item 0 is {_described(values[0])} and item {position} {_described(values[position])}"
        )
    else:
        found = f"item 0 is {_described(values[0])}"
    raise ValueError(
        f"{key}: a list holds strings (a StrEnum) or (id, name) pairs of an int and a str (an "
        f"IntEnum), as id_name_pairs builds them; {found}"
    )


def _described(item: object) -> str:
    """What ``item`` is, by type, never by value: ``"a str"``, ``"a tuple of int, str"``."""
    if _is_pair(item):
        return "an (id, name) pair"
    if isinstance(item, tuple):
        return f"a tuple of {', '.join(type(part).__name__ for part in item) or 'nothing'}"
    name = type(item).__name__
    return f"{'an' if name[:1] in 'aeiou' else 'a'} {name}"


def _derived(text: str) -> str | None:
    """``enum_member_name(text)``, or ``None`` when ``text`` has nothing to derive it from."""
    try:
        return enum_member_name(text)
    except ValueError:
        return None


def _acceptable(member: str) -> bool:
    """Whether ``member`` is an ASCII identifier that an enum takes as a member.

    An enum refuses ``mro`` and ``_sunder_`` names and makes no member of a name with a
    double underscore in it, a ``__dunder__`` or a class-private ``_Class__name``; a
    keyword is no identifier to assign to. A derived name never holds ``__``.
    """
    sunder = len(member) > 2 and member[0] == member[-1] == "_"
    return (
        member.isascii()
        and member.isidentifier()
        and not keyword.iskeyword(member)
        and "__" not in member
        and not sunder
        and member != "mro"
    )


def _member_names[T](
    key: str,
    items: Sequence[T],
    derived: Sequence[str | None],
    labels: Sequence[str],
    overrides: Mapping[T, str],
) -> list[str]:
    """Member names for ``items``: each item's override, else its derived name.

    An override is taken before any name is derived, so a value with nothing to derive a
    name from (``None`` in ``derived``) can be named by hand. ``labels`` describe the
    items in messages.

    Raises:
        ValueError: When an override names an item the list does not hold, an item has
            neither a derived name nor an override, a name is no identifier an enum
            accepts, or two names collide.
    """
    held = set(items)
    unknown = [item for item in overrides if item not in held]
    if unknown:
        raise ValueError(f"{key}: member_names names what the list does not hold: {unknown}")
    hint = f"name it by hand in member_names={{{key!r}: {{...}}}}"
    members: list[str] = []
    for index, (item, name, label) in enumerate(zip(items, derived, labels, strict=True)):
        if item in overrides:
            members.append(overrides[item])
        elif name is None:
            raise ValueError(
                f"{key}: no member name can be derived from {label} at position {index}; {hint}"
            )
        else:
            members.append(name)
    for index, (member, label) in enumerate(zip(members, labels, strict=True)):
        if not _acceptable(member):
            raise ValueError(
                f"{key}: {member!r} for {label} at position {index} is not a member name an "
                "enum accepts"
            )
    positions: dict[str, list[int]] = {}
    for index, member in enumerate(members):
        positions.setdefault(member, []).append(index)
    colliding = [
        f"{member!r} at positions {', '.join(map(str, where))}"
        for member, where in sorted(positions.items())
        if len(where) > 1
    ]
    if colliding:
        raise ValueError(f"{key}: member names collide: {'; '.join(colliding)}")
    return members


def _str_members(
    key: str, values: Sequence[str], overrides: Mapping[str, str]
) -> list[tuple[str, str]]:
    """``(member, literal)`` per value, the value written as ``ascii()`` writes it."""
    derived = [_derived(value) for value in values]
    labels = [repr(value) for value in values]
    members = _member_names(key, values, derived, labels, overrides)
    return [(member, ascii(value)) for member, value in zip(members, values, strict=True)]


def _int_members(
    key: str, pairs: Sequence[tuple[int, str]], overrides: Mapping[int, str]
) -> list[tuple[str, str]]:
    """``(member, literal)`` per pair: names from the names, ``_<id>`` where one repeats.

    Raises:
        ValueError: An id is listed twice, naming the key and the ids.
    """
    repeated = sorted(ident for ident, count in Counter(i for i, _ in pairs).items() if count > 1)
    if repeated:
        raise ValueError(f"{key}: ids listed more than once: {repeated}")
    plain = [_derived(name) for _, name in pairs]
    counts = Counter(name for name in plain if name is not None)
    derived = [
        name if name is None or counts[name] == 1 else f"{name}_{ident}"
        for name, (ident, _) in zip(plain, pairs, strict=True)
    ]
    ids = [ident for ident, _ in pairs]
    labels = [f"{name!r} (id {ident})" for ident, name in pairs]
    members = _member_names(key, ids, derived, labels, overrides)
    return [(member, f"{ident:d}") for member, ident in zip(members, ids, strict=True)]


def render_enums(
    lists: Mapping[str, Sequence[str] | Sequence[tuple[int, str]]],
    *,
    fetched: str | Mapping[str, str],
    class_names: Mapping[str, str] | None = None,
    member_names: Mapping[str, Mapping[Any, str]] | None = None,
    generator: str = "the reference refresh script",
) -> str:
    r"""Python source for a source's ``enums.py``: one enum per packaged list (conventions §3).

    The kind is inferred per list, so one module holds both: a list of strings renders a
    ``StrEnum`` whose members are the upstream strings, verbatim; a list of ``(id, name)``
    pairs, as ``id_name_pairs`` builds them, renders an ``IntEnum`` whose members are the
    ids, so a member compares equal to the id in upstream's data, with ``_<id>`` appended
    to a name several ids share (``TOTAL_DISAPPEARANCE_126``). Member names come from
    ``enum_member_name``, or from ``member_names`` where a source names one by hand. Each
    class's docstring is one line, ``Values of ``<key>`` (fetched <date>).``, which an MCP
    tool's input schema shows an agent (conventions §8).

    The output is plain and ASCII-only (ADR-0031): a value is written as ``ascii()``
    writes it, so a quote, a backslash, a control character and every character outside
    ASCII is escaped (``"Côte"`` as ``'C\xf4te'``) and the value is the same at runtime;
    one member per line; ``__all__`` one name per line in the order of ``lists``; the
    import names the kinds the module needs. A line longer than 100 columns carries
    ``# noqa: E501``, and a member named ``I``, ``O`` or ``l``, which ruff flags as
    ambiguous with no fix, ``# noqa: E741``. The refresh script runs ``ruff format`` and
    ``ruff check --fix`` on the result, which choose the quotes, wrap what fits and sort
    ``__all__`` (RUF022); the module is committed as formatted.

    Args:
        lists: Enum key to its values in upstream order: strings
            (``{"region_code": ["R01", "R02"]}``) or ``(id, name)`` pairs
            (``{"seriesId": [(4, "Rainfall"), (20, "Temperature")]}``).
        fetched: When the lists were fetched, as text: one date for the module
            (``"2026-10-27"``), or one per key (``{"region_code": "2026-10-27",
            "seriesId": "2026-10-23"}``) for lists fetched on different days.
        class_names: Class name per key, e.g. ``{"regions": "Region"}``;
            by default each word of the key capitalized, a camelCase hump kept:
            ``RegionCode`` for ``region_code`` and ``SeriesId`` for ``seriesId``.
        member_names: Member names set by hand, per key and value (an id for an
            ``IntEnum``), for a value whose derived name collides or that has none (an
            empty or a non-Latin label), e.g. ``{"series_name": {"RAINFALL, MONTHLY": "RAINFALL"}}``
            or ``{"seriesId": {173: "TOTAL"}}``. Taken before any name is derived;
            each must be an identifier an enum accepts and unique in its list.
        generator: What the module docstring names as its generator, e.g.
            ``"scripts/refresh_reference.py"``.

    Raises:
        ValueError: A list is empty, a string, or mixes strings and pairs; ``generator``,
            a date or a key is not non-empty printable ASCII or holds a backslash or three
            double quotes; a class name is no ASCII identifier, is a keyword, ``IntEnum``
            or ``StrEnum``, is longer than 84 characters, or two lists get one; an id is
            listed twice; a value without an override has nothing to derive a member name
            from; two members of one list share a name; a name in ``member_names`` is not
            one an enum takes (``mro``, ``_x_``, any with ``__``); or ``fetched``,
            ``class_names`` or ``member_names`` names a key ``lists`` does not hold,
            ``fetched`` lacks one, or ``member_names`` names a value or an id its list does
            not hold. A message names the argument and the position, a list's items by
            type.
    """
    if not _plain_text(generator):
        raise ValueError(f"generator must be {_TEXT_RULE}")
    _unknown_keys("class_names", class_names or {}, lists)
    _unknown_keys("member_names", member_names or {}, lists)
    names = _class_names(lists, class_names or {})
    dates = _dates(lists, fetched)
    kinds: set[str] = set()
    classes: list[list[str]] = []
    for key, values in lists.items():
        kind = _kind(key, values)
        overrides = (member_names or {}).get(key, {})
        members = (
            _str_members(key, cast(Sequence[str], values), overrides)
            if kind == "StrEnum"
            else _int_members(key, cast(Sequence[tuple[int, str]], values), overrides)
        )
        kinds.add(kind)
        classes.append(
            [
                f"class {names[key]}({kind}):",
                _fit(f'    """Values of ``{key}`` (fetched {dates[key]})."""'),
                "",
                *(
                    _fit(f"    {member} = {literal}", *("E741",) * (member in _AMBIGUOUS))
                    for member, literal in members
                ),
            ]
        )
    lines = [
        _fit(f'"""Enums of the packaged lists, generated by {generator}; do not edit by hand."""'),
        "",
    ]
    if kinds:
        lines += [f"from enum import {', '.join(sorted(kinds))}", ""]
    if names:
        lines += ["__all__ = [", *(f'    "{name}",' for name in names.values()), "]"]
    else:
        lines.append("__all__ = []")
    for body in classes:
        lines += ["", "", *body]
    return "\n".join(lines) + "\n"
