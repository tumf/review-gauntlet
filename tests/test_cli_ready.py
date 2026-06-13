import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from review_gauntlet.cli import main
from review_gauntlet.findings import FindingState
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import target_digest

READY_PREFIX = "Use the review-gauntlet task execution skill."
FORBIDDEN_PROMPT_TERMS = ("task_id", "claim", "release", "queue", "lease")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_git_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")


def _init_session(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(root), "--worktree", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    return str(data["session_id"])


def _ready_json(root: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, str | None]:
    main(["ready", str(root), "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"prompt"}
    prompt = data["prompt"]
    assert prompt is None or isinstance(prompt, str)
    return {"prompt": prompt}


def _ready_json_exits(
    root: Path, capsys: pytest.CaptureFixture[str], expected_code: int
) -> dict[str, str | None]:
    with pytest.raises(SystemExit) as exc_info:
        main(["ready", str(root), "--format", "json"])
    assert exc_info.value.code == expected_code
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"prompt"}
    prompt = data["prompt"]
    assert prompt is None or isinstance(prompt, str)
    return {"prompt": prompt}


def _set_all_cells(root: Path, state: CellState) -> None:
    store = SessionStore(root)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            """
            update review_cells
            set state = ?, content_digest = content_digest
            where session_id = ?
            """,
            (state.value, session_id),
        )


def _insert_finding(root: Path, state: FindingState, suffix: int) -> None:
    store = SessionStore(root)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
              session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            ) values (?, ?, ?, ?, 'README.md', 'docs-accuracy', 'finding', '{}')
            """,
            (session_id, f"RGF-{suffix:04d}", f"fingerprint-{suffix}", state.value),
        )


def _mark_finalize_ready(root: Path) -> None:
    _set_all_cells(root, CellState.REVIEWED)
    store = SessionStore(root)
    store.create_run(store.active_session_id(), target_digest(root))


def _ready_prompt(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    prompt = _ready_json(root, capsys)["prompt"]
    assert prompt is not None
    return prompt


def _ledger_snapshot(root: Path) -> dict[str, object]:
    ledger = root / ".review-gauntlet" / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        return {
            "counts": {
                table: conn.execute(f"select count(*) from {table}").fetchone()[0]
                for table in ("runs", "finding_events", "findings", "review_cells")
            },
            "runs": conn.execute(
                "select run_id, session_id, target_digest from runs order by run_id"
            ).fetchall(),
            "findings": conn.execute(
                "select finding_id, state from findings order by finding_id"
            ).fetchall(),
            "cells": conn.execute(
                "select cell_id, state, content_digest from review_cells order by cell_id"
            ).fetchall(),
        }


def _assert_skill_directed_short_prompt(prompt: str, expected_phrase: str) -> None:
    assert prompt.startswith(READY_PREFIX)
    assert expected_phrase in prompt
    assert len(prompt) < 260
    lowered = prompt.lower()
    for forbidden in FORBIDDEN_PROMPT_TERMS:
        assert forbidden not in lowered


def test_ready_command_outputs_prompt_only_json_and_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    data = _ready_json(tmp_path, capsys)
    prompt = data["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Review pending review cells")

    main(["ready", str(tmp_path), "--format", "text"])
    text = capsys.readouterr().out.strip()
    assert text == prompt
    assert "prompt:" not in text
    assert "{" not in text


def test_ready_actionable_prompt_returns_success_without_system_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    result = main(["ready", str(tmp_path), "--format", "json"])

    assert result is None
    data = json.loads(capsys.readouterr().out)
    prompt = data["prompt"]
    assert isinstance(prompt, str)
    _assert_skill_directed_short_prompt(prompt, "Review pending review cells")


def test_ready_priority_order_is_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)
    _insert_finding(tmp_path, FindingState.CONFIRMED, 2)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 3)
    _insert_finding(tmp_path, FindingState.REOPENED, 4)
    with SessionStore(tmp_path).connect() as conn:
        conn.execute("update review_cells set state = ?", (CellState.STALE.value,))

    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    assert "Re-triage reopened findings" in prompt

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.REOPENED.value,))
    assert "Triage untriaged findings" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.UNTRIAGED.value,))
    assert "Fix the next confirmed finding" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.CONFIRMED.value,))
    assert "Verify fixed-pending findings" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute(
            "delete from findings where state = ?",
            (FindingState.FIXED_PENDING_VERIFICATION.value,),
        )
    assert "Review stale review cells" in _ready_prompt(tmp_path, capsys)

    _set_all_cells(tmp_path, CellState.PENDING)
    assert "Review pending review cells" in _ready_prompt(tmp_path, capsys)

    _mark_finalize_ready(tmp_path)
    finalize_prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert finalize_prompt is not None
    assert "finalize the review-gauntlet session" in finalize_prompt


def test_ready_outputs_no_ready_task_when_only_blockers_remain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.REVIEWED)

    assert _ready_json_exits(tmp_path, capsys, expected_code=1) == {"prompt": None}

    with pytest.raises(SystemExit) as exc_info:
        main(["ready", str(tmp_path), "--format", "text"])
    assert exc_info.value.code == 1
    assert capsys.readouterr().out == "no ready task\n"


def test_ready_prompts_commit_when_finalize_blocked_by_dirty_git_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_git_repo(tmp_path)
    _init_session(tmp_path, capsys)
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "initial")

    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")
    _mark_finalize_ready(tmp_path)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Commit intended git changes before finalizing")

    _git(tmp_path, "add", "dirty.py")
    _git(tmp_path, "commit", "-m", "add review dirty file")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    _mark_finalize_ready(tmp_path)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Commit intended git changes before finalizing")


def test_ready_outputs_no_ready_task_when_only_non_commit_blockers_remain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_git_repo(tmp_path)
    _init_session(tmp_path, capsys)
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "initial")
    _set_all_cells(tmp_path, CellState.REVIEWED)

    assert _ready_json_exits(tmp_path, capsys, expected_code=1) == {"prompt": None}


def test_status_treats_target_digest_drift_as_review_action(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "README.md").write_text("# docs\n\nchanged\n", encoding="utf-8")
    before = _ledger_snapshot(tmp_path)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.REVIEWED.value: 1}
    assert data["finalize_blockers"] == ["target digest has changed since the last review run"]
    assert data["next_required_action"] == "run_review"
    assert _ledger_snapshot(tmp_path) == before
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_ready_prompts_review_for_target_digest_drift_without_mutating_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "README.md").write_text("# docs\n\nchanged\n", encoding="utf-8")
    before = _ledger_snapshot(tmp_path)

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Review target changes")
    assert _ledger_snapshot(tmp_path) == before
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_ready_prompts_are_skill_directed_and_avoid_coordination_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Review pending review cells")

    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Triage untriaged findings")


def test_ready_finalize_prompt_mentions_commit_and_does_not_write_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    assert prompt.startswith(READY_PREFIX)
    assert "Commit intended git changes before finalizing" in prompt
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_ready_is_read_only_for_ledger_and_checkpoint_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)
    ledger = tmp_path / ".review-gauntlet" / "ledger.sqlite"
    with sqlite3.connect(ledger) as conn:
        before_counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in ("runs", "finding_events", "findings", "review_cells")
        }
        before_findings = conn.execute(
            "select finding_id, state from findings order by finding_id"
        ).fetchall()
        before_cells = conn.execute(
            "select cell_id, state, content_digest from review_cells order by cell_id"
        ).fetchall()

    _ready_json(tmp_path, capsys)

    with sqlite3.connect(ledger) as conn:
        after_counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in ("runs", "finding_events", "findings", "review_cells")
        }
        after_findings = conn.execute(
            "select finding_id, state from findings order by finding_id"
        ).fetchall()
        after_cells = conn.execute(
            "select cell_id, state, content_digest from review_cells order by cell_id"
        ).fetchall()
    assert after_counts == before_counts
    assert after_findings == before_findings
    assert after_cells == before_cells
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_ready_does_not_change_status_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)

    main(["status", str(tmp_path), "--format", "json"])
    before = json.loads(capsys.readouterr().out)
    _ready_json(tmp_path, capsys)
    main(["status", str(tmp_path), "--format", "json"])
    after = json.loads(capsys.readouterr().out)

    assert set(after) == set(before)
    assert "prompt" not in after
