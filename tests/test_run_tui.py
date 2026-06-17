from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from review_gauntlet import run_tui
from review_gauntlet.run_controller import (
    AgentLifecycle,
    AgentOutputEntry,
    RunController,
    RunEvent,
    RunSnapshot,
    SessionCommandResult,
)
from review_gauntlet.run_tui import (
    PANEL_TITLES,
    actionable_finding_summary,
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
    assert metrics.percent == 42
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


def test_actionable_finding_summary_derives_open_count_without_open_key() -> None:
    summary = actionable_finding_summary(
        {"untriaged": 2, "confirmed": 1, "fixed_pending_verification": 1}
    )

    assert summary.open == 4
    assert summary.triage == 2
    assert summary.fix == 1
    assert summary.verify == 1


def test_actionable_finding_summary_preserves_zero_actionable_behavior() -> None:
    summary = actionable_finding_summary({"closed": 5, "open": 99})

    assert summary.open == 0
    assert summary.triage == 0
    assert summary.fix == 0
    assert summary.verify == 0


def test_elapsed_time_formatting() -> None:
    assert format_elapsed_time(0) == "00:00"
    assert format_elapsed_time(65.9) == "01:05"
    assert format_elapsed_time(3661) == "1:01:01"
    assert format_elapsed_time(-1) == "00:00"
    assert format_elapsed_time(float("nan")) == "00:00"
    assert format_elapsed_time(float("inf")) == "00:00"


def test_duration_formatting_handles_non_finite_values() -> None:
    assert run_tui.format_duration(float("nan")) == "0s"
    assert run_tui.format_duration(float("inf")) == "0s"


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
    assert "RUNNING · gate 1/6 · Review coverage" in text
    assert "elapsed 02:05" not in text
    assert "agent step 4" not in text
    assert "agent agent" in text
    assert "current cells" not in text


def test_header_omits_timeout_and_agent_summary_keeps_quiet_timeout_artifact_liveness() -> None:
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

    assert "quiet 7s" in header
    assert "timeout" not in header
    assert "53s" not in header
    assert "last output 7s ago" not in header
    assert "agent alive no output" not in activity
    assert "waiting for run activity" in activity
    assert "artifact .review-gauntlet/runs/run-1/activity.jsonl" in operation
    assert "status  quiet 7s" in operation
    assert "output  last output 7s ago" in operation
    assert "timeout in 53s" in operation
    assert "timeout timeout" not in operation


def test_liveness_omits_quiet_heartbeat_rows_across_animation_frames() -> None:
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

    for frame in range(8):
        view = dashboard_state(snapshot, (), activity_frame=frame)
        activity = activity_text(view)

        assert "agent alive no output" not in activity
        assert "waiting for run activity" in activity
        assert "quiet 9s" in run_tui.header_text(view)
        assert "status  quiet 9s" in run_tui.agent_summary_text(view)
        assert "output  last output 9s ago" in run_tui.agent_summary_text(view)


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
    assert "open 3" in findings
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
        "Finalize checklist": run_tui.finalize_path_text(view),
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

    assert compact.index("Review Gauntlet") < compact.index("Finalize checklist")
    assert compact.index("Finalize checklist") < compact.index("Agent")
    assert compact.index("Agent") < compact.index("Session")
    assert compact.index("Session") < compact.index("Activity")
    assert "Next to finalize" not in compact


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
    assert "Finalize checkpoint" not in text
    assert "command command resolving..." in text
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


def test_finalized_snapshot_without_session_state_marks_checkpoint_done() -> None:
    snapshot = RunSnapshot(
        session_id=None,
        coverage={},
        findings={},
        next_ready_prompt=None,
        step=1,
        agent_status="finalized",
        command_argv=("agent",),
        elapsed_seconds=0,
        session_state=None,
    )

    view = dashboard_state(snapshot, ())
    checkpoint_gate = view.gates[5]
    rendered = compact_dashboard_text(snapshot)

    assert view.status_summary == "FINALIZED"
    assert view.state_class == "panel-finalized"
    assert checkpoint_gate.title == "Finalize checkpoint"
    assert checkpoint_gate.state == "done"
    assert checkpoint_gate.detail == "complete"
    assert "FINALIZED · gate 6/6 · Finalize checkpoint" in rendered
    assert "✓ Finalize checkpoint      done    complete" in rendered


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

    assert "12:34:56 event - run started session RGS-1234…7890" in text
    assert "--:--:-- event - status refreshed" in text
    assert "12:35:01 event - step 1 started REVIEW PENDING CELLS" in text
    assert "12:35:02 event - agent started agent --safe" in text
    assert "event - failed command_failed" in text
    assert "event - blocked no_ready_task" in text
    assert "event - finalized session RGS-1234…7890" in text
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
    assert "Finalize checklist" in compact
    assert "Next to finalize" not in compact
    assert "Session metrics" not in compact
    assert "Current operation" not in compact
    assert "Finalize path" not in compact
    assert "Agent" in compact
    assert "Session" in compact
    assert "Review coverage" in compact
    assert "Activity" in compact
    assert "q stop after current step" in compact


def test_new_dashboard_checklist_rows_and_blocker_classification_hide_internal_names() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-redesign-1234567890",
        coverage={"pending": 9},
        findings={},
        next_ready_prompt="run_review",
        step=1,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=0,
        command_label="opencode",
        finalize_blockers=("review cells are still pending",),
        next_required_action="resolve_finalize_blockers",
    )
    view = dashboard_state(snapshot, ())
    text = "\n".join(
        [
            run_tui.header_text(view),
            run_tui.finalize_path_text(view),
            run_tui.agent_summary_text(view),
            run_tui.session_summary_text(view),
            activity_text(view),
        ]
    )

    assert "RUNNING · gate 5/6 · Final checks" in text
    assert "Current   final checks" in text
    assert "Next to finalize" not in text
    for title in (
        "Review coverage",
        "Triage findings",
        "Fix confirmed findings",
        "Verify fixes",
        "Final checks",
        "Finalize checkpoint",
    ):
        assert title in text
    assert "Final checks" in text
    assert "later" in text
    assert "checked after review/findings" in text
    assert "1 finalize blocker(s)" not in text
    assert "run_review" not in text
    assert "resolve_finalize_blockers" not in text
    checklist = run_tui.finalize_path_text(view)
    assert "gate 1/6" not in checklist
    assert "gate 2/6" not in checklist


@pytest.mark.parametrize(
    ("next_required_action", "gate_index", "gate_title"),
    [
        ("run_review", 1, "Review coverage"),
        ("triage_findings", 2, "Triage findings"),
        ("fix_confirmed_findings", 3, "Fix confirmed findings"),
        ("run_verify_fixes", 4, "Verify fixes"),
        ("resolve_finalize_blockers", 5, "Final checks"),
        ("finalize", 6, "Finalize checkpoint"),
    ],
)
def test_finalize_checklist_uses_next_required_action_for_active_gate(
    next_required_action: str, gate_index: int, gate_title: str
) -> None:
    snapshot = RunSnapshot(
        session_id="RGS-next-action",
        coverage={"pending": 2},
        findings={"untriaged": 1, "confirmed": 1, "fixed_pending_verification": 1},
        next_ready_prompt=next_required_action,
        step=1,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=0,
        command_label="agent",
        finalize_blockers=("working tree has uncommitted changes",),
        next_required_action=next_required_action,
    )

    view = dashboard_state(snapshot, ())
    rendered = compact_dashboard_text(snapshot)

    assert view.active_gate.index == gate_index
    assert view.active_gate.title == gate_title
    assert f"RUNNING · gate {gate_index}/6 · {gate_title}" in rendered
    assert f"Current   {gate_title.lower()}" in rendered
    if "_" in next_required_action:
        assert next_required_action not in rendered


def test_finalize_checklist_uses_next_required_action_for_active_gate_with_stale_coverage() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-next-action-stale",
        coverage={"reviewed": 3, "stale": 2},
        findings={"fixed_pending_verification": 1},
        next_ready_prompt="verify fixed_pending_verification findings",
        step=3,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=0,
        command_label="agent",
        finalize_blockers=(
            "review cells are stale",
            "fixed findings require verification",
        ),
        next_required_action="run_verify_fixes",
    )

    view = dashboard_state(snapshot, ())
    checklist = run_tui.finalize_path_text(view)
    rendered = compact_dashboard_text(snapshot)

    assert view.active_gate.index == 4
    assert view.active_gate.title == "Verify fixes"
    assert "RUNNING · gate 4/6 · Verify fixes" in rendered
    assert "Current   verify fixes" in rendered
    assert "Review coverage" in checklist
    assert "3 / 5 reviewed, 2 pending" in checklist
    assert "run_verify_fixes" not in rendered


def test_unknown_next_required_action_preserves_derived_active_gate() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-unknown-next-action",
        coverage={"reviewed": 3, "pending": 1},
        findings={"fixed_pending_verification": 1},
        next_ready_prompt="custom adapter action",
        step=2,
        agent_status="running",
        command_argv=(),
        elapsed_seconds=0,
        command_label="agent",
        next_required_action="custom_internal_action",
    )

    view = dashboard_state(snapshot, ())
    rendered = compact_dashboard_text(snapshot)

    assert view.active_gate.index == 1
    assert view.active_gate.title == "Review coverage"
    assert "RUNNING · gate 1/6 · Review coverage" in rendered
    assert "custom_internal_action" not in rendered


def test_finalize_checklist_state_derivation_across_gates() -> None:
    pending = dashboard_state(
        RunSnapshot("RGS-a", {"pending": 1}, {}, None, 0, "running", (), 0), ()
    ).gates
    triage = dashboard_state(
        RunSnapshot("RGS-b", {"reviewed": 1}, {"untriaged": 1}, None, 0, "running", (), 0),
        (),
    ).gates
    fix = dashboard_state(
        RunSnapshot("RGS-c", {"reviewed": 1}, {"confirmed": 1}, None, 0, "running", (), 0),
        (),
    ).gates
    verify = dashboard_state(
        RunSnapshot(
            "RGS-d",
            {"reviewed": 1},
            {"fixed_pending_verification": 1},
            None,
            0,
            "running",
            (),
            0,
        ),
        (),
    ).gates
    final_blocked = dashboard_state(
        RunSnapshot(
            "RGS-e",
            {"reviewed": 1},
            {},
            None,
            0,
            "running",
            (),
            0,
            finalize_blockers=("working tree has uncommitted changes",),
        ),
        (),
    ).gates
    finalized = dashboard_state(
        RunSnapshot("RGS-f", {"reviewed": 1}, {}, None, 0, "finalized", (), 0), ()
    ).gates

    assert pending[0].state == "running"
    assert triage[1].state == "running"
    assert fix[2].state == "running"
    assert verify[3].state == "running"
    assert final_blocked[4].state == "blocked"
    assert final_blocked[4].detail == "working tree has uncommitted changes"
    assert all(gate.state == "done" for gate in finalized)


def test_session_summary_derives_open_findings_and_action_breakdown_without_open_key() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-actionable-findings",
        coverage={"reviewed": 1},
        findings={"reopened": 1, "untriaged": 2, "confirmed": 1, "fixed_pending_verification": 1},
        next_ready_prompt="triage untriaged findings",
        step=2,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=0,
        command_label="agent",
    )

    view = dashboard_state(snapshot, ())
    session = run_tui.session_summary_text(view)
    details = findings_text(snapshot)

    assert view.open_findings == 5
    assert "Findings  open 5   triage 3 | fix 1 | verify 1" in session
    assert "open 5" in details
    assert "reopened 1" in details
    assert "untriaged 2" in details
    assert "confirmed 1" in details
    assert "fixed-pending 1" in details


def test_session_summary_keeps_zero_actionable_findings_without_work_breakdown() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-no-actionable-findings",
        coverage={"reviewed": 1},
        findings={"closed": 3, "open": 7},
        next_ready_prompt="finalize session",
        step=1,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    view = dashboard_state(snapshot, ())
    session = run_tui.session_summary_text(view)
    details = findings_text(snapshot)

    assert view.open_findings == 0
    assert "Findings  open 0" in session
    assert "triage" not in session
    assert "fix" not in session
    assert "verify" not in session
    assert "open 0" in details
    assert "closed 3" in details


def test_agent_session_summary_and_activity_rows_are_human_facing_and_sanitized() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-summary-1234",
        coverage={"pending": 9},
        findings={"open": 0},
        next_ready_prompt=None,
        step=1,
        agent_status="running",
        command_argv=("opencode", "run", "--secret", "x"),
        elapsed_seconds=0,
        command_label="opencode",
        agent_lifecycle=AgentLifecycle(
            status="quiet",
            last_output_age_seconds=120,
            timeout_remaining_seconds=426,
            artifact_path="/tmp/repo/.review-gauntlet/runs/run-1/output.txt",
            output_tail=(
                AgentOutputEntry("stdout", "hello TOKEN=supersecret", "2026-06-15T12:00:01+00:00"),
                AgentOutputEntry("stderr", "\x1b[31mwarn SECRET=value"),
            ),
        ),
    )
    events = (
        RunEvent("run_started", "2026-06-15T12:00:00+00:00", {"session_id": snapshot.session_id}),
    )
    view = dashboard_state(snapshot, events, activity_frame=0)
    agent = run_tui.agent_summary_text(view)
    session = run_tui.session_summary_text(view)
    activity = activity_text(view)

    assert "Agent" not in agent
    assert "command opencode" in agent
    assert "status  quiet 2m00s" in agent
    assert "output  last output 2m00s ago" in agent
    assert "timeout in 7m06s" in agent
    assert "timeout timeout" not in agent
    assert "last output 2m00s ago | quiet 2m00s" not in agent
    assert "artifact .review-gauntlet/runs/run-1/output.txt" in agent
    assert "Session" not in session
    assert "Coverage  0%   0 / 9" in session
    assert "Findings  open 0" in session
    assert "Current   review coverage" in session
    assert "Agent step 1" in session
    assert "event - run started session RGS-summ…1234" in activity
    assert "agent alive no output" not in activity
    assert "stdout - hello <redacted>" in activity
    assert "stderr - warn <redacted>" in activity
    assert "supersecret" not in activity
    assert "SECRET=value" not in activity
    assert run_tui.sanitize_agent_output_line("api_key=supersecret") == "<redacted>"
    assert run_tui.sanitize_agent_output_line("ClientSecret=supersecret") == "<redacted>"
    assert run_tui.sanitize_agent_output_line("Authorization: Bearer supersecret") == "<redacted>"
    assert run_tui.sanitize_agent_output_line("x-api-key: supersecret") == "<redacted>"
    assert run_tui.sanitize_agent_output_line('{"api_key": "supersecret"}') == "{<redacted>"
    assert run_tui.sanitize_agent_output_line("password=supersecret") == "<redacted>"


@pytest.mark.parametrize(
    ("status", "header", "agent_label"),
    [
        ("timed_out", "TIMED OUT", "timed out"),
        ("command_failed", "COMMAND FAILED", "command failed"),
        ("startup_error", "STARTUP ERROR", "startup error"),
        ("template_error", "TEMPLATE ERROR", "template error"),
        ("interrupted", "INTERRUPTED", "interrupted"),
        ("max_steps_exhausted", "MAX STEPS EXHAUSTED", "max steps exhausted"),
    ],
)
def test_failure_families_render_distinct_concise_agent_text(
    status: str, header: str, agent_label: str
) -> None:
    snapshot = RunSnapshot(
        session_id="RGS-failure-status",
        coverage={"pending": 1},
        findings={},
        next_ready_prompt="review pending cells",
        step=1,
        agent_status=status,
        command_argv=("agent",),
        elapsed_seconds=1,
        command_label="agent",
        agent_lifecycle=AgentLifecycle(status=status, timeout_seconds=600.0),
    )
    view = dashboard_state(snapshot, ())
    agent = run_tui.agent_summary_text(view)
    activity = run_tui.agent_activity_text(status)

    assert view.status_summary == header
    assert f"status  · {agent_label}" in agent
    assert activity == f"· {agent_label}"
    if status != "timed_out":
        assert "timed out" not in agent
        assert "timeout timeout" not in agent


def test_activity_panel_uses_command_failure_reason_and_keeps_stderr_evidence() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-command-failure",
        coverage={"pending": 1},
        findings={},
        next_ready_prompt="review pending cells",
        step=1,
        agent_status="command_failed",
        command_argv=("agent",),
        elapsed_seconds=1,
        command_label="agent",
        agent_lifecycle=AgentLifecycle(
            status="command_failed",
            timeout_seconds=600.0,
            output_tail=(AgentOutputEntry("stderr", "File not found: missing.txt"),),
        ),
    )
    events = (RunEvent("failed", "2026-06-15T12:35:03+00:00", {"reason": "command_failed"}),)

    text = activity_text(dashboard_state(snapshot, events))

    assert "event - failed command_failed" in text
    assert "stderr - File not found: missing.txt" in text
    assert "timed out" not in text


def test_agent_summary_uses_configured_default_timeout_without_unset_or_duplicate_wording() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-timeout-default",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt="finalize session",
        step=1,
        agent_status="timed_out",
        command_argv=("agent",),
        elapsed_seconds=600,
        command_label="agent",
        agent_lifecycle=AgentLifecycle(status="timed_out", timeout_seconds=600.0),
    )

    text = run_tui.agent_summary_text(dashboard_state(snapshot, ()))

    assert "timeout configured 10m00s" in text
    assert "timeout not set" not in text
    assert "timeout timeout" not in text


def test_finalize_ready_timeout_keeps_prior_gates_successful_and_shows_manual_finalize_cue() -> (
    None
):
    snapshot = RunSnapshot(
        session_id="RGS-ready-timeout",
        coverage={"reviewed": 13},
        findings={},
        next_ready_prompt="finalize session",
        step=3,
        agent_status="timed_out",
        command_argv=("agent",),
        elapsed_seconds=600,
        command_label="agent",
        can_finalize=True,
        finalize_blockers=(),
        next_required_action="finalize",
        agent_lifecycle=AgentLifecycle(status="timed_out", timeout_seconds=600.0),
    )
    view = dashboard_state(snapshot, ())
    checklist = run_tui.finalize_path_text(view)
    operation = run_tui.current_operation_text(view)

    assert view.gates[0].state == "done"
    assert view.gates[1].state == "done"
    assert view.gates[2].state == "done"
    assert view.gates[3].state == "done"
    assert view.gates[4].state == "done"
    assert view.gates[5].title == "Finalize checkpoint"
    assert view.gates[5].state == "running"
    assert "agent timed out; run review-gauntlet finalize" in checklist
    assert "timeout configured 10m00s" in operation
    assert "failed" not in checklist


def test_timeout_before_finalize_ready_remains_failed_without_manual_finalize_cue() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-preready-timeout",
        coverage={"reviewed": 2, "pending": 1},
        findings={},
        next_ready_prompt="review pending cells",
        step=2,
        agent_status="timed_out",
        command_argv=("agent",),
        elapsed_seconds=600,
        command_label="agent",
        can_finalize=False,
        finalize_blockers=("review cells are still pending",),
        agent_lifecycle=AgentLifecycle(status="timed_out", timeout_seconds=600.0),
    )
    checklist = run_tui.finalize_path_text(dashboard_state(snapshot, ()))

    assert "× Review coverage" in checklist
    assert "run review-gauntlet finalize" not in checklist


def test_timeout_with_finalize_blockers_remains_blocked_without_manual_finalize_cue() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-blocked-timeout",
        coverage={"reviewed": 13},
        findings={},
        next_ready_prompt="finalize session",
        step=3,
        agent_status="timed_out",
        command_argv=("agent",),
        elapsed_seconds=600,
        command_label="agent",
        can_finalize=False,
        finalize_blockers=("working tree has uncommitted changes",),
        agent_lifecycle=AgentLifecycle(status="timed_out", timeout_seconds=600.0),
    )
    checklist = run_tui.finalize_path_text(dashboard_state(snapshot, ()))

    assert "× Final checks" in checklist
    assert "working tree has uncommitted changes" in checklist
    assert "run review-gauntlet finalize" not in checklist


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


def test_header_title_carries_brand_sparkle_and_name() -> None:
    title = run_tui.header_title_text()

    assert "✻" in title
    assert "Review Gauntlet" in title


def test_header_first_line_is_brand_title_and_meta_omits_timeout() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-brand-1234567890",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt=None,
        step=1,
        agent_status="running",
        command_argv=("agent",),
        elapsed_seconds=0,
        command_label="agent",
        agent_lifecycle=AgentLifecycle(
            status="quiet",
            last_output_age_seconds=7.0,
            timeout_remaining_seconds=53.0,
        ),
    )
    view = dashboard_state(snapshot, (), activity_frame=0)

    assert run_tui.header_text(view).splitlines()[0] == run_tui.header_title_text()
    meta = run_tui.header_meta_text(view)
    assert "quiet 7s" in meta
    assert "timeout" not in meta
    assert "53s" not in meta


def test_run_tui_source_styles_header_with_brand_accent_and_state_status() -> None:
    source = Path("src/review_gauntlet/run_tui.py").read_text(encoding="utf-8")

    assert "$brand: #d97757;" in source
    assert "#header_title { color: $brand;" in source
    assert ".panel-active #header_status { color: $success; }" in source
    assert ".panel-failed #header_status { color: $error; }" in source


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
