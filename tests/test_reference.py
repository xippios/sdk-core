import importlib
import json
from pathlib import Path

import pytest

from xippios.core.models import UpstreamModel
from xippios.core.reference import _read_text, load_csv, load_json, load_table

PKG = "refpkg_for_tests"


class Code(UpstreamModel):
    code: str
    name: str
    rank: int


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    root = tmp_path / PKG
    (root / "reference").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "reference" / "codes.csv").write_text(
        "code,name,rank\nUS,United States,1\nDE,Germany,2\n"
    )
    (root / "reference" / "codes.json").write_text(
        json.dumps([{"code": "US", "name": "United States", "rank": 1}])
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    _read_text.cache_clear()
    return PKG


def test_load_csv(package: str) -> None:
    rows = load_csv(package, "codes.csv")
    assert rows == [
        {"code": "US", "name": "United States", "rank": "1"},
        {"code": "DE", "name": "Germany", "rank": "2"},
    ]


def test_load_json(package: str) -> None:
    assert load_json(package, "codes.json")[0]["code"] == "US"


def test_load_table_csv_coerces_types(package: str) -> None:
    rows = load_table(package, "codes.csv", Code)
    assert rows[1] == Code(code="DE", name="Germany", rank=2)


def test_load_table_json(package: str) -> None:
    assert load_table(package, "codes.json", Code)[0].rank == 1


def test_callers_get_fresh_objects(package: str) -> None:
    first = load_csv(package, "codes.csv")
    first[0]["code"] = "mutated"
    assert load_csv(package, "codes.csv")[0]["code"] == "US"


def test_missing_file(package: str) -> None:
    with pytest.raises(FileNotFoundError, match=r"nope\.csv"):
        load_csv(package, "nope.csv")
