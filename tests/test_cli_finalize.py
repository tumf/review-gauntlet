import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from review_gauntlet.cli import main


def _init_and_review(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    main(["review", str(tmp_path), "--format", "json"])
    capsys.readouterr()


def test_finalize_fails_with_pending_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert exc.value.code == 1
    assert "review cells are still pending" in data["finalize_blockers"]
    assert "no review run has been completed" in data["finalize_blockers"]


def test_finalize_uses_last_reviewed_digest_not_initial_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_and_review(tmp_path, capsys)
    (tmp_path / "README.md").write_text("# changed docs\n", encoding="utf-8")
    main(["review", str(tmp_path), "--format", "json"])
    capsys.readouterr()

    main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is True
    assert data["session_state"] == "finalized"


def test_finalize_fails_for_expired_accepted_risk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()
    cell_id = _first_cell_id(tmp_path)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                cell_id: [
                    {
                        "path": "README.md",
                        "content": "Risk",
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
    finding_id = _first_finding_id(tmp_path)
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    main(
        [
            "mark",
            str(tmp_path),
            finding_id,
            "accepted-risk",
            "--until",
            yesterday,
            "--format",
            "json",
        ]
    )
    capsys.readouterr()

    with pytest.raises(SystemExit):
        main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert "waived or accepted-risk findings have expired" in data["finalize_blockers"]


def _first_cell_id(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select cell_id from review_cells limit 1").fetchone()[0])


def _first_finding_id(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select finding_id from findings limit 1").fetchone()[0])
