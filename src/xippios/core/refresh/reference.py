"""The frame of a source's reference refresh script, ``scripts/refresh_reference.py`` (ADR-0051).

A source's script declares one ``Listed`` per packaged list, with the fetch that gets it
through the source's ``api/`` wrappers, its enum, if any, and its origin, and runs them; the
frame does the rest, the same in every source::

    LISTS = (Listed("commodities", api.get_commodities, endpoint="GetCommodities"),)

    if __name__ == "__main__":
        raise SystemExit(
            run(LISTS, package="xippios.example", packaged=PACKAGED_LISTS, client=client)
        )

The lists must be those the package declares it ships, ``packaged``, its
``params.PACKAGED_LISTS``. Every list is fetched before anything is written, through
``client`` with one attempt per request, each counted, so a 5xx or a 429 spends no second
call of upstream's quota; the requests sent and the quota left are printed after the
fetches, a failed run's too. A fetch answers values, records or a finished
``PackagedList``. Then each list is written to
``reference/<name>.json`` by ``PackagedList.write``, the rows of the provenance table of
``reference/README.md`` are rewritten in place under the header the README has, and
``enums.py`` is rendered by one ``render_enums`` call in the order the lists are declared,
then formatted with ``ruff format`` and ``ruff check --fix``; where no list declares an
enum, ``enums.py`` is left alone. Every file is made, the module formatted, before the first
is written, and they are written as one: a write that fails puts back what the run
replaced, so a run that fails writes nothing and is run again.

``--only`` fetches the lists it names and keeps every other list's file. ``--render-only``
writes the provenance rows and ``enums.py`` from the packaged files alone, without a request
or a key. A hook before the first request and one after the last write carry what a script
writes beside the lists.
"""

import argparse
import importlib.util
import inspect
import re
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, overload

import httpx

from xippios.core._loop import run as _run_coroutine
from xippios.core.client import AsyncClient, RetryPolicy
from xippios.core.errors import TransportError
from xippios.core.models import UpstreamModel
from xippios.core.reference import PackagedList, id_name_pairs, render_enums
from xippios.core.refresh.upstream import Snapshot
from xippios.core.refresh.upstream import run as _run_snapshot

COMMAND = "uv run python scripts/refresh_reference.py"
"""How a source runs its reference refresh script, from its repository's root."""
GENERATOR = "scripts/refresh_reference.py"
"""What the docstring of the generated ``enums.py`` names as its generator."""
README = "README.md"
"""The file under ``reference/`` that holds the provenance table, one row per file."""
HEADERS = {
    "| File | Origin | Fetched |": False,
    "| File | Origin | Fetched (UTC) | Records |": True,
}
"""The provenance table's two headers, each to whether its rows count the file's records:
the one the template renders, and the FAS sources' with ``Records``."""

type Fetched = PackagedList | Sequence[Any]
"""What a list's fetch answers: values, records or a finished ``PackagedList``."""
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

    Attributes:
        values: The field each value is read from, for a ``StrEnum``: the packaged file's
            ``param`` by default, the one field of a list of values.
        ids: The field of each integer id, for an ``IntEnum`` of ``(id, name)`` pairs,
            e.g. ``"unitId"``; given with ``names``.
        names: The field of each id's name, e.g. ``"unitDescription"``.
        key: The enum's key, which its docstring names and its class takes its name from:
            the list's name for a ``StrEnum``, ``ids`` for an ``IntEnum``.
        class_name: The class's name where core's default from ``key`` will not do, e.g.
            ``"ProgressStage"`` for ``progress_stages``.
        member_names: Members named by hand, per value or per id, where a derived name
            collides or there is none: a mapping, or a function of the list's values or
            pairs that returns one, for a rule that names many (``render_enums``).
    """

    values: str | None = None
    ids: str | None = None
    names: str | None = None
    key: str | None = None
    class_name: str | None = None
    member_names: MemberNames | None = None


@dataclass(frozen=True)
class Listed:
    """One packaged list, ``reference/<name>.json``, and how the frame gets it.

    Attributes:
        name: The list's name, its file under ``reference/`` without ``.json`` and the name
            ``--only`` takes, e.g. ``"commodities"`` or ``"element_QCL"``.
        fetch: Gets the list through the source's ``api/`` wrappers, never through a task
            that answers from the package: values, which become records of one field
            named by ``param``; records, a model's by ``dump_upstream`` and a mapping as
            it is; or a finished ``PackagedList``, written as built. Values and records
            are fetched when the fetch returns; a finished list carries its own
            ``fetched``, such as the wrapper's ``retrieved_at`` or the time of its first
            request.
        endpoint: The upstream operation the list comes from, the file's ``endpoint``:
            needed for values and records, and where given, a finished list's must match.
        param: The upstream parameter the list feeds, the file's ``param``: ``name`` by
            default for values and records, and where given, a finished list's must match.
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
            enum of ids without the field of their names, two enums of one key, or lists
            other than those the package declares it ships, ``packaged``.
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
            raise SystemExit(f"run takes one Listed per list, not {type(listed).__name__}")
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
        if (enum.ids is None) != (enum.names is None) or (enum.ids and enum.values):
            raise SystemExit(
                f"{listed.name}: an Enumeration of ids names the field of their names too, "
                "and one of values names neither"
            )
        key = enum.key or enum.ids or listed.name
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


def _table(text: str, readme: Path) -> tuple[int, bool]:
    """Where the provenance table's header stands in ``text``, and whether it counts records.

    Raises:
        SystemExit: ``text`` holds neither header followed by its separator line.
    """
    lines = text.split("\n")
    for index, line in enumerate(lines[:-1]):
        if line in HEADERS and lines[index + 1].startswith("| --- |"):
            return index, HEADERS[line]
    headers = " or ".join(repr(header) for header in HEADERS)
    raise SystemExit(f"{readme} has no provenance table headed {headers}; nothing was written")


def _provenance(text: str, lists: Sequence[Listed], packaged: Mapping[str, PackagedList]) -> str:
    """``text``, a ``reference/README.md``, with the provenance rows of ``lists`` rewritten.

    Each row is ``| `<name>.json` | <origin> | <fetched> |``, with the count of records after
    ``fetched`` under the header with ``Records``, ``fetched`` in UTC to the second with ``Z``.
    A list's row is rewritten where it stands; a row of a file no list declares, such as one
    a hook writes, is kept; a row that names no file, the template's ``(none yet)``, is
    dropped; and a list without a row gets one after the others, in the declared order. The
    text around the table is kept.

    Args:
        text: The README as it stands.
        lists: The declared lists.
        packaged: Every declared list by name, as written.

    Raises:
        SystemExit: The README holds no provenance table, or an origin would break its row.
    """
    start, counted = _table(text, Path("reference", README))
    rows: dict[str, str] = {}
    for listed in lists:
        written = packaged[listed.name]
        cells = [f"`{listed.name}.json`", _origin(listed, written)]
        cells.append(f"{written.fetched.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}")
        if counted:
            cells.append(f"{len(written.records):,}")
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
            key = enum.key or enum.ids
            found = id_name_pairs(written.records, id_field=enum.ids, name_field=enum.names)
        else:
            key = enum.key or listed.name
            field = enum.values or written.param
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
        SystemExit: A finished list that disagrees with the declaration, values or records
            with no endpoint, or an answer that is neither.
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
    if isinstance(answer, str | bytes) or not isinstance(answer, Sequence):
        raise SystemExit(
            f"{listed.name}'s fetch answered a {type(answer).__name__}: it answers values, "
            "records or a PackagedList; nothing was written"
        )
    if listed.endpoint is None:
        raise SystemExit(
            f"{listed.name}'s fetch answers values or records: name its endpoint, the upstream "
            "operation, in its Listed; nothing was written"
        )
    param = listed.param or listed.name
    records = [
        item.dump_upstream()
        if isinstance(item, UpstreamModel)
        else dict(item)
        if isinstance(item, Mapping)
        else {param: item}
        for item in answer
    ]
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


def _refresh(
    lists: Sequence[Listed],
    argv: Sequence[str] | None,
    *,
    package: str,
    packaged: Collection[str],
    client: AsyncClient,
    quota_header: str | None,
    before: Callable[[], object] | None,
    after: Callable[[Mapping[str, PackagedList]], object] | None,
) -> int:
    """The reference frame's run: ``run`` with a sequence of ``Listed``."""
    _check(lists, packaged)
    names = [listed.name for listed in lists]
    parser = argparse.ArgumentParser(
        description=f"Refresh the packaged reference data of {package} from upstream."
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
    directory = _directory(package)
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
        if before is not None:
            before()
        with _metered(client, quota_header):
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
    if chosen and after is not None:
        try:
            after(written)
        except BaseException as error:
            print(f"after raised {type(error).__name__}: the files above stand written")  # noqa: T201
            raise
    return 0


@overload
def run(snapshot: Snapshot, argv: Sequence[str] | None = None) -> int: ...


@overload
def run(
    lists: Sequence[Listed],
    /,
    argv: Sequence[str] | None = None,
    *,
    package: str,
    packaged: Collection[str],
    client: AsyncClient,
    quota_header: str | None = None,
    before: Callable[[], object] | None = None,
    after: Callable[[Mapping[str, PackagedList]], object] | None = None,
) -> int: ...


def run(
    snapshot: Snapshot | Sequence[Listed],
    argv: Sequence[str] | None = None,
    *,
    package: str | None = None,
    packaged: Collection[str] | None = None,
    client: AsyncClient | None = None,
    quota_header: str | None = None,
    before: Callable[[], object] | None = None,
    after: Callable[[Mapping[str, PackagedList]], object] | None = None,
) -> int:
    """Run a source's refresh script: its ``Snapshot``, or its packaged lists (ADR-0051).

    ``run(snapshot)`` is the snapshot frame's run as it stands (ADR-0046), and
    ``run(lists, package=..., packaged=..., client=...)`` the reference frame's: it
    fetches every list of ``lists`` through ``client``, then writes each to
    ``reference/<name>.json``, the provenance rows of ``reference/README.md`` and
    ``enums.py`` as one, each file made, ``enums.py`` formatted by ruff, before the first
    is written, and a write that fails puts back what it replaced. The command line takes
    ``--only LIST [LIST ...]``, which fetches those lists alone and keeps every other
    list's file, or ``--render-only``, which writes the rows and ``enums.py`` from the
    packaged files without a request.

    Args:
        snapshot: The snapshot's declaration, or the lists, one ``Listed`` each, in the
            order of ``enums.py``.
        argv: The command line's arguments, ``sys.argv[1:]`` by default.
        package: The source's import path, e.g. ``"xippios.usda.psd"``: the frame writes
            into its directory, which must lie in the directory the script runs in.
        packaged: The names of the lists the package declares it ships, such as its
            ``params.PACKAGED_LISTS``: the lists must be exactly these, or the run stops
            before a request, naming those declared on one side alone.
        client: The client the fetches send through: one attempt per request for the
            run, each counted, its configuration restored after.
        quota_header: The response header in which upstream reports the requests left in
            its quota, e.g. ``"x-ratelimit-remaining"``, or ``None`` where it reports none.
        before: Called once before the first request, after the command line and the
            declaration are checked: what can stop the run before it spends a request,
            such as parsing a snapshot's table that a list beside the lists is made from.
        after: Called after the last write with the lists this run fetched, by name: what
            a script writes beside the lists, an index or a manifest. Neither hook is
            called by ``--render-only``. A hook that raises leaves the frame's files
            written, and the run says so before the error ends it.

    Returns:
        The exit status: 0. A fetch's error, an upstream error among them, is raised as it
        is, after the requests sent are printed, and nothing is written.

    Raises:
        SystemExit: A declaration the frame cannot run, lists other than ``packaged``, a
            list ``--only`` does not know, a packaged file missing, or a README without
            its provenance table, each before the first request; a fetch's answer that
            does not fit its declaration, or a module ruff leaves failing, before the
            first write.
        TypeError: A snapshot given the lists' arguments, or lists without their package,
            the lists it ships and their client.
    """
    if isinstance(snapshot, Snapshot):
        given = (package, packaged, client, quota_header, before, after)
        if any(argument is not None for argument in given):
            raise TypeError("a Snapshot takes argv alone: package, client and the hooks are lists'")
        return _run_snapshot(snapshot, argv)
    if package is None or packaged is None or client is None:
        raise TypeError("run(lists, ...) takes the lists' package, packaged and client by keyword")
    return _refresh(
        snapshot,
        argv,
        package=package,
        packaged=packaged,
        client=client,
        quota_header=quota_header,
        before=before,
        after=after,
    )
