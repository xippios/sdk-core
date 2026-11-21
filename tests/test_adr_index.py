"""The index of the decision records, `docs/adr.md` and `docs/adr.json`.

The organization's repositories carry one `scripts/adr_index.py`, byte for byte, and an issue's
`ADR-0014` links to `docs/adr.md#0014`: the link lands on the record only where the index gives
each record's line its anchor (https://github.com/xippios/sdk-core/issues/350).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "adr.md"
SCRIPT = ROOT / "scripts" / "adr_index.py"
RECORD = re.compile(r"^(\d{4})-.+\.md$")


def record_lines() -> list[str]:
    return [line for line in INDEX.read_text(encoding="utf-8").splitlines() if "[ADR-" in line]


def test_the_index_is_the_one_the_script_writes_from_the_records() -> None:
    # The sdist ships tests/ and docs/ but not scripts/. In a checkout, the organization's
    # check adr-index runs the same --check, so this skip leaves the repository held.
    if not SCRIPT.is_file():
        pytest.skip("the sdist ships no scripts/, so there is no script to check the index with")
    run = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_each_record_line_opens_with_the_anchor_a_citation_links_to() -> None:
    numbers = sorted(
        found.group(1)
        for path in (ROOT / "docs" / "adr").iterdir()
        if (found := RECORD.match(path.name))
    )
    opened = [line for line in record_lines() if line.startswith('- <a id="')]
    assert len(opened) == len(record_lines())
    for number in numbers:
        assert any(line.startswith(f'- <a id="{number}"></a>[ADR-{number}]') for line in opened)


def test_the_records_in_force_come_before_the_superseded_ones() -> None:
    superseded = ["Superseded by ADR-" in line for line in record_lines()]
    assert any(superseded)
    assert superseded == sorted(superseded)
