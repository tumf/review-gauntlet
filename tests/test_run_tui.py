from typing import Any, cast

import pytest

from review_gauntlet.coverage_projection import (
    CoverageCellFilter,
    CoverageCellInput,
    CoverageFindingInput,
    CoverageProjection,
    FileCoverageSummary,
    FindingSummaryEntry,
    QueueEntry,
    RuleCoverageSummary,
    build_coverage_projection,
)
from review_gauntlet.run_controller import AgentLifecycle, RunController, RunSnapshot
from review_gauntlet.run_tui import (
    FINDING_STATES,
    actionable_finding_summary,
    calculate_progress_metrics,
    cells_text,
    color_legend_tui_lines,
    compact_dashboard_text,
    create_run_app,
    dashboard_state,
    derive_finalize_gates,
    finalized_summary_text,
    findings_panel_title,
    findings_tui_lines,
    format_task_title_from_action,
    header_agent_text,
    header_status_tui_lines,
    render_tui_lines,
    tui_render_sections,
)


class FakeRunController:
    def __init__(self, snapshots: list[RunSnapshot] | None = None) -> None:
        self._snapshots = snapshots or [_running_snapshot()]
        self.snapshot_call_count = 0
        self.events = ()
        self.interrupt_requested = False
        self.stop_requested = False
        self.run_called = False

    def snapshot(self) -> RunSnapshot:
        self.snapshot_call_count += 1
        index = min(self.snapshot_call_count - 1, len(self._snapshots) - 1)
        return self._snapshots[index]

    def run(self) -> dict[str, object]:
        self.run_called = True
        return {"status": "completed"}

    def interrupt(self) -> None:
        self.interrupt_requested = True

    def request_stop_after_current_step(self) -> None:
        self.stop_requested = True


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _running_snapshot(*, step: int = 1) -> RunSnapshot:
    return RunSnapshot(
        session_id="RGS-test",
        coverage={"pending": 1},
        findings={},
        next_ready_prompt="review",
        step=step,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=float(step),
        agent_lifecycle=AgentLifecycle(status="running"),
    )


def _create_fake_run_app(
    fake_controller: FakeRunController,
    fake_clock: FakeClock,
    *,
    full_refresh_interval_seconds: float = 2.0,
) -> Any:
    return create_run_app(
        cast(RunController, fake_controller),
        full_refresh_interval_seconds=full_refresh_interval_seconds,
        monotonic=fake_clock.monotonic,
    )


def test_automatic_background_refresh_reuses_snapshot_inside_throttle_window() -> None:
    clock = FakeClock()
    controller = FakeRunController([_running_snapshot(step=1), _running_snapshot(step=2)])
    app = _create_fake_run_app(controller, clock)

    app._background_refresh()
    app._background_refresh()

    assert controller.snapshot_call_count == 1
    assert app._activity_frame == 2
    assert app.snapshot.step == 1

    clock.advance(2.0)
    app._background_refresh()

    assert controller.snapshot_call_count == 2
    assert app.snapshot.step == 2


def test_manual_refresh_bypasses_automatic_refresh_throttle() -> None:
    clock = FakeClock()
    controller = FakeRunController([_running_snapshot(step=1), _running_snapshot(step=2)])
    app = _create_fake_run_app(controller, clock)

    app._background_refresh()
    app.action_refresh()

    assert controller.snapshot_call_count == 2
    assert app.snapshot.step == 2


def test_controller_completion_forces_refresh_even_with_fresh_throttle() -> None:
    clock = FakeClock()
    controller = FakeRunController([_running_snapshot(step=1), _running_snapshot(step=2)])
    app = _create_fake_run_app(controller, clock)

    app._background_refresh()
    app.refresh_view()

    assert controller.snapshot_call_count == 2
    assert app.snapshot.step == 2


def test_liveness_display_moves_between_full_snapshots() -> None:
    clock = FakeClock()
    controller = FakeRunController([_running_snapshot(step=1), _running_snapshot(step=2)])
    app = _create_fake_run_app(controller, clock)
    first_text = header_agent_text(
        dashboard_state(app.snapshot, (), activity_frame=app._activity_frame)
    )

    app._background_refresh()
    second_text = header_agent_text(
        dashboard_state(app.snapshot, (), activity_frame=app._activity_frame)
    )

    assert controller.snapshot_call_count == 1
    assert app.snapshot.step == 1
    assert first_text != second_text
    assert "⠙ running" in second_text


def test_automatic_refresh_frequency_is_bounded_independently_from_tick_count() -> None:
    clock = FakeClock()
    controller = FakeRunController([_running_snapshot(step=1), _running_snapshot(step=2)])
    app = _create_fake_run_app(controller, clock, full_refresh_interval_seconds=10.0)

    for _ in range(20):
        clock.advance(0.25)
        app._background_refresh()

    assert controller.snapshot_call_count == 1
    assert app._activity_frame == 20


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


def test_cells_view_renders_resolved_over_total_findings() -> None:
    projection = build_coverage_projection(
        (
            CoverageCellInput(
                cell_id="RGC-1",
                file_path="src/app.py",
                rule_id="security",
                slice_id="python",
                state="reviewed",
            ),
        ),
        (
            CoverageFindingInput(
                finding_id="RGF-0001",
                file_path="src/app.py",
                rule_id="security",
                state="open",
                content="still unresolved",
                latest_cell_id="RGC-1",
            ),
            CoverageFindingInput(
                finding_id="RGF-0002",
                file_path="src/app.py",
                rule_id="security",
                state="confirmed",
                content="confirmed issue",
                latest_cell_id="RGC-1",
            ),
            CoverageFindingInput(
                finding_id="RGF-0003",
                file_path="src/app.py",
                rule_id="security",
                state="dismissed",
                content="false alarm",
                latest_cell_id="RGC-1",
            ),
        ),
    )
    entry = projection.queue[0]
    view = dashboard_state(
        RunSnapshot(
            session_id="RGS-test",
            coverage={"reviewed": 1},
            findings={"open": 1, "confirmed": 1, "dismissed": 1},
            next_ready_prompt="review",
            step=1,
            agent_status="idle",
            command_argv=(),
            elapsed_seconds=1,
            coverage_projection=projection,
        ),
        (),
        active_view="cells",
    )

    assert entry.finding_count == 3
    assert entry.actionable_finding_count == 1
    assert entry.resolved_finding_count == 2
    assert projection.rules[0].finding_count == 3
    assert projection.rules[0].resolved_findings == 2
    assert projection.files[0].finding_count == 3
    assert projection.files[0].resolved_findings == 2
    assert entry.priority_label == "P0"
    assert entry.why.startswith("1 actionable finding(s)")
    assert "findings 2/3" in cells_text(view, filters=CoverageCellFilter())
    assert "2/3" in render_tui_lines(tui_render_sections(view)["rules"])
    assert "2/3" in render_tui_lines(tui_render_sections(view)["files"])
    assert "resolved" not in cells_text(view, filters=CoverageCellFilter())
    assert "resolved" not in render_tui_lines(tui_render_sections(view)["rules"])
    assert "resolved" not in render_tui_lines(tui_render_sections(view)["files"])


def test_color_legend_matches_finding_progress_ratio() -> None:
    legend = render_tui_lines(color_legend_tui_lines())

    assert "done / find" in legend
    assert "pend / find" not in legend
    assert "resolved" not in legend


def test_task_title_mapping_uses_resolve_findings() -> None:
    task = format_task_title_from_action("resolve_findings", {}, {"open": 1})
    assert task.title == "RESOLVE FINDINGS"


def _findings_projection() -> CoverageProjection:
    return CoverageProjection(
        queue=(),
        rules=(),
        files=(),
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
            FindingSummaryEntry(
                finding_id="RGF-0002",
                file_path="src/other.py",
                rule_id="correctness",
                state="open",
                content="second bug",
                latest_cell_id="RGC-2",
                actionable=True,
            ),
            FindingSummaryEntry(
                finding_id="RGF-0003",
                file_path="src/ignored.py",
                rule_id="correctness",
                state="dismissed",
                content="not a bug",
                latest_cell_id="RGC-3",
                actionable=False,
            ),
        ),
    )


def testfindings_panel_title_uses_projection_resolved_counts() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1, "dismissed": 1},
        next_ready_prompt="resolve",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
        coverage_projection=_findings_projection(),
    )

    view = dashboard_state(snapshot, (), active_view="findings")

    assert findings_panel_title(view) == "Findings 1/3"


def testfindings_panel_title_falls_back_to_finding_state_counts() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 2, "dismissed": 3},
        next_ready_prompt="resolve",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
    )

    view = dashboard_state(snapshot, (), active_view="overview")

    assert findings_panel_title(view) == "Findings 3/5"


@pytest.mark.parametrize(
    ("frame", "title"),
    [(0, "Finding"), (1, "Finding."), (2, "Finding.."), (3, "Finding...")],
)
def testfindings_panel_title_animates_during_review(frame: int, title: str) -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"pending": 1},
        findings={"open": 1},
        next_ready_prompt="review",
        step=1,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=1,
        active_step_action="run_review",
        coverage_projection=_findings_projection(),
    )

    view = dashboard_state(snapshot, (), activity_frame=frame, active_view="findings")

    assert findings_panel_title(view) == title


def test_resolve_findings_title_preserves_counts() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1, "dismissed": 1},
        next_ready_prompt="resolve",
        step=1,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=1,
        active_step_action="resolve_findings",
        active_target_finding_ids=("RGF-0001",),
        coverage_projection=_findings_projection(),
    )

    view = dashboard_state(snapshot, (), activity_frame=2, active_view="findings")

    assert findings_panel_title(view) == "Findings 1/3"


def test_resolve_findings_rows_show_only_targeted_spinner_and_aligned_blank() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1, "dismissed": 1},
        next_ready_prompt="resolve",
        step=1,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=1,
        active_step_action="resolve_findings",
        active_target_finding_ids=("RGF-0001",),
        coverage_projection=_findings_projection(),
    )

    view = dashboard_state(snapshot, (), activity_frame=1, active_view="findings")
    rendered = render_tui_lines(findings_tui_lines(view, limit=2)).splitlines()

    assert rendered[0].startswith("⠙ RGF-0001")
    assert rendered[1].startswith("  RGF-0002")
    assert rendered[0].index("RGF-0001") == rendered[1].index("RGF-0002")


def test_resolve_findings_rows_clear_indicators_without_active_targets() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1, "dismissed": 1},
        next_ready_prompt="resolve",
        step=1,
        agent_status="running",
        command_argv=("fake-agent",),
        elapsed_seconds=1,
        active_step_action=None,
        active_target_finding_ids=(),
        coverage_projection=_findings_projection(),
    )

    view = dashboard_state(snapshot, (), activity_frame=1, active_view="findings")
    rendered = render_tui_lines(findings_tui_lines(view, limit=2)).splitlines()

    assert rendered[0].startswith("RGF-0001")
    assert rendered[1].startswith("RGF-0002")


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
                    resolved_finding_count=1,
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
                    finding_count=1,
                    actionable_findings=0,
                    resolved_findings=1,
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
                    finding_count=1,
                    actionable_findings=0,
                    resolved_findings=1,
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
                resolved_finding_count=0,
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
                finding_count=0,
                actionable_findings=0,
                resolved_findings=0,
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
                finding_count=0,
                actionable_findings=0,
                resolved_findings=0,
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


def testfindings_panel_title_preserves_agent_and_empty_detail_views() -> None:
    snapshot = RunSnapshot(
        session_id="RGS-test",
        coverage={"reviewed": 1},
        findings={"open": 1},
        next_ready_prompt="resolve",
        step=0,
        agent_status="idle",
        command_argv=(),
        elapsed_seconds=0,
        coverage_projection=_findings_projection(),
    )

    assert findings_panel_title(dashboard_state(snapshot, (), active_view="agent")) == "Agent"
    for active_view in ("files", "rules", "cells"):
        assert findings_panel_title(dashboard_state(snapshot, (), active_view=active_view)) == ""


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
