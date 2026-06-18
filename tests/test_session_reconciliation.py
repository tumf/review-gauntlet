import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.session_store import SessionStore


def _empty_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    return fixture


def test_reconcile_adds_new_current_cells_without_stale_states(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    main(["review", str(tmp_path), "--fixture", str(_empty_fixture(tmp_path)), "--format", "json"])
    capsys.readouterr()

    (tmp_path / "src.py").write_text("print('new')\n", encoding="utf-8")
    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert "stale" not in data["coverage"]
    assert "superseded" not in data["coverage"]
    assert data["coverage"].get("pending", 0) > 0


def test_changed_reviewed_file_remains_reviewed_in_two_phase_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    main(["review", str(tmp_path), "--fixture", str(_empty_fixture(tmp_path)), "--format", "json"])
    capsys.readouterr()

    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["status", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"].get(CellState.REVIEWED.value, 0) > 0
    assert "stale" not in data["coverage"]


def test_refresh_file_digest_updates_all_cells_for_path(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    cells = (
        CellState.PENDING,
        CellState.REVIEWED,
    )
    review_cells = tuple(
        ReviewCell(
            id=f"RGC-{index}",
            file_path="README.md",
            rule_id=f"rule-{index}",
            slice_id="docs",
            state=state,
            content_digest="old",
        )
        for index, state in enumerate(cells, start=1)
    )
    store.create_session({"session_id": "RGS-test", "target_digest": "d", "target": {}}, review_cells)

    store.refresh_file_digest("RGS-test", "README.md", "new")

    rows = store.list_cells("RGS-test")
    assert {str(row["content_digest"]) for row in rows} == {"new"}
    assert {str(row["state"]) for row in rows} == {"pending", "reviewed"}
