import json
from collections.abc import Callable
from pathlib import Path

import pytest

from review_gauntlet.cli import (
    _apply_resolutions,  # pyright: ignore[reportPrivateUsage]
    _continuation_prompt_sections,  # pyright: ignore[reportPrivateUsage]
    main,
    run_session_command_step_for_testing,
)
from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.continuation import continuation_path_for_task
from review_gauntlet.findings import FindingResolution, FindingState, normalize_ocr_comment
from review_gauntlet.ocr_rules import OCRComment
from review_gauntlet.review_cells import ReviewCell
from review_gauntlet.session_store import SessionStore


def test_run_detects_v2_continue_verdict(tmp_path: Path) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    verdict = state_dir / "turns" / "RGS-test" / "open__aaaaaaaaaaaa.json"
    prompt = "\n".join(
        [
            "Before ending this turn, write valid JSON to the following path:",
            str(verdict),
        ]
    )
    script = (
        "import json, pathlib, sys; "
        "p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text(json.dumps({'schema_version':2,'verdict':'continue','summary':'more',"
        "'completed_finding_ids':[],'remaining_finding_ids':['RGF-0001'],'resolutions':[],"
        "'next_turn_instructions':'continue','error':None}))"
    )

    result = run_session_command_step_for_testing(
        config=CommandAdapterConfig(
            type="command", command="python", args=("-c", script, str(verdict))
        ),
        root=tmp_path,
        state_dir=state_dir,
        prompt=prompt,
    )

    assert result.failure is None
    assert result.verdict_metadata is not None
    assert result.verdict_metadata["verdict"] == "continue"


def test_run_treats_abort_verdict_as_failure(tmp_path: Path) -> None:
    state_dir = tmp_path / ".review-gauntlet"
    verdict = state_dir / "turns" / "RGS-test" / "open__aaaaaaaaaaaa.json"
    prompt = "\n".join(
        [
            "Before ending this turn, write valid JSON to the following path:",
            str(verdict),
        ]
    )
    payload = {
        "schema_version": 2,
        "verdict": "abort",
        "summary": "blocked",
        "completed_finding_ids": [],
        "remaining_finding_ids": ["RGF-0001"],
        "resolutions": [],
        "next_turn_instructions": None,
        "error": "blocked",
    }
    script = (
        "import pathlib, sys; "
        "p=pathlib.Path(sys.argv[1]); "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text(sys.argv[2])"
    )

    result = run_session_command_step_for_testing(
        config=CommandAdapterConfig(
            type="command", command="python", args=("-c", script, str(verdict), json.dumps(payload))
        ),
        root=tmp_path,
        state_dir=state_dir,
        prompt=prompt,
    )

    assert result.failure is not None
    assert result.failure["reason"] == "step_verdict_abort"


def _turn_verdict_payload(
    *, state: str = "confirmed", finding_id: str = "RGF-0001"
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "verdict": "finish",
        "summary": "completed useful work",
        "completed_finding_ids": [finding_id],
        "remaining_finding_ids": [],
        "resolutions": [
            {"finding_id": finding_id, "state": state, "dismiss_reason": None},
        ],
        "next_turn_instructions": None,
        "error": None,
    }


def _write_turn_verdict(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _create_session_with_finding(
    tmp_path: Path,
    *,
    session_id: str = "RGS-test",
    finding_state: FindingState = FindingState.OPEN,
    content: str = "Missing auth",
    cell_id: str = "RGC-1",
) -> tuple[SessionStore, str]:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id=cell_id, file_path="src/example.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": session_id, "target_digest": "digest", "target": {}}, (cell,)
    )
    finding_id = _add_finding_to_session(
        store,
        session_id=session_id,
        cell_id=cell.id,
        finding_state=finding_state,
        content=content,
    )
    return store, finding_id


def _add_finding_to_session(
    store: SessionStore,
    *,
    session_id: str = "RGS-test",
    cell_id: str = "RGC-1",
    finding_state: FindingState = FindingState.OPEN,
    content: str = "Missing auth",
) -> str:
    run_id = store.create_run(session_id, "digest")
    finding = normalize_ocr_comment(
        OCRComment(path="src/example.py", content=content, existing_code="return secret"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )
    finding_id = store.upsert_finding(session_id, run_id, cell_id, finding)
    if finding_state != FindingState.OPEN:
        try:
            store.mark_finding(finding_id, state=finding_state, reason="triaged", metadata={})
        except ValueError:
            with store.connect() as conn:
                conn.execute(
                    "update findings set state = ? where finding_id = ?",
                    (finding_state.value, finding_id),
                )
    return finding_id


def _finding_state(store: SessionStore, finding_id: str) -> str:
    with store.connect() as conn:
        row = conn.execute(
            "select state from findings where finding_id = ?", (finding_id,)
        ).fetchone()
    assert row is not None
    return str(row["state"])


def _finding_event_count(store: SessionStore, finding_id: str) -> int:
    with store.connect() as conn:
        row = conn.execute(
            "select count(*) as count from finding_events where finding_id = ?", (finding_id,)
        ).fetchone()
    assert row is not None
    return int(row["count"])


def _missing_turn_verdict_path(root: Path) -> Path:
    return root / ".review-gauntlet" / "turns" / "RGS-test" / "open__aaaaaaaaaaaa.json"


def _unsafe_turn_verdict_path(root: Path) -> Path:
    return root / "bad.json"


def test_validate_turn_verdict_cli_accepts_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    _write_turn_verdict(path, _turn_verdict_payload())

    main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "valid": True,
        "path": str(path),
        "verdict": "finish",
        "resolution_count": 1,
    }


def test_validate_turn_verdict_cli_rejects_fixed_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    _write_turn_verdict(path, _turn_verdict_payload(state="fixed"))

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert output["path"] == str(path)
    assert "invalid continuation verdict schema" in output["error"]
    assert "fixed" in output["error"]


@pytest.mark.parametrize(
    "path_builder, error_fragment",
    [
        (_missing_turn_verdict_path, "missing"),
        (_unsafe_turn_verdict_path, "under .review-gauntlet/turns"),
    ],
)
def test_validate_turn_verdict_cli_reports_actionable_file_and_path_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    path_builder: Callable[[Path], Path],
    error_fragment: str,
) -> None:
    path = path_builder(tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert output["path"] == str(path)
    assert error_fragment in output["error"]


def test_validate_turn_verdict_cli_reports_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert output["path"] == str(path)
    assert "not valid JSON" in output["error"]


def test_validate_turn_verdict_cli_rejects_impossible_active_session_transition(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="src/example.py", rule_id="security", slice_id="src")
    store.create_session(
        {"session_id": "RGS-test", "target_digest": "digest", "target": {}}, (cell,)
    )
    run_id = store.create_run("RGS-test", "digest")
    finding = normalize_ocr_comment(
        OCRComment(path="src/example.py", content="Missing auth", existing_code="return secret"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )
    finding_id = store.upsert_finding("RGS-test", run_id, cell.id, finding)
    store.mark_finding(finding_id, state=FindingState.CONFIRMED, reason="triaged", metadata={})
    path = continuation_path_for_task(store.state_dir, "RGS-test", "open", "src/example.py")
    _write_turn_verdict(path, _turn_verdict_payload(state="dismissed", finding_id=finding_id))

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert "invalid finding transition" in output["error"]
    assert "active session RGS-test" in output["error"]
    assert f"finding_id={finding_id}" in output["error"]
    assert "current_state=confirmed" in output["error"]
    assert "requested_state=dismissed" in output["error"]
    assert "attempted transition confirmed -> dismissed" in output["error"]
    assert "current state confirmed is terminal; no transitions are allowed" in output["error"]


def test_validate_turn_verdict_cli_reports_open_false_positive_transition_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store, finding_id = _create_session_with_finding(tmp_path)
    path = continuation_path_for_task(store.state_dir, "RGS-test", "open", "src/example.py")
    _write_turn_verdict(path, _turn_verdict_payload(state="false_positive", finding_id=finding_id))

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert "active session RGS-test" in output["error"]
    assert f"finding_id={finding_id}" in output["error"]
    assert "current_state=open" in output["error"]
    assert "requested_state=false_positive" in output["error"]
    assert "attempted transition open -> false_positive" in output["error"]
    assert "allowed target states for current state open: confirmed, dismissed" in output["error"]


@pytest.mark.parametrize("terminal_state", [FindingState.DISMISSED, FindingState.FALSE_POSITIVE])
def test_validate_turn_verdict_cli_accepts_idempotent_terminal_noop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], terminal_state: FindingState
) -> None:
    store, finding_id = _create_session_with_finding(tmp_path, finding_state=terminal_state)
    path = continuation_path_for_task(store.state_dir, "RGS-test", "open", "src/example.py")
    _write_turn_verdict(
        path, _turn_verdict_payload(state=terminal_state.value, finding_id=finding_id)
    )

    main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["active_session_id"] == "RGS-test"
    assert output["verdict_session_id"] == "RGS-test"
    assert output["valid_resolution_count"] == 0
    assert output["ignored_resolution_count"] == 1
    assert output["ignored_resolutions"] == [
        {
            "finding_id": finding_id,
            "current_state": terminal_state.value,
            "requested_state": terminal_state.value,
            "reason": "idempotent_terminal_noop",
        }
    ]


@pytest.mark.parametrize(
    ("current_state", "requested_state"),
    [
        (FindingState.CONFIRMED, "dismissed"),
        (FindingState.FALSE_POSITIVE, "dismissed"),
    ],
)
def test_validate_turn_verdict_cli_rejects_terminal_semantic_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    current_state: FindingState,
    requested_state: str,
) -> None:
    store, finding_id = _create_session_with_finding(tmp_path, finding_state=current_state)
    path = continuation_path_for_task(store.state_dir, "RGS-test", "open", "src/example.py")
    _write_turn_verdict(path, _turn_verdict_payload(state=requested_state, finding_id=finding_id))

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert output["valid"] is False
    assert output["finding_id"] == finding_id
    assert output["current_state"] == current_state.value
    assert output["requested_state"] == requested_state
    assert output["allowed_target_states"] == []
    assert output["terminal_current_state"] is True
    assert f"attempted transition {current_state.value} -> {requested_state}" in output["error"]


def test_validate_turn_verdict_cli_reports_mismatched_verdict_session_context(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store, finding_id = _create_session_with_finding(tmp_path, session_id="RGS-active")
    path = continuation_path_for_task(store.state_dir, "RGS-stale", "open", "src/example.py")
    _write_turn_verdict(path, _turn_verdict_payload(state="confirmed", finding_id=finding_id))

    main(["validate-turn-verdict", str(path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["active_session_id"] == "RGS-active"
    assert output["verdict_session_id"] == "RGS-stale"
    assert output["session_mismatch"] is True


def test_apply_resolutions_ignores_terminal_noops_and_preserves_mixed_progress(
    tmp_path: Path,
) -> None:
    store, open_finding_id = _create_session_with_finding(tmp_path, content="Open issue")
    with store.connect() as conn:
        conn.execute(
            """
            insert into review_cells(
              session_id, cell_id, file_path, rule_id, slice_id, state, content_digest
            ) values (
              'RGS-test', 'RGC-2', 'src/example.py', 'security', 'src', 'reviewed', 'digest'
            )
            """
        )
    terminal_finding_id = _add_finding_to_session(
        store,
        finding_state=FindingState.FALSE_POSITIVE,
        content="Already false positive",
        cell_id="RGC-2",
    )
    terminal_events_before = _finding_event_count(store, terminal_finding_id)

    resolved = _apply_resolutions(
        store,
        (
            FindingResolution(
                finding_id=open_finding_id,
                state="dismissed",
                dismiss_reason="done",
            ),
            FindingResolution(
                finding_id=terminal_finding_id,
                state="false_positive",
                dismiss_reason=None,
            ),
        ),
    )

    assert resolved == [open_finding_id]
    assert _finding_state(store, open_finding_id) == "dismissed"
    assert _finding_state(store, terminal_finding_id) == "false_positive"
    assert _finding_event_count(store, terminal_finding_id) == terminal_events_before


@pytest.mark.parametrize("target_state", ["confirmed", "dismissed"])
def test_resolve_valid_open_finding_resolution_updates_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], target_state: str
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("def example():\n    return 1\n", encoding="utf-8")
    store = SessionStore(tmp_path)
    cell = ReviewCell(id="RGC-1", file_path="src/example.py", rule_id="security", slice_id="src")
    store.create_session(
        {
            "session_id": "RGS-test",
            "target_digest": "digest",
            "target": {
                "kind": "all",
                "base_ref": None,
                "head_ref": None,
                "commit": None,
                "head_mode": "moving",
            },
        },
        (cell,),
    )
    with store.connect() as conn:
        conn.execute("update review_cells set state = 'reviewed' where session_id = 'RGS-test'")
    run_id = store.create_run("RGS-test", "digest")
    finding = normalize_ocr_comment(
        OCRComment(path="src/example.py", content="Potential issue", existing_code="return 1"),
        repository_id="repo",
        base_target="target",
        rule_id="security",
        ruleset_digest="rules",
    )
    finding_id = store.upsert_finding("RGS-test", run_id, cell.id, finding)
    script = """
import json
import pathlib
import sys
prompt = sys.argv[1]
state = sys.argv[2]
lines = prompt.splitlines()
verdict_path = None
finding_id = None
for index, line in enumerate(lines):
    if line.strip() == "Before ending this turn, write valid JSON to the following path:":
        verdict_path = lines[index + 1].strip()
    if "finding_id:" in line:
        finding_id = line.split("finding_id:", 1)[1].split(";", 1)[0].strip()
if verdict_path is None or finding_id is None:
    raise SystemExit("missing prompt data")
payload = {
    "schema_version": 2,
    "verdict": "finish",
    "summary": f"resolved {finding_id} as {state}",
    "completed_finding_ids": [finding_id],
    "remaining_finding_ids": [],
    "resolutions": [
        {
            "finding_id": finding_id,
            "state": state,
            "dismiss_reason": "not reproducible" if state == "dismissed" else None,
        }
    ],
    "next_turn_instructions": None,
    "error": None,
}
path = pathlib.Path(verdict_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(payload), encoding="utf-8")
"""
    script_path = tmp_path / "resolve_agent.py"
    script_path.write_text(script, encoding="utf-8")
    config_path = tmp_path / "review-gauntlet.json"
    config_path.write_text(
        json.dumps(
            {
                "adapter": {
                    "type": "command",
                    "command": "python",
                    "args": [str(script_path), "{prompt}", target_state],
                    "output": {"mode": "stdout-json"},
                    "timeout_seconds": 5,
                    "quiet_timeout_seconds": 5,
                    "verdict_grace_seconds": 0.1,
                }
            }
        ),
        encoding="utf-8",
    )

    main(["resolve", str(tmp_path), "--config", str(config_path), "--format", "json"])

    output = json.loads(capsys.readouterr().out)
    assert output["resolved_finding_ids"] == [finding_id]
    assert output["finding_state_counts"].get("open") is None
    assert output["finding_state_counts"][target_state] == 1


def test_validate_verdict_remains_ocr_specific(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ocr_path = tmp_path / "ocr-verdict.json"
    ocr_path.write_text('{"comments": []}', encoding="utf-8")
    turn_path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )
    _write_turn_verdict(turn_path, _turn_verdict_payload())

    main(["validate-verdict", str(ocr_path), "--format", "json"])
    ocr_output = json.loads(capsys.readouterr().out)
    assert ocr_output == {"valid": True, "path": str(ocr_path), "comment_count": 0}

    with pytest.raises(SystemExit) as excinfo:
        main(["validate-verdict", str(turn_path), "--format", "json"])

    turn_output = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert turn_output["valid"] is False
    assert "VerdictPayload" in turn_output["error"]
    assert "schema_version" in turn_output["error"]


def test_continuation_prompt_includes_self_validation_command(tmp_path: Path) -> None:
    continuation_path = continuation_path_for_task(
        tmp_path / ".review-gauntlet", "RGS-test", "open", "src/example.py"
    )

    prompt = "\n".join(_continuation_prompt_sections(continuation_path))

    assert f"review-gauntlet validate-turn-verdict {continuation_path} --format json" in prompt
    assert "After writing the turn verdict file, validate it before ending this turn" in prompt
    assert "If validation fails, rewrite the verdict file and run the command again" in prompt
    assert "Do not end this turn until validation returns valid=true" in prompt
