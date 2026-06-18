import json
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

import review_gauntlet.cli as cli
from review_gauntlet.cli import ReviewProgressReporter, main, review_cells_concurrently
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_adapter import ReviewAdapter, ReviewAdapterError, ReviewAdapterResult
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


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


ReviewCallback = Callable[[ReviewCell, ReviewAdapterResult | ReviewAdapterError], None]


def _write_two_file_review_session(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    (root / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(root), "--all", "--format", "json"])
    capsys.readouterr()


def test_interrupted_review_persists_successful_cells_and_resume_skips_them(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_two_file_review_session(tmp_path, capsys)
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    interrupted_cell_ids: list[str] = []

    def interrupted_review_cells(
        adapter: ReviewAdapter,
        cells: list[ReviewCell],
        *,
        concurrency: int,
        reporter: ReviewProgressReporter | None = None,
        on_result: ReviewCallback | None = None,
    ) -> dict[str, ReviewAdapterResult | ReviewAdapterError]:
        del adapter, concurrency, reporter
        assert on_result is not None
        completed = cells[0]
        interrupted_cell_ids.append(completed.id)
        on_result(
            completed,
            ReviewAdapterResult(
                cell_id=completed.id,
                comments=(
                    OCRComment(
                        path=completed.file_path,
                        content="interrupted but durable finding",
                        start_line=1,
                        end_line=1,
                    ),
                ),
            ),
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "review_cells_concurrently", interrupted_review_cells)

    with pytest.raises(KeyboardInterrupt):
        main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])

    interrupted_output = json.loads(capsys.readouterr().out)
    reviewed_cell_id = interrupted_cell_ids[0]
    store = SessionStore(tmp_path)
    session_id = store.active_session_id()
    rows_by_id = {str(row["cell_id"]): row for row in store.list_cells(session_id)}
    assert interrupted_output["reviewed_cells"] == 1
    assert interrupted_output["interrupted"] is True
    assert rows_by_id[reviewed_cell_id]["state"] == "reviewed"
    assert {
        str(row["state"]) for cell_id, row in rows_by_id.items() if cell_id != reviewed_cell_id
    } == {"pending"}
    assert interrupted_output["session_state"] == "active"
    assert interrupted_output["coverage"]["reviewed"] == 1
    assert interrupted_output["coverage"]["pending"] == len(rows_by_id) - 1
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        assert conn.execute("select count(*) from findings").fetchone()[0] == 1
        occurrence = conn.execute("select run_id, cell_id from finding_occurrences").fetchone()
    assert occurrence == (interrupted_output["run_id"], reviewed_cell_id)

    resumed_cell_ids: list[str] = []

    def resumed_review_cells(
        adapter: ReviewAdapter,
        cells: list[ReviewCell],
        *,
        concurrency: int,
        reporter: ReviewProgressReporter | None = None,
        on_result: ReviewCallback | None = None,
    ) -> dict[str, ReviewAdapterResult | ReviewAdapterError]:
        del adapter, concurrency, reporter
        assert on_result is not None
        resumed_cell_ids.extend(cell.id for cell in cells)
        for cell in cells:
            on_result(cell, ReviewAdapterResult(cell_id=cell.id, comments=()))
        return {cell.id: ReviewAdapterResult(cell_id=cell.id, comments=()) for cell in cells}

    monkeypatch.setattr(cli, "review_cells_concurrently", resumed_review_cells)

    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])

    resumed_output = json.loads(capsys.readouterr().out)
    assert reviewed_cell_id not in resumed_cell_ids
    assert set(resumed_cell_ids) == set(rows_by_id) - {reviewed_cell_id}
    assert resumed_output["reviewed_cells"] == len(rows_by_id) - 1
    assert resumed_output["coverage"] == {"reviewed": len(rows_by_id)}
