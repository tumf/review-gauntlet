import json
import sqlite3
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.findings import normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.session_store import SessionStore


def _init_session(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(tmp_path), "--worktree", "--format", "json"])
    capsys.readouterr()


def _cell_for_path(tmp_path: Path, path: str) -> str:
    store = SessionStore(tmp_path)
    rows = store.list_cells()
    for row in rows:
        if row["file_path"] == path:
            return str(row["cell_id"])
    raise AssertionError(f"missing review cell for {path}")


def _fixture(tmp_path: Path, cell_id: str, content: str = "Missing auth") -> Path:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                cell_id: [
                    {
                        "path": "README.md",
                        "content": content,
                        "existing_code": "# docs",
                        "start_line": 1,
                        "end_line": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return fixture


def _run_count(tmp_path: Path) -> int:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return int(conn.execute("select count(*) from runs").fetchone()[0])


def _finding_state(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select state from findings").fetchone()[0])


def _finding_id(tmp_path: Path) -> str:
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select finding_id from findings").fetchone()[0])


def test_review_advances_once_with_limited_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    main(["review", str(tmp_path), "--budget", "1", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["run_count"] == 1
    assert data["reviewed_cells"] == 1
    assert data["coverage"]["pending"] > 0


def test_mark_updates_finding_without_creating_review_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)

    main(
        [
            "mark",
            str(tmp_path),
            finding_id,
            "confirmed",
            "--reason",
            "real issue",
            "--format",
            "json",
        ]
    )

    data = json.loads(capsys.readouterr().out)
    assert data["state"] == "confirmed"
    assert _finding_state(tmp_path) == "confirmed"
    assert _run_count(tmp_path) == 1


def test_fixed_finding_is_verified_only_when_relevant_path_is_reviewed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--budget", "0", "--format", "json"])
    capsys.readouterr()
    assert _finding_state(tmp_path) == "fixed_pending_verification"

    main(["review", str(tmp_path), "--format", "json"])
    capsys.readouterr()
    assert _finding_state(tmp_path) == "fixed_verified"


def test_fixed_finding_reopens_when_fingerprint_is_seen_again(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    fixture = _fixture(tmp_path, _cell_for_path(tmp_path, "README.md"))
    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()
    finding_id = _finding_id(tmp_path)
    main(["mark", str(tmp_path), finding_id, "fixed", "--format", "json"])
    capsys.readouterr()

    main(["review", str(tmp_path), "--fixture", str(fixture), "--format", "json"])
    capsys.readouterr()

    assert _finding_state(tmp_path) == "reopened"


def test_finding_fingerprint_deduplicates_shifted_line_numbers() -> None:
    first = normalize_ocr_comment(
        OCRComment(
            path="app.py", content="Missing auth", existing_code="guard()", start_line=3, end_line=3
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="digest",
    )
    shifted = normalize_ocr_comment(
        OCRComment(
            path="app.py",
            content="Missing auth",
            existing_code="guard()",
            start_line=90,
            end_line=90,
        ),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="digest",
    )

    assert first.fingerprint == shifted.fingerprint
