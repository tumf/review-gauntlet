import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.session_store import SessionStore


def _empty_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    return fixture


def _row_for_cell(tmp_path: Path, cell_id: str) -> dict[str, object]:
    rows = [dict(row) for row in SessionStore(tmp_path).list_cells()]
    for row in rows:
        if row["cell_id"] == cell_id:
            return row
    raise AssertionError(f"missing review cell: {cell_id}")


def _first_cell_id_for_path(tmp_path: Path, path: str) -> str:
    for row in SessionStore(tmp_path).list_cells():
        if row["file_path"] == path:
            return str(row["cell_id"])
    raise AssertionError(f"missing review cell for {path}")


def _reviewed_cell_ids(tmp_path: Path) -> set[str]:
    return {
        str(row["cell_id"])
        for row in SessionStore(tmp_path).list_cells()
        if row["state"] == "reviewed"
    }


def test_reconcile_adds_new_pending_cells_for_changed_universe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    fixture = _empty_fixture(tmp_path)
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()

    (tmp_path / "src.py").write_text("print('hello')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"].get("pending", 0) > 0
    assert any(row["file_path"] == "src.py" for row in SessionStore(tmp_path).list_cells())


def test_reconcile_marks_modified_reviewed_cells_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    fixture = _empty_fixture(tmp_path)
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()

    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"].get("stale", 0) > 0


def test_successful_stale_rereview_refreshes_digest_and_advances_to_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    cell_id = _first_cell_id_for_path(tmp_path, "README.md")
    initial_digest = str(_row_for_cell(tmp_path, cell_id)["content_digest"])
    fixture = _empty_fixture(tmp_path)

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])
    capsys.readouterr()
    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    (tmp_path / "src.py").write_text("print('pending')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    stale_data = json.loads(capsys.readouterr().out)
    stale_row = _row_for_cell(tmp_path, cell_id)
    stale_count = int(stale_data["coverage"].get("stale", 0))
    assert stale_count > 0
    assert stale_data["coverage"].get("pending", 0) > 0
    assert stale_row["state"] == "stale"
    assert stale_row["content_digest"] == initial_digest

    rereview_budget = 999
    main(
        [
            "review",
            str(tmp_path),
            "--fixture",
            str(fixture),
            "--budget",
            str(rereview_budget),
            "--format",
            "json",
        ]
    )
    refreshed_data = json.loads(capsys.readouterr().out)
    refreshed_row = _row_for_cell(tmp_path, cell_id)
    refreshed_digest = str(refreshed_row["content_digest"])
    assert refreshed_data["reviewed_cells"] > stale_count
    assert refreshed_data["coverage"].get("pending", 0) == 0
    assert refreshed_row["state"] == "reviewed"
    assert refreshed_digest != initial_digest

    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    reconciled_data = json.loads(capsys.readouterr().out)
    assert reconciled_data["coverage"].get("stale", 0) == 0
    assert _row_for_cell(tmp_path, cell_id)["content_digest"] == refreshed_digest
    assert len(_reviewed_cell_ids(tmp_path)) == refreshed_data["reviewed_cells"]


def test_file_change_after_digest_refresh_still_marks_reviewed_cell_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    cell_id = _first_cell_id_for_path(tmp_path, "README.md")
    fixture = _empty_fixture(tmp_path)

    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])
    capsys.readouterr()
    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])
    capsys.readouterr()
    refreshed_digest = str(_row_for_cell(tmp_path, cell_id)["content_digest"])

    (tmp_path / "README.md").write_text("# changed again\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    row = _row_for_cell(tmp_path, cell_id)
    assert data["coverage"].get("stale", 0) > 0
    assert row["state"] == "stale"
    assert row["content_digest"] == refreshed_digest
