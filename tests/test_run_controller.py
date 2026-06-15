from __future__ import annotations

import json
from pathlib import Path

from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.run_controller import RunController, SessionCommandResult
from review_gauntlet.session_store import SessionStore


def _store(tmp_path: Path) -> SessionStore:
    store = SessionStore(tmp_path)
    store.create_session(
        {
            "session_id": "RGS-test",
            "root": str(tmp_path),
            "target": {
                "base_ref": None,
                "head_ref": None,
                "worktree": True,
                "commit": None,
                "all_files": False,
            },
        },
        (
            ReviewCell(
                id="cell-1",
                file_path="README.md",
                rule_id="docs-accuracy",
                slice_id="docs",
                state=CellState.PENDING,
                content_digest="digest",
            ),
        ),
    )
    config = {
        "adapter": {
            "type": "command",
            "command": "fake-agent",
            "args": ["{prompt}"],
            "output": {"mode": "stdout-json"},
        }
    }
    config_path = tmp_path / "review-gauntlet.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return store


def _status(_store: SessionStore, _root: Path) -> dict[str, object]:
    return {"coverage": {"pending": 1}, "findings": {"untriaged": 0}}


def test_run_controller_completes_when_command_finalizes_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prompts: list[str] = []

    def command(
        config: CommandAdapterConfig, root: Path, state_dir: Path, prompt: str
    ) -> SessionCommandResult:
        prompts.append(prompt)
        store.active_path.unlink()
        return SessionCommandResult(
            argv=[config.command, prompt], cwd=str(root), returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=3,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    assert result["reason"] == "completed"
    assert result["step_count"] == 1
    assert prompts == ["ready prompt"]
    assert [event.type for event in controller.events] == [
        "run_started",
        "status_refreshed",
        "step_started",
        "agent_started",
        "agent_finished",
        "finalized",
    ]


def test_run_controller_reports_command_failure(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        return SessionCommandResult(
            argv=["fake-agent"],
            cwd=None,
            returncode=2,
            stdout="",
            stderr="boom",
            failure={"reason": "command_failed", "error": "command exited with status 2"},
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=3,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "command_failed"
    assert result["error"] == "command exited with status 2"
    assert result["step_count"] == 1


def test_run_controller_reports_interrupted_command_and_keeps_active_session(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        raise KeyboardInterrupt

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=3,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "interrupted"
    assert result["error"] == "run interrupted by user"
    assert result["step_count"] == 0
    assert result["steps"] == []
    assert result["session_id"] == "RGS-test"
    assert store.active_path.exists()
    assert store.active_session_id() == "RGS-test"
    assert [event.type for event in controller.events][-1] == "interrupted"


def test_run_controller_reports_no_ready_task(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=3,
        ready_prompt=lambda _store, _root: None,
        status_snapshot=_status,
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "no_ready_task"
    assert result["step_count"] == 0


def test_run_controller_reports_max_steps_exhausted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=2,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=lambda config, _root, _state_dir, prompt: SessionCommandResult(
            argv=[config.command, prompt], cwd=None, returncode=0, stdout="ok", stderr=""
        ),
    )

    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "max_steps_exhausted"
    assert result["max_steps"] == 2
    assert result["step_count"] == 2


def test_run_controller_stop_after_current_step_prevents_next_step(tmp_path: Path) -> None:
    store = _store(tmp_path)
    calls = 0

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        nonlocal calls
        calls += 1
        controller.request_stop_after_current_step()
        return SessionCommandResult(
            argv=["fake-agent"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=5,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert calls == 1
    assert result["completed"] is False
    assert result["reason"] == "stop_after_current_step"
    assert result["step_count"] == 1


def test_run_controller_refresh_snapshot_exposes_status(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    snapshot = controller.refresh()

    assert snapshot.session_id == "RGS-test"
    assert snapshot.coverage == {"pending": 1}
    assert snapshot.findings == {"untriaged": 0}
    assert snapshot.next_ready_prompt == "ready prompt"
