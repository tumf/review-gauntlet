from __future__ import annotations

import json
import subprocess
import threading
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path
from typing import cast

import pytest

import review_gauntlet.run_controller as run_controller_module
from review_gauntlet.checkpoint import CheckpointCommitResult, write_latest_checkpoint
from review_gauntlet.config import CommandAdapterConfig
from review_gauntlet.review_cells import CellState, ReviewCell
from review_gauntlet.run_controller import (
    AgentOutputProgress,
    RunController,
    RunEvent,
    RunExecutionContext,
    SessionCommandResult,
    checkpoint_generated_files_from_stdout,
    command_display_label,
)
from review_gauntlet.session_store import SessionStore


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "README.md").write_text("# docs\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        "\n".join(
            (
                ".review-gauntlet/*",
                "!.review-gauntlet/checkpoints/",
                ".review-gauntlet/checkpoints/*",
                "!.review-gauntlet/checkpoints/RGC-*/",
                "!.review-gauntlet/checkpoints/RGC-*/*",
                "!.review-gauntlet/checkpoints/latest",
                "",
            )
        ),
        encoding="utf-8",
    )
    _git(root, "add", "README.md", ".gitignore")
    _git(root, "commit", "-m", "initial")


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


def test_agent_output_progress_thread_safe_snapshot_returns_age_and_tail() -> None:
    progress = AgentOutputProgress()
    pushed = threading.Event()

    def push_output() -> None:
        progress.push("stdout", "hello")
        pushed.set()

    thread = threading.Thread(target=push_output)
    thread.start()
    assert pushed.wait(timeout=1.0)
    age, tail = progress.snapshot()
    thread.join(timeout=1.0)

    assert age is not None and age < 1.0
    assert tail == progress.snapshot()[1]
    assert len(tail) == 1
    assert tail[0].stream == "stdout"
    assert tail[0].text == "hello"
    assert tail[0].timestamp is not None


def test_run_controller_exposes_agent_output_progress_during_command(tmp_path: Path) -> None:
    store = _store(tmp_path)
    observed: list[AgentOutputProgress | None] = []

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        observed.append(controller.agent_output_progress)
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent", "ready prompt"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    assert controller.agent_output_progress is None
    result = controller.run()

    assert result["completed"] is True
    assert len(observed) == 1
    assert isinstance(observed[0], AgentOutputProgress)
    assert controller.agent_output_progress is None


def test_run_controller_lifecycle_uses_live_output_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    current_time = datetime(2026, 1, 1, tzinfo=UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return current_time

    monkeypatch.setattr(run_controller_module, "datetime", FrozenDateTime)
    snapshots: list[tuple[str, float | None, tuple[str, ...]]] = []

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        nonlocal current_time
        assert controller.agent_output_progress is not None
        controller.agent_output_progress.push("stdout", "recent output")
        current_time += timedelta(seconds=1)
        recent = controller.snapshot().agent_lifecycle
        snapshots.append(
            (
                recent.status,
                recent.last_output_age_seconds,
                tuple(e.text for e in recent.output_tail),
            )
        )
        current_time += timedelta(seconds=5)
        quiet = controller.snapshot().agent_lifecycle
        snapshots.append(
            (quiet.status, quiet.last_output_age_seconds, tuple(e.text for e in quiet.output_tail))
        )
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent", "ready prompt"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    assert snapshots[0][0] == "running"
    assert snapshots[0][1] == 1.0
    assert snapshots[0][2] == ("recent output",)
    assert snapshots[1][0] == "quiet"
    assert snapshots[1][1] == 6.0
    assert snapshots[1][2] == ("recent output",)


def test_run_execution_context_ignores_stale_git_worktree_metadata(tmp_path: Path) -> None:
    store = _store(tmp_path)
    metadata = store.session_metadata("RGS-test")
    with store.connect() as conn:
        conn.execute(
            "update sessions set metadata = ? where session_id = ?",
            (
                json.dumps(
                    {
                        **metadata,
                        "git_worktree": {
                            "enabled": True,
                            "worktree_path": ".review-gauntlet/worktrees/RGS-test",
                        },
                    },
                    sort_keys=True,
                ),
                "RGS-test",
            ),
        )

    context = RunExecutionContext.from_active_session(
        root=tmp_path,
        store=store,
        session_id="RGS-test",
    )

    assert context.agent_root == tmp_path
    assert context.state_dir == tmp_path / ".review-gauntlet"


def test_run_controller_passes_base_root_to_command_with_stale_git_metadata(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    metadata = store.session_metadata("RGS-test")
    with store.connect() as conn:
        conn.execute(
            "update sessions set metadata = ? where session_id = ?",
            (
                json.dumps(
                    {
                        **metadata,
                        "git_worktree": {
                            "enabled": True,
                            "worktree_path": ".review-gauntlet/worktrees/RGS-test",
                        },
                    },
                    sort_keys=True,
                ),
                "RGS-test",
            ),
        )
    observed: list[tuple[Path, Path]] = []

    def command(
        _config: CommandAdapterConfig, root: Path, state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        observed.append((root, state_dir))
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent"], cwd=str(root), returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    assert observed == [(tmp_path, tmp_path / ".review-gauntlet")]


def test_run_controller_completes_when_command_finalizes_session(tmp_path: Path) -> None:
    store = _store(tmp_path)
    prompts: list[str] = []

    events_during_command: list[str] = []

    def command(
        config: CommandAdapterConfig, root: Path, state_dir: Path, prompt: str
    ) -> SessionCommandResult:
        prompts.append(prompt)
        events_during_command.extend(event.type for event in controller.events)
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
    snapshot = controller.snapshot()

    assert result["completed"] is True
    assert result["reason"] == "completed"
    assert result["step_count"] == 1
    assert snapshot.agent_status == "finalized"
    assert snapshot.agent_lifecycle.status == "finalized"
    assert prompts == ["ready prompt"]
    assert "agent_started" in events_during_command
    assert "agent_finished" not in events_during_command
    assert [event.type for event in controller.events] == [
        "run_started",
        "status_refreshed",
        "step_started",
        "agent_started",
        "agent_finished",
        "checkpoint_commit_started",
        "checkpoint_commit_finished",
        "finalized",
    ]


def test_run_controller_attempts_checkpoint_commit_after_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    calls: list[tuple[Path, str, tuple[str, ...]]] = []

    def fake_commit_latest_checkpoint(
        root: Path, *, session_id: str, generated_files: tuple[str, ...] = ()
    ) -> CheckpointCommitResult:
        calls.append((root, session_id, generated_files))
        return CheckpointCommitResult(
            attempted=True,
            committed=True,
            commit="abc123",
            reason="committed",
        )

    monkeypatch.setattr(
        run_controller_module, "commit_latest_checkpoint", fake_commit_latest_checkpoint
    )

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent"],
            cwd=None,
            returncode=0,
            stdout=json.dumps(
                {"generated_files": [".review-gauntlet/checkpoints/latest/status.json"]}
            ),
            stderr="",
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert calls == [(tmp_path, "RGS-test", (".review-gauntlet/checkpoints/latest/status.json",))]
    cc = cast(dict[str, object], result["checkpoint_commit"])
    assert cc["checkpoint_commit_attempted"] is True
    assert cc["checkpoint_committed"] is True
    assert cc["checkpoint_commit"] == "abc123"
    assert cc["checkpoint_commit_reason"] == "committed"
    assert [event.type for event in controller.events][-3:] == [
        "checkpoint_commit_started",
        "checkpoint_commit_finished",
        "finalized",
    ]


def test_run_controller_commits_checkpoint_when_finalizing_agent_stdout_is_non_json(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    store = SessionStore(tmp_path)
    session_id = store.create_session(
        {
            "session_id": "RGS-test",
            "root": str(tmp_path),
            "target": {"all_files": True},
        },
        (
            ReviewCell(
                id="cell-1",
                file_path="README.md",
                rule_id="docs-accuracy",
                slice_id="docs",
                state=CellState.REVIEWED,
                content_digest="digest",
            ),
        ),
    )
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "fake-agent", "args": []}}),
        encoding="utf-8",
    )
    _git(tmp_path, "add", "review-gauntlet.json")
    _git(tmp_path, "commit", "-m", "add run config")
    checkpoint: dict[str, object] = {}

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        nonlocal checkpoint
        checkpoint = write_latest_checkpoint(
            store,
            tmp_path,
            session_id,
            {"coverage": {"reviewed": 1}, "finding_state_counts": {}, "run_count": 1},
        )
        with store.connect() as conn:
            conn.execute(
                "update sessions set state = 'finalized' where session_id = ?", (session_id,)
            )
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent"], cwd=None, returncode=0, stdout="finalized in prose", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "finalize session",
        status_snapshot=lambda _store, _root: {
            "coverage": {"reviewed": 1},
            "finding_state_counts": {},
            "can_finalize": True,
            "finalize_blockers": [],
            "next_required_action": "finalize",
        },
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    cc = cast(dict[str, object], result["checkpoint_commit"])
    assert cc["checkpoint_committed"] is True
    assert cc["checkpoint_commit_reason"] == "committed"
    committed_paths = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert committed_paths == [
        f"{checkpoint['checkpoint_dir']}/events.json",
        f"{checkpoint['checkpoint_dir']}/findings.json",
        f"{checkpoint['checkpoint_dir']}/status.json",
        f"{checkpoint['checkpoint_dir']}/summary.md",
        ".review-gauntlet/checkpoints/latest",
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""


def test_checkpoint_generated_files_from_stdout_ignores_non_json() -> None:
    assert checkpoint_generated_files_from_stdout("not json") == ()


def test_checkpoint_generated_files_from_stdout_accepts_nested_verdict_files() -> None:
    stdout = json.dumps(
        {"verdict": {"generated_files": [".review-gauntlet/checkpoints/latest/status.json"]}}
    )

    assert checkpoint_generated_files_from_stdout(stdout) == (
        ".review-gauntlet/checkpoints/latest/status.json",
    )


def test_checkpoint_generated_files_from_stdout_rejects_non_json_checkpoint_paths() -> None:
    stdout = json.dumps(
        {
            "generated_files": [
                ".review-gauntlet/checkpoints/latest",
                ".review-gauntlet/checkpoints/latest/summary.md",
                ".review-gauntlet/checkpoints/latest/status.json",
            ]
        }
    )

    assert checkpoint_generated_files_from_stdout(stdout) == (
        ".review-gauntlet/checkpoints/latest/status.json",
    )


def test_checkpoint_generated_files_from_stdout_rejects_absolute_path() -> None:
    stdout = json.dumps({"generated_files": ["/etc/passwd"]})
    assert checkpoint_generated_files_from_stdout(stdout) == ()


def test_checkpoint_generated_files_from_stdout_rejects_parent_traversal() -> None:
    stdout = json.dumps({"generated_files": ["../../etc/passwd"]})
    assert checkpoint_generated_files_from_stdout(stdout) == ()


def test_checkpoint_generated_files_from_stdout_rejects_empty_string() -> None:
    stdout = json.dumps({"generated_files": [""]})
    assert checkpoint_generated_files_from_stdout(stdout) == ()


def test_checkpoint_generated_files_from_stdout_deduplicates() -> None:
    path = ".review-gauntlet/checkpoints/latest/status.json"
    stdout = json.dumps({"generated_files": [path, path, path]})
    assert checkpoint_generated_files_from_stdout(stdout) == (path,)


def test_run_controller_honors_interrupt_requested_during_command(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        controller.interrupt()
        return SessionCommandResult(
            argv=["fake-agent", "ready prompt"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "interrupted"
    assert result["error"] == "run interrupted by controller request"
    assert result["step_count"] == 1
    assert "finalized" not in [event.type for event in controller.events]


def test_run_controller_exposes_command_label_before_command_returns(tmp_path: Path) -> None:
    store = _store(tmp_path)
    labels_during_command: list[str | None] = []
    agent_started_payloads: list[dict[str, object]] = []

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        labels_during_command.append(controller.snapshot().command_label)
        agent_started_payloads.extend(
            event.payload for event in controller.events if event.type == "agent_started"
        )
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent", "ready prompt"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    assert labels_during_command == ["fake-agent"]
    assert agent_started_payloads == [{"command_label": "fake-agent", "step": 1}]


def test_run_controller_synthesizes_quiet_liveness_and_timeout_remaining(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    snapshots: list[tuple[str, float | None, float | None]] = []

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        controller.set_agent_step_started_at_for_testing(datetime.now(UTC) - timedelta(seconds=6))
        snapshot = controller.snapshot()
        snapshots.append(
            (
                snapshot.agent_lifecycle.status,
                snapshot.agent_lifecycle.last_output_age_seconds,
                snapshot.agent_lifecycle.timeout_remaining_seconds,
            )
        )
        store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent", "ready prompt"], cwd=None, returncode=0, stdout="ok", stderr=""
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=command,
    )

    result = controller.run()

    assert result["completed"] is True
    assert snapshots
    status, last_output_age, timeout_remaining = snapshots[0]
    assert status == "quiet"
    assert last_output_age is not None and last_output_age >= 5.0
    assert timeout_remaining is not None and 0 < timeout_remaining <= 594


def test_command_display_label_omits_template_arguments() -> None:
    config = CommandAdapterConfig(
        type="command", command="fake-agent", args=("--mode", "review", "{prompt}")
    )

    assert command_display_label(config) == "fake-agent --mode review"


def test_run_controller_preserves_effective_timeout_after_command_timeout(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)

    def command(
        config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        return SessionCommandResult(
            argv=[config.command],
            cwd=None,
            returncode=None,
            stdout="",
            stderr="command timed out",
            failure={
                "reason": "timeout",
                "error": f"command timed out after {config.timeout_seconds} seconds",
            },
        )

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {
            "coverage": {"reviewed": 1},
            "findings": {},
            "can_finalize": True,
            "finalize_blockers": [],
            "next_required_action": "finalize",
        },
        command_runner=command,
    )

    result = controller.run()
    snapshot = controller.snapshot()

    assert result["completed"] is False
    assert result["reason"] == "timeout"
    assert snapshot.agent_status == "timed_out"
    assert snapshot.agent_lifecycle.status == "timed_out"
    assert snapshot.agent_lifecycle.timeout_seconds == 600.0
    assert snapshot.agent_lifecycle.timeout_remaining_seconds is None
    assert snapshot.can_finalize is True


@pytest.mark.parametrize(
    ("reason", "expected_status"),
    [
        ("timeout", "timed_out"),
        ("command_failed", "command_failed"),
        ("startup_error", "startup_error"),
        ("template_error", "template_error"),
        ("interrupted", "interrupted"),
    ],
)
def test_run_controller_preserves_specific_command_failure_statuses(
    tmp_path: Path, reason: str, expected_status: str
) -> None:
    store = _store(tmp_path)

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        return SessionCommandResult(
            argv=["fake-agent"],
            cwd=None,
            returncode=2 if reason == "command_failed" else None,
            stdout="",
            stderr="boom",
            failure={"reason": reason, "error": f"{reason} error"},
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
    snapshot = controller.snapshot()

    assert result["completed"] is False
    assert result["reason"] == reason
    assert result["error"] == f"{reason} error"
    assert result["step_count"] == 1
    assert snapshot.agent_status == expected_status
    assert snapshot.agent_lifecycle.status == expected_status
    assert snapshot.agent_status != "timed_out" or reason == "timeout"


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
    snapshot = controller.snapshot()

    assert result["completed"] is False
    assert result["reason"] == "interrupted"
    assert result["error"] == "run interrupted by user"
    assert result["step_count"] == 0
    assert result["steps"] == []
    assert result["session_id"] == "RGS-test"
    assert snapshot.agent_status == "interrupted"
    assert snapshot.agent_lifecycle.status == "interrupted"
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

    snapshot = controller.snapshot()

    assert result["completed"] is False
    assert result["reason"] == "max_steps_exhausted"
    assert result["max_steps"] == 2
    assert result["step_count"] == 2
    assert snapshot.agent_status == "max_steps_exhausted"
    assert snapshot.agent_lifecycle.status == "max_steps_exhausted"


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


def test_run_controller_snapshot_uses_finding_state_counts_fallback(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {
            "coverage": {"pending": 1},
            "finding_state_counts": {"untriaged": 2},
        },
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    snapshot = controller.snapshot()

    assert snapshot.findings == {"untriaged": 2}


def test_run_controller_snapshot_prefers_legacy_findings_when_present(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {
            "coverage": {"pending": 1},
            "findings": {"legacy": 1},
            "finding_state_counts": {"untriaged": 2},
        },
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    snapshot = controller.snapshot()

    assert snapshot.findings == {"legacy": 1}


def test_agent_output_progress_ring_buffer_truncation() -> None:
    progress = AgentOutputProgress(limit=3)
    for i in range(5):
        progress.push("stdout", f"line-{i}")
    _age, tail = progress.snapshot()
    assert len(tail) == 3
    assert [e.text for e in tail] == ["line-2", "line-3", "line-4"]


def test_run_event_model_dump_key_collision() -> None:
    event = RunEvent.create("test", type="should_be_overwritten", timestamp="should_be_overwritten")
    dumped = event.model_dump()
    assert dumped["type"] == "test"
    assert dumped["timestamp"] != "should_be_overwritten"


def test_run_controller_max_steps_zero_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        RunController(
            root=tmp_path,
            store=store,
            config_path=None,
            max_steps=0,
            ready_prompt=lambda _store, _root: "ready prompt",
            status_snapshot=_status,
            command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
                argv=[], cwd=None, returncode=0, stdout="", stderr=""
            ),
        )


def test_run_controller_max_steps_negative_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="positive integer"):
        RunController(
            root=tmp_path,
            store=store,
            config_path=None,
            max_steps=-1,
            ready_prompt=lambda _store, _root: "ready prompt",
            status_snapshot=_status,
            command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
                argv=[], cwd=None, returncode=0, stdout="", stderr=""
            ),
        )


def test_run_controller_session_disappeared_before_loop(tmp_path: Path) -> None:
    store = _store(tmp_path)
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=3,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=_status,
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=["fake-agent"], cwd=None, returncode=0, stdout="ok", stderr=""
        ),
    )

    store.active_path.unlink()
    result = controller.run()

    assert result["completed"] is False
    assert result["reason"] == "session_disappeared"


def test_run_controller_post_loop_completion_session_disappears_on_final_step(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    call_count = 0

    def command(
        _config: CommandAdapterConfig, _root: Path, _state_dir: Path, _prompt: str
    ) -> SessionCommandResult:
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            store.active_path.unlink()
        return SessionCommandResult(
            argv=["fake-agent"], cwd=None, returncode=0, stdout="ok", stderr=""
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
    snapshot = controller.snapshot()

    assert result["completed"] is True
    assert result["reason"] == "completed"
    assert snapshot.agent_status == "finalized"
    assert snapshot.agent_lifecycle.status == "finalized"
