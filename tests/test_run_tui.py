from review_gauntlet.coverage_projection import (
    CoverageProjection,
    FileCoverageSummary,
    FindingSummaryEntry,
    QueueEntry,
    RuleCoverageSummary,
)
from review_gauntlet.run_controller import RunSnapshot
from review_gauntlet.run_tui import (
    FINDING_STATES,
    actionable_finding_summary,
    calculate_progress_metrics,
    compact_dashboard_text,
    dashboard_state,
    derive_finalize_gates,
    finalized_summary_text,
    format_task_title_from_action,
    header_status_tui_lines,
    render_tui_lines,
    tui_render_sections,
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


def _finalized_snapshot(*, with_details: bool = True) -> RunSnapshot:
    projection = CoverageProjection(queue=(), rules=(), files=(), findings=())
    findings: dict[str, object] = {}
    checkpoint_commit: dict[str, object] | None = None
    if with_details:
        projection = CoverageProjection(
            queue=(
                QueueEntry(
                    cell_id="RGC-1",
                    file_path="src/app.py",
                    rule_id="security",
                    slice_id="python",
                    state="reviewed",
                    priority_label="P1",
                    priority_score=100,
                    finding_count=1,
                    actionable_finding_count=0,
                    stale_reason=None,
                    why="reviewed",
                    changed_since_review=False,
                ),
            ),
            rules=(
                RuleCoverageSummary(
                    rule_id="security",
                    total=1,
                    reviewed=1,
                    pending=0,
                    stale=0,
                    actionable_findings=0,
                    priority_label="P1",
                ),
            ),
            files=(
                FileCoverageSummary(
                    file_path="src/app.py",
                    total=1,
                    reviewed=1,
                    pending=0,
                    stale=0,
                    actionable_findings=0,
                    highest_priority_label="P1",
                    highest_priority_score=100,
                ),
            ),
            findings=(
                FindingSummaryEntry(
                    finding_id="RGF-0001",
                    file_path="src/app.py",
                    rule_id="security",
                    state="dismissed",
                    content="not a bug",
                    latest_cell_id="RGC-1",
                    actionable=False,
                ),
            ),
        )
        findings = {"dismissed": 1}
        checkpoint_commit = {
            "checkpoint_commit_attempted": True,
            "checkpoint_committed": True,
            "checkpoint_commit": "abc1234567890",
            "checkpoint_commit_reason": "committed",
        }
    return RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 3, "pending": 1},
        findings=findings,
        next_ready_prompt=None,
        step=2,
        agent_status="finalized",
        command_argv=("fake-agent",),
        elapsed_seconds=75,
        session_state="finalized",
        run_count=2,
        cell_terminal_count=3,
        coverage_projection=projection,
        checkpoint_commit=checkpoint_commit,
    )


def test_finalized_summary_derives_details_and_explicit_empty_wording() -> None:
    detailed = dashboard_state(_finalized_snapshot(), ())

    assert detailed.finalized_summary is not None
    assert detailed.finalized_summary.coverage_percent == 75
    assert detailed.finalized_summary.terminal_cells == 3
    assert detailed.finalized_summary.total_cells == 4
    assert detailed.finalized_summary.resolved_finding_count == 1
    assert detailed.finalized_summary.resolved_files == ("src/app.py",)
    assert detailed.finalized_summary.rule_ids == ("security",)
    assert detailed.finalized_summary.finding_ids == ("RGF-0001",)
    assert detailed.finalized_summary.elapsed == "01:15"
    assert detailed.finalized_summary.step_count == 2
    assert detailed.finalized_summary.checkpoint == "abc123456789"

    empty = dashboard_state(_finalized_snapshot(with_details=False), ())
    text = finalized_summary_text(empty)

    assert "Resolved findings 0" in text
    assert "Resolved files  none" in text
    assert "Rules           none" in text
    assert "Finding IDs     none" in text
    assert "Checkpoint      unavailable (no checkpoint metadata)" in text


def test_finalized_render_replaces_operational_sections_with_summary() -> None:
    view = dashboard_state(_finalized_snapshot(), ())
    rendered = render_tui_lines(tui_render_sections(view)["queue"])

    assert "Final coverage" in rendered
    assert "75%" in rendered
    assert "terminal/total cells 3/4" in rendered
    assert "elapsed 01:15" in rendered
    assert "steps 2" in rendered
    assert "abc123456789" in rendered
    assert "Resolved files  src/app.py" in rendered
    assert "Rules           security" in rendered
    assert "Finding IDs     RGF-0001" in rendered


def test_finalized_sections_hide_operational_panels_and_running_keeps_them() -> None:
    finalized_sections = tui_render_sections(dashboard_state(_finalized_snapshot(), ()))

    assert finalized_sections["queue"]
    assert finalized_sections["rules"] == ()
    assert finalized_sections["files"] == ()
    assert finalized_sections["findings"] == ()
    assert finalized_sections["activity"] == ()

    running_projection = CoverageProjection(
        queue=(
            QueueEntry(
                cell_id="RGC-1",
                file_path="src/app.py",
                rule_id="security",
                slice_id="python",
                state="pending",
                priority_label="P1",
                priority_score=100,
                finding_count=0,
                actionable_finding_count=0,
                stale_reason=None,
                why="pending",
                changed_since_review=False,
            ),
        ),
        rules=(
            RuleCoverageSummary(
                rule_id="security",
                total=1,
                reviewed=0,
                pending=1,
                stale=0,
                actionable_findings=0,
                priority_label="P1",
            ),
        ),
        files=(
            FileCoverageSummary(
                file_path="src/app.py",
                total=1,
                reviewed=0,
                pending=1,
                stale=0,
                actionable_findings=0,
                highest_priority_label="P1",
                highest_priority_score=100,
            ),
        ),
        findings=(
            FindingSummaryEntry(
                finding_id="RGF-0001",
                file_path="src/app.py",
                rule_id="security",
                state="open",
                content="bug",
                latest_cell_id="RGC-1",
                actionable=True,
            ),
        ),
    )
    running = RunSnapshot(
        session_id="RGS-test",
        coverage={"pending": 1},
        findings={"open": 1},
        next_ready_prompt="review",
        step=1,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=1,
        coverage_projection=running_projection,
    )
    running_sections = tui_render_sections(dashboard_state(running, ()))

    assert running_sections["queue"]
    assert running_sections["rules"]
    assert running_sections["files"]
    assert running_sections["findings"]
    assert running_sections["activity"]


def test_finalized_header_keeps_nonzero_progress_in_compact_render() -> None:
    view = dashboard_state(_finalized_snapshot(), ())
    header = render_tui_lines(header_status_tui_lines(view))
    compact = compact_dashboard_text(_finalized_snapshot())

    assert "75%" in header
    assert "3/4" in header
    assert "75%" in compact
    assert "0%" not in header
    assert "Next review queue" not in compact
    assert "Rule coverage" not in compact
    assert "File hotlist" not in compact
    assert "Findings\n" not in compact
    assert "Activity" not in compact
