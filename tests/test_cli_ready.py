import json
from pathlib import Path

import pytest

from review_gauntlet.cli import RunSnapshotReadinessProvider, main
from review_gauntlet.findings import FindingState
from review_gauntlet.review_cells import CellState
from review_gauntlet.session_store import SessionStore
from review_gauntlet.targets import target_digest


def _init_session(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    main(["init", str(root), "--format", "json"])
    return str(json.loads(capsys.readouterr().out)["session_id"])


def _set_all_cells(root: Path, state: CellState) -> None:
    store = SessionStore(root)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            "update review_cells set state = ? where session_id = ?", (state.value, session_id)
        )


def _insert_finding(root: Path, state: FindingState = FindingState.OPEN) -> None:
    store = SessionStore(root)
    session_id = store.active_session_id()
    with store.connect() as conn:
        conn.execute(
            """
            insert into findings(
                session_id, finding_id, fingerprint, state, path, rule_id, content, metadata
            )
            values (?, 'RGF-0001', 'fp', ?, 'README.md', 'docs-accuracy', 'finding', '{}')
            """,
            (session_id, state.value),
        )


def test_ready_prioritizes_pending_cells_then_open_findings_then_finalize(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _insert_finding(tmp_path)

    main(["ready", str(tmp_path), "--format", "json"])
    prompt = json.loads(capsys.readouterr().out)["prompt"]
    assert "pending review cells need coverage" in prompt

    _set_all_cells(tmp_path, CellState.REVIEWED)
    main(["ready", str(tmp_path), "--format", "json"])
    prompt = json.loads(capsys.readouterr().out)["prompt"]
    assert "open findings need resolution" in prompt
    assert "allowed_target_states: confirmed, dismissed" in prompt
    assert "For open findings, valid targets are confirmed or dismissed only" in prompt
    assert "False positives and other non-issues must be state=dismissed" in prompt
    assert "false_positive, accepted_risk, waived" not in prompt

    with SessionStore(tmp_path).connect() as conn:
        conn.execute("update findings set state = 'dismissed'")
    SessionStore(tmp_path).create_run(
        SessionStore(tmp_path).active_session_id(), target_digest(tmp_path)
    )
    main(["ready", str(tmp_path), "--format", "json"])
    prompt = json.loads(capsys.readouterr().out)["prompt"]
    assert "finalize the review-gauntlet session" in prompt


def test_status_reports_open_findings_as_resolve_action(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    _set_all_cells(tmp_path, CellState.REVIEWED)
    _insert_finding(tmp_path)

    main(["status", str(tmp_path), "--allow-non-review-dirty", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["finding_state_counts"] == {"open": 1}
    assert data["next_required_action"] == "resolve_findings"
    assert data["finalize_blockers"] == ["findings remain open", "no review run has been completed"]


def test_ready_snapshot_provider_reuses_status_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _init_session(tmp_path, capsys)
    provider = RunSnapshotReadinessProvider()
    store = SessionStore(tmp_path)

    status = provider.status_snapshot(store, tmp_path)
    task = provider.ready_prompt(store, tmp_path)

    assert status["next_required_action"] == "run_review"
    assert task is not None
    assert task.next_required_action == "run_review"
