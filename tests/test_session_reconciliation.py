import json
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.session_store import SessionStore


def _empty_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    return fixture


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
