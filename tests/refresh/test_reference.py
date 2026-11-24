"""The reference frame, ``xippios.core.refresh`` (ADR-0062): a source's lists declared in one
``Lists`` and run against answers served in memory.

The tests of sdk-template's script, ``tests/test_reference_data.py`` and the refresh's part of
``scripts/prove.sh`` there (#40, #64), moved here with the frame, one ``Listed`` per list in
place of the script's three dicts: each request sent once and counted, a failed run that
writes nothing, ``--only`` and ``--render-only`` as one choice, and a value list and an id list
rendered into one ``enums.py`` as ruff leaves it. The frame's own rules follow them: what a
fetch answers and when it was fetched, the provenance table under its one header,
``enums.py`` in the declared order, the hooks, and the one ``run`` of both frames, which takes
one declaration. respx answers every request, so nothing leaves the process.
"""

import dataclasses
import importlib
import inspect
import io
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import Field

from xippios.core import (
    Answer,
    AsyncClient,
    ClientConfig,
    PackagedList,
    RetryPolicy,
    TransportError,
    UpstreamModel,
    XippiosError,
)
from xippios.core.refresh import Enumeration, Listed, Lists, Snapshot, run

BASE = "https://api.example.org"
HEADER = "| File | Origin | Fetched |\n| --- | --- | --- |\n"
RECORDS_HEADER = "| File | Origin | Fetched (UTC) | Records |\n| --- | --- | --- | --- |\n"
"""A second header with a count of records, which the frame no longer knows (ADR-0062)."""
INTRO = "# Reference data for Example\n\nOne row per file.\n\n"
README = f"{INTRO}{HEADER}| (none yet) | | |\n"
RUFF = 'line-length = 100\n\n[lint]\nselect = ["E", "W", "F", "I", "UP", "RUF"]\n'
ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Source:
    """A source's checkout with its package, ``refexample``, and the client of its lists."""

    root: Path
    package: str
    directory: Path
    client: AsyncClient

    @property
    def reference(self) -> Path:
        return self.directory / "reference"

    @property
    def readme(self) -> Path:
        return self.reference / "README.md"

    @property
    def enums(self) -> Path:
        return self.directory / "enums.py"

    def file(self, name: str) -> Path:
        return self.reference / f"{name}.json"

    def packaged(self, name: str) -> PackagedList:
        return PackagedList.model_validate_json(self.file(name).read_text(encoding="utf-8"))

    def files(self) -> dict[str, bytes]:
        """Every file of the package and its bytes, to show that a run wrote nothing."""
        return {
            str(path.relative_to(self.directory)): path.read_bytes()
            for path in sorted(self.directory.rglob("*"))
            if path.is_file()
        }


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Source:
    """A checkout run from its root, its package importable, its README the template's."""
    root = tmp_path / "repo"
    directory = root / "src" / "refexample"
    (directory / "reference").mkdir(parents=True)
    (directory / "__init__.py").write_text("")
    (directory / "reference/README.md").write_text(README)
    (root / "ruff.toml").write_text(RUFF)
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "src"))
    retry = RetryPolicy(max_attempts=3, backoff_base=0.0, jitter=False)
    config = ClientConfig(source="example", version="1", base_url=BASE, retry=retry)
    return Source(root, "refexample", directory, AsyncClient(config))


def values(client: AsyncClient, param: str) -> Callable[[], Any]:
    """The fetch of a list of values through ``get_param_values`` for ``param``: async, its
    values made records of one field named by ``param``, as a script makes them."""

    async def fetch() -> list[dict[str, str]]:
        answer = (await client.get_answer("/get_param_values", params={"param": param})).payload
        return [{param: str(value)} for value in answer]

    return fetch


class Unit(UpstreamModel):
    unit_id: int = Field(alias="unitId")
    unit_description: str = Field(alias="unitDescription")


def units(client: AsyncClient) -> Callable[[], Any]:
    """The wrapper of ``GetUnitsOfMeasure``: an async fetch of its records."""

    async def fetch() -> list[Unit]:
        answer = (await client.get_answer("/units")).payload
        return [Unit.model_validate(record) for record in answer]

    return fetch


def declared(source: Source, lists: Sequence[Listed], fields: dict[str, Any]) -> Lists:
    """The script's declaration: the package, ``lists``, the names it ships, by default
    those declared, and the client, with ``fields`` over them."""
    shipped = [listed.name for listed in lists if isinstance(listed, Listed)]
    given = {"package": source.package, "packaged": shipped, "client": source.client, **fields}
    return Lists(lists=lists, **given)


def go(source: Source, lists: Sequence[Listed], *args: str, **fields: Any) -> tuple[int, str]:
    """The script's ``run`` with ``args``: its exit status and what it printed."""
    printed = io.StringIO()
    with redirect_stdout(printed):
        status = run(declared(source, lists, fields), list(args))
    return status, printed.getvalue()


def go_raising(
    source: Source, lists: Sequence[Listed], *args: str, **fields: Any
) -> tuple[BaseException, str]:
    """``go`` for a run that raises: what it raised and what it printed before."""
    printed = io.StringIO()
    raised = (XippiosError, SystemExit, ValueError, OSError, RuntimeError)
    with redirect_stdout(printed), pytest.raises(raised) as error:
        run(declared(source, lists, fields), list(args))
    return error.value, printed.getvalue()


def two_value_lists(source: Source) -> list[Listed]:
    return [
        Listed(name, values(source.client, name), endpoint="get_param_values", enum=Enumeration())
        for name in ("state_alpha", "unit")
    ]


def stamped(
    source: Source,
    name: str,
    endpoint: str,
    day: int,
    records: list[Any],
    *,
    param: str | None = None,
) -> None:
    """Package ``name`` as a run fetched it on 2026-10-``day``, its ``param`` by default its
    name."""
    fetched = datetime(2026, 10, day, 9, 15, tzinfo=UTC)
    PackagedList(param=param or name, endpoint=endpoint, fetched=fetched, records=records).write(
        source.file(name)
    )


# --- one request each, counted, and nothing written on failure (#64) ----------------------


def test_each_request_is_sent_once_and_a_failed_run_writes_nothing(source: Source) -> None:
    """#64: the client sends each request once, a 503's included, and the run prints the
    requests it sent and the quota left, a failed run's too; nothing is written, and the
    client's configuration is restored."""
    configured = source.client.config
    before = source.files()
    with respx.mock(base_url=BASE) as upstream:
        route = upstream.get("/get_param_values").respond(503)
        error, printed = go_raising(source, two_value_lists(source))
    assert isinstance(error, XippiosError), error
    assert route.call_count == 1, "one request, no retry"
    assert "requests sent: 1; quota left: not reported" in printed, printed
    assert source.files() == before, "nothing written"
    assert source.client.config is configured


def test_a_run_writes_every_list_then_its_rows_and_its_enums(source: Source) -> None:
    """Every list is fetched, then written by ``PackagedList.write``, a list of values as the
    records of one field named by the list that its fetch makes; the provenance rows and
    ``enums.py`` follow, and the run prints what it sent and the quota upstream reported."""
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").respond(
            200, json=["AK", "CA"], headers={"x-ratelimit-remaining": "41"}
        )
        status, printed = go(source, two_value_lists(source), quota_header="x-ratelimit-remaining")
    assert status == 0
    assert "requests sent: 2; quota left: 41 (x-ratelimit-remaining)" in printed, printed
    state = source.packaged("state_alpha")
    assert (state.param, state.endpoint) == ("state_alpha", "get_param_values")
    assert state.records == [{"state_alpha": "AK"}, {"state_alpha": "CA"}]
    assert "state_alpha.json: 2 records from get_param_values" in printed
    rows = source.readme.read_text().split(HEADER, 1)[1].splitlines()
    assert rows == [
        f"| `state_alpha.json` | `get_param_values` | {state.fetched:%Y-%m-%dT%H:%M:%SZ} |",
        f"| `unit.json` | `get_param_values` | "
        f"{source.packaged('unit').fetched:%Y-%m-%dT%H:%M:%SZ} |",
    ], "the template's placeholder row gives way to one row per list"
    enums = source.enums.read_text()
    assert "class StateAlpha(StrEnum):" in enums
    assert "class Unit(StrEnum):" in enums
    assert '"""Enums of the packaged lists, generated by scripts/refresh_reference.py' in enums


def test_only_fetches_the_named_lists_and_keeps_every_other_file(source: Source) -> None:
    """#64: ``--only`` fetches the lists it names and keeps the other's file; it refuses a
    name no list has, and a kept list not packaged yet, before any request."""
    lists = two_value_lists(source)
    with respx.mock(base_url=BASE) as upstream:
        route = upstream.get("/get_param_values")
        route.respond(200, json=["MT"])
        error, _ = go_raising(source, lists, "--only", "unit")
        assert isinstance(error, SystemExit)
        assert "state_alpha.json is not packaged yet" in str(error), error
        assert route.call_count == 0
        go(source, lists)
        kept = source.file("state_alpha").read_bytes()
        route.respond(200, json=["WY"])
        status, printed = go(source, lists, "--only", "unit")
        assert status == 0
        assert route.call_count == 3
        assert "requests sent: 1; quota left: not reported" in printed, printed
        assert source.file("state_alpha").read_bytes() == kept, "--only keeps the other's file"
        assert source.packaged("unit").records == [{"unit": "WY"}]
        error, _ = go_raising(source, lists, "--only", "county")
        assert isinstance(error, SystemExit)
        assert "--only: no list county" in str(error), error
        assert route.call_count == 3, "refused before any request"


def test_render_only_and_only_are_one_choice(source: Source) -> None:
    """#64: the command line takes ``--render-only`` or ``--only``, never both."""
    error, _ = go_raising(source, two_value_lists(source), "--render-only", "--only", "unit")
    assert isinstance(error, SystemExit)
    assert error.code == 2


def test_a_transport_error_is_counted_as_sent(source: Source) -> None:
    """A request that fails in transport has no answer to count, yet it may have reached
    upstream: the run counts it as sent, so its count is never below what it spent."""
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").mock(side_effect=httpx.ReadTimeout("slow"))
        error, printed = go_raising(source, two_value_lists(source))
    assert isinstance(error, TransportError), error
    assert "requests sent: 1 (1 ended in a transport error, counted as sent)" in printed


# --- enums.py ------------------------------------------------------------------------------


def test_a_value_list_and_an_id_list_render_into_one_module(source: Source) -> None:
    """The template's proof: two packaged lists fetched on different days, a value list and
    an id list whose names repeat, render one ``enums.py`` of a ``StrEnum`` and an
    ``IntEnum``, each with its date, as ruff leaves it; ``--render-only`` sends no request."""
    lists = [
        Listed("state_alpha", values(source.client, "state_alpha"), enum=Enumeration()),
        Listed(
            "unitsOfMeasure",
            units(source.client),
            enum=Enumeration(ids="unitId", names="unitDescription"),
        ),
    ]
    stamped(
        source,
        "state_alpha",
        "get_param_values",
        25,
        [{"state_alpha": "AK"}, {"state_alpha": "Côte"}],
    )
    stamped(
        source,
        "unitsOfMeasure",
        "GetUnitsOfMeasure",
        23,
        [{"unitId": 33, "unitDescription": "Crates"}, {"unitId": 105, "unitDescription": "Crates"}],
    )
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        status, printed = go(source, lists, "--render-only")
    assert status == 0
    assert route.call_count == 0
    assert "enums.py: 2 enums" in printed
    enums = importlib.import_module("refexample.enums")
    try:
        assert enums.__all__ == ["StateAlpha", "UnitId"], enums.__all__
        assert [enums.StateAlpha.AK, enums.StateAlpha.C_TE] == ["AK", "Côte"]
        assert [enums.UnitId.CRATES_33, enums.UnitId.CRATES_105] == [33, 105]
        assert "(fetched 2026-10-25)" in (enums.StateAlpha.__doc__ or "")
        assert "(fetched 2026-10-23)" in (enums.UnitId.__doc__ or "")
    finally:
        for name in ("refexample.enums", "refexample"):
            sys.modules.pop(name, None)
    for command in (["format", "--check"], ["check"]):
        ruff = subprocess.run(
            [sys.executable, "-m", "ruff", *command, str(source.enums)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert ruff.returncode == 0, ruff.stdout + ruff.stderr


def test_enums_follow_the_declared_order_and_take_names_by_hand(source: Source) -> None:
    """The classes stand in the order the lists are declared, whatever their names. A list's
    ``StrEnum`` reads its values from the field its file's ``param`` names, takes the list's
    name as its key, and a class name and members by hand, as a mapping or from the values,
    and a table declares no enum."""
    stamped(source, "zone", "get_param_values", 20, [{"zone": "B"}, {"zone": "A"}])
    stamped(
        source,
        "stages",
        "api_GET",
        21,
        [{"unit_desc": "PCT PLANTED"}, {"unit_desc": "$ / BU"}],
        param="unit_desc",
    )
    stamped(source, "commodities", "GetCommodities", 22, [{"code": "01", "name": "Wheat"}])

    def dollars(found: Sequence[Any]) -> Mapping[Any, str]:
        return {value: "DOLLARS_PER_BU" for value in found if "$" in value}

    lists = [
        Listed("zone", values(source.client, "zone"), enum=Enumeration(member_names={"B": "BEE"})),
        Listed(
            "stages",
            values(source.client, "unit_desc"),
            param="unit_desc",
            enum=Enumeration(class_name="ProgressStage", member_names=dollars),
        ),
        Listed("commodities", values(source.client, "commodities")),
    ]
    status, _ = go(source, lists, "--render-only")
    assert status == 0
    text = source.enums.read_text()
    assert text.index("class Zone(StrEnum):") < text.index("class ProgressStage(StrEnum):")
    assert "BEE = " in text
    assert "DOLLARS_PER_BU = " in text
    assert '"""Values of ``stages`` (fetched 2026-10-21)."""' in text
    assert "Commodities" not in text


def test_enums_py_is_left_alone_where_no_list_declares_an_enum(source: Source) -> None:
    """A source whose lists are all tables keeps its ``enums.py`` as it stands, hand-written
    or empty, and one with none gets none."""
    stamped(source, "commodities", "GetCommodities", 22, [{"code": "01", "name": "Wheat"}])
    lists = [Listed("commodities", values(source.client, "commodities"))]
    status, printed = go(source, lists, "--render-only")
    assert status == 0
    assert not source.enums.exists()
    assert "enums.py: left alone, no list declares an enum" in printed
    source.enums.write_text('"""Hand-written: none."""\n\n__all__ = []\n')
    go(source, lists, "--render-only")
    assert source.enums.read_text() == '"""Hand-written: none."""\n\n__all__ = []\n'


def test_nothing_is_written_when_the_render_fails(source: Source) -> None:
    """``enums.py`` and the provenance rows are made before the first file is written, so an
    enum that cannot be rendered leaves every file as it was."""
    lists = two_value_lists(source)
    before = source.files()
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").respond(200, json=["", "AK"])
        error, _ = go_raising(source, lists)
    assert isinstance(error, ValueError)
    assert "no member name can be derived" in str(error)
    assert source.files() == before


# --- what a fetch answers, and when it was fetched -----------------------------------------


def test_a_fetch_answers_records_or_a_finished_list(source: Source) -> None:
    """Records keep upstream's names, a model's by ``dump_upstream`` and a mapping's as it
    is, under the list's ``param``, its name by default, and a finished list is written as
    built, its ``fetched`` and ``note`` its own; the others are stamped when their fetch
    returned."""
    built = datetime(2026, 11, 1, 8, 0, 5, tzinfo=UTC)

    def finished() -> PackagedList:
        return PackagedList(
            param="unit_desc",
            endpoint="api_GET",
            fetched=built,
            note="distinct unit_desc of api_GET",
            records=[{"unit_desc": "PCT"}],
        )

    lists = [
        Listed("area_QCL", lambda: [{"area": "4"}], endpoint="getCodeList", param="area"),
        Listed("unitsOfMeasure", units(source.client), endpoint="GetUnitsOfMeasure"),
        Listed("regions", lambda: [{"regionCode": "1", "extra": None}], endpoint="GetRegions"),
        Listed("progress_stages", finished),
    ]
    start = datetime.now(UTC).replace(microsecond=0)
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/units").respond(200, json=[{"unitId": 4, "unitDescription": "Bales"}])
        go(source, lists)
    end = datetime.now(UTC)
    area = source.packaged("area_QCL")
    assert (area.param, area.records) == ("area", [{"area": "4"}])
    assert source.packaged("regions").param == "regions"
    assert source.packaged("unitsOfMeasure").records == [{"unitId": 4, "unitDescription": "Bales"}]
    assert source.packaged("regions").records == [{"regionCode": "1", "extra": None}]
    stages = source.packaged("progress_stages")
    assert (stages.fetched, stages.note, stages.param) == (built, finished().note, "unit_desc")
    for name in ("area_QCL", "unitsOfMeasure", "regions"):
        assert start <= source.packaged(name).fetched <= end


@pytest.mark.parametrize(
    ("answer", "found"),
    [(["4", "8"], "a str at position 0"), ([{"area": "4"}, 8], "an int at position 1")],
)
def test_a_fetch_that_answers_plain_values_is_refused(
    source: Source, answer: list[Any], found: str
) -> None:
    """ADR-0062, decision 11: the fetch that answers plain values leaves, so an item that is
    no record, a model or a mapping, stops the run before the first write, and the message
    names the list, the item's type and its position, never its value."""
    before = source.files()
    listed = Listed("area_QCL", lambda: answer, endpoint="getCodeList", param="area")
    error, _ = go_raising(source, [listed])
    assert isinstance(error, SystemExit)
    assert str(error).startswith(f"area_QCL's fetch answered {found}: a fetch answers records,")
    assert "'4'" not in str(error)
    assert source.files() == before


def test_a_fetch_that_answers_an_answer_is_written_as_its_records(source: Source) -> None:
    """https://github.com/xippios/sdk-core/issues/577: an ``api/`` wrapper answers an
    ``Answer`` by ``get_answer`` (https://github.com/xippios/sdk-core/issues/479), and a list
    whose fetch is that wrapper is written as one whose fetch answers the records, its
    ``payload``: the same file, stamped when the fetch returned, whatever the ``Answer``'s
    ``retrieved_at``."""
    long_ago = datetime(2020, 1, 1, tzinfo=UTC)
    regions = [{"regionCode": "1", "extra": None}]

    async def get_units_of_measure() -> Answer[list[Unit]]:
        return await source.client.get_answer(
            "/units", parse=list[Unit], endpoint="GetUnitsOfMeasure"
        )

    bare = [
        Listed("unitsOfMeasure", units(source.client), endpoint="GetUnitsOfMeasure"),
        Listed("regions", lambda: regions, endpoint="GetRegions"),
    ]
    answered = [
        Listed("unitsOfMeasure", get_units_of_measure, endpoint="GetUnitsOfMeasure"),
        Listed("regions", lambda: Answer(regions, long_ago), endpoint="GetRegions"),
    ]
    written: list[dict[str, dict[str, Any]]] = []
    for lists in (bare, answered):
        start = datetime.now(UTC).replace(microsecond=0)
        with respx.mock(base_url=BASE) as upstream:
            upstream.get("/units").respond(200, json=[{"unitId": 4, "unitDescription": "Bales"}])
            status, _ = go(source, lists)
        end = datetime.now(UTC)
        assert status == 0
        files = {listed.name: source.packaged(listed.name) for listed in lists}
        for name, packaged in files.items():
            assert start <= packaged.fetched <= end, name
        written.append(
            {name: packaged.model_dump(exclude={"fetched"}) for name, packaged in files.items()}
        )
    assert written[1] == written[0]
    assert written[1]["unitsOfMeasure"]["records"] == [{"unitId": 4, "unitDescription": "Bales"}]


@pytest.mark.parametrize(
    ("payload", "found"),
    [({"data": [{"area": "4"}]}, "an Answer of a dict"), ("4", "an Answer of a str")],
    ids=["body", "text"],
)
def test_an_answer_that_holds_no_records_is_refused(
    source: Source, payload: object, found: str
) -> None:
    """https://github.com/xippios/sdk-core/issues/577: an ``Answer`` whose payload is the body
    that holds the records, or anything else that is no sequence of them, stops the run before
    the first write, as a fetch that answers neither records nor a finished list does, and the
    message says to hand the records and names the payload's type, never its value."""
    before = source.files()
    answer: Any = Answer(payload, datetime(2026, 11, 1, tzinfo=UTC))  # a fetch mypy refuses
    listed = Listed("area_QCL", lambda: answer, endpoint="getCodeList", param="area")
    error, _ = go_raising(source, [listed])
    assert isinstance(error, SystemExit)
    assert str(error).startswith(f"area_QCL's fetch answered {found}: "), error
    assert "hand the records" in str(error), error
    assert "'4'" not in str(error)
    assert source.files() == before


def test_a_finished_list_agrees_with_its_declaration(source: Source) -> None:
    """A finished list that names another ``param`` or ``endpoint`` than its declaration,
    records with no endpoint to name, and an answer that is neither stop the run, and
    nothing is written."""
    fetched = datetime(2026, 11, 1, tzinfo=UTC)

    def other() -> PackagedList:
        return PackagedList(param="b", endpoint="Other", fetched=fetched, records=[])

    before = source.files()
    cases = {
        "a's fetch built a list of endpoint 'Other'": Listed("a", other, endpoint="GetA"),
        "a's fetch built a list of param 'b'": Listed("a", other, param="a"),
        "a's fetch answers records: name its endpoint": Listed("a", lambda: [{"a": "x"}]),
        "a's fetch answered a str": Listed(
            "a",
            lambda: "x",  # type: ignore[arg-type,return-value]
            endpoint="GetA",
        ),
    }
    for message, listed in cases.items():
        error, _ = go_raising(source, [listed])
        assert isinstance(error, SystemExit)
        assert message in str(error), error
    assert source.files() == before


def test_an_enumeration_names_no_field_of_values_and_no_key() -> None:
    """ADR-0062, decision 11: ``Enumeration.values`` and ``.key`` leave; a ``StrEnum`` reads
    the field its file's ``param`` names and takes the list's name as its key, an ``IntEnum``
    the fields of its ids and names and ``ids`` as its key."""
    assert [field.name for field in dataclasses.fields(Enumeration)] == [
        "ids",
        "names",
        "class_name",
        "member_names",
    ]


def test_the_declaration_is_checked_before_a_request(source: Source) -> None:
    """Two lists of one name, two enums of one key, an id enum without its names and a
    declaration of no list stop the run before anything is fetched."""
    fetch = values(source.client, "a")
    cases: dict[str, list[Listed]] = {
        "two lists are named a": [Listed("a", fetch), Listed("a", fetch)],
        "two lists declare the enum of key a": [
            Listed("a", fetch, enum=Enumeration()),
            Listed("b", fetch, enum=Enumeration(ids="a", names="name")),
        ],
        "a: an Enumeration of ids names both ids and names": [
            Listed("a", fetch, enum=Enumeration(ids="id"))
        ],
        "b: an Enumeration of ids names both ids and names": [
            Listed("b", fetch, enum=Enumeration(names="name"))
        ],
        "a list's name is a file's name under reference/": [Listed("../a", fetch)],
        "Nothing to fetch": [],
    }
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        for message, lists in cases.items():
            error, _ = go_raising(source, lists)
            assert isinstance(error, SystemExit)
            assert message in str(error), error
    assert route.call_count == 0


# --- the provenance table of reference/README.md -------------------------------------------


def test_the_rows_are_rewritten_in_place_under_the_header_found(source: Source) -> None:
    """Each declared list's row is written where it stands, a row of a file no list declares
    is kept, the text after the table too, and a list without a row gets one after the
    others."""
    stamped(source, "b", "GetB", 2, [{"b": "x"}])
    stamped(source, "a", "GetA", 1, [{"a": "x"}])
    stamped(source, "c", "GetC", 3, [{"c": "x"}])
    source.readme.write_text(
        f"{INTRO}{HEADER}"
        "| `b.json` | old | 2026-01-01T00:00:00Z |\n"
        "| `columns.csv` | `docs/upstream/param_define.md` | 2026-10-28T13:44:34Z |\n"
        "| `a.json` | old | 2026-01-01T00:00:00Z |\n"
        "\nThe two derived lists come from the year before the fetch.\n"
    )
    lists = [Listed(name, values(source.client, name)) for name in ("a", "b", "c")]
    status, printed = go(source, lists, "--render-only")
    assert status == 0
    assert source.readme.read_text() == (
        f"{INTRO}{HEADER}"
        "| `b.json` | `GetB` | 2026-10-02T09:15:00Z |\n"
        "| `columns.csv` | `docs/upstream/param_define.md` | 2026-10-28T13:44:34Z |\n"
        "| `a.json` | `GetA` | 2026-10-01T09:15:00Z |\n"
        "| `c.json` | `GetC` | 2026-10-03T09:15:00Z |\n"
        "\nThe two derived lists come from the year before the fetch.\n"
    )
    assert "README.md: the rows of 3 lists" in printed, printed


def test_the_frame_knows_one_header_and_counts_no_records(source: Source) -> None:
    """ADR-0062, decision 13: the frame knows the one header that sdk-template renders, so no
    row counts its file's records, and a README under a second header, one with ``Records``,
    stops a run, and a render alone, before anything is fetched or written, naming the one
    header it takes."""
    stamped(source, "commodities", "GetCommodities", 28, [{"c": n} for n in range(2909)])
    lists = [Listed("commodities", values(source.client, "c"))]
    go(source, lists, "--render-only")
    assert source.readme.read_text() == (
        f"{INTRO}{HEADER}| `commodities.json` | `GetCommodities` | 2026-10-28T09:15:00Z |\n"
    )
    source.readme.write_text(f"{INTRO}{RECORDS_HEADER}| `commodities.json` | x | y | 1 |\n")
    before = source.files()
    headed = "has no provenance table headed '| File | Origin | Fetched |'; nothing was written"
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        for args in ((), ("--render-only",)):
            error, _ = go_raising(source, lists, *args)
            assert isinstance(error, SystemExit)
            assert str(error).endswith(headed), error
    assert route.call_count == 0
    assert source.files() == before


def test_an_origin_is_the_endpoint_a_text_or_made_from_the_list(source: Source) -> None:
    """Origin is the endpoint in a code span by default, a declared text, or a function of
    the list as written, such as a count the source puts in its words."""
    for name in ("a", "b", "c"):
        stamped(source, name, f"Get{name.upper()}", 4, [{name: "x"}, {name: "y"}])

    def counted(packaged: PackagedList) -> str:
        return f"`{packaged.endpoint}`, one request ({len(packaged.records)} records)"

    lists = [
        Listed("a", values(source.client, "a")),
        Listed("b", values(source.client, "b"), origin="the snapshot's `b` enum"),
        Listed("c", values(source.client, "c"), origin=counted),
    ]
    go(source, lists, "--render-only")
    assert source.readme.read_text().split(HEADER, 1)[1] == (
        "| `a.json` | `GetA` | 2026-10-04T09:15:00Z |\n"
        "| `b.json` | the snapshot's `b` enum | 2026-10-04T09:15:00Z |\n"
        "| `c.json` | `GetC`, one request (2 records) | 2026-10-04T09:15:00Z |\n"
    )


def test_a_readme_without_the_table_stops_the_run_before_a_request(source: Source) -> None:
    """A README that holds no header of the table stops a run, and a render alone, before
    anything is fetched or written; so does an origin that would break its row."""
    lists = two_value_lists(source)
    source.readme.write_text(f"{INTRO}| File | Fetched |\n| --- | --- |\n")
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        for args in ((), ("--render-only",)):
            error, _ = go_raising(source, lists, *args)
            assert isinstance(error, SystemExit)
            assert "has no provenance table headed" in str(error), error
    assert route.call_count == 0
    source.readme.write_text(README)
    stamped(source, "a", "GetA", 4, [{"a": "x"}])
    error, _ = go_raising(source, [Listed("a", lambda: [], origin="a | b")], "--render-only")
    assert isinstance(error, SystemExit)
    assert "a's origin holds a | or a line break" in str(error), error
    assert source.readme.read_text() == README


def test_render_only_needs_every_file_and_changes_nothing_twice(source: Source) -> None:
    """``--render-only`` reads every declared list's file, names the first one missing, and
    a second render leaves ``enums.py`` and the README as the first wrote them."""
    lists = two_value_lists(source)
    stamped(source, "state_alpha", "get_param_values", 5, [{"state_alpha": "AK"}])
    error, _ = go_raising(source, lists, "--render-only")
    assert isinstance(error, SystemExit)
    assert "unit.json is not packaged yet: run the script without --render-only" in str(error)
    stamped(source, "unit", "get_param_values", 6, [{"unit": "BU"}])
    go(source, lists, "--render-only")
    first = source.files()
    go(source, lists, "--render-only")
    assert source.files() == first


# --- the hooks, and nothing written before everything is fetched ---------------------------


def test_the_hooks_run_before_the_first_request_and_after_the_last_write(source: Source) -> None:
    """``before`` runs once the command line is read and before the first request,
    ``after`` once every file is written, with the lists this run fetched; ``--render-only``
    calls neither."""
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(f"request {request.url.params['param']}")
        return httpx.Response(200, json=["AK"])

    def after(written: Mapping[str, PackagedList]) -> None:
        seen.append(f"after {sorted(written)} {source.enums.is_file()}")

    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").mock(side_effect=answer)
        go(source, two_value_lists(source), before=lambda: seen.append("before"), after=after)
        assert seen == [
            "before",
            "request state_alpha",
            "request unit",
            "after ['state_alpha', 'unit'] True",
        ]
        seen.clear()
        go(source, two_value_lists(source), "--only", "unit", after=after)
        assert seen == ["request unit", "after ['unit'] True"]
        seen.clear()
        go(
            source,
            two_value_lists(source),
            "--render-only",
            before=lambda: seen.append("before"),
            after=after,
        )
        assert seen == []


def test_nothing_is_written_until_everything_is_fetched(source: Source) -> None:
    """A ``before`` that raises stops the run before a request, and a failed fetch of the
    last list leaves every file as it was and ``after`` uncalled: what a script writes
    beside the lists is written after them or not at all."""
    called: list[str] = []

    def refuse() -> None:
        raise SystemExit("the snapshot's column table is gone")

    before = source.files()
    with respx.mock(base_url=BASE) as upstream:
        route = upstream.get("/get_param_values")
        route.side_effect = [httpx.Response(200, json=["AK"]), httpx.Response(500)]
        error, _ = go_raising(source, two_value_lists(source), before=refuse)
        assert "column table is gone" in str(error)
        assert route.call_count == 0
        error, printed = go_raising(
            source, two_value_lists(source), after=lambda written: called.append("after")
        )
    assert isinstance(error, XippiosError)
    assert "requests sent: 2; quota left: not reported" in printed
    assert source.files() == before
    assert called == []


def test_a_formatter_that_fails_leaves_every_file_as_it_was(source: Source) -> None:
    """``enums.py`` is formatted with ``ruff format`` and ``ruff check --fix`` before the
    first write, under the source's configuration for its path, so a module ruff leaves
    failing stops a run, and a render alone, with every file as it was."""
    (source.root / "ruff.toml").write_text('line-length = 30\n\n[lint]\nselect = ["E501"]\n')
    lists = [
        Listed(
            "state_alpha_long_name",
            values(source.client, "state_alpha_long_name"),
            endpoint="get_param_values",
            enum=Enumeration(),
        )
    ]
    before = source.files()
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").respond(200, json=["ALPHA_VALUE_THAT_IS_LONG"])
        error, _ = go_raising(source, lists)
    assert isinstance(error, SystemExit)
    assert "ruff check --fix left enums.py failing; nothing was written" in str(error), error
    assert source.files() == before
    stamped(
        source, "state_alpha_long_name", "get_param_values", 7, [{"state_alpha_long_name": "A"}]
    )
    before = source.files()
    error, _ = go_raising(source, lists, "--render-only")
    assert "ruff check --fix left enums.py failing; nothing was written" in str(error), error
    assert source.files() == before


def test_a_write_that_fails_puts_back_every_file_it_replaced(source: Source) -> None:
    """The packaged files, the README and ``enums.py`` are written as one: a write that fails
    halfway, here the README's, puts back each file the run replaced, removes each it made,
    and raises its error."""
    stamped(source, "state_alpha", "get_param_values", 8, [{"state_alpha": "OLD"}])
    source.readme.chmod(0o444)
    before = source.files()
    try:
        with respx.mock(base_url=BASE) as upstream:
            upstream.get("/get_param_values").respond(200, json=["AK"])
            error, printed = go_raising(source, two_value_lists(source))
    finally:
        source.readme.chmod(0o644)
    assert isinstance(error, PermissionError), error
    assert source.files() == before, "state_alpha.json put back, unit.json and enums.py gone"
    assert "state_alpha.json:" not in printed


def test_an_after_hook_that_raises_leaves_the_frames_files_written(source: Source) -> None:
    """``after`` runs once the frame's files are written whole, so a hook that raises leaves
    them standing, the run says so, and the hook's error ends it."""

    def after(written: Mapping[str, PackagedList]) -> None:
        raise RuntimeError("the index could not be written")

    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/get_param_values").respond(200, json=["AK"])
        error, printed = go_raising(source, two_value_lists(source), after=after)
    assert isinstance(error, RuntimeError)
    assert source.packaged("unit").records == [{"unit": "AK"}]
    assert "class Unit(StrEnum):" in source.enums.read_text()
    assert "after raised RuntimeError: the files above stand written" in printed, printed


# --- the one run of both frames, the package's own lists, and where the package is ---------


def test_the_lists_are_those_the_package_declares(source: Source) -> None:
    """``packaged`` names the lists the package declares it ships, its
    ``params.PACKAGED_LISTS``: a list declared to ``run`` alone, or by the package alone,
    stops a run, and a render alone, before anything is fetched or written."""
    lists = two_value_lists(source)
    before = source.files()
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        for args in ((), ("--render-only",)):
            error, _ = go_raising(source, lists, *args, packaged=("state_alpha", "county"))
            assert isinstance(error, SystemExit)
            assert "declared to run alone: unit. Declared by the package alone: county." in str(
                error
            ), error
        error, _ = go_raising(source, lists, packaged="state_alpha")
        assert "packaged names the lists the package ships" in str(error), error
    assert route.call_count == 0
    assert source.files() == before


def test_run_takes_one_declaration_of_either_frame(source: Source, tmp_path: Path) -> None:
    """ADR-0062, decision 2: ``run(declaration, argv=None)`` is the one signature of both
    frames, given a ``Snapshot`` or a ``Lists``, a frozen dataclass of seven fields beside it;
    the overloads and the lists' keywords leave, and what is neither declaration is refused
    before anything is read or fetched."""
    parameters = inspect.signature(run).parameters
    assert list(parameters) == ["declaration", "argv"]
    assert parameters["argv"].default is None
    assert [field.name for field in dataclasses.fields(Lists)] == [
        "package",
        "lists",
        "packaged",
        "client",
        "quota_header",
        "before",
        "after",
    ]
    lists = two_value_lists(source)
    declaration = Lists(source.package, lists, ("state_alpha", "unit"), source.client)
    assert (declaration.quota_header, declaration.before, declaration.after) == (None, None, None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        declaration.package = "elsewhere"  # type: ignore[misc]
    snapshot = Snapshot(name="Example", slug="example", pages=(), out=tmp_path / "upstream")
    with pytest.raises(SystemExit, match="Nothing to fetch: declare the snapshot's pages"):
        run(snapshot, [])
    with pytest.raises(SystemExit, match="Nothing to fetch: declare the snapshot's pages"):
        run(declaration=snapshot, argv=[])
    before = source.files()
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        with pytest.raises(SystemExit, match=r"^run takes one declaration, a Snapshot or a Lists"):
            run(lists, [])  # type: ignore[arg-type]
    assert route.call_count == 0
    assert source.files() == before


def test_a_package_outside_the_working_directory_is_refused(
    source: Source, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The frame writes into the package's directory as imported, so a package imported
    from elsewhere than the checkout the script runs in, an installed copy, is refused."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    error, _ = go_raising(source, two_value_lists(source), "--render-only")
    assert isinstance(error, SystemExit)
    assert "outside the directory the script runs in" in str(error), error
    nowhere = Lists(
        "nowhere.at.all", two_value_lists(source), ("state_alpha", "unit"), source.client
    )
    with pytest.raises(SystemExit, match=r"nowhere\.at\.all is not importable"):
        run(nowhere, [])


# --- the README's short script -------------------------------------------------------------

EXAMPLE_CLIENT = """from xippios.core import AsyncClient, ClientConfig

BASE_URL = "https://api.example.org"
client = AsyncClient(ClientConfig(source="example", version="0", base_url=BASE_URL))
"""

EXAMPLE_API = """from typing import Any

from xippios.core import Answer, UpstreamModel
from xippios.example._client import client


class Unit(UpstreamModel):
    unitId: int
    unitDescription: str


async def get_param_values(param: str) -> Answer[list[str]]:
    params = {"param": param}
    path, endpoint = "/api/get_param_values", "get_param_values"
    return await client.get_answer(path, params=params, parse=list[str], endpoint=endpoint)


async def get_units_of_measure() -> Answer[list[Unit]]:
    path, endpoint = "/api/unitsOfMeasure", "GetUnitsOfMeasure"
    return await client.get_answer(path, parse=list[Unit], endpoint=endpoint)


async def get_commodities() -> Answer[list[dict[str, Any]]]:
    return await client.get_answer("/api/commodities")
"""
"""The ``api/`` wrappers, each answering the ``Answer`` of ``get_answer`` as every wrapper does
(https://github.com/xippios/sdk-core/issues/479), which the README's script hands the frame as
its fetches (https://github.com/xippios/sdk-core/issues/577)."""

EXAMPLE_PARAMS = """PACKAGED_LISTS: tuple[str, ...] = ({names})
"""


@pytest.fixture
def example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A checkout of ``xippios.example``, its ``api/`` wrappers on the client of ``_client``."""
    root = tmp_path / "sdk-example"
    package = root / "src/xippios/example"
    (package / "reference").mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "_client.py").write_text(EXAMPLE_CLIENT)
    (package / "api.py").write_text(EXAMPLE_API)
    names = '"state_alpha", "unitsOfMeasure", "commodities"'
    (package / "params.py").write_text(EXAMPLE_PARAMS.format(names=names))
    (package / "reference/README.md").write_text(README)
    (root / "ruff.toml").write_text(RUFF)
    monkeypatch.chdir(root)
    monkeypatch.syspath_prepend(str(root / "src"))
    yield package
    for name in [name for name in sys.modules if name.startswith("xippios.example")]:
        del sys.modules[name]


def test_the_readmes_short_script_runs_on_the_frame(
    example: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The short script that sdk-template renders, as the README's section on the frame
    holds it, declares its lists in one ``Lists`` that the frame fetches, writes and renders
    as they stand, its ``api/`` wrappers' ``Answer`` read from its payload, and hands ``run``
    that declaration alone."""
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## The reference refresh script's frame\n", 1)[1]
    script = section.split("```python\n", 1)[1].split("```\n", 1)[0]
    assert 40 <= len(script.splitlines()) <= 60, len(script.splitlines())
    assert "from xippios.core.refresh import Enumeration, Listed, Lists, run\n" in script
    assert "    raise SystemExit(run(LISTS))\n" in script
    monkeypatch.setattr(sys, "argv", ["scripts/refresh_reference.py"])
    namespace: dict[str, Any] = {"__name__": "__main__", "__file__": "scripts/refresh_reference.py"}
    with respx.mock(base_url=BASE) as upstream:
        upstream.get("/api/get_param_values").respond(200, json=["AK", "CA"])
        upstream.get("/api/unitsOfMeasure").respond(
            200, json=[{"unitId": 33, "unitDescription": "Crates"}]
        )
        upstream.get("/api/commodities").respond(
            200, json=[{"commodityCode": "0410000", "commodityName": "Wheat"}]
        )
        with pytest.raises(SystemExit) as exited:
            exec(compile(script, "README.md", "exec"), namespace)
    assert exited.value.code == 0
    assert sorted(path.name for path in (example / "reference").iterdir()) == [
        "README.md",
        "commodities.json",
        "state_alpha.json",
        "unitsOfMeasure.json",
    ]
    state = PackagedList.model_validate_json((example / "reference/state_alpha.json").read_text())
    assert state.records == [{"state_alpha": "AK"}, {"state_alpha": "CA"}]
    enums = (example / "enums.py").read_text()
    assert "class StateAlpha(StrEnum):" in enums
    assert "class UnitId(IntEnum):" in enums
    rows = (example / "reference/README.md").read_text().split(HEADER, 1)[1].splitlines()
    assert [row.split(" | ")[0] for row in rows] == [
        "| `state_alpha.json`",
        "| `unitsOfMeasure.json`",
        "| `commodities.json`",
    ]
    (example / "params.py").write_text(EXAMPLE_PARAMS.format(names='"state_alpha", "regions"'))
    sys.modules.pop("xippios.example.params", None)
    with respx.mock(base_url=BASE, assert_all_called=False) as upstream:
        route = upstream.route()
        with pytest.raises(SystemExit) as exited:
            exec(compile(script, "README.md", "exec"), {**namespace})
    assert "Declared by the package alone: regions." in str(exited.value), exited.value
    assert route.call_count == 0, "the package's own lists are checked before a request"


def test_the_readmes_examples_are_written_as_the_renderer_writes_them() -> None:
    """The README's section on the frame says that ``enums.py`` writes every character
    outside ASCII as an escape: its example of an escaped value is the one ``ascii()``
    writes, and its code, the member named by hand among it, is ASCII as the module is."""
    readme = (ROOT / "README.md").read_text()
    section = readme.split("## The reference refresh script's frame\n", 1)[1].split("\n## ", 1)[0]
    value = "C" + chr(0xF4) + "te d" + chr(0x2019) + "Ivoire"
    assert f"(`{value!a}`)" in section
    blocks = section.split("```python\n")[1:]
    assert len(blocks) == 3, len(blocks)
    for block in blocks:
        code = block.split("```\n", 1)[0]
        assert code.isascii(), code
