# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUntypedBaseClass=false, reportUnknownParameterType=false
from __future__ import annotations

import importlib.util
import math
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from review_gauntlet.__about__ import __version__
from review_gauntlet.coverage_projection import (
    CoverageCellFilter,
    CoverageProjection,
    FileCoverageSummary,
    FindingSummaryEntry,
    QueueEntry,
    RuleCoverageSummary,
    filter_queue_entries,
)
from review_gauntlet.run_controller import AgentOutputEntry, RunController, RunEvent, RunSnapshot

TUI_FALLBACK_WARNING = "TUI support is not installed; falling back to text mode."
TUI_INSTALL_GUIDANCE = "Reinstall review-gauntlet to restore bundled TUI dependencies."
RUN_TUI_FULL_REFRESH_INTERVAL_SECONDS = 2.0
PANEL_TITLES = {
    "header": "Review Gauntlet",
    "finalize_path": "Finalize checklist",
    "queue": "Next review queue",
    "rules": "Rule coverage",
    "files": "File hotlist",
    "findings": "Findings",
    "agent": "Agent",
    "session": "Session",
    "activity": "Activity",
}


def textual_available() -> bool:
    return (
        importlib.util.find_spec("rich") is not None
        and importlib.util.find_spec("textual") is not None
    )


def should_use_tui(*, output_format: str, no_tui: bool, stdout_is_tty: bool) -> bool:
    return output_format == "text" and not no_tui and stdout_is_tty


def create_run_app(
    controller: RunController,
    *,
    full_refresh_interval_seconds: float = RUN_TUI_FULL_REFRESH_INTERVAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
) -> object:
    if full_refresh_interval_seconds <= 0 or not math.isfinite(full_refresh_interval_seconds):
        raise ValueError(
            "full_refresh_interval_seconds must be a finite positive number, "
            f"got {full_refresh_interval_seconds}"
        )
    try:
        from textual.app import App, ComposeResult, ScreenStackError
        from textual.containers import Horizontal, Vertical
        from textual.css.query import NoMatches
        from textual.widgets import Static
    except ImportError as exc:
        raise RuntimeError(TUI_FALLBACK_WARNING) from exc

    def titled_panel(
        title: str, body: Static, *, id: str | None = None, classes: str = "panel"
    ) -> Vertical:
        panel = Vertical(body, id=id, classes=classes)
        panel.border_title = title
        return panel

    class RunApp(App[dict[str, object]]):
        CSS = """
        $brand: #d97757;
        $dashboard-bg: #0f1117;
        $dashboard-surface: #151923;
        $dashboard-surface-muted: #11151d;
        Screen { layout: vertical; background: $dashboard-bg; }
        #body { height: 1fr; padding: 0 1; background: $dashboard-bg; }
        #session_header {
            border: round $primary;
            border-title-color: $brand;
            border-title-style: bold;
            padding: 0 1;
            height: auto;
            background: $dashboard-surface;
        }
        #header_status_line { text-style: bold; height: auto; }
        #header_agent_line { color: $text-muted; height: auto; }
        .panel-active #header_status_line { color: $success; }
        .panel-blocked #header_status_line { color: $warning; }
        .panel-failed #header_status_line { color: $error; }
        .panel-finalized #header_status_line { color: $success; }
        .panel {
            border: round $surface-lighten-2;
            border-title-color: $text-muted;
            border-title-style: bold;
            padding: 0 1;
            height: auto;
            background: $dashboard-surface;
        }
        .panel-active { border: round $success; border-title-color: $success; }
        .panel-blocked { border: round $warning; border-title-color: $warning; }
        .panel-failed { border: round $error; border-title-color: $error; }
        .panel-finalized { border: round $success; border-title-color: $success; }
        #coverage_row { height: auto; }
        #rules_panel_container, #files_panel_container {
            width: 1fr;
        }
        #bottom_row { height: 1fr; }
        #findings_panel_container, #activity_panel_container {
            width: 1fr;
            height: 1fr;
        }
        #findings_panel { height: 1fr; overflow-y: auto; }
        #activity_timeline { height: 1fr; overflow-y: auto; }
        #controls {
            color: $text-muted;
            height: auto;
            background: $dashboard-surface-muted;
        }        """
        BINDINGS = [
            ("q", "stop_after_current_step", "Stop after current step"),
            ("ctrl+c", "interrupt", "Interrupt"),
            ("r", "refresh", "Refresh"),
            ("h", "help", "Help"),
            ("1", "show_overview", "Overview"),
            ("2", "show_files", "Files"),
            ("3", "show_rules", "Rules"),
            ("4", "show_cells", "Cells"),
            ("5", "show_findings", "Findings"),
            ("a", "show_agent", "Agent"),
        ]

        def __init__(self, run_controller: RunController) -> None:
            super().__init__()
            self.controller = run_controller
            self.snapshot = run_controller.snapshot()
            self._last_full_refresh_at = monotonic()
            self._activity_frame = 0
            self._active_view = "overview"
            self._tui_render_state = empty_tui_render_state()
            self._completed_result: dict[str, object] | None = None
            self._exit_on_complete: bool = False

        def compose(self) -> ComposeResult:
            view = dashboard_state(
                self.snapshot,
                self.controller.events,
                activity_frame=self._activity_frame,
                active_view=self._active_view,
            )
            with Vertical(id="body"):
                session_header = Vertical(id="session_header", classes=view.state_class)
                session_header.border_title = header_title_text()
                with session_header:
                    yield Static(header_status_text(view), id="header_status_line")
                    yield Static(header_agent_text(view), id="header_agent_line")
                yield titled_panel(
                    PANEL_TITLES["queue"],
                    Static(queue_text(view), id="queue_panel"),
                    id="queue_panel_container",
                    classes=f"panel {view.state_class}",
                )
                with Horizontal(id="coverage_row"):
                    yield titled_panel(
                        PANEL_TITLES["rules"],
                        Static(rule_coverage_text(view), id="rules_panel"),
                        id="rules_panel_container",
                        classes="panel",
                    )
                    yield titled_panel(
                        PANEL_TITLES["files"],
                        Static(file_hotlist_text(view), id="files_panel"),
                        id="files_panel_container",
                        classes="panel",
                    )
                with Horizontal(id="bottom_row"):
                    yield titled_panel(
                        findings_panel_title(view),
                        Static(finding_projection_text(view), id="findings_panel"),
                        id="findings_panel_container",
                        classes="panel",
                    )
                    yield titled_panel(
                        PANEL_TITLES["activity"],
                        Static(activity_text(view), id="activity_timeline"),
                        id="activity_panel_container",
                    )
                yield Static(footer_text(), id="controls")
                yield Static("", id="legend")

        def on_mount(self) -> None:
            self.refresh_view()
            self.set_interval(0.25, self._background_refresh)
            self.run_worker(self._run_controller, thread=True)

        def _background_refresh(self) -> None:
            if self._completed_result is not None:
                return
            self._automatic_refresh()

        def _automatic_refresh(self) -> None:
            now = monotonic()
            if now - self._last_full_refresh_at >= full_refresh_interval_seconds:
                self.snapshot = self.controller.snapshot()
                self._last_full_refresh_at = now
            self._advance_liveness_frame()
            self._render_from_snapshot()

        def _run_controller(self) -> None:
            result = self.controller.run()
            self._completed_result = result
            if self._exit_on_complete:
                self.call_from_thread(self.exit, result)
            else:
                self.call_from_thread(self.refresh_view)

        def action_stop_after_current_step(self) -> None:
            if self._completed_result is not None:
                self.exit(self._completed_result)
                return
            self.controller.request_stop_after_current_step()
            self.refresh_view()

        def action_interrupt(self) -> None:
            if self._completed_result is not None:
                self.exit(self._completed_result)
                return
            self._exit_on_complete = True
            self.controller.interrupt()
            self.refresh_view()

        def action_refresh(self) -> None:
            self.refresh_view()

        def action_help(self) -> None:
            self.notify(footer_text())

        def action_show_overview(self) -> None:
            self._show_view("overview")

        def action_show_files(self) -> None:
            self._show_view("files")

        def action_show_rules(self) -> None:
            self._show_view("rules")

        def action_show_cells(self) -> None:
            self._show_view("cells")

        def action_show_findings(self) -> None:
            self._show_view("findings")

        def action_show_agent(self) -> None:
            self._show_view("agent")

        def _show_view(self, view_name: str) -> None:
            self._active_view = view_name
            self.refresh_view()

        def refresh_view(self) -> None:
            self._force_full_refresh()

        def _force_full_refresh(self) -> None:
            self.snapshot = self.controller.snapshot()
            self._last_full_refresh_at = monotonic()
            self._advance_liveness_frame()
            self._render_from_snapshot()

        def _advance_liveness_frame(self) -> None:
            if self.snapshot.agent_status in {"running", "starting"}:
                self._activity_frame += 1

        def _render_from_snapshot(self) -> None:
            view = dashboard_state(
                self.snapshot,
                self.controller.events,
                activity_frame=self._activity_frame,
                active_view=self._active_view,
            )
            sections = tui_render_sections(view)
            self._tui_render_state = update_tui_render_state(
                self._tui_render_state, tuple(sections.values())
            )
            flashes = self._tui_render_state.flashes
            try:
                session_header = self.query_one("#session_header", Vertical)
                header_status_line = self.query_one("#header_status_line", Static)
                header_agent_line = self.query_one("#header_agent_line", Static)
                queue_panel_container = self.query_one("#queue_panel_container", Vertical)
                queue_panel = self.query_one("#queue_panel", Static)
                rules_panel_container = self.query_one("#rules_panel_container", Vertical)
                rules_panel = self.query_one("#rules_panel", Static)
                files_panel_container = self.query_one("#files_panel_container", Vertical)
                files_panel = self.query_one("#files_panel", Static)
                findings_panel_container = self.query_one("#findings_panel_container", Vertical)
                findings_panel = self.query_one("#findings_panel", Static)
                activity_timeline = self.query_one("#activity_timeline", Static)
                activity_panel_container = self.query_one("#activity_panel_container", Vertical)
                legend = self.query_one("#legend", Static)
            except (NoMatches, ScreenStackError):
                return
            header_status_line.update(
                render_tui_lines(sections["header_status"], flashes, mode="rich")
            )
            header_agent_line.update(
                render_tui_lines(sections["header_agent"], flashes, mode="rich")
            )
            for state_class in (
                "panel",
                "panel-active",
                "panel-blocked",
                "panel-failed",
                "panel-finalized",
            ):
                state_active = state_class == view.state_class
                panel_or_state_active = state_class == "panel" or state_active
                session_header.set_class(state_active, state_class)
                queue_panel_container.set_class(panel_or_state_active, state_class)
                activity_panel_container.set_class(panel_or_state_active, state_class)
            finalized = view.finalized_summary is not None
            queue_panel_container.border_title = (
                "Finalized summary" if finalized else PANEL_TITLES["queue"]
            )
            queue_panel_container.display = bool(sections["queue"])
            queue_panel.update(render_tui_lines(sections["queue"], flashes, mode="rich"))
            rules_panel_container.display = not finalized
            files_panel_container.display = not finalized
            findings_panel_container.display = not finalized
            activity_panel_container.display = not finalized and view.active_view != "agent"
            rules_panel_container.border_title = _rules_panel_title(view.active_view)
            rules_panel.update(_render_rules_panel(view, flashes))
            files_panel_container.border_title = _files_panel_title(view.active_view)
            files_panel.update(_render_files_panel(view, flashes))
            findings_panel_container.border_title = findings_panel_title(view)
            if view.active_view == "agent":
                findings_panel.update(agent_summary_text(view))
            else:
                f_limit = 16 if view.active_view == "findings" else 5
                findings_panel.update(
                    render_tui_lines(findings_tui_lines(view, limit=f_limit), flashes, mode="rich")
                )
            activity_timeline.update(render_tui_lines(sections["activity"], flashes, mode="rich"))
            legend.update(render_tui_lines(color_legend_tui_lines(), flashes, mode="rich"))

    return RunApp(controller)


COMPLETED_COVERAGE_STATES = frozenset({"covered", "reviewed", "done"})
INCOMPLETE_COVERAGE_STATES = frozenset({"pending"})
EXCLUDED_COVERAGE_STATES = frozenset()
FINDING_STATES = ("open", "confirmed", "dismissed")
_FINDING_STATE_LABELS = ("open", "confirmed", "dismissed")
_FINDING_STATE_ABBREV: dict[str, str] = {
    "open": "open",
    "confirmed": "conf",
    "dismissed": "dismiss",
}
_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_BAR_WIDTH = 24
_FLASH_STYLE = "bold #fef3c7 on #3f3520"
_FLASH_DURATION_SECONDS = 0.9
_FIELD_RENDER_MODE = Literal["plain", "rich"]
_FAILED_AGENT_STATUSES = frozenset(
    {
        "failed",
        "timed_out",
        "command_failed",
        "startup_error",
        "template_error",
        "interrupted",
        "cancelled",
        "max_steps_exhausted",
    }
)
_AGENT_STATUS_LABELS = {
    "idle": "idle",
    "running": "running",
    "starting": "starting",
    "quiet": "quiet but alive",
    "completed": "completed",
    "timed_out": "timed out",
    "command_failed": "command failed",
    "startup_error": "startup error",
    "template_error": "template error",
    "interrupted": "interrupted",
    "cancelled": "interrupted",
    "max_steps_exhausted": "max steps exhausted",
    "failed": "failed",
}
_PRIORITY_COLORS: dict[str, str] = {
    "P0": "bold #ef4444",
    "P1": "#f59e0b",
    "P2": "#60a5fa",
    "P3": "#6b7280",
}
_FINDING_STATE_COLORS: dict[str, str] = {
    "open": "#f59e0b",
    "confirmed": "bold #ef4444",
    "dismissed": "#6b7280",
}
_ACTIVITY_LABEL_COLORS: dict[str, str] = {
    "stdout": "#34d399",
    "stderr": "#f59e0b",
    "event": "#60a5fa",
}
_STATE_COLORS: dict[str, str] = {
    "stale": "#f59e0b",
    "pending": "#60a5fa",
    "reviewed": "#6b7280",
    "covered": "#6b7280",
    "done": "#6b7280",
    "superseded": "#4b5563",
}
_RULE_ID_COLOR = "#a78bfa"
_FINDING_ID_COLOR = "#93c5fd"
_FIND_COUNT_COLOR = "#c084fc"
_NEXT_ACTION_GATE_INDEX = {
    "run_review": 1,
    "resolve_findings": 2,
    "resolve_finalize_blockers": 3,
    "finalize": 4,
}


@dataclass(frozen=True)
class ProgressMetrics:
    completed: int
    total: int
    percent: int
    superseded: int
    incomplete: int
    pending: int = 0
    stale: int = 0
    terminal: int = 0


@dataclass(frozen=True)
class TaskDisplay:
    title: str
    description: str


@dataclass(frozen=True)
class TimelineEvent:
    time: str
    label: str
    detail: str


@dataclass(frozen=True)
class AgentSummary:
    command: str
    status: str
    output: str
    timeout: str
    artifact: str | None


@dataclass(frozen=True)
class SessionSummary:
    coverage: str
    findings: str
    current: str
    agent_step: str


@dataclass(frozen=True)
class FinalizedSummary:
    coverage_percent: int
    terminal_cells: int
    total_cells: int
    fixed_finding_count: int
    changed_files: tuple[str, ...]
    rule_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    elapsed: str
    step_count: int
    checkpoint: str


@dataclass(frozen=True)
class ActionableFindingSummary:
    open: int
    triage: int
    fix: int
    verify: int


@dataclass(frozen=True)
class FindingsProgress:
    resolved: int
    total: int


@dataclass(frozen=True)
class FinalizeGate:
    index: int
    title: str
    state: str
    detail: str


@dataclass(frozen=True)
class TuiField:
    key: str
    display: str
    compare: object
    color: str | None = None


@dataclass(frozen=True)
class TuiLine:
    fields: tuple[TuiField, ...]


@dataclass(frozen=True)
class TuiFlash:
    key: str
    expires_at: float


@dataclass(frozen=True)
class TuiRenderState:
    previous: dict[str, object]
    flashes: dict[str, TuiFlash]
    initialized: bool = False


def empty_tui_render_state() -> TuiRenderState:
    return TuiRenderState(previous={}, flashes={}, initialized=False)


@dataclass(frozen=True)
class RunViewState:
    status: str
    status_summary: str
    state_class: str
    session_short_id: str
    agent_name: str
    step_label: str
    gate_label: str
    active_gate: FinalizeGate
    gates: tuple[FinalizeGate, ...]
    coverage: ProgressMetrics
    open_findings: int
    findings_progress: FindingsProgress
    task: TaskDisplay
    command_label: str | None
    agent_summary: AgentSummary
    session_summary: SessionSummary
    timeline_events: tuple[TimelineEvent, ...]
    coverage_projection: CoverageProjection
    active_view: str
    activity: str
    activity_frame: int
    active_step_action: str | None
    active_target_finding_ids: tuple[str, ...]
    liveness_detail: str
    artifact_path: str | None
    elapsed: str
    finalized_summary: FinalizedSummary | None


def calculate_progress_metrics(
    coverage: dict[str, object], *, cell_terminal_count: int = 0
) -> ProgressMetrics:
    total = 0
    completed = 0
    superseded = 0
    pending = _count_value(coverage.get("pending", 0))
    stale = 0  # stale is intentionally ignored
    for state, raw_count in coverage.items():
        count = _count_value(raw_count)
        if state in EXCLUDED_COVERAGE_STATES:
            superseded += count
            continue
        total += count
        if state in COMPLETED_COVERAGE_STATES or state == "stale":
            completed += count
    displayed_completed = min(completed, total)
    percent = min(int((cell_terminal_count / total) * 100), 100) if total else 0
    return ProgressMetrics(
        displayed_completed,
        total,
        percent,
        superseded,
        pending,
        pending,
        stale,
        terminal=cell_terminal_count,
    )


def actionable_finding_summary(findings: dict[str, object]) -> ActionableFindingSummary:
    open_count = _count_value(findings.get("open", 0))
    return ActionableFindingSummary(open=open_count, triage=open_count, fix=0, verify=0)


def findings_progress(snapshot: RunSnapshot) -> FindingsProgress:
    projected_findings = snapshot.coverage_projection.findings
    if projected_findings:
        total = len(projected_findings)
        resolved = sum(1 for finding in projected_findings if not finding.actionable)
        return FindingsProgress(resolved=resolved, total=total)
    total = sum(_count_value(value) for value in snapshot.findings.values())
    open_count = _count_value(snapshot.findings.get("open", 0))
    return FindingsProgress(resolved=max(0, total - open_count), total=total)


def format_elapsed_time(seconds: float) -> str:
    total_seconds = 0 if not math.isfinite(seconds) else max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def short_session_id(session_id: str | None) -> str:
    if not session_id:
        return "none"
    safe = _plain_text(session_id)
    if len(safe) <= 12:
        return safe
    return f"{safe[:8]}…{safe[-4:]}"


def short_artifact_path(path: str) -> str:
    safe = _plain_text(path)
    marker = ".review-gauntlet/"
    if marker in safe:
        return marker + safe.rsplit(marker, maxsplit=1)[1]
    return _summarize_text(safe, limit=96)


def format_event_time(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).strftime("%H:%M:%S")
    except (ValueError, AttributeError):
        return "--:--:--"


_ACTION_TASK_DESCRIPTIONS: dict[str, str] = {
    "REVIEW PENDING CELLS": "Review cells that have not received coverage yet.",
    "REVIEW CELLS": "Review cells need coverage.",
    "RESOLVE FINDINGS": "Resolve open findings with judgment and fixes.",
    "RESOLVE FINALIZE BLOCKERS": "Resolve blockers before finalizing the session.",
    "FINALIZE SESSION": "Finalize the review session when all required work is complete.",
    "READY TASK": "An actionable ready task is available.",
}
_ACTION_TASK_TITLES: dict[str, str] = {
    "resolve_findings": "RESOLVE FINDINGS",
    "resolve_finalize_blockers": "RESOLVE FINALIZE BLOCKERS",
    "finalize": "FINALIZE SESSION",
}


def _task_display(title: str) -> TaskDisplay:
    return TaskDisplay(title, _ACTION_TASK_DESCRIPTIONS[title])


def format_task_title_from_action(
    next_required_action: str | None,
    coverage: dict[str, object],
    findings: dict[str, object],
) -> TaskDisplay:
    del findings
    if next_required_action is None:
        return _task_display("READY TASK")
    if next_required_action == "run_review":
        if _count_value(coverage.get("pending", 0)) > 0:
            return _task_display("REVIEW PENDING CELLS")
        return _task_display("REVIEW CELLS")
    title = _ACTION_TASK_TITLES.get(next_required_action)
    if title is not None:
        return _task_display(title)
    return _task_display("READY TASK")


def format_command_label(snapshot: RunSnapshot) -> str | None:
    if snapshot.command_label:
        return _summarize_text(snapshot.command_label, limit=80)
    if snapshot.command_argv:
        return sanitize_agent_output_line(" ".join(snapshot.command_argv), limit=80)
    if snapshot.agent_status == "running":
        return "command resolving..."
    return None


def dashboard_state(
    snapshot: RunSnapshot,
    events: tuple[RunEvent, ...],
    *,
    activity_frame: int = 0,
    active_view: str = "overview",
) -> RunViewState:
    status_summary, state_class = terminal_state(snapshot.agent_status)
    command_label = format_command_label(snapshot)
    gates = derive_finalize_gates(snapshot)
    active_gate = select_active_gate(snapshot, gates)
    timeline_events = tuple(format_activity_event(event) for event in events[-10:])
    output_events = tuple(
        format_agent_output_entry(entry) for entry in snapshot.agent_lifecycle.output_tail[-6:]
    )
    liveness_detail = agent_liveness_detail(snapshot)
    coverage = calculate_progress_metrics(
        snapshot.coverage, cell_terminal_count=snapshot.cell_terminal_count
    )
    findings_summary = actionable_finding_summary(snapshot.findings)
    findings_progress_summary = findings_progress(snapshot)
    task = format_task_title_from_action(
        snapshot.next_required_action,
        snapshot.coverage,
        snapshot.findings,
    )
    artifact_path = snapshot.agent_lifecycle.artifact_path
    elapsed = format_elapsed_time(snapshot.elapsed_seconds)
    return RunViewState(
        status=snapshot.agent_status,
        status_summary=status_summary,
        state_class=state_class,
        session_short_id=short_session_id(snapshot.session_id),
        agent_name=command_label or "agent idle",
        step_label=f"agent step {snapshot.step}",
        gate_label=f"gate {active_gate.index}/{len(gates)}",
        active_gate=active_gate,
        gates=gates,
        coverage=coverage,
        open_findings=findings_summary.open,
        findings_progress=findings_progress_summary,
        task=task,
        command_label=command_label,
        agent_summary=build_agent_summary(snapshot, command_label, liveness_detail, artifact_path),
        session_summary=build_session_summary(snapshot, coverage, active_gate, findings_summary),
        timeline_events=timeline_events + output_events,
        coverage_projection=snapshot.coverage_projection,
        active_view=active_view,
        activity=agent_activity_text(
            _display_agent_status(snapshot), activity_frame=activity_frame
        ),
        activity_frame=activity_frame,
        active_step_action=snapshot.active_step_action,
        active_target_finding_ids=snapshot.active_target_finding_ids,
        liveness_detail=liveness_detail,
        artifact_path=artifact_path,
        elapsed=elapsed,
        finalized_summary=derive_finalized_summary(snapshot, coverage, elapsed),
    )


def derive_finalized_summary(
    snapshot: RunSnapshot, coverage: ProgressMetrics, elapsed: str
) -> FinalizedSummary | None:
    if snapshot.agent_status != "finalized" and snapshot.session_state != "finalized":
        return None
    projection = snapshot.coverage_projection
    changed_files = tuple(
        sorted({entry.file_path for entry in projection.queue if entry.changed_since_review})
    )
    changed_file_set = frozenset(changed_files)
    fixed_findings = tuple(
        finding
        for finding in projection.findings
        if finding.file_path in changed_file_set
        and finding.state in {"fixed_pending_verification", "fixed_verified"}
    )
    rule_ids = tuple(sorted({finding.rule_id for finding in fixed_findings}))
    return FinalizedSummary(
        coverage_percent=coverage.percent,
        terminal_cells=coverage.terminal,
        total_cells=coverage.total,
        fixed_finding_count=len(fixed_findings),
        changed_files=changed_files,
        rule_ids=rule_ids,
        finding_ids=tuple(finding.finding_id for finding in fixed_findings),
        elapsed=elapsed,
        step_count=snapshot.run_count or snapshot.step,
        checkpoint=_checkpoint_summary(snapshot.checkpoint_commit),
    )


def _checkpoint_summary(checkpoint: dict[str, object] | None) -> str:
    if checkpoint is None:
        return "unavailable (no checkpoint metadata)"
    commit = checkpoint.get("checkpoint_commit")
    if isinstance(commit, str) and commit:
        return commit[:12]
    reason = checkpoint.get("checkpoint_commit_reason")
    if isinstance(reason, str) and reason:
        return f"unavailable ({reason})"
    return "unavailable (no commit recorded)"


def select_active_gate(snapshot: RunSnapshot, gates: tuple[FinalizeGate, ...]) -> FinalizeGate:
    mapped_index = _NEXT_ACTION_GATE_INDEX.get(snapshot.next_required_action or "")
    if mapped_index is not None:
        return gates[mapped_index - 1]
    return next(
        (gate for gate in gates if gate.state in {"running", "blocked", "failed", "next"}),
        gates[-1],
    )


def build_agent_summary(
    snapshot: RunSnapshot,
    command_label: str | None,
    liveness_detail: str,
    artifact_path: str | None,
) -> AgentSummary:
    lifecycle = snapshot.agent_lifecycle
    output = "no output yet"
    if lifecycle.last_output_age_seconds is not None:
        output = f"last output {format_duration(lifecycle.last_output_age_seconds)} ago"
    timeout = "not configured"
    if lifecycle.timeout_remaining_seconds is not None:
        timeout = f"in {format_duration(lifecycle.timeout_remaining_seconds)}"
    elif lifecycle.timeout_seconds is not None:
        timeout = f"configured {format_duration(lifecycle.timeout_seconds)}"
    artifact = short_artifact_path(artifact_path) if artifact_path is not None else None
    return AgentSummary(
        command=command_label or "command resolving...",
        status=liveness_detail,
        output=output,
        timeout=timeout,
        artifact=artifact,
    )


def build_session_summary(
    snapshot: RunSnapshot,
    coverage: ProgressMetrics,
    active_gate: FinalizeGate,
    findings_summary: ActionableFindingSummary,
) -> SessionSummary:
    finding_parts: list[str] = []
    for state in _FINDING_STATE_LABELS:
        count = _count_value(snapshot.findings.get(state, 0))
        if count:
            abbr = _FINDING_STATE_ABBREV.get(state, state)
            finding_parts.append(f"{abbr} {count}")
    findings = "  ".join(finding_parts) if finding_parts else "none"
    return SessionSummary(
        coverage=f"{coverage.percent}%   {coverage.completed} / {coverage.total}",
        findings=findings,
        current=active_gate.title.lower(),
        agent_step=str(snapshot.step),
    )


@dataclass(frozen=True)
class BlockerGroups:
    coverage: tuple[str, ...]
    findings: tuple[str, ...]
    final_checks: tuple[str, ...]


def classify_finalize_blockers(blockers: tuple[str, ...]) -> BlockerGroups:
    coverage: list[str] = []
    findings: list[str] = []
    final_checks: list[str] = []
    for blocker in blockers:
        normalized = blocker.lower()
        if "review cells are still pending" in normalized:
            coverage.append(blocker)
        elif "findings remain open" in normalized:
            findings.append(blocker)
        else:
            final_checks.append(blocker)
    return BlockerGroups(tuple(coverage), tuple(findings), tuple(final_checks))


def _is_finalize_ready_timeout(snapshot: RunSnapshot) -> bool:
    return (
        snapshot.agent_status == "timed_out"
        and snapshot.can_finalize
        and not snapshot.finalize_blockers
    )


def derive_finalize_gates(snapshot: RunSnapshot) -> tuple[FinalizeGate, ...]:
    coverage = calculate_progress_metrics(snapshot.coverage)
    open_count = _count_value(snapshot.findings.get("open", 0))
    blockers = classify_finalize_blockers(snapshot.finalize_blockers)
    failed = snapshot.agent_status in _FAILED_AGENT_STATUSES
    finalized = snapshot.agent_status == "finalized" or snapshot.session_state == "finalized"

    review_state = "done" if coverage.incomplete == 0 else "running"
    review_detail = (
        f"{coverage.completed} / {coverage.total} reviewed, {coverage.incomplete} pending"
    )
    resolve_state = "next" if review_state != "done" else ("running" if open_count else "done")
    resolve_detail = (
        "waits for review"
        if review_state != "done"
        else _count_detail(
            open_count,
            "open finding needs resolution",
            "no open findings",
            plural="open findings need resolution",
        )
    )
    if resolve_state != "done":
        final_checks_state = "later"
        final_checks_detail = "checked after review/resolve"
    elif blockers.final_checks:
        final_checks_state = "blocked"
        final_checks_detail = _summarize_text(blockers.final_checks[0], limit=64)
    else:
        final_checks_state = "done"
        final_checks_detail = "ready"
    if finalized:
        checkpoint_state = "done"
        checkpoint_detail = "complete"
    elif _is_finalize_ready_timeout(snapshot):
        checkpoint_state = "running"
        checkpoint_detail = "agent timed out; run review-gauntlet finalize"
    elif final_checks_state == "done" and snapshot.can_finalize:
        checkpoint_state = "running"
        checkpoint_detail = "ready to finalize"
    else:
        checkpoint_state = "later"
        checkpoint_detail = "waiting"
    gates = [
        FinalizeGate(1, "Review phase", review_state, review_detail),
        FinalizeGate(2, "Resolve phase", resolve_state, resolve_detail),
        FinalizeGate(3, "Final checks", final_checks_state, final_checks_detail),
        FinalizeGate(4, "Finalize checkpoint", checkpoint_state, checkpoint_detail),
    ]
    if finalized:
        return tuple(FinalizeGate(gate.index, gate.title, "done", "complete") for gate in gates)
    if (
        failed
        and not _is_finalize_ready_timeout(snapshot)
        and any(gate.state in {"running", "blocked", "next", "later"} for gate in gates)
    ):
        return tuple(
            FinalizeGate(item.index, item.title, "failed", item.detail)
            if item.state in {"running", "blocked", "next", "later"}
            else item
            for item in gates
        )
    return tuple(gates)


def _display_agent_status(snapshot: RunSnapshot) -> str:
    if snapshot.agent_status == "running" and snapshot.agent_lifecycle.status == "idle":
        return "running"
    return snapshot.agent_lifecycle.status or snapshot.agent_status


def agent_liveness_detail(snapshot: RunSnapshot) -> str:
    lifecycle = snapshot.agent_lifecycle
    display_status = _display_agent_status(snapshot)
    if display_status == "quiet":
        quiet_for = lifecycle.last_output_age_seconds
        if quiet_for is not None:
            return f"quiet {format_duration(quiet_for)}"
        return "quiet but alive"
    return agent_activity_text(display_status)


def format_duration(seconds: float) -> str:
    safe_seconds = 0 if not math.isfinite(seconds) else max(0, int(seconds))
    if safe_seconds < 60:
        return f"{safe_seconds}s"
    minutes, remainder = divmod(safe_seconds, 60)
    if minutes < 60:
        return f"{minutes}m{remainder:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def terminal_state(agent_status: str) -> tuple[str, str]:
    status = _plain_text(agent_status)
    if status == "running":
        return "RUNNING", "panel-active"
    if status == "starting":
        return "STARTING", "panel-active"
    if status == "blocked":
        return "BLOCKED", "panel-blocked"
    if status in _FAILED_AGENT_STATUSES:
        return _agent_terminal_label(status), "panel-failed"
    if status in {"finalized", "completed"}:
        return "FINALIZED", "panel-finalized"
    return f"READY {_agent_status_label(status).upper()}", "panel"


def _agent_terminal_label(status: str) -> str:
    if status == "timed_out":
        return "TIMED OUT"
    if status == "command_failed":
        return "COMMAND FAILED"
    if status == "startup_error":
        return "STARTUP ERROR"
    if status == "template_error":
        return "TEMPLATE ERROR"
    if status in {"interrupted", "cancelled"}:
        return "INTERRUPTED"
    if status == "max_steps_exhausted":
        return "MAX STEPS EXHAUSTED"
    return "FAILED"


def _agent_status_label(status: str) -> str:
    return _AGENT_STATUS_LABELS.get(status, status.replace("_", " "))


def header_title_text() -> str:
    return f"✻ Review Gauntlet v{__version__}"


def header_status_text(view: RunViewState) -> str:
    blocker = " · finalize BLOCKED" if view.state_class == "panel-blocked" else ""
    cov = view.coverage
    bar = _progress_bar(cov.terminal, cov.total)
    parts = [f"Finalize {cov.percent}% {bar} {cov.terminal}/{cov.total}"]
    if cov.pending:
        parts.append(f"pend {cov.pending}")
    # cov.stale is always 0 (stale cells count as completed in calculate_progress_metrics)
    if cov.stale:
        parts.append(f"stale {cov.stale}")
    coverage = "   ".join(parts)
    return (
        f"{view.session_short_id} · {view.status_summary}{blocker} · {view.gate_label}   {coverage}"
    )


def header_agent_text(view: RunViewState) -> str:
    summary = view.agent_summary
    parts = [f"Agent    {summary.command}"]
    if view.step_label:
        parts.append(view.step_label)
    parts.append(view.activity)
    parts.append(summary.output)
    parts.append(f"timeout {summary.timeout}")
    return " · ".join(parts)


def header_meta_text(view: RunViewState) -> str:
    return f"{view.session_short_id} · agent {view.agent_name} · {view.liveness_detail}"


def header_text(view: RunViewState) -> str:
    return "\n".join(
        [
            header_title_text(),
            header_status_text(view),
            header_agent_text(view),
        ]
    )


def progress_text(snapshot: RunSnapshot, *, activity_frame: int = 0) -> str:
    return header_text(dashboard_state(snapshot, (), activity_frame=activity_frame))


def update_tui_render_state(
    state: TuiRenderState,
    sections: tuple[tuple[TuiLine, ...], ...],
    *,
    now: float | None = None,
    flash_duration_seconds: float = _FLASH_DURATION_SECONDS,
) -> TuiRenderState:
    current_time = time.monotonic() if now is None else now
    current = _field_compare_map(sections)
    flashes = {
        key: flash
        for key, flash in state.flashes.items()
        if flash.expires_at > current_time and key in current
    }
    if state.initialized:
        for key, value in current.items():
            if (key in state.previous and state.previous[key] != value) or (
                key not in state.previous and _is_activity_value_key(key)
            ):
                flashes[key] = TuiFlash(key=key, expires_at=current_time + flash_duration_seconds)
    return TuiRenderState(previous=current, flashes=flashes, initialized=True)


def tui_render_sections(view: RunViewState) -> dict[str, tuple[TuiLine, ...]]:
    if view.finalized_summary is not None:
        return {
            "header_status": header_status_tui_lines(view),
            "header_agent": header_agent_tui_lines(view),
            "queue": finalized_summary_tui_lines(view),
            "activity": (),
            "rules": (),
            "files": (),
            "findings": (),
        }
    return {
        "header_status": header_status_tui_lines(view),
        "header_agent": header_agent_tui_lines(view),
        "queue": queue_tui_lines(view),
        "activity": activity_tui_lines(view),
        "rules": rules_tui_lines(view),
        "files": files_tui_lines(view),
        "findings": findings_tui_lines(view),
    }


def render_tui_lines(
    lines: tuple[TuiLine, ...],
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> Any:
    flash_keys = frozenset(flashes or {})
    if mode == "rich":
        from rich.text import Text

        rendered = Text()
        for line_index, line in enumerate(lines):
            if line_index:
                rendered.append("\n")
            for field in line.fields:
                style: str | None = None
                if field.key in flash_keys:
                    style = _FLASH_STYLE
                elif field.color is not None:
                    style = field.color
                rendered.append(field.display, style=style)
        return rendered
    return "\n".join("".join(field.display for field in line.fields) for line in lines)


def header_status_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    blocker = " · finalize BLOCKED" if view.state_class == "panel-blocked" else ""
    cov = view.coverage
    bar = _progress_bar(cov.terminal, cov.total)
    coverage_parts = [f"{cov.percent}% {bar} {cov.terminal}/{cov.total}"]
    if cov.pending:
        coverage_parts.append(f"pend {cov.pending}")
    # cov.stale is always 0 (stale cells count as completed in calculate_progress_metrics)
    if cov.stale:
        coverage_parts.append(f"stale {cov.stale}")
    coverage_text = "   ".join(coverage_parts)
    return (
        TuiLine(
            (
                _field("header.session", view.session_short_id),
                _literal(" · ", key="header.sep.s1"),
                _field("header.status", view.status_summary),
                _field("header.blocker", blocker, compare=blocker),
                _literal(" · ", key="header.sep.s2"),
                _field("header.gate", view.gate_label, compare=view.active_gate.index),
                _literal("   ", key="header.sep.s3"),
                _field(
                    "header.cov",
                    coverage_text,
                    compare=(cov.terminal, cov.completed, cov.total, cov.percent),
                ),
            )
        ),
    )


def header_agent_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    summary = view.agent_summary
    parts: list[str] = [summary.command]
    if view.step_label:
        parts.append(view.step_label)
    parts.append(view.activity)
    parts.append(summary.output)
    parts.append(f"timeout {summary.timeout}")
    return (
        TuiLine(
            (
                _literal("Agent    ", key="header.agent.label"),
                _field(
                    "header.agent.body",
                    " · ".join(parts),
                    compare=(
                        view.agent_summary.command,
                        view.step_label,
                        view.activity,
                        _agent_output_compare(view.agent_summary.output),
                    ),
                ),
            )
        ),
    )


def header_meta_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    return (
        TuiLine(
            (
                _field("header.meta.session", view.session_short_id),
                _literal(" · agent ", key="header.meta.agent_prefix"),
                _field("header.meta.agent", view.agent_name),
                _literal(" · ", key="header.meta.sep"),
                _field(
                    "header.meta.liveness",
                    view.liveness_detail,
                    compare=_semantic_liveness_compare(view.liveness_detail),
                ),
            )
        ),
    )


def finalize_path_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    lines: list[TuiLine] = []
    for gate in view.gates:
        marker = {"done": "✓", "running": "▶", "blocked": "!", "failed": "×"}.get(gate.state, " ")
        prefix = f"gate.{gate.index}"
        lines.append(
            TuiLine(
                (
                    _field(f"finalize.{prefix}.marker", marker),
                    _literal(" ", key=f"finalize.{prefix}.marker_space"),
                    _field(f"finalize.{prefix}.title", f"{gate.title:<24}", compare=gate.title),
                    _literal(" ", key=f"finalize.{prefix}.title_space"),
                    _field(f"finalize.{prefix}.state", f"{gate.state:<7}", compare=gate.state),
                    _literal(" ", key=f"finalize.{prefix}.state_space"),
                    _field(f"finalize.{prefix}.detail", gate.detail),
                )
            )
        )
    return tuple(lines)


def finalized_summary_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    summary = view.finalized_summary
    if summary is None:
        return ()
    changed_files = _none_or_join(summary.changed_files)
    rule_ids = _none_or_join(summary.rule_ids)
    finding_ids = _none_or_join(summary.finding_ids)
    return (
        TuiLine(
            (
                _literal("Final coverage  ", key="finalized.coverage.label"),
                _field(
                    "finalized.coverage.percent",
                    f"{summary.coverage_percent}%",
                    compare=summary.coverage_percent,
                ),
                _literal("   terminal/total cells ", key="finalized.coverage.cells_label"),
                _field(
                    "finalized.coverage.cells",
                    f"{summary.terminal_cells}/{summary.total_cells}",
                    compare=(summary.terminal_cells, summary.total_cells),
                ),
            )
        ),
        TuiLine(
            (
                _literal("Run summary     ", key="finalized.run.label"),
                _field(
                    "finalized.run.elapsed", f"elapsed {summary.elapsed}", compare=summary.elapsed
                ),
                _literal(" · ", key="finalized.run.sep"),
                _field(
                    "finalized.run.steps",
                    f"steps {summary.step_count}",
                    compare=summary.step_count,
                ),
            )
        ),
        _label_value_line("finalized.checkpoint", "Checkpoint      ", summary.checkpoint),
        _label_value_line(
            "finalized.finding_count",
            "Fixed findings  ",
            str(summary.fixed_finding_count),
            compare=summary.fixed_finding_count,
        ),
        _label_value_line("finalized.files", "Changed files   ", changed_files),
        _label_value_line("finalized.rules", "Rules           ", rule_ids),
        _label_value_line("finalized.findings", "Finding IDs     ", finding_ids),
    )


def _none_or_join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def queue_tui_lines(view: RunViewState, *, limit: int = 4) -> tuple[TuiLine, ...]:
    entries = actionable_queue_entries(view, limit=limit)
    if not entries:
        return ()
    lines: list[TuiLine] = []
    for index, entry in enumerate(entries, start=1):
        prefix = f"queue.{entry.file_path}"
        cell_label = f"{entry.cell_count} cells" if entry.cell_count > 1 else "1 cell"
        cell_label = f"{cell_label:<7}"
        lines.append(
            TuiLine(
                (
                    _field(f"{prefix}.rank", f"{index:>2}. ", compare=index),
                    _colored_field(
                        f"{prefix}.priority",
                        f"{entry.priority_label} ",
                        _PRIORITY_COLORS.get(entry.priority_label, ""),
                    ),
                    _field(f"{prefix}.cells", cell_label, compare=entry.cell_count),
                    _literal(" ", key=f"{prefix}.cells_space"),
                    _field(f"{prefix}.file", _summarize_text(entry.file_path, limit=36)),
                    _literal(" · ", key=f"{prefix}.why_sep"),
                    _field(
                        f"{prefix}.why",
                        _summarize_text(entry.why, limit=48),
                        compare=entry.why,
                    ),
                )
            )
        )
    return tuple(lines)


def agent_summary_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    lines = [
        _label_value_line("agent.command", "command ", view.agent_summary.command),
        _label_value_line(
            "agent.status",
            "status  ",
            view.agent_summary.status,
            compare=_semantic_liveness_compare(view.agent_summary.status),
        ),
        _label_value_line(
            "agent.output",
            "output  ",
            view.agent_summary.output,
            compare=_agent_output_compare(view.agent_summary.output),
        ),
        _label_value_line(
            "agent.timeout",
            "timeout ",
            view.agent_summary.timeout,
            compare=_agent_timeout_compare(view.agent_summary.timeout),
        ),
    ]
    if view.agent_summary.artifact is not None:
        lines.append(_label_value_line("agent.artifact", "artifact ", view.agent_summary.artifact))
    return tuple(lines)


def session_summary_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    coverage = view.coverage
    return (
        TuiLine(
            (
                _literal("Coverage  ", key="session.coverage.label"),
                _field(
                    "session.coverage.percent", f"{coverage.percent}%", compare=coverage.percent
                ),
                _literal("   ", key="session.coverage.percent_sep"),
                _field(
                    "session.coverage.completed",
                    str(coverage.completed),
                    compare=coverage.completed,
                ),
                _literal(" / ", key="session.coverage.count_sep"),
                _field("session.coverage.total", str(coverage.total), compare=coverage.total),
            )
        ),
        TuiLine(
            (
                _literal("Findings  ", key="session.findings.label"),
                _field(
                    "session.findings.detail",
                    view.session_summary.findings,
                    compare=view.session_summary.findings,
                ),
            )
        ),
        _label_value_line("session.current", "Current   ", view.session_summary.current),
        _label_value_line(
            "session.agent_step",
            "Agent step ",
            view.session_summary.agent_step,
            compare=view.session_summary.agent_step,
        ),
    )


def activity_tui_lines(view: RunViewState) -> tuple[TuiLine, ...]:
    if not view.timeline_events:
        return (TuiLine((_field("activity.empty", "--:--:-- waiting for run activity"),)),)
    lines: list[TuiLine] = []
    for i, event in enumerate(view.timeline_events):
        identity = _activity_identity(event)
        prefix = f"activity.{i}.{identity}"
        suffix = f" - {event.detail}" if event.detail else ""
        lines.append(
            TuiLine(
                (
                    _field(f"{prefix}.time", event.time, compare="timestamp"),
                    _literal(" ", key=f"{prefix}.time_space"),
                    _colored_field(
                        f"{prefix}.label",
                        event.label,
                        _ACTIVITY_LABEL_COLORS.get(event.label, ""),
                    ),
                    _field(f"{prefix}.detail", suffix, compare=(event.label, event.detail)),
                )
            )
        )
    return tuple(lines)


def findings_tui_lines(view: RunViewState, *, limit: int = 5) -> tuple[TuiLine, ...]:
    findings = tuple(finding for finding in view.coverage_projection.findings if finding.actionable)
    if not findings:
        return ()
    active_target_ids = set(view.active_target_finding_ids)
    show_resolve_indicators = (
        view.status == "running"
        and view.active_step_action == "resolve_findings"
        and bool(active_target_ids)
    )
    spinner = _SPINNER_FRAMES[view.activity_frame % len(_SPINNER_FRAMES)]
    lines: list[TuiLine] = []
    for finding in findings[:limit]:
        prefix = f"finding.{finding.finding_id}"
        state_color = _FINDING_STATE_COLORS.get(finding.state, "")
        indicator = (
            spinner if show_resolve_indicators and finding.finding_id in active_target_ids else " "
        )
        indicator_fields = (
            (_field(f"{prefix}.active", f"{indicator} ", compare=indicator),)
            if show_resolve_indicators
            else ()
        )
        lines.append(
            TuiLine(
                (
                    *indicator_fields,
                    _colored_field(
                        f"{prefix}.id",
                        f"{finding.finding_id:<12}",
                        _FINDING_ID_COLOR,
                        compare=finding.finding_id,
                    ),
                    _colored_field(
                        f"{prefix}.state",
                        f"{finding.state:<28}",
                        state_color,
                        compare=finding.state,
                    ),
                    _colored_field(
                        f"{prefix}.rule",
                        f"{finding.rule_id:<18}",
                        _RULE_ID_COLOR,
                        compare=finding.rule_id,
                    ),
                    _field(
                        f"{prefix}.file",
                        _summarize_text(finding.file_path, limit=36),
                    ),
                    _literal(" · ", key=f"{prefix}.sep"),
                    _field(
                        f"{prefix}.content",
                        _summarize_text(finding.content, limit=72),
                    ),
                )
            )
        )
    return tuple(lines)


def finalize_path_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(finalize_path_tui_lines(view), flashes, mode=mode)


def agent_summary_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(agent_summary_tui_lines(view), flashes, mode=mode)


def session_summary_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(session_summary_tui_lines(view), flashes, mode=mode)


def activity_tui_render(
    view: RunViewState,
    flashes: dict[str, TuiFlash] | None = None,
    *,
    mode: _FIELD_RENDER_MODE = "plain",
) -> object:
    return render_tui_lines(activity_tui_lines(view), flashes, mode=mode)


def _field(key: str, display: str, *, compare: object | None = None) -> TuiField:
    return TuiField(key=key, display=display, compare=display if compare is None else compare)


def _colored_field(
    key: str, display: str, color: str, *, compare: object | None = None
) -> TuiField:
    return TuiField(
        key=key, display=display, color=color, compare=display if compare is None else compare
    )


def _literal(display: str, *, key: str) -> TuiField:
    return TuiField(key=key, display=display, compare=display)


def _join_fields(
    fields: tuple[TuiField, ...], separator: str, *, key_prefix: str
) -> tuple[TuiField, ...]:
    joined: list[TuiField] = []
    for index, field in enumerate(fields):
        if index:
            joined.append(_literal(separator, key=f"{key_prefix}.{index}"))
        joined.append(field)
    return tuple(joined)


def _label_value_line(
    key: str, label: str, value: str, *, compare: object | None = None
) -> TuiLine:
    return TuiLine(
        (
            _literal(label, key=f"{key}.label"),
            _field(f"{key}.value", value, compare=value if compare is None else compare),
        )
    )


def _field_compare_map(sections: tuple[tuple[TuiLine, ...], ...]) -> dict[str, object]:
    result: dict[str, object] = {}
    for lines in sections:
        for line in lines:
            for field in line.fields:
                result[field.key] = field.compare
    return result


def _is_activity_value_key(key: str) -> bool:
    return key.startswith("activity.") and key.endswith(".detail")


def _semantic_liveness_compare(value: str) -> object:
    if value.startswith("quiet "):
        return ("quiet",)
    if value.startswith("last output "):
        return ("last_output",)
    return value


def _agent_output_compare(value: str) -> object:
    if value.startswith("last output "):
        return ("last_output",)
    return value


def _agent_timeout_compare(value: str) -> object:
    if value.startswith("in "):
        return ("countdown",)
    if value.startswith("configured "):
        return ("configured",)
    return value


def _activity_identity(event: TimelineEvent) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", f"{event.label}-{event.detail}").strip("-")
    if not normalized:
        return "empty"
    return normalized[:80]


def titled_section(title: str, body: str) -> str:
    return f"{title}\n{body}" if body else ""


def compact_dashboard_text(snapshot: RunSnapshot, events: tuple[RunEvent, ...] = ()) -> str:
    view = dashboard_state(snapshot, events)
    if view.finalized_summary is not None:
        return "\n".join(
            part
            for part in (
                header_text(view),
                titled_section("Finalized summary", finalized_summary_text(view)),
                footer_text(),
            )
            if part
        )
    parts = [
        header_text(view),
        titled_section(PANEL_TITLES["queue"], queue_text(view)),
        titled_section(PANEL_TITLES["rules"], rule_coverage_text(view)),
        titled_section(PANEL_TITLES["files"], file_hotlist_text(view)),
        titled_section(findings_panel_title(view), finding_projection_text(view)),
        titled_section(PANEL_TITLES["activity"], activity_text(view)),
        footer_text(),
    ]
    return "\n".join(part for part in parts if part)


def finalize_path_text(view: RunViewState) -> str:
    lines: list[str] = []
    for gate in view.gates:
        marker = {"done": "✓", "running": "▶", "blocked": "!", "failed": "×"}.get(gate.state, " ")
        lines.append(f"{marker} {gate.title:<24} {gate.state:<7} {gate.detail}")
    return "\n".join(lines)


def coverage_text(snapshot: RunSnapshot) -> str:
    metrics = calculate_progress_metrics(
        snapshot.coverage, cell_terminal_count=snapshot.cell_terminal_count
    )
    return "\n".join(
        [
            f"{metrics.percent:3d}% {_progress_bar(metrics.terminal, metrics.total)}",
            f"terminal / total cells: {metrics.terminal} / {metrics.total}",
            (
                f"reviewed {metrics.completed} | terminal {metrics.terminal} | "
                f"pending {metrics.pending} | "
                f"superseded {metrics.superseded}"
            ),
        ]
    )


@dataclass(frozen=True)
class FileQueueEntry:
    file_path: str
    cell_count: int
    priority_label: str
    priority_score: int
    actionable_finding_count: int
    finding_count: int
    pending_count: int
    stale_count: int
    reviewed_count: int
    rule_ids: tuple[str, ...]
    why: str


def group_queue_by_file(
    entries: tuple[QueueEntry, ...], *, limit: int | None = None
) -> tuple[FileQueueEntry, ...]:
    groups: dict[str, list[QueueEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.file_path, []).append(entry)

    file_groups: list[dict[str, object]] = []
    for file_path, cell_entries in groups.items():
        highest_priority_label: str = "P3"
        highest_priority_score: int = 0
        actionable_finding_count = 0
        finding_count = 0
        pending_count = 0
        stale_count = 0
        reviewed_count = 0
        rule_ids: list[str] = []
        whys: list[str] = []
        for entry in cell_entries:
            actionable_finding_count += entry.actionable_finding_count
            finding_count += entry.finding_count
            if entry.state == "pending":
                pending_count += 1
            elif entry.state == "stale":
                stale_count += 1
            else:
                reviewed_count += 1
            if entry.rule_id not in rule_ids:
                rule_ids.append(entry.rule_id)
            if entry.why not in whys:
                whys.append(entry.why)
            entry_rank = _priority_rank(str(entry.priority_label))
            highest_rank = _priority_rank(highest_priority_label)
            if entry_rank < highest_rank:
                highest_priority_label = str(entry.priority_label)
                highest_priority_score = entry.priority_score
            elif entry_rank == highest_rank and entry.priority_score > highest_priority_score:
                highest_priority_score = entry.priority_score
        file_groups.append(
            {
                "file_path": file_path,
                "cell_count": len(cell_entries),
                "highest_priority_label": highest_priority_label,
                "highest_priority_score": highest_priority_score,
                "actionable_finding_count": actionable_finding_count,
                "finding_count": finding_count,
                "pending_count": pending_count,
                "stale_count": stale_count,
                "reviewed_count": reviewed_count,
                "rule_ids": rule_ids,
                "whys": whys,
            }
        )

    file_groups.sort(
        key=lambda g: (
            _priority_rank(str(g["highest_priority_label"])),
            -int(cast(int, g["highest_priority_score"])),
            str(g["file_path"]),
        )
    )
    entries_out: list[FileQueueEntry] = []
    for g in file_groups:
        parts: list[str] = []
        state_parts: list[str] = []
        pending = cast(int, g["pending_count"])
        stale = cast(int, g["stale_count"])
        reviewed = cast(int, g["reviewed_count"])
        actionable = cast(int, g["actionable_finding_count"])
        if pending:
            state_parts.append(f"{pending} pending")
        if stale:
            state_parts.append(f"{stale} stale")
        if reviewed:
            state_parts.append(f"{reviewed} reviewed")
        if state_parts:
            parts.append(", ".join(state_parts))
        if actionable:
            parts.append(f"{actionable} actionable finding(s)")
        rules_str = ", ".join(cast(list[str], g["rule_ids"]))
        parts.append(f"rules: {rules_str}")
        why = " · ".join(parts)
        entries_out.append(
            FileQueueEntry(
                file_path=str(g["file_path"]),
                cell_count=cast(int, g["cell_count"]),
                priority_label=str(g["highest_priority_label"]),
                priority_score=cast(int, g["highest_priority_score"]),
                actionable_finding_count=actionable,
                finding_count=cast(int, g["finding_count"]),
                pending_count=pending,
                stale_count=stale,
                reviewed_count=reviewed,
                rule_ids=tuple(cast(list[str], g["rule_ids"])),
                why=why,
            )
        )
    return tuple(entries_out[:limit] if limit is not None else entries_out)


def _priority_rank(label: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(label, 99)


def actionable_queue_entries(
    view: RunViewState, *, limit: int | None = None
) -> tuple[FileQueueEntry, ...]:
    entries = tuple(
        entry for entry in view.coverage_projection.queue if _entry_is_actionable(entry)
    )
    if not entries:
        entries = view.coverage_projection.queue
    return group_queue_by_file(entries, limit=limit)


def queue_text(view: RunViewState, *, limit: int = 4) -> str:
    return render_tui_lines(queue_tui_lines(view, limit=limit))


def finalized_summary_text(view: RunViewState) -> str:
    return render_tui_lines(finalized_summary_tui_lines(view))


def rule_coverage_text(view: RunViewState, *, limit: int = 5) -> str:
    if not view.coverage_projection.rules:
        return "no rule coverage details"
    return "\n".join(_format_rule_summary(rule) for rule in view.coverage_projection.rules[:limit])


def rules_tui_lines(view: RunViewState, *, limit: int = 5) -> tuple[TuiLine, ...]:
    rules = view.coverage_projection.rules[:limit]
    if not rules:
        return ()
    lines: list[TuiLine] = []
    for rule in rules:
        prefix = f"rule.{rule.rule_id}"
        lines.append(
            TuiLine(
                (
                    _colored_field(
                        f"{prefix}.priority",
                        rule.priority_label,
                        _PRIORITY_COLORS.get(rule.priority_label, ""),
                        compare=rule.priority_label,
                    ),
                    _literal(" ", key=f"{prefix}.p_space"),
                    _colored_field(
                        f"{prefix}.id",
                        f"{rule.rule_id:<18}",
                        _RULE_ID_COLOR,
                        compare=rule.rule_id,
                    ),
                    _field(
                        f"{prefix}.reviewed",
                        f"{rule.reviewed}/{rule.total}",
                        compare=rule.reviewed,
                    ),
                    _literal(" · ", key=f"{prefix}.sep1"),
                    _colored_field(
                        f"{prefix}.resolved_findings",
                        str(rule.resolved_findings),
                        _FIND_COUNT_COLOR,
                        compare=rule.resolved_findings,
                    ),
                    _literal("/", key=f"{prefix}.slash1"),
                    _field(
                        f"{prefix}.finding_count",
                        str(rule.finding_count),
                        compare=rule.finding_count,
                    ),
                )
            )
        )
    return tuple(lines)


def file_hotlist_text(view: RunViewState, *, limit: int = 5) -> str:
    if not view.coverage_projection.files:
        return "no file hot spots"
    return "\n".join(_format_file_summary(file) for file in view.coverage_projection.files[:limit])


def files_tui_lines(view: RunViewState, *, limit: int = 5) -> tuple[TuiLine, ...]:
    files = view.coverage_projection.files[:limit]
    if not files:
        return ()
    lines: list[TuiLine] = []
    for f_entry in files:
        prefix = f"file.{_activity_identity(TimelineEvent('', f_entry.file_path, ''))}"
        highest = f_entry.highest_priority_label
        lines.append(
            TuiLine(
                (
                    _colored_field(
                        f"{prefix}.priority",
                        highest,
                        _PRIORITY_COLORS.get(highest, ""),
                        compare=highest,
                    ),
                    _literal(" ", key=f"{prefix}.p_space"),
                    _field(
                        f"{prefix}.path",
                        _summarize_text(f_entry.file_path, limit=44),
                        compare=f_entry.file_path,
                    ),
                    _field(
                        f"{prefix}.reviewed",
                        f" {f_entry.reviewed}/{f_entry.total}",
                        compare=f_entry.reviewed,
                    ),
                    _literal(" · ", key=f"{prefix}.sep1"),
                    _colored_field(
                        f"{prefix}.resolved_findings",
                        str(f_entry.resolved_findings),
                        _FIND_COUNT_COLOR,
                        compare=f_entry.resolved_findings,
                    ),
                    _literal("/", key=f"{prefix}.slash1"),
                    _field(
                        f"{prefix}.finding_count",
                        str(f_entry.finding_count),
                        compare=f_entry.finding_count,
                    ),
                )
            )
        )
    return tuple(lines)


def finding_projection_text(view: RunViewState, *, limit: int = 5) -> str:
    findings = tuple(finding for finding in view.coverage_projection.findings if finding.actionable)
    if not findings:
        return "no open actionable findings"
    return "\n".join(_format_finding_summary(finding) for finding in findings[:limit])


def cells_text(
    view: RunViewState,
    filters: CoverageCellFilter | None = None,
    *,
    limit: int = 12,
) -> str:
    entries = filter_queue_entries(view.coverage_projection.queue, filters or CoverageCellFilter())
    if not entries:
        return "no cells match filters"
    return "\n".join(_format_cell_entry(entry) for entry in entries[:limit])


def _rules_panel_title(active_view: str) -> str:
    return {
        "overview": PANEL_TITLES["rules"],
        "files": PANEL_TITLES["files"],
        "rules": PANEL_TITLES["rules"],
        "cells": "Cells",
        "findings": "",
        "agent": "",
    }.get(active_view, PANEL_TITLES["rules"])


def _files_panel_title(active_view: str) -> str:
    return {
        "overview": PANEL_TITLES["files"],
        "files": "Selected file detail",
        "rules": "Selected rule detail",
        "cells": "",
        "findings": "",
        "agent": "",
    }.get(active_view, PANEL_TITLES["files"])


def findings_panel_title(view: RunViewState) -> str:
    if view.active_view == "agent":
        return PANEL_TITLES["agent"]
    if view.active_view not in {"overview", "findings"}:
        return ""
    if view.status == "running" and view.active_step_action == "run_review":
        return "Finding" + "." * (view.activity_frame % 4)
    progress = view.findings_progress
    return f"Findings {progress.resolved}/{progress.total}"


def _render_rules_panel(view: RunViewState, flashes: dict[str, TuiFlash]) -> Any:
    if view.active_view == "files":
        return render_tui_lines(files_tui_lines(view, limit=16), flashes, mode="rich")
    if view.active_view == "rules":
        return render_tui_lines(rules_tui_lines(view, limit=16), flashes, mode="rich")
    if view.active_view == "cells":
        return cells_text(view, limit=20)
    if view.active_view in ("findings", "agent"):
        return ""
    return render_tui_lines(rules_tui_lines(view, limit=5), flashes, mode="rich")


def _render_files_panel(view: RunViewState, flashes: dict[str, TuiFlash]) -> Any:
    if view.active_view == "files":
        return "select a file to see rule states"
    if view.active_view == "rules":
        return "select a rule to see file states"
    if view.active_view in ("cells", "findings", "agent"):
        return ""
    return render_tui_lines(files_tui_lines(view, limit=5), flashes, mode="rich")


def overview_text(view: RunViewState, *, width: int = 120) -> str:
    section_names = responsive_overview_sections(width)
    rendered: list[str] = []
    for name in section_names:
        if name == "status":
            rendered.append(header_text(view))
        elif name == "blockers":
            if view.state_class == "panel-blocked":
                active_gate = view.active_gate
                rendered.append(
                    titled_section("Finalize blocked", f"{active_gate.title}: {active_gate.detail}")
                )
        elif name == "queue":
            rendered.append(titled_section(PANEL_TITLES["queue"], queue_text(view)))
        elif name == "rules":
            rendered.append(titled_section(PANEL_TITLES["rules"], rule_coverage_text(view)))
        elif name == "files":
            rendered.append(titled_section(PANEL_TITLES["files"], file_hotlist_text(view)))
        elif name == "findings":
            rendered.append(
                titled_section(findings_panel_title(view), finding_projection_text(view))
            )
        elif name == "activity":
            rendered.append(titled_section(PANEL_TITLES["activity"], activity_text(view)))
    return "\n".join(part for part in rendered if part)


def responsive_overview_sections(width: int) -> tuple[str, ...]:
    if width >= 140:
        return ("status", "blockers", "queue", "rules", "files", "findings", "activity")
    if width >= 100:
        return ("status", "blockers", "queue", "rules", "files", "activity")
    return ("status", "blockers", "queue", "activity")


def active_detail_text(view: RunViewState) -> str:
    if view.active_view == "overview":
        return ""
    if view.active_view == "files":
        return file_hotlist_text(view, limit=12)
    if view.active_view == "rules":
        return rule_coverage_text(view, limit=12)
    if view.active_view == "cells":
        return cells_text(view, limit=16)
    if view.active_view == "findings":
        return finding_projection_text(view, limit=12)
    if view.active_view == "agent":
        return agent_summary_text(view)
    return ""


def _entry_is_actionable(entry: QueueEntry) -> bool:
    return entry.state in INCOMPLETE_COVERAGE_STATES or entry.actionable_finding_count > 0


def _format_cell_entry(entry: QueueEntry) -> str:
    finding = f" findings {entry.resolved_finding_count}/{entry.finding_count}"
    return (
        f"{entry.priority_label:<2} {entry.state:<8} {entry.rule_id:<18} "
        f"{_summarize_text(entry.file_path, limit=48)}{finding} · {entry.why}"
    )


def _format_rule_summary(rule: RuleCoverageSummary) -> str:
    return (
        f"{rule.priority_label} {rule.rule_id:<18} {rule.reviewed}/{rule.total} reviewed · "
        f"findings {rule.resolved_findings}/{rule.finding_count}"
    )


def _format_file_summary(file: FileCoverageSummary) -> str:
    return (
        f"{file.highest_priority_label} {_summarize_text(file.file_path, limit=48):<48} "
        f"{file.reviewed}/{file.total} reviewed · "
        f"findings {file.resolved_findings}/{file.finding_count}"
    )


def _format_finding_summary(finding: FindingSummaryEntry) -> str:
    cell = finding.latest_cell_id or "cell unknown"
    return (
        f"{finding.finding_id:<12} {finding.state:<28} {finding.rule_id:<18} "
        f"{_summarize_text(finding.file_path, limit=36)} · {cell} · "
        f"{_summarize_text(finding.content, limit=72)}"
    )


def findings_text(snapshot: RunSnapshot) -> str:
    summary = actionable_finding_summary(snapshot.findings)
    parts: list[str] = []
    for state in FINDING_STATES:
        label = state
        count = summary.open if state == "open" else _count_value(snapshot.findings.get(state, 0))
        parts.append(f"{label} {count}")
    return " | ".join(parts)


def agent_summary_text(view: RunViewState) -> str:
    lines = [
        f"command {view.agent_summary.command}",
        f"status  {view.agent_summary.status}",
        f"output  {view.agent_summary.output}",
        f"timeout {view.agent_summary.timeout}",
    ]
    if view.agent_summary.artifact is not None:
        lines.append(f"artifact {view.agent_summary.artifact}")
    return "\n".join(lines)


def session_summary_text(view: RunViewState) -> str:
    return "\n".join(
        [
            f"Coverage  {view.session_summary.coverage}",
            f"Findings  {view.session_summary.findings}",
            f"Current   {view.session_summary.current}",
            f"Agent step {view.session_summary.agent_step}",
        ]
    )


def current_operation_text(view: RunViewState) -> str:
    return agent_summary_text(view)


def _task_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    return current_operation_text(dashboard_state(snapshot, ()))


def agent_activity_text(agent_status: str, *, activity_frame: int = 0) -> str:
    if agent_status in {"running", "starting"}:
        return f"{_SPINNER_FRAMES[activity_frame % len(_SPINNER_FRAMES)]} {agent_status}"
    if agent_status == "quiet":
        return "quiet but alive"
    return f"· {_agent_status_label(_plain_text(agent_status))}"


def format_agent_output_entry(entry: AgentOutputEntry) -> TimelineEvent:
    label = "stderr" if entry.stream == "stderr" else "stdout"
    return TimelineEvent("--:--:--", label, sanitize_agent_output_line(entry.text))


def sanitize_agent_output_line(value: object, *, limit: int = 120) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))  # CSI sequences
    text = re.sub(
        r"\x1b\][^\x07\n\r]*(?:\x07|\x1b\\)", "", text
    )  # OSC sequences (e.g. terminal hyperlinks)
    text = text.replace("\r", "\n")
    text = " ".join(_plain_text(text).split())
    secret_patterns = (
        r"\b[A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD)=\S+",
        r"\b(?:authorization|x-api-key)\s*:\s*\S+(?:\s+\S+)?",
        r"[\"']?\b(?:api[_-]?key|token|secret|password)\b[\"']?\s*[:=]\s*[\"']?\S+[\"']?",
        r"\bBearer\s+[A-Za-z0-9+/=_\-.]+",
    )
    for pattern in secret_patterns:
        text = re.sub(pattern, "<redacted>", text, flags=re.IGNORECASE)
    return _summarize_text(text, limit=limit)


def format_activity_event(event: RunEvent) -> TimelineEvent:
    label = "event"
    detail = _event_label(event)
    event_detail = _event_detail(event)
    if event_detail:
        detail = f"{detail} {event_detail}"
    return TimelineEvent(format_event_time(event.timestamp), label, detail)


def activity_text(view: RunViewState) -> str:
    lines: list[str] = []
    if not view.timeline_events:
        lines.append("--:--:-- waiting for run activity")
    for event in view.timeline_events:
        suffix = f" - {event.detail}" if event.detail else ""
        lines.append(f"{event.time} {event.label}{suffix}")
    return "\n".join(lines)


def footer_text() -> str:
    return "q stop | r refresh | 1-5 views | Ctrl-C interrupt"


def color_legend_tui_lines() -> tuple[TuiLine, ...]:
    priority_fields = tuple(
        _colored_field(f"legend.priority.{label}", label, _PRIORITY_COLORS[label])
        for label in ("P0", "P1", "P2", "P3")
    )
    finding_state_fields = tuple(
        _colored_field(f"legend.finding_state.{state}", state, _FINDING_STATE_COLORS[state])
        for state in ("open", "confirmed", "dismissed")
    )
    progress_fields = (
        _colored_field("legend.progress.done", "done", _FIND_COUNT_COLOR),
        _literal(" / ", key="legend.progress.separator"),
        _colored_field("legend.progress.find", "find", _FIND_COUNT_COLOR),
    )
    return (
        TuiLine(
            (
                _literal("legend  priority ", key="legend.label.priority"),
                *_join_fields(priority_fields, " ", key_prefix="legend.priority.sep"),
                _literal(" | findings ", key="legend.label.findings"),
                *_join_fields(finding_state_fields, " ", key_prefix="legend.finding_state.sep"),
                _literal(" | progress ", key="legend.label.progress"),
                *progress_fields,
            )
        ),
    )


def _event_label(event: RunEvent) -> str:
    if event.type == "run_started":
        return "run started"
    if event.type == "status_refreshed":
        return "status refreshed"
    if event.type == "step_started":
        return f"step {_plain_text(event.payload.get('step', '?'))} started"
    if event.type == "agent_started":
        return "agent started"
    if event.type == "blocked":
        return "blocked"
    if event.type == "failed":
        return "failed"
    if event.type == "finalized":
        return "finalized"
    return _plain_text(event.type).replace("_", " ")


def _event_detail(event: RunEvent) -> str:
    if event.type in {"run_started", "status_refreshed", "blocked", "finalized"}:
        session_id = event.payload.get("session_id")
        reason = event.payload.get("reason")
        parts: list[str] = []
        if session_id is not None:
            parts.append(f"session {short_session_id(str(session_id))}")
        if reason is not None:
            parts.append(_summarize_text(reason, limit=48))
        return "; ".join(parts)
    if event.type == "step_started":
        action = event.payload.get("next_required_action")
        return format_task_title_from_action(
            str(action) if action is not None else None,
            {},
            {},
        ).title
    if event.type == "agent_started":
        label = event.payload.get("command_label")
        return _summarize_text(label, limit=64) if label is not None else "command resolving..."
    if event.type == "failed":
        return _summarize_text(event.payload.get("reason") or "command failed", limit=64)
    return ""


def _agent_text(snapshot: RunSnapshot) -> str:  # pyright: ignore[reportUnusedFunction]
    command = format_command_label(snapshot) or "command resolving..."
    return (
        "Agent\n"
        f"status={_plain_text(snapshot.agent_status)} step={snapshot.step} "
        f"elapsed={snapshot.elapsed_seconds:.1f}s\ncommand={command}"
    )


def _plain_text(value: object) -> str:
    return "".join(_plain_character(character) for character in str(value))


def _plain_character(character: str) -> str:
    if character in {"\n", "\r", "\t"}:
        return " "
    if ord(character) >= 32 and ord(character) != 127:
        return character
    return "�"


def _summarize_text(value: object, *, limit: int) -> str:
    text = " ".join(_plain_text(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)]}…"


def _progress_bar(completed: int, total: int) -> str:
    if total <= 0:
        return "[" + "·" * _BAR_WIDTH + "]"
    filled = min(_BAR_WIDTH, max(0, round((completed / total) * _BAR_WIDTH)))
    return "[" + "█" * filled + "░" * (_BAR_WIDTH - filled) + "]"


def _count_detail(count: int, singular: str, zero: str, *, plural: str | None = None) -> str:
    if count == 0:
        return zero
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural}" if plural is not None else f"{count} {singular}s"


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and not value.is_integer():
        return 0
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value))
        except (ValueError, OverflowError):
            return 0
    return 0
