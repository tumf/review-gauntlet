from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from review_gauntlet import run_tui
from review_gauntlet.run_controller import (
    AgentLifecycle,
    RunController,
    RunEvent,
    RunSnapshot,
    SessionCommandResult,
)
from review_gauntlet.run_tui import (
    PANEL_TITLES,
    activity_text,
    agent_activity_text,
    calculate_progress_metrics,
    compact_dashboard_text,
    coverage_text,
    create_run_app,
    dashboard_state,
    findings_text,
    footer_text,
    format_elapsed_time,
    format_event_time,
    format_task_title,
    progress_text,
    short_session_id,
    should_use_tui,
    textual_available,
)
from review_gauntlet.session_store import SessionStore


def test_should_use_tui_selection_rules() -> None:
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=True) is True
    assert should_use_tui(output_format="json", no_tui=False, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=True, stdout_is_tty=True) is False
    assert should_use_tui(output_format="text", no_tui=False, stdout_is_tty=False) is False


def test_progress_metrics_exclude_superseded_and_only_count_known_completed_states() -> None:
    metrics = calculate_progress_metrics(
        {"reviewed": 3, "pending": 2, "stale": 1, "failed": 1, "superseded": 99}
    )

    assert metrics.completed == 3
    assert metrics.total == 7
    assert metrics.percent == 43
    assert metrics.incomplete == 3
    assert metrics.pending == 2
    assert metrics.stale == 1
    assert metrics.superseded == 99


def test_progress_metrics_handle_zero_cell_sessions() -> None:
    metrics = calculate_progress_metrics({"superseded": 2})

    assert metrics.completed == 0
    assert metrics.total == 0
    assert metrics.percent == 0
    assert metrics.incomplete == 0
    assert metrics.superseded == 2


def test_progress_metrics_ignore_boolean_counts() -> None:
    metrics = calculate_progress_metrics({"reviewed": True, "pending": True, "stale": False})

    assert metrics.completed == 0
    assert metrics.total == 0
    assert metrics.percent == 0
    assert metrics.incomplete == 0


def test_progress_metrics_never_exceed_total() -> None:
    metrics = calculate_progress_metrics({"reviewed": 5})

    assert metrics.completed == metrics.total
    assert metrics.percent == 100


def test_elapsed_time_formatting() -> None:
    assert format_elapsed_time(0) == "00:00"
    assert format_elapsed_time(65.9) == "01:05"
    assert format_elapsed_time(3661) == "1:01:01"
    assert format_elapsed_time(-1) == "00:00"


def test_dashboard_header_contains_human_run_state_and_short_session() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-progress-1234567890",
        coverage={"reviewed": 2, "pending": 1, "stale": 1, "superseded": 3},
        findings={"open": 2},
        next_ready_prompt="review pending cells",
        step=4,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=125,
        command_label="agent",
    )

    text = progress_text(snapshot, activity_frame=1)

    assert "Review Gauntlet" in text
    assert "RGS-prog…7890" in text
    assert "RUNNING - agent is working" in text
    assert "elapsed 02:05" in text
    assert "gate 1/6" in text
    assert "agent step 4" in text
    assert "agent ⠙ running" in text
    assert "current cells" not in text


def test_header_and_current_operation_show_quiet_timeout_and_artifact_liveness() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-liveness-1234",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt="finalize session",
        step=2,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=10,
        command_label="agent",
        agent_lifecycle=AgentLifecycle(
            status="quiet",
            last_output_age_seconds=7.0,
            timeout_remaining_seconds=53.0,
            artifact_path="/tmp/repo/.review-gauntlet/runs/run-1/activity.jsonl",
        ),
    )
    view = dashboard_state(snapshot, (), activity_frame=0)

    header = run_tui.header_text(view)
    operation = run_tui.current_operation_text(view)
    activity = activity_text(view)

    assert "last output 7s ago" in header
    assert "quiet 7s" in header
    assert "timeout in 53s" in header
    assert "agent still running" in activity
    assert "artifact .review-gauntlet/runs/run-1/activity.jsonl" in operation
    assert "timeout in 53s" in operation


def test_liveness_synthesizes_non_flooding_quiet_heartbeat_rows() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-liveness",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt=None,
        step=1,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=0,
        agent_lifecycle=AgentLifecycle(status="quiet", last_output_age_seconds=9.0),
    )

    assert "agent still running" in activity_text(dashboard_state(snapshot, (), activity_frame=0))
    assert "agent still running" not in activity_text(
        dashboard_state(snapshot, (), activity_frame=1)
    )


def test_coverage_and_findings_render_dashboard_metrics_without_old_markers() -> None:
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

    assert "50%" in coverage
    assert "reviewed / total cells: 2 / 4" in coverage
    assert "reviewed 2 | pending 1 | stale 1 | superseded 1" in coverage
    assert "current cells" not in coverage
    assert "! pending" not in coverage
    assert "! stale" not in coverage
    assert "open 0" in findings
    assert "untriaged 2" in findings
    assert "confirmed 0" in findings
    assert "reopened 0" in findings
    assert "fixed-pending 1" in findings
    assert "closed 0" in findings


def test_tui_panel_body_helpers_omit_standalone_section_headings() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-body-headings",
        coverage={"reviewed": 2, "pending": 1},
        findings={"open": 1},
        next_ready_prompt="review pending cells",
        step=1,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=1,
        command_label="agent",
    )
    view = dashboard_state(snapshot, ())

    bodies = {
        "Activity": activity_text(view),
        "Finalize path": run_tui.finalize_path_text(view),
        "Session metrics": coverage_text(snapshot),
        "Findings": findings_text(snapshot),
        "Current operation": run_tui.current_operation_text(view),
    }

    for heading, body in bodies.items():
        assert body.splitlines()[0] != heading


def test_compact_dashboard_text_uses_shared_panel_titles() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-shared-titles",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt=None,
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )
    compact = compact_dashboard_text(snapshot)

    for title in PANEL_TITLES.values():
        assert title in compact


@pytest.mark.parametrize(
    ("prompt", "title"),
    [
        ("review pending cells in this session", "REVIEW PENDING CELLS"),
        ("review stale cells in this session", "REVIEW STALE CELLS"),
        ("triage untriaged findings", "TRIAGE FINDINGS"),
        ("fix confirmed finding", "FIX CONFIRMED FINDING"),
        ("verify fixed_pending_verification findings", "VERIFY FIXES"),
        ("finalize session", "FINALIZE SESSION"),
    ],
)
def test_task_title_mapping_for_ready_prompt_intents(prompt: str, title: str) -> None:
    assert format_task_title(prompt).title == title


def test_task_text_sanitizes_unknown_prompt_and_omits_command_na() -> None:
    prompt = "[bold]task[/bold]\x1b[31m\nwith a very long explanation " * 4
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt=prompt,
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    task_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_task_text"])
    text = task_text(snapshot)

    assert "Current operation" not in text
    assert "Finalize checkpoint" in text
    assert "\\[bold]task" not in text
    assert "\x1b" not in text
    assert "command n/a" not in text
    assert "argv=[]" not in text


def test_command_placeholder_and_agent_text_never_render_raw_empty_argv() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-tui",
        coverage={},
        findings={},
        next_ready_prompt="review pending cells",
        step=2,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=1.25,
    )

    agent_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_agent_text"])
    task_text = cast(Callable[[RunSnapshot], str], run_tui.__dict__["_task_text"])

    assert "command resolving..." in agent_text(snapshot)
    assert "command resolving..." in task_text(snapshot)
    assert "command n/a" not in agent_text(snapshot)
    assert "argv=[]" not in task_text(snapshot)


def test_running_activity_animates_only_for_running_status() -> None:
    assert agent_activity_text("running", activity_frame=0) != agent_activity_text(
        "running", activity_frame=1
    )
    assert agent_activity_text("idle", activity_frame=0) == agent_activity_text(
        "idle", activity_frame=1
    )


def test_view_state_fields_and_terminal_state_classes() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-abcdefghijk",
        coverage={"reviewed": 1, "pending": 1},
        findings={"open": 2},
        next_ready_prompt="finalize session",
        step=3,
        agent_status="finalized",
        command_argv=("agent", "run"),
        elapsed_seconds=9,
    )

    view = dashboard_state(snapshot, ())

    assert view.session_short_id == "RGS-abcd…hijk"
    assert view.agent_name == "agent run"
    assert view.step_label == "agent step 3"
    assert view.task.title == "FINALIZE SESSION"
    assert view.command_label == "agent run"
    assert view.state_class == "panel-finalized"
    assert "FINALIZED" in view.status_summary


@pytest.mark.parametrize(
    ("status", "word", "css_class"),
    [
        ("blocked", "BLOCKED", "panel-blocked"),
        ("failed", "FAILED", "panel-failed"),
        ("finalized", "FINALIZED", "panel-finalized"),
    ],
)
def test_terminal_state_rendering(status: str, word: str, css_class: str) -> None:
    snapshot = RunSnapshot(None, {}, {}, None, 0, status, (), 0)
    view = dashboard_state(snapshot, ())

    assert word in view.status_summary
    assert view.state_class == css_class


def test_activity_timeline_formats_events_without_raw_payloads() -> None:
    events = (
        RunEvent("run_started", "2026-06-15T12:34:56+00:00", {"session_id": "RGS-1234567890"}),
        RunEvent("status_refreshed", "bad timestamp", {"session_id": "RGS-1234567890"}),
        RunEvent(
            "step_started",
            "2026-06-15T12:35:01+00:00",
            {"step": 1, "prompt": "review pending cells [bold]\x1b"},
        ),
        RunEvent(
            "agent_started",
            "2026-06-15T12:35:02+00:00",
            {"argv": [], "command_label": "agent --safe"},
        ),
        RunEvent("failed", "2026-06-15T12:35:03+00:00", {"reason": "command_failed"}),
        RunEvent("blocked", "2026-06-15T12:35:04+00:00", {"reason": "no_ready_task"}),
        RunEvent("finalized", "2026-06-15T12:35:05+00:00", {"session_id": "RGS-1234567890"}),
    )
    snapshot = RunSnapshot("RGS-1234567890", {}, {}, None, 0, "idle", (), 0)

    text = activity_text(dashboard_state(snapshot, events))

    assert "12:34:56 run started - session RGS-1234…7890" in text
    assert "--:--:-- status refreshed" in text
    assert "12:35:01 step 1 started - REVIEW PENDING CELLS" in text
    assert "12:35:02 agent started - agent --safe" in text
    assert "failed - command_failed" in text
    assert "blocked - no_ready_task" in text
    assert "finalized - session RGS-1234…7890" in text
    assert "2026-06-15T" not in text
    assert "argv=[]" not in text
    assert "[bold]" not in text


def test_event_time_and_session_shortening_helpers() -> None:
    assert format_event_time("2026-06-15T01:02:03+00:00") == "01:02:03"
    assert format_event_time("not a date") == "--:--:--"
    assert short_session_id("RGS-1234567890") == "RGS-1234…7890"
    assert short_session_id(None) == "none"


def test_plain_text_collapses_control_whitespace() -> None:
    plain_text = cast(Callable[[object], str], run_tui.__dict__["_plain_text"])

    assert plain_text("ok\nnext\rprev\ttab") == r"ok next prev tab"


def test_progress_bar_clamps_filled_width() -> None:
    progress_bar = cast(Callable[[int, int], str], run_tui.__dict__["_progress_bar"])

    assert progress_bar(20, 10) == "[" + "█" * 24 + "]"
    assert progress_bar(-1, 10) == "[" + "░" * 24 + "]"


def test_compact_dashboard_text_keeps_required_sections() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-compact-1234",
        coverage={"reviewed": 8, "pending": 1, "stale": 1, "superseded": 2},
        findings={},
        next_ready_prompt="triage untriaged findings",
        step=1,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=3,
        command_label="agent",
    )
    compact = compact_dashboard_text(snapshot)

    assert "Review Gauntlet" in compact
    assert "Finalize path" in compact
    assert "Session metrics" in compact
    assert "Findings" in compact
    assert "Review coverage" in compact
    assert "Activity" in compact
    assert "q stop after current step" in compact


def test_footer_lists_only_implemented_controls() -> None:
    footer = footer_text()

    assert "q stop after current step" in footer
    assert "r refresh" in footer
    assert "h help" in footer
    assert "Ctrl-C interrupt" in footer
    assert "prompt" not in footer
    assert "artifacts" not in footer


def test_run_tui_source_uses_border_titles_and_semantic_title_styles() -> None:
    source = Path("src/review_gauntlet/run_tui.py").read_text(encoding="utf-8")

    assert "Header" not in source
    assert "Footer" not in source
    assert "border_title" in source
    assert "border-title-color" in source
    assert "border-title-style" in source
    assert "$warning" in source
    assert "$accent" not in source


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


@pytest.mark.anyio
async def test_run_app_executes_controller_in_headless_mode(tmp_path: Path) -> None:
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

    app = cast(Any, create_run_app(controller))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._completed_result is not None
        assert not pilot.app._exit
        await pilot.press("q")

    result = getattr(app, "return_value", None)
    if result is None:
        result = getattr(app, "_return_value", None)
    assert isinstance(result, dict)
    assert result["completed"] is True
