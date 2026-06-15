import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest

from review_gauntlet.checkpoint import target_from_latest_checkpoint, write_latest_checkpoint
from review_gauntlet.cli import main
from review_gauntlet.session_store import SessionStore


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

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

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
    pointer_path = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    assert pointer_path.is_file()
    assert pointer_path.read_text(encoding="utf-8").strip() == data["checkpoint_id"]
    status = json.loads((checkpoint_dir / "status.json").read_text(encoding="utf-8"))
    assert status["checkpoint_id"] == data["checkpoint_id"]
    assert status["next_required_action"] == "init_next_session"
    assert status["review_base_commit"] == data["review_base_commit"]
    assert not (tmp_path / ".review-gauntlet" / "active-session.json").exists()
    with pytest.raises(SystemExit) as excinfo:
        main(["status", str(tmp_path), "--format", "json"])
    assert excinfo.value.code == 1
    assert "review-gauntlet init" in capsys.readouterr().err


def test_status_blocks_dirty_review_universe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is False
    dirty_blockers = [
        blocker
        for blocker in data["finalize_blockers"]
        if "review-universe files are dirty" in blocker
    ]
    assert dirty_blockers
    assert all("dirty.py" not in blocker for blocker in dirty_blockers)


def test_status_blocks_non_review_dirty_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is False
    assert any("uncommitted non-review files" in blocker for blocker in data["finalize_blockers"])
    assert any("package.json" in blocker for blocker in data["finalize_blockers"])


def test_finalize_allows_non_review_dirty_with_explicit_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["can_finalize"] is True
    assert data["session_state"] == "finalized"
    assert (tmp_path / "package.json").exists()


def test_finalize_blocks_dirty_review_universe_without_writing_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    dirty_blockers = [
        blocker
        for blocker in data["finalize_blockers"]
        if "review-universe files are dirty" in blocker
    ]
    assert dirty_blockers
    assert all("dirty.py" not in blocker for blocker in dirty_blockers)
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_latest_checkpoint_rejects_sidecar_without_schema_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    findings_path = tmp_path / data["checkpoint_dir"] / "findings.json"
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    findings.pop("schema_version")
    findings_path.write_text(json.dumps(findings), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version is not supported"):
        target_from_latest_checkpoint(tmp_path)


def test_latest_checkpoint_rejects_malformed_payload_entries(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    findings_path = tmp_path / data["checkpoint_dir"] / "findings.json"
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    findings["findings"].append(
        {
            "checkpoint_id": data["checkpoint_id"],
            "finding_id": "RGF-malformed",
        }
    )
    findings_path.write_text(json.dumps(findings), encoding="utf-8")

    with pytest.raises(ValueError, match="latest checkpoint is internally inconsistent"):
        target_from_latest_checkpoint(tmp_path)


def test_latest_checkpoint_rejects_invalid_payload_field_types(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    findings_path = tmp_path / data["checkpoint_dir"] / "findings.json"
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    findings["findings"].append(
        {
            "checkpoint_id": data["checkpoint_id"],
            "finding_id": "RGF-malformed",
            "session_id": "RGS-malformed",
            "fingerprint": "fp",
            "state": "not-a-state",
            "path": 123,
            "rule_id": "rule",
            "content": "content",
        }
    )
    findings_path.write_text(json.dumps(findings), encoding="utf-8")

    with pytest.raises(ValueError, match="latest checkpoint is internally inconsistent"):
        target_from_latest_checkpoint(tmp_path)


def test_finalize_rejects_path_unsafe_session_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    store = SessionStore(tmp_path)
    for session_id in ("../evil", "RGS-evil\nmessage"):
        with pytest.raises(ValueError, match="session_id must be a single path-safe segment"):
            write_latest_checkpoint(
                store,
                tmp_path,
                session_id,
                {"session_id": session_id, "coverage": {}, "finding_state_counts": {}},
            )


def test_finalize_restores_previous_checkpoint_when_replacement_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (checkpoint_dir / "marker.txt").write_text("previous\n", encoding="utf-8")
    original_replace = Path.replace

    def fail_tmp_install(self: Path, target: Path) -> Path:
        if target.name == "latest" and self.is_file():
            try:
                content = self.read_text(encoding="utf-8").strip()
                if content:
                    raise OSError("simulated install failure")
            except OSError:
                raise
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_tmp_install)

    with pytest.raises(OSError, match="simulated install failure"):
        main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    assert (checkpoint_dir / "marker.txt").read_text(encoding="utf-8") == "previous\n"
    assert (tmp_path / ".review-gauntlet" / "active-session.json").exists()


def test_finalize_restores_previous_checkpoint_when_cleanup_after_pointer_replace_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_repo(tmp_path)
    _complete_session(tmp_path, capsys)
    checkpoint_dir = tmp_path / ".review-gauntlet" / "checkpoints" / "latest"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    (checkpoint_dir / "marker.txt").write_text("previous\n", encoding="utf-8")
    original_rmtree = shutil.rmtree

    def fail_backup_cleanup(path: Path | str) -> None:
        target = Path(path)
        if target.name.startswith(".latest.bak-"):
            raise RuntimeError("simulated cleanup failure")
        original_rmtree(path)

    monkeypatch.setattr(shutil, "rmtree", fail_backup_cleanup)

    with pytest.raises(RuntimeError, match="simulated cleanup failure"):
        main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

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

    main(["finalize", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

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
