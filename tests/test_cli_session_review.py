import json
import sqlite3
import threading
from pathlib import Path

import pytest

from review_gauntlet.cli import main, review_cells_concurrently
from review_gauntlet.review_adapter import ReviewAdapterResult
from review_gauntlet.review_cells import ReviewCell


class CountingAdapter:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def review(self, cell: ReviewCell) -> ReviewAdapterResult:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            return ReviewAdapterResult(cell_id=cell.id, comments=())
        finally:
            with self.lock:
                self.active -= 1


def test_review_cells_concurrently_returns_results() -> None:
    cells = tuple(
        ReviewCell(id=f"RGC-{index}", file_path=f"f{index}.py", rule_id="r", slice_id="s")
        for index in range(3)
    )
    adapter = CountingAdapter()

    results = review_cells_concurrently(adapter, list(cells), concurrency=2)

    assert set(results) == {cell.id for cell in cells}
    assert adapter.max_active <= 2


def test_review_creates_open_finding_from_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "README.md": [
                    {"path": "README.md", "content": "issue", "start_line": 1, "end_line": 1}
                ]
            }
        ),
        encoding="utf-8",
    )
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["finding_ids"] == ["RGF-0001"]
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        assert conn.execute("select state from findings").fetchone()[0] == "open"


def test_review_budget_zero_reports_pending_without_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["reviewed_cells"] == 0
    assert data["run_id"] is None
    assert data["coverage"].get("pending", 0) > 0
