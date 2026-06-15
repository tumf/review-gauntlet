from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from review_gauntlet import run_tui
from review_gauntlet.run_controller import RunController, RunSnapshot, SessionCommandResult
from review_gauntlet.run_tui import (
    agent_activity_text,
    calculate_progress_metrics,
    coverage_text,
    create_run_app,
    findings_text,
    format_elapsed_time,
    progress_text,
    should_use_tui,
    textual_available,
)
from review_gauntlet.session_store import SessionStore


def test_should_use_tui_selection_rules() -> None:
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=True) is True
    assert should_use_tui(output_format="json", no_tui=False, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=True, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=False) is False


def test_progress_metrics_exclude_superseded_and_treat_pending_stale_as_incomplete() -> None:
    metrics = calculate_progress_metrics(
        {"reviewed": 3, "pending": 2, "stale": 1, "failed": 1, "superseded": 99}
    )

    assert metrics.completed == 4
    assert metrics.total == 7
    assert metrics.percent == 57
    assert metrics.incomplete == 3
    assert metrics.superseded == 99


def test_progress_metrics_handle_zero_cell_sessions() -> None:
    metrics = calculate_progress_metrics({"superseded": 2})

    assert metrics.completed == 0
    assert metrics.total == 0
    assert metrics.percent == 0
    assert metrics.incomplete == 0
    assert metrics.superseded == 2


def test_elapsed_time_formatting() -> None:
    assert format_elapsed_time(0) == "00:00"
    assert format_elapsed_time(65.9) == "01:05"
    assert format_elapsed_time(3661) == "1:01:01"
    assert format_elapsed_time(-1) == "00:00"


def test_progress_first_header_contains_dense_run_state() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-progress",
        coverage={"reviewed": 2, "pending": 1, "stale": 1, "superseded": 3},
        findings={"open": 2},
        next_ready_prompt="review docs",
        step=4,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=125,
    )

    text = progress_text(snapshot, activity_frame=1)

    assert "50%" in text
    assert "2/4 current cells" in text
    assert "elapsed 02:05" in text
    assert "step 4" in text
    assert "agent ⠙ running" in text
    assert "superseded 3" in text


def test_coverage_and_findings_render_high_density_summaries() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-density",
        coverage={"reviewed": 2, "pending": 1, "stale": 1, "superseded": 1},
        findings={"untriaged": 2, "fixed_pending_verification": 1},
        next_ready_prompt=None,
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    coverage = coverage_text(snapshot)
    findings = findings_text(snapshot)

    assert "! pending" in coverage
    assert "! stale" in coverage
    assert "remaining" in coverage
    assert "excluded" in coverage
    assert "■" in coverage
    assert "[fixed_pending_verification:1]" in findings
    assert "[untriaged:2]" in findings
    assert "untriaged: 2" not in findings


def test_task_text_renders_prompt_as_plain_text() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt="[bold]task[/bold]\x1b[31m",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    task_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_task_text"])

    assert task_text(snapshot) == "Current task\n\\[bold]task\\[/bold]�\\[31m\ncommand n/a"


def test_agent_text_renders_status_and_argv_as_plain_text() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt=None,
        step=2,
        agent_status="[red]running[/red]\x1b[31m",
        command_argv=("agent", "[bold]arg[/bold]\x1b[32m"),
        elapsed_seconds=1.25,
    )

    agent_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_agent_text"])

    assert agent_text(snapshot) == (
        "Agent\n"
        "status=\\[red]running\\[/red]�\\[31m step=2 elapsed=1.2s\n"
        "argv=agent \\[bold]arg\\[/bold]�\\[32m"
    )


def test_running_activity_animates_only_for_running_status() -> None:
    assert agent_activity_text("running", activity_frame=0) != agent_activity_text(
        "running", activity_frame=1
    )
    assert agent_activity_text("idle", activity_frame=0) == agent_activity_text(
        "idle", activity_frame=1
    )


def test_run_tui_source_does_not_import_default_header_footer() -> None:
    source = Path("src/review_gauntlet/run_tui.py").read_text(encoding="utf-8")

    assert "Header" not in source
    assert "Footer" not in source


def test_create_run_app_constructs_when_textual_available(tmp_path: Path) -> None:
    if not textual_available():
        pytest.skip("Textual optional dependency is not installed")
    store = SessionStore(tmp_path)
    store.create_session(
        {
            "session_id": "RGS-tui",
            "root": str(tmp_path),
            "target": {
                "base_ref": None,
                "head_ref": None,
                "worktree": True,
                "commit": None,
                "all_files": False,
            },
        },
        (),
    )
    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {"coverage": {}, "findings": {}},
        command_runner=lambda _config, _root, _state_dir, _prompt: SessionCommandResult(
            argv=[], cwd=None, returncode=0, stdout="", stderr=""
        ),
    )

    app = create_run_app(controller)

    assert app is not None


def test_run_app_executes_controller_in_headless_mode(tmp_path: Path) -> None:
    if not textual_available():
        pytest.skip("Textual optional dependency is not installed")
    (tmp_path / "review-gauntlet.json").write_text(
        json.dumps({"adapter": {"type": "command", "command": "agent"}}), encoding="utf-8"
    )
    store = SessionStore(tmp_path)
    store.create_session(
        {
            "session_id": "RGS-tui-run",
            "root": str(tmp_path),
            "target": {
                "base_ref": None,
                "head_ref": None,
                "worktree": True,
                "commit": None,
                "all_files": False,
            },
        },
        (),
    )

    def command_runner(*_args: object) -> SessionCommandResult:
        (tmp_path / ".review-gauntlet" / "active-session.json").unlink()
        return SessionCommandResult(argv=["agent"], cwd=None, returncode=0, stdout="", stderr="")

    controller = RunController(
        root=tmp_path,
        store=store,
        config_path=None,
        max_steps=1,
        ready_prompt=lambda _store, _root: "ready prompt",
        status_snapshot=lambda _store, _root: {"coverage": {}, "findings": {}},
        command_runner=command_runner,
    )

    result = cast(Any, create_run_app(controller)).run(headless=True)

    assert isinstance(result, dict)
    assert result["completed"] is True
