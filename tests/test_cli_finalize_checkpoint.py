import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest

from review_gauntlet.cli import main


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    _git(root, "add", "app.py")
    _git(root, "commit", "-m", "initial")


def _complete_session(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    main(["init", str(root), "--all", "--format", "json"])
    init_data = json.loads(capsys.readouterr().out)
    fixture_dir = root / "tests"
    fixture_dir.mkdir(exist_ok=True)
    fixture = fixture_dir / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    while True:
        main(["review", str(root), "--fixture", str(fixture), "--budget", "50", "--format", "json"])
        data = json.loads(capsys.readouterr().out)
        if data["coverage"].get("pending", 0) == 0:
            break
    return init_data


def test_finalize_writes_checkpoint_files_and_cleans_active_session(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)

    main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    checkpoint_dir = tmp_path / data["checkpoint_dir"]
    assert data["checkpoint_state"] == "complete"
    assert data["usable_as_review_base"] is True
    assert data["review_base_commit"] == _git(tmp_path, "rev-parse", "HEAD")
    assert data["next_required_action"] == "init_next_session"
    assert {Path(path).name for path in data["generated_files"]} == {
        "status.json",
        "findings.json",
        "events.json",
        "summary.md",
    }
    status = json.loads((checkpoint_dir / "status.json").read_text(encoding="utf-8"))
    assert status["checkpoint_id"] == data["checkpoint_id"]
    assert status["next_required_action"] == "init_next_session"
    assert status["review_base_commit"] == data["review_base_commit"]
    assert not (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    with pytest.raises(SystemExit) as excinfo:
        main(["status", str(tmp_path), "--format", "json"])
    assert excinfo.value.code == 1
    assert "review-gauntlet init" in capsys.readouterr().err


def test_finalize_blocks_dirty_review_universe_without_writing_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert any("dirty.py" in blocker for blocker in data["finalize_blockers"])
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_finalize_restores_previous_checkpoint_when_replacement_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "marker.txt").write_text("previous\n", encoding="utf-8")
    original_rename = Path.rename

    def fail_tmp_install(self: Path, target: Path) -> Path:
        if self.name.startswith(".latest.tmp-") and target.name == "latest":
            raise OSError("simulated install failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_tmp_install)

    with pytest.raises(OSError, match="simulated install failure"):
        main(["finalize", str(tmp_path), "--format", "json"])

    assert (checkpoint_dir / "marker.txt").read_text(encoding="utf-8") == "previous\n"
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_finalize_includes_terminal_findings_and_malformed_nonterminal_event_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    main(["init", str(tmp_path), "--all", "--format", "json"])
    capsys.readouterr()
    cell_id = _first_cell_id(tmp_path)
    fixture_dir = tmp_path / "tests"
    fixture_dir.mkdir(exist_ok=True)
    fixture = fixture_dir / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                cell_id: [
                    {
                        "path": "app.py",
                        "content": "Risk",
                        "existing_code": "print('ok')",
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
    main(["mark", str(tmp_path), finding_id, "false-positive", "--format", "json"])
    capsys.readouterr()
    with sqlite3.connect(tmp_path / ".review-gauntlet" / "ledger.sqlite") as conn:
        conn.execute(
            """
            insert into finding_events(finding_id, from_state, to_state, reason, metadata)
            values (?, ?, ?, ?, ?)
            """,
            (finding_id, "false_positive", "confirmed", "malformed-note", "not-json"),
        )
    _git(tmp_path, "status", "--short")

    main(["finalize", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    checkpoint_dir = tmp_path / data["checkpoint_dir"]
    findings = json.loads((checkpoint_dir / "findings.json").read_text(encoding="utf-8"))
    events = json.loads((checkpoint_dir / "events.json").read_text(encoding="utf-8"))
    assert findings["findings"][0]["state"] == "false_positive"
    assert findings["findings"][0]["latest_occurrence"]["path"] == "app.py"
    assert any(event.get("metadata_raw") == "not-json" for event in events["events"])
    summary = (checkpoint_dir / "summary.md").read_text(encoding="utf-8")
    assert "Review base commit" in summary
    assert "## Coverage" in summary
    assert "## Findings" in summary
    assert "## Triage Events" in summary


def _first_cell_id(root: Path) -> str:
    with sqlite3.connect(root / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select cell_id from review_cells limit 1").fetchone()[0])


def _first_finding_id(root: Path) -> str:
    with sqlite3.connect(root / ".review-gauntlet" / "ledger.sqlite") as conn:
        return str(conn.execute("select finding_id from findings limit 1").fetchone()[0])
