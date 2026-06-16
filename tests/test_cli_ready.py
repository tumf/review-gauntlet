import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import pytest

import review_gauntlet.cli as cli
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


def _init_commit_target_session(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    _init_git_repo(root)
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "initial")
    (root / "README.md").write_text("# docs\n\nreview target\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "update docs")
    commit = _git(root, "rev-parse", "HEAD")
    main(["init", str(root), "--commit", commit, "--format", "json"])
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
    assert "file_path:" in prompt or "Commit intended git changes" in prompt
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
    _assert_skill_directed_short_prompt(prompt, "pending review cells need coverage")

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
    _assert_skill_directed_short_prompt(prompt, "pending review cells need coverage")


def test_ready_skips_empty_finding_bucket_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.REVIEWED)
    _insert_finding(tmp_path, FindingState.CONFIRMED, 1)

    def empty_ready_findings(_store: object, _session_id: str) -> tuple[Any, ...]:
        return ()

    monkeypatch.setattr(cli, "_ready_findings", empty_ready_findings)

    result = _ready_json_exits(tmp_path, capsys, expected_code=1)

    assert result == {"prompt": None}


@pytest.mark.parametrize("aggregate_state", (CellState.PENDING, CellState.STALE))
def test_ready_skips_empty_review_cell_bucket_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    aggregate_state: CellState,
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.REVIEWED)

    def drifted_coverage(_store: object, _session_id: str, _root: Path) -> dict[str, int]:
        return {aggregate_state.value: 1}

    def fail_if_empty_review_cell_prompt_is_requested(
        *,
        reason: str,
        review_cells: tuple[Any, ...],
        findings: tuple[Any, ...],
        state: CellState,
    ) -> str:
        raise AssertionError(
            "empty materialized review-cell bucket must not request a prompt: "
            f"reason={reason} state={state.value} review_cells={review_cells} findings={findings}"
        )

    monkeypatch.setattr(cli, "_effective_current_target_coverage", drifted_coverage)
    monkeypatch.setattr(
        cli,
        "_review_cell_ready_prompt",
        fail_if_empty_review_cell_prompt_is_requested,
    )

    result = _ready_json_exits(tmp_path, capsys, expected_code=1)

    assert result == {"prompt": None}


@pytest.mark.parametrize("aggregate_state", (CellState.PENDING, CellState.STALE))
def test_ready_falls_through_from_empty_review_cell_bucket_to_next_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    aggregate_state: CellState,
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.REVIEWED)
    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)

    def drifted_coverage(_store: object, _session_id: str, _root: Path) -> dict[str, int]:
        return {aggregate_state.value: 1}

    monkeypatch.setattr(cli, "_effective_current_target_coverage", drifted_coverage)

    prompt = _ready_prompt(tmp_path, capsys)

    _assert_skill_directed_short_prompt(prompt, "untriaged findings need triage")
    assert "pending review cells need coverage" not in prompt
    assert "stale review cells need refreshed coverage" not in prompt


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
    assert "reopened findings need re-triage" in prompt

    _set_all_cells(tmp_path, CellState.PENDING)
    assert "pending review cells need coverage" in _ready_prompt(tmp_path, capsys)

    _set_all_cells(tmp_path, CellState.REVIEWED)
    assert "reopened findings need re-triage" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.REOPENED.value,))
    assert "untriaged findings need triage" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.UNTRIAGED.value,))
    assert "confirmed findings need fixing or re-triage" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from findings where state = ?", (FindingState.CONFIRMED.value,))
    assert "fixed-pending findings need verification" in _ready_prompt(tmp_path, capsys)

    with SessionStore(tmp_path).connect() as conn:
        conn.execute(
            "delete from findings where state = ?",
            (FindingState.FIXED_PENDING_VERIFICATION.value,),
        )

    _set_all_cells(tmp_path, CellState.STALE)
    assert "stale review cells need refreshed coverage" in _ready_prompt(tmp_path, capsys)

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


def test_ready_prioritizes_pending_review_before_dirty_finalize_blocker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_git_repo(tmp_path)
    _init_session(tmp_path, capsys)
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "initial")
    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "pending review cells need coverage")
    assert "Commit intended git changes before finalizing" not in prompt


def test_ready_prompts_commit_when_finalize_blocked_by_dirty_git_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_git_repo(tmp_path)
    _init_session(tmp_path, capsys)
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "initial")

    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    _mark_finalize_ready(tmp_path)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Commit intended git changes before finalizing")

    _git(tmp_path, "add", "package.json")
    _git(tmp_path, "commit", "-m", "add non-review dirty file")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    _mark_finalize_ready(tmp_path)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "Commit intended git changes before finalizing")


def test_ready_prompts_commit_when_finalize_blocked_by_dirty_review_universe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "dirty.py").write_text("print('dirty')\n", encoding="utf-8")

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


def test_status_prioritizes_pending_review_cells_before_untriaged_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.PENDING.value: 1}
    assert data["finding_state_counts"] == {FindingState.UNTRIAGED.value: 1}
    assert data["next_required_action"] == "run_review"
    assert data["finalize_blockers"] == [
        "review cells are still pending",
        "findings remain untriaged",
        "no review run has been completed",
    ]


def test_status_prioritizes_pending_review_cells_before_confirmed_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.CONFIRMED, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.PENDING.value: 1}
    assert data["finding_state_counts"] == {FindingState.CONFIRMED.value: 1}
    assert data["next_required_action"] == "run_review"
    assert data["finalize_blockers"] == [
        "review cells are still pending",
        "findings remain confirmed",
        "no review run has been completed",
    ]


def test_status_prioritizes_confirmed_findings_before_stale_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)
    _insert_finding(tmp_path, FindingState.CONFIRMED, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["finding_state_counts"] == {FindingState.CONFIRMED.value: 1}
    assert data["next_required_action"] == "fix_confirmed_findings"
    assert data["finalize_blockers"] == [
        "review cells are stale after target changes",
        "findings remain confirmed",
        "no review run has been completed",
    ]


def test_status_prioritizes_untriaged_findings_before_stale_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)
    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["finding_state_counts"] == {FindingState.UNTRIAGED.value: 1}
    assert data["next_required_action"] == "triage_findings"
    assert data["finalize_blockers"] == [
        "review cells are stale after target changes",
        "findings remain untriaged",
        "no review run has been completed",
    ]


def test_status_prioritizes_reopened_findings_before_stale_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)
    _insert_finding(tmp_path, FindingState.REOPENED, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["finding_state_counts"] == {FindingState.REOPENED.value: 1}
    assert data["next_required_action"] == "triage_findings"
    assert data["finalize_blockers"] == [
        "review cells are stale after target changes",
        "findings remain reopened",
        "no review run has been completed",
    ]


def test_status_keeps_stale_only_review_cells_reachable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["finding_state_counts"] == {}
    assert data["next_required_action"] == "run_review"
    assert data["finalize_blockers"] == [
        "review cells are stale after target changes",
        "no review run has been completed",
    ]


def test_ready_keeps_stale_only_review_cells_reachable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "stale review cells need refreshed coverage")


def test_status_reports_reviewed_current_cell_as_stale_after_digest_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "README.md").write_text("# docs\n\nreview target changed\n", encoding="utf-8")
    before = _ledger_snapshot(tmp_path)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["next_required_action"] == "run_review"
    assert "review cells are stale after target changes" in data["finalize_blockers"]
    assert _ledger_snapshot(tmp_path) == before
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_status_keeps_digest_drift_as_finalize_blocker_when_coverage_is_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "unrelated.py").write_text("print('drift')\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.py")
    _git(tmp_path, "commit", "-m", "add unrelated file")
    before = _ledger_snapshot(tmp_path)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.REVIEWED.value: 1}
    assert data["can_finalize"] is False
    assert data["finalize_blockers"] == ["target digest has changed since the last review run"]
    assert data["next_required_action"] == "resolve_finalize_blockers"
    assert _ledger_snapshot(tmp_path) == before
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_status_prioritizes_pending_review_cells_before_fixed_pending_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.PENDING.value: 1}
    assert data["finding_state_counts"] == {FindingState.FIXED_PENDING_VERIFICATION.value: 1}
    assert data["next_required_action"] == "run_review"
    assert data["finalize_blockers"] == [
        "review cells are still pending",
        "fixed findings require verification",
        "no review run has been completed",
    ]


def test_status_prioritizes_fixed_pending_findings_before_stale_review_cells(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.STALE.value: 1}
    assert data["finding_state_counts"] == {FindingState.FIXED_PENDING_VERIFICATION.value: 1}
    assert data["next_required_action"] == "run_verify_fixes"
    assert data["finalize_blockers"] == [
        "review cells are stale after target changes",
        "fixed findings require verification",
        "no review run has been completed",
    ]


def test_status_prioritizes_review_when_current_target_cell_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)
    (tmp_path / "unrelated.py").write_text("print('drift')\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.py")
    _git(tmp_path, "commit", "-m", "add unrelated file")
    with SessionStore(tmp_path).connect() as conn:
        conn.execute("delete from review_cells")
    before = _ledger_snapshot(tmp_path)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.PENDING.value: 1}
    assert data["finding_state_counts"] == {FindingState.FIXED_PENDING_VERIFICATION.value: 1}
    assert data["next_required_action"] == "run_review"
    assert data["finalize_blockers"] == [
        "review cells are still pending",
        "fixed findings require verification",
        "target digest has changed since the last review run",
    ]
    assert _ledger_snapshot(tmp_path) == before


def test_status_prioritizes_fixed_pending_findings_when_only_whole_digest_drifted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)
    (tmp_path / "unrelated.py").write_text("print('drift')\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.py")
    _git(tmp_path, "commit", "-m", "add unrelated file")
    before = _ledger_snapshot(tmp_path)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.REVIEWED.value: 1}
    assert data["finding_state_counts"] == {FindingState.FIXED_PENDING_VERIFICATION.value: 1}
    assert data["next_required_action"] == "run_verify_fixes"
    assert data["finalize_blockers"] == [
        "fixed findings require verification",
        "target digest has changed since the last review run",
    ]
    assert _ledger_snapshot(tmp_path) == before


def test_ready_has_no_task_for_digest_drift_only_blocker_without_mutating_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    (tmp_path / "unrelated.py").write_text("print('drift')\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.py")
    _git(tmp_path, "commit", "-m", "add unrelated file")
    before = _ledger_snapshot(tmp_path)

    data = _ready_json_exits(tmp_path, capsys, expected_code=1)

    assert data == {"prompt": None}
    assert _ledger_snapshot(tmp_path) == before
    assert not (tmp_path / ".review-gauntlet" / "checkpoints" / "latest").exists()


def test_ready_prompts_are_skill_directed_and_avoid_coordination_metadata(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "pending review cells need coverage")

    _insert_finding(tmp_path, FindingState.UNTRIAGED, 1)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "pending review cells need coverage")

    _set_all_cells(tmp_path, CellState.REVIEWED)
    prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "untriaged findings need triage")


def test_ready_prompts_review_for_incomplete_coverage_before_confirmed_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.CONFIRMED, 1)

    pending_prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert pending_prompt is not None
    _assert_skill_directed_short_prompt(pending_prompt, "pending review cells need coverage")
    assert "confirmed findings need fixing or re-triage" not in pending_prompt

    _set_all_cells(tmp_path, CellState.STALE)
    stale_prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert stale_prompt is not None
    _assert_skill_directed_short_prompt(stale_prompt, "confirmed findings need fixing or re-triage")
    assert "stale review cells need refreshed coverage" not in stale_prompt


def test_ready_prompts_review_for_incomplete_coverage_before_fixed_pending_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)

    pending_prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert pending_prompt is not None
    _assert_skill_directed_short_prompt(pending_prompt, "pending review cells need coverage")
    assert "fixed-pending findings need verification" not in pending_prompt

    _set_all_cells(tmp_path, CellState.STALE)
    stale_prompt = _ready_json(tmp_path, capsys)["prompt"]
    assert stale_prompt is not None
    _assert_skill_directed_short_prompt(stale_prompt, "fixed-pending findings need verification")
    assert "stale review cells need refreshed coverage" not in stale_prompt


def test_ready_prompts_verify_fixes_when_stale_cells_coexist_with_fixed_pending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.STALE)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "fixed-pending findings need verification")
    assert "stale review cells need refreshed coverage" not in prompt


def test_ready_prompts_verify_fixes_when_only_whole_digest_drifted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_commit_target_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)
    (tmp_path / "unrelated.py").write_text("print('drift')\n", encoding="utf-8")
    _git(tmp_path, "add", "unrelated.py")
    _git(tmp_path, "commit", "-m", "add unrelated file")
    before = _ledger_snapshot(tmp_path)

    prompt = _ready_json(tmp_path, capsys)["prompt"]

    assert prompt is not None
    _assert_skill_directed_short_prompt(prompt, "fixed-pending findings need verification")
    assert "Review target changes" not in prompt
    assert "target digest" not in prompt.lower()
    assert _ledger_snapshot(tmp_path) == before


def test_status_keeps_verify_fixes_when_coverage_is_current(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _mark_finalize_ready(tmp_path)
    _insert_finding(tmp_path, FindingState.FIXED_PENDING_VERIFICATION, 1)

    main(["status", str(tmp_path), "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["coverage"] == {CellState.REVIEWED.value: 1}
    assert data["finding_state_counts"] == {FindingState.FIXED_PENDING_VERIFICATION.value: 1}
    assert data["finalize_blockers"] == ["fixed findings require verification"]
    assert data["next_required_action"] == "run_verify_fixes"


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
