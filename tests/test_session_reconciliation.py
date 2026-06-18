import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import file_digests


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


def _cell_rows_for_path(tmp_path: Path, path: str) -> list[dict[str, object]]:
    return [dict(row) for row in SessionStore(tmp_path).list_cells() if row["file_path"] == path]


def _reviewed_cell_ids(tmp_path: Path) -> set[str]:
    return {
        str(row["cell_id"])
        for row in SessionStore(tmp_path).list_cells()
        if row["state"] == "reviewed"
    }


def _cell_states_by_path(tmp_path: Path) -> dict[str, set[str]]:
    states: dict[str, set[str]] = {}
    for row in SessionStore(tmp_path).list_cells():
        states.setdefault(str(row["file_path"]), set()).add(str(row["state"]))
    return states


def _finding_id(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select finding_id from findings").fetchone()[0])


def test_session_store_refresh_file_digest_preserves_sibling_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    store = SessionStore(tmp_path)
    rows = _cell_rows_for_path(tmp_path, "app.py")
    assert len(rows) > 1
    reviewed_cell = str(rows[0]["cell_id"])
    stale_cell = str(rows[1]["cell_id"])
    store.update_cell_state(store.active_session_id(), reviewed_cell, CellState.REVIEWED)
    store.update_cell_state(store.active_session_id(), stale_cell, CellState.STALE)

    store.refresh_file_digest(store.active_session_id(), "app.py", "new-digest")

    refreshed = _cell_rows_for_path(tmp_path, "app.py")
    states_by_id = {str(row["cell_id"]): str(row["state"]) for row in refreshed}
    assert {str(row["content_digest"]) for row in refreshed} == {"new-digest"}
    assert states_by_id[reviewed_cell] == "reviewed"
    assert states_by_id[stale_cell] == "stale"
    with pytest.raises(LookupError):
        store.refresh_file_digest(store.active_session_id(), "missing.py", "digest")
    with pytest.raises(LookupError):
        store.refresh_file_digest("missing-session", "app.py", "digest")


def test_review_refreshes_targeted_file_siblings_without_staling_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    before_rows = _cell_rows_for_path(tmp_path, "app.py")
    assert len(before_rows) > 1
    fixture = _empty_fixture(tmp_path)
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
    capsys.readouterr()
    reviewed_before_rows = _cell_rows_for_path(tmp_path, "app.py")
    before_digest = str(reviewed_before_rows[0]["content_digest"])

    (tmp_path / "app.py").write_text("print('changed')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    capsys.readouterr()
    main(["review", str(tmp_path), "--fixture", str(fixture), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    after_rows = _cell_rows_for_path(tmp_path, "app.py")
    assert data["reviewed_cells"] == 1
    current_digest = file_digests(tmp_path)["app.py"]
    assert {str(row["content_digest"]) for row in after_rows} == {current_digest}
    assert current_digest != before_digest
    assert {str(row["state"]) for row in after_rows} == {"pending", "reviewed"}
    assert data["coverage"].get("stale", 0) == 0


def test_incidental_changed_file_stales_while_target_file_siblings_do_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("print('other')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    app_cell = _first_cell_id_for_path(tmp_path, "app.py")
    issue_fixture = tmp_path / "issue-fixture.json"
    issue_fixture.write_text(
        json.dumps(
            {
                app_cell: [
                    {
                        "path": "app.py",
                        "content": "Code issue",
                        "existing_code": "print('hello')",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    main(
        [
            "review",
            str(tmp_path),
            "--fixture",
            str(issue_fixture),
            "--budget",
            "50",
            "--format",
            "json",
        ]
    )
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()
    fixture = _empty_fixture(tmp_path)

    (tmp_path / "app.py").write_text("print('target changed')\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("print('incidental changed')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    capsys.readouterr()
    main(
        [
            "verify-fixes",
            str(tmp_path),
            "--fixture",
            str(fixture),
            "--finding",
            finding_id,
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    states_by_path = _cell_states_by_path(tmp_path)
    assert states_by_path["app.py"] == {"reviewed", "stale"}
    assert states_by_path["other.py"] == {"stale"}
    assert data["coverage"].get("stale", 0) > 0
    assert "review cells are stale after target changes" in data["finalize_blockers"]


def test_reconcile_adds_new_pending_cells_for_changed_universe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
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
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    fixture = _empty_fixture(tmp_path)
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()

    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"].get("stale", 0) > 0


def test_reconcile_stales_fixed_pending_path_digest_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    cell_id = _first_cell_id_for_path(tmp_path, "README.md")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                cell_id: [
                    {
                        "path": "README.md",
                        "content": "Docs issue",
                        "existing_code": "# docs",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    main(["mark", str(tmp_path), _finding_id(tmp_path), "fixed", "--format", "json"])
    capsys.readouterr()

    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"].get("stale", 0) > 0
    assert _cell_states_by_path(tmp_path)["README.md"] == {"stale"}


def test_reconcile_stales_incidental_and_fixed_pending_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    readme_cell = _first_cell_id_for_path(tmp_path, "README.md")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                readme_cell: [
                    {
                        "path": "README.md",
                        "content": "Docs issue",
                        "existing_code": "# docs",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    main(["mark", str(tmp_path), _finding_id(tmp_path), "fixed", "--format", "json"])
    capsys.readouterr()

    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('changed')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    states_by_path = _cell_states_by_path(tmp_path)
    assert data["coverage"].get("stale", 0) > 0
    assert states_by_path["README.md"] == {"stale"}
    assert states_by_path["app.py"] == {"stale"}
    assert "review cells are stale after target changes" in data["finalize_blockers"]


def test_successful_stale_rereview_refreshes_digest_and_advances_to_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
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
    main(["init", str(tmp_path), "--format", "json"])
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
