from review_gauntlet.run_controller import RunSnapshot
from review_gauntlet.run_tui import (
    FINDING_STATES,
    actionable_finding_summary,
    calculate_progress_metrics,
    dashboard_state,
    derive_finalize_gates,
    format_task_title_from_action,
)


def test_progress_metrics_counts_pending_and_reviewed_only() -> None:
    metrics = calculate_progress_metrics({"reviewed": 3, "pending": 2})
    assert metrics.completed == 3
    assert metrics.total == 5
    assert metrics.incomplete == 2


def test_finding_states_are_two_phase_model() -> None:
    assert FINDING_STATES == ("open", "confirmed", "dismissed")


def test_actionable_finding_summary_counts_open_only() -> None:
    summary = actionable_finding_summary({"open": 2, "confirmed": 1, "dismissed": 1})
    assert summary.open == 2
    assert summary.triage == 2
    assert summary.fix == 0
    assert summary.verify == 0


def test_task_title_mapping_uses_resolve_findings() -> None:
    task = format_task_title_from_action("resolve_findings", {}, {"open": 1})
    assert task.title == "RESOLVE FINDINGS"


def test_finalize_gates_show_review_and_resolve_phases() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1},
        next_ready_prompt="resolve",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
        next_required_action="resolve_findings",
    )

    gates = derive_finalize_gates(snapshot)

    assert [gate.title for gate in gates] == [
        "Review phase",
        "Resolve phase",
        "Final checks",
        "Finalize checkpoint",
    ]
    assert gates[1].state == "running"


def test_dashboard_state_uses_dynamic_gate_count() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={},
        next_ready_prompt="finalize",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
        can_finalize=True,
        next_required_action="finalize",
    )

    view = dashboard_state(snapshot, ())

    assert view.gate_label == "gate 4/4"
